extends Node3D
## Asset showroom for assets/nature: every asset in a row on flat meadow ground, each with a
## 1.8 m player-scale capsule, lit by the midday sun through the game's world shaders.
##   godot --path . res://scenes/showroom.tscn -- [--focus=<asset_id>] [--view=high|low|tactical] [--group=rocks]
## --focus frames one asset; --view high = 35 deg 3/4, low = player eye height, tactical = the
## game's 57 deg pitch at 26 m. Without --focus the camera frames the whole row from above.

const GAP := 2.5
const CAPSULE := 1.8

@export var style: WorldStyle = preload("res://materials/world_style.tres")

var _slots := {} # asset_id -> [x centre, AABB]


func _ready() -> void:
	style.apply()
	# Midday preset shadow fill (atmosphere.gd pushes this in the game scenes).
	RenderingServer.global_shader_parameter_set("shadow_tint", Color(0.3, 0.42, 0.58, 0.3))
	var focus := ""
	var view := "high"
	var group := ""
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--focus="):
			focus = arg.trim_prefix("--focus=")
		elif arg.begins_with("--view="):
			view = arg.trim_prefix("--view=")
		elif arg.begins_with("--group="):
			group = arg.trim_prefix("--group=")
	_layout(group)
	_frame(focus, view)


func _layout(group: String) -> void:
	var x := 0.0
	for id in NatureAssets.ids():
		var m := NatureAssets.meta(id)
		if group != "" and m.get("group", "") != group:
			continue
		var mesh := NatureAssets.mesh(id)
		if mesh == null:
			continue
		var aabb := mesh.get_aabb()
		x += -aabb.position.x
		var mi := MeshInstance3D.new()
		mi.name = id
		mi.mesh = mesh
		mi.position = Vector3(x, 0.0, 0.0)
		add_child(mi)
		_slots[id] = [x, aabb]
		# Behind-right of the asset so it never hides small plants in the focus views.
		_add_capsule(Vector3(x + aabb.end.x + 0.6, 0.0, aabb.position.z - 0.8))
		x += aabb.end.x + GAP
		print("SHOWROOM %s tris=%s size=%s" % [id, m.get("tris", "?"), aabb.size])


func _add_capsule(at: Vector3) -> void:
	var mi := MeshInstance3D.new()
	var cap := CapsuleMesh.new()
	cap.radius = 0.35
	cap.height = CAPSULE
	var mat := StandardMaterial3D.new()
	mat.albedo_color = Color(0.72, 0.32, 0.22)
	cap.material = mat
	mi.mesh = cap
	mi.position = at + Vector3(0.0, CAPSULE * 0.5, 0.0)
	add_child(mi)


func _frame(focus: String, view: String) -> void:
	var cam := $Camera as Camera3D
	var center := Vector3.ZERO
	var size := 4.0
	if _slots.has(focus):
		var aabb: AABB = _slots[focus][1]
		center = Vector3(_slots[focus][0], 0.0, 0.0) + aabb.get_center()
		size = maxf(aabb.size.length(), 1.5)
	else:
		var last: Array = _slots.values().back() if not _slots.is_empty() else [0.0, AABB()]
		center = Vector3(float(last[0]) * 0.5, 2.0, 0.0)
		size = float(last[0]) * 0.9 + 4.0
	var pitch := deg_to_rad(35.0)
	var dist := size * 1.25 + 1.5
	var look := center
	if view == "low":
		# Eye height, looking at the asset centre so tall trees frame whole (player-height read).
		pitch = deg_to_rad(4.0)
		dist = maxf(dist, size * 0.9)
	elif view == "tactical":
		pitch = deg_to_rad(57.0)
		dist = 26.0
		cam.fov = 55.0
	var dir := Vector3(sin(deg_to_rad(-30.0)) * cos(pitch), sin(pitch), cos(deg_to_rad(-30.0)) * cos(pitch))
	cam.position = look + dir * dist
	cam.position.y = 1.6 if view == "low" else maxf(cam.position.y, 1.6)
	cam.look_at(look)
