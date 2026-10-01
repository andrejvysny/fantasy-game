# FG-00 baseline (FG-SPEC-1.1 §8 FG-00)

Captured 2026-10-01. No game script/scene/resource/project.godot changed. All numbers are **HOST (macOS) evidence**, not iPad/device.

## 1. Environment

| Item | Value |
|---|---|
| Repo / branch / HEAD | fantasy-game / main / `ce478c4` (full `ce478c479b101ad21fa98bf5bbb5690fdf9997d5`), tree clean before run |
| Godot | 4.7.2.stable.official.ed1daf0bf (`/opt/homebrew/bin/godot`) |
| OS / GPU | macOS 26.6.2 (Darwin 25.6.0) / Apple M4 Pro, 20 GPU cores, Metal 4 |
| Main scene | `res://scenes/valley.tscn` (config name "Forest Walk") |
| Renderer | features `4.7`, `Forward Plus` (no `rendering_method` override); default driver on macOS = metal |
| Physics | `3d/physics_engine="Jolt Physics"` |
| Render settings | msaa_3d=1 (2x), SSAA/TAA off, dir shadow 8192, SSAO quality 1, volumetric fog 48x48 (`volume_size/depth`) |
| Inputs | move_*/turn_*/zoom_*, preset_dawn/midday/evening |

Note: `manifest.txt` shows `dirty=yes` only because the evidence dir itself was untracked at capture time.

## 2. Import / asset check

| Check | Command | Result |
|---|---|---|
| Headless import | `godot --headless --path . --import` (300 s hard timeout, stdin /dev/null) | rc 0; 0 warnings, 1 ERROR line = exit-time `3 RID allocations of type ...DummyShader were leaked` (headless dummy renderer noise, pre-existing); no script/shader/resource errors |
| Asset check | `godot --headless --path . --script res://tools/environment/asset_check.gd` | rc 0; `asset_check: 24 assets, 0 failures` |

Logs: `docs/evidence/fg-00/logs/{import,asset_check}.log`.

## 3. Deterministic valley captures

`SCENE=res://scenes/valley.tscn VIEWS=views_valley.tsv zsh tools/capture/capture.sh docs/evidence/fg-00/captures` (movie mode, 1152x648, fixed 30 fps, frame 89, driver metal/forward_plus, msaa 2). Windowed run on desktop.

- Result: 21/21 views rendered (TSV has 21 rows, README says 16; README is stale), 0 MISSING, 0 ERROR/SHADER ERROR lines in any view log.
- Seeds: forest 2024, mist 99. Placements: `20600 instances, 35 assets, overrides 0/0/0` (revision `tools/terrain/out/heightmap.f32 @ dfb2ce3 + habitats 6be51cf4bf`).
- Non-deterministic per tool README: GPU particle seeds (dust, fireflies, fire), campfire flicker.
- Files: `docs/evidence/fg-00/captures/*.png` (21), `00_contact_sheet.png`, `manifest.txt`, `logs/`. Evidence total ~16 MB.

## 4. Perf (HOST macOS, M4 Pro)

`godot --path . res://scenes/valley.tscn --resolution 1152x648 --rendering-driver <drv> --disable-vsync --quit-after 660 -- --preset=1 --perf --pos=.. --yaw=..` (per `.claude/agent-memory/impl-careful/gpu-timing-mac.md`: vsync'd GPU times are DVFS-noisy). 660 frames, first 60 warmup, 600 sampled. Pre-run check: no other godot process. Ms values are `viewport_get_measured_render_time_*` from main.gd.

| View | Driver | GPU ms avg / p50 / p95 / p99 / max | CPU render ms p50 / p95 | Peak RSS |
|---|---|---|---|---|
| 01_spawn_meadow (-22,-145 yaw 32) | vulkan | 5.87 / 5.83 / 6.06 / 6.16 / 6.34 | 0.18 / 0.27 | 785 MB |
| 03_upper_lake (-55,-300 yaw 87) | vulkan | 4.89 / 4.86 / 5.08 / 5.18 / 5.29 | 0.16 / 0.23 | 730 MB |
| 13_forest (40,-200 yaw 34) | vulkan | 6.17 / 6.14 / 6.33 / 6.43 / 6.52 | 0.19 / 0.27 | 729 MB |
| 01_spawn_meadow | metal | GPU timing reads 0.00 (not supported by metal driver here) | 0.18 / 0.25 | 473 MB |

Peak RSS from `/usr/bin/time -l` (max over wrapper + godot child, i.e. effectively the whole process incl. startup/world gen), not a Godot-reported number. Tree occluder cost 4-22 us avg. Logs: `docs/evidence/fg-00/perf/`.

## 5. Atmosphere dependency map

### 5.1 `scripts/atmosphere.gd` node requirements (valley.tscn wiring)

| Export | Valley path | Required? | Needs / used for |
|---|---|---|---|
| `environment_path` | `../WorldEnvironment` | **required** (`get_node`) | `.environment` with `sky.sky_material` (a `ShaderMaterial` using `materials/sky.gdshader`, params `sky_top, sky_horizon, sun_halo_*, ground_horizon, ground_bottom, cloud_color_lit/shade`); ssao/glow/fog/adjustment props written; color-correction GradientTexture1D assigned |
| `sun_path` | `../Sun` | **required** | `DirectionalLight3D` (energy/color/shadow; `directional_shadow_max_distance`+`fade_start` pushed to global `sun_shadow_fade`); warns if >1 DirectionalLight3D in tree |
| `ground_fog_path` | `../Mist` | **required** | Node3D exposing `material` (FogMaterial) + `visible` (valley: `mist.gd` node; forest: FogVolume) |
| `dust_path` | `../Motes/Dust` | **required** (`get_node`; crash if absent) | GPUParticles3D; parent (`Motes`) is moved to player position each frame, so parent must be a Node3D |
| `fireflies_path` | `../Motes/Fireflies` | **required** | GPUParticles3D, emission toggled by preset |
| `player_path` | `../Player` | optional | `global_position` for Motes; child `Fill` (Light3D) tinted/energy by preset |
| `focus_fog_path` | `../CameraRig/Camera/FocusFog` | optional | `.visible` for debug toggle |
| `campfire_path` | unset in valley | optional | node with `energy` property |
| `occluder_path` | `../TreeOccluder` | optional | `enabled` property + `set_enabled()` |
| `presets` | valley_dawn / midday / valley_evening `.tres` | required array (non-empty) | `LightingPreset` resources (`scripts/lighting_preset.gd`); `start_index=1` |

Cmdline user args consumed: `--preset= --off= --on= --wind= --ground_debug=`. Actions used: `preset_dawn/midday/evening` (project input map), F1-F12 debug keys.

### 5.2 Other valley scene scripts

| Node | Script | Dependencies |
|---|---|---|
| root `Valley` | `main.gd` | children `$Player`, `$Terrain` (`get_height(x,z)`), `$CameraRig` (`snap()`), optional `Forest/Grass/Mist` (seed log); preloads `materials/world_style.tres`; args `--pos --yaw --msaa --walk --turn --perf` |
| Terrain | `valley_terrain.gd` | `terrains/valley/` data, `materials/valley_terrain.tres`, `world/generated/fields/` (fields, `_stub_*` git-ignored); builds chunk meshes + collision + walls itself (custom, no Terrain3D) |
| Water / Falls / Forest / Props / Grass | `valley_*.gd` | `terrain_path=../Terrain` (`get_node`, required) |
| Forest | `valley_forest.gd` | `placement_mode="generated"` -> `ValleyPlacements.load` (`world/generated/manifest.json`, VPL1 binaries, `world/overrides/valley_overrides.json`); each tree asset scene needs children `Tree` (MeshInstance3D) and `TrunkCollision/<CollisionShape3D>`; legacy mode = old noise placement |
| Groundcover | `valley_groundcover.gd` | `terrain_path`, `camera_path=../CameraRig/Camera` (optional), 7 `groundcover_layer` `.tres` |
| TreeOccluder | `tree_occluder.gd` | `forest_path`, `camera_path`, `player_path` all required; reads `Forest/Trees/*/Tree` |
| Mist | `mist.gd` | `terrain_path` |
| CameraRig | `camera_rig.gd` | `target_path=../Player`, child `Camera`, `Camera/FocusFog` mesh (`materials/focus_fog.gdshader`) |
| Player | `player.gd` | `$Model`, `Fill` OmniLight; writes global `player_position` every physics tick |

Side-effect to note: `ValleyPlacements._apply_overrides` **creates** `world/overrides/valley_overrides.json` if missing (file exists now; no change this run).

### 5.3 Shader globals (project.godot `[shader_globals]`) and users

| Global | Type | Written at runtime by | Read by |
|---|---|---|---|
| `player_position` | vec3 | player.gd | painted_light.gdshaderinc, focus_fog.gdshader |
| `cloud_offset` | vec2 | atmosphere.gd | painted_light, sky, water |
| `cloud_shadow_strength` | float | atmosphere.gd | painted_light, water |
| `shadow_tint` | color | atmosphere.gd (preset); showroom.gd | painted_light |
| `focus_fog_color` | color | atmosphere.gd | focus_fog |
| `sun_shadow_fade` | vec2 | atmosphere.gd (from Sun shadow range) | painted_light |
| `backlight_scale` | float | atmosphere.gd | painted_light |
| `ground_debug` | int | atmosphere.gd | ground.gdshaderinc |
| `wind` | vec4 | atmosphere.gd | wind.gdshaderinc (all vegetation) |
| `ground_meadow/dry/moss/litter/dirt` | color | `world_style.gd` `apply()` (srgb->linear) | ground.gdshaderinc (`ground_moss` also world.gdshaderinc) |
| `ground_mask` | sampler2D | legacy `forest.gd` only (not valley_forest) | ground.gdshaderinc; default empty in project.godot |
| `brush_noise`, `cloud_noise` | sampler2D | static (`materials/*.tres`) | painted_light, sky, water |

### 5.4 What a separate Terrain3D preview scene must provide

- Nodes: `WorldEnvironment` (Environment + sky ShaderMaterial on `sky.gdshader`), one `DirectionalLight3D` (only one), a Node3D with `material` FogMaterial + visibility (Mist substitute, or reuse `mist.gd` with a `get_height`-capable terrain node), `Motes/Dust` + `Motes/Fireflies` GPUParticles3D under a Node3D; wire the 5 required export paths. Optional: Player (with `Fill` light) for `player_position`, FocusFog under Camera, TreeOccluder.
- Resources: >=1 `LightingPreset` (e.g. valley_dawn/midday/evening).
- Autoload/global state: `WorldStyle.apply()` (e.g. `materials/world_style.tres`) must run to set ground colors; `[shader_globals]` already in project.godot apply to any scene in this project.
- Materials: Terrain3D default shader will not read these globals; for matching look it needs an override shader including `painted_light.gdshaderinc`/`ground.gdshaderinc`, and `player_position` must be set by something other than player.gd if no Player exists.
- Terrain API gap: valley scripts call `get_height(x, z)` on a `terrain_path` node; Terrain3D exposes `data.get_height(Vector3)`, so an adapter is needed if valley_* nodes are reused.

## 6. Integration destinations (verified, nothing created)

| Path | Exists | Collision |
|---|---|---|
| `scenes/integration/` | no | none (scenes/ has camera_rig, campfire_fx, main, player, showroom, valley) |
| `painted_worlds/` | no | none |
| `assets/library/` | no (`assets/` holds only `nature/`) | none; `git check-ignore assets/library` -> not ignored yet |
| `integration/` | no | none (`docs/integration/` is the doc location, distinct) |
| `addons/` | no | none |

`.gitignore` currently: `.godot/ .DS_Store screenshots/*.zip __pycache__/ *.blend1 tools/environment/out/ world/generated/fields/_stub_* TODO.md`. Lines needed later: `assets/library/` (spec: git-ignored library), and, if Terrain3D binaries or heavy preview data are not to be tracked, entries decided at integration time. Do not ignore `addons/` wholesale if the plugin is to be committed (decision for the lead).

## 7. Not run / caveats

- Nothing NOT RUN. Metal driver GPU timing unavailable (0.00); use vulkan numbers.
- Perf numbers are single runs (600 frames each) on an M4 Pro desktop with vsync disabled; not representative of iPad.
- `tools/capture/README.md` says 16 views; TSV has 21.
