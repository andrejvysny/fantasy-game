extends SceneTree
## Converts the generated water data into a lossless Godot Image resource.
##   godot --headless --path <project> --script <abs path>/export_water.gd
## Reads out/water.f32 (+ water.json) written by gen_water.py next to this script and writes
## res://terrains/valley/water.res (FORMAT_RGF: r = water level m, g = coverage 0..1).

const DEST := "res://terrains/valley/"


func _init() -> void:
	var src: String = get_script().resource_path.get_base_dir().path_join("out")
	if src.begins_with("res://"):
		src = ProjectSettings.globalize_path(src)
	var meta: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(src.path_join("water.json")))
	var res: int = meta["res"]
	var raw := FileAccess.get_file_as_bytes(src.path_join("water.f32"))
	if raw.size() != res * res * 8:
		push_error("water.f32 has %d bytes, expected %d" % [raw.size(), res * res * 8])
		quit(1)
		return
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(DEST))
	var err := ResourceSaver.save(Image.create_from_data(res, res, false, Image.FORMAT_RGF, raw), DEST + "water.res")
	if err != OK:
		push_error("saving water failed: %d" % err)
		quit(1)
		return
	print("exported valley water %dx%d, level %.1f..%.1f m" % [res, res, meta["min_level_m"], meta["max_level_m"]])
	quit()
