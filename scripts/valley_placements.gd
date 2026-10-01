class_name ValleyPlacements extends RefCounted
## Offline scatter output (world/generated, tools/environment/README.md) merged across zones,
## with hand-authored overrides (world/overrides) applied on top at runtime. Generated files are
## never written back. Parsed once per run and shared by Forest and Props.

const MANIFEST := "res://world/generated/manifest.json"
const OVERRIDES := "res://world/overrides/valley_overrides.json"
const MAGIC := "VPL1"
const RECORD_FLOATS := 8 # f32 x, y, z, yaw, scale, tilt_x, tilt_z + u32 id
const ADD_ID_BASE := 0xF0000000

static var _cache := {}


## {"revision": String, "instances": int, "assets": {asset_id: Array of [id: int, Transform3D]},
## "removed": int, "moved": int, "added": int}. Empty "assets" when the manifest is missing.
static func load(terrain: Node) -> Dictionary:
	if not _cache.is_empty():
		return _cache
	var manifest: Variant = JSON.parse_string(FileAccess.get_file_as_string(MANIFEST))
	if not manifest is Dictionary:
		push_warning("valley placements: no manifest at %s" % MANIFEST)
		return {"revision": "", "instances": 0, "assets": {}, "removed": 0, "moved": 0, "added": 0}
	# id -> [asset_id, Transform3D]; insertion order = manifest zone order, then file (id) order.
	var by_id := {}
	for zone: String in manifest["zones"]:
		var per: Dictionary = manifest["zones"][zone]
		for asset_id: String in per:
			_read_file("res://" + str(per[asset_id]["file"]), asset_id, by_id)
	var counts := _apply_overrides(by_id, terrain)
	var assets := {}
	for id: int in by_id:
		var rec: Array = by_id[id]
		if not assets.has(rec[0]):
			assets[rec[0]] = []
		assets[rec[0]].append([id, rec[1]])
	_cache = {"revision": str(manifest.get("revision", "")), "instances": by_id.size(), "assets": assets,
		"removed": counts.x, "moved": counts.y, "added": counts.z}
	print("valley placements: %s %d instances, %d assets, overrides %d/%d/%d" % [
		_cache["revision"], by_id.size(), assets.size(), counts.x, counts.y, counts.z])
	return _cache


## Runtime basis: Rx(tilt_x) * Rz(tilt_z) * Ry(yaw) * scale (tools/environment/binfmt.py).
static func make_transform(x: float, y: float, z: float, yaw: float, s: float,
		tilt_x := 0.0, tilt_z := 0.0) -> Transform3D:
	var basis := Basis(Vector3.RIGHT, tilt_x) * Basis(Vector3.BACK, tilt_z) * Basis(Vector3.UP, yaw)
	return Transform3D(basis.scaled(Vector3.ONE * s), Vector3(x, y, z))


static func _read_file(path: String, asset_id: String, by_id: Dictionary) -> void:
	var bytes := FileAccess.get_file_as_bytes(path)
	if bytes.size() < 8 or bytes.slice(0, 4).get_string_from_ascii() != MAGIC:
		push_warning("valley placements: %s is not a VPL1 file" % path)
		return
	var n := bytes.decode_u32(4)
	if bytes.size() != 8 + n * RECORD_FLOATS * 4:
		push_warning("valley placements: %s size mismatch for %d records" % [path, n])
		return
	var block := bytes.slice(8)
	var f := block.to_float32_array()
	var ids := block.to_int32_array()
	for i in n:
		var o := i * RECORD_FLOATS
		var xf := make_transform(f[o], f[o + 1], f[o + 2], f[o + 3], f[o + 4], f[o + 5], f[o + 6])
		by_id[ids[o + 7] & 0xFFFFFFFF] = [asset_id, xf]


# Returns (removed, moved, added). Missing file -> created empty (generator does the same).
static func _apply_overrides(by_id: Dictionary, terrain: Node) -> Vector3i:
	if not FileAccess.file_exists(OVERRIDES):
		var fw := FileAccess.open(OVERRIDES, FileAccess.WRITE)
		if fw:
			fw.store_string(JSON.stringify({"remove": [], "move": {}, "add": []}, " ") + "\n")
		return Vector3i.ZERO
	var ov: Variant = JSON.parse_string(FileAccess.get_file_as_string(OVERRIDES))
	if not ov is Dictionary:
		push_warning("valley placements: cannot parse %s" % OVERRIDES)
		return Vector3i.ZERO
	var out := Vector3i.ZERO
	for id_v: Variant in ov.get("remove", []):
		var id := int(id_v)
		if by_id.erase(id):
			out.x += 1
		else:
			push_warning("valley placements: override remove id %d not found" % id)
	var moves: Dictionary = ov.get("move", {})
	for key: String in moves:
		var id := int(key)
		if not by_id.has(id):
			push_warning("valley placements: override move id %d not found" % id)
			continue
		var m: Array = moves[key]
		var y: float = terrain.get_height(m[0], m[2]) if m[1] == null else float(m[1])
		by_id[id][1] = make_transform(m[0], y, m[2], m[3], m[4])
		out.y += 1
	var adds: Array = ov.get("add", [])
	for i in adds.size():
		var a: Dictionary = adds[i]
		var x := float(a["x"])
		var z := float(a["z"])
		var y: float = float(a["y"]) if a.get("y") != null else terrain.get_height(x, z)
		if by_id.has(ADD_ID_BASE + i):
			push_warning("valley placements: override add id %d replaces a generated instance" % (ADD_ID_BASE + i))
		by_id[ADD_ID_BASE + i] = [str(a["asset"]), make_transform(x, y, z, a.get("yaw", 0.0), a.get("scale", 1.0))]
		out.z += 1
	return out
