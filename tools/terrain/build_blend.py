"""Build out/terrain.blend from out/heightmap.npy (run gen_heightmap.py first).

    Blender -b -P build_blend.py -- [--render] [--mesh-res 1024]

Scene layout:
  Terrain            Terrain (flat UV grid, Terrain_Painted splat material) + Terrain_Displace fed by
                     Terrain_HeightTex -> out/heightmap.exr (float meters). Regenerating the
                     heightmap and reloading the image updates the terrain non-destructively.
  Terrain_Preview    ortho top camera + oblique cameras used for clay previews.
  Terrain_Reference  image empties of the two reference images (hidden).
"""
import json
import math
import sys
from pathlib import Path

import bpy
import numpy as np
from mathutils import Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from terrain_material import painted_material  # noqa: E402
OUT = HERE / "out"
ARGS = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []

# name: (camera location, look-at target, lens mm); world meters, +Y = north
CAMERAS = {
    "Cam_Oblique_S": ((0, -980, 620), (0, -40, 20), 32),
    "Cam_Oblique_SE": ((820, -820, 520), (40, 20, 20), 30),
    "Cam_Oblique_SW": ((-820, -780, 480), (0, 40, 20), 30),
    "Cam_Oblique_N": ((-100, 900, 560), (0, -20, 20), 32),
    "Cam_NE_Canyon": ((150, 40, 170), (350, 320, 60), 30),
    "Cam_E_Butte": ((60, -250, 110), (300, 0, 40), 28),
    "Cam_S_Coast": ((-120, -780, 130), (-120, -330, 15), 30),
}


def reset_scene() -> bpy.types.Scene:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0
    return scene


def collection(scene, name: str) -> bpy.types.Collection:
    col = bpy.data.collections.new(name)
    scene.collection.children.link(col)
    return col


def write_exr(h: np.ndarray) -> bpy.types.Image:
    res = h.shape[0]
    tmp = bpy.data.images.new("tmp_height", res, res, float_buffer=True, is_data=True)
    rgba = np.repeat(np.flipud(h)[..., None], 4, axis=2)  # Blender images start bottom-left
    rgba[..., 3] = 1.0
    tmp.pixels.foreach_set(rgba.astype(np.float32).ravel())
    path = OUT / "heightmap.exr"
    tmp.filepath_raw = str(path)
    tmp.file_format = "OPEN_EXR"
    tmp.save()
    bpy.data.images.remove(tmp)
    img = bpy.data.images.load(str(path))
    img.name = "Terrain_Heightmap"
    img.colorspace_settings.name = "Non-Color"
    return img


def grid_mesh(name: str, n: int, size: float) -> bpy.types.Mesh:
    """n x n vertex grid centered on origin, spacing size/n, UVs hit heightmap pixel centers."""
    step = size / n
    ax = (np.arange(n) - (n - 1) / 2) * step
    xx, yy = np.meshgrid(ax, ax)
    co = np.stack([xx, yy, np.zeros_like(xx)], -1).reshape(-1, 3)
    i = np.arange(n - 1)
    a = (i[None, :] + i[:, None] * n).ravel()
    quads = np.stack([a, a + 1, a + n + 1, a + n], -1)
    me = bpy.data.meshes.new(name)
    me.vertices.add(len(co))
    me.vertices.foreach_set("co", co.astype(np.float32).ravel())
    me.loops.add(quads.size)
    me.loops.foreach_set("vertex_index", quads.astype(np.int32).ravel())
    me.polygons.add(len(quads))
    me.polygons.foreach_set("loop_start", np.arange(0, quads.size, 4, dtype=np.int32))
    uv_axis = (np.arange(n) + 0.5) / n
    uvx, uvy = np.meshgrid(uv_axis, uv_axis)
    vuv = np.stack([uvx, uvy], -1).reshape(-1, 2)
    uv = me.uv_layers.new(name="UVMap")
    uv.data.foreach_set("uv", vuv[quads.ravel()].astype(np.float32).ravel())
    me.polygons.foreach_set("use_smooth", np.ones(len(quads), bool))
    me.update(calc_edges=True)
    me.validate()
    return me


def clay_material() -> bpy.types.Material:
    mat = bpy.data.materials.new("Terrain_Clay")
    mat.diffuse_color = (0.62, 0.6, 0.57, 1.0)
    bsdf = mat.node_tree.nodes.get("Principled BSDF") if mat.node_tree else None
    if bsdf:
        bsdf.inputs["Base Color"].default_value = (0.62, 0.6, 0.57, 1.0)
        bsdf.inputs["Roughness"].default_value = 0.9
    return mat


def build_terrain(col, img, meta: dict, mesh_res: int) -> bpy.types.Object:
    me = grid_mesh("Terrain_Mesh", mesh_res, meta["size_m"])
    painted = (OUT / "splat.json").exists()
    me.materials.append(painted_material(OUT) if painted else clay_material())
    obj = bpy.data.objects.new("Terrain", me)
    col.objects.link(obj)
    tex = bpy.data.textures.new("Terrain_HeightTex", type="IMAGE")
    tex.image = img
    tex.use_interpolation = True
    tex.use_clamp = False  # keep float meters above 1.0
    tex.extension = "EXTEND"
    mod = obj.modifiers.new("Terrain_Displace", "DISPLACE")
    mod.texture = tex
    mod.texture_coords = "UV"
    mod.uv_layer = "UVMap"
    mod.direction = "Z"
    mod.space = "LOCAL"
    mod.mid_level = 0.0
    mod.strength = 1.0  # heightmap is already in meters
    obj["heightmap"] = "//heightmap.exr"
    obj["regenerate"] = "tools/terrain/build.sh"
    obj["sea_level_m"] = 0.0
    return obj


def add_reference(col, name: str, path: Path, size: float, z: float) -> None:
    img = bpy.data.images.load(str(path))
    img.name = name
    emp = bpy.data.objects.new(name, None)
    emp.empty_display_type = "IMAGE"
    emp.data = img
    emp.empty_display_size = size
    emp.location = (0, 0, z)
    emp.color[3] = 0.6
    emp.use_empty_image_alpha = True
    col.objects.link(emp)
    emp.hide_render = True


def look_at(obj, target) -> None:
    d = Vector(target) - obj.location
    obj.rotation_euler = d.to_track_quat("-Z", "Y").to_euler()


def add_cameras(col, size: float) -> dict:
    cams = {}
    top = bpy.data.cameras.new("Cam_Top")
    top.type = "ORTHO"
    top.ortho_scale = size
    top.clip_end = 3000
    o = bpy.data.objects.new("Cam_Top", top)
    o.location = (0, 0, 600)
    col.objects.link(o)
    cams["Cam_Top"] = o
    for name, (loc, tgt, lens) in CAMERAS.items():
        cd = bpy.data.cameras.new(name)
        cd.lens = lens
        cd.clip_end = 5000
        o = bpy.data.objects.new(name, cd)
        o.location = loc
        look_at(o, tgt)
        col.objects.link(o)
        cams[name] = o
    return cams


def setup_render(scene) -> None:
    scene.render.engine = "BLENDER_WORKBENCH"
    sh = scene.display.shading
    sh.light = "STUDIO"
    sh.color_type = "SINGLE"
    sh.single_color = (0.78, 0.76, 0.72)
    sh.show_shadows = True
    sh.shadow_intensity = 0.55
    sh.show_cavity = True
    sh.cavity_type = "WORLD"
    scene.display.light_direction = (-0.55, -0.45, 0.70)  # low sun from the south-west
    scene.render.film_transparent = False
    world = bpy.data.worlds.new("Preview_World")
    world.color = (0.55, 0.6, 0.66)
    if world.node_tree is None:  # Blender < 5 needs node trees enabled explicitly
        world.use_nodes = True
    bg = world.node_tree.nodes.get("Background")
    bg.inputs["Color"].default_value = (0.42, 0.52, 0.66, 1.0)
    bg.inputs["Strength"].default_value = 0.9
    scene.world = world
    scene.render.image_settings.file_format = "PNG"
    scene.view_settings.view_transform = "Standard"  # keep the painted palette as authored
    scene.eevee.taa_render_samples = 32
    scene.render.engine = "BLENDER_EEVEE"  # F12 renders the painted terrain; clay uses Workbench


def add_sun(col) -> None:
    sun = bpy.data.lights.new("Preview_Sun", "SUN")
    sun.energy = 3.2
    sun.angle = 0.03  # crisp shadows, matching the game's painted look
    o = bpy.data.objects.new("Preview_Sun", sun)
    o.location = (-650, 450, 600)  # from the north-west, like the painted map
    look_at(o, (0, 0, 0))
    col.objects.link(o)


def setup_viewports() -> None:
    """Solid clay view, 5 km clip, framed oblique from the south (applies when opened in the UI)."""
    from mathutils import Euler
    for screen in bpy.data.screens:
        for area in screen.areas:
            if area.type != "VIEW_3D":
                continue
            for sp in area.spaces:
                if sp.type != "VIEW_3D":
                    continue
                sp.clip_start, sp.clip_end = 0.5, 5000
                sp.shading.type = "MATERIAL"
                sp.shading.use_scene_lights = True
                sp.shading.use_scene_world = True
                sp.shading.show_cavity = True
                sp.shading.show_shadows = True
                r3d = sp.region_3d
                r3d.view_perspective = "PERSP"
                r3d.view_location = (0, 0, 30)
                r3d.view_distance = 1500
                r3d.view_rotation = Euler((math.radians(55), 0, 0)).to_quaternion()


def render_previews(scene, cams: dict, engine: str, folder: str) -> None:
    prev = OUT / folder
    prev.mkdir(exist_ok=True)
    scene.render.engine = engine
    for name, cam in cams.items():
        scene.camera = cam
        top = name == "Cam_Top"
        scene.render.resolution_x = 1400 if top else 1600
        scene.render.resolution_y = 1400 if top else 1000
        scene.render.filepath = str(prev / f"{name}.png")
        bpy.ops.render.render(write_still=True)
        print("rendered", name)


def main() -> None:
    mesh_res = int(ARGS[ARGS.index("--mesh-res") + 1]) if "--mesh-res" in ARGS else 1024
    meta = json.loads((OUT / "heightmap.json").read_text())
    h = np.load(OUT / "heightmap.npy")
    scene = reset_scene()
    img = write_exr(h)
    terrain = build_terrain(collection(scene, "Terrain"), img, meta, mesh_res)
    preview = collection(scene, "Terrain_Preview")
    cams = add_cameras(preview, meta["size_m"])
    add_sun(preview)
    ref = collection(scene, "Terrain_Reference")
    add_reference(ref, "Ref_Topo", HERE / "ref/topo.png", meta["size_m"], meta["max_m"] + 5)
    add_reference(ref, "Ref_Painted", HERE / "ref/painted.png", meta["size_m"], meta["max_m"] + 6)
    for o in ref.objects:
        o.hide_set(True)
        o.hide_viewport = True
    setup_render(scene)
    setup_viewports()
    scene.camera = cams["Cam_Oblique_S"]
    ev = terrain.evaluated_get(bpy.context.evaluated_depsgraph_get())
    zs = [v.co.z for v in ev.data.vertices]
    print(f"evaluated z range {min(zs):.2f} .. {max(zs):.2f} (heightmap {meta['min_m']:.2f} .. {meta['max_m']:.2f})")
    path = OUT / "terrain.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(path))
    bpy.ops.file.make_paths_relative()
    bpy.ops.wm.save_mainfile()
    if "--render" in ARGS:
        render_previews(scene, cams, "BLENDER_WORKBENCH", "previews")
        if (OUT / "splat.json").exists():
            render_previews(scene, cams, "BLENDER_EEVEE", "previews_painted")


main()
