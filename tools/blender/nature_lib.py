"""Shared helpers for the valley nature asset scripts (Blender 5.2, run headless).

Asset contract (full text: assets/nature/README.md):
  * Metres, authored Z-up; the glTF exporter converts to Godot's Y-up. No manual axis fix.
  * One mesh object per asset, transforms applied, pivot at the ground contact (plants,
    trees) or at the deliberate contact/embed origin (rocks; `embed_depth` in metadata).
  * At most two materials, named by surface identity (never inferred from colour):
      M_solid   - rock, bark, wood, soil (single sided)
      M_foliage - needles, leaves, fronds, grass blades, petals (double sided)
  * COLOR_0 (RGBA, linear): rgb = broad painted base colour, a = flex weight for wind
    (0 = anchored root/trunk, 1 = free tip).
  * TEXCOORD_0 = stable unwrap (future texture slot). TEXCOORD_1 (Godot UV2):
    x = restrained cavity/occlusion (1 open .. 0 occluded), y = per-part random 0..1.
  * No baked sun, cast shadows or fire light in colour.

Typical family script:
    import nature_lib as nl
    nl.reset_scene()
    obj = build_something(...)            # bmesh -> object, colours via nl.paint_*
    nl.finalize(obj)
    meta = nl.export_asset(obj, "rocks", "boulder_large_A", family="boulder_large", ...)
    nl.render_previews(obj, "rocks", "boulder_large_A")
    nl.save_blend("rocks")
"""
from __future__ import annotations

import json
import math
import random
from pathlib import Path

import bmesh
import bpy
from mathutils import Matrix, Vector

ROOT = Path(__file__).resolve().parent.parent.parent  # project root
ASSET_ROOT = ROOT / "assets" / "nature"
SOLID = "M_solid"
FOLIAGE = "M_foliage"
COLOR_ATTR = "Col"
DATA_UV = "UVData"
CHARACTER_HEIGHT = 1.8  # scale marker in previews (player capsule)

# Shared sRGB albedo palette (convert with srgb()). Picked for neutral light, not from lit
# screenshots; conifers continue the existing spruce library (#1d4731 .. #5c9342), ground
# greens continue WorldStyle (meadow #6e8b40, moss #4d6a33, litter #5e4c33, dirt #806549).
PALETTE = {
    # geology: pale neutral grey planes, restrained cavity, faint warm weathering
    "rock_light": "#b4afa4", "rock": "#a19d94", "rock_dark": "#8f8b83", "rock_cavity": "#7c7973",
    "rock_weathered": "#aaa08c", "rock_wet": "#6e6c68",
    "moss": "#4d6a33", "moss_light": "#5f7d3c", "soil": "#5e4c33", "litter": "#5e4c33", "dirt": "#806549",
    # conifers
    "conifer_deep": "#1f4630", "conifer": "#2a5936", "conifer_tip": "#4f8540",
    "pine_deep": "#2c4f2f", "pine": "#3e6a36", "pine_tip": "#5f8a44",
    "bark_dark": "#4a3a2e", "bark": "#5b4535", "bark_ridge": "#6e5642", "deadwood": "#7a6c5c",
    "wood_exposed": "#a88c68",
    # understory
    "shrub_deep": "#3f6230", "shrub": "#4d7236", "shrub_light": "#5c8240",
    "fern_deep": "#3b6029", "fern": "#4b7a34", "fern_light": "#5d8c3c",
    # meadow
    "grass_root": "#4f6a2e", "grass": "#6e8b40", "grass_tip": "#8aa24e", "grass_dry": "#a09553",
    "stem": "#577a36",
    "flower_white": "#ece8dc", "flower_white_eye": "#d9b84a", "flower_pink": "#d58aa8",
    "flower_pink_deep": "#c06f95", "flower_yellow": "#e0c04a", "flower_blue": "#7089c8",
    "reed": "#6f7f3f", "reed_tip": "#a39a5c",
}


def pal(name: str) -> tuple[float, float, float]:
    """Linear RGB of a PALETTE entry."""
    return srgb(PALETTE[name])


# ---------------------------------------------------------------- scene

def reset_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)
    scene = bpy.context.scene
    scene.unit_settings.system = "METRIC"
    scene.unit_settings.scale_length = 1.0


def asset_dir(group: str) -> Path:
    d = ASSET_ROOT / group
    d.mkdir(parents=True, exist_ok=True)
    return d


def source_dir(group: str) -> Path:
    d = asset_dir(group) / "source"
    d.mkdir(parents=True, exist_ok=True)
    (d / ".gdignore").touch()
    return d


def preview_dir(group: str) -> Path:
    d = asset_dir(group) / "previews"
    d.mkdir(parents=True, exist_ok=True)
    (d / ".gdignore").touch()
    return d


# ---------------------------------------------------------------- materials

def material(name: str) -> bpy.types.Material:
    """Vertex-colour material; the exporter writes COLOR_0 because the material uses it."""
    mat = bpy.data.materials.get(name)
    if mat is not None:
        return mat
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    bsdf = nodes.get("Principled BSDF")
    attr = nodes.new("ShaderNodeVertexColor")
    attr.layer_name = COLOR_ATTR
    mat.node_tree.links.new(attr.outputs["Color"], bsdf.inputs["Base Color"])
    bsdf.inputs["Roughness"].default_value = 0.9
    bsdf.inputs["Metallic"].default_value = 0.0
    mat.use_backface_culling = name != FOLIAGE
    return mat


def mesh_object(name: str, bm: bmesh.types.BMesh, materials: tuple[str, ...] = (SOLID,)) -> bpy.types.Object:
    """Object from a bmesh whose faces carry material_index into `materials`."""
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(obj)
    for m in materials:
        me.materials.append(material(m))
    return obj


# ---------------------------------------------------------------- vertex data

def ensure_layers(obj: bpy.types.Object) -> None:
    me = obj.data
    if COLOR_ATTR not in me.color_attributes:
        me.color_attributes.new(COLOR_ATTR, "FLOAT_COLOR", "CORNER")
    me.color_attributes.active_color = me.color_attributes[COLOR_ATTR]
    if not me.uv_layers:
        me.uv_layers.new(name="UVMap")
    if DATA_UV not in me.uv_layers:
        me.uv_layers.new(name=DATA_UV)
    me.uv_layers.active = me.uv_layers[0]


def paint(obj: bpy.types.Object, fn) -> None:
    """fn(poly, loop_index, vertex_co) -> (r, g, b, flex) per face corner. Colours linear."""
    ensure_layers(obj)
    me = obj.data
    col = me.color_attributes[COLOR_ATTR].data
    for poly in me.polygons:
        for li in poly.loop_indices:
            v = me.vertices[me.loops[li].vertex_index].co
            col[li].color = fn(poly, li, v)


def paint_data(obj: bpy.types.Object, fn) -> None:
    """fn(poly, loop_index, vertex_co) -> (cavity 0..1, part_random 0..1) into TEXCOORD_1."""
    ensure_layers(obj)
    me = obj.data
    uv = me.uv_layers[DATA_UV].data
    for poly in me.polygons:
        for li in poly.loop_indices:
            v = me.vertices[me.loops[li].vertex_index].co
            uv[li].uv = fn(poly, li, v)


def srgb(hex_or_rgb) -> tuple[float, float, float]:
    """sRGB '#rrggbb' or 0..255 triple -> linear floats (vertex colours are linear)."""
    if isinstance(hex_or_rgb, str):
        h = hex_or_rgb.lstrip("#")
        rgb = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    else:
        rgb = [c / 255.0 for c in hex_or_rgb]
    return tuple(c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb)


def mix(a, b, t: float):
    return tuple(x + (y - x) * t for x, y in zip(a, b))


def scale_rgb(c, k: float):
    return tuple(x * k for x in c)


# ---------------------------------------------------------------- finalize / validate

def join(objs: list[bpy.types.Object], name: str) -> bpy.types.Object:
    bpy.ops.object.select_all(action="DESELECT")
    for o in objs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = objs[0]
    bpy.ops.object.join()
    obj = bpy.context.view_layer.objects.active
    obj.name = name
    obj.data.name = name
    return obj


def finalize(obj: bpy.types.Object, smooth_angle_deg: float | None = None,
             custom_normals: bool = False) -> None:
    """Apply transforms; flat shading by default, auto smooth by angle, or (custom_normals)
    all faces smooth so a later me.normals_split_custom_set() is honoured (Blender ignores
    custom split normals on sharp faces)."""
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    ensure_layers(obj)
    me = obj.data
    if custom_normals:
        for p in me.polygons:
            p.use_smooth = True
    elif smooth_angle_deg is None:
        for p in me.polygons:
            p.use_smooth = False
    else:
        for p in me.polygons:
            p.use_smooth = True
        bpy.ops.object.shade_smooth_by_angle(angle=math.radians(smooth_angle_deg))
    me.validate(clean_customdata=False)
    me.update()


def uv_unwrap(obj: bpy.types.Object, island_margin: float = 0.02) -> None:
    """Stable UV0 via smart project (deterministic for a given mesh)."""
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    obj.data.uv_layers.active = obj.data.uv_layers[0]
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(66), island_margin=island_margin)
    bpy.ops.object.mode_set(mode="OBJECT")


def validate(obj: bpy.types.Object) -> dict:
    """Export-blocking checks plus informative topology counts."""
    me = obj.data
    bm = bmesh.new()
    bm.from_mesh(me)
    nonfinite = sum(1 for v in bm.verts if not all(math.isfinite(c) for c in v.co))
    degenerate = sum(1 for f in bm.faces if f.calc_area() < 1e-8)
    loose = sum(1 for v in bm.verts if not v.link_faces)
    non_manifold = sum(1 for e in bm.edges if not e.is_manifold)
    tris = sum(len(f.verts) - 2 for f in bm.faces)
    bm.free()
    mats = [m.name for m in me.materials]
    errors = []
    if nonfinite:
        errors.append(f"{nonfinite} non-finite vertices")
    if degenerate:
        errors.append(f"{degenerate} degenerate faces")
    if loose:
        errors.append(f"{loose} loose vertices")
    if not set(mats) <= {SOLID, FOLIAGE}:
        errors.append(f"unexpected materials {mats}")
    return {"errors": errors, "tris": tris, "verts": len(me.vertices),
            "non_manifold_edges": non_manifold, "materials": mats}


def bounds(obj: bpy.types.Object) -> tuple[Vector, Vector]:
    cs = [obj.matrix_world @ v.co for v in obj.data.vertices]
    lo = Vector((min(c.x for c in cs), min(c.y for c in cs), min(c.z for c in cs)))
    hi = Vector((max(c.x for c in cs), max(c.y for c in cs), max(c.z for c in cs)))
    return lo, hi


# ---------------------------------------------------------------- export

def export_asset(obj: bpy.types.Object, group: str, asset_id: str, *, family: str,
                 habitats: list[str], collision: dict, budget_tris: tuple[int, int],
                 embed_depth: float = 0.0, scale_range=(0.9, 1.1), max_tilt_deg: float = 0.0,
                 orientation_constrained: bool = False, wind: str = "none",
                 recipe: dict | None = None, notes: str = "", pivot: str | None = None) -> dict:
    """Validate, write <group>/<asset_id>.glb and .json. Raises on export-blocking errors.
    pivot defaults to ground_contact (trees/plants, even when roots reach below y = 0);
    rocks with an embed depth default to embed_origin."""
    report = validate(obj)
    if report["errors"]:
        raise RuntimeError(f"{asset_id}: " + "; ".join(report["errors"]))
    lo, hi = bounds(obj)
    out = asset_dir(group)
    glb = out / f"{asset_id}.glb"
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.export_scene.gltf(
        filepath=str(glb), export_format="GLB", use_selection=True, export_yup=True,
        export_apply=True, export_texcoords=True, export_normals=True, export_tangents=False,
        export_materials="EXPORT", export_vertex_color="ACTIVE", export_all_vertex_colors=False,
        export_image_format="NONE", export_animations=False, export_skins=False,
        export_morph=False, export_cameras=False, export_lights=False, export_extras=False)
    tris = report["tris"]
    meta = {
        "asset_id": asset_id, "version": 1, "family": family, "group": group,
        "habitats": habitats,
        # Godot axes (Y up): size x, y (height), z.
        "bbox_min": [round(lo.x, 3), round(lo.z, 3), round(-hi.y, 3)],
        "bbox_max": [round(hi.x, 3), round(hi.z, 3), round(-lo.y, 3)],
        "pivot": pivot or ("embed_origin" if embed_depth > 0.0 and group == "rocks" else "ground_contact"),
        "embed_depth": embed_depth, "scale_range": list(scale_range), "max_tilt_deg": max_tilt_deg,
        "orientation_constrained": orientation_constrained,
        "materials": report["materials"], "tris": tris, "verts": report["verts"],
        "budget_tris": list(budget_tris), "within_budget": budget_tris[0] <= tris <= budget_tris[1],
        "non_manifold_edges": report["non_manifold_edges"],
        "lod": "godot_auto" if tris > 400 else "none",
        "collision": collision, "wind": wind,
        "texel_density": "vertex_colour (no texture); UV0 reserved at 256 px/m",
        "channels": {"COLOR_0.rgb": "base colour linear", "COLOR_0.a": "flex weight",
                     "UV2.x": "cavity", "UV2.y": "part random"},
        "recipe": recipe or {}, "approval": "candidate", "provenance": "procedural, tools/blender",
        "notes": notes,
    }
    (out / f"{asset_id}.json").write_text(json.dumps(meta, indent=2))
    return meta


def save_blend(group: str, name: str | None = None) -> Path:
    path = source_dir(group) / f"{name or group}.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(path), compress=True)
    for p in path.parent.glob("*.blend1"):
        p.unlink()
    return path


# ---------------------------------------------------------------- previews

def _preview_material(name: str, clay: bool) -> bpy.types.Material:
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes = mat.node_tree.nodes
    bsdf = nodes.get("Principled BSDF")
    bsdf.inputs["Roughness"].default_value = 0.9
    if clay:
        bsdf.inputs["Base Color"].default_value = (0.42, 0.42, 0.42, 1.0)
    else:
        attr = nodes.new("ShaderNodeVertexColor")
        attr.layer_name = COLOR_ATTR
        mat.node_tree.links.new(attr.outputs["Color"], bsdf.inputs["Base Color"])
    return mat


def _markers(lo: Vector, hi: Vector) -> list[bpy.types.Object]:
    """1 m cube and a 1.8 m capsule (character scale) beside the asset, plus a ground plane."""
    made = []
    if (hi - lo).length < 1.2:
        # Small plants: a 10 cm cube beside the asset instead of full-size markers out of frame.
        bpy.ops.mesh.primitive_cube_add(size=0.1, location=(hi.x + 0.08, lo.y - 0.02, 0.05))
        made.append(bpy.context.object)
        return _finish_markers(made, lo, hi)
    off = hi.x + 1.2
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(off, lo.y - 0.2, 0.5))
    made.append(bpy.context.object)
    r = 0.35
    bpy.ops.mesh.primitive_cylinder_add(radius=r, depth=CHARACTER_HEIGHT - 2 * r,
                                        location=(off + 1.3, lo.y - 0.2, CHARACTER_HEIGHT * 0.5))
    made.append(bpy.context.object)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=r, location=(off + 1.3, lo.y - 0.2, CHARACTER_HEIGHT - r))
    made.append(bpy.context.object)
    return _finish_markers(made, lo, hi)


def _finish_markers(made: list, lo: Vector, hi: Vector) -> list[bpy.types.Object]:
    size = max(hi.x - lo.x, hi.y - lo.y, 4.0) * 4
    bpy.ops.mesh.primitive_plane_add(size=size, location=((lo.x + hi.x) * 0.5, (lo.y + hi.y) * 0.5, 0.0))
    made.append(bpy.context.object)
    mark = _preview_material("PV_marker", True)
    mark.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.75, 0.3, 0.2, 1)
    ground = _preview_material("PV_ground", True)
    ground.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.22, 0.24, 0.2, 1)
    for o in made[:-1]:
        o.data.materials.append(mark)
    made[-1].data.materials.append(ground)
    return made


def render_previews(obj: bpy.types.Object | list, group: str, asset_id: str,
                    views=(("front34", 35.0, 18.0), ("low", 20.0, 4.0)), res=(960, 720)) -> list[Path]:
    """Clay + colour renders from a 3/4 view and a player-height view, with scale markers.
    `obj` may be a list (placed composition). Leaves the scene as it was (markers removed)."""
    objs = obj if isinstance(obj, list) else [obj]
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x, scene.render.resolution_y = res
    scene.render.film_transparent = False
    scene.view_settings.view_transform = "AgX"
    world = bpy.data.worlds.get("PV_world") or bpy.data.worlds.new("PV_world")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.55, 0.62, 0.72, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.6
    scene.world = world
    sun_data = bpy.data.lights.new("PV_sun", "SUN")
    sun_data.energy = 3.5
    sun_data.angle = math.radians(1.5)
    sun = bpy.data.objects.new("PV_sun", sun_data)
    scene.collection.objects.link(sun)
    lo = Vector((min(bounds(o)[0].x for o in objs), min(bounds(o)[0].y for o in objs), min(bounds(o)[0].z for o in objs)))
    hi = Vector((max(bounds(o)[1].x for o in objs), max(bounds(o)[1].y for o in objs), max(bounds(o)[1].z for o in objs)))
    markers = _markers(lo, hi)
    cam_data = bpy.data.cameras.new("PV_cam")
    cam_data.lens = 50
    cam = bpy.data.objects.new("PV_cam", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    center = (lo + hi) * 0.5
    radius = max((hi - lo).length * 0.5, 0.2)
    saved = {o.name: [s.material for s in o.material_slots] for o in objs}
    outs = []
    for clay in (True, False):
        pm = _preview_material("PV_clay" if clay else "PV_color", clay)
        for o in objs:
            for s in o.material_slots:
                s.material = pm
        for vname, az, el in views:
            a, e = math.radians(az), math.radians(el)
            # Raking sun 75 deg to the side of the camera, 35 deg high: planes separate by light.
            sun.rotation_euler = (math.radians(55), 0, a + math.radians(75))
            dist = radius / math.tan(math.radians(18)) * 1.15
            target = center.copy()
            if vname == "low":
                target.z = min(center.z, 1.4)
            cam.location = target + Vector((math.sin(a) * math.cos(e), -math.cos(a) * math.cos(e), math.sin(e))) * dist
            cam.location.z = max(cam.location.z, 0.4)
            cam.rotation_euler = (target - cam.location).to_track_quat("-Z", "Y").to_euler()
            path = preview_dir(group) / f"{asset_id}_{'clay' if clay else 'color'}_{vname}.png"
            scene.render.filepath = str(path)
            bpy.ops.render.render(write_still=True)
            outs.append(path)
    for o in objs:
        for s, m in zip(o.material_slots, saved[o.name]):
            s.material = m
    for o in markers + [sun, cam]:
        bpy.data.objects.remove(o, do_unlink=True)
    return outs


# ---------------------------------------------------------------- geometry helpers

def rng(seed: int) -> random.Random:
    return random.Random(seed)


def rot_z(deg: float) -> Matrix:
    return Matrix.Rotation(math.radians(deg), 4, "Z")
