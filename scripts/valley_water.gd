extends Node3D
## Water surface over every lake, river and the sea, from tools/terrain/gen_water.py data
## (res://terrains/valley/water.res: r = level m, g = coverage). Flat grid chunks are lifted
## to the level on the GPU by water.gdshader; only chunks that carry water are built. A flat
## sea skirt continues the sea past the southern and south-western map edges to the horizon.

const SKIRT_LENGTH := 1500.0 # metres of open sea beyond the map edge
const SKIRT_WEST_FROM_Z := 200.0 # sea meets the west edge from about z = +250 southwards

@export var terrain_path: NodePath
@export var material: ShaderMaterial = preload("res://materials/water.tres")
@export var data_path := "res://terrains/valley/water.res"
@export var chunk_size := 64 # metres, matches the terrain chunks
@export var quad_size := 2 # metres per grid quad
@export var chunk_range := 320.0 # camera far is 250 m

var _res := 0
var _half := 0.0


func _ready() -> void:
	var img: Image = load(data_path)
	_res = img.get_width()
	_half = (_res - 1) * 0.5
	_setup_material(img)
	_build_chunks(img.get_data().to_float32_array())
	_build_skirt()
	# A/B and perf runs: --water=0 hides all water.
	if "--water=0" in OS.get_cmdline_user_args():
		visible = false


func _setup_material(img: Image) -> void:
	var terrain := get_node(terrain_path)
	var terrain_mat := terrain.get("material") as ShaderMaterial
	var height: Texture2D = terrain_mat.get_shader_parameter("heightmap") if terrain_mat else null
	if height == null: # terrain not set up yet: load the same data it uses
		height = ImageTexture.create_from_image(load(String(terrain.get("data_dir")) + "height.res"))
	material.set_shader_parameter("heightmap", height)
	material.set_shader_parameter("water_map", ImageTexture.create_from_image(img))
	material.set_shader_parameter("map_size", float(_res))


# Per-chunk level range over covered samples; empty chunks get no mesh. A sample on a chunk
# border is a vertex of both chunks, so it counts for both.
func _chunk_ranges(data: PackedFloat32Array, n: int) -> Array[Vector2]:
	var ranges: Array[Vector2] = []
	ranges.resize(n * n)
	ranges.fill(Vector2(INF, -INF))
	for z in _res:
		var zs := _owners(z, n)
		for x in _res:
			var i := (z * _res + x) * 2
			if data[i + 1] <= 0.0:
				continue
			for cz in zs:
				for cx in _owners(x, n):
					var r := ranges[cz * n + cx]
					ranges[cz * n + cx] = Vector2(minf(r.x, data[i]), maxf(r.y, data[i]))
	return ranges


func _owners(s: int, n: int) -> Array[int]:
	var c := mini(s / chunk_size, n - 1)
	if s % chunk_size == 0 and c > 0:
		return [c, c - 1]
	return [c]


func _build_chunks(data: PackedFloat32Array) -> void:
	var mesh := PlaneMesh.new()
	mesh.size = Vector2(chunk_size, chunk_size)
	mesh.subdivide_width = chunk_size / quad_size - 1
	mesh.subdivide_depth = chunk_size / quad_size - 1
	var root := Node3D.new()
	root.name = "WaterMesh"
	add_child(root)
	var n := ceili(float(_res) / chunk_size)
	var ranges := _chunk_ranges(data, n)
	for cz in n:
		for cx in n:
			var r: Vector2 = ranges[cz * n + cx]
			if r.x > r.y:
				continue
			var mi := _make_instance(mesh, material)
			mi.name = "WaterChunk_%d_%d" % [cx, cz]
			# Vertices land on sample positions, as in valley_terrain.gd.
			mi.position = Vector3(cx * chunk_size + chunk_size * 0.5 - _half, 0.0, cz * chunk_size + chunk_size * 0.5 - _half)
			# Flat on the CPU, lifted by the shader: culling needs the level range.
			var e := chunk_size * 0.5 + 1.0
			mi.custom_aabb = AABB(Vector3(-e, r.x - 1.0, -e), Vector3(2.0 * e, r.y - r.x + 2.0, 2.0 * e))
			mi.visibility_range_end = chunk_range
			root.add_child(mi)


func _build_skirt() -> void:
	var skirt_mat := material.duplicate() as ShaderMaterial
	skirt_mat.set_shader_parameter("skirt", true)
	var lo := -_half # west/north map edge
	var hi := _half + 1.0 # south/east edge: the last chunk row reaches one metre past the samples
	var far := SKIRT_LENGTH
	# [min corner x, z, max corner x, z]: south strip across the whole map, west strip to the coast.
	var rects := [
		[lo - far, hi, hi + far, hi + far],
		[lo - far, SKIRT_WEST_FROM_Z, lo, hi],
	]
	for i in rects.size():
		var q: Array = rects[i]
		var mesh := PlaneMesh.new()
		mesh.size = Vector2(q[2] - q[0], q[3] - q[1])
		mesh.subdivide_width = 15
		mesh.subdivide_depth = 15
		var mi := _make_instance(mesh, skirt_mat)
		mi.name = "SeaSkirt_%d" % i
		mi.position = Vector3((q[0] + q[2]) * 0.5, 0.0, (q[1] + q[3]) * 0.5)
		add_child(mi)


func _make_instance(mesh: Mesh, mat: Material) -> MeshInstance3D:
	var mi := MeshInstance3D.new()
	mi.mesh = mesh
	mi.material_override = mat
	mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	return mi
