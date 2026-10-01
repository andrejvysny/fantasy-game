# tools/environment

Offline tools for the valley environment (plan: `docs/valley_environment_plan.md`, sections 3, 7, 8, 10).

| tool | what |
|---|---|
| `probe.py` | height / slope / layer / water level at world points, yaw toward a target |
| `asset_check.gd` | GLB vs metadata contract check for `assets/nature` |
| `scatter.py` | deterministic placement generator (CLI; modules below) |
| `export_fields.gd` | field PNGs -> lossless Godot `Image` resources (bank.png optional) |

## Placement generator

```
cd tools/environment
uv run scatter.py --dry-run            # compute, diff vs world/generated, report; writes only out/
uv run scatter.py                      # publish all zones (refuses on hard validation failures, exit 1)
uv run scatter.py --zone spawn_meadow  # publish only that zone (repeatable); other zones untouched
godot --headless --path ../.. --script $PWD/export_fields.gd   # after a publish
```

Inputs: `tools/terrain/out` (heightmap.npy, terrain_masks.npz, splat_0..2.png, splat.json),
`world/anchors/valley_anchors.json`, `world/routes/valley_routes.json`,
`world/recipes/valley_recipes.json`, `world/recipes/valley_habitats.json`,
`assets/nature/*/*.json` and `spruce_trees/models/variants.json` (library tree ids).
Missing assets are skipped and listed in the manifest, never fatal.

Sequence (plan 8.2): fields -> locked recipe members (+ reserves) -> trees per habitat
(variable-radius spacing, gaps, meadow groups) -> canopy raster -> props (rocks, logs, root
flares, shrubs, ferns, reeds) -> cliff dressing -> bank dressing -> groundcover density fields.

Modules: `common.py` (paths, hashing, noise, bilinear sampling = `ValleyTerrain.get_height`),
`assets.py`, `fields.py`, `routes.py`, `recipes.py`, `spatial.py` (footprints, exclusions,
spacing hash, zones), `candidates.py`, `trees.py`, `props.py`, `rockground.py`, `cliffs.py`, `banks.py`,
`bank_props.py`, `groundcover.py`, `binfmt.py`,
`generate.py` (pipeline), `validate.py`, `report.py`, `preview.py`.

### Determinism
- Revision = anchors `terrain_revision` + sha1 (10 hex) of the habitats JSON re-serialised with
  `json.dumps(indent=2)` without its `banks` section (= the file sha1 while the file is written that
  way and has no `banks`; keep it so), so tuning bank rules never re-seeds trees. Per-instance randomness is
  splitmix64 of (revision seed, zone hash, family hash, cell ix, iz, slot): one stream per
  family, so adding a prop family never moves trees. Noise fields are seeded by name only.
- Instance id = uint32 hash of (family, cell ix, iz, slot) (recipe members: recipe id, index).
- Same inputs -> byte-identical `.bin`, manifest and field PNGs (no timestamps; run time goes
  to `out/scatter_log.txt`). Every run also re-runs the pipeline in-process and compares digests.

### Outputs
- `world/generated/<zone>/<asset_id>.bin` (VPL1, little-endian): `b"VPL1"`, uint32 count, then
  32-byte records `f32 x, y, z, yaw, scale, tilt_x, tilt_z, u32 id`, sorted by id. Runtime basis
  `Rx(tilt_x) * Rz(tilt_z) * Ry(yaw) * scale`. Zone = first anchors zone containing the origin,
  else `fill`. Library tree ids load `res://spruce_trees/models/<id>.glb`.
- `world/generated/manifest.json`: revision, input sha1s, per zone/asset {count, file, sha1},
  locked recipe ids, skipped assets, warnings, field sha1s, validation summary.
- `out/fields/{ground,flowers,habitat,bank}.png` RGBA8 1024x1024, row 0 north, pixel (ix, iz) at
  world (ix - 511.5, iz - 511.5); exported to `res://world/generated/fields/*.res`:
  - ground: r grass_short, g grass_tall, b wear (core 1, shoulder ~0.5, painted paths ~0.6), a canopy / 1.5
  - flowers: r white, g pink, b yellow, a blue
  - habitat: r forest (mature 1, edge ~0.5), g rock exposure, b wetness, a fern density
  - bank (only with a habitats `banks` section; new file, no existing channel changed): r exposed
    soil/gravel (gravel character of inland banks and sea coast x (1 - smoothstep(2, 5 m, shore
    distance)): 1 at the water line, 0 by ~5 m inland; also > 0 on the shallow water side down to
    -2.5 m), g rock character (inland + coast, x band), b sedge character (inland, x band),
    a bank band (1 from -1.5 m in the water to 0.6 x width inland, 0 by width: 7 m inland, 8 m coast).
    Wetness (habitat.b) is unchanged.
- `out/scatter_report.md` (counts, diff added/moved/removed/preserved by id, untouched-zone sha1
  check, validation, overrides ids that no longer exist), `out/fields_preview.png`,
  `out/fields_zoom_spawn*.png` (spawn slice at 4 px/m), `out/fields_zoom_west_river_banks.png` (bank
  characters: gravel sand, rock grey, sedge green, coast paler; plain shore magenta; bank rocks white,
  reeds lime, shrubs cyan).
- `world/overrides/valley_overrides.json` (`{"remove": [], "move": {}, "add": []}`) is created if
  absent and never applied here (the runtime applies it).

### Rock grounding (`rockground.py`)
- Tilt: least-squares plane over the footprint grid, clamped to the asset's `max_tilt_deg`; burial
  and exposure are evaluated on the tilted base (`y - embed_depth * scale` along the tilted up axis).
- Boulders / rubble / shore rocks (fill): no footprint sample of the base above the terrain and
  exposure (share of bbox height above the terrain at the origin) >= 0.5, else the candidate is rejected.
- Shelves / cliff faces (fill): grounded by the front (+z, downhill) edge: front-bottom at most 0.1 m
  above the lowest front terrain, back may be buried; rejected when the residual terrain rise across
  the depth exceeds 0.85 (shelf) / 0.9 (cliff) x (bbox height - embed).
- Recipe rocks: same tilt and no-float cap (`min(ground rule - sink, no-float y)`), never rejected;
  exposure per member is listed in the manifest validation (`recipe_rock_members`).

- Props rules may set `rise_limit` (replaces 0.85 shelf / 0.9 cliff) and `max_tilt` (deg, overrides
  the asset's `max_tilt_deg`, capped at 20). Recipes keep the asset tilt.

### Cliff dressing (`cliffs.py`, habitats `cliff_dressing`)
Candidates where terrain `cliff` > 0.3 or slope > `min_slope_deg`, off water / route core / spawn /
reserves (not view corridors). Family by `assets` weights (corner weight x4 where downhill directions
spread > `corner_bend_deg` within 10 m), front (+z) downhill along a 3 m-smoothed gradient, scale
from `scale`, spacing by centre distance plus oriented-footprint overlap (x0.85) against every placed
rock, no trunk inside the footprint, front-edge grounding with the section's `rise_limit`,
`max_tilt`, `min_exposure`. `shelf_on_treads` then puts rock_shelf modules on `tread_slope_deg`
ground within `within_m_of_face` of a placed module. Placed last on own streams: no tree/prop moves.
Habitat `meadow_rock` (slope band near rock/scree) is an overlay weight outside the six-habitat
normalisation.

### Bank character (`banks.py`, `bank_props.py`, habitats `banks`, plan 7E/7F/7J)
- Field: every shore pixel (land next to water) gets a soft character from a seeded noise along the
  shore (`char_noise_m` plus `fine_mix` of a 0.3x finer noise, so the two banks of a narrow reach
  differ), shifted by shoreline curvature (`bend_bias`; outer bends = convex water outline -> gravel /
  rock end, inner bends -> sedge end) and band slope (`slope_bias` over `slope_bias_deg`). `classes`
  are bands of that value; values between them stay plain (open access, ~21 % of inland shore).
  Rock is forced at `rock_slope_deg` / `rock_exposure`; sedge fades on banks steeper than
  `sedge_max_slope_deg`. Band pixels take the character of their nearest shore pixel (`bank_*` /
  `coast_*` fields; the sea coast has no sedge). Overlay fields only: habitats are unchanged.
- Props (`banks.props`, file order, after cliff dressing, own streams `bank:<rule>`): density per
  100 m2 per character field (`fields`, optional `require` mask), variant `assets` weights, `cluster`
  [min, max] members within `cluster_radius_m`; leaders and members are moved across the shore to a
  hashed distance inside `shore_distance_m` (negative = in water), so the narrow strip fills along the
  water line. Only assets listed in `in_water` may stand in water, up to that depth (m, level - terrain
  at the origin); others keep >= 0.3 m from the water line. Spacing: rule (`spacing`, `footprint_k`
  share of summed footprint radii), shared solid hash (trunks, rocks, logs; bank rocks are added),
  same-family plants, cliff module footprints; route core/shoulder, painted paths, spawn, corridors and
  reserves as props. Rocks use `rockground` (`max_tilt`, exposure >= 0.5); `face: along_shore` lays long
  footprints (rubble) on the contour. Bank ids never reuse an existing instance id.
- Groundcover (`banks.groundcover`): grass_tall = max(field, sedge x `tall_near_water` (patchy) fading
  over `tall_falloff_m`); grass_short x (1 - `short_on_gravel_cut` x gravel).
- Validation: `banks` in the manifest (instances per character x zone, shore metres per character,
  worst in-water depth per rule/asset); a bank asset deeper than its `in_water` limit is a hard failure.

### Routes
`stones_on_turns`: bends > 25 deg over 8 m get a `turn_stones` band 1.5-3.5 m outside the core on the
outer side; `boulder_medium_*` / `rubble_cluster_*` are placed there (own stream) once those assets
exist. `roots` is not used by the generator; both flags and the detected turns are written to the
manifest `routes` section for the runtime.

### Validation
Hard (exit 1, nothing published): recipe members unaccounted, origins in water (except
shore rules and bank `in_water` assets), bank assets deeper than their `in_water` limit, tree trunks / rock footprints in the route core, spawn clear radius occupied,
fill rocks with exposure < 0.35 (cliff dressing: its `min_exposure`) or floating (tolerance 0.02 m, shelves/cliffs 0.1 m),
determinism self-check. Reported: rock exposure min/p10/median per family (fill, recipe),
rejected rock candidates by reason, floating recipe rocks, tree count outside 12k-25k.
