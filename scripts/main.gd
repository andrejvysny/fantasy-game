extends Node3D

const PERF_WARMUP := 60

var _perf := false
var _perf_frames := 0
var _perf_gpu := 0.0
var _perf_cpu := 0.0


func _ready() -> void:
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


# --perf: average render times after warmup, printed on exit.
func _process(_delta: float) -> void:
	if not _perf:
		return
	_perf_frames += 1
	if _perf_frames <= PERF_WARMUP:
		return
	var rid := get_viewport().get_viewport_rid()
	_perf_gpu += RenderingServer.viewport_get_measured_render_time_gpu(rid)
	_perf_cpu += RenderingServer.viewport_get_measured_render_time_cpu(rid)


func _exit_tree() -> void:
	var n := _perf_frames - PERF_WARMUP
	if _perf and n > 0:
		print("PERF frames=%d gpu_ms=%.2f cpu_ms=%.2f" % [n, _perf_gpu / n, _perf_cpu / n])
