extends Node3D
## Lodge and tree stumps around the campfire: grounded on the terrain, with colliders, and
## registered in "grass_clear"/"prop_clear" so grass, trees, bushes and rocks keep off them.

@export var terrain_path: NodePath = ^"../Terrain"
@export var lodge_scene: PackedScene
@export var stump_scene: PackedScene
@export var lodge_position := Vector2(-4.0, -11.0)
@export var lodge_yaw_deg := 0.0
@export var lodge_scale := 7.0
@export var stump_count := 6
@export var stump_ring := Vector2(5.5, 8.0) # min/max distance from the lodge centre
@export var stump_scale := Vector2(0.55, 0.8)
@export var world_seed := 77

const LODGE_AABB := AABB(Vector3(-0.50, -0.41, -0.49), Vector3(1.00, 0.82, 0.98))
const STUMP_AABB := AABB(Vector3(-0.49, -0.27, -0.46), Vector3(0.96, 0.53, 0.89))
const MAX_TRIES := 20

var _terrain: Node
var _half := Vector2.ZERO # lodge footprint half-extents (x, z), metres
var _yaw := 0.0


func _ready() -> void:
	_terrain = get_node(terrain_path)
	_yaw = deg_to_rad(lodge_yaw_deg)
	_half = Vector2(LODGE_AABB.size.x, LODGE_AABB.size.z) * 0.5 * lodge_scale
	_build_lodge()
	_build_stumps()


func _build_lodge() -> void:
	var lodge := lodge_scene.instantiate() as Node3D
	var c := lodge_position
	var low: float = _terrain.get_height(c.x, c.y)
	for corner: Vector2 in [Vector2(1, 1), Vector2(1, -1), Vector2(-1, 1), Vector2(-1, -1)]:
		var q := c + (corner * _half).rotated(-_yaw)
		low = minf(low, _terrain.get_height(q.x, q.y))
	# Lowest footprint sample minus a small sink, so no corner floats; bottom of the mesh at y.
	var y := low - 0.05 - LODGE_AABB.position.y * lodge_scale
	lodge.transform = Transform3D(Basis(Vector3.UP, _yaw).scaled(Vector3.ONE * lodge_scale), Vector3(c.x, y, c.y))
	PropMaterials.make_dielectric(lodge)
	var shape := BoxShape3D.new()
	shape.size = Vector3(LODGE_AABB.size.x * 0.9, LODGE_AABB.size.y, LODGE_AABB.size.z * 0.9) * lodge_scale
	_add_body(lodge, shape, LODGE_AABB.get_center() * lodge_scale)
	var r := _half.length()
	_register(lodge, 5.5, r + 0.5, r + 3.0)
	add_child(lodge)


func _build_stumps() -> void:
	var rng := RandomNumberGenerator.new()
	rng.seed = world_seed
	var campfire := get_node_or_null("../Campfire") as Node3D
	var r := _half.length()
	for i in stump_count:
		var base := TAU * i / stump_count
		for attempt in MAX_TRIES:
			var a := base + rng.randf_range(-0.4, 0.4) if attempt == 0 else rng.randf() * TAU
			var p := lodge_position + Vector2.from_angle(a) * rng.randf_range(stump_ring.x, stump_ring.y)
			if _in_footprint(p, 1.0):
				continue
			if campfire != null and p.distance_to(Vector2(campfire.global_position.x, campfire.global_position.z)) < 2.5:
				continue
			_add_stump(p, rng)
			break


# Inside the rotated lodge rectangle grown by margin metres.
func _in_footprint(p: Vector2, margin: float) -> bool:
	var local := (p - lodge_position).rotated(_yaw)
	return absf(local.x) < _half.x + margin and absf(local.y) < _half.y + margin


func _add_stump(p: Vector2, rng: RandomNumberGenerator) -> void:
	var s := rng.randf_range(stump_scale.x, stump_scale.y)
	var stump := stump_scene.instantiate() as Node3D
	var y: float = _terrain.get_height(p.x, p.y) - 0.03 - STUMP_AABB.position.y * s
	stump.transform = Transform3D(Basis(Vector3.UP, rng.randf() * TAU).scaled(Vector3.ONE * s), Vector3(p.x, y, p.y))
	PropMaterials.make_dielectric(stump)
	var shape := CylinderShape3D.new()
	shape.radius = 0.45 * s
	shape.height = STUMP_AABB.size.y * s
	_add_body(stump, shape, STUMP_AABB.get_center() * s)
	_register(stump, 1.2, 0.7, 1.5)
	add_child(stump)


# Unscaled body beside the prop (shape sizes are already in metres); offset is in yaw-local metres.
func _add_body(prop: Node3D, shape: Shape3D, offset: Vector3) -> void:
	var body := StaticBody3D.new()
	body.transform = Transform3D(Basis(Vector3.UP, prop.rotation.y), prop.position)
	var cs := CollisionShape3D.new()
	cs.shape = shape
	cs.position = offset
	body.add_child(cs)
	add_child(body)


func _register(n: Node3D, wear: float, grass: float, clear: float) -> void:
	n.add_to_group("grass_clear")
	n.add_to_group("prop_clear")
	n.set_meta("wear_radius", wear)
	n.set_meta("grass_clear_radius", grass)
	n.set_meta("clear_radius", clear)
