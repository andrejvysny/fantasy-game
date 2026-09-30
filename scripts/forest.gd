extends Node3D

@export var terrain_path: NodePath
@export var world_seed: int = 1337
@export var tree_cell: float = 5.0
@export var tree_density: float = 0.85
@export var glade_threshold: float = 0.45
@export var bush_count: int = 300
@export var rock_count: int = 120
@export var canopy_radius: float = 3.5

const MAX_SLOPE := 0.7
const EDGE := 124.0
const CHUNK := 32.0
const TREE_DIR := "res://spruce_trees/models/"
const TREE_SHADER := preload("res://materials/world_double_sided.gdshader")
const DEAD_SHARE := 0.06
const MASK_SIZE := 256 # 1 px per metre, covers the whole terrain

var _terrain: Node
var _rng := RandomNumberGenerator.new()
var _variants: Array[PackedScene] = []
var _weights: Array[float] = []
var _weight_sum := 0.0
var _canopy: Image


func _ready() -> void:
	_terrain = get_node(terrain_path)
	_rng.seed = world_seed
	_build_trees()
	_build_bushes()
	_build_rocks()


func _slope(x: float, z: float) -> float:
	var h: float = _terrain.get_height(x, z)
	var dx: float = _terrain.get_height(x + 1.0, z) - h
	var dz: float = _terrain.get_height(x, z + 1.0) - h
	return sqrt(dx * dx + dz * dz)


# Returns Vector2(x, z), or Vector2.INF if the sampled point is rejected.
func _sample_point(clearing: float) -> Vector2:
	var p := Vector2(_rng.randf_range(-EDGE, EDGE), _rng.randf_range(-EDGE, EDGE))
	if p.length() < clearing or _slope(p.x, p.y) > MAX_SLOPE:
		return Vector2.INF
	return p


func _scatter(count: int, clearing: float) -> Array[Vector2]:
	var pts: Array[Vector2] = []
	var attempts := 0
	while pts.size() < count and attempts < count * 30:
		attempts += 1
		var p := _sample_point(clearing)
		if p != Vector2.INF:
			pts.append(p)
	return pts


func _make_chunked(parent_name: String, mesh: Mesh, material: Material, transforms: Array[Transform3D], colors: Array[Color], shadows: bool, range_end: float) -> void:
	var parent := Node3D.new()
	parent.name = parent_name
	add_child(parent)
	var buckets := {}
	for i in transforms.size():
		var o := transforms[i].origin
		var key := Vector2i(floori((o.x + 128.0) / CHUNK), floori((o.z + 128.0) / CHUNK))
		if not buckets.has(key):
			buckets[key] = [] as Array[int]
		buckets[key].append(i)
	for key: Vector2i in buckets:
		var idx: Array[int] = buckets[key]
		var mm := MultiMesh.new()
		mm.transform_format = MultiMesh.TRANSFORM_3D
		mm.use_colors = not colors.is_empty()
		mm.mesh = mesh
		mm.instance_count = idx.size()
		for j in idx.size():
			mm.set_instance_transform(j, transforms[idx[j]])
			if mm.use_colors:
				mm.set_instance_color(j, colors[idx[j]])
		var inst := MultiMeshInstance3D.new()
		inst.name = "%s_%d_%d" % [parent_name, key.x, key.y]
		inst.multimesh = mm
		inst.material_override = material
		inst.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON if shadows else GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		_set_visibility_range(inst, range_end)
		parent.add_child(inst)


func _set_visibility_range(inst: GeometryInstance3D, range_end: float, margin: float = 15.0) -> void:
	inst.visibility_range_end = range_end
	inst.visibility_range_end_margin = margin
	inst.visibility_range_fade_mode = GeometryInstance3D.VISIBILITY_RANGE_FADE_SELF


const WORLD_SHADER := preload("res://materials/world.gdshader")


func _material(color: Color, vertex_colors: bool, flat: bool = false, dither: bool = false) -> ShaderMaterial:
	var m := ShaderMaterial.new()
	m.shader = WORLD_SHADER
	m.set_shader_parameter("albedo", color)
	m.set_shader_parameter("use_vertex_color", vertex_colors)
	m.set_shader_parameter("flat_shading", flat)
	m.set_shader_parameter("dither_occlusion", dither)
	return m


func _vary(base: Color, amount: float) -> Color:
	var v := _rng.randf_range(-amount, amount)
	return Color(base.r + v, base.g + v * 1.5, base.b + v)


# Jittered grid instead of rejection sampling: O(n) for ~1000 trees, and keeps
# trunks >= tree_cell * 0.3 apart. Low-frequency noise cuts glades, which give
# the sun deliberate canopy gaps for light shafts.
func _place_trees() -> Array[Vector2]:
	var glades := FastNoiseLite.new()
	glades.seed = world_seed + 1
	glades.frequency = 0.02
	var pts: Array[Vector2] = []
	var cells := int(2.0 * EDGE / tree_cell)
	var jitter := tree_cell * 0.35
	for cz in cells:
		for cx in cells:
			if _rng.randf() > tree_density:
				continue
			var c := Vector2(-EDGE + (cx + 0.5) * tree_cell, -EDGE + (cz + 0.5) * tree_cell)
			var p := c + Vector2(_rng.randf_range(-jitter, jitter), _rng.randf_range(-jitter, jitter))
			if p.length() < 6.0 or glades.get_noise_2d(p.x, p.y) > glade_threshold:
				continue
			pts.append(p)
	return pts


func _load_tree_variants() -> void:
	var files := ResourceLoader.list_directory(TREE_DIR)
	files.sort()
	var live_names: Array[String] = []
	var dead_names: Array[String] = []
	for f in files:
		if not f.ends_with(".glb"):
			continue
		if f.begins_with("dead_"):
			dead_names.append(f)
		else:
			live_names.append(f)
	var dead_weight := DEAD_SHARE / (1.0 - DEAD_SHARE) * live_names.size() / maxf(dead_names.size(), 1)
	for f in live_names:
		_add_variant(f, 1.0)
	for f in dead_names:
		_add_variant(f, dead_weight)


func _add_variant(file: String, weight: float) -> void:
	_variants.append(load(TREE_DIR + file) as PackedScene)
	_weights.append(weight)
	_weight_sum += weight


func _pick_variant() -> int:
	var r := _rng.randf() * _weight_sum
	for i in _weights.size():
		r -= _weights[i]
		if r <= 0.0:
			return i
	return _weights.size() - 1


func _tree_material() -> ShaderMaterial:
	var m := ShaderMaterial.new()
	m.shader = TREE_SHADER
	m.set_shader_parameter("use_vertex_color", true)
	m.set_shader_parameter("flat_shading", false)
	m.set_shader_parameter("dither_occlusion", true)
	m.set_shader_parameter("brush_strength", 0.12)
	m.set_shader_parameter("saturation", 0.85)
	return m


func _build_trees() -> void:
	_load_tree_variants()
	var mat := _tree_material()
	var parent := Node3D.new()
	parent.name = "Trees"
	add_child(parent)
	var crowns: Array[Vector3] = [] # x, z, radius
	for p in _place_trees():
		var vi := _pick_variant()
		var tree := _variants[vi].instantiate() as Node3D
		var s := _rng.randf_range(0.85, 1.15)
		var rot := Basis(Vector3.UP, _rng.randf_range(0.0, TAU))
		# Sunk slightly so trunks stay planted on slopes.
		tree.transform = Transform3D(rot.scaled(Vector3.ONE * s), Vector3(p.x, _terrain.get_height(p.x, p.y) - 0.15, p.y))
		var mi := tree.get_node("Tree") as MeshInstance3D
		mi.material_override = mat
		mi.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON
		_set_visibility_range(mi, 110.0, 15.0)
		tree.set_meta("variant", vi)
		parent.add_child(tree)
		crowns.append(Vector3(p.x, p.y, canopy_radius * s))
	_build_canopy_mask(crowns)


func _build_bushes() -> void:
	var mesh := SphereMesh.new()
	mesh.radius = 0.7
	mesh.height = 1.0
	mesh.radial_segments = 8
	mesh.rings = 4
	var xs: Array[Transform3D] = []
	var cs: Array[Color] = []
	for p in _scatter(bush_count, 6.0):
		var s := _rng.randf_range(0.6, 1.3)
		var b := Basis(Vector3.UP, _rng.randf_range(0.0, TAU)).scaled(Vector3.ONE * s)
		xs.append(Transform3D(b, Vector3(p.x, _terrain.get_height(p.x, p.y) + 0.2, p.y)))
		cs.append(_vary(Color("#3d4f2e"), 0.04))
	_make_chunked("Bushes", mesh, _material(Color.WHITE, true, true), xs, cs, false, 130.0)


func _build_rocks() -> void:
	var mesh := SphereMesh.new()
	mesh.radius = 0.5
	mesh.height = 0.7
	mesh.radial_segments = 6
	mesh.rings = 3
	var xs: Array[Transform3D] = []
	for p in _scatter(rock_count, 6.0):
		var b := Basis.from_euler(Vector3(_rng.randf_range(0.0, TAU), _rng.randf_range(0.0, TAU), _rng.randf_range(0.0, TAU)))
		b = b.scaled(Vector3(_rng.randf_range(0.5, 1.5), _rng.randf_range(0.5, 1.5), _rng.randf_range(0.5, 1.5)))
		xs.append(Transform3D(b, Vector3(p.x, _terrain.get_height(p.x, p.y) + 0.1, p.y)))
	_make_chunked("Rocks", mesh, _material(Color("#6a6562"), false, true), xs, [], true, 130.0)



# Canopy coverage 0..1 per metre; the ground shader uses it for needle litter and
# the grass scatter thins out under trees.
func _build_canopy_mask(crowns: Array[Vector3]) -> void:
	var data := PackedFloat32Array()
	data.resize(MASK_SIZE * MASK_SIZE)
	var half := MASK_SIZE / 2
	for c in crowns:
		var r := c.z
		for py in range(maxi(floori(c.y - r) + half, 0), mini(ceili(c.y + r) + half, MASK_SIZE - 1) + 1):
			for px in range(maxi(floori(c.x - r) + half, 0), mini(ceili(c.x + r) + half, MASK_SIZE - 1) + 1):
				var d := Vector2(px - half + 0.5 - c.x, py - half + 0.5 - c.y).length() / r
				if d < 1.0:
					var i := py * MASK_SIZE + px
					data[i] = maxf(data[i], 1.0 - d * d)
	_canopy = Image.create_from_data(MASK_SIZE, MASK_SIZE, false, Image.FORMAT_RF, data.to_byte_array())
	RenderingServer.global_shader_parameter_set("canopy_mask", ImageTexture.create_from_image(_canopy))


func canopy_at(x: float, z: float) -> float:
	var px := clampi(floori(x) + MASK_SIZE / 2, 0, MASK_SIZE - 1)
	var pz := clampi(floori(z) + MASK_SIZE / 2, 0, MASK_SIZE - 1)
	return _canopy.get_pixel(px, pz).r
