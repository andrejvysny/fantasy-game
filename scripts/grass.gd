extends Node3D

@export var terrain_path: NodePath
@export var forest_path: NodePath
@export var world_seed := 4242
@export var cell := 0.6
@export var max_keep := 0.9
@export var blades_per_clump := 9
@export var min_height := 0.3
@export var max_height := 0.7
@export var clump_radius := 0.25
@export var fade_end := 80.0
@export var chunk := 16.0

const EDGE := 124.0
const MAX_SLOPE := 0.7
const CLEAR_GROUP := "grass_clear" # nodes in this group keep a bare patch around them
const CLEAR_RADIUS := 1.4
const GRASS_SHADER := preload("res://materials/grass.gdshader")

var _terrain: Node
var _forest: Node
var _rng := RandomNumberGenerator.new()


func _ready() -> void:
	_terrain = get_node(terrain_path)
	_forest = get_node(forest_path)
	_rng.seed = world_seed
	var mesh := _build_clump_mesh()
	var material := _material()
	var placed := _place()
	_make_chunked(mesh, material, placed[0], placed[1])


func _slope(x: float, z: float) -> float:
	var h: float = _terrain.get_height(x, z)
	var dx: float = _terrain.get_height(x + 1.0, z) - h
	var dz: float = _terrain.get_height(x, z + 1.0) - h
	return sqrt(dx * dx + dz * dz)


func _material() -> ShaderMaterial:
	var m := ShaderMaterial.new()
	m.shader = GRASS_SHADER
	m.set_shader_parameter("wrap", 0.6)
	m.set_shader_parameter("brush_strength", 0.0)
	m.set_shader_parameter("fade_end", fade_end)
	m.set_shader_parameter("fade_start", fade_end - 20.0)
	return m


func _vert(st: SurfaceTool, pos: Vector3, normal: Vector3, uv: Vector2, color: Color) -> void:
	st.set_normal(normal)
	st.set_uv(uv)
	st.set_color(color)
	st.add_vertex(pos)


func _build_clump_mesh() -> ArrayMesh:
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	for i in blades_per_clump:
		_add_blade(st)
	return st.commit()


func _add_blade(st: SurfaceTool) -> void:
	var disc := Vector2.from_angle(_rng.randf() * TAU) * (clump_radius * sqrt(_rng.randf()))
	var origin := Vector3(disc.x, 0.0, disc.y)
	var yaw := _rng.randf() * TAU
	var side := Vector3(cos(yaw), 0.0, -sin(yaw))
	var facing := Vector3(sin(yaw), 0.0, cos(yaw))
	var height := _rng.randf_range(min_height, max_height)
	var width := 0.045
	# Small per-blade spread; most variation comes per clump (instance colour) so patches read as groups.
	var v := _rng.randf_range(0.95, 1.03)
	var color := Color(v, v, v)
	# rows: base, mid, tip as (t, half-width)
	var rows := [Vector2(0.0, width), Vector2(0.5, width * 0.6), Vector2(1.0, 0.0)]
	var pts: Array[Vector3] = []
	var uvs: Array[Vector2] = []
	for r: Vector2 in rows:
		var c := origin + Vector3.UP * (height * r.x) + facing * (0.18 * height * r.x * r.x)
		if r.y > 0.0:
			pts.append(c - side * r.y)
			pts.append(c + side * r.y)
			uvs.append(Vector2(0.0, r.x))
			uvs.append(Vector2(1.0, r.x))
		else:
			pts.append(c)
			uvs.append(Vector2(0.5, r.x))
	# pts: 0,1 base; 2,3 mid; 4 tip
	for idx in [0, 1, 2, 1, 3, 2, 2, 3, 4]:
		_vert(st, pts[idx], facing, uvs[idx], color)


# Transforms plus one colour per clump.
func _place() -> Array:
	var noise := FastNoiseLite.new()
	noise.seed = world_seed
	noise.frequency = 0.03
	var clear: Array[Vector3] = [] # x, z, radius
	for node: Node3D in get_tree().get_nodes_in_group(CLEAR_GROUP):
		clear.append(Vector3(node.global_position.x, node.global_position.z, node.get_meta("grass_clear_radius", CLEAR_RADIUS)))
	var out: Array[Transform3D] = []
	var colors: Array[Color] = []
	var jitter := cell * 0.45
	var n := int(ceil(2.0 * EDGE / cell))
	for i in n:
		for j in n:
			var x := -EDGE + i * cell + _rng.randf_range(-jitter, jitter)
			var z := -EDGE + j * cell + _rng.randf_range(-jitter, jitter)
			# No baseline density: low-noise areas stay genuinely quiet ground.
			var patch := smoothstep(-0.15, 0.35, noise.get_noise_2d(x, z))
			var keep: float = max_keep * patch * (1.0 - 0.85 * _forest.canopy_at(x, z))
			keep *= 1.0 - smoothstep(0.1, 0.5, _forest.wear_at(x, z))
			if _rng.randf() >= keep or _slope(x, z) > MAX_SLOPE or _near_any(Vector2(x, z), clear):
				continue
			var basis := Basis(Vector3.UP, _rng.randf() * TAU).scaled(Vector3.ONE * _rng.randf_range(0.8, 1.25))
			out.append(Transform3D(basis, Vector3(x, _terrain.get_height(x, z), z)))
			# Tint follows a slow field so neighbouring clumps share a colour; random part stays small.
			var v := 1.0 + noise.get_noise_2d(x * 0.4 + 311.0, z * 0.4) * 0.14 + _rng.randf_range(-0.03, 0.03)
			var warm := noise.get_noise_2d(x * 0.3 - 97.0, z * 0.3 + 53.0) * 0.08
			colors.append(Color(v * (1.0 + warm), v, v * (1.0 - warm)))
	return [out, colors]


func _near_any(p: Vector2, points: Array[Vector3]) -> bool:
	for q in points:
		if p.distance_to(Vector2(q.x, q.y)) < q.z:
			return true
	return false


func _make_chunked(mesh: Mesh, material: Material, transforms: Array[Transform3D], colors: Array[Color]) -> void:
	var parent := Node3D.new()
	parent.name = "GrassChunks"
	add_child(parent)
	var buckets := {}
	for i in transforms.size():
		var o := transforms[i].origin
		var key := Vector2i(floori((o.x + 128.0) / chunk), floori((o.z + 128.0) / chunk))
		if not buckets.has(key):
			buckets[key] = [] as Array[int]
		buckets[key].append(i)
	for key: Vector2i in buckets:
		var list: Array[int] = buckets[key]
		var mm := MultiMesh.new()
		mm.transform_format = MultiMesh.TRANSFORM_3D
		mm.use_colors = true
		mm.mesh = mesh
		mm.instance_count = list.size()
		for j in list.size():
			mm.set_instance_transform(j, transforms[list[j]])
			mm.set_instance_color(j, colors[list[j]])
		var inst := MultiMeshInstance3D.new()
		inst.name = "Grass_%d_%d" % [key.x, key.y]
		inst.multimesh = mm
		inst.material_override = material
		inst.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		inst.extra_cull_margin = 1.0
		inst.visibility_range_end = fade_end + chunk * 0.75
		inst.visibility_range_end_margin = 0.0
		inst.visibility_range_fade_mode = GeometryInstance3D.VISIBILITY_RANGE_FADE_DISABLED
		parent.add_child(inst)
