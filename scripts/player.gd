extends CharacterBody3D

const SPEED := 5.0
const KEY_TURN_SPEED := 2.5

@export var mouse_sensitivity := 0.003 # radians per pixel

var _gravity: float = ProjectSettings.get_setting("physics/3d/default_gravity")


func _ready() -> void:
	Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
	_fix_model_materials($Model)


# character.glb ships metallic = 1 on every texel (metal channel ~0.99). A fully metallic
# rough cloak has no diffuse term, so it only shows blurred sky reflections and reads as a
# black silhouette away from the sun. The cloth is dielectric: drop the metal map, keep
# albedo and roughness data untouched.
func _fix_model_materials(root: Node) -> void:
	for mi: MeshInstance3D in root.find_children("*", "MeshInstance3D", true, false):
		for s in mi.mesh.get_surface_count():
			var m := mi.get_active_material(s) as StandardMaterial3D
			if m == null or m.metallic == 0.0:
				continue
			m = m.duplicate() as StandardMaterial3D
			m.metallic = 0.0
			m.metallic_texture = null
			mi.set_surface_override_material(s, m)


func _physics_process(delta: float) -> void:
	rotate_y(Input.get_axis("turn_right", "turn_left") * KEY_TURN_SPEED * delta)
	var input := Input.get_vector("move_left", "move_right", "move_forward", "move_back")
	var dir := (transform.basis * Vector3(input.x, 0.0, input.y)).limit_length(1.0)
	velocity.x = dir.x * SPEED
	velocity.z = dir.z * SPEED
	if not is_on_floor():
		velocity.y -= _gravity * delta
	else:
		velocity.y = 0.0
	move_and_slide()
	RenderingServer.global_shader_parameter_set("player_position", global_position)


func turn(dx: float) -> void:
	rotate_y(-dx * mouse_sensitivity)


func _unhandled_input(event: InputEvent) -> void:
	var captured := Input.mouse_mode == Input.MOUSE_MODE_CAPTURED
	if event is InputEventMouseMotion and captured:
		turn(event.relative.x)
	elif event is InputEventMouseButton and event.pressed and not captured:
		Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
	elif event.is_action_pressed("ui_cancel"):
		# First Esc frees the cursor, second quits.
		if captured:
			Input.mouse_mode = Input.MOUSE_MODE_VISIBLE
		else:
			get_tree().quit()
