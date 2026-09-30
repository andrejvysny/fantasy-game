class_name LightingPreset extends Resource

@export var sun_rotation_deg: Vector3
@export var sun_color: Color
@export var sun_energy: float
@export var sun_volumetric_energy: float
@export var ambient_color: Color
@export var ambient_energy: float
@export var ambient_sky_contribution := 0.5
@export var sky_top: Color
@export var sky_horizon: Color
@export var ground_horizon: Color
@export var fog_color: Color
@export var fog_density: float # depth fog: maximum opacity at fog_depth_end
@export var fog_depth_begin := 30.0
@export var fog_depth_end := 160.0
@export var fog_height: float
@export var fog_height_density: float
@export var vol_fog_density: float
@export var vol_fog_albedo: Color
@export var vol_fog_emission: Color
@export var ground_fog_density: float
@export var shadow_tint: Color
@export var cloud_shadow_strength: float
@export var exposure: float
@export var agx_contrast := 1.25
@export var saturation := 1.0
@export var fog_sun_scatter := 0.0
@export var fog_aerial_perspective := 0.0
@export var focus_fog_color := Color(0.93, 0.95, 0.97, 0.9)
@export var grade: Gradient
@export var fireflies: bool
@export var fire_energy := 1.0
