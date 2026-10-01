extends Node3D
## Spruce forest for the valley. "generated": trees from the offline scatter (world/generated +
## overrides, ValleyPlacements), library spruces and assets/nature trees alike. "legacy": runtime
## jittered grid; density follows the painted forest-floor layer, with lone trees in meadows and
## on scree; none on water, rock, sand, paths or steep ground. User arg --forest=legacy forces it.
## Rendering: one MultiMesh per chunk per variant (mesh LODs + visibility range).
## Collision: trunk shapes (GLB TrunkCollision or metadata cylinder) added straight to
## PhysicsServer3D per chunk.

@export var terrain_path: NodePath
@export_enum("generated", "legacy") var placement_mode := "generated"
@export var world_seed := 2024
@export var cell := 4.5 # jittered grid spacing, metres
@export var forest_density := 0.9
@export var meadow_density := 0.03
@export var scree_density := 0.06
@export var max_slope := 0.85 # rise over run
@export var min_height := 0.8 # keep shores and river beds clear
@export var chunk := 64.0
@export var view_range := 0.0 # 0 = unlimited; camera far plane and depth fog end the view
@export var crown_sway_margin := 0.8 # covers --wind=3 (0.66 m measured); metres of cull slack for nature-tree crown wind sway
@export var scale_range := Vector2(0.9, 1.3)
## file name -> relative weight
@export var variants := {
	"spruce_L_normal_std_s25": 1.2, "spruce_L_normal_std_irregular_s21": 1.2,
	"spruce_L_slim_std_s32": 1.0, "spruce_L_wide_std_s3": 1.0, "spruce_L_normal_tall_s21": 0.8,
	"spruce_M_normal_std_s9": 1.0, "spruce_M_normal_std_layered_s6": 1.0,
	"spruce_M_slim_std_s27": 1.0, "spruce_M_wide_std_s35": 1.0, "spruce_M_normal_long_s11": 0.8,
	"spruce_S_normal_std_s10": 0.6, "spruce_S_wide_std_dense_s39": 0.6,
	"dead_M_std_s3": 0.12, "dead_L_std_s3": 0.12,
}

const TREE_DIR := "res://spruce_trees/models/"
const TREE_SHADER := preload("res://materials/world_double_sided_mm.gdshader")
const NATURE_WOOD := preload("res://materials/nature/nature_wood.tres")
const NATURE_FOLIAGE := preload("res://materials/nature/nature_foliage.tres")
# Layer indices in ValleyTerrain.get_layers().
const WATER_DEEP := 0
const WATER_SHALLOW := 1
const ROCK := 2
const SAND := 3
const SCREE := 4
const DIRT := 5
const FOREST := 6
const GRASS_DRY := 7
const GRASS := 8

var _terrain: Node
var _rng := RandomNumberGenerator.new()
var _meshes: Array[Mesh] = []
var _shapes: Array[Shape3D] = []
var _shape_xforms: Array[Transform3D] = []
var _weights: Array[float] = []
# Per variant: material_override (null = the mesh's own surface materials) and cull margin.
var _overrides: Array[Material] = []
var _margins: Array[float] = []
var _bodies: Array[RID] = []
var tree_count := 0
var _mat: ShaderMaterial
var _nature_mats: Array[ShaderMaterial] = [] # [bark, crown], built on first nature tree
# Per placed tree, for tree_occluder.gd (fade goes through MultiMesh custom data).
var _occ_bases := PackedVector3Array()
var _occ_tops := PackedFloat32Array()
var _occ_radii := PackedFloat32Array()
var _occ_mm: Array[MultiMesh] = []
var _occ_idx := PackedInt32Array()


func _ready() -> void:
	_terrain = get_node(terrain_path)
	_rng.seed = world_seed
	if "--forest=legacy" in OS.get_cmdline_user_args():
		placement_mode = "legacy"
	_mat = _tree_material()
	var placed := _place_generated() if placement_mode == "generated" else _place_legacy()
	if placed.is_empty() and placement_mode == "generated":
		# Missing or unreadable world/generated must never leave the valley treeless.
		push_warning("valley forest: no generated trees, falling back to legacy scatter")
		placement_mode = "legacy"
		for arr: Array in [_meshes, _shapes, _shape_xforms, _overrides, _margins, _weights]:
			arr.clear()
		placed = _place_legacy()
	# buckets[chunk key][variant] = Array[Transform3D]
	var buckets := {}
	for t: Array in placed:
		var xf: Transform3D = t[1]
		var key := Vector2i(floori(xf.origin.x / chunk), floori(xf.origin.z / chunk))
		if not buckets.has(key):
			buckets[key] = {}
		var per: Dictionary = buckets[key]
		if not per.has(t[0]):
			per[t[0]] = [] as Array[Transform3D]
		per[t[0]].append(xf)
	for key: Vector2i in buckets:
		_build_chunk(key, buckets[key])
	print("valley forest: %d trees in %d chunks (%s)" % [tree_count, buckets.size(), placement_mode])


func _exit_tree() -> void:
	for rid in _bodies:
		PhysicsServer3D.free_rid(rid)
	_bodies.clear()


func _place_legacy() -> Array:
	for name: String in variants:
		_load_library(name)
		_weights.append(variants[name])
	return _place_trees()


# Every placement whose asset is a library spruce or an assets/nature "trees" asset.
func _place_generated() -> Array:
	var out := []
	var assets: Dictionary = ValleyPlacements.load(_terrain)["assets"]
	for asset_id: String in assets:
		var vi := _variant_for(asset_id)
		if vi < 0:
			continue
		for rec: Array in assets[asset_id]:
			out.append([vi, rec[1]])
	return out


func _variant_for(asset_id: String) -> int:
	if ResourceLoader.exists(TREE_DIR + asset_id + ".glb"):
		_load_library(asset_id)
	elif NatureAssets.has(asset_id) and NatureAssets.meta(asset_id).get("group") == "trees" and NatureAssets.mesh(asset_id) != null:
		_load_nature(asset_id)
	else:
		return -1
	return _meshes.size() - 1


func _load_library(name: String) -> void:
	var scene := load(TREE_DIR + name + ".glb") as PackedScene
	var root := scene.instantiate() as Node3D
	_meshes.append((root.get_node("Tree") as MeshInstance3D).mesh)
	var cs := root.get_node("TrunkCollision").get_child(0) as CollisionShape3D
	_shapes.append(cs.shape)
	_shape_xforms.append((cs.get_parent() as Node3D).transform * cs.transform)
	_overrides.append(_mat)
	_margins.append(0.0)
	root.free()


# Own mesh copy so bark and crown get the fadeable tree materials instead of the shared contract ones.
func _load_nature(asset_id: String) -> void:
	if _nature_mats.is_empty():
		_nature_mats = _nature_tree_materials()
	var src := NatureAssets.mesh(asset_id)
	var m := src.duplicate() as Mesh
	for s in m.get_surface_count():
		var crown := src.surface_get_material(s) == NatureAssets.FOLIAGE
		m.surface_set_material(s, _nature_mats[1] if crown else _nature_mats[0])
	_meshes.append(m)
	var col: Dictionary = NatureAssets.meta(asset_id).get("collision", {})
	if col.get("class") == "trunk":
		var cyl := CylinderShape3D.new()
		cyl.radius = col["radius"]
		cyl.height = col["height"]
		_shapes.append(cyl)
		_shape_xforms.append(Transform3D(Basis(), Vector3(0.0, cyl.height * 0.5, 0.0)))
	else:
		_shapes.append(null)
		_shape_xforms.append(Transform3D())
	_overrides.append(null)
	_margins.append(crown_sway_margin)


func _pick_variant() -> int:
	var total := 0.0
	for w in _weights:
		total += w
	var r := _rng.randf() * total
	for i in _weights.size():
		r -= _weights[i]
		if r <= 0.0:
			return i
	return _weights.size() - 1


func _probability(l: PackedFloat32Array) -> float:
	if l[WATER_DEEP] + l[WATER_SHALLOW] > 0.05 or l[ROCK] > 0.3 or l[SAND] > 0.3 or l[DIRT] > 0.35:
		return 0.0
	return forest_density * l[FOREST] + meadow_density * (l[GRASS] + l[GRASS_DRY]) + scree_density * l[SCREE]


func _slope(x: float, z: float) -> float:
	var dx: float = _terrain.get_height(x + 1.0, z) - _terrain.get_height(x - 1.0, z)
	var dz: float = _terrain.get_height(x, z + 1.0) - _terrain.get_height(x, z - 1.0)
	return 0.5 * sqrt(dx * dx + dz * dz)


# Returns [variant index, Transform3D] pairs on a jittered grid (trunks >= cell * 0.2 apart).
func _place_trees() -> Array:
	var out := []
	var half: float = _terrain.get_size() * 0.5 - 2.0
	var cells := int(2.0 * half / cell)
	var jitter := cell * 0.4
	for cz in cells:
		for cx in cells:
			var p := Vector2(-half + (cx + 0.5) * cell, -half + (cz + 0.5) * cell)
			p += Vector2(_rng.randf_range(-jitter, jitter), _rng.randf_range(-jitter, jitter))
			var roll := _rng.randf()
			if roll >= _probability(_terrain.get_layers(p.x, p.y)) or _slope(p.x, p.y) > max_slope:
				continue
			var h: float = _terrain.get_height(p.x, p.y)
			if h < min_height:
				continue
			var s := _rng.randf_range(scale_range.x, scale_range.y)
			var basis := Basis(Vector3.UP, _rng.randf_range(0.0, TAU)).scaled(Vector3.ONE * s)
			# Sunk slightly so trunks stay planted on slopes.
			out.append([_pick_variant(), Transform3D(basis, Vector3(p.x, h - 0.2, p.y))])
	return out


func _tree_material() -> ShaderMaterial:
	var m := ShaderMaterial.new()
	m.shader = TREE_SHADER
	m.set_shader_parameter("use_vertex_color", true)
	m.set_shader_parameter("flat_shading", false)
	m.set_shader_parameter("dither_occlusion", true)
	m.set_shader_parameter("use_instance_fade", true)
	m.set_shader_parameter("brush_strength", 0.12)
	m.set_shader_parameter("saturation", 0.85)
	m.set_shader_parameter("canopy_normal_blend", 0.55)
	m.set_shader_parameter("foliage_translucency", 0.35)
	m.set_shader_parameter("tree_variation", 0.12)
	return m


# [bark, crown] from the nature contract materials, with per-instance fade and tree jitter.
func _nature_tree_materials() -> Array[ShaderMaterial]:
	var bark := NATURE_WOOD.duplicate() as ShaderMaterial
	var crown := NATURE_FOLIAGE.duplicate() as ShaderMaterial
	for m in [bark, crown]:
		m.set_shader_parameter("dither_occlusion", true)
		m.set_shader_parameter("use_instance_fade", true)
	bark.set_shader_parameter("tree_variation", 0.0)
	bark.set_shader_parameter("wind_sway", 0.03)
	crown.set_shader_parameter("canopy_normal_blend", 0.55)
	crown.set_shader_parameter("foliage_translucency", 0.35)
	crown.set_shader_parameter("tree_variation", 0.12)
	crown.set_shader_parameter("wind_sway", 0.22)
	crown.set_shader_parameter("saturation", 0.85)
	return [bark, crown]


func _build_chunk(key: Vector2i, per_variant: Dictionary) -> void:
	var body := PhysicsServer3D.body_create()
	PhysicsServer3D.body_set_mode(body, PhysicsServer3D.BODY_MODE_STATIC)
	PhysicsServer3D.body_set_collision_layer(body, 1)
	PhysicsServer3D.body_set_collision_mask(body, 0)
	PhysicsServer3D.body_set_space(body, get_world_3d().space)
	_bodies.append(body)
	for vi: int in per_variant:
		var xforms: Array[Transform3D] = per_variant[vi]
		var mm := MultiMesh.new()
		mm.transform_format = MultiMesh.TRANSFORM_3D
		mm.mesh = _meshes[vi]
		mm.use_custom_data = true
		mm.instance_count = xforms.size()
		var mesh_aabb := _meshes[vi].get_aabb()
		for j in xforms.size():
			mm.set_instance_transform(j, xforms[j])
			mm.set_instance_custom_data(j, Color(0, 0, 0, 0))
			_record_tree(mm, j, xforms[j], mesh_aabb)
			if _shapes[vi]:
				PhysicsServer3D.body_add_shape(body, _shapes[vi].get_rid(), xforms[j] * _shape_xforms[vi])
		var inst := MultiMeshInstance3D.new()
		inst.name = "Trees_%d_%d_v%d" % [key.x, key.y, vi]
		inst.multimesh = mm
		inst.material_override = _overrides[vi]
		inst.extra_cull_margin = _margins[vi]
		inst.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_ON
		inst.visibility_range_end = view_range
		inst.visibility_range_fade_mode = GeometryInstance3D.VISIBILITY_RANGE_FADE_DISABLED
		add_child(inst)
		tree_count += xforms.size()


func _record_tree(mm: MultiMesh, j: int, xf: Transform3D, mesh_aabb: AABB) -> void:
	var aabb := xf * mesh_aabb
	_occ_bases.append(xf.origin)
	_occ_tops.append(aabb.end.y)
	_occ_radii.append(0.5 * maxf(aabb.size.x, aabb.size.z))
	_occ_mm.append(mm)
	_occ_idx.append(j)


## Per-tree blocker data for tree_occluder.gd: bases, crown tops (y) and crown radii.
func occluder_trees() -> Dictionary:
	return {"bases": _occ_bases, "tops": _occ_tops, "radii": _occ_radii}


func set_tree_fade(i: int, f: float) -> void:
	_occ_mm[i].set_instance_custom_data(_occ_idx[i], Color(f, 0, 0, 0))


## Every tree material (tree_occluder.gd toggles dither on all of them).
func occluder_material() -> Array[ShaderMaterial]:
	var out: Array[ShaderMaterial] = [_mat]
	out.append_array(_nature_mats)
	return out
