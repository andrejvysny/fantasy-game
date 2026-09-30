extends Node3D
## Local ground-mist pockets: ellipsoid FogVolumes in terrain hollows, sharing one
## FogMaterial whose density the atmosphere presets drive (ground_fog_density).

@export var terrain_path: NodePath
@export var material: FogMaterial
@export var world_seed := 99
@export var count := 14
@export var area := 90.0 # half-extent of the placement square, metres
@export var min_spacing := 16.0
@export var clear_radius := 10.0 # keep the camp readable
@export var center := Vector2.ZERO # placement square centre (x, z)
@export var min_height := -INF # skip lower ground, e.g. sea floor
@export var size_min := Vector3(12.0, 2.5, 12.0)
@export var size_max := Vector3(26.0, 4.0, 22.0)

const CANDIDATES := 500


func _ready() -> void:
	var terrain := get_node(terrain_path)
	var rng := RandomNumberGenerator.new()
	rng.seed = world_seed
	var candidates: Array[Vector3] = []
	for i in CANDIDATES:
		var p := center + Vector2(rng.randf_range(-area, area), rng.randf_range(-area, area))
		var h: float = terrain.get_height(p.x, p.y)
		if h >= min_height:
			candidates.append(Vector3(p.x, h, p.y))
	# Lowest ground first: mist pools in hollows.
	candidates.sort_custom(func(a: Vector3, b: Vector3) -> bool: return a.y < b.y)
	var placed: Array[Vector3] = []
	for c in candidates:
		if placed.size() >= count:
			break
		if placed.any(func(q: Vector3) -> bool: return Vector2(q.x, q.z).distance_to(Vector2(c.x, c.z)) < min_spacing):
			continue
		var size := Vector3(
			rng.randf_range(size_min.x, size_max.x),
			rng.randf_range(size_min.y, size_max.y),
			rng.randf_range(size_min.z, size_max.z))
		# The ellipsoid's horizontal reach, not its centre, must stay outside the clear radius.
		if Vector2(c.x, c.z).distance_to(center) < clear_radius + 0.5 * maxf(size.x, size.z):
			continue
		placed.append(c)
		_add_pocket(c, size, rng)


func _add_pocket(pos: Vector3, size: Vector3, rng: RandomNumberGenerator) -> void:
	var v := FogVolume.new()
	v.shape = RenderingServer.FOG_VOLUME_SHAPE_ELLIPSOID
	v.size = size
	v.material = material
	v.position = pos
	v.rotation.y = rng.randf() * TAU
	add_child(v)
