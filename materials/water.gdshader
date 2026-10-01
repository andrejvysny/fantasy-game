shader_type spatial;
render_mode blend_mix, depth_draw_opaque, cull_back, diffuse_lambert, specular_schlick_ggx, world_vertex_coords;

// Valley water surface (scripts/valley_water.gd). Flat grid chunks are lifted to the per-pixel
// water level (water_map.r, from tools/terrain/gen_water.py); depth = level - terrain bed.
// Colour runs shallow teal -> deep blue with depth, alpha fades to zero at the shore contact and
// with coverage (water_map.g), so the painted bed shows through shallows and edges have no seam.
// Own light(): water is not painted-banded; soft lambert plus a soft-edged stylized sun glint.
// Sky reflection comes from the environment radiance (low roughness, schlick fresnel).
// Falls (steep level gradient) turn into a pale aerated sheet with soft white streaks stretched
// along the fall and scrolling down it; the splash at their foot is valley_falls.gd particles.
global uniform vec2 cloud_offset;
global uniform float cloud_shadow_strength;
global uniform sampler2D cloud_noise : filter_linear_mipmap, repeat_enable;
global uniform sampler2D brush_noise : filter_linear_mipmap, repeat_enable; // seamless; repeat instead of fract() (fract breaks mip derivatives -> 1 px seams)

uniform sampler2D heightmap : filter_linear, repeat_disable;
uniform sampler2D scene_depth : hint_depth_texture, filter_nearest;
uniform sampler2D water_map : filter_linear, repeat_disable;
uniform float map_size = 1024.0;
uniform bool skirt = false; // open-sea skirt outside the map: level 0, full coverage
uniform vec4 shallow_color : source_color = vec4(0.310, 0.561, 0.541, 1.0);
uniform vec4 deep_color : source_color = vec4(0.118, 0.298, 0.408, 1.0);
uniform vec4 sea_deep_color : source_color = vec4(0.094, 0.255, 0.424, 1.0);
uniform float depth_scale = 2.2; // metres; colour is ~93% deep at 6 m
uniform float alpha_max : hint_range(0.0, 1.0) = 0.92;
uniform float alpha_depth = 1.1; // metres of depth until the surface is at alpha_max
uniform float roughness : hint_range(0.0, 1.0) = 0.08;
uniform float specular : hint_range(0.0, 1.0) = 0.5;
uniform float offshore_depth = 7.0; // sea colour depth the map edge ramps to
uniform sampler2D normal_a : hint_normal, filter_linear_mipmap, repeat_enable;
uniform sampler2D normal_b : hint_normal, filter_linear_mipmap, repeat_enable;
uniform float scale_a = 0.035; // 1 / metres per tile
uniform float scale_b = 0.11;
uniform float normal_strength = 0.22;
uniform vec2 wind_velocity = vec2(0.06, 0.025); // m/s drift on lakes and sea
uniform float flow_speed = 0.9; // m/s along rivers
uniform float flow_period = 3.0; // seconds per flow-map phase
uniform vec4 foam_color : source_color = vec4(0.86, 0.9, 0.88, 1.0);
uniform float foam_edge_depth = 0.12;
uniform vec2 fall_steep = vec2(0.3, 1.5); // level gradient (m/m): rapids start .. full fall face
uniform vec4 fall_tint : source_color = vec4(0.66, 0.82, 0.82, 1.0); // aerated sheet between streaks
uniform float fall_speed = 4.0; // m/s the streaks run down the fall
uniform float streak_width = 0.6; // metres across a streak
uniform float streak_length = 6.0; // metres along a streak
uniform float fall_alpha = 0.92;
uniform float fall_contact = 2.5; // metres of view depth over which a fall sheet fades into rock
uniform vec2 fall_bed_fade = vec2(-0.5, 1.0); // smooth level minus bed (m) over which the sheet fades in
uniform float glint_power = 1500.0;
uniform float glint_threshold = 0.55;
uniform float glint_softness = 0.3;
uniform float glint_strength = 0.6;
uniform float diffuse_amount = 0.65; // water is mostly absorption + reflection, not lit paint

varying vec3 world_pos;
varying vec3 world_normal;
varying vec2 flow; // downhill level gradient, m/m

vec2 map_uv(vec2 xz) {
	return (xz + (map_size - 1.0) * 0.5 + 0.5) / map_size;
}

float level_at(vec2 xz) {
	return textureLod(water_map, map_uv(xz), 0.0).r;
}

void vertex() {
	// World-space vertices snapped to the sample grid (every chunk vertex sits on x.5): shared
	// chunk edges then rasterize bit-identically, so blended edges are never drawn twice.
	if (!skirt) {
		VERTEX.xz = floor(VERTEX.xz) + 0.5;
	}
	vec2 xz = VERTEX.xz;
	flow = vec2(0.0);
	if (!skirt) {
		VERTEX.y = level_at(xz);
		vec2 g = vec2(level_at(xz + vec2(2.0, 0.0)) - level_at(xz - vec2(2.0, 0.0)),
			level_at(xz + vec2(0.0, 2.0)) - level_at(xz - vec2(0.0, 2.0))) * 0.25;
		flow = -g;
		NORMAL = normalize(vec3(-g.x, 1.0, -g.y));
	}
	world_pos = VERTEX;
	world_normal = NORMAL;
}

vec2 nrm(sampler2D tex, vec2 uv) {
	return texture(tex, uv).xy * 2.0 - 1.0;
}

// Two broad normal layers. Lakes/sea drift with the wind; rivers use a two-phase flow map
// along the downhill direction so the pattern moves with the current without stretching.
vec2 surface_ripple(vec2 xz, float moving, vec2 dir) {
	vec2 ua = xz * scale_a;
	vec2 ub = mat2(vec2(0.8, 0.6), vec2(-0.6, 0.8)) * xz * scale_b;
	vec2 wind = wind_velocity * TIME;
	vec2 calm = nrm(normal_a, ua - wind * scale_a) + 0.6 * nrm(normal_b, ub - wind * 1.7 * scale_b);
	if (moving < 0.001) {
		return calm;
	}
	float p0 = fract(TIME / flow_period);
	float p1 = fract(TIME / flow_period + 0.5);
	float w = abs(2.0 * p0 - 1.0); // phase 0 weight is 0 at its reset, phase 1 at its own
	vec2 v = dir * flow_speed * flow_period;
	vec2 f0 = nrm(normal_a, ua - v * p0 * scale_a) + 0.6 * nrm(normal_b, ub - v * p0 * scale_b);
	vec2 f1 = nrm(normal_a, ua - v * p1 * scale_a + 0.37) + 0.6 * nrm(normal_b, ub - v * p1 * scale_b + 0.61);
	return mix(calm, mix(f0, f1, w), moving);
}

// Streak uv on one projection: `across` and `along` are world metres, along runs downstream.
vec2 streak_uv(float across, float along) {
	return vec2(across / streak_width, (along - TIME * fall_speed) / streak_length) * 0.07;
}

// Two octaves; explicit gradients so the fetch may sit in a branch.
float streak_noise(vec2 uv, vec2 dx, vec2 dy) {
	float a = textureGrad(brush_noise, uv, dx, dy).r;
	float b = textureGrad(brush_noise, uv * vec2(2.3, 1.7) + vec2(0.37, 0.11), dx * 2.3, dy * 2.3).r;
	return a * 0.6 + b * 0.4;
}

// Per-fragment level slope (m/m). The vertex `flow` is linear across 2 m triangles, and on a
// fall face its iso-lines follow the triangle diagonals as a sawtooth.
float fragment_steepness(vec2 xz) {
	const float STEP = 1.5;
	vec2 g = vec2(level_at(xz + vec2(STEP, 0.0)) - level_at(xz - vec2(STEP, 0.0)),
		level_at(xz + vec2(0.0, STEP)) - level_at(xz - vec2(0.0, STEP)));
	return length(g) / (2.0 * STEP);
}

void fragment() {
	vec2 xz = world_pos.xz;
	vec2 uv = map_uv(xz);
	float level = world_pos.y;
	float cover = skirt ? 1.0 : texture(water_map, uv).g;
	float depth = level - texture(heightmap, uv).r;
	// The sea (level 0) deepens towards and past the map edge, where the generated bed shelves up.
	float sea = skirt ? 1.0 : 1.0 - smoothstep(0.004, 0.012, level);
	float outside = max(abs(xz.x), abs(xz.y)) - map_size * 0.5;
	float off = offshore_depth * smoothstep(-40.0, 16.0, outside);
	depth = max(depth, sea * off * smoothstep(0.0, 0.5, depth));
	cover = max(cover, sea * smoothstep(-16.0, 0.0, outside));
	if (skirt) {
		depth = max(depth, off);
	}
	float steep = length(flow);
	float moving = smoothstep(0.004, 0.02, steep);
	vec2 dir = flow / max(steep, 1e-5);
	vec2 rip = surface_ripple(xz, moving, dir);
	vec3 n = normalize(world_normal + vec3(rip.x, 0.0, rip.y) * normal_strength);
	NORMAL = normalize((VIEW_MATRIX * vec4(n, 0.0)).xyz);

	float t = 1.0 - exp(-max(depth, 0.0) / depth_scale);
	vec3 col = mix(shallow_color.rgb, mix(deep_color.rgb, sea_deep_color.rgb, sea), t);
	float alpha = alpha_max * smoothstep(0.0, alpha_depth, depth) * cover;
	// Foam only on moving water: a thin broken band at the very edge of rivers, never on still
	// lakes or the sea. Falls and rapids get the streaked sheet instead.
	vec2 buv = xz * 0.21 + dir * TIME * 0.4;
	// Explicit gradients: fract() wrap would otherwise pick the smallest mip along a seam line.
	float breakup = textureGrad(brush_noise, buv, dFdx(buv), dFdy(buv)).r;
	float edge = moving * (1.0 - smoothstep(0.02, foam_edge_depth, depth)) * smoothstep(0.0, 0.02, depth);
	float foam = edge * 0.25 * smoothstep(0.55, 0.75, breakup);
	// Fall streaks aligned with the flow. A rotated frame (dot with dir) would swirl wherever dir
	// turns, since |xz| is hundreds of metres; instead an x-flow and a z-flow projection blend by
	// the flow direction (triplanar style). Along = run downstream plus the drop, so on a fall
	// face the streaks hang vertically and on rapids they lie along the current. Derivatives are
	// taken here, in uniform control flow.
	float fall = steep > 0.05 && !skirt ? smoothstep(fall_steep.x, fall_steep.y, fragment_steepness(xz)) : 0.0;
	vec2 sux = streak_uv(xz.y, xz.x * sign(dir.x) - level);
	vec2 suz = streak_uv(xz.x, xz.y * sign(dir.y) - level);
	vec4 dx = vec4(dFdx(sux), dFdx(suz));
	vec4 dy = vec4(dFdy(sux), dFdy(suz));
	if (fall > 0.0) {
		vec2 w = pow(abs(dir), vec2(4.0));
		w /= w.x + w.y + 1e-5;
		float sn = w.x * streak_noise(sux, dx.xy, dy.xy) + w.y * streak_noise(suz, dx.zw, dy.zw);
		float streak = smoothstep(0.42, 0.68, sn);
		col = mix(col, mix(fall_tint.rgb, foam_color.rgb, streak), fall);
		// The steep sheet cuts into the rock along its 2 m triangles as a sawtooth. Fade it out
		// before that line by the bed depth of the smooth (bilinear) level, and by the view-depth
		// gap to the opaque scene behind.
		float bed = smoothstep(fall_bed_fade.x, fall_bed_fade.y, level_at(xz) - texture(heightmap, uv).r);
		vec4 sv = INV_PROJECTION_MATRIX * vec4(SCREEN_UV * 2.0 - 1.0, texture(scene_depth, SCREEN_UV).r, 1.0);
		float contact = smoothstep(0.0, fall_contact, -sv.z / sv.w + VERTEX.z) * bed;
		// Replaces (not maxes) the depth alpha: where the sheet hovers just off the rock its
		// bed depth reads deep, and the depth alpha alone would draw the sawtooth opaque.
		alpha = mix(alpha, mix(0.8, 1.0, streak) * fall_alpha * cover * contact, fall);
	}
	col = mix(col, foam_color.rgb, foam);
	alpha = max(alpha, foam * 0.8 * cover * step(0.0, depth));
	float rough = max(foam, fall);

	ALBEDO = col;
	ALPHA = alpha;
	ROUGHNESS = mix(roughness, 0.6, rough);
	METALLIC = 0.0;
	SPECULAR = mix(specular, 0.15, rough);
}

void light() {
	float ndl = clamp(dot(NORMAL, LIGHT) * 0.7 + 0.3, 0.0, 1.0);
	float c = 1.0;
	if (LIGHT_IS_DIRECTIONAL) {
		float cn = textureLod(cloud_noise, world_pos.xz * 0.004 + cloud_offset, 0.0).r; // lod 0: no seam at the wrap
		c = 1.0 - cloud_shadow_strength * smoothstep(0.5, 0.6, cn);
	}
	float shade = mix(0.35, 1.0, ATTENUATION) * c;
	DIFFUSE_LIGHT += LIGHT_COLOR * (ndl * shade * diffuse_amount / PI);
	vec3 h = normalize(LIGHT + VIEW);
	float s = pow(clamp(dot(NORMAL, h), 0.0, 1.0), glint_power);
	float glint = smoothstep(glint_threshold - glint_softness, glint_threshold + glint_softness, s);
	SPECULAR_LIGHT += LIGHT_COLOR * (glint * glint_strength * ATTENUATION * c);
}
