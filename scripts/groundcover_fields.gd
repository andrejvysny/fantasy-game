class_name GroundcoverFields extends RefCounted
## Density fields for valley_groundcover.gd. The scatter generator writes the real ones to
## res://world/generated/fields/{ground,flowers}.res (Image RGBA8, 1 px per terrain sample);
## until then an interim stub is derived from the terrain splat and cached next to them.

const DIR := "res://world/generated/fields/"
const FLOWER_SEEDS := [9101, 9202, 9303, 9404] # white, pink, yellow, blue
# Peak drift density and noise threshold per flower colour: white/pink drifts, yellow/blue accents.
const FLOWER_PEAK := [0.85, 0.7, 0.5, 0.4]
const FLOWER_EDGE := [0.58, 0.62, 0.7, 0.72]


## Real field if present, else the cached stub (built on first use). Logs which one it used.
static func load_field(field_name: String, splat_dir: String) -> Image:
	var real := DIR + field_name + ".res"
	if ResourceLoader.exists(real):
		var img := load(real) as Image
		if img != null:
			print("groundcover: field %s <- %s" % [field_name, real])
			return img
		push_warning("groundcover: %s failed to load, using the stub" % real)
	var stub := DIR + "_stub_" + field_name + ".res"
	if ResourceLoader.exists(stub):
		print("groundcover: field %s <- %s (stub)" % [field_name, stub])
		return load(stub) as Image
	var img := _build_ground(splat_dir) if field_name == "ground" else _build_flowers(splat_dir)
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(DIR))
	var err := ResourceSaver.save(img, stub)
	print("groundcover: field %s <- generated stub %s (save %s)" % [field_name, stub, error_string(err)])
	return img


static func _splat_bytes(splat_dir: String, index: int) -> PackedByteArray:
	var img := (load(splat_dir + "splat_%d.res" % index) as Image).duplicate() as Image
	img.convert(Image.FORMAT_RGB8)
	return img.get_data()


# r = grass + dry grass + a little on forest floor; tall, wear and canopy stay 0.
static func _build_ground(splat_dir: String) -> Image:
	var s2 := _splat_bytes(splat_dir, 2)
	var n := s2.size() / 3
	var size := int(sqrt(n))
	var out := PackedByteArray()
	out.resize(n * 4)
	out.fill(0)
	for i in n:
		out[i * 4] = mini(255, s2[i * 3 + 1] + s2[i * 3 + 2] + int(s2[i * 3] * 0.12))
	return Image.create_from_data(size, size, false, Image.FORMAT_RGBA8, out)


# Drifts: thresholded low-frequency noise, faded by a second noise, only over grass.
static func _build_flowers(splat_dir: String) -> Image:
	var s2 := _splat_bytes(splat_dir, 2)
	var n := s2.size() / 3
	var size := int(sqrt(n))
	var out := PackedByteArray()
	out.resize(n * 4)
	out.fill(0)
	for c in 4:
		var drift := _noise(FLOWER_SEEDS[c], 0.02, size).get_data()
		var body := _noise(FLOWER_SEEDS[c] + 1, 0.08, size).get_data()
		var edge: float = FLOWER_EDGE[c]
		var peak: float = FLOWER_PEAK[c]
		for i in n:
			var grass := (s2[i * 3 + 1] * 0.5 + s2[i * 3 + 2]) / 255.0
			var w := smoothstep(edge, edge + 0.1, drift[i] / 255.0) * (0.5 + 0.5 * body[i] / 255.0)
			out[i * 4 + c] = int(clampf(w * peak * grass, 0.0, 1.0) * 255.0)
	return Image.create_from_data(size, size, false, Image.FORMAT_RGBA8, out)


static func _noise(noise_seed: int, frequency: float, size: int) -> Image:
	var noise := FastNoiseLite.new()
	noise.seed = noise_seed
	noise.frequency = frequency
	noise.fractal_octaves = 3
	var img := noise.get_image(size, size, false, false, true)
	img.convert(Image.FORMAT_L8)
	return img
