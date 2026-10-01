shader_type sky;

// Stylized valley sky: smooth vertical gradient, sun disc + soft halo, and a few broad,
// low-contrast cloud masses projected on a dome. Clouds use the same global cloud_noise and
// cloud_offset drift as the painted cloud shadows on the ground. Colours are pushed per
// lighting preset by scripts/atmosphere.gd. The radiance/ambient cubemap pass skips the sun
// disc and the cloud lighting, so reflections and ambient stay soft and cheap.
global uniform vec2 cloud_offset;
global uniform sampler2D cloud_noise : filter_linear_mipmap, repeat_enable;

uniform vec4 sky_top : source_color = vec4(0.3, 0.55, 0.86, 1.0);
uniform vec4 sky_horizon : source_color = vec4(0.72, 0.82, 0.9, 1.0);
uniform vec4 ground_horizon : source_color = vec4(0.4, 0.44, 0.36, 1.0);
uniform vec4 ground_bottom : source_color = vec4(0.2, 0.22, 0.18, 1.0);
uniform float sky_curve = 0.35; // exponent of the horizon -> top blend
uniform vec4 cloud_color_lit : source_color = vec4(0.89, 0.91, 0.92, 1.0);
uniform vec4 cloud_color_shade : source_color = vec4(0.59, 0.68, 0.78, 1.0);
uniform float cloud_coverage : hint_range(0.0, 1.0) = 0.26;
uniform float cloud_softness : hint_range(0.01, 0.5) = 0.09;
uniform float cloud_opacity : hint_range(0.0, 1.0) = 0.8;
uniform float cloud_blur = 1.5; // mip level of the cloud noise
uniform float cloud_shade_mix : hint_range(0.0, 1.0) = 0.45; // shaded side leans to the sky behind it
uniform float cloud_scale = 0.22; // dome uv per unit of projected direction
uniform float cloud_drift = 1.5; // multiple of the global cloud_offset
uniform float sun_disc_size = 0.02; // radians
uniform float sun_disc_energy = 4.0;
uniform float sun_halo_power = 24.0;
uniform float sun_halo_strength = 0.25;

vec3 gradient(vec3 dir) {
	float t = pow(clamp(dir.y, 0.0, 1.0), sky_curve);
	vec3 sky = mix(sky_horizon.rgb, sky_top.rgb, t);
	// Below the horizon only far-away sea/haze is ever seen (beyond the camera far plane),
	// so ground_horizon is a haze tone that darkens slowly downwards.
	vec3 ground = mix(ground_horizon.rgb, ground_bottom.rgb, smoothstep(0.0, 0.3, -dir.y));
	return mix(ground, sky, smoothstep(-0.01, 0.01, dir.y));
}

float density(vec2 p) {
	// Fixed coarse mip: soft broad shapes, and no derivative seam where fract() wraps.
	// A low-frequency term keeps a few big masses and large open areas, not even speckle.
	float big = textureLod(cloud_noise, p * 0.35 + vec2(0.31, 0.77), 1.0).r;
	float n = textureLod(cloud_noise, p, cloud_blur).r * 0.6 + big * 0.4;
	float thr = mix(0.66, 0.42, cloud_coverage);
	return smoothstep(thr - cloud_softness, thr + cloud_softness, n);
}

void sky() {
	vec3 col = gradient(EYEDIR);
	float up = EYEDIR.y;
	if (up > 0.0) {
		vec2 p = EYEDIR.xz / (up + 0.2) * cloud_scale + cloud_offset * cloud_drift;
		float fade = smoothstep(0.0, 0.08, up);
		float d = density(p) * fade;
		vec3 cloud = mix(cloud_color_shade.rgb, cloud_color_lit.rgb, 0.5);
		if (!AT_CUBEMAP_PASS && d > 0.0) {
			// Lit where density falls off towards the sun (its edge faces the light).
			vec2 to_sun = LIGHT0_ENABLED ? normalize(LIGHT0_DIRECTION.xz + 1e-4) : vec2(0.0, 1.0);
			float ahead = density(p + to_sun * 0.02);
			float lit = clamp(0.55 + (d - ahead) * 3.0 - d * 0.25, 0.0, 1.0);
			cloud = mix(mix(cloud_color_shade.rgb, col, cloud_shade_mix), cloud_color_lit.rgb, lit);
		}
		col = mix(col, cloud, d * cloud_opacity);
		if (LIGHT0_ENABLED) {
			float cosang = dot(EYEDIR, LIGHT0_DIRECTION);
			float halo = pow(max(cosang, 0.0), sun_halo_power) * sun_halo_strength;
			col += LIGHT0_COLOR * halo * (1.0 - d * 0.6);
			if (!AT_CUBEMAP_PASS) {
				float ang = acos(clamp(cosang, -1.0, 1.0));
				float disc = 1.0 - smoothstep(sun_disc_size * 0.7, sun_disc_size, ang);
				col += LIGHT0_COLOR * LIGHT0_ENERGY * disc * sun_disc_energy * (1.0 - d);
			}
		}
	}
	COLOR = col;
}
