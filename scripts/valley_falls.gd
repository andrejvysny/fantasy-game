extends Node3D
## Splash mist at the foot of each waterfall, plus a little spray at its lip. Fall lines come
## from res://terrains/valley/falls.json (tools/terrain/export_falls.py); the face itself is
## found in the water levels (water.res) near each line, because the level solver may put the
## step off the drawn line or merge it away. The streaked sheet is water.gdshader.

const SEARCH_RADIUS := 24.0 # metres around a fall line searched for its steep water
const FACE_SLOPE := 0.5 # level slope (m/m) that counts as fall face
const MIN_COVER := 0.3
const HIDDEN_DEPTH := -0.5 # face samples deeper than this inside the terrain are not visible
const FOOT_SHARE := 0.3 # lowest share of the visible face height that is its foot
const LIP_SHARE := 0.15

@export var terrain_path: NodePath
@export var falls_path := "res://terrains/valley/falls.json"
@export var water_path := "res://terrains/valley/water.res"
@export var min_drop := 5.0 # metres; smaller steps are rapids without a splash
@export var mist_amount := 32
@export var spray_amount := 12
@export var visibility_end := 220.0

var _terrain: Node
var _levels: PackedFloat32Array # level, coverage interleaved
var _res := 0
var _half := 0.0
var _disc: GradientTexture2D


func _ready() -> void:
	_terrain = get_node(terrain_path)
	var img: Image = load(water_path)
	_res = img.get_width()
	_half = (_res - 1) * 0.5
	_levels = img.get_data().to_float32_array()
	_disc = _soft_disc()
	var data: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(falls_path))
	for fall: Dictionary in data["falls"]:
		var pts: Array = fall["pts"]
		var face := _find_face(Vector2(pts[0][0], pts[0][1]), Vector2(pts[-1][0], pts[-1][1]))
		if face.is_empty() or face.drop < min_drop:
			continue
		add_child(_mist(fall["name"], face))
		add_child(_spray(fall["name"], face))
		print("falls: %s drop %.1f m, foot %s" % [fall["name"], face.drop, face.foot])
	# A/B and perf runs: --falls=0 hides the splash particles.
	if "--falls=0" in OS.get_cmdline_user_args():
		visible = false


func _sample(i: int, j: int) -> Vector2:
	var k := (clampi(j, 0, _res - 1) * _res + clampi(i, 0, _res - 1)) * 2
	return Vector2(_levels[k], _levels[k + 1])


# Steep covered water within SEARCH_RADIUS of segment a-b, as world points (y = level) with
# their downhill gradient; empty when the line has no fall face.
func _face_samples(a: Vector2, b: Vector2) -> Array[Array]:
	var pts: Array[Array] = []
	var lo := (a.min(b) - Vector2.ONE * SEARCH_RADIUS + Vector2.ONE * _half).floor()
	var hi := (a.max(b) + Vector2.ONE * SEARCH_RADIUS + Vector2.ONE * _half).ceil()
	for j in range(maxi(int(lo.y), 1), mini(int(hi.y), _res - 2) + 1):
		for i in range(maxi(int(lo.x), 1), mini(int(hi.x), _res - 2) + 1):
			var p := Vector2(i - _half, j - _half)
			if Geometry2D.get_closest_point_to_segment(p, a, b).distance_to(p) > SEARCH_RADIUS:
				continue
			var s := _sample(i, j)
			if s.y < MIN_COVER:
				continue
			var g := Vector2(_sample(i + 1, j).x - _sample(i - 1, j).x, _sample(i, j + 1).x - _sample(i, j - 1).x) * 0.5
			if g.length() >= FACE_SLOPE:
				pts.append([Vector3(p.x, s.x, p.y), -g])
	return pts


# Fall face summary: drop, downhill dir, foot and lip centres with half-widths across the flow.
func _find_face(a: Vector2, b: Vector2) -> Dictionary:
	var pts := _face_samples(a, b)
	if pts.is_empty():
		return {}
	var top := -INF
	var low := INF
	var flow := Vector2.ZERO
	var visible_pts: Array[Vector3] = []
	for e in pts:
		var p: Vector3 = e[0]
		top = maxf(top, p.y)
		low = minf(low, p.y)
		flow += e[1]
		if p.y - _terrain.get_height(p.x, p.z) > HIDDEN_DEPTH:
			visible_pts.append(p)
	if visible_pts.is_empty():
		return {}
	var dir := flow.normalized()
	var vt := -INF
	var vb := INF
	for p in visible_pts:
		vt = maxf(vt, p.y)
		vb = minf(vb, p.y)
	var span := vt - vb
	var foot := _band(visible_pts, vb - 0.01, vb + span * FOOT_SHARE + 0.01, dir)
	var lip := _band(visible_pts, vt - span * LIP_SHARE - 0.01, vt + 0.01, dir)
	return {"drop": top - low, "dir": dir, "foot": foot[0], "foot_w": foot[1], "lip": lip[0], "lip_w": lip[1]}


# Centre and half-width across the flow of the points whose level lies in [y0, y1].
func _band(pts: Array[Vector3], y0: float, y1: float, dir: Vector2) -> Array:
	var across := Vector2(-dir.y, dir.x)
	var sum := Vector3.ZERO
	var picked: Array[Vector3] = []
	for p in pts:
		if p.y >= y0 and p.y <= y1:
			picked.append(p)
			sum += p
	var c := sum / picked.size()
	var w := 0.0
	for p in picked:
		w = maxf(w, absf(Vector2(p.x - c.x, p.z - c.z).dot(across)))
	return [c, clampf(w + 1.0, 1.5, 12.0)]


func _mist(fall_name: String, face: Dictionary) -> GPUParticles3D:
	var k := clampf(sqrt(face.drop / 20.0), 0.6, 1.3) # bigger drops throw the mist higher
	var w: float = face.foot_w
	var p := _particles(fall_name + "_Mist", face.foot + Vector3(0.0, 0.3, 0.0), face.dir, mist_amount, 1.6)
	var m := _process_material(Vector3(w, 0.3, 1.0), 0.55)
	m.direction = Vector3(0.0, 1.0, -0.35) # up and a little downstream (local -Z)
	m.spread = 35.0
	m.initial_velocity_min = 1.0 * k
	m.initial_velocity_max = 2.6 * k
	m.gravity = Vector3(0.0, -1.5, 0.0)
	m.damping_min = 0.8
	m.damping_max = 1.2
	p.process_material = m
	p.draw_pass_1 = _quad(1.8 * k)
	p.visibility_aabb = AABB(Vector3(-w - 4.0, -2.0, -6.0), Vector3(2.0 * w + 8.0, 10.0, 12.0))
	return p


func _spray(fall_name: String, face: Dictionary) -> GPUParticles3D:
	var w: float = face.lip_w
	var p := _particles(fall_name + "_Spray", face.lip, face.dir, spray_amount, 1.0)
	var m := _process_material(Vector3(w, 0.2, 0.5), 0.35)
	m.direction = Vector3(0.0, 0.2, -1.0) # over the lip, downstream
	m.spread = 20.0
	m.initial_velocity_min = 1.0
	m.initial_velocity_max = 2.2
	m.gravity = Vector3(0.0, -9.8, 0.0)
	p.process_material = m
	p.draw_pass_1 = _quad(0.7)
	p.visibility_aabb = AABB(Vector3(-w - 3.0, -12.0, -6.0), Vector3(2.0 * w + 6.0, 14.0, 9.0))
	return p


# Emitter facing downstream: local -Z = flow, local X = across the fall.
func _particles(node_name: String, at: Vector3, dir: Vector2, amount: int, lifetime: float) -> GPUParticles3D:
	var p := GPUParticles3D.new()
	p.name = node_name
	p.amount = amount
	p.lifetime = lifetime
	p.preprocess = lifetime
	p.randomness = 0.5
	p.cast_shadow = GeometryInstance3D.SHADOW_CASTING_SETTING_OFF
	p.visibility_range_end = visibility_end
	p.transform = Transform3D(Basis.looking_at(Vector3(dir.x, 0.0, dir.y)), at)
	return p


func _process_material(extents: Vector3, alpha: float) -> ParticleProcessMaterial:
	var m := ParticleProcessMaterial.new()
	m.emission_shape = ParticleProcessMaterial.EMISSION_SHAPE_BOX
	m.emission_box_extents = extents
	m.scale_min = 0.7
	m.scale_max = 1.3
	var grow := Curve.new()
	grow.add_point(Vector2(0.0, 0.35))
	grow.add_point(Vector2(1.0, 1.0))
	m.scale_curve = CurveTexture.new()
	m.scale_curve.curve = grow
	var fade := Gradient.new()
	fade.offsets = PackedFloat32Array([0.0, 0.2, 1.0])
	fade.colors = PackedColorArray([Color(1, 1, 1, 0), Color(1, 1, 1, alpha), Color(1, 1, 1, 0)])
	m.color_ramp = GradientTexture1D.new()
	m.color_ramp.gradient = fade
	return m


# Lit soft disc, so the mist takes the preset's light; proximity fade hides where it meets rock.
func _quad(size: float) -> QuadMesh:
	var mat := StandardMaterial3D.new()
	mat.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
	mat.billboard_mode = BaseMaterial3D.BILLBOARD_PARTICLES
	mat.vertex_color_use_as_albedo = true
	mat.albedo_color = Color(0.92, 0.96, 0.97)
	mat.albedo_texture = _disc
	mat.diffuse_mode = BaseMaterial3D.DIFFUSE_LAMBERT_WRAP
	mat.specular_mode = BaseMaterial3D.SPECULAR_DISABLED
	mat.disable_receive_shadows = true
	mat.proximity_fade_enabled = true
	mat.proximity_fade_distance = 1.0
	var q := QuadMesh.new()
	q.size = Vector2(size, size)
	q.material = mat
	return q


# Same soft disc as the scene's dust motes.
func _soft_disc() -> GradientTexture2D:
	var g := Gradient.new()
	g.offsets = PackedFloat32Array([0.0, 0.5, 1.0])
	g.colors = PackedColorArray([Color(1, 1, 1, 1), Color(1, 1, 1, 0.5), Color(1, 1, 1, 0)])
	var t := GradientTexture2D.new()
	t.gradient = g
	t.width = 32
	t.height = 32
	t.fill = GradientTexture2D.FILL_RADIAL
	t.fill_from = Vector2(0.5, 0.5)
	t.fill_to = Vector2(1.0, 0.5)
	return t
