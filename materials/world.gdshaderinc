// Shared painted-light body; included by world.gdshader (culled) and world_double_sided.gdshader (foliage).
#define PAINTED_BACKLIGHT
#include "res://materials/painted_light.gdshaderinc"
#include "res://materials/wind.gdshaderinc"

global uniform vec4 ground_moss; // linear, pushed by WorldStyle

uniform vec4 albedo : source_color = vec4(1.0);
uniform bool use_vertex_color = true;
uniform bool flat_shading = false;
uniform bool dither_occlusion = false;
uniform float occlusion_radius = 2.5;
uniform float occlusion_ghost = 0.0; // coverage kept on line-of-sight trees
uniform float near_fade_start = 0.6; // lens-only safety band; whole trees are removed by tree_occluder.gd
uniform float near_fade_end = 1.2;
uniform int occlusion_mode : hint_enum("Per object", "Spatial") = 0;
// Per-object fade for MeshInstance3D trees (forest scene). MultiMesh shaders define WORLD_MULTIMESH:
// every instance uniform takes a slot in a global buffer per geometry instance, and the valley's
// thousands of chunks only ever use INSTANCE_CUSTOM.
#ifndef WORLD_MULTIMESH
instance uniform float occluder_fade = 0.0; // coverage to remove, driven per tree by tree_occluder.gd
#endif
uniform bool use_instance_fade = false; // MultiMesh: fade arrives in INSTANCE_CUSTOM.r instead
uniform float roughness : hint_range(0.0, 1.0) = 0.85;
// Keeps asset colours under the reserved gameplay colours' saturation (spec: saturation ceiling).
uniform float saturation : hint_range(0.0, 1.5) = 1.0;
// Foliage profile. Legacy spruce library: foliage vs bark inferred from vertex colour (needles are
// green-dominant). Nature assets (assets/nature, contract in its README) instead name the surface
// (M_solid / M_foliage) and the loader sets foliage_source = Constant on that surface's material.
uniform int foliage_source : hint_enum("Vertex colour heuristic", "Constant") = 0;
uniform float foliage_constant : hint_range(0.0, 1.0) = 0.0;
// Nature-asset channels: COLOR.a = flex weight (0 anchored .. 1 free tip), UV2.x = cavity,
// UV2.y = per-part random. Legacy meshes have neither, so all three default to off.
uniform float wind_sway = 0.0; // response: metres of sway at flex 1 and wind strength 1; 0 = static
uniform vec2 wind_dir = vec2(0.8, 0.6); // unused: direction comes from the global wind field
uniform float wind_speed = 1.0; // tempo multiplier on the global wind (1 = in step with the grass)
uniform float cavity_strength : hint_range(0.0, 1.0) = 0.0;
uniform float part_variation : hint_range(0.0, 0.5) = 0.0;
uniform float canopy_normal_blend : hint_range(0.0, 1.0) = 0.0; // pulls facet normals toward the crown volume
uniform float canopy_up = 0.6; // upward tilt of crown normals (spruce cone)
uniform float foliage_translucency : hint_range(0.0, 1.0) = 0.0;
uniform float tree_variation : hint_range(0.0, 0.3) = 0.0; // per-tree hue/value jitter
// Stone profile: broad moss on up-facing surfaces.
uniform float moss_top : hint_range(0.0, 1.0) = 0.0;

varying float foliage;
varying float tree_seed;
varying float inst_fade;
varying float cavity;
varying float part_rnd;

float hash12(vec2 p) {
	vec3 p3 = fract(vec3(p.xyx) * 0.1031);
	p3 += dot(p3, p3.yzx + 33.33);
	return fract((p3.x + p3.y) * p3.z);
}

// World wind field (wind.gdshaderinc) sampled at the object root, so a whole plant moves as one;
// roots (flex 0) never move. Offset is built in world space and taken back to object space
// (rotation + uniform scale: inverse = transpose / scale^2).
vec3 wind_offset(mat4 model, float flex, float time) {
	vec3 root = model[3].xyz;
	float gust = wind_gust(root.xz, time, hash12(root.xz) * 1.3, wind_speed);
	vec3 w = vec3(wind.x, 0.0, wind.y) * gust * wind_sway * flex * flex;
	mat3 m = mat3(model);
	return transpose(m) * w / max(dot(m[0], m[0]), 1e-4);
}

void vertex() {
	float heuristic = use_vertex_color ? smoothstep(0.0, 0.04, COLOR.g - COLOR.r) : 0.0;
	foliage = foliage_source == 1 ? foliage_constant : heuristic;
	cavity = mix(1.0, UV2.x, cavity_strength);
	part_rnd = UV2.y;
	if (wind_sway > 0.0) {
		VERTEX += wind_offset(MODEL_MATRIX, COLOR.a, TIME);
	}
	if (canopy_normal_blend > 0.0) {
		// Object origin sits at the trunk base, so the crown normal is radial plus an upward tilt.
		vec3 crown = normalize(vec3(VERTEX.x, length(VERTEX.xz) * canopy_up + 0.1, VERTEX.z));
		NORMAL = normalize(mix(NORMAL, crown, canopy_normal_blend * foliage));
	}
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	world_normal = normalize(MODEL_NORMAL_MATRIX * NORMAL);
	tree_seed = hash12(MODEL_MATRIX[3].xz);
	inst_fade = use_instance_fade ? INSTANCE_CUSTOM.r : 0.0;
	translucency = foliage * foliage_translucency;
}

// Interleaved gradient noise: finer and less patterned than a 4x4 Bayer screen door.
float ign(vec2 p) {
	return fract(52.9829189 * fract(dot(p, vec2(0.06711056, 0.00583715))));
}

// Legacy spatial path (occlusion_mode 1): coverage for fragments near the camera-player segment.
float spatial_fade(vec3 cam, float cam_dist) {
	vec3 target = player_position + vec3(0.0, 1.0, 0.0);
	vec3 seg = target - cam;
	float t = clamp(dot(world_pos - cam, seg) / dot(seg, seg), 0.0, 1.0);
	float seg_dist = distance(world_pos, cam + seg * t);
	if (cam_dist >= length(seg) - 0.5) {
		return 0.0;
	}
	return (1.0 - smoothstep(occlusion_radius * 0.85, occlusion_radius, seg_dist)) * (1.0 - occlusion_ghost);
}

// Coverage to remove (0..1). Anything hugging the lens fades out fully; a partial dither there covers the whole screen.
float occlusion_fade(vec3 cam) {
	float cam_dist = distance(cam, world_pos);
	float near = 1.0 - smoothstep(near_fade_start, near_fade_end, cam_dist);
#ifdef WORLD_MULTIMESH
	float object_fade = inst_fade;
#else
	float object_fade = max(occluder_fade, inst_fade);
#endif
	return max(near, occlusion_mode == 1 ? spatial_fade(cam, cam_dist) : object_fade);
}

void fragment() {
	vec3 col = albedo.rgb * (use_vertex_color ? COLOR.rgb : vec3(1.0)) * cavity;
	col *= 1.0 + (part_rnd - 0.5) * 2.0 * part_variation;
	// Whole-tree variation keeps each crown one colour family instead of speckling every tier.
	float v = (tree_seed - 0.5) * 2.0 * tree_variation * foliage;
	col *= vec3(1.0 + v * 0.6, 1.0 + v * 0.25, 1.0 - v * 0.5) * (1.0 + v * 0.5);
	col = mix(vec3(dot(col, vec3(0.2126, 0.7152, 0.0722))), col, saturation);
	if (moss_top > 0.0) {
		// Moss follows the normal that shades the surface: facets when flat-shaded, so a
		// mossy top is always a lit top instead of straddling facet edges.
		vec3 n = flat_shading ? normalize(cross(dFdx(world_pos), dFdy(world_pos))) : normalize(world_normal);
		float up = n.y + (texture(brush_noise, world_pos.xz * 0.6).r - 0.5) * 0.5;
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
