shader_type spatial;
render_mode diffuse_lambert, specular_disabled, cull_disabled, world_vertex_coords;

#include "res://materials/painted_light.gdshaderinc"
#include "res://materials/ground.gdshaderinc"

uniform float wind_strength = 0.12;
uniform float wind_speed = 1.3;
uniform float wind_scale = 0.15;
uniform float gust_scale = 0.02;
uniform float fade_start = 60.0;
uniform float fade_end = 80.0;
uniform float root_shade = 0.8;
uniform float tip_shade = 1.2;
uniform float tip_dry = 0.35;
uniform float bend_radius = 1.0;
uniform float bend_strength = 0.5;
uniform float up_normal_blend = 0.7;
// Matches focus_fog.gdshader fog_end: blades past the haze are not worth rasterising.
uniform float player_fade_end = 42.0;

varying vec3 root_pos;

void vertex() {
	root_pos = MODEL_MATRIX[3].xyz;
	float h = UV.y;
	float w = h * h;

	float gust = texture(cloud_noise, fract(root_pos.xz * gust_scale + TIME * vec2(0.03, 0.012))).r;
	float sway = sin(TIME * wind_speed + dot(root_pos.xz, vec2(1.0, 0.4)) * wind_scale) * 0.5 + 0.5;
	VERTEX.xz += normalize(vec2(1.0, 0.4)) * wind_strength * w * (0.4 + gust) * (0.5 + sway);

	vec2 d = root_pos.xz - player_position.xz;
	float k = (1.0 - smoothstep(0.0, bend_radius, length(d))) * bend_strength * w;
	VERTEX.xz += normalize(d + 1e-4) * k;
	VERTEX.y -= k * 0.5;

	// Shrink toward the root instead of alpha-fading so distant blades vanish without blending.
	float dist = distance(root_pos, INV_VIEW_MATRIX[3].xyz);
	float shrink = 1.0 - smoothstep(fade_start, fade_end, dist);
	shrink *= 1.0 - smoothstep(player_fade_end - 8.0, player_fade_end, distance(root_pos.xz, player_position.xz));
	VERTEX = root_pos + (VERTEX - root_pos) * shrink;

	NORMAL = normalize(mix(NORMAL, vec3(0.0, 1.0, 0.0), up_normal_blend));
	world_pos = VERTEX;
	world_normal = NORMAL;
}

void fragment() {
	vec3 base = ground_color(root_pos.xz, 0.0);
	base = mix(base, GROUND_DRY, tip_dry * UV.y);
	ALBEDO = base * mix(root_shade, tip_shade, UV.y) * COLOR.rgb;
	ROUGHNESS = 1.0;
}
