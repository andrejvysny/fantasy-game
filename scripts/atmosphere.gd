extends Node

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
@export var cloud_wind := Vector2(0.004, 0.0015) # uv per second

var _env: Environment
var _sky: ProceduralSkyMaterial
var _sun: DirectionalLight3D
var _fog_mat: FogMaterial
var _dust: GPUParticles3D
var _fireflies: GPUParticles3D
var _player: Node3D
var _motes: Node3D
var _grade_tex: GradientTexture1D
var _cur := LightingPreset.new()
var _from := LightingPreset.new()
var _target: LightingPreset
var _tween: Tween
var _cloud_offset := Vector2.ZERO


func _ready() -> void:
	_env = (get_node(environment_path) as WorldEnvironment).environment
	_sky = _env.sky.sky_material as ProceduralSkyMaterial
	_sun = get_node(sun_path)
	_fog_mat = (get_node(ground_fog_path) as FogVolume).material as FogMaterial
	_dust = get_node(dust_path)
	_fireflies = get_node(fireflies_path)
	_player = get_node_or_null(player_path)
	_motes = _dust.get_parent() as Node3D
	var idx := clampi(start_index, 0, presets.size() - 1)
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--preset="):
			idx = clampi(int(arg.trim_prefix("--preset=")), 0, presets.size() - 1)
	_cur.grade = presets[idx].grade.duplicate()
	_grade_tex = GradientTexture1D.new()
	_grade_tex.width = 256
	_grade_tex.gradient = _cur.grade
	_env.adjustment_color_correction = _grade_tex
	_copy_state(presets[idx], _cur)
	_apply()
	_set_particles(presets[idx].fireflies)


func _unhandled_input(event: InputEvent) -> void:
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
	_env.fog_height = c.fog_height
	_env.fog_height_density = c.fog_height_density
	_env.volumetric_fog_density = c.vol_fog_density
	_env.volumetric_fog_albedo = c.vol_fog_albedo
	_env.volumetric_fog_emission = c.vol_fog_emission
	_env.fog_sun_scatter = c.fog_sun_scatter
	_env.fog_aerial_perspective = c.fog_aerial_perspective
	_env.tonemap_exposure = c.exposure
	_env.tonemap_agx_contrast = c.agx_contrast
	_env.adjustment_saturation = c.saturation
	_sky.sky_top_color = c.sky_top
	_sky.sky_horizon_color = c.sky_horizon
	_sky.ground_horizon_color = c.ground_horizon
	_sky.ground_bottom_color = c.ground_horizon.darkened(0.5)
	_fog_mat.density = c.ground_fog_density
	_fog_mat.albedo = c.fog_color
	RenderingServer.global_shader_parameter_set("shadow_tint", c.shadow_tint)
	RenderingServer.global_shader_parameter_set("cloud_shadow_strength", c.cloud_shadow_strength)
	RenderingServer.global_shader_parameter_set("focus_fog_color", c.focus_fog_color)


func _set_particles(fireflies: bool) -> void:
	_fireflies.emitting = fireflies
	_dust.emitting = not fireflies
