# Valley nature assets

Procedural Blender 5.2 assets for the valley (plan: `docs/valley_environment_plan.md`).
Scripts live in `tools/blender/` (shared helpers: `nature_lib.py`); run headless:

```
/Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup -P tools/blender/<family>.py [-- asset_id ...]
```

## Layout
```
assets/nature/<group>/<asset_id>.glb     evaluated export (Godot imports this)
assets/nature/<group>/<asset_id>.json    measured metadata (below)
assets/nature/<group>/source/<asset_id>.blend   editable source (ignored by Godot), nl.save_blend(group, asset_id)
assets/nature/<group>/previews/*.png     clay + colour, 3/4 view and player-height view, 1 m cube + 1.8 m capsule
```
Groups: `rocks`, `trees`, `groundcover`, `understory`, `debris`.

## Asset contract
- Metres. Authored Z-up in Blender; the glTF exporter converts to Godot Y-up (`export_yup`). No manual
  axis rotation anywhere. Verified with `tools/environment/asset_check.gd` (AABB must match metadata).
- One mesh per asset, transforms applied (instancing reads mesh vertices, not node transforms).
- Pivot: plants/trees at ground contact (y = 0 at trunk/stem base). Rocks at a deliberate contact origin;
  `embed_depth` = how far the mesh reaches below y = 0 and is meant to stay buried.
- Surfaces (max two), identified by material name, never by colour:
  - `M_solid`: rock, bark, wood, soil. Single sided.
  - `M_foliage`: needles, leaves, fronds, blades, petals. Double sided in Godot.
- `COLOR_0` RGBA, linear: rgb = broad painted base colour (grouped per plane/lobe, no speckle),
  a = flex weight for wind (0 anchored root/trunk/rock, 1 free tip).
- `UV0`: stable unwrap, reserved for a later texture pass (256 px/m environment, 512 px/m hero).
- `UV2` (glTF TEXCOORD_1): x = restrained cavity/occlusion (1 open .. 0 occluded), y = per-part random 0..1.
- No baked sunlight, cast shadows, fire light or AO standing in for contact. Metallic 0, roughness from shader.
- Directional modules (cliff faces/corners, rock shelves, logs lying across a slope): the exposed front faces
  Blender -Y, which is Godot +Z. Placement recipes rotate so +Z faces the viewer/route/downhill.
- No negative scale on asymmetric assets. Rocks keep a shared fracture axis per outcrop (placement rule).
- Moss/grass on rocks is shader-side (up-facing mask), not a fixed green cap, unless the metadata says
  `orientation_constrained: true`.

## Metadata (`<asset_id>.json`)
`asset_id, version, family, group, habitats, bbox_min/bbox_max (Godot axes), pivot, embed_depth,
scale_range, max_tilt_deg, orientation_constrained, materials, tris, verts, budget_tris, within_budget,
non_manifold_edges, lod, collision, wind, texel_density, channels, recipe (seed + parameters),
approval, provenance, notes`.

`collision.class`: `none` | `trunk` (`radius`, `height`: Godot cylinder at the pivot) | `convex` (hull of
the mesh) | `trimesh` (cliff modules). `lod`: `godot_auto` (import-generated mesh LODs) or `none`.

`approval`: `candidate` -> `clay_approved` -> `material_approved` -> `approved`. Status tracking:
implemented / structurally validated / visually approved / validated in motion / published (TODO.md).

## Checks
```
godot --headless --path . --import
godot --headless --path . --script $PWD/tools/environment/asset_check.gd [-- group ...]
```
