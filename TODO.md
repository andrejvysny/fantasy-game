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
