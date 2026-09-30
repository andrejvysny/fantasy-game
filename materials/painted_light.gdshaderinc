// Painted-light model shared by every world shader: banded diffuse, brush noise,
// tinted shadows, cloud shadows. Includers must write world_pos/world_normal in vertex().
global uniform vec3 player_position;
global uniform vec2 cloud_offset;
global uniform float cloud_shadow_strength;
global uniform vec4 shadow_tint;
global uniform sampler2D brush_noise;
global uniform sampler2D cloud_noise;

uniform float wrap : hint_range(0.0, 1.0) = 0.3;
uniform float band_low = 0.3;
uniform float band_high = 0.65;
uniform float band_softness = 0.04;
uniform float brush_scale = 0.12;
uniform float brush_strength = 0.18;
uniform vec4 lit_warmth : source_color = vec4(1.0, 0.96, 0.88, 1.0);

varying vec3 world_pos;
varying vec3 world_normal;

float brush_sample() {
	vec3 w = pow(abs(world_normal), vec3(4.0));
	w /= (w.x + w.y + w.z + 1e-5);
	vec3 p = world_pos * brush_scale;
	float sx = texture(brush_noise, fract(p.zy * vec2(1.0, 3.0))).r;
	float sy = texture(brush_noise, fract(p.xz * vec2(1.0, 3.0))).r;
	float sz = texture(brush_noise, fract(p.xy * vec2(1.0, 3.0))).r;
	return sx * w.x + sy * w.y + sz * w.z - 0.5;
}

// Cast and cloud shadows are thresholded, not filtered: sharp edges, one flat
// shadow colour inside. Shadow-map blur only rounds the contour.
void light() {
	float ndl = dot(NORMAL, LIGHT);
	float x = clamp((ndl + wrap) / (1.0 + wrap), 0.0, 1.0) + brush_sample() * brush_strength;
	float band = 0.5 * smoothstep(band_low - band_softness, band_low + band_softness, x)
		+ 0.5 * smoothstep(band_high - band_softness, band_high + band_softness, x);
	band *= smoothstep(0.45, 0.55, ATTENUATION);
	float cloud = 1.0;
	if (LIGHT_IS_DIRECTIONAL) {
		float c = texture(cloud_noise, fract(world_pos.xz * 0.004 + cloud_offset)).r;
		cloud = 1.0 - cloud_shadow_strength * smoothstep(0.54, 0.56, c);
	}
	vec3 lit = mix(shadow_tint.rgb * shadow_tint.a, lit_warmth.rgb * cloud, band);
	DIFFUSE_LIGHT += LIGHT_COLOR / PI * lit;
}
