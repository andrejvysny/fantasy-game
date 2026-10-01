shader_type spatial;
render_mode diffuse_lambert, specular_disabled, cull_disabled;

#include "res://materials/painted_light.gdshaderinc"
#include "res://materials/ground.gdshaderinc"
#include "res://materials/wind.gdshaderinc"

// GPU-scattered groundcover (scripts/valley_groundcover.gd). The MultiMesh holds identity
// instances; INSTANCE_ID picks a world cell around the node origin (camera snapped to the
// spacing), and everything else comes from a hash of that cell, so a clump never moves when
// the camera does. Killed instances collapse to a point (zero-area triangles).
// Every kill is a smooth shrink (static fields) or a hash threshold swept by camera distance,
// so nothing pops and nothing alpha-fades.
uniform sampler2D heightmap : filter_linear, repeat_disable;
uniform sampler2D splat_0 : filter_linear, repeat_disable; // r+g = water
uniform sampler2D splat_2 : filter_linear, repeat_disable; // r forest floor, g grass_dry, b grass
uniform sampler2D ground_field : filter_linear, repeat_disable; // r short, g tall, b wear, a canopy/1.5
uniform sampler2D layer_field : filter_linear, repeat_disable;
uniform bool field_is_ground = true;
uniform vec4 channel_mask = vec4(1.0, 0.0, 0.0, 0.0);
uniform float map_size = 1024.0;
uniform int grid_n = 1;
uniform float spacing = 0.5;
uniform float radius = 30.0;
// Ring hand-off bands (start, end) in metres from the camera; end <= start disables a band.
uniform vec2 band_in = vec2(0.0);
uniform vec2 band_out = vec2(0.0);
uniform float thin_start = 12.0;
uniform float far_keep = 0.6;
uniform float density = 1.0;
uniform float scale_min = 0.8;
uniform float scale_max = 1.2;
uniform float max_slope = 0.8;
uniform float palette_strength = 0.7;
uniform float wind_amplitude = 0.04; // per-layer response to the world wind field, metres at flex 1
uniform int seed = 1;
uniform float tilt_follow = 0.6; // share of the terrain normal in the clump's up axis
uniform float ground_normal_share = 0.7; // share of the terrain normal in the shading normal
uniform float sink = 0.02; // bilinear heights sit a little above the terrain's triangles
uniform float keep_soft = 0.12; // hash margin over which a clump grows from zero
uniform float bend_radius = 0.9;
uniform float bend_strength = 0.2;
uniform float dry_share = 0.35; // dry splat only leans the grass, dry areas stay green-leaning
uniform float value_scale = 11.0; // metres per shade patch, shared by neighbouring clumps
uniform float value_strength = 0.1;
uniform bool plain = false; // debug: asset colour only
uniform bool patch_only = false; // debug: a single full-density square patch
uniform vec4 patch_rect = vec4(0.0); // min xz, max xz

const float HANDOFF_SOFT = 0.35; // share of a band over which one clump grows or shrinks

varying vec3 tint;

uvec3 pcg3d(uvec3 v) {
	v = v * 1664525u + 1013904223u;
	v.x += v.y * v.z;
	v.y += v.z * v.x;
	v.z += v.x * v.y;
	v = v ^ (v >> uvec3(16u));
	v.x += v.y * v.z;
	v.y += v.z * v.x;
	v.z += v.x * v.y;
	return v;
}

vec3 rand3(ivec2 c, uint salt) {
	uvec3 h = pcg3d(uvec3(uint(c.x), uint(c.y), uint(seed) * 747796405u + salt));
	return vec3(h >> uvec3(8u)) / 16777216.0;
}

vec2 map_uv(vec2 xz) {
	return (xz + (map_size - 1.0) * 0.5 + 0.5) / map_size;
}

float height_at(vec2 xz) {
	return textureLod(heightmap, map_uv(xz), 0.0).r;
}

// Minimal rotation taking +Y to n.
mat3 up_to(vec3 n) {
	float f = 1.0 / (1.0 + n.y);
	return mat3(vec3(1.0 - n.x * n.x * f, -n.x, -n.x * n.z * f), n, vec3(-n.x * n.z * f, -n.z, 1.0 - n.z * n.z * f));
}

// Size factor from the camera-distance bands. h is the cell's hand-off hash: over a band the
// threshold sweeps through [0, 1], so the inner ring loses exactly the cells the outer gains.
float ring_factor(float d, float h) {
	float k = 1.0 - step(radius, d);
	if (band_in.y > band_in.x) {
		float t = clamp((d - band_in.x) / (band_in.y - band_in.x), 0.0, 1.0) * (1.0 + HANDOFF_SOFT) - HANDOFF_SOFT;
		k *= clamp((t + HANDOFF_SOFT - h) / HANDOFF_SOFT, 0.0, 1.0);
	}
	if (band_out.y > band_out.x) {
		float t = clamp((d - band_out.x) / (band_out.y - band_out.x), 0.0, 1.0) * (1.0 + HANDOFF_SOFT) - HANDOFF_SOFT;
		k *= clamp((h - t) / HANDOFF_SOFT, 0.0, 1.0);
	} else {
		k *= 1.0 - smoothstep(radius * 0.85, radius, d);
	}
	return k;
}

// Field density, distance thinning, path wear and water; returns the size factor.
float field_factor(vec2 p, float d, float h) {
	vec2 uv = map_uv(p);
	vec4 g = textureLod(ground_field, uv, 0.0);
	vec4 f = field_is_ground ? g : textureLod(layer_field, uv, 0.0);
	float keep = dot(f, channel_mask) * density * mix(1.0, far_keep, smoothstep(thin_start, radius, d));
	float k = clamp((keep - h) / keep_soft, 0.0, 1.0);
	k *= 1.0 - smoothstep(0.55, 0.7, g.b);
	vec2 water = textureLod(splat_0, uv, 0.0).rg;
	return k * (1.0 - smoothstep(0.005, 0.02, water.r + water.g));
}

vec3 palette_tint(vec3 base, vec2 p) {
	if (plain) {
		return base;
	}
	const vec3 LUMA = vec3(0.2126, 0.7152, 0.0722);
	// Follow the terrain layer beneath (splat_2: forest floor, dry, grass) so sparse tufts on
	// moss share its darker colour instead of dotting it with meadow green.
	vec3 w = textureLod(splat_2, map_uv(p), 0.0).rgb;
	vec3 dry = mix(ground_meadow.rgb, ground_dry.rgb, dry_share);
	// Forest floor as valley_terrain.gdshader paints it (moss/litter by macro noise), kept a
	// little greener: grass on litter is still grass.
	float n = textureLod(brush_noise, p * 0.08, 0.0).r - 0.5;
	float macro = textureLod(cloud_noise, p * 0.011 + vec2(0.37, 0.71), 0.0).r;
	vec3 forest = mix(ground_moss.rgb, ground_litter.rgb, smoothstep(0.45, 0.7, macro + n * 0.3) * 0.7);
	vec3 layered = (forest * w.r + dry * w.g + ground_meadow.rgb * w.b) / max(w.r + w.g + w.b, 1e-3);
	vec3 target = mix(ground_meadow.rgb, layered, smoothstep(0.0, 0.1, w.r + w.g + w.b));
	// Keep the asset's root-to-tip value, take the hue from the palette.
	// Capped so sunlit tips stay near the ground value: bright tips read as speckle, not meadow.
	float shade = clamp(dot(base, LUMA) / max(dot(ground_meadow.rgb, LUMA), 1e-3), 0.5, 1.25);
	vec3 c = mix(base, target * shade, palette_strength);
	return c * (1.0 + (textureLod(brush_noise, p / value_scale, 0.0).r - 0.5) * 2.0 * value_strength);
}

void vertex() {
	ivec2 base = ivec2(round(MODEL_MATRIX[3].xz / spacing));
	ivec2 cell = base + ivec2(INSTANCE_ID % grid_n, INSTANCE_ID / grid_n) - grid_n / 2;
	vec3 r0 = rand3(cell, 0u); // jitter x, jitter z, keep
	vec3 r1 = rand3(cell, 7919u); // yaw, scale, hand-off
	vec2 p = (vec2(cell) + r0.xy - 0.5) * spacing;
	float d = distance(p, CAMERA_POSITION_WORLD.xz);
	float k = ring_factor(d, r1.z);
	if (patch_only) {
		// Shape diagnostic: every cell of the square, whatever the fields say (spawn is a path).
		k *= float(all(greaterThanEqual(p, patch_rect.xy)) && all(lessThan(p, patch_rect.zw)));
	} else if (k > 0.0) {
		k *= field_factor(p, d, r0.z);
	}
	float hc = 0.0;
	vec3 tn = vec3(0.0, 1.0, 0.0);
	if (k > 0.0) {
		// Forward differences over 1 m: three fetches per vertex instead of five.
		hc = height_at(p);
		vec2 grad = vec2(height_at(p + vec2(1.0, 0.0)), height_at(p + vec2(0.0, 1.0))) - hc;
		tn = normalize(vec3(-grad.x, 1.0, -grad.y));
		k *= 1.0 - smoothstep(max_slope * 0.75, max_slope, length(grad));
	}
	if (k <= 0.0) {
		VERTEX = vec3(0.0);
	} else {
		float yaw = r1.x * TAU;
		mat3 spin = mat3(vec3(cos(yaw), 0.0, -sin(yaw)), vec3(0.0, 1.0, 0.0), vec3(sin(yaw), 0.0, cos(yaw)));
		mat3 basis = up_to(normalize(mix(vec3(0.0, 1.0, 0.0), tn, tilt_follow))) * spin;
		vec3 v = basis * (VERTEX * mix(scale_min, scale_max, r1.y) * k);
		// World wind field (wind.gdshaderinc): crests travel downwind, gust patches drift across.
		vec2 push = wind.xy * wind_amplitude * wind_gust(p, TIME, 0.0, 1.0);
		vec2 away = p - player_position.xz;
		push += normalize(away + 1e-4) * (1.0 - smoothstep(0.15, bend_radius, length(away))) * bend_strength;
		v.xz += push * COLOR.a;
		v.y -= length(push) * COLOR.a * 0.4;
		vec3 wpos = vec3(p.x, hc - sink, p.y) + v;
		VERTEX = wpos - MODEL_MATRIX[3].xyz;
		// Mostly the terrain normal: the painted light bands by N.L, so clumps must fall in the
		// same band as the ground under them, or a slope in the half-lit band gets bright dots.
		NORMAL = normalize(mix(basis * NORMAL, tn, ground_normal_share));
		world_pos = wpos;
		world_normal = NORMAL;
		tint = palette_tint(COLOR.rgb, p);
	}
}

void fragment() {
	ALBEDO = tint;
	// Two-sided policy (grass.gdshader): both faces keep the front, up-blended normal.
	NORMAL = normalize((VIEW_MATRIX * vec4(world_normal, 0.0)).xyz);
	ROUGHNESS = 1.0;
}
