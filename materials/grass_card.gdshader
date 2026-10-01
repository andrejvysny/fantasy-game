shader_type spatial;
render_mode diffuse_lambert, specular_disabled, cull_back;

#include "res://materials/painted_light.gdshaderinc"
#include "res://materials/ground.gdshaderinc"
#include "res://materials/wind.gdshaderinc"

// Card grass from res://grass (sprite blades + flat ground card). The painted sprites are
// bright green, so their luminance is kept as shading while the hue comes from the
// WorldStyle palette (a multiply tint could only darken them, never turn them dry/yellow).
// Instance COLOR: r = dry share (meadow -> dry), g = brightness, b = hue jitter.
// World-position noise shifts all three coherently, so neighbouring patches share a shade.
uniform sampler2D albedo_tex : source_color, filter_linear_mipmap_anisotropic;
uniform float alpha_cut = 0.5;
uniform float tint_strength : hint_range(0.0, 1.0) = 0.85;
uniform float tex_mean_luma = 0.31; // linear luminance of the sprite's opaque texels
uniform float wind_strength = 0.0; // response to the world wind field, metres at blade tips; 0 for the ground card
uniform float wind_speed = 1.0; // tempo multiplier on the global wind
uniform float blade_height = 0.3;
uniform float hue_range = 0.25; // radians of hue rotation across the jitter range
uniform float noise_scale = 0.02; // shade patches ~50 m across
uniform float noise_dry = 0.12; // small: patches must stay close to the ground colour beneath
uniform float noise_shade = 0.12;

varying float dry;
varying float shade;
varying float hue;

// Rotation around the grey axis: shifts hue, keeps luminance roughly constant.
vec3 hue_rotate(vec3 c, float a) {
	const vec3 k = vec3(0.57735);
	return c * cos(a) + cross(k, c) * sin(a) + k * dot(k, c) * (1.0 - cos(a));
}

void vertex() {
	vec3 root = MODEL_MATRIX[3].xyz;
	float n = textureLod(cloud_noise, root.xz * noise_scale, 0.0).r - 0.5;
	float m = textureLod(cloud_noise, root.xz * noise_scale * 0.6 + vec2(0.41, 0.17), 0.0).r - 0.5;
	dry = clamp(COLOR.r + n * noise_dry, 0.0, 1.0);
	shade = COLOR.g * (1.0 + m * noise_shade);
	hue = (0.7 * m + 0.3 * (COLOR.b - 0.5)) * hue_range;
	if (wind_strength > 0.0) {
		float tip = clamp(VERTEX.y / blade_height, 0.0, 1.0);
		vec2 push = wind.xy * wind_strength * wind_gust(root.xz, TIME, 0.0, wind_speed) * tip;
		// World push back to object space (rotation + uniform scale: inverse = transpose / scale^2).
		mat3 m = mat3(MODEL_MATRIX);
		VERTEX += transpose(m) * vec3(push.x, 0.0, push.y) / max(dot(m[0], m[0]), 1e-4);
	}
	world_pos = (MODEL_MATRIX * vec4(VERTEX, 1.0)).xyz;
	world_normal = normalize((MODEL_MATRIX * vec4(NORMAL, 0.0)).xyz);
}

void fragment() {
	vec4 t = texture(albedo_tex, UV);
	float luma = dot(t.rgb, vec3(0.2126, 0.7152, 0.0722)) / tex_mean_luma;
	vec3 palette = max(hue_rotate(mix(ground_meadow.rgb, ground_dry.rgb, dry), hue), vec3(0.0)) * luma;
	ALBEDO = mix(t.rgb, palette, tint_strength) * shade * ground_mottle(world_pos.xz);
	ALPHA = t.a;
	ALPHA_SCISSOR_THRESHOLD = alpha_cut;
	ROUGHNESS = 1.0;
}
