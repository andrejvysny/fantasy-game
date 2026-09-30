class_name CameraRig extends Node3D

const TERRAIN_MASK := 1 << 2

@export var target_path: NodePath
@export var pitch_deg := 57.0
@export var min_pitch_deg := 20.0
@export var max_pitch_deg := 80.0
@export var mouse_sensitivity_deg := 0.17 # degrees per pixel
@export var ground_clearance := 1.0
@export var distance := 26.0
@export var min_distance := 2.5
@export var max_distance := 42.0
@export var zoom_factor := 0.85 # per wheel step; multiplicative so close range isn't one jump
@export_group("Close-up")
@export var closeup_start := 20.0 # distance where the blend toward over-the-shoulder begins
@export var tactical_fov := 55.0
@export var closeup_fov := 70.0
# (distance m, pitch deg) keypoints, ascending distance, for the default 57 deg pitch.
# Beyond the last point the mouse-set pitch applies unchanged.
@export var closeup_pitch_curve := PackedVector2Array([Vector2(2.5, 8.0), Vector2(8.0, 14.0), Vector2(10.0, 20.0), Vector2(20.0, 57.0)])
@export var tactical_look_height := 1.0
@export var closeup_look_height := 1.6
@export var closeup_look_ahead := 4.0
@export_group("")
@export var follow_speed := 8.0
@export var rotate_speed := 12.0
@export var zoom_speed := 6.0

@onready var _camera: Camera3D = $Camera

var _target: Node3D
var _yaw := 0.0
var _target_yaw := 0.0
var _target_distance := 26.0
var _target_pitch := 57.0
var _snap := true


func _ready() -> void:
	top_level = true
	# Scripted screenshots: --cam=<distance>,<mouse pitch deg>.
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--cam="):
			var v := arg.trim_prefix("--cam=").split_floats(",")
			distance = v[0]
			if v.size() > 1:
				pitch_deg = v[1]
	_target_distance = clampf(distance, min_distance, max_distance)
	distance = _target_distance
	_target_pitch = clampf(pitch_deg, min_pitch_deg, max_pitch_deg)
	_target = get_node_or_null(target_path) as Node3D


func get_yaw() -> float:
	return _yaw


# Mouse up (negative dy) looks toward the horizon (lower pitch).
func tilt(dy: float) -> void:
	_target_pitch = clampf(_target_pitch + dy * mouse_sensitivity_deg, min_pitch_deg, max_pitch_deg)


func snap() -> void:
	_snap = true


func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseMotion and Input.mouse_mode == Input.MOUSE_MODE_CAPTURED:
		tilt(event.relative.y)
	elif event.is_action_pressed("zoom_in"):
		_target_distance = clampf(_target_distance * zoom_factor, min_distance, max_distance)
	elif event.is_action_pressed("zoom_out"):
		_target_distance = clampf(_target_distance / zoom_factor, min_distance, max_distance)


func _process(delta: float) -> void:
	if _target == null:
		return
	# Sit behind the player: player forward is -Z, rig offset is +Z in yaw space.
	_target_yaw = _target.global_rotation.y
	if _snap:
		global_position = _target.global_position
		_yaw = _target_yaw
		distance = _target_distance
		pitch_deg = _target_pitch
		_snap = false
	else:
		global_position = global_position.lerp(_target.global_position, 1.0 - exp(-follow_speed * delta))
		_yaw = lerp_angle(_yaw, _target_yaw, 1.0 - exp(-rotate_speed * delta))
		distance = lerpf(distance, _target_distance, 1.0 - exp(-zoom_speed * delta))
		pitch_deg = lerpf(pitch_deg, _target_pitch, 1.0 - exp(-rotate_speed * delta))
	_place_camera()


# Tactical above closeup_start; zooming in blends to a flatter, wider, over-the-shoulder view.
func _place_camera() -> void:
	var t := smoothstep(closeup_start, min_distance, distance)
	var pitch := deg_to_rad(_closeup_pitch(distance))
	var yaw_basis := Basis(Vector3.UP, _yaw)
	var head := global_position + Vector3.UP * lerpf(tactical_look_height, closeup_look_height, t)
	var look_at_point := head + yaw_basis * Vector3.FORWARD * closeup_look_ahead * t
	var offset := yaw_basis * Vector3(0.0, sin(pitch) * distance, cos(pitch) * distance)
	_camera.fov = lerpf(tactical_fov, closeup_fov, t)
	_camera.global_position = _clear_terrain(head, head + offset)
	_camera.look_at(look_at_point)


# Piecewise-linear pitch by distance. Scaled by pitch_deg / 57 so mouse tilt still
# works proportionally up close; exactly the keypoints at the default pitch.
func _closeup_pitch(d: float) -> float:
	var pts := closeup_pitch_curve
	if pts.is_empty() or d >= pts[pts.size() - 1].x:
		return pitch_deg
	var scale := pitch_deg / pts[pts.size() - 1].y
	if d <= pts[0].x:
		return pts[0].y * scale
	for i in range(1, pts.size()):
		if d <= pts[i].x:
			var k := inverse_lerp(pts[i - 1].x, pts[i].x, d)
			return lerpf(pts[i - 1].y, pts[i].y, k) * scale
	return pitch_deg


# Low pitch can put a hill between player and camera; ray only hits terrain (layer 3) so trees still dither instead.
func _clear_terrain(from: Vector3, to: Vector3) -> Vector3:
	var query := PhysicsRayQueryParameters3D.create(from, to, TERRAIN_MASK)
	var hit := get_world_3d().direct_space_state.intersect_ray(query)
	if hit.is_empty():
		return to
	return hit.position + (from - to).normalized() * ground_clearance + Vector3.UP * ground_clearance
