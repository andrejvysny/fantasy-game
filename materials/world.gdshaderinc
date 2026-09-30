// Shared painted-light body; included by world.gdshader (culled) and world_double_sided.gdshader (foliage).
#include "res://materials/painted_light.gdshaderinc"

uniform vec4 albedo : source_color = vec4(1.0);
uniform bool use_vertex_color = true;
uniform bool flat_shading = false;
uniform bool dither_occlusion = false;
uniform float occlusion_radius = 2.5;
uniform float near_fade_start = 2.0;
uniform float near_fade_end = 4.0;
uniform float roughness : hint_range(0.0, 1.0) = 0.85;
// Keeps asset colours under the reserved gameplay colours' saturation (spec: saturation ceiling).
uniform float saturation : hint_range(0.0, 1.5) = 1.0;

const mat4 BAYER = mat4(
	vec4(0.0, 8.0, 2.0, 10.0),
	vec4(12.0, 4.0, 14.0, 6.0),
	vec4(3.0, 11.0, 1.0, 9.0),
	vec4(15.0, 7.0, 13.0, 5.0));

void vertex() {
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	world_normal = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
}

void fragment() {
	ALBEDO = albedo.rgb * (use_vertex_color ? COLOR.rgb : vec3(1.0));
	ALBEDO = mix(vec3(dot(ALBEDO, vec3(0.2126, 0.7152, 0.0722))), ALBEDO, saturation);
	ROUGHNESS = roughness;
	if (flat_shading) {
		NORMAL = normalize(cross(dFdx(VERTEX), dFdy(VERTEX)));
	}
	if (dither_occlusion) {
		vec3 cam = INV_VIEW_MATRIX[3].xyz;
		vec3 target = player_position + vec3(0.0, 1.0, 0.0);
		vec3 seg = target - cam;
		float t = clamp(dot(world_pos - cam, seg) / dot(seg, seg), 0.0, 1.0);
		float seg_dist = distance(world_pos, cam + seg * t);
		float cam_dist = distance(cam, world_pos);
		if (cam_dist < length(seg) - 0.5) {
			// Line-of-sight trees keep a faint 15% screen-door hint.
			float fade = (1.0 - smoothstep(occlusion_radius * 0.5, occlusion_radius, seg_dist)) * 0.85;
			// Anything hugging the lens fades out fully; a partial dither there covers the whole screen.
			fade = max(fade, 1.0 - smoothstep(near_fade_start, near_fade_end, cam_dist));
			ivec2 p = ivec2(FRAGCOORD.xy) & ivec2(3);
			float bayer = (BAYER[p.x][p.y] + 0.5) / 16.0;
			if (bayer < fade) {
				discard;
			}
		}
	}
}
