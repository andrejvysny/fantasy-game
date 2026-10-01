extends CharacterBody3D

const SPEED := 5.0
const KEY_TURN_SPEED := 2.5
# Visual layer 20 is the character's alone: the Fill light (cool dark-side fill, energy per
# lighting preset in atmosphere.gd) is culled to it so the environment grading is untouched.
const FILL_LAYER := 1 << 19

@export var mouse_sensitivity := 0.003 # radians per pixel

var _gravity: float = ProjectSettings.get_setting("physics/3d/default_gravity")


func _ready() -> void:
	Input.mouse_mode = Input.MOUSE_MODE_CAPTURED
	PropMaterials.make_dielectric($Model)
	for mi: MeshInstance3D in $Model.find_children("*", "MeshInstance3D", true, false):
		mi.layers |= FILL_LAYER
	$Fill.light_cull_mask = FILL_LAYER


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
