// Shared painted-light body; included by world.gdshader (culled) and world_double_sided.gdshader (foliage).
#define PAINTED_BACKLIGHT
#include "res://materials/painted_light.gdshaderinc"

global uniform vec4 ground_moss; // linear, pushed by WorldStyle

uniform vec4 albedo : source_color = vec4(1.0);
uniform bool use_vertex_color = true;
uniform bool flat_shading = false;
uniform bool dither_occlusion = false;
uniform float occlusion_radius = 2.5;
uniform float occlusion_ghost = 0.0; // coverage kept on line-of-sight trees
uniform float near_fade_start = 2.0;
uniform float near_fade_end = 4.0;
uniform float roughness : hint_range(0.0, 1.0) = 0.85;
// Keeps asset colours under the reserved gameplay colours' saturation (spec: saturation ceiling).
uniform float saturation : hint_range(0.0, 1.5) = 1.0;
// Foliage profile. Foliage vs bark comes from vertex colour (needles are green-dominant).
uniform float canopy_normal_blend : hint_range(0.0, 1.0) = 0.0; // pulls facet normals toward the crown volume
uniform float canopy_up = 0.6; // upward tilt of crown normals (spruce cone)
uniform float foliage_translucency : hint_range(0.0, 1.0) = 0.0;
uniform float tree_variation : hint_range(0.0, 0.3) = 0.0; // per-tree hue/value jitter
// Stone profile: broad moss on up-facing surfaces.
uniform float moss_top : hint_range(0.0, 1.0) = 0.0;

varying float foliage;
varying float tree_seed;

float hash12(vec2 p) {
	vec3 p3 = fract(vec3(p.xyx) * 0.1031);
	p3 += dot(p3, p3.yzx + 33.33);
	return fract((p3.x + p3.y) * p3.z);
}

void vertex() {
	foliage = use_vertex_color ? smoothstep(0.0, 0.04, COLOR.g - COLOR.r) : 0.0;
	if (canopy_normal_blend > 0.0) {
		// Object origin sits at the trunk base, so the crown normal is radial plus an upward tilt.
		vec3 crown = normalize(vec3(VERTEX.x, length(VERTEX.xz) * canopy_up + 0.1, VERTEX.z));
		NORMAL = normalize(mix(NORMAL, crown, canopy_normal_blend * foliage));
	}
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	world_normal = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
	tree_seed = hash12(MODEL_MATRIX[3].xz);
	translucency = foliage * foliage_translucency;
}

// Interleaved gradient noise: finer and less patterned than a 4x4 Bayer screen door.
float ign(vec2 p) {
	return fract(52.9829189 * fract(dot(p, vec2(0.06711056, 0.00583715))));
}

// Coverage to remove (0..1) for fragments between the camera and the player.
float occlusion_fade(vec3 cam) {
	vec3 target = player_position + vec3(0.0, 1.0, 0.0);
	vec3 seg = target - cam;
	float t = clamp(dot(world_pos - cam, seg) / dot(seg, seg), 0.0, 1.0);
	float seg_dist = distance(world_pos, cam + seg * t);
	float cam_dist = distance(cam, world_pos);
	if (cam_dist >= length(seg) - 0.5) {
		return 0.0;
	}
	float fade = (1.0 - smoothstep(occlusion_radius * 0.6, occlusion_radius, seg_dist)) * (1.0 - occlusion_ghost);
	// Anything hugging the lens fades out fully; a partial dither there covers the whole screen.
	return max(fade, 1.0 - smoothstep(near_fade_start, near_fade_end, cam_dist));
}

void fragment() {
	vec3 col = albedo.rgb * (use_vertex_color ? COLOR.rgb : vec3(1.0));
	// Whole-tree variation keeps each crown one colour family instead of speckling every tier.
	float v = (tree_seed - 0.5) * 2.0 * tree_variation * foliage;
	col *= vec3(1.0 + v * 0.6, 1.0 + v * 0.25, 1.0 - v * 0.5) * (1.0 + v * 0.5);
	col = mix(vec3(dot(col, vec3(0.2126, 0.7152, 0.0722))), col, saturation);
	if (moss_top > 0.0) {
		float up = world_normal.y + (texture(brush_noise, fract(world_pos.xz * 0.6)).r - 0.5) * 0.5;
		col = mix(col, ground_moss.rgb, moss_top * smoothstep(0.45, 0.75, up));
	}
	ALBEDO = col;
	ROUGHNESS = roughness;
	if (flat_shading) {
		NORMAL = normalize(cross(dFdx(VERTEX), dFdy(VERTEX)));
	}
	// Shadow pass sees the light's view, not the player camera: never cut holes in shadow maps.
	if (dither_occlusion && !IN_SHADOW_PASS && ign(FRAGCOORD.xy) < occlusion_fade(CAMERA_POSITION_WORLD)) {
		discard;
	}
}
