extends Node3D
## Card grass from res://grass on the valley's grass and dry-grass layers, with sparse tufts
## on forest floor and scree. Patches follow the terrain normal (their ground card is flat).
## One MultiMesh per chunk per patch size; no shadows (README: vertical cards crease the ground).

@export var terrain_path: NodePath
@export var world_seed := 777
@export var cell := 2.2 # jittered grid spacing; patches overlap ~30 %
@export var grass_density := 1.0
@export var forest_density := 0.12
@export var scree_density := 0.08
@export var max_slope := 0.55 # rise over run
@export var min_height := 0.6
@export var chunk := 32.0
@export var view_range := 70.0
@export var wind_strength := 0.05

const SHADER := preload("res://materials/grass_card.gdshader")
# tuft, M, L; the two sprites are identical copies in every GLB, so one pair is shared.
const SCENES := ["res://grass/glb/grass_tuft.glb", "res://grass/glb/grass_patch_M.glb", "res://grass/glb/grass_patch_L.glb"]
const SIDE_TEX := preload("res://grass/glb/grass_patch_L_grass_side.png")
const TOP_TEX := preload("res://grass/glb/grass_patch_L_grass_top.png")
const TUFT := 0
const PATCH_M := 1
const PATCH_L := 2
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
var patch_count := 0


func _ready() -> void:
	_terrain = get_node(terrain_path)
	_rng.seed = world_seed
	_load_meshes()
	var buckets := {} # chunk key -> {mesh index -> [[Transform3D, Color], ...]}
	for item: Array in _place():
		var o: Vector3 = (item[1] as Transform3D).origin
		var key := Vector2i(floori(o.x / chunk), floori(o.z / chunk))
		if not buckets.has(key):
			buckets[key] = {}
		var per: Dictionary = buckets[key]
		if not per.has(item[0]):
			per[item[0]] = []
		per[item[0]].append([item[1], item[2]])
	for key: Vector2i in buckets:
		_build_chunk(key, buckets[key])
	print("valley grass: %d patches in %d chunks" % [patch_count, buckets.size()])


func _card_material(tex: Texture2D, wind: float) -> ShaderMaterial:
	var m := ShaderMaterial.new()
	m.shader = SHADER
	m.set_shader_parameter("albedo_tex", tex)
	m.set_shader_parameter("wind_strength", wind)
	m.set_shader_parameter("wrap", 0.6)
	m.set_shader_parameter("brush_strength", 0.0)
	return m


func _load_meshes() -> void:
	var side := _card_material(SIDE_TEX, wind_strength)
	var top := _card_material(TOP_TEX, 0.0)
	for path: String in SCENES:
		var root := (load(path) as PackedScene).instantiate()
		var src := (root.get_child(0) as MeshInstance3D).mesh
		var mesh := src.duplicate() as Mesh
		# Surface 0 = vertical blade cards, surface 1 = flat ground card (see grass/README.md).
		mesh.surface_set_material(0, side)
		mesh.surface_set_material(1, top)
		_meshes.append(mesh)
		root.free()


func _normal(x: float, z: float) -> Vector3:
	var hl: float = _terrain.get_height(x - 1.0, z)
	var hr: float = _terrain.get_height(x + 1.0, z)
	var hd: float = _terrain.get_height(x, z - 1.0)
	var hu: float = _terrain.get_height(x, z + 1.0)
	return Vector3(hl - hr, 2.0, hd - hu).normalized()


func _probability(l: PackedFloat32Array) -> float:
	if l[WATER_DEEP] + l[WATER_SHALLOW] > 0.02 or l[ROCK] > 0.25 or l[SAND] > 0.3 or l[DIRT] > 0.4:
		return 0.0
	return grass_density * (l[GRASS] + l[GRASS_DRY]) + forest_density * l[FOREST] + scree_density * l[SCREE]


# Returns [mesh index, Transform3D, instance Color(dry share, brightness, hue jitter)] entries.
func _place() -> Array:
	var out := []
	var half: float = _terrain.get_size() * 0.5 - 2.0
	var cells := int(2.0 * half / cell)
	var jitter := cell * 0.45
	for cz in cells:
		for cx in cells:
			var p := Vector2(-half + (cx + 0.5) * cell, -half + (cz + 0.5) * cell)
			p += Vector2(_rng.randf_range(-jitter, jitter), _rng.randf_range(-jitter, jitter))
			var l: PackedFloat32Array = _terrain.get_layers(p.x, p.y)
			if _rng.randf() >= _probability(l):
				continue
			var n := _normal(p.x, p.y)
			var h: float = _terrain.get_height(p.x, p.y)
			if n.y < 1.0 / sqrt(1.0 + max_slope * max_slope) or h < min_height:
				continue
			var grass := l[GRASS] + l[GRASS_DRY]
			var kind := TUFT
			if grass > 0.75 and _rng.randf() < 0.6:
				kind = PATCH_L
			elif grass > 0.4:
				kind = PATCH_M
			var tilt := Basis(Quaternion(Vector3.UP, n))
			var basis := tilt * Basis(Vector3.UP, _rng.randf_range(0.0, TAU)).scaled(Vector3.ONE * _rng.randf_range(0.9, 1.15))
			var dry := l[GRASS_DRY] / maxf(grass, 0.001) if grass > 0.05 else 0.0
			# Tufts under the canopy sit in shade on dark forest floor; full brightness reads as pale discs.
			var shade := lerpf(1.0, 0.72, clampf(l[FOREST] * 1.5, 0.0, 1.0)) * _rng.randf_range(0.9, 1.08)
			out.append([kind, Transform3D(basis, Vector3(p.x, h - 0.02, p.y)), Color(dry, shade, _rng.randf())])
	return out


func _build_chunk(key: Vector2i, per_kind: Dictionary) -> void:
	for kind: int in per_kind:
		var items: Array = per_kind[kind]
		var mm := MultiMesh.new()
		mm.transform_format = MultiMesh.TRANSFORM_3D
		mm.use_colors = true
		mm.mesh = _meshes[kind]
		mm.instance_count = items.size()
		for j in items.size():
			mm.set_instance_transform(j, items[j][0])
			mm.set_instance_color(j, items[j][1])
		var inst := MultiMeshInstance3D.new()
		inst.name = "Grass_%d_%d_k%d" % [key.x, key.y, kind]
		inst.multimesh = mm
		inst.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
		inst.visibility_range_end = view_range
		inst.visibility_range_end_margin = 10.0
		inst.visibility_range_fade_mode = GeometryInstance3D.VISIBILITY_RANGE_FADE_SELF
		add_child(inst)
		patch_count += items.size()
