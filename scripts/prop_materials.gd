class_name PropMaterials
extends RefCounted

# Generated GLBs (character, lodge, stump) ship noise metal maps: character.glb has
# metallic = 1 on every texel (~0.99). A fully metallic rough surface has no diffuse term, so
# it only shows blurred sky reflections and reads as a black silhouette away from the sun.
# These are dielectric: drop the metal map, keep albedo and roughness data untouched.
static func make_dielectric(root: Node) -> void:
	for mi: MeshInstance3D in root.find_children("*", "MeshInstance3D", true, false):
		for s in mi.mesh.get_surface_count():
			var m := mi.get_active_material(s) as StandardMaterial3D
			if m == null or m.metallic == 0.0:
				continue
			m = m.duplicate() as StandardMaterial3D
			m.metallic = 0.0
			m.metallic_texture = null
			mi.set_surface_override_material(s, m)
