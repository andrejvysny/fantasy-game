extends Node

# F1-F11 in this order; F12 cycles the ground debug view.
const DEBUG_KEYS := ["focus", "fog", "vol", "lut", "sat", "clouds", "ssao", "glow", "mist", "back", "occ"]
const GROUND_DEBUG_VIEWS := 7 # 0 off, 1..6 see ground.gdshaderinc
const PRESET_ACTIONS := ["preset_dawn", "preset_midday", "preset_evening"]

@export var presets: Array[LightingPreset] = []
@export var start_index := 0
@export var blend_time := 2.0
@export var environment_path: NodePath
@export var sun_path: NodePath
@export var ground_fog_path: NodePath
@export var dust_path: NodePath
@export var fireflies_path: NodePath
@export var player_path: NodePath
@export var focus_fog_path: NodePath
@export var campfire_path: NodePath
@export var occluder_path: NodePath
@export var cloud_wind := Vector2(0.004, 0.0015) # uv per second
## World wind field for every vegetation shader (global `wind`, materials/wind.gdshaderinc);
## strength comes from the preset (or --wind=<strength> for extreme-wind tests).
@export var wind_direction := Vector2(1.0, 0.4) # world x, z
@export var wind_tempo := 1.0

var _env: Environment
var _sky: Material # ProceduralSkyMaterial (forest) or ShaderMaterial with sky.gdshader (valley)
var _sun: DirectionalLight3D
var _fog_mat: FogMaterial
var _dust: GPUParticles3D
var _fireflies: GPUParticles3D
var _player: Node3D
var _focus_fog: Node3D
var _campfire: Node
var _mist: Node3D
var _occluder: Node
var _player_fill: Light3D
var _wind_override := -1.0 # --wind=<strength>; negative = use the preset
var _motes: Node3D
var _grade_tex: GradientTexture1D
var _cur := LightingPreset.new()
var _from := LightingPreset.new()
var _target: LightingPreset
var _tween: Tween
var _cloud_offset := Vector2.ZERO
# true = effect enabled; toggled with F1-F11 or --off=/--on= for A/B judging.
# lut/sat split the colour adjustment; mist = local FogVolumes only (vol = all volumetrics).
var _debug := {
	"focus": false, "fog": true, "vol": true, "lut": true, "sat": true, "clouds": true,
	"ssao": false, "glow": true, "mist": true, "back": true, "occ": true,
}
var _ground_debug := 0


func _ready() -> void:
	_env = (get_node(environment_path) as WorldEnvironment).environment
	_sky = _env.sky.sky_material
	_sun = get_node(sun_path)
	# FogVolume or the Mist node: both expose the shared FogMaterial as `material`.
	_mist = get_node(ground_fog_path) as Node3D
	_fog_mat = _mist.get("material") as FogMaterial
	_dust = get_node(dust_path)
	_fireflies = get_node(fireflies_path)
	_player = get_node_or_null(player_path)
	if _player != null:
		_player_fill = _player.get_node_or_null("Fill") as Light3D
	_focus_fog = get_node_or_null(focus_fog_path)
	_campfire = get_node_or_null(campfire_path)
	_occluder = get_node_or_null(occluder_path)
	if _occluder != null:
		_debug.occ = _occluder.get("enabled") # keeps its --occ= choice unless --off=occ
	_motes = _dust.get_parent() as Node3D
	var idx := clampi(start_index, 0, presets.size() - 1)
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--preset="):
			idx = clampi(int(arg.trim_prefix("--preset=")), 0, presets.size() - 1)
		elif arg.begins_with("--off="):
			_set_flags(arg.trim_prefix("--off="), false)
		elif arg.begins_with("--on="):
			_set_flags(arg.trim_prefix("--on="), true)
		elif arg.begins_with("--wind="):
			_wind_override = maxf(float(arg.trim_prefix("--wind=")), 0.0)
		elif arg.begins_with("--ground_debug="):
			_ground_debug = clampi(int(arg.trim_prefix("--ground_debug=")), 0, GROUND_DEBUG_VIEWS - 1)
	_cur.grade = presets[idx].grade.duplicate()
	_grade_tex = GradientTexture1D.new()
	_grade_tex.width = 256
	_grade_tex.gradient = _cur.grade
	_env.adjustment_color_correction = _grade_tex
	_env.ssao_radius = 0.6
	_env.ssao_intensity = 1.2
	_env.ssao_power = 1.5
	_env.ssao_detail = 0.5
	_env.ssao_light_affect = 0.0
	_env.ssao_ao_channel_affect = 0.0
	_copy_state(presets[idx], _cur)
	_apply()
	_set_particles(presets[idx].fireflies)
	_push_sun_shadow_fade()
	_warn_extra_suns()
	_apply_debug()
	_print_debug()


# painted_light softens its shadow threshold where Godot fades sun shadows out.
func _push_sun_shadow_fade() -> void:
	var fade_end := _sun.directional_shadow_max_distance * _sun.directional_shadow_fade_start
	RenderingServer.global_shader_parameter_set("sun_shadow_fade", Vector2(fade_end * 0.85, fade_end))


func _warn_extra_suns() -> void:
	var suns := get_tree().root.find_children("*", "DirectionalLight3D", true, false)
	if suns.size() > 1:
		push_warning("painted_light adds shadow fill per directional light; %d found" % suns.size())


func _set_flags(csv: String, value: bool) -> void:
	for name in csv.split(","):
		if name == "grade": # old key: whole colour adjustment
			_debug.lut = value
			_debug.sat = value
		elif _debug.has(name):
			_debug[name] = value
		else:
			push_warning("unknown debug effect: " + name)


func _apply_debug() -> void:
	if _focus_fog != null:
		_focus_fog.visible = _debug.focus
	_env.fog_enabled = _debug.fog
	_env.volumetric_fog_enabled = _debug.vol
	_env.adjustment_enabled = _debug.lut or _debug.sat
	_env.adjustment_color_correction = _grade_tex if _debug.lut else null
	_env.adjustment_saturation = _cur.saturation if _debug.sat else 1.0
	_env.ssao_enabled = _debug.ssao
	_env.glow_enabled = _debug.glow
	_mist.visible = _debug.mist
	if _occluder != null:
		_occluder.call("set_enabled", _debug.occ)
	RenderingServer.global_shader_parameter_set("cloud_shadow_strength", _cloud_strength())
	RenderingServer.global_shader_parameter_set("backlight_scale", 1.0 if _debug.back else 0.0)
	RenderingServer.global_shader_parameter_set("ground_debug", _ground_debug)


func _cloud_strength() -> float:
	return _cur.cloud_shadow_strength if _debug.clouds else 0.0


func _debug_key(event: InputEvent) -> void:
	var k := event as InputEventKey
	if k == null or not k.pressed or k.echo:
		return
	if k.physical_keycode == KEY_F12:
		_ground_debug = (_ground_debug + 1) % GROUND_DEBUG_VIEWS
	else:
		var i := k.physical_keycode - KEY_F1
		if i < 0 or i >= DEBUG_KEYS.size():
			return
		_debug[DEBUG_KEYS[i]] = not _debug[DEBUG_KEYS[i]]
	_apply_debug()
	_print_debug()


func _print_debug() -> void:
	var parts: PackedStringArray = []
	for key in DEBUG_KEYS:
		parts.append("%s=%s" % [key, "on" if _debug[key] else "off"])
	parts.append("ground_debug=%d" % _ground_debug)
	print("DEBUG " + " ".join(parts))


func _unhandled_input(event: InputEvent) -> void:
	_debug_key(event)
	for i in mini(PRESET_ACTIONS.size(), presets.size()):
		if event.is_action_pressed(PRESET_ACTIONS[i]):
			blend_to(i)


func _process(delta: float) -> void:
	_cloud_offset += cloud_wind * delta
	RenderingServer.global_shader_parameter_set("cloud_offset", _cloud_offset)
	if _player != null and _motes != null:
		_motes.global_position = _player.global_position


func blend_to(index: int) -> void:
	if _tween != null:
		_tween.kill()
	_copy_state(_cur, _from)
	_target = presets[index]
	_tween = create_tween()
	_tween.tween_method(_on_blend, 0.0, 1.0, blend_time)
	_tween.tween_callback(_set_particles.bind(_target.fireflies))


func _on_blend(t: float) -> void:
	_blend(t)
	_apply()


func _blend(t: float) -> void:
	_cur.sun_rotation_deg = _slerp_euler(_from.sun_rotation_deg, _target.sun_rotation_deg, t)
	for p in _lerp_props():
		_cur.set(p.name, _lerp_value(_from.get(p.name), _target.get(p.name), t))
	var fg := _from.grade
	var tg := _target.grade
	for i in _cur.grade.get_point_count():
		_cur.grade.set_color(i, fg.get_color(i).lerp(tg.get_color(i), t))


func _slerp_euler(a: Vector3, b: Vector3, t: float) -> Vector3:
	var qa := Quaternion.from_euler(a * (PI / 180.0))
	var qb := Quaternion.from_euler(b * (PI / 180.0))
	return qa.slerp(qb, t).get_euler() * (180.0 / PI)


func _lerp_props() -> Array[Dictionary]:
	var out: Array[Dictionary] = []
	for p in LightingPreset.new().get_property_list():
		if not (p.usage & PROPERTY_USAGE_SCRIPT_VARIABLE) or p.name == "sun_rotation_deg":
			continue
		if p.type == TYPE_FLOAT or p.type == TYPE_COLOR:
			out.append(p)
	return out


func _lerp_value(a: Variant, b: Variant, t: float) -> Variant:
	return lerpf(a, b, t) if a is float else (a as Color).lerp(b, t)


# Copies numeric/colour state plus grade stop colours; grade Gradient object is kept per-instance.
func _copy_state(src: LightingPreset, dst: LightingPreset) -> void:
	dst.sun_rotation_deg = src.sun_rotation_deg
	for p in _lerp_props():
		dst.set(p.name, src.get(p.name))
	dst.fireflies = src.fireflies
	if dst.grade == null:
		dst.grade = src.grade.duplicate()
	for i in src.grade.get_point_count():
		dst.grade.set_color(i, src.grade.get_color(i))


func _apply() -> void:
	var c := _cur
	_sun.basis = Basis.from_euler(c.sun_rotation_deg * (PI / 180.0))
	_sun.light_color = c.sun_color
	_sun.light_energy = c.sun_energy
	_sun.light_volumetric_fog_energy = c.sun_volumetric_energy
	_env.ambient_light_color = c.ambient_color
	_env.ambient_light_energy = c.ambient_energy
	_env.ambient_light_sky_contribution = c.ambient_sky_contribution
	_env.fog_light_color = c.fog_color
	_env.fog_density = c.fog_density
	_env.fog_depth_begin = c.fog_depth_begin
	_env.fog_depth_end = c.fog_depth_end
	_env.fog_height = c.fog_height
	_env.fog_height_density = c.fog_height_density
	_env.volumetric_fog_density = c.vol_fog_density
	_env.volumetric_fog_albedo = c.vol_fog_albedo
	_env.volumetric_fog_emission = c.vol_fog_emission
	_env.fog_sun_scatter = c.fog_sun_scatter
	_env.fog_aerial_perspective = c.fog_aerial_perspective
	_env.tonemap_exposure = c.exposure
	_env.tonemap_agx_contrast = c.agx_contrast
	_env.adjustment_saturation = c.saturation if _debug.sat else 1.0
	_apply_sky(c)
	_fog_mat.density = c.ground_fog_density
	_fog_mat.albedo = c.fog_color
	RenderingServer.global_shader_parameter_set("shadow_tint", c.shadow_tint)
	RenderingServer.global_shader_parameter_set("cloud_shadow_strength", _cloud_strength())
	RenderingServer.global_shader_parameter_set("focus_fog_color", c.focus_fog_color)
	if _campfire != null:
		_campfire.set("energy", c.fire_energy)
	if _player_fill != null:
		_player_fill.light_energy = c.player_fill
		_player_fill.visible = c.player_fill > 0.001
	var strength := _wind_override if _wind_override >= 0.0 else c.wind_strength
	var d := wind_direction.normalized()
	RenderingServer.global_shader_parameter_set("wind", Vector4(d.x, d.y, strength, wind_tempo))


func _apply_sky(c: LightingPreset) -> void:
	var proc := _sky as ProceduralSkyMaterial
	if proc != null:
		proc.sky_top_color = c.sky_top
		proc.sky_horizon_color = c.sky_horizon
		proc.ground_horizon_color = c.ground_horizon
		proc.ground_bottom_color = c.ground_horizon.darkened(0.5)
		return
	var mat := _sky as ShaderMaterial
	if mat == null:
		return
	mat.set_shader_parameter("sky_top", c.sky_top)
	mat.set_shader_parameter("sky_horizon", c.sky_horizon)
	mat.set_shader_parameter("sun_halo_strength", c.sun_halo_strength)
	mat.set_shader_parameter("sun_halo_power", c.sun_halo_power)
	# Below the valley horizon only the distant sea past the far plane shows: a fog-toned haze.
	var haze := c.sky_horizon.lerp(c.fog_color, 0.5)
	mat.set_shader_parameter("ground_horizon", haze)
	mat.set_shader_parameter("ground_bottom", haze.darkened(0.3))
	# Cloud tones come from the preset: lit side near-white toward the sun colour, shaded side
	# the fog tone leaning to the sky top, desaturated so masses stay low-contrast.
	var lit := c.sky_horizon.lerp(Color.WHITE, 0.45).lerp(c.sun_color, 0.25)
	var shade := c.fog_color.lerp(c.sky_top, 0.3)
	var grey := shade.get_luminance()
	shade = shade.lerp(Color(grey, grey, grey), 0.4)
	mat.set_shader_parameter("cloud_color_lit", lit)
	mat.set_shader_parameter("cloud_color_shade", shade)


func _set_particles(fireflies: bool) -> void:
	_fireflies.emitting = fireflies
	_dust.emitting = not fireflies
