---
name: instance-uniform-budget
description: world.gdshaderinc has an `instance uniform`; every GeometryInstance3D using it eats global shader buffer slots — valley overflowed at ~4k instances
metadata:
  type: project
---
`materials/world.gdshaderinc` declares `instance uniform float occluder_fade`, so every MultiMeshInstance3D / MeshInstance3D using world*.gdshader (trees, nature rocks/plants) allocates slots in the global shader variable buffer. Default buffer (65536) fits ~4096 such instances; valley legacy forest (~2900 chunks) + props (~1500 chunks) overflowed with "Too many instances using shader instance variables" and follow-on `instance_buffer_pos.has(p_instance)` errors (backtrace points at unrelated mesh/material calls). project.godot now sets `rendering/limits/global_shader_variables/buffer_size=262144`.

**Why:** error only shows in the RD renderer (not headless dummy), so headless checks miss it.

**How to apply:** when adding many chunked instances, count GeometryInstance3D nodes and test a windowed run (`godot --path . res://scenes/valley.tscn --resolution 320x180 --quit-after 10`) for ERROR lines.
