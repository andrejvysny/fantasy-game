class_name WorldStyle extends Resource
## Material style shared by every world shader, independent of time of day.
## Colours are authored in sRGB (as picked in the inspector) and pushed as linear globals.

@export_group("Ground palette")
@export var meadow := Color("6e8b40")
@export var dry := Color("a09553")
@export var moss := Color("4d6a33")
@export var litter := Color("5e4c33")
@export var dirt := Color("806549")


func apply() -> void:
	var globals := {
		"ground_meadow": meadow,
		"ground_dry": dry,
		"ground_moss": moss,
		"ground_litter": litter,
		"ground_dirt": dirt,
	}
	for name: String in globals:
		RenderingServer.global_shader_parameter_set(name, (globals[name] as Color).srgb_to_linear())
