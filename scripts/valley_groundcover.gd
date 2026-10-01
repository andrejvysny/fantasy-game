extends Node3D
## GPU grid-scattered groundcover: per layer one MultiMesh of identity instances, drawn as a
## grid of tiles that follow the camera (snapped to the layer spacing); groundcover.gdshader
## places each instance on a world cell from density fields, so placement is deterministic and
## costs no CPU per frame. Tiles (not one ring-sized instance) let frustum culling drop the
## half of the ring behind the camera.
## Replaces valley_grass.gd, which stays available for A/B with --grass=cards.
## --groundcover_debug=patch,plain,off,ab: 4x4 m patch at the spawn / asset colour only /
## disabled / with --perf, toggle every AB_PERIOD frames and print GPU time on vs off (in one
## process, so other GPU load hits both sides equally).

@export var terrain_path: NodePath
@export var camera_path: NodePath
@export var layers: Array[GroundcoverLayer] = []
@export var patch_centre := Vector2(-22, -145) # scene spawn point
@export var patch_size := 4.0
@export var plant_height := 1.2 # tallest asset plus sway, for the culling box

const SHADER := preload("res://materials/groundcover.gdshader")
const TILE_SIZE := 12.0 # metres, target tile edge
const BLOCK := 8 # metres per cell of the height min/max grid behind the tile boxes
const AB_PERIOD := 30
const AB_SETTLE := 3 # frames after a toggle that still hold the previous state's work

var _terrain: Node
var _camera: Camera3D
var _tiles: Array[MultiMeshInstance3D] = []
var _tile_spacing := PackedFloat32Array()
var _tile_offset := PackedVector2Array() # tile centre in cells from the camera's cell
var _tile_half := PackedFloat32Array()
var _tile_cell: Array[Vector2] = [] # last placed centre cell, to refit boxes only on change
var _layer_count := 0
var _block_lo := PackedFloat32Array()
var _block_hi := PackedFloat32Array()
var _blocks := 0
var _map_half := 0.0
var _ab := false
var _ab_frame := 0
var _ab_blocks: Array[PackedFloat32Array] = [] # GPU ms samples per AB_PERIOD block
var _ab_draws := [0, 0] # draw calls summed over off, on samples


func _ready() -> void:
	var debug := _debug_flags()
	var cards := _user_arg("--grass=") == "cards"
	if cards or debug.has("off"):
		print("groundcover: disabled (%s)" % ("--grass=cards" if cards else "--groundcover_debug=off"))
		queue_free()
		return
	# After the camera rig has moved this frame, so tiles never trail the view by a frame.
	process_priority = 100
	_terrain = get_node(terrain_path)
	_camera = get_node_or_null(camera_path) as Camera3D
	var terrain_mat: ShaderMaterial = _terrain.material
	var data_dir: String = _terrain.data_dir
	var fields := {
		"ground": ImageTexture.create_from_image(GroundcoverFields.load_field("ground", data_dir)),
		"flowers": ImageTexture.create_from_image(GroundcoverFields.load_field("flowers", data_dir)),
	}
	_build_blocks(load(data_dir + "height.res") as Image)
	for layer in layers:
		var mesh := _load_mesh(layer.mesh_path)
		if mesh == null:
			continue
		var mat := _material(layer, terrain_mat, fields, debug)
		_add_layer(layer, mesh, mat)
	print("groundcover: %d layers, %d tiles, %d instances" % [_layer_count, _tiles.size(), _instance_total()])
	_ab = debug.has("ab") and "--perf" in OS.get_cmdline_user_args()


func _process(_delta: float) -> void:
	var cam := _camera if _camera != null else get_viewport().get_camera_3d()
	if cam == null:
		return
	var p := cam.global_position
	for i in _tiles.size():
		var s := _tile_spacing[i]
		var c := Vector2(roundf(p.x / s), roundf(p.z / s)) + _tile_offset[i]
		if c != _tile_cell[i]:
			_tile_cell[i] = c
			_tiles[i].global_position = Vector3(c.x * s, 0.0, c.y * s)
			_fit_tile(i, c * s)
	if _ab:
		_ab_step()


func _ab_step() -> void:
	_ab_frame += 1
	var block := _ab_frame / AB_PERIOD
	var on := block % 2 == 0
	if _ab_frame % AB_PERIOD >= AB_SETTLE and _ab_frame > 120:
		while _ab_blocks.size() <= block:
			_ab_blocks.append(PackedFloat32Array())
		_ab_blocks[block].append(RenderingServer.viewport_get_measured_render_time_gpu(get_viewport().get_viewport_rid()))
		_ab_draws[int(on)] += RenderingServer.get_rendering_info(RenderingServer.RENDERING_INFO_TOTAL_DRAW_CALLS_IN_FRAME)
	for tile in _tiles:
		tile.visible = on


# Cost = median over (on block - following off block) of block medians: slow drift and other
# processes' GPU load change both halves of a pair alike.
func _exit_tree() -> void:
	if not _ab:
		return
	var diffs := PackedFloat32Array()
	var on_med := PackedFloat32Array()
	var off_med := PackedFloat32Array()
	for b in range(0, _ab_blocks.size() - 1, 2):
		if _ab_blocks[b].is_empty() or _ab_blocks[b + 1].is_empty():
			continue
		on_med.append(_median(_ab_blocks[b]))
		off_med.append(_median(_ab_blocks[b + 1]))
		diffs.append(on_med[-1] - off_med[-1])
	if diffs.is_empty():
		return
	var frames := maxf(1.0, diffs.size() * (AB_PERIOD - AB_SETTLE))
	print("GROUNDCOVER_AB pairs=%d cost_ms_med=%.2f min=%.2f max=%.2f on_ms=%.2f off_ms=%.2f draws_on=%d draws_off=%d" % [
		diffs.size(), _median(diffs), _sorted(diffs)[0], _sorted(diffs)[-1], _median(on_med), _median(off_med),
		_ab_draws[1] / frames, _ab_draws[0] / frames])


func _sorted(v: PackedFloat32Array) -> PackedFloat32Array:
	var t := v.duplicate()
	t.sort()
	return t


func _median(v: PackedFloat32Array) -> float:
	return _sorted(v)[v.size() / 2]


func _user_arg(prefix: String) -> String:
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with(prefix):
			return arg.trim_prefix(prefix)
	return ""


func _debug_flags() -> PackedStringArray:
	var value := _user_arg("--groundcover_debug=")
	return value.split(",", false) if value != "" else PackedStringArray()


func _load_mesh(path: String) -> Mesh:
	if path == "" or not ResourceLoader.exists(path):
		push_warning("groundcover: mesh %s missing, layer skipped" % path)
		return null
	var res := load(path)
	if res is Mesh:
		return res
	if res is PackedScene:
		var root := (res as PackedScene).instantiate()
		var found := root.find_children("*", "MeshInstance3D", true, false)
		var mesh: Mesh = (found[0] as MeshInstance3D).mesh if not found.is_empty() else null
		if root is MeshInstance3D:
			mesh = (root as MeshInstance3D).mesh
		root.free()
		if mesh != null:
			return mesh
	push_warning("groundcover: %s has no mesh, layer skipped" % path)
	return null


# Height min/max per BLOCK x BLOCK metres, so each tile's culling box spans only the
# terrain under it (a box spanning the whole valley's height range is almost never culled).
func _build_blocks(img: Image) -> void:
	var res := img.get_width()
	var h := img.get_data().to_float32_array()
	_map_half = (res - 1) * 0.5
	_blocks = ceili(float(res) / BLOCK)
	_block_lo.resize(_blocks * _blocks)
	_block_hi.resize(_blocks * _blocks)
	_block_lo.fill(INF)
	_block_hi.fill(-INF)
	for z in res:
		var row := (z / BLOCK) * _blocks
		for x in res:
			var v := h[z * res + x]
			var b := row + x / BLOCK
			_block_lo[b] = minf(_block_lo[b], v)
			_block_hi[b] = maxf(_block_hi[b], v)


func _fit_tile(i: int, centre: Vector2) -> void:
	var half := _tile_half[i]
	var lo := INF
	var hi := -INF
	var b0 := ((centre - Vector2.ONE * half + Vector2.ONE * _map_half) / BLOCK).floor()
	var b1 := ((centre + Vector2.ONE * half + Vector2.ONE * _map_half) / BLOCK).floor()
	for bz in range(clampi(int(b0.y), 0, _blocks - 1), clampi(int(b1.y), 0, _blocks - 1) + 1):
		for bx in range(clampi(int(b0.x), 0, _blocks - 1), clampi(int(b1.x), 0, _blocks - 1) + 1):
			lo = minf(lo, _block_lo[bz * _blocks + bx])
			hi = maxf(hi, _block_hi[bz * _blocks + bx])
	_tiles[i].custom_aabb = AABB(Vector3(-half, lo - 1.0, -half), Vector3(2.0 * half, hi - lo + plant_height + 1.0, 2.0 * half))


# Ring hand-off: an inner ring (inner_radius 0) and an outer ring of the same mesh whose
# inner_radius lies inside the inner ring's radius share the overlap as one band.
func _bands(layer: GroundcoverLayer) -> Array[Vector2]:
	var band_in := Vector2.ZERO
	var band_out := Vector2.ZERO
	for other in layers:
		if other == layer or other.mesh_path != layer.mesh_path:
			continue
		if layer.inner_radius > 0.0 and other.inner_radius < layer.inner_radius and other.radius > layer.inner_radius:
			band_in = Vector2(layer.inner_radius, other.radius)
		elif other.inner_radius > layer.inner_radius and other.inner_radius < layer.radius:
			band_out = Vector2(other.inner_radius, layer.radius)
	if layer.inner_radius > 0.0 and band_in == Vector2.ZERO:
		band_in = Vector2(layer.inner_radius, layer.inner_radius + 4.0)
	return [band_in, band_out]


func _material(layer: GroundcoverLayer, terrain_mat: ShaderMaterial, fields: Dictionary, debug: PackedStringArray) -> ShaderMaterial:
	var m := ShaderMaterial.new()
	m.shader = SHADER
	for key in ["heightmap", "splat_0", "splat_2", "map_size"]:
		m.set_shader_parameter(key, terrain_mat.get_shader_parameter(key))
	m.set_shader_parameter("ground_field", fields["ground"])
	m.set_shader_parameter("layer_field", fields[layer.field])
	m.set_shader_parameter("field_is_ground", layer.field == "ground")
	var mask := Vector4.ZERO
	mask[clampi(layer.channel, 0, 3)] = 1.0
	m.set_shader_parameter("channel_mask", mask)
	var bands := _bands(layer)
	m.set_shader_parameter("band_in", bands[0])
	m.set_shader_parameter("band_out", bands[1])
	m.set_shader_parameter("grid_n", _tile_cells(layer))
	for key in ["spacing", "radius", "density", "scale_min", "scale_max", "max_slope", "palette_strength", "seed", "thin_start", "far_keep"]:
		m.set_shader_parameter(key, layer.get(key))
	m.set_shader_parameter("wind_amplitude", layer.wind) # shader `wind` is the global field
	# Terrain's wrap (shader default) so clumps band with the ground; no brush speckle on blades.
	m.set_shader_parameter("brush_strength", 0.0)
	m.set_shader_parameter("plain", debug.has("plain"))
	if debug.has("patch"):
		var h := patch_size * 0.5
		m.set_shader_parameter("patch_only", true)
		m.set_shader_parameter("patch_rect", Vector4(patch_centre.x - h, patch_centre.y - h, patch_centre.x + h, patch_centre.y + h))
	return m


# Cells per tile edge, even so tile centres land on whole cells.
func _tile_cells(layer: GroundcoverLayer) -> int:
	return maxi(2, 2 * ceili(TILE_SIZE / layer.spacing * 0.5))


# All tiles of a layer share one MultiMesh; tiles wholly outside the ring are never made.
func _add_layer(layer: GroundcoverLayer, mesh: Mesh, mat: ShaderMaterial) -> void:
	var m := _tile_cells(layer)
	var edge := m * layer.spacing
	var count := ceili(2.0 * layer.radius / edge)
	var half := edge * 0.5 + layer.spacing + 0.5 # jitter, snap lag and sway
	var mm := MultiMesh.new()
	mm.transform_format = MultiMesh.TRANSFORM_3D
	mm.mesh = mesh
	mm.instance_count = m * m
	mm.buffer = _identity_buffer(m * m)
	for tz in count:
		for tx in count:
			var off := Vector2(tx, tz) * m + Vector2.ONE * (m / 2 - count * m / 2)
			var d := off * layer.spacing
			var near := (d.abs() - Vector2.ONE * half).max(Vector2.ZERO).length()
			var far := (d.abs() + Vector2.ONE * half).length()
			if near > layer.radius or far < layer.inner_radius:
				continue
			var tile := MultiMeshInstance3D.new()
			tile.name = "L%d_%s_%d_%d" % [_layer_count, layer.mesh_path.get_file().get_basename(), tx, tz]
			tile.multimesh = mm
			tile.material_override = mat
			tile.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
			add_child(tile)
			tile.top_level = true
			_tiles.append(tile)
			_tile_spacing.append(layer.spacing)
			_tile_offset.append(off)
			_tile_half.append(half)
			_tile_cell.append(Vector2(INF, INF))
	_layer_count += 1


func _identity_buffer(count: int) -> PackedFloat32Array:
	var one := PackedFloat32Array([1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0])
	var buf := PackedFloat32Array()
	buf.resize(count * 12)
	for i in count:
		for j in 12:
			buf[i * 12 + j] = one[j]
	return buf


func _instance_total() -> int:
	var total := 0
	for tile in _tiles:
		total += tile.multimesh.instance_count
	return total
