shader_type spatial;
render_mode diffuse_lambert, specular_disabled;

// MultiMesh variant (valley): no instance uniform, fade from INSTANCE_CUSTOM.r.
#define WORLD_MULTIMESH
#include "res://materials/world.gdshaderinc"
