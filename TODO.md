# Forest Walk TODO

## Phase 1 — base prototype (done)
- [x] Godot 4.7.2, terrain, forest scatter, player, basic env
- [ ] User manual play test

## Phase 2 — rendering style (spec: fantasy-game-style-3d-rendering-guide v1.2)
Scope: rendering, atmosphere, lighting, camera only. No new assets (user provides).
- [x] Input map (camera-relative move, Q/E rotate, wheel zoom, 1–3 presets) + shader globals + noise textures
- [x] A: painted-light world shader (bands, brush, tinted shadows, flat shading, cloud shadows, occlusion dither) on terrain/forest materials
- [x] B: tactical camera rig (57°, fov 32), camera-relative player, atmosphere presets (dawn/midday/evening), volumetric fog + shafts, ground fog, AgX, glow, grade LUT, particles
- [x] Review + verify (windowed movie run for shader errors, screenshots per preset)

## Phase 3 — navigation
- [x] Mouse turns player (captured cursor), WASD moves/strafes relative to facing, arrows/Q/E turn, camera yaw follows player
- [x] Mouse Y tilts camera pitch 20–80° (default 57), terrain-only camera clearance ray (terrain on layer 3)
- [ ] User test mouse feel (yaw 0.003 rad/px, pitch 0.17 deg/px)

## Phase 4 — assets, flat forest, midday, Apple Silicon perf
- [x] Spruce GLBs (res://spruce_trees, Forward+ set) as per-tree instances: culling + import LODs + visibility range; shared double-sided painted shader, saturation 0.7
- [x] character.glb as player model (rotated 180°, scaled 1.8, feet at y=0)
- [x] Mostly flat terrain (amplitude 2 m), jittered-grid forest (~1960 trees) with noise glades
- [x] Terrain 8x8 chunks with LODs + continuous normals; bushes/rocks/grass chunked MultiMesh + visibility ranges
- [x] Midday default, tuned toward spec palette (mean luma 114 vs 100; gap = no painted ground/path assets yet)
- [x] Perf: Jolt physics, volumetric fog 48^3, SSAO low, 2 shadow splits, no PCSS; upscaling tested and dropped (GPU ~2.7 ms @1080p on M4 Pro via Vulkan timing)
- [ ] character.glb is 97.7k tris (spec budget 8–15k), static (no rig/animations)

- [x] Zoom-in blends to over-the-shoulder view: below 20 m, pitch x0.25, FOV 32 to 70, look at head + 4 m ahead; min distance 2.5 m, multiplicative zoom
- [x] Close-up pitch keypoints (distance m, pitch deg): 20→57, 10→20, 8→14, 2.5→8; scaled by mouse pitch / 57
- [x] Fix full-screen dither when a tree touches the camera (near_fade 2–4 m full discard)
- [ ] Check world edge (terrain ends at +-128 m) visibility in close-up view toward walls

## Phase 5 — sunny painted lighting, ground, grass (plan: ~/.claude/plans/act-as-senior-game-rippling-giraffe.md)
Painted style kept; brighter + sunnier.
- [x] Debug args `--cam=dist,pitch`, `--perf` (GPU ms needs `--rendering-driver vulkan`; Metal reports 0)
- [x] Canopy mask (forest.gd) as global `canopy_mask`; prism grass removed
- [x] world.gdshaderinc split: lighting in painted_light.gdshaderinc
- [x] Painted ground: ground.gdshaderinc palette (meadow/dry/moss/litter/dirt) + terrain.gdshader with optional per-layer textures (use_textures, anti-tiling)
- [x] Procedural grass: grass.gd + grass.gdshader (clumps of 9 blades, wind, player bend, camera + player-radius shrink, `grass_clear` group)
- [x] Sharp flat shadows: thresholded ATTENUATION + cloud mask in light(); SSAO off; no PCSS
- [x] Midday: sky ambient, cool shadow tint, sun 1.8, exposure 0.85, AgX contrast 1.35, saturation 1.1, sun scatter + aerial perspective
- [x] Focus fog: camera quad (focus_fog.gdshader) — clear 12 m around player, screen-mip blur 10–35 m, white haze to 40 m; VRS unsupported on Metal/MoltenVK
- [x] Perspective tactical camera: FOV 55, distance 26 (max 42)
- [x] campfire.glb at (1.5, 0, -3), scale 1.3, cylinder collider, grass cleared
- [ ] GPU ~9.3 ms @1080p (target ~5): focus fog ~2 ms, grass ~0.8 ms; wider FOV adds rest. Options: MetalFX upscaling, cheaper blur
- [ ] Dawn/evening only compat-checked (evening saturated, sat 146)
- [ ] Campfire has no fire FX (light/embers) — ask user
- [ ] User to supply ground textures (tex_meadow/dry/moss/litter/dirt on terrain material)

## Open / follow-up
- [ ] Faint dotted light line on terrain near tree shadow edges (seen midday) — investigate (shadow bias / SSAO)
- [ ] Midday reads pale under AgX; tune once real assets land
- [x] Occlusion dither visually confirmed (low-pitch frame)
- [ ] Light shafts not yet visually confirmed (sparse placeholder trees)
- [ ] Quality presets (High/Medium/Low volumetrics) per spec
- [ ] Player readability: rim light / selection ring (spec, not selected yet)
- [ ] Headless exit warning: 1 leaked dummy shader RID (harmless)

## Phase 6 — rendering assessment plan (art-directed image, "painted surfaces, real air")
Decisions (2026-09-30): focus fog off by default (debug toggle); sun cast shadows stay sharp, cloud/band edges softer; campfire FX = particles + OmniLight (no meshes); no new texture assets (slots only).
- [x] P0 debug toggles (F1 focus fog, F2 fog, F3 volumetrics, F4 grade, F5 clouds, F6 SSAO, F7 glow) + `--off=`/`--on=` args; `--perf` avg/p50/p95/p99/max + driver/method/size
- [x] P0 painted_light: sun-only shadow threshold, smooth local-light falloff (wider bands), cool shadow fill once from sun luminance, band_softness 0.08, cloud edge 0.5–0.6
- [x] P0 color workflow: ground palette = sRGB colours in `materials/world_style.tres` (WorldStyle), pushed as linear globals; terrain, grass, rock moss share it. Colour-type globals reach shaders unconverted (checked Godot source)
- [x] P1 ground: persistent `materials/terrain.tres`, explicit `has_*` texture flags, RG `ground_mask` (r canopy summed: litter only in dense stands; g wear around `grass_clear` nodes = camp dirt + trampled ring), dry = accent, quieter fine mottle + stroke term
- [x] P1 grass: tip_dry 0.12, tip_shade 1.05, root 0.9, per-clump tint from slow noise field, no baseline density (quiet ground), wear clears grass, player fade 48–64 m, ground colour sampled per vertex
- [x] P1 trees/materials: canopy normal blend 0.55, foliage backlight 0.35 (PAINTED_BACKLIGHT), per-tree variation 0.12, foliage/bark from vertex colour, rock moss tops, bush colour linearised
- [x] P1 atmosphere: presets retuned (dawn cool/peach, midday rich green, evening cool + fire anchor), depth fog (per-preset begin/end), Mist node = ellipsoid FogVolume pockets in hollows (replaces map-wide GroundFog)
- [x] P1 campfire FX scene (flame shader, embers, smoke, flicker OmniLight), `fire_energy` per preset (0.5 / 0.25 / 1.0)
- [x] P2 occlusion: IGN coverage instead of 4x4 Bayer, ghost 0, no discard in shadow pass (IN_SHADOW_PASS), CAMERA_POSITION_WORLD
- [x] Soft-disc textures on dust/firefly particles (were squares)
- [x] Verify: 18-view set captured (scratchpad v2), perf vulkan 1080p tactical: gpu avg 6.60 / p95 10.49 ms; with focus fog 7.90 / 13.30 ms
- [ ] Character is a dark silhouette in evening back views (fire in front); decide rim/fill approach with user
- [ ] Large dry-grass patches still visible at midday zoomed out (macro noise); tune if unwanted
- [ ] Tree visibility range (110 m) vs depth fog: check popping while walking
- [ ] Normal-map slots for terrain need tangents or world-space projection — deferred until user textures + colour pass approved
- [ ] Quality presets (volumetrics/shadows) — not started
- [ ] In-motion check: grass fade edge, occlusion noise shimmer, flame wobble, mist stability

## Phase 6 — valley scenery (tools/terrain -> scenes/valley.tscn)
- [x] Terrain generated from topo/painted reference maps (tools/terrain: gen_heightmap.py, gen_splat.py, build_blend.py, build.sh)
- [x] Painted splat layers (water, rock, sand, scree, dirt, forest floor, dry grass, grass); river banks without levees
- [x] Godot import: export_godot.gd -> res://terrains/valley/*.res; valley_terrain.gd (GPU-displaced 64 m chunks, HeightMapShape3D, walls)
- [x] valley_forest.gd: ~18.5k spruces, MultiMesh per chunk/variant, trunk collision via PhysicsServer3D
- [x] valley_grass.gd + grass_card.gdshader: ~40k card patches from res://grass, palette recolour, hue/noise variation, wind
- [ ] User play test of scenes/valley.tscn (not main scene yet)
- [ ] No water surface (painted beds only); player can walk on sea/river beds
- [ ] Perf pass with --perf on valley (trees + grass overdraw)

## Phase 7 — version 2 review fixes (review of b27da72, 2026-09-30)
Scope: correctness, visibility, readability. Cameras/layout/terrain shape untouched; no new assets; sun shadows stay sharp.
- [x] R1 wear noise gated by wear support (zero mask = zero wear); GPU-checked with ground debug view (F12 / `--ground_debug=1..6`: wear, trampled, natural dry, final dry, litter, dirt). Large yellow patches = natural dry macro field, not wear
- [x] R2 world normal via MODEL_NORMAL_MATRIX (world + terrain shaders); moss uses facet normal when flat-shaded, interpolated normal otherwise
- [x] R3 per-tree blocker fade (tree_occluder.gd: segment vs trunk-axis test, enter/exit hysteresis, 0.25 s hold, fade out 0.2 s / in 0.35 s, `occluder_fade` instance uniform); endpoint fully removed, shadows kept; ~25-55 us/frame. Legacy spatial path kept for A/B (`--occ=spatial`, ring narrowed to 0.85r..r); `--occ=off` or F11
- [x] R4 AA explicit: MSAA 2x default (`--msaa=0|2|4|8`), no FXAA/TAA; RENDER config line logged at start. Shadow stair-steps are atlas resolution, not filtering (filter quality 4 = no change): directional shadow atlas 8192 (~+96 MB VRAM)
- [x] R5 hero: character.glb material is metallic 1.0 on every texel (no diffuse, black silhouette) — player.gd overrides to dielectric at runtime, textures untouched. No extra fill/rim needed so far
- [x] R6 painted_light keeps Godot's shadow distance fade (threshold released over `sun_shadow_fade`, pushed by atmosphere.gd); sun fade_start 0.7 (42-60 m); trees 140 m + 20 m margin (no measurable GPU cost at tactical)
- [x] R8 grass: fragment NORMAL shared by both faces (Godot flipped back-face normals downward = dark pickets)
- [x] Debug isolation: F4 lut, F5 saturation (grade split; `--off=grade` = both), F9 mist, F10 backlight, F11 occlusion, F12 ground debug; DEBUG line printed at start
- [x] Mist exclusion by ellipsoid reach (placement changed, still seeded); campfire `burning` (extinguish) vs `energy` (intensity only); warning if >1 DirectionalLight3D (fill owner)
- [x] Player spawns on the ground (was 2 m drop)
- [x] Capture tooling: tools/capture (views.tsv, capture.sh + manifest, walk.sh mp4, contact_sheet.py)
- [ ] Perf: 6.60 ms v2 figure not reproducible today; clean HEAD 7.8-9.5 ms vs working tree 9.2-9.4 ms (vulkan 1080p tactical, noisy ±1 ms)
- [ ] Hero reads slate blue in midday sun (albedo is what it is); decide if cloth specular/tint wanted
- [ ] Preset-transition capture at campfire (needs scripted preset switch)
- [ ] R7 ground grouping / dry contrast; smoke palette; foliage mask metadata; fire shadow; quality presets — deferred
