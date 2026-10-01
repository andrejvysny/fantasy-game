shader_type spatial;
render_mode diffuse_lambert, specular_disabled, cull_disabled, world_vertex_coords;

#include "res://materials/painted_light.gdshaderinc"
#include "res://materials/ground.gdshaderinc"
#include "res://materials/wind.gdshaderinc"

uniform float wind_strength = 0.12; // response to the world wind field, metres at blade tips
uniform float wind_speed = 1.0; // tempo multiplier on the global wind
uniform float fade_start = 60.0;
uniform float fade_end = 80.0;
uniform float root_shade = 0.9;
uniform float tip_shade = 1.05;
uniform float tip_dry = 0.12;
uniform float bend_radius = 1.0;
uniform float bend_strength = 0.5;
uniform float up_normal_blend = 0.7;
// Blades far from the player shrink away; grass shares the ground colour, so the edge
// reads as a meadow thinning into the ground rather than a boundary.
uniform float player_fade_end = 64.0;
uniform float player_fade_width = 16.0;

varying vec3 root_pos;
// Per-clump constant, so sampled once per vertex instead of per fragment.
varying vec3 ground_col;

void vertex() {
	root_pos = MODEL_MATRIX[3].xyz;
	ground_col = ground_color(root_pos.xz, 0.0);
	float h = UV.y;
	float w = h * h;

	VERTEX.xz += wind.xy * wind_strength * w * wind_gust(root_pos.xz, TIME, 0.0, wind_speed);

	vec2 d = root_pos.xz - player_position.xz;
	float k = (1.0 - smoothstep(0.0, bend_radius, length(d))) * bend_strength * w;
	VERTEX.xz += normalize(d + 1e-4) * k;
	VERTEX.y -= k * 0.5;

	// Shrink toward the root instead of alpha-fading so distant blades vanish without blending.
	float dist = distance(root_pos, INV_VIEW_MATRIX[3].xyz);
	float shrink = 1.0 - smoothstep(fade_start, fade_end, dist);
	shrink *= 1.0 - smoothstep(player_fade_end - player_fade_width, player_fade_end, distance(root_pos.xz, player_position.xz));
	VERTEX = root_pos + (VERTEX - root_pos) * shrink;

	NORMAL = normalize(mix(NORMAL, vec3(0.0, 1.0, 0.0), up_normal_blend));
	world_pos = VERTEX;
	world_normal = NORMAL;
}

void fragment() {
	vec3 base = ground_col;
	base = mix(base, ground_dry.rgb, tip_dry * UV.y);
	ALBEDO = base * mix(root_shade, tip_shade, UV.y) * COLOR.rgb;
	// Two-sided policy: both faces of a blade share the front, up-bent normal. Godot flips
	// NORMAL on back faces of cull_disabled meshes, which points half the blades at the
	// ground and paints them as dark pickets against lit soil.
	NORMAL = normalize((VIEW_MATRIX * vec4(world_normal, 0.0)).xyz);
	ROUGHNESS = 1.0;
}
