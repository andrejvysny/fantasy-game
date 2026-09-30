// Procedural painted ground palette, shared by terrain.gdshader and grass.gdshader
// so blades pick up the soil colour they grow from. Needs painted_light.gdshaderinc
// included first (brush_noise, cloud_noise globals).
global uniform sampler2D canopy_mask;

const float WORLD_HALF = 128.0;
const vec3 GROUND_MEADOW = vec3(0.30, 0.45, 0.14);
const vec3 GROUND_DRY = vec3(0.52, 0.49, 0.20);
const vec3 GROUND_MOSS = vec3(0.22, 0.36, 0.14);
const vec3 GROUND_LITTER = vec3(0.33, 0.23, 0.13);
const vec3 GROUND_DIRT = vec3(0.43, 0.30, 0.17);

struct GroundWeights {
	float meadow;
	float dry;
	float moss;
	float litter;
	float dirt;
};

float canopy_at(vec2 xz) {
	vec2 uv = clamp((xz + WORLD_HALF) / (2.0 * WORLD_HALF), vec2(0.0), vec2(1.0));
	return texture(canopy_mask, uv).r;
}

// Weights sum to 1. Noise breaks every transition so layer edges read as painted, not blurred.
GroundWeights ground_weights(vec2 xz, float slope) {
	float n = texture(brush_noise, fract(xz * 0.08)).r - 0.5;
	float macro = texture(cloud_noise, fract(xz * 0.011 + vec2(0.37, 0.71))).r;
	float c = canopy_at(xz) + n * 0.35;
	GroundWeights w;
	w.litter = smoothstep(0.4, 0.55, c);
	w.moss = smoothstep(0.12, 0.28, c) * (1.0 - w.litter);
	float open_ground = 1.0 - w.litter - w.moss;
	w.dry = smoothstep(0.5, 0.6, macro + n * 0.25) * open_ground;
	float bare = smoothstep(0.3, 0.5, slope + n * 0.2) + (1.0 - smoothstep(0.2, 0.25, macro + n * 0.2)) * open_ground;
	w.dirt = clamp(bare, 0.0, 1.0);
	float keep = 1.0 - w.dirt;
	w.meadow = (open_ground - w.dry) * keep;
	w.dry *= keep;
	w.moss *= keep;
	w.litter *= keep;
	return w;
}

// Two-scale brush mottling, roughly +-12% value.
float ground_mottle(vec2 xz) {
	float m1 = texture(brush_noise, fract(xz * 0.35)).r - 0.5;
	float m2 = texture(brush_noise, fract(xz * 0.05 + 0.5)).r - 0.5;
	return 1.0 + m1 * 0.16 + m2 * 0.14;
}

vec3 ground_color(vec2 xz, float slope) {
	GroundWeights w = ground_weights(xz, slope);
	vec3 col = GROUND_MEADOW * w.meadow + GROUND_DRY * w.dry + GROUND_MOSS * w.moss
		+ GROUND_LITTER * w.litter + GROUND_DIRT * w.dirt;
	return col * ground_mottle(xz);
}
