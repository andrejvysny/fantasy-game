// Painted-light model shared by every world shader: banded diffuse, brush noise,
// tinted shadows, cloud shadows. Includers must write world_pos/world_normal in vertex().
// Define PAINTED_BACKLIGHT before including to read the `translucency` varying in light().
global uniform vec3 player_position;
global uniform vec2 cloud_offset;
global uniform float cloud_shadow_strength;
global uniform vec4 shadow_tint;
global uniform sampler2D brush_noise : filter_linear_mipmap, repeat_enable; // seamless; repeat instead of fract() (fract breaks mip derivatives -> 1 px seams)
global uniform sampler2D cloud_noise : filter_linear_mipmap, repeat_enable;
// Sun shadow fade band in view depth (metres): Godot's own fade (fade_start..max_distance)
// ramps ATTENUATION up gradually; thresholding it would turn that ramp into a moving hard line.
global uniform vec2 sun_shadow_fade;
global uniform float backlight_scale; // debug A/B for foliage backlight

uniform float wrap : hint_range(0.0, 1.0) = 0.3;
uniform float band_low = 0.3;
uniform float band_high = 0.65;
uniform float band_softness = 0.08;
// Local lights (fire, lanterns) get wider band edges so their pools read as soft warm light.
uniform float local_band_softness = 0.2;
uniform float brush_scale = 0.12;
uniform float brush_strength = 0.18;
uniform vec4 lit_warmth : source_color = vec4(1.0, 0.96, 0.88, 1.0);

varying vec3 world_pos;
varying vec3 world_normal;
#ifdef PAINTED_BACKLIGHT
varying float translucency;
#endif

float brush_sample() {
	vec3 w = pow(abs(world_normal), vec3(4.0));
	w /= (w.x + w.y + w.z + 1e-5);
	vec3 p = world_pos * brush_scale;
	float sx = texture(brush_noise, p.zy * vec2(1.0, 3.0)).r;
	float sy = texture(brush_noise, p.xz * vec2(1.0, 3.0)).r;
	float sz = texture(brush_noise, p.xy * vec2(1.0, 3.0)).r;
	return sx * w.x + sy * w.y + sz * w.z - 0.5;
}

float painted_bands(float x, float softness) {
	return 0.5 * smoothstep(band_low - softness, band_low + softness, x)
		+ 0.5 * smoothstep(band_high - softness, band_high + softness, x);
}

// Sun: cast shadows thresholded (sharp edge, one flat colour inside), cloud shadows
// soft-edged, cool shadow fill added once. Local lights keep Godot's smooth distance
// attenuation and add no fill, so extra lights never brighten shadowed ground.
// Every directional light adds the fill; the scene keeps exactly one sun (atmosphere.gd
// warns otherwise). Give fill a single owner before adding a moon or auxiliary directional.
void light() {
	float ndl = dot(NORMAL, LIGHT);
	float x = clamp((ndl + wrap) / (1.0 + wrap), 0.0, 1.0) + brush_sample() * brush_strength;
	if (LIGHT_IS_DIRECTIONAL) {
		float depth = dot(world_pos - INV_VIEW_MATRIX[3].xyz, -INV_VIEW_MATRIX[2].xyz);
		float fading = smoothstep(sun_shadow_fade.x, sun_shadow_fade.y, depth);
		float shadow = mix(smoothstep(0.45, 0.55, ATTENUATION), ATTENUATION, fading);
		float band = painted_bands(x, band_softness) * shadow;
		float c = texture(cloud_noise, world_pos.xz * 0.004 + cloud_offset).r;
		float cloud = 1.0 - cloud_shadow_strength * smoothstep(0.5, 0.6, c);
		// Fill takes the sun's brightness but not its hue, so shadows stay cool at dawn/evening.
		float sun_lum = dot(LIGHT_COLOR, vec3(0.2126, 0.7152, 0.0722));
		vec3 fill = shadow_tint.rgb * shadow_tint.a * sun_lum;
		DIFFUSE_LIGHT += mix(fill, LIGHT_COLOR * lit_warmth.rgb * cloud, band) / PI;
#ifdef PAINTED_BACKLIGHT
		// Thin foliage facing away from the sun glows where the viewer looks toward it.
		float back = pow(clamp(dot(VIEW, -LIGHT), 0.0, 1.0), 3.0) * (1.0 - clamp(ndl, 0.0, 1.0));
		DIFFUSE_LIGHT += LIGHT_COLOR * lit_warmth.rgb * (translucency * backlight_scale * back * shadow * cloud / PI);
#endif
	} else {
		float band = painted_bands(x, local_band_softness);
		DIFFUSE_LIGHT += LIGHT_COLOR * lit_warmth.rgb * (band * ATTENUATION / PI);
	}
}
