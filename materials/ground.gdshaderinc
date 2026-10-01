// Painted ground palette, shared by terrain.gdshader and grass.gdshader so blades pick
// up the soil colour they grow from. Needs painted_light.gdshaderinc included first
// (brush_noise, cloud_noise globals).
// Palette globals are linear: WorldStyle authors them in sRGB and converts before pushing
// (colour-type globals reach shaders unconverted).
global uniform sampler2D ground_mask; // r = canopy cover (0..2, overlapping crowns sum), g = wear
global uniform vec4 ground_meadow;
global uniform vec4 ground_dry;
global uniform vec4 ground_moss;
global uniform vec4 ground_litter;
global uniform vec4 ground_dirt;
// Debug view (atmosphere.gd F12 / --ground_debug=): 1 wear, 2 trampled, 3 natural dry,
// 4 final dry, 5 litter, 6 dirt. Shown as unlit grey on terrain.
global uniform int ground_debug;

const float WORLD_HALF = 128.0;

struct GroundWeights {
	float meadow;
	float dry;
	float moss;
	float litter;
	float dirt;
	// Intermediates kept for the ground debug view.
	float wear;
	float trampled;
	float natural_dry;
};

vec2 ground_mask_at(vec2 xz) {
	vec2 uv = clamp((xz + WORLD_HALF) / (2.0 * WORLD_HALF), vec2(0.0), vec2(1.0));
	return texture(ground_mask, uv).rg;
}

// Weights sum to 1. Noise breaks every transition so layer edges read as painted, not blurred.
// Large-scale structure: canopy -> moss/litter, wear -> dirt with a trampled dry ring,
// open ground -> meadow with dry grass only as occasional accents.
GroundWeights ground_weights(vec2 xz, float slope) {
	float n = texture(brush_noise, xz * 0.08).r - 0.5;
	float macro = texture(cloud_noise, xz * 0.011 + vec2(0.37, 0.71)).r;
	vec2 mask = ground_mask_at(xz);
	float c = mask.r + n * 0.35;
	// Macro noise decides whether a crown drops litter or keeps moss, so trees don't all stamp identical rings.
	float c_litter = c + (macro - 0.5) * 0.7;
	// Noise only roughens wear where the mask has some: zero mask must mean zero wear,
	// or noise alone paints trampled islands far from any camp object.
	float wear_support = smoothstep(0.0, 0.08, mask.g);
	float wear_raw = clamp(mask.g + n * 0.5 * wear_support, 0.0, 1.0);
	GroundWeights w;
	w.wear = wear_raw;
	w.litter = smoothstep(0.8, 1.0, c_litter);
	w.moss = smoothstep(0.12, 0.28, c) * (1.0 - w.litter);
	float open_ground = 1.0 - w.litter - w.moss;
	w.trampled = smoothstep(0.1, 0.3, wear_raw);
	w.natural_dry = smoothstep(0.7, 0.78, macro + n * 0.25);
	w.dry = max(w.natural_dry, w.trampled) * open_ground;
	float bare = smoothstep(0.35, 0.55, slope + n * 0.2) + (1.0 - smoothstep(0.16, 0.2, macro + n * 0.2)) * open_ground;
	w.dirt = clamp(bare + smoothstep(0.4, 0.6, wear_raw), 0.0, 1.0);
	float keep = 1.0 - w.dirt;
	w.meadow = (open_ground - w.dry) * keep;
	w.dry *= keep;
	w.moss *= keep;
	w.litter *= keep;
	return w;
}

// Medium-scale strokes dominate; fine speckle stays quiet at gameplay distance.
float ground_mottle(vec2 xz) {
	const mat2 ROT = mat2(vec2(0.8, 0.6), vec2(-0.6, 0.8));
	float fine = texture(brush_noise, xz * 0.35).r - 0.5;
	float broad = texture(brush_noise, xz * 0.05 + 0.5).r - 0.5;
	vec2 s = ROT * xz;
	float stroke = texture(brush_noise, vec2(s.x * 0.06, s.y * 0.22)).r - 0.5;
	return 1.0 + fine * 0.06 + broad * 0.14 + stroke * 0.12;
}

vec3 ground_blend(GroundWeights w, vec3 meadow, vec3 dry, vec3 moss, vec3 litter, vec3 dirt) {
	return meadow * w.meadow + dry * w.dry + moss * w.moss + litter * w.litter + dirt * w.dirt;
}

float ground_debug_value(GroundWeights w) {
	float v[6] = float[](w.wear, w.trampled, w.natural_dry, w.dry, w.litter, w.dirt);
	return v[clamp(ground_debug, 1, 6) - 1];
}

vec3 ground_color(vec2 xz, float slope) {
	GroundWeights w = ground_weights(xz, slope);
	vec3 col = ground_blend(w, ground_meadow.rgb, ground_dry.rgb, ground_moss.rgb, ground_litter.rgb, ground_dirt.rgb);
	return col * ground_mottle(xz);
}
