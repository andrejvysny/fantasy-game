---
name: groundcover-cost-model
description: What dominates GPU cost of the GPU-scattered groundcover (valley_groundcover.gd) and which levers work
metadata:
  type: project
---

Cost of GPU-placed MultiMesh groundcover is vertex invocations, killed or not: a collapsed instance still runs the full Godot vertex pipeline for every mesh vertex, twice (depth prepass + colour). Measured 2026-09-30: a sparse flower layer (300-vert mesh, ~1% field coverage) cost as much as the dense grass ring.

**Why:** there is no per-instance culling in a MultiMesh; frustum culling is per MultiMeshInstance3D AABB only.

**How to apply:** levers that worked: camera-following tiles (12 m) instead of one ring-sized instance, per-tile AABB y-range from a height min/max grid (a box spanning the valley's full height range is rarely culled), wider spacing / smaller radius for sparse layers, bigger clump scale instead of more instances for coverage. Shader-side early outs help little. Final: ~1.4 ms at 1080p vulkan spawn view. See [[gpu-timing-mac]].
