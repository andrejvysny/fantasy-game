class_name GroundcoverLayer extends Resource
## One GPU-scattered groundcover mesh (valley_groundcover.gd): a world-space cell grid of
## `spacing` around the camera out to `radius`, thinned by a density field channel.
## Two layers with the same mesh where one's inner_radius lies inside the other's radius
## form a ring pair: they cross-fade by cell hash over the overlap instead of doubling.

@export_file("*.glb", "*.gltf", "*.tscn", "*.res", "*.tres") var mesh_path := ""
@export_enum("ground", "flowers") var field := "ground"
@export_range(0, 3) var channel := 0 # ground: r short, g tall; flowers: r white, g pink, b yellow, a blue
@export var spacing := 0.5 # metres per cell, one candidate instance each
@export var radius := 30.0
@export var inner_radius := 0.0 # 0 for the inner ring
@export var density := 1.0 # multiplier on the field value (keep probability per cell)
@export var scale_min := 0.8
@export var scale_max := 1.2
@export var max_slope := 0.8 # rise over run
@export_range(0.0, 1.0) var palette_strength := 0.7 # pull toward the ground palette; 0 for flowers
@export var wind := 0.04 # metres of sway at flex 1
@export var seed := 1
@export_group("Distance thinning")
@export var thin_start := 12.0 # metres from the camera where thinning begins
@export_range(0.0, 1.0) var far_keep := 0.6 # keep share at radius
