// Full-screen pass on a camera-attached quad: keeps a sharp, clear radius around the
// player; beyond it the image turns progressively low-res (screen mip blur) and fades
// into white haze. Distance is horizontal from the player so tall trees next to the
// player stay clear. Stands in for per-region render resolution (no VRS on Metal).
shader_type spatial;
render_mode unshaded, fog_disabled, depth_draw_never, depth_test_disabled, cull_disabled, shadows_disabled;

global uniform vec3 player_position;
global uniform vec4 focus_fog_color; // rgb haze colour, a = max opacity

uniform sampler2D screen_tex : hint_screen_texture, filter_linear_mipmap, repeat_disable;
uniform sampler2D depth_tex : hint_depth_texture, filter_nearest, repeat_disable;
uniform float clear_radius = 12.0;
uniform float fog_end = 40.0;
uniform float blur_start = 10.0;
uniform float blur_end = 35.0;
uniform float max_blur_lod = 3.0;
uniform float fog_energy = 1.6; // HDR boost so the haze reads white after tonemapping

void vertex() {
	POSITION = vec4(VERTEX.xy, 1.0, 1.0);
}

void fragment() {
	float depth = texture(depth_tex, SCREEN_UV).r;
	vec4 view = INV_PROJECTION_MATRIX * vec4(SCREEN_UV * 2.0 - 1.0, depth, 1.0);
	view.xyz /= view.w;
	vec3 world = (INV_VIEW_MATRIX * vec4(view.xyz, 1.0)).xyz;
	// Sky (reverse-Z depth 0) counts as infinitely far.
	float d = depth <= 0.0 ? 1e6 : distance(world.xz, player_position.xz);
	float lod = max_blur_lod * smoothstep(blur_start, blur_end, d);
	vec3 col = textureLod(screen_tex, SCREEN_UV, lod).rgb;
	float fog = focus_fog_color.a * smoothstep(clear_radius, fog_end, d);
	ALBEDO = mix(col, focus_fog_color.rgb * fog_energy, fog);
}
