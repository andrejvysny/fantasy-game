extends SceneTree
## Converts the generated placement fields into lossless Godot Image resources.
##   godot --headless --path <project> --script <abs path>/export_fields.gd
## Reads out/fields/{ground,flowers,habitat,bank}.png next to this script (written by scatter.py),
## writes res://world/generated/fields/{ground,flowers,habitat,bank}.res (FORMAT_RGBA8, row 0 north,
## pixel (ix, iz) at world x = ix - 511.5, z = iz - 511.5). bank is optional (habitats 'banks').

const DEST := "res://world/generated/fields/"
const NAMES := ["ground", "flowers", "habitat", "bank"]
const OPTIONAL := ["bank"]


func _init() -> void:
	var src: String = get_script().resource_path.get_base_dir().path_join("out/fields")
	if src.begins_with("res://"):
		src = ProjectSettings.globalize_path(src)
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(DEST))
	for name: String in NAMES:
		if name in OPTIONAL and not FileAccess.file_exists(src.path_join(name + ".png")):
			print("skipped %s (no %s.png)" % [name, name])
			continue
		var img := Image.load_from_file(src.path_join(name + ".png"))
		if img == null or img.is_empty():
			push_error("missing %s/%s.png (run scatter.py first)" % [src, name])
			quit(1)
			return
		img.convert(Image.FORMAT_RGBA8)
		var err := ResourceSaver.save(img, DEST + name + ".res")
		if err != OK:
			push_error("saving %s failed: %d" % [name, err])
			quit(1)
			return
		print("exported %s %dx%d" % [name, img.get_width(), img.get_height()])
	quit()
