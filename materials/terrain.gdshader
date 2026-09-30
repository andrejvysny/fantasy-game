shader_type spatial;
render_mode diffuse_lambert, specular_disabled;

#include "res://materials/painted_light.gdshaderinc"
#include "res://materials/ground.gdshaderinc"

uniform float roughness : hint_range(0.0, 1.0) = 0.9;
// Optional painted albedo texture per ground layer, authored in sRGB, relightable (no baked
// light or shadow). A layer uses its texture only while its has_* flag is on; otherwise the
// WorldStyle palette colour. Textures should be painted to that palette so grass, which
// only reads the palette, still matches.
uniform float tex_strength : hint_range(0.0, 1.0) = 1.0;
uniform float tex_scale = 0.25; // repeats per metre
uniform bool has_meadow = false;
uniform bool has_dry = false;
uniform bool has_moss = false;
uniform bool has_litter = false;
uniform bool has_dirt = false;
uniform sampler2D tex_meadow : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D tex_dry : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D tex_moss : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D tex_litter : source_color, filter_linear_mipmap_anisotropic, repeat_enable;
uniform sampler2D tex_dirt : source_color, filter_linear_mipmap_anisotropic, repeat_enable;

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

vec3 layer(bool has, sampler2D tex, vec2 uv, float blend, vec3 palette) {
	return has ? mix(palette, untiled(tex, uv, blend), tex_strength) : palette;
}

void fragment() {
	vec2 xz = world_pos.xz;
	float slope = length(world_normal.xz) / max(world_normal.y, 0.1);
	GroundWeights w = ground_weights(xz, slope);
	vec2 uv = xz * tex_scale;
	float blend = smoothstep(0.35, 0.65, texture(cloud_noise, fract(xz * 0.02)).r);
	vec3 col = ground_blend(w,
		layer(has_meadow, tex_meadow, uv, blend, ground_meadow.rgb),
		layer(has_dry, tex_dry, uv, blend, ground_dry.rgb),
		layer(has_moss, tex_moss, uv, blend, ground_moss.rgb),
		layer(has_litter, tex_litter, uv, blend, ground_litter.rgb),
		layer(has_dirt, tex_dirt, uv, blend, ground_dirt.rgb));
	ALBEDO = col * ground_mottle(xz);
	ROUGHNESS = roughness;
}
