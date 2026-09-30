# Stylized short grass for Godot 4

One tuft and two wide patches, all built from the same two painted sprites.
Built/exported with Blender 4.0.2; import checked in headless Godot 4.4.1 (not rendered in a Godot viewport).

## Files
- `glb/grass_tuft.glb`      16 tris, visible grass ~1.5 m across (single sprite)
- `glb/grass_patch_M.glb`   60 tris, ~3 m across (5 sprites)
- `glb/grass_patch_L.glb`   96 tris, ~3.8 m across (8 sprites)
- `textures/grass_side.png` (1024x256, blade strip) and `grass_top.png` (1024x1024, top-down ground layer)
- Blade height ~0.3 m in all three. Origin = ground level. Bounding boxes are larger than the visible grass
  (the square ground card has empty corners): about 2.1 / 3.3 / 4.2 m.

## How it works
Sprite = 1 top-down ground card (z = 3.5 cm and up, staggered per sprite) + 2-3 crossed low vertical cards.
Blade size is constant; a wider area means more sprites (random rotation/scale), never a stretched texture.
Cards are two single-sided quads back to back with UP normals, so they light like the terrain and avoid
Godot's flipped normals on double-sided materials.

## Godot setup
1. Materials import as Alpha Scissor 0.5, cull back, roughness 1.
2. **Set `cast_shadow = Off` on grass.** The vertical cards otherwise throw dark creases onto the ground layer.
3. Scatter with `MultiMeshInstance3D` (random Y rotation, scale 0.9-1.15). Overlap patches ~20-30 % to merge edges.
4. Use `visibility_range_end` (and optionally fade) for distant patches; overdraw, not triangles, is the cost.
5. Assumes fairly flat ground: the ground layer is a flat card 3.5-12 cm above the origin.
6. Each GLB embeds its own copy of the two PNGs. To avoid duplicate VRAM, re-point all materials to one shared pair.

## Rebuild
```
python3 scripts/gen_grass_textures.py tex
blender -b -P scripts/make_grass.py -- --tex tex --out out low:14 mid:40 top:72
```
(`--shadows` renders previews with shadow casting on.) Blender 4.2+: `blend_method` is deprecated;
check the material imports as Alpha Scissor in Godot and set it manually if not.
