// One world wind field shared by every vegetation shader; scripts/atmosphere.gd pushes `wind`.
// Include after painted_light.gdshaderinc (uses its cloud_noise global).
// wind: xy = unit direction in world x/z, z = strength (1 = default breeze), w = tempo multiplier.
// Materials keep their own response amplitude (metres at strength 1) and multiply this gust.
global uniform vec4 wind;

const float WIND_WAVELENGTH = 14.0; // metres between gust crests travelling downwind
const float WIND_TEMPO = 1.1; // rad/s of the crest wave at tempo 1
const float WIND_NOISE_SCALE = 0.02; // broad gust patches ~50 m across
const float WIND_NOISE_DRIFT = 1.0; // m/s the gust patches travel downwind

// Signed gust factor at world xz (about -0.3..1.5 times strength): a crest wave travelling
// downwind, so phase varies with position, modulated by drifting broad noise. Mostly a lean
// downwind with a sway around it. `jitter` (radians) desyncs neighbouring objects; `tempo`
// is the material's frequency response (1 = in step with the grass).
float wind_gust(vec2 p, float time, float jitter, float tempo) {
	float t = time * wind.w;
	float phase = t * WIND_TEMPO * tempo - dot(p, wind.xy) * TAU / WIND_WAVELENGTH + jitter;
	float osc = sin(phase) * 0.75 + sin(phase * 2.3 + 1.1) * 0.25;
	float n = textureLod(cloud_noise, (p - wind.xy * t * WIND_NOISE_DRIFT) * WIND_NOISE_SCALE, 0.0).r;
	return (0.35 + 0.65 * osc) * (0.5 + n) * wind.z;
}
