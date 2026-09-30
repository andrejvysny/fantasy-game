extends Node3D

# Artistic intensity (presets use it as time-of-day compensation): scales the light and
# thins flame/smoke, but never puts the fire out. Extinguishing is `burning`.
@export var energy := 1.0: set = set_energy
@export var burning := true: set = set_burning
@export var base_light_energy := 2.2
@export var flicker_amount := 0.18
@export var flicker_speed := 9.0

const JITTER := 0.03

var _t := 0.0
var _light_base := Vector3.ZERO

@onready var _light: OmniLight3D = $FireLight
@onready var _flame: GPUParticles3D = $Flame
@onready var _smoke: GPUParticles3D = $Smoke
@onready var _embers: GPUParticles3D = $Embers


func _ready() -> void:
	_light_base = _light.position
	_t = randf() * 100.0


func set_energy(value: float) -> void:
	energy = maxf(value, 0.0)


func set_burning(value: bool) -> void:
	burning = value
	if not is_node_ready():
		await ready
	_light.visible = burning
	for p: GPUParticles3D in [_flame, _smoke, _embers]:
		p.emitting = burning


func _process(delta: float) -> void:
	_t += delta * flicker_speed
	_light.light_energy = base_light_energy * energy * (1.0 + flicker_amount * _noise(_t))
	_light.position = _light_base + Vector3(_noise(_t * 1.3 + 7.0), 0.0, _noise(_t * 0.9 + 19.0)) * JITTER
	_flame.amount_ratio = clampf(0.35 + 0.65 * energy, 0.0, 1.0)
	_smoke.amount_ratio = clampf(0.5 + 0.5 * energy, 0.0, 1.0)


# Incommensurate sines, normalized to about [-1, 1].
func _noise(x: float) -> float:
	return (sin(x) + sin(x * 2.3 + 1.7) * 0.6 + sin(x * 0.61 + 4.1) * 0.8) / 2.4
