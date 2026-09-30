shader_type spatial;
render_mode diffuse_lambert, specular_disabled;

#include "res://materials/painted_light.gdshaderinc"
#include "res://materials/ground.gdshaderinc"

uniform float roughness : hint_range(0.0, 1.0) = 0.9;
// Optional albedo texture per ground layer (CC0 sets can be dropped in later).
// Procedural palette is used for a layer while its texture is unset or tex_strength is 0.
uniform bool use_textures = false;
uniform float tex_strength : hint_range(0.0, 1.0) = 1.0;
uniform float tex_scale = 0.25; // repeats per metre
uniform sampler2D tex_meadow : source_color, filter_linear_mipmap_anisotropic, repeat_enable, hint_default_black;
uniform sampler2D tex_dry : source_color, filter_linear_mipmap_anisotropic, repeat_enable, hint_default_black;
uniform sampler2D tex_moss : source_color, filter_linear_mipmap_anisotropic, repeat_enable, hint_default_black;
uniform sampler2D tex_litter : source_color, filter_linear_mipmap_anisotropic, repeat_enable, hint_default_black;
uniform sampler2D tex_dirt : source_color, filter_linear_mipmap_anisotropic, repeat_enable, hint_default_black;

void vertex() {
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	world_normal = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
}

// Two scales at a rotated offset, blended by low-frequency noise, hide the tile grid.
vec3 untiled(sampler2D tex, vec2 uv, float blend) {
	const mat2 ROT = mat2(vec2(0.8, 0.6), vec2(-0.6, 0.8));
	vec3 a = texture(tex, uv).rgb;
	vec3 b = texture(tex, ROT * uv * 0.37 + 0.5).rgb;
	return mix(a, b, blend);
}

// Unset slots sample black (hint_default_black); fall back to the procedural colour there.
vec3 layer(sampler2D tex, vec2 uv, float blend, vec3 proc) {
	vec3 t = untiled(tex, uv, blend);
	return dot(t, vec3(1.0)) > 0.0 ? mix(proc, t, tex_strength) : proc;
}

void fragment() {
	vec2 xz = world_pos.xz;
	float slope = length(world_normal.xz) / max(world_normal.y, 0.1);
	GroundWeights w = ground_weights(xz, slope);
	vec3 meadow = GROUND_MEADOW;
	vec3 dry = GROUND_DRY;
	vec3 moss = GROUND_MOSS;
	vec3 litter = GROUND_LITTER;
	vec3 dirt = GROUND_DIRT;
	if (use_textures) {
		vec2 uv = xz * tex_scale;
		float blend = smoothstep(0.35, 0.65, texture(cloud_noise, fract(xz * 0.02)).r);
		meadow = layer(tex_meadow, uv, blend, meadow);
		dry = layer(tex_dry, uv, blend, dry);
		moss = layer(tex_moss, uv, blend, moss);
		litter = layer(tex_litter, uv, blend, litter);
		dirt = layer(tex_dirt, uv, blend, dirt);
	}
	vec3 col = meadow * w.meadow + dry * w.dry + moss * w.moss + litter * w.litter + dirt * w.dirt;
	ALBEDO = col * ground_mottle(xz);
	ROUGHNESS = roughness;
}
