extends Node3D

@export var world_seed: int = 1337
@export var size: int = 256
@export var amplitude: float = 2.0
## Persistent so texture assignments and tuning survive reloads.
@export var material: ShaderMaterial = preload("res://materials/terrain.tres")

const CHUNK_QUADS := 32

var _noise: FastNoiseLite


func _ready() -> void:
	_build_mesh()
	_build_collision()
	_build_walls()


# Lazy so Forest/Player can query heights regardless of _ready order.
func _ensure_noise() -> void:
	if _noise != null:
		return
	_noise = FastNoiseLite.new()
	_noise.noise_type = FastNoiseLite.TYPE_SIMPLEX
	_noise.frequency = 0.008
	_noise.fractal_type = FastNoiseLite.FRACTAL_FBM
	_noise.fractal_octaves = 4
	_noise.seed = world_seed


func get_height(x: float, z: float) -> float:
	_ensure_noise()
	var h := _noise.get_noise_2d(x, z) * amplitude
	var r := Vector2(x, z).length()
	if r < 8.0:
		h = lerpf(0.0, h, smoothstep(4.0, 8.0, r))
	return h


func _build_mesh() -> void:
	var root := Node3D.new()
	root.name = "TerrainMesh"
	add_child(root)
	var chunks := size / CHUNK_QUADS
	for cz in chunks:
		for cx in chunks:
			var mi := MeshInstance3D.new()
			mi.name = "TerrainChunk_%d_%d" % [cx, cz]
			mi.mesh = _build_chunk(cx, cz)
			mi.material_override = material
			root.add_child(mi)


# Normals come from the height function, not the mesh, so they match across chunk borders.
func _normal_at(x: float, z: float) -> Vector3:
	return Vector3(get_height(x - 1.0, z) - get_height(x + 1.0, z), 2.0, get_height(x, z - 1.0) - get_height(x, z + 1.0)).normalized()


func _build_chunk(cx: int, cz: int) -> Mesh:
	var half := size / 2
	var n := CHUNK_QUADS + 1
	var st := SurfaceTool.new()
	st.begin(Mesh.PRIMITIVE_TRIANGLES)
	for zi in n:
		for xi in n:
			var gx := cx * CHUNK_QUADS + xi
			var gz := cz * CHUNK_QUADS + zi
			var x := float(gx - half)
			var z := float(gz - half)
			var h := get_height(x, z)
			st.set_uv(Vector2(float(gx) / size, float(gz) / size))
			st.set_normal(_normal_at(x, z))
			st.add_vertex(Vector3(x, h, z))
	for zi in CHUNK_QUADS:
		for xi in CHUNK_QUADS:
			var i := zi * n + xi
			# Clockwise from above in Godot's front-face convention => normals up.
			st.add_index(i)
			st.add_index(i + 1)
			st.add_index(i + n)
			st.add_index(i + 1)
			st.add_index(i + n + 1)
			st.add_index(i + n)
	var im := ImporterMesh.new()
	im.add_surface(Mesh.PRIMITIVE_TRIANGLES, st.commit_to_arrays())
	im.generate_lods(25.0, 60.0, [])
	return im.get_mesh()


func _build_collision() -> void:
	var half := size / 2
	var n := size + 1
	var data := PackedFloat32Array()
	data.resize(n * n)
	for zi in n:
		for xi in n:
			data[zi * n + xi] = get_height(float(xi - half), float(zi - half))
	var shape := HeightMapShape3D.new()
	shape.map_width = n
	shape.map_depth = n
	shape.map_data = data
	var body := StaticBody3D.new()
	body.name = "TerrainBody"
	# Layer 1 for player collision, layer 3 so the camera can test terrain only.
	body.collision_layer = 1 | (1 << 2)
	var cs := CollisionShape3D.new()
	cs.shape = shape
	body.add_child(cs)
	add_child(body)


func _build_walls() -> void:
	var half := size / 2.0
	var t := 1.0
	var span := size + 2.0 * t
	var defs := [
		[Vector3(half + t * 0.5, 0, 0), Vector3(t, 60, span)],
		[Vector3(-half - t * 0.5, 0, 0), Vector3(t, 60, span)],
		[Vector3(0, 0, half + t * 0.5), Vector3(span, 60, t)],
		[Vector3(0, 0, -half - t * 0.5), Vector3(span, 60, t)],
	]
	var body := StaticBody3D.new()
	body.name = "Walls"
	body.collision_layer = 1
	for d in defs:
		var cs := CollisionShape3D.new()
		var box := BoxShape3D.new()
		box.size = d[1]
		cs.shape = box
		cs.position = d[0]
		body.add_child(cs)
	add_child(body)
