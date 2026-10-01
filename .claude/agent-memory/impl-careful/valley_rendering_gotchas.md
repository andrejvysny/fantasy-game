---
name: valley-rendering-gotchas
description: Non-obvious Godot valley rendering/verification gotchas (transparent chunk seams, fract mip seams, noisy perf, sky visibility, class cache)
metadata:
  type: project
---

- Transparent chunked grids (water) double-blend shared edges unless vertices are bit-identical: use `world_vertex_coords` and snap VERTEX.xz to the sample grid. Opaque terrain hides this.
- `texture(tex, fract(uv))` on mipmapped noise draws 1-px seam lines where uv wraps; use textureLod / textureGrad (cloud_noise, brush_noise globals). Terrain/painted_light still has such dashed lines (not fixed, off-limits).
- Perf (`--perf` PERF gpu_ms) is very noisy when other agents run godot in parallel: check `pgrep -f "godot --path"`, interleave on/off pairs, compare p50. Water toggle: `--water=0`.
- Camera far = 250 m, fov 32-55: little sky is visible in capture views; judge sky with capture.sh extra args `-- --cam=3,57` (extra args override view args). Below-horizon sky shows past the far plane over the southern sea.
- When another agent adds a `class_name`, scenes fail with "Identifier not declared" until `godot --headless --path . --import` refreshes the class cache.
- The capture rig camera can't frame the east falls (gorge walls, close-up pitch curve). For free inspection make a TEMPORARY scene instancing valley.tscn plus a Camera3D with a built-in GDScript reading `--dbgcam=x,y,z,tx,ty,tz` (and an in-process A/B node toggling a feature every 30 frames for paired GPU p50); delete it afterwards.
- Fall faces in water.res are not on the FALLS lines (canyon top/mid have no step at all); the sheet geometry dives into the terrain, so its contact must be faded (bed depth of the bilinear level + scene-depth gap) or it shows a 2 m sawtooth. valley_falls.gd finds faces from the level gradient.
- A view capture occasionally renders with the player displaced (seen once on 18_east_falls_gorge, same args, identical rerun fine): rerun before blaming a change.
- Water data is regenerated from tools/terrain/out by gen_water.py + export_water.gd (appended to build.sh); never rerun build.sh/gen_heightmap for water work.

**Why:** learned while adding water + sky (2026-09-30); each cost a debugging round.
**How to apply:** check these first when a valley capture shows thin lines/seams or perf numbers look inconsistent.
