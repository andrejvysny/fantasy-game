extends Node3D

const PERF_WARMUP := 60

@export var style: WorldStyle = preload("res://materials/world_style.tres")

var _perf := false
var _perf_frames := 0
var _perf_gpu := PackedFloat32Array()
var _perf_cpu := PackedFloat32Array()


func _ready() -> void:
	style.apply()
	var spawn := Vector2.ZERO
	# Scripted screenshots: --pos=<x>,<z> spawn point, --yaw=<deg> facing.
	for arg in OS.get_cmdline_user_args():
		if arg.begins_with("--pos="):
			var v := arg.trim_prefix("--pos=").split_floats(",")
			spawn = Vector2(v[0], v[1])
		elif arg.begins_with("--yaw="):
			$Player.rotation.y = deg_to_rad(float(arg.trim_prefix("--yaw=")))
	$Player.global_position = Vector3(spawn.x, $Terrain.get_height(spawn.x, spawn.y) + 2.0, spawn.y)
	$CameraRig.snap()
	_perf = "--perf" in OS.get_cmdline_user_args()
	if _perf:
		RenderingServer.viewport_set_measure_render_time(get_viewport().get_viewport_rid(), true)


# --perf: per-frame render times after warmup; avg/percentiles printed on exit.
func _process(_delta: float) -> void:
	if not _perf:
		return
	_perf_frames += 1
	if _perf_frames <= PERF_WARMUP:
		return
	var rid := get_viewport().get_viewport_rid()
	_perf_gpu.append(RenderingServer.viewport_get_measured_render_time_gpu(rid))
	_perf_cpu.append(RenderingServer.viewport_get_measured_render_time_cpu(rid))


func _exit_tree() -> void:
	var n := _perf_gpu.size()
	if not _perf or n == 0:
		return
	print("PERF driver=%s method=%s size=%s frames=%d" % [
		RenderingServer.get_current_rendering_driver_name(),
		RenderingServer.get_current_rendering_method(),
		_size_str(), n])
	print(_perf_line("gpu_ms", _perf_gpu))
	print(_perf_line("cpu_ms", _perf_cpu))


func _perf_line(label: String, data: PackedFloat32Array) -> String:
	var sorted := data.duplicate()
	sorted.sort()
	var n := sorted.size()
	var sum := 0.0
	for v in data:
		sum += v
	var pct := func(p: float) -> float: return sorted[clampi(int(ceil(p * n)) - 1, 0, n - 1)]
	return "PERF %s avg=%.2f p50=%.2f p95=%.2f p99=%.2f max=%.2f" % [
		label, sum / n, pct.call(0.5), pct.call(0.95), pct.call(0.99), sorted[n - 1]]


func _size_str() -> String:
	var s := get_viewport().get_visible_rect().size
	return "%dx%d" % [s.x, s.y]
