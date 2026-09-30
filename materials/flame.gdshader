shader_type spatial;
render_mode unshaded, blend_add, depth_draw_never, cull_disabled, shadows_disabled, fog_disabled;

uniform float emission_strength = 0.4;
uniform float wobble = 0.07;
uniform float wobble_speed = 7.0;

varying float seed;

void vertex() {
	// Particle billboard keeping per-particle scale (same as StandardMaterial3D billboard_mode = 3).
	MODELVIEW_MATRIX = VIEW_MATRIX * mat4(INV_VIEW_MATRIX[0], INV_VIEW_MATRIX[1], INV_VIEW_MATRIX[2], MODEL_MATRIX[3]);
	MODELVIEW_MATRIX = MODELVIEW_MATRIX * mat4(
		vec4(length(MODEL_MATRIX[0].xyz), 0.0, 0.0, 0.0),
		vec4(0.0, length(MODEL_MATRIX[1].xyz), 0.0, 0.0),
		vec4(0.0, 0.0, length(MODEL_MATRIX[2].xyz), 0.0),
		vec4(0.0, 0.0, 0.0, 1.0));
	seed = fract(sin(float(INSTANCE_ID) * 12.9898 + INSTANCE_CUSTOM.z * 78.233) * 43758.5453) * 6.2831;
}

void fragment() {
	float t = 1.0 - UV.y; // 0 = base, 1 = tip
	float x = (UV.x - 0.5) * 2.0;
	x += sin(t * 5.0 - TIME * wobble_speed + seed) * wobble * 2.0 * t
		+ sin(t * 11.0 - TIME * wobble_speed * 1.7 + seed * 2.0) * wobble * t;
	// Teardrop: round wide base, pointed tip.
	float base_round = smoothstep(0.0, 0.18, t) * 0.35 + 0.65;
	float half_w = 0.9 * pow(max(1.0 - t, 0.0), 0.75) * base_round;
	float d = abs(x) / max(half_w, 0.001);
	float m = 1.0 - smoothstep(0.55, 1.0, d);
	m *= 1.0 - smoothstep(0.92, 1.0, t);
	// Painted steps: outer soft, mid, hot core.
	float steps = smoothstep(0.0, 0.25, m) * 0.5 + smoothstep(0.35, 0.6, m) * 0.3 + smoothstep(0.7, 0.9, m) * 0.2;
	ALBEDO = COLOR.rgb * emission_strength * (0.7 + 0.5 * smoothstep(0.7, 0.9, m));
	ALPHA = steps * COLOR.a;
}
