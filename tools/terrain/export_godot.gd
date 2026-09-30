extends SceneTree
## Converts the generated terrain data into lossless Godot Image resources.
##   godot --headless --path <project> --script <abs path>/export_godot.gd
## Reads out/heightmap.f32 (+ heightmap.json) and out/splat_*.png next to this script,
## writes res://terrains/valley/{height,splat_0,splat_1,splat_2}.res and valley.json.

const DEST := "res://terrains/valley/"


func _init() -> void:
	var src: String = get_script().resource_path.get_base_dir().path_join("out")
	if src.begins_with("res://"):
		src = ProjectSettings.globalize_path(src)
	var meta: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(src.path_join("heightmap.json")))
	var res: int = meta["res"]
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(DEST))
	var raw := FileAccess.get_file_as_bytes(src.path_join("heightmap.f32"))
	if raw.size() != res * res * 4:
		push_error("heightmap.f32 has %d bytes, expected %d" % [raw.size(), res * res * 4])
		quit(1)
		return
	_save(Image.create_from_data(res, res, false, Image.FORMAT_RF, raw), "height")
	for i in 3:
		var img := Image.load_from_file(src.path_join("splat_%d.png" % i))
		img.convert(Image.FORMAT_RGB8)
		_save(img, "splat_%d" % i)
	var splat: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(src.path_join("splat.json")))
	meta["layers"] = splat["layers"]
	var f := FileAccess.open(DEST + "valley.json", FileAccess.WRITE)
	f.store_string(JSON.stringify(meta, "  "))
	f.close()
	print("exported valley terrain %dx%d, %.1f..%.1f m" % [res, res, meta["min_m"], meta["max_m"]])
	quit()


func _save(img: Image, name: String) -> void:
	var err := ResourceSaver.save(img, DEST + name + ".res")
	if err != OK:
		push_error("saving %s failed: %d" % [name, err])
