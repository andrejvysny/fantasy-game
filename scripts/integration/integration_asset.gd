extends Node3D
## Game-owned parent of an AssetStudio wrapper instance. Reads the wrapper's assetstudio_binding
## meta, looks the binding up in integration/collision_policy.json and builds one StaticBody3D
## sibling (layer 1, mask 0). Bodies shipped inside the asset are dropped: the game owns collision.
## Runtime-only: no addon class or script is referenced.
##   trunk  CylinderShape3D centred at y = height / 2 (radius, height from the policy)
##   convex convex hull of the wrapper mesh
##   box    mesh AABB, optional xz_scale shrink
##   none   no body

const POLICY_PATH := "res://integration/collision_policy.json"
const BINDING_META := "assetstudio_binding"
const BODY_NAME := "PolicyBody"

static var _policy := {}


static func policy_for(binding: String) -> Dictionary:
	if _policy.is_empty():
		var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(POLICY_PATH))
		if parsed is Dictionary:
			_policy = parsed.get("bindings", {})
	return _policy.get(binding, {})


func _ready() -> void:
	var wrapper := _find_wrapper()
	if wrapper == null:
		push_warning("integration_asset %s: no AssetStudio wrapper child" % name)
		return
	_drop_asset_bodies(wrapper)
	var binding := str(wrapper.get_meta(BINDING_META))
	var pol := policy_for(binding)
	if pol.is_empty():
		push_warning("integration_asset: no collision policy for %s" % binding)
		return
	var shape: Shape3D = null
	var offset := Transform3D()
	match pol.get("class", "none"):
		"trunk":
			var cyl := CylinderShape3D.new()
			cyl.radius = pol["radius"]
			cyl.height = pol["height"]
			shape = cyl
			offset = Transform3D(Basis(), Vector3(0.0, cyl.height * 0.5, 0.0))
		"convex":
			var mi := _first_mesh(wrapper)
			if mi != null:
				shape = mi.mesh.create_convex_shape(true, true)
				offset = _relative(mi, wrapper)
		"box":
			var box := BoxShape3D.new()
			var aabb := _mesh_aabb(wrapper)
			var k: float = pol.get("xz_scale", 1.0)
			box.size = Vector3(aabb.size.x * k, aabb.size.y, aabb.size.z * k)
			shape = box
			offset = Transform3D(Basis(), aabb.get_center())
	if shape == null:
		return
	var body := StaticBody3D.new()
	body.name = BODY_NAME
	body.collision_layer = 1
	body.collision_mask = 0
	body.set_meta("collision_class", pol.get("class"))
	var cs := CollisionShape3D.new()
	cs.shape = shape
	cs.transform = offset
	body.add_child(cs)
	add_child(body)


func _find_wrapper() -> Node3D:
	for c in get_children():
		if c is Node3D and c.has_meta(BINDING_META):
			return c
	return null


func _drop_asset_bodies(wrapper: Node) -> void:
	for b in wrapper.find_children("*", "CollisionObject3D", true, false):
		b.get_parent().remove_child(b)
		b.queue_free()


func _first_mesh(root: Node) -> MeshInstance3D:
	var all := root.find_children("*", "MeshInstance3D", true, false)
	return all[0] if not all.is_empty() else null


# Transform of n relative to the wrapper (the wrapper sits under this node, possibly offset).
func _relative(n: Node3D, wrapper: Node3D) -> Transform3D:
	var t := Transform3D()
	var cur: Node = n
	while cur != null and cur != wrapper.get_parent():
		if cur is Node3D:
			t = (cur as Node3D).transform * t
		cur = cur.get_parent()
	return t


func _mesh_aabb(wrapper: Node3D) -> AABB:
	var out := AABB()
	var first := true
	for mi: MeshInstance3D in wrapper.find_children("*", "MeshInstance3D", true, false):
		var a := _relative(mi, wrapper) * mi.get_aabb()
		out = a if first else out.merge(a)
		first = false
	return out
