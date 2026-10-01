extends SceneTree
## Import check for assets/nature GLBs against their metadata (asset contract, assets/nature/README.md).
##   godot --headless --path . --import            (once, so new GLBs are imported)
##   godot --headless --path . --script res://tools/environment/asset_check.gd [-- group ...]
## Per asset: surfaces + material names, COLOR (with alpha range), UV2, AABB vs metadata bbox,
## triangle count, and the first mesh found. Prints FAIL lines for contract violations.

const ROOT := "res://assets/nature/"


func _init() -> void:
	var groups := OS.get_cmdline_user_args()
	var fails := 0
	var checked := 0
	for group in DirAccess.get_directories_at(ROOT):
		if not groups.is_empty() and not groups.has(group):
			continue
		for f in DirAccess.get_files_at(ROOT + group):
			if f.get_extension() != "glb":
				continue
			checked += 1
			fails += _check(ROOT + group + "/" + f)
	print("asset_check: %d assets, %d failures" % [checked, fails])
	quit(1 if fails > 0 else 0)


func _find_mesh(n: Node) -> MeshInstance3D:
	if n is MeshInstance3D:
		return n
	for c in n.get_children():
		var m := _find_mesh(c)
		if m:
			return m
	return null


func _check(path: String) -> int:
	var fails := 0
	var scene := load(path) as PackedScene
	if scene == null:
		print("FAIL %s: not importable" % path)
		return 1
	var root := scene.instantiate()
	var mi := _find_mesh(root)
	var meta_path := path.get_basename() + ".json"
	var meta: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(meta_path)) if FileAccess.file_exists(meta_path) else {}
	if mi == null:
		print("FAIL %s: no MeshInstance3D" % path)
		root.free()
		return 1
	var mesh := mi.mesh
	var xf := mi.transform
	var tris := 0
	var names := []
	var alpha := Vector2(INF, -INF)
	var has_color := true
	var has_uv2 := true
	for s in mesh.get_surface_count():
		var arrays := mesh.surface_get_arrays(s)
		var idx: PackedInt32Array = arrays[Mesh.ARRAY_INDEX]
		tris += (idx.size() if idx.size() > 0 else (arrays[Mesh.ARRAY_VERTEX] as PackedVector3Array).size()) / 3
		var mat := mesh.surface_get_material(s)
		names.append(mat.resource_name if mat else "<none>")
		if arrays[Mesh.ARRAY_COLOR] == null:
			has_color = false
		else:
			for c: Color in arrays[Mesh.ARRAY_COLOR]:
				alpha.x = minf(alpha.x, c.a)
				alpha.y = maxf(alpha.y, c.a)
		if arrays[Mesh.ARRAY_TEX_UV2] == null:
			has_uv2 = false
	var aabb := xf * mesh.get_aabb()
	var line := "%s surfaces=%s tris=%d color=%s alpha=%.2f..%.2f uv2=%s aabb=%s..%s node_xf_identity=%s" % [
		path.get_file(), names, tris, has_color, alpha.x, alpha.y, has_uv2,
		_v(aabb.position), _v(aabb.end), xf.is_equal_approx(Transform3D.IDENTITY)]
	print(line)
	for n in names:
		if n not in ["M_solid", "M_foliage"]:
			print("FAIL %s: material '%s' not in contract" % [path, n])
			fails += 1
	if not has_color:
		print("FAIL %s: no vertex colours" % path)
		fails += 1
	if not has_uv2:
		print("FAIL %s: no UV2 data channel" % path)
		fails += 1
	if not meta.is_empty():
		var lo := Vector3(meta.bbox_min[0], meta.bbox_min[1], meta.bbox_min[2])
		var hi := Vector3(meta.bbox_max[0], meta.bbox_max[1], meta.bbox_max[2])
		if not (aabb.position.distance_to(lo) < 0.02 and aabb.end.distance_to(hi) < 0.02):
			print("FAIL %s: AABB %s..%s differs from metadata %s..%s (axis/unit mismatch?)" % [path, _v(aabb.position), _v(aabb.end), _v(lo), _v(hi)])
			fails += 1
		if absi(tris - int(meta.tris)) > 0:
			print("WARN %s: tris %d vs metadata %d" % [path, tris, int(meta.tris)])
	root.free()
	return fails


func _v(v: Vector3) -> String:
	return "(%.2f,%.2f,%.2f)" % [v.x, v.y, v.z]
