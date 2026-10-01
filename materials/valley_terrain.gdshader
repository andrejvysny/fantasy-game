shader_type spatial;
render_mode diffuse_lambert, specular_disabled;

#include "res://materials/painted_light.gdshaderinc"
#include "res://materials/ground.gdshaderinc"

// Valley terrain: flat grid chunks lifted by the heightmap (metres, 1 sample per metre,
// centred on the origin) and painted from three splat maps written by tools/terrain.
// splat_0 = water_deep, water_shallow, rock; splat_1 = sand, scree, dirt;
// splat_2 = forest_floor, grass_dry, grass. Grass, dry grass, forest floor and dirt use the
// WorldStyle palette globals so the valley follows the same style as the rest of the game.
uniform sampler2D heightmap : filter_linear, repeat_disable;
uniform sampler2D splat_0 : filter_linear, repeat_disable;
uniform sampler2D splat_1 : filter_linear, repeat_disable;
uniform sampler2D splat_2 : filter_linear, repeat_disable;
// Generator fields (tools/environment, same 1 m grid): ground r short grass, g tall grass,
// b wear (route core 1, shoulder ~0.5, painted paths ~0.6), a canopy / 1.5;
// habitat r forest, g rock exposure, b wetness, a fern.
uniform sampler2D field_ground : filter_linear, repeat_disable;
uniform sampler2D field_habitat : filter_linear, repeat_disable;
uniform bool use_fields = false;
// Bank character (tools/environment banks.py): r exposed gravel/soil at the water line, g rock bank,
// b sedge bank, a bank band. Replaces one uniform wet strip along every shore.
uniform sampler2D field_bank : filter_linear, repeat_disable;
uniform bool use_bank = false;
// The painted map's dry-grass and dirt layers are broad; read them as a drier meadow and as
// soil only where a path, bank or steep patch explains it (plan: no blanket dirt threshold).
uniform float dry_share : hint_range(0.0, 1.0) = 0.45;
uniform float stray_dirt_keep : hint_range(0.0, 1.0) = 0.3;
uniform vec4 path_color : source_color = vec4(0.541, 0.435, 0.322, 1.0);
uniform vec4 gravel_color : source_color = vec4(0.655, 0.616, 0.541, 1.0);
uniform vec4 wet_color : source_color = vec4(0.353, 0.333, 0.275, 1.0);
uniform float map_size = 1024.0;
uniform float roughness : hint_range(0.0, 1.0) = 0.9;
uniform vec4 rock_color : source_color = vec4(0.631, 0.616, 0.580, 1.0);
uniform vec4 scree_color : source_color = vec4(0.561, 0.545, 0.514, 1.0);
uniform vec4 sand_color : source_color = vec4(0.808, 0.741, 0.565, 1.0);
uniform vec4 water_shallow_color : source_color = vec4(0.478, 0.451, 0.353, 1.0); // submerged sediment; the blue comes from water.gdshader
uniform vec4 water_deep_color : source_color = vec4(0.204, 0.251, 0.243, 1.0);
// Rock reads as large angular planes: world-space cells each tilt the shading normal and shift
// the value slightly (replaces the old horizontal strata, which striped every hillside).
uniform float rock_cell = 5.0; // metres per fracture plane
uniform float rock_facet = 0.45; // normal tilt per plane
uniform float rock_value_jitter = 0.07;
uniform float rock_crack = 0.1; // restrained darkening where planes meet
uniform float rock_lichen = 0.25; // warm weathering on upward planes, per plane
uniform vec4 rock_light_color : source_color = vec4(0.706, 0.686, 0.643, 1.0);
uniform vec4 rock_lichen_color : source_color = vec4(0.667, 0.627, 0.549, 1.0);

vec2 map_uv(vec2 xz) {
	return (xz + (map_size - 1.0) * 0.5 + 0.5) / map_size;
}

vec3 hash33(vec3 p) {
	p = fract(p * vec3(0.1031, 0.1030, 0.0973));
	p += dot(p, p.yxz + 33.33);
	return fract((p.xxy + p.yxx) * p.zyx);
}

// Nearest and second-nearest cell distance plus the nearest cell's random vector.
// Cells are stretched vertically so faces break into tall planes rather than round dents.
vec4 rock_cells(vec3 p, out vec3 rnd) {
	vec3 q = p / vec3(rock_cell, rock_cell * 1.6, rock_cell);
	vec3 base = floor(q);
	float d1 = 8.0;
	float d2 = 8.0;
	rnd = vec3(0.5);
	for (int z = -1; z <= 1; z++) {
		for (int y = -1; y <= 1; y++) {
			for (int x = -1; x <= 1; x++) {
				vec3 c = base + vec3(float(x), float(y), float(z));
				vec3 h = hash33(c);
				float d = length(c + h - q);
				if (d < d1) {
					d2 = d1;
					d1 = d;
					rnd = h;
				} else if (d < d2) {
					d2 = d;
				}
			}
		}
	}
	return vec4(d1, d2, d2 - d1, 0.0);
}

float height_at(vec2 xz) {
	return textureLod(heightmap, map_uv(xz), 0.0).r;
}

void vertex() {
	vec2 xz = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xz;
	VERTEX.y = height_at(xz);
	float hl = height_at(xz - vec2(1.0, 0.0));
	float hr = height_at(xz + vec2(1.0, 0.0));
	float hd = height_at(xz - vec2(0.0, 1.0));
	float hu = height_at(xz + vec2(0.0, 1.0));
	NORMAL = normalize(vec3(hl - hr, 2.0, hd - hu));
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	world_normal = NORMAL;
}

// Path core = compacted soil with pale gravel drifts, shoulder = trampled meadow; both with
// noise-broken margins. Wetness lays a sediment band along inland banks.
vec3 apply_fields(vec3 col, vec2 uv, vec2 xz, float n, float water, vec3 forest) {
	vec4 g = texture(field_ground, uv);
	vec4 h = texture(field_habitat, uv);
	float core = smoothstep(0.62, 0.85, g.b + n * 0.25);
	float shoulder = smoothstep(0.25, 0.55, g.b + n * 0.3) * (1.0 - core);
	// Gravel in broad drifts along the walking line (~5 m), not a cobble speckle.
	float gravel = smoothstep(0.52, 0.72, texture(brush_noise, xz * 0.19 + vec2(0.13, 0.57)).r);
	vec3 path = mix(path_color.rgb, gravel_color.rgb, gravel * 0.4) * (1.0 + n * 0.12);
	col = mix(col, mix(ground_dry.rgb, path_color.rgb, 0.35), shoulder * 0.55);
	col = mix(col, path, core);
	float wet = smoothstep(0.35, 0.8, h.b + n * 0.3) * (1.0 - water);
	vec3 wet_tone = wet_color.rgb;
	if (use_bank) {
		vec4 b = texture(field_bank, uv);
		float stony = clamp(b.r + b.g * b.a, 0.0, 1.0);
		wet *= mix(1.0, 0.35, stony);
		wet_tone = mix(wet_color.rgb, mix(wet_color.rgb, ground_moss.rgb, 0.35), b.b);
		float gravel_bank = smoothstep(0.3, 0.75, b.r + n * 0.3);
		col = mix(col, gravel_color.rgb * (1.0 + n * 0.15), gravel_bank * 0.75);
		col = mix(col, scree_color.rgb, b.g * b.a * 0.3);
	}
	col = mix(col, wet_tone, wet * 0.6);
	// Litter only under real crown cover, broken by noise so trees do not stamp rings.
	float canopy = g.a * 1.5;
	col = mix(col, forest, smoothstep(0.9, 1.3, canopy + n * 0.5) * 0.45 * (1.0 - core));
	return col;
}

void fragment() {
	vec2 xz = world_pos.xz;
	vec2 uv = map_uv(xz);
	vec3 s0 = texture(splat_0, uv).rgb;
	vec3 s1 = texture(splat_1, uv).rgb;
	vec3 s2 = texture(splat_2, uv).rgb;
	float n = texture(brush_noise, xz * 0.08).r - 0.5;
	float macro = texture(cloud_noise, xz * 0.011 + vec2(0.37, 0.71)).r;
	float litter = smoothstep(0.45, 0.7, macro + n * 0.3);
	if (use_fields) {
		// Brown litter needs crowns overhead; open forest-floor stays moss green.
		litter *= smoothstep(0.35, 1.0, texture(field_ground, uv).a * 1.5 + n * 0.4);
	}
	vec3 forest = mix(ground_moss.rgb, ground_litter.rgb, litter);
	float rocky = s0.b + s1.g * 0.5;
	vec3 rock = rock_color.rgb;
	vec3 scree = scree_color.rgb;
	vec3 facet_n = world_normal;
	if (rocky > 0.02) {
		vec3 rnd;
		vec4 cells = rock_cells(world_pos, rnd);
		vec3 tilt = (rnd - 0.5) * 2.0 * rock_facet;
		facet_n = normalize(world_normal + tilt * rocky);
		float edge = 1.0 - smoothstep(0.0, 0.12, cells.z);
		float up = smoothstep(0.55, 0.85, facet_n.y) * step(0.55, rnd.y);
		rock = mix(rock_color.rgb, rock_light_color.rgb, rnd.x) * (1.0 + (rnd.z - 0.5) * 2.0 * rock_value_jitter);
		rock = mix(rock, rock_lichen_color.rgb, up * rock_lichen) * (1.0 - edge * rock_crack);
		scree = mix(scree, rock, 0.35);
	}
	float dirt_keep = 1.0;
	float dry = s2.g;
	if (use_fields) {
		float wear = texture(field_ground, uv).b;
		float wet = texture(field_habitat, uv).b;
		dirt_keep = max(stray_dirt_keep, max(smoothstep(0.35, 0.6, wear), smoothstep(0.3, 0.7, wet)));
		dry = s2.g * dry_share;
	}
	float plant_total = s2.r + s2.b + 1e-4;
	vec3 plant = mix(ground_meadow.rgb, forest, s2.r / plant_total);
	vec3 col = water_deep_color.rgb * s0.r
		+ water_shallow_color.rgb * s0.g
		+ rock * s0.b
		+ sand_color.rgb * s1.r
		+ scree * s1.g
		+ ground_dirt.rgb * s1.b * dirt_keep + plant * s1.b * (1.0 - dirt_keep)
		+ forest * s2.r
		+ ground_dry.rgb * dry + ground_meadow.rgb * (s2.g - dry)
		+ ground_meadow.rgb * s2.b;
	// Splat weights are 8-bit; renormalise so rounding never darkens the ground.
	col /= max(dot(s0 + s1 + s2, vec3(1.0)), 0.05);
	float water = s0.r + s0.g;
	if (use_fields) {
		col = apply_fields(col, uv, xz, n, water, forest);
	}
	ALBEDO = col * mix(ground_mottle(xz), 1.0 + n * 0.04, water);
	ROUGHNESS = mix(roughness, 0.3, water);
	if (rocky > 0.02) {
		NORMAL = normalize((VIEW_MATRIX * vec4(facet_n, 0.0)).xyz);
	}
}
