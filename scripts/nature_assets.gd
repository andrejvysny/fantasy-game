class_name NatureAssets extends RefCounted
## Loads assets/nature GLBs per the asset contract (assets/nature/README.md): one mesh, surfaces
## named M_solid / M_foliage, metadata JSON beside the GLB. Materials are chosen by surface
## identity and asset group, never by colour. Cached per asset id.

const ROOT := "res://assets/nature/"
const ROCK := preload("res://materials/nature/nature_rock.tres")
const WOOD := preload("res://materials/nature/nature_wood.tres")
const FOLIAGE := preload("res://materials/nature/nature_foliage.tres")

static var _index := {} # asset_id -> group
static var _meshes := {} # asset_id -> Mesh with materials assigned
static var _meta := {} # asset_id -> Dictionary


static func _scan() -> void:
	if not _index.is_empty():
		return
	for group in DirAccess.get_directories_at(ROOT):
		for f in DirAccess.get_files_at(ROOT + group):
			if f.get_extension() == "glb":
				_index[f.get_basename()] = group


static func has(asset_id: String) -> bool:
	_scan()
	return _index.has(asset_id)


static func ids() -> PackedStringArray:
	_scan()
	var out := PackedStringArray(_index.keys())
	out.sort()
	return out


static func meta(asset_id: String) -> Dictionary:
	_scan()
	if not _meta.has(asset_id):
		var path: String = ROOT + _index[asset_id] + "/" + asset_id + ".json"
		var parsed: Variant = JSON.parse_string(FileAccess.get_file_as_string(path)) if FileAccess.file_exists(path) else null
		if not parsed is Dictionary:
			return {} # missing or half-written by an exporter; not cached so a later call retries
		_meta[asset_id] = parsed
	return _meta[asset_id]


## Mesh with contract materials on every surface (shared, do not modify). Null if not importable.
static func mesh(asset_id: String) -> Mesh:
	_scan()
	if _meshes.has(asset_id):
		return _meshes[asset_id]
	var group: String = _index[asset_id]
	# A GLB written after the last import is not loadable yet: skip it rather than feed null meshes on.
	var path: String = ROOT + group + "/" + asset_id + ".glb"
	var scene := load(path) as PackedScene if ResourceLoader.exists(path) else null
	if scene == null:
		push_warning("nature asset %s not imported yet (run godot --headless --import)" % asset_id)
		return null
	var root := scene.instantiate()
	var found := _find_mesh(root)
	var src: Mesh = found.mesh if found else null
	root.free()
	if src == null:
		return null
	var m := src.duplicate() as Mesh
	for s in m.get_surface_count():
		var name := src.surface_get_material(s).resource_name if src.surface_get_material(s) else ""
		m.surface_set_material(s, material_for(group, name))
	_meshes[asset_id] = m
	return m


static func material_for(group: String, surface_name: String) -> Material:
	if surface_name == "M_foliage":
		return FOLIAGE
	return ROCK if group == "rocks" else WOOD


static func _find_mesh(n: Node) -> MeshInstance3D:
	if n is MeshInstance3D:
		return n
	for c in n.get_children():
		var m := _find_mesh(c)
		if m:
			return m
	return null
