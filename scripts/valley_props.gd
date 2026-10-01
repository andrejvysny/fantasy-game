extends Node3D
## Rocks, understory and debris from the offline scatter (ValleyPlacements): every placed
## assets/nature asset that is neither a tree (valley_forest.gd) nor groundcover (GPU-scattered).
## Rendering: one MultiMesh per asset per chunk, contract materials (NatureAssets), per-class
## visibility range without fade. Collision from metadata: one static PhysicsServer3D body per
## chunk (layer 1). User arg --props=off skips them all (A/B).

@export var terrain_path: NodePath
@export var rock_chunk := 64.0 # cliffs, shelves, boulders, rubble
@export var plant_chunk := 64.0 # shrubs, ferns, reeds, logs, root flares, branch piles (32 m gave ~3k MultiMeshes of a few instances each)
## Visibility range ends in metres (0 = unlimited). Starting values; cliffs, shelves, large
## boulders and logs are unlimited (camera far plane and depth fog end the view).
@export var range_medium_rock := 180.0 # boulder_medium*, shore_boulder*
@export var range_rubble := 120.0
@export var range_shrub := 140.0 # also root flares, branch piles and other debris
@export var range_low_plant := 90.0 # ferns, reeds
@export var plant_sway_margin := 0.2 # covers --wind=3 (0.15 m measured); metres of cull slack for foliage wind sway

const TREE_DIR := "res://spruce_trees/models/"

var _terrain: Node
var _bodies := {} # Vector3i(chunk x, chunk z, chunk size) -> RID
var _shapes := {} # asset_id -> [Shape3D or null, Transform3D]
var instance_count := 0
var _chunk_count := 0


func _ready() -> void:
	if "--props=off" in OS.get_cmdline_user_args():
		print("valley props: off")
		return
	_terrain = get_node(terrain_path)
	var assets: Dictionary = ValleyPlacements.load(_terrain)["assets"]
	var built := 0
	for asset_id: String in assets:
		if not _is_prop(asset_id):
			continue
		_build_asset(asset_id, assets[asset_id])
		built += 1
	print("valley props: %d instances, %d assets, %d chunks" % [instance_count, built, _chunk_count])


func _exit_tree() -> void:
	for key: Vector3i in _bodies:
		PhysicsServer3D.free_rid(_bodies[key])
	_bodies.clear()


func _is_prop(asset_id: String) -> bool:
	if not NatureAssets.has(asset_id):
		if not ResourceLoader.exists(TREE_DIR + asset_id + ".glb"):
			push_warning("valley props: placed asset %s has no GLB, skipped" % asset_id)
		return false
	return not NatureAssets.meta(asset_id).get("group") in ["trees", "groundcover"]


# {"chunk": metres, "range": visibility end (0 = unlimited), "shadow": casts}
func _profile(asset_id: String) -> Dictionary:
	var meta := NatureAssets.meta(asset_id)
	var fam: String = meta.get("family", asset_id)
	if _starts(fam, ["cliff", "rock_shelf", "boulder_large"]):
		return {"chunk": rock_chunk, "range": 0.0, "shadow": true}
	if _starts(fam, ["boulder_medium", "shore_boulder"]):
		return {"chunk": rock_chunk, "range": range_medium_rock, "shadow": true}
	if fam.begins_with("rubble"):
		return {"chunk": rock_chunk, "range": range_rubble, "shadow": true}
	if _starts(fam, ["fallen_log", "log"]):
		return {"chunk": plant_chunk, "range": 0.0, "shadow": true}
	if fam.begins_with("shrub"):
		return {"chunk": plant_chunk, "range": range_shrub, "shadow": true}
	if _starts(fam, ["fern", "reed"]):
		return {"chunk": plant_chunk, "range": range_low_plant, "shadow": false}
	if fam.begins_with("root_flare"):
		return {"chunk": plant_chunk, "range": range_shrub, "shadow": false}
	if meta.get("group") == "rocks":
		return {"chunk": rock_chunk, "range": range_medium_rock, "shadow": true}
	return {"chunk": plant_chunk, "range": range_shrub, "shadow": true}


func _starts(s: String, prefixes: Array) -> bool:
	for p: String in prefixes:
		if s.begins_with(p):
			return true
	return false


func _build_asset(asset_id: String, recs: Array) -> void:
	var prof := _profile(asset_id)
	var size: float = prof["chunk"]
	var buckets := {} # Vector2i -> Array[Transform3D]
	for rec: Array in recs:
		var xf: Transform3D = rec[1]
		var key := Vector2i(floori(xf.origin.x / size), floori(xf.origin.z / size))
		if not buckets.has(key):
			buckets[key] = [] as Array[Transform3D]
		buckets[key].append(xf)
	var mesh := NatureAssets.mesh(asset_id)
	if mesh == null:
		return
	var shape: Array = _shape_for(asset_id, mesh)
	for key: Vector2i in buckets:
		var xforms: Array[Transform3D] = buckets[key]
		var inst := _chunk_instance(mesh, xforms, prof)
		inst.name = "%s_%d_%d" % [asset_id, key.x, key.y]
		add_child(inst)
		if shape[0]:
			var body := _body(Vector3i(key.x, key.y, int(size)))
			for xf in xforms:
				PhysicsServer3D.body_add_shape(body, (shape[0] as Shape3D).get_rid(), xf * (shape[1] as Transform3D))
		instance_count += xforms.size()


func _chunk_instance(mesh: Mesh, xforms: Array[Transform3D], prof: Dictionary) -> MultiMeshInstance3D:
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.mesh = mesh
	mm.instance_count = xforms.size()
	for j in xforms.size():
		mm.set_instance_transform(j, xforms[j])
	var inst := MultiMeshInstance3D.new()
	inst.multimesh = mm
	var on := GeometryInstance3D.SHADOW_CASTING_SETTING_ON
	inst.cast_shadow = on if prof["shadow"] else GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	inst.visibility_range_end = prof["range"]
	inst.visibility_range_fade_mode = GeometryInstance3D.VISIBILITY_RANGE_FADE_DISABLED
	if _has_foliage(mesh):
		inst.extra_cull_margin = plant_sway_margin
	_chunk_count += 1
	return inst


func _has_foliage(mesh: Mesh) -> bool:
	for s in mesh.get_surface_count():
		if mesh.surface_get_material(s) == NatureAssets.FOLIAGE:
			return true
	return false


# [Shape3D or null, shape offset from the pivot], cached per asset (shared by all instances).
func _shape_for(asset_id: String, mesh: Mesh) -> Array:
	if _shapes.has(asset_id):
		return _shapes[asset_id]
	var col: Dictionary = NatureAssets.meta(asset_id).get("collision", {})
	var out: Array = [null, Transform3D()]
	match col.get("class", "none"):
		"convex":
			out[0] = mesh.create_convex_shape(true, true)
		"trimesh":
			out[0] = mesh.create_trimesh_shape()
		"trunk":
			var cyl := CylinderShape3D.new()
			cyl.radius = col["radius"]
			cyl.height = col["height"]
			out = [cyl, Transform3D(Basis(), Vector3(0.0, cyl.height * 0.5, 0.0))]
	_shapes[asset_id] = out
	return out


func _body(key: Vector3i) -> RID:
	if _bodies.has(key):
		return _bodies[key]
	var body := PhysicsServer3D.body_create()
	PhysicsServer3D.body_set_mode(body, PhysicsServer3D.BODY_MODE_STATIC)
	PhysicsServer3D.body_set_collision_layer(body, 1)
	PhysicsServer3D.body_set_collision_mask(body, 0)
	PhysicsServer3D.body_set_space(body, get_world_3d().space)
	_bodies[key] = body
	return body
