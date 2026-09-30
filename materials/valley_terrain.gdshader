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
uniform float map_size = 1024.0;
uniform float roughness : hint_range(0.0, 1.0) = 0.9;
uniform vec4 rock_color : source_color = vec4(0.455, 0.439, 0.404, 1.0);
uniform vec4 scree_color : source_color = vec4(0.537, 0.502, 0.427, 1.0);
uniform vec4 sand_color : source_color = vec4(0.808, 0.741, 0.565, 1.0);
uniform vec4 water_shallow_color : source_color = vec4(0.216, 0.416, 0.455, 1.0);
uniform vec4 water_deep_color : source_color = vec4(0.090, 0.224, 0.322, 1.0);
uniform float rock_strata = 0.12; // horizontal banding on cliff faces

vec2 map_uv(vec2 xz) {
	return (xz + (map_size - 1.0) * 0.5 + 0.5) / map_size;
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

void fragment() {
	vec2 xz = world_pos.xz;
	vec2 uv = map_uv(xz);
	vec3 s0 = texture(splat_0, uv).rgb;
	vec3 s1 = texture(splat_1, uv).rgb;
	vec3 s2 = texture(splat_2, uv).rgb;
	float n = texture(brush_noise, fract(xz * 0.08)).r - 0.5;
	float macro = texture(cloud_noise, fract(xz * 0.011 + vec2(0.37, 0.71))).r;
	vec3 forest = mix(ground_moss.rgb, ground_litter.rgb, smoothstep(0.45, 0.7, macro + n * 0.3));
	float strata = sin(world_pos.y * 1.7 + n * 3.0) * rock_strata;
	vec3 col = water_deep_color.rgb * s0.r
		+ water_shallow_color.rgb * s0.g
		+ rock_color.rgb * (1.0 + strata) * s0.b
		+ sand_color.rgb * s1.r
		+ scree_color.rgb * s1.g
		+ ground_dirt.rgb * s1.b
		+ forest * s2.r
		+ ground_dry.rgb * s2.g
		+ ground_meadow.rgb * s2.b;
	// Splat weights are 8-bit; renormalise so rounding never darkens the ground.
	col /= max(dot(s0 + s1 + s2, vec3(1.0)), 0.05);
	float water = s0.r + s0.g;
	ALBEDO = col * mix(ground_mottle(xz), 1.0 + n * 0.04, water);
	ROUGHNESS = mix(roughness, 0.3, water);
}
