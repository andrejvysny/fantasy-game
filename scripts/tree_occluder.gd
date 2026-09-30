extends Node
## Per-tree blocker fade: trees crossing the camera->player sightline fade fully out
## (dither only while fading), with hysteresis. Drives the `occluder_fade` instance uniform.

@export var forest_path: NodePath
@export var camera_path: NodePath
@export var player_path: NodePath
@export var enabled := true : set = set_enabled
@export var spatial_mode := false : set = set_spatial_mode # legacy per-fragment A/B path
@export var target_height := 1.2
@export var body_margin := 0.5
@export var crown_scale := 0.7
@export var enter_scale := 0.85
@export var exit_scale := 1.1
@export var fade_out_time := 0.2
@export var fade_in_time := 0.35
@export var min_hold := 0.25 # seconds before a tree may flip state again
@export var cell := 8.0

var _cam: Node3D
var _player: Node3D
var _mat: ShaderMaterial
var _meshes: Array[MeshInstance3D] = []
var _bases := PackedVector3Array()
var _tops := PackedFloat32Array()
var _radii := PackedFloat32Array()
var _fade := PackedFloat32Array()
var _last_flip := PackedFloat32Array()
var _blocking := PackedByteArray()
var _stamp := PackedInt32Array()
var _grid := {} # Vector2i -> PackedInt32Array
var _active := {} # tree index -> true
var _max_radius := 0.0
var _frame := 0
var _time := 0.0 # accumulated delta, so holds match fades under fixed-fps movie capture
var _perf := false
var _us_sum := 0
var _us_max := 0
var _us_n := 0


func _ready() -> void:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--occ="):
			var m := arg.trim_prefix("--occ=")
			spatial_mode = m == "spatial"
			enabled = m != "off"
	_perf = OS.get_cmdline_user_args().has("--perf")
	_cam = get_node(camera_path)
	_player = get_node(player_path)
	# Forest builds in its own _ready, which has run by the time idle frame one starts.
	_build.call_deferred()


func _build() -> void:
	var trees := get_node(forest_path).get_node_or_null("Trees")
	if trees == null:
		return
	for t in trees.get_children():
		var mi := t.get_node_or_null("Tree") as MeshInstance3D
		if mi == null:
			continue
		var aabb := mi.global_transform * mi.get_aabb()
		var i := _meshes.size()
		_meshes.append(mi)
		_bases.append(t.global_position)
		_tops.append(aabb.end.y)
		var r := 0.5 * maxf(aabb.size.x, aabb.size.z) * crown_scale
		_radii.append(r)
		_max_radius = maxf(_max_radius, r)
		var key := Vector2i(floori(t.global_position.x / cell), floori(t.global_position.z / cell))
		if not _grid.has(key):
			_grid[key] = PackedInt32Array()
		_grid[key].append(i)
	_fade.resize(_meshes.size())
	_last_flip.resize(_meshes.size())
	_last_flip.fill(-1000.0)
	_blocking.resize(_meshes.size())
	_stamp.resize(_meshes.size())
	if not _meshes.is_empty():
		_mat = _meshes[0].material_override as ShaderMaterial
	_apply_material()


func set_enabled(v: bool) -> void:
	enabled = v
	_reset()
	_apply_material()


func set_spatial_mode(v: bool) -> void:
	spatial_mode = v
	_reset()
	_apply_material()


func _apply_material() -> void:
	if _mat:
		_mat.set_shader_parameter("dither_occlusion", enabled)
		_mat.set_shader_parameter("occlusion_mode", 1 if spatial_mode else 0)


func _reset() -> void:
	for i in _active:
		_blocking[i] = 0
		_fade[i] = 0.0
		_meshes[i].set_instance_shader_parameter("occluder_fade", 0.0)
	_active.clear()


func _process(delta: float) -> void:
	if not enabled or spatial_mode or _meshes.is_empty():
		return
	var t0 := Time.get_ticks_usec()
	_frame += 1
	_time += delta
	var now := _time
	var cam := _cam.global_position
	var target := _player.global_position + Vector3(0.0, target_height, 0.0)
	var pad := _max_radius * exit_scale + body_margin
	var lo := Vector2(minf(cam.x, target.x), minf(cam.z, target.z)) - Vector2(pad, pad)
	var hi := Vector2(maxf(cam.x, target.x), maxf(cam.z, target.z)) + Vector2(pad, pad)
	for cx in range(floori(lo.x / cell), floori(hi.x / cell) + 1):
		for cz in range(floori(lo.y / cell), floori(hi.y / cell) + 1):
			for i in _grid.get(Vector2i(cx, cz), PackedInt32Array()):
				_update(i, cam, target, now, delta)
	for i in _active.keys():
		_update(i, cam, target, now, delta)
	if _perf:
		var us := Time.get_ticks_usec() - t0
		_us_sum += us
		_us_max = maxi(_us_max, us)
		_us_n += 1


func _update(i: int, cam: Vector3, target: Vector3, now: float, delta: float) -> void:
	if _stamp[i] == _frame:
		return
	_stamp[i] = _frame
	var was := _blocking[i] == 1
	var r := _radii[i] * (exit_scale if was else enter_scale) + body_margin
	var base := _bases[i]
	var res := _closest(cam, target, base, Vector3(base.x, _tops[i], base.z))
	var want: bool = res.x < r and res.y < 0.999
	if want != was and now - _last_flip[i] >= min_hold:
		_blocking[i] = 1 if want else 0
		_last_flip[i] = now
		was = want
	var f := _fade[i]
	var nf := move_toward(f, 1.0 if was else 0.0, delta / (fade_out_time if was else fade_in_time))
	if nf != f:
		_fade[i] = nf
		_meshes[i].set_instance_shader_parameter("occluder_fade", nf)
	if was or nf > 0.0:
		_active[i] = true
	else:
		_active.erase(i)


# Closest points between segments p1->q1 and p2->q2; returns (distance, s on first segment).
func _closest(p1: Vector3, q1: Vector3, p2: Vector3, q2: Vector3) -> Vector2:
	var d1 := q1 - p1
	var d2 := q2 - p2
	var r := p1 - p2
	var a := d1.dot(d1)
	var e := d2.dot(d2)
	var f := d2.dot(r)
	var c := d1.dot(r)
	var b := d1.dot(d2)
	var denom := a * e - b * b
	var s := clampf((b * f - c * e) / denom, 0.0, 1.0) if denom > 1e-8 else 0.0
	var t := (b * s + f) / e
	if t < 0.0:
		t = 0.0
		s = clampf(-c / a, 0.0, 1.0)
	elif t > 1.0:
		t = 1.0
		s = clampf((b - c) / a, 0.0, 1.0)
	return Vector2(((p1 + d1 * s) - (p2 + d2 * t)).length(), s)


func _exit_tree() -> void:
	if _perf and _us_n > 0:
		print("PERF occluder_us avg=%.1f max=%d" % [float(_us_sum) / _us_n, _us_max])
