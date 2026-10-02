extends SceneTree
## FG-01/02 headless check:
##   godot --headless --path . --script res://scripts/integration/verify_integration.gd
## Loads the roundtrip test scene and checks wrappers, material overrides per profile, collision
## per policy and that nothing under res://addons is needed at runtime.

const SCENE := "res://scenes/integration/asset_roundtrip_test.tscn"
const POLICY := preload("res://scripts/integration/integration_asset.gd")
const NATURE_MATS := {"M_foliage": "res://materials/nature/nature_foliage.tres"}
const SPRUCE_MAT := "res://materials/integration/spruce_legacy.tres"

var _fails := 0
var _checks := 0


func _init() -> void:
	var packed := load(SCENE) as PackedScene
	_check(packed != null, "scene loads")
	if packed == null:
		quit(1)
		return
	var root := packed.instantiate()
	root.set_process(false)
	get_root().add_child(root)
	await process_frame
	_check_no_addon_deps(SCENE)
	var row_a := root.get_node("RowA")
	_check(row_a.get_child_count() == 7, "RowA has 7 integration_asset parents (%d)" % row_a.get_child_count())
	for parent: Node in row_a.get_children():
		_check_asset(parent)
	print("verify_integration: %d checks, %d failures" % [_checks, _fails])
	root.queue_free()
	quit(1 if _fails > 0 else 0)


func _check_asset(parent: Node) -> void:
	var b := String(parent.name)
	var wrapper: Node = null
	for c in parent.get_children():
		if c.has_meta("assetstudio_binding"):
			wrapper = c
	_check(wrapper != null and wrapper.get_meta("assetstudio_binding") == b, "%s: wrapper instanced with binding meta" % b)
	if wrapper == null:
		return
	var meshes := wrapper.find_children("*", "MeshInstance3D", true, false)
	_check(not meshes.is_empty(), "%s: MeshInstance3D present" % b)
	for mi: MeshInstance3D in meshes:
		for s in mi.mesh.get_surface_count():
			_check_surface(b, mi, s)
	_check_collision(parent, b, wrapper)


func _check_surface(b: String, mi: MeshInstance3D, s: int) -> void:
	var over := mi.get_surface_override_material(s)
	var src_name := mi.mesh.surface_get_material(s).resource_name if mi.mesh.surface_get_material(s) else ""
	match b:
		"fg_pine_open_a", "fg_spruce_mature_a":
			var want := "res://materials/nature/nature_foliage.tres" if src_name == "M_foliage" else "res://materials/nature/nature_wood.tres"
			_check(over != null and over.resource_path == want, "%s s%d (%s): override %s" % [b, s, src_name, want])
		"fg_boulder_large_a":
			_check(over != null and over.resource_path == "res://materials/nature/nature_rock.tres", "%s s%d: nature_rock" % [b, s])
		"fg_spruce_legacy_l_long_s27":
			_check(over != null and over.resource_path == SPRUCE_MAT, "%s s%d: spruce_legacy" % [b, s])
		"fg_campfire", "fg_wooden_lodge":
			var m := over as StandardMaterial3D
			_check(m != null and m.metallic == 0.0 and m.metallic_texture == null, "%s s%d: patched dielectric" % [b, s])
		"fg_grass_tuft":
			_check(over == null, "%s s%d: preserved (no override)" % [b, s])


func _check_collision(parent: Node, b: String, wrapper: Node) -> void:
	var pol: Dictionary = POLICY.policy_for(b)
	var cls: String = pol.get("class", "")
	var bodies: Array[Node] = []
	for c in parent.get_children():
		if c is StaticBody3D:
			bodies.append(c)
	var want := 0 if cls == "none" else 1
	_check(bodies.size() == want, "%s: %d policy body(ies) for class %s (got %d)" % [b, want, cls, bodies.size()])
	_check(wrapper.find_children("*", "CollisionObject3D", true, false).is_empty(), "%s: no asset-shipped collision left" % b)
	if bodies.size() != 1:
		return
	var body := bodies[0] as StaticBody3D
	_check(body.collision_layer == 1 and body.collision_mask == 0, "%s: layer 1 mask 0" % b)
	var shape := (body.get_child(0) as CollisionShape3D).shape
	match cls:
		"trunk":
			_check(shape is CylinderShape3D and is_equal_approx(shape.radius, pol["radius"]) and is_equal_approx(shape.height, pol["height"]), "%s: trunk cylinder r/h" % b)
		"convex":
			_check(shape is ConvexPolygonShape3D and shape.points.size() > 3, "%s: convex hull" % b)
		"box":
			_check(shape is BoxShape3D and shape.size.x > 0.0 and shape.size.y > 0.0, "%s: box from mesh AABB" % b)


func _check_no_addon_deps(path: String) -> void:
	var seen := {}
	var stack: Array[String] = [path]
	for f in DirAccess.get_files_at("res://assets/prefabs"):
		if f.ends_with(".tscn"):
			stack.append("res://assets/prefabs/" + f) # loaded by path from the scene script
	while not stack.is_empty():
		var p: String = stack.pop_back()
		if seen.has(p):
			continue
		seen[p] = true
		for d in ResourceLoader.get_dependencies(p):
			var dp := d.get_slice("::", 2) if d.contains("::") else d
			if dp.begins_with("res://") and (dp.ends_with(".tscn") or dp.ends_with(".gd") or dp.ends_with(".tres")):
				stack.append(dp)
	var bad := seen.keys().filter(func(k: String) -> bool: return k.begins_with("res://addons/"))
	_check(bad.is_empty(), "no res://addons dependency in scene closure (%d resources)" % seen.size())


func _check(ok: bool, msg: String) -> void:
	_checks += 1
	if not ok:
		_fails += 1
	print(("PASS " if ok else "FAIL ") + msg)
