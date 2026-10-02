extends Node3D
## FG-02 integration test scene. Row A (z = -ROW_Z): AssetStudio wrappers inside game-owned
## integration_asset parents. Row B (z = +ROW_Z): the in-repo originals rendered the game's way.
## Lit like showroom.gd. Not the main scene.
##   godot --path . res://scenes/integration/asset_roundtrip_test.tscn

const IntegrationAsset := preload("res://scripts/integration/integration_asset.gd")
const ROW_Z := 11.0
const GAP := 3.0
const PREFABS := "res://assets/prefabs/"
## binding, kind (nature|spruce|prop|plain), original id/path, scale, slot width
const ENTRIES := [
	["fg_pine_open_a", "nature", "pine_open_A", 1.0, 8.5],
	["fg_spruce_mature_a", "nature", "spruce_mature_A", 1.0, 7.0],
	["fg_boulder_large_a", "nature", "boulder_large_A", 1.0, 3.0],
	["fg_spruce_legacy_l_long_s27", "spruce", "res://spruce_trees/models/spruce_L_normal_long_s27.glb", 1.0, 4.4],
	["fg_campfire", "prop", "res://campfire.glb", 1.3, 1.8],
	["fg_wooden_lodge", "prop", "res://wooden_lodge.glb", 7.0, 7.5],
	["fg_grass_tuft", "plain", "res://grass/glb/grass_tuft.glb", 1.0, 2.2],
]

@export var style: WorldStyle = preload("res://materials/world_style.tres")


func _ready() -> void:
	style.apply()
	RenderingServer.global_shader_parameter_set("shadow_tint", Color(0.3, 0.42, 0.58, 0.3))
	var row_a := Node3D.new()
	row_a.name = "RowA"
	add_child(row_a)
	var row_b := Node3D.new()
	row_b.name = "RowB"
	add_child(row_b)
	var x := 0.0
	for e: Array in ENTRIES:
		var w: float = e[4]
		x += w * 0.5
		_add_wrapper(row_a, e, Vector3(x, 0.0, -ROW_Z))
		_add_original(row_b, e, Vector3(x, 0.0, ROW_Z))
		x += w * 0.5 + GAP
	_frame(x - GAP)


func _add_wrapper(row: Node3D, e: Array, at: Vector3) -> void:
	var parent := Node3D.new()
	parent.set_script(IntegrationAsset)
	parent.name = e[0]
	parent.position = at
	parent.scale = Vector3.ONE * float(e[3])
	var wrapper := (load(PREFABS + str(e[0]) + ".tscn") as PackedScene).instantiate()
	parent.add_child(wrapper)
	row.add_child(parent)


func _add_original(row: Node3D, e: Array, at: Vector3) -> void:
	var node: Node3D
	match e[1]:
		"nature":
			var mi := MeshInstance3D.new()
			mi.mesh = NatureAssets.mesh(e[2])
			node = mi
		"spruce":
			node = (load(e[2]) as PackedScene).instantiate()
			# Same params as valley_forest.gd _tree_material(); the valley drives the fade per MultiMesh instance.
			(node.get_node("Tree") as MeshInstance3D).material_override = _valley_spruce_material()
			node.get_node("TrunkCollision").queue_free()
		"prop":
			node = (load(e[2]) as PackedScene).instantiate()
			PropMaterials.make_dielectric(node)
		_:
			node = (load(e[2]) as PackedScene).instantiate()
	node.name = "orig_" + str(e[0])
	node.position = at
	node.scale = Vector3.ONE * float(e[3])
	row.add_child(node)


func _valley_spruce_material() -> ShaderMaterial:
	var m := ShaderMaterial.new()
	m.shader = preload("res://materials/world_double_sided_mm.gdshader")
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


func _frame(width: float) -> void:
	var cam := $Camera as Camera3D
	var center := Vector3(width * 0.5, 2.5, 0.0)
	var pitch := deg_to_rad(32.0)
	var dist := width * 1.2
	cam.position = center + Vector3(0.0, sin(pitch), cos(pitch)) * dist
	cam.look_at(center)
