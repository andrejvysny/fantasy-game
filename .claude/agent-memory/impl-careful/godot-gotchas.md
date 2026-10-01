---
name: godot-gotchas
description: Godot project gotchas hit while adding scripts/shaders to the valley scene (class cache, painted-light banding)
metadata:
  type: reference
---

- A new `class_name` script is unknown to `godot --path . <scene>` runs until `godot --headless --path . --import` refreshes .godot/global_script_class_cache.cfg (typed exports like Array[MyClass] fail to parse before that).
- painted_light.gdshaderinc bands diffuse by N.L (band_low/band_high). Foliage on terrain must use the terrain's `wrap` (0.3 default) and mostly the terrain normal, or on slopes the ground sits in the half-lit band while up-facing blades sit in the full band and read as bright dots. See [[groundcover-cost-model]].
- A `global uniform` shares the namespace of material uniforms: adding global `wind` (materials/wind.gdshaderinc) forced groundcover's per-layer uniform to become `wind_amplitude` (valley_groundcover.gd maps GroundcoverLayer.wind onto it). Check every includer for a same-named uniform before adding a global.
- `godot --write-movie <path>` with a relative path resolves against the project dir when the command cd's there; pass absolute paths (failure shows as `d.is_null()` / `f_wav.is_null()` spam).
