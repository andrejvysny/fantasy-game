"""
Short grass for Godot 4: a tuft and two wide patches, all built from the SAME two sprites.

Run: blender -b -P make_grass.py -- --tex gtex --out gout [low:15 mid:40 top:70 ...]

A "sprite" = 1 top-down ground card (grass_top) + N crossed low vertical cards (grass_side).
  grass_tuft     : 1 sprite, 3 cards
  grass_patch_M  : centre + 4 ring sprites, 2 cards
  grass_patch_L  : centre + 7 ring sprites, 2 cards
Blade size is identical in all three, so wider area = more sprites, never a stretched texture.
Sprites get deterministic random rotation / scale / height so overlaps don't z-fight or repeat.
Every card is two single-sided quads back to back (1 mm apart) with UP normals (matches terrain
lighting, and avoids Godot's flipped-normal problem on double-sided materials).
"""
import bpy, bmesh, json, math, os, random, sys
from mathutils import Vector

argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
def arg(n, d=None):
    return argv[argv.index(n) + 1] if n in argv else d
TEX = os.path.abspath(arg("--tex", "gtex"))
OUT = os.path.abspath(arg("--out", "gout"))
RENDERS = [a for a in argv if ":" in a and not a.startswith("--")]
os.makedirs(OUT, exist_ok=True)
meta = json.load(open(os.path.join(TEX, "meta.json")))

CARD_W = 1.20          # m, width of one vertical card (blades ~1.5 cm wide, ~30 cm tall)
TOP_D = 1.50           # m, diameter of one ground disc
SINK = 0.03            # m, cards start below ground
CAP_Z0, CAP_DZ = 0.035, 0.014   # ground disc heights, staggered per sprite (no coplanar overlap)

ASSETS = {
    "grass_tuft":    dict(ring=0, r=0.0,  cards=3, seed=1),
    "grass_patch_M": dict(ring=4, r=0.70, cards=2, seed=2),
    "grass_patch_L": dict(ring=7, r=1.15, cards=2, seed=3),
}

bpy.ops.wm.read_factory_settings(use_empty=True)
scene = bpy.context.scene


def make_material(name, png):
    img = bpy.data.images.load(png, check_existing=True)
    img.colorspace_settings.name = "sRGB"
    img.alpha_mode = "STRAIGHT"
    img.pack()
    m = bpy.data.materials.new(name)
    m.use_nodes = True
    nt = m.node_tree
    bsdf = nt.nodes["Principled BSDF"]
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image, tex.interpolation, tex.extension = img, "Linear", "EXTEND"
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    nt.links.new(tex.outputs["Alpha"], bsdf.inputs["Alpha"])
    bsdf.inputs["Roughness"].default_value = 1.0
    for k in ("Specular IOR Level", "Specular"):
        if k in bsdf.inputs:
            bsdf.inputs[k].default_value = 0.0
    if hasattr(m, "blend_method"):          # Blender <= 4.1 -> glTF alphaMode MASK
        m.blend_method, m.alpha_threshold, m.shadow_method = "CLIP", 0.5, "CLIP"
    m.use_backface_culling = True
    return m


def add_card(bm, uvl, corners, uvs, mat_index):
    p = [Vector(c) for c in corners]
    n = (p[1] - p[0]).cross(p[2] - p[1]).normalized()
    eps = 0.001
    fa = bm.faces.new([bm.verts.new(c + n * eps) for c in p])
    fb = bm.faces.new([bm.verts.new(c - n * eps) for c in reversed(p)])
    for f, uv in ((fa, uvs), (fb, list(reversed(uvs)))):
        f.material_index = mat_index
        for l, (u, v) in zip(f.loops, uv):
            l[uvl].uv = (u, v)


def sprites_for(spec):
    rng = random.Random(spec["seed"])
    out = [dict(x=0.0, y=0.0, rot=rng.uniform(0, math.pi), s=1.05)]
    n = spec["ring"]
    for k in range(n):
        ang = 2 * math.pi * k / n + rng.uniform(-0.25, 0.25) * 2 * math.pi / n
        r = spec["r"] * rng.uniform(0.92, 1.08)
        out.append(dict(x=r * math.cos(ang), y=r * math.sin(ang),
                        rot=rng.uniform(0, math.pi), s=rng.uniform(0.88, 1.08)))
    return out


def build(key, loc):
    spec = ASSETS[key]
    ms, mt = meta["grass_side"], meta["grass_top"]
    sx0, sy0, sx1, sy1 = ms["bbox"]
    ks = CARD_W / (sx1 - sx0)                       # m per texel, side card
    qw, qh = ms["w"] * ks, ms["h"] * ks
    tx0, ty0, tx1, ty1 = mt["bbox"]
    kt = TOP_D / (tx1 - tx0)
    ts = mt["w"] * kt

    me = bpy.data.meshes.new(key)
    bm = bmesh.new()
    uvl = bm.loops.layers.uv.new("UVMap")
    me.materials.append(make_material("grass_side_mat", os.path.join(TEX, "grass_side.png")))
    me.materials.append(make_material("grass_top_mat", os.path.join(TEX, "grass_top.png")))

    for j, sp in enumerate(sprites_for(spec)):
        s, cx, cy, rot = sp["s"], sp["x"], sp["y"], sp["rot"]
        for i in range(spec["cards"]):
            a = rot + math.pi * i / spec["cards"]
            dx, dy = math.cos(a), math.sin(a)
            zb = -SINK
            pts = []
            for px, pz in ((-qw / 2, zb), (qw / 2, zb), (qw / 2, zb + qh), (-qw / 2, zb + qh)):
                pts.append((cx + px * s * dx, cy + px * s * dy, pz))
            # scale height about the ground (keep sunk part fixed)
            pts = [(x, y, (z + SINK) * s - SINK) for x, y, z in pts]
            uv = [(0, 0), (1, 0), (1, 1), (0, 1)]
            if (i + j) % 2:
                uv = [(1 - u, v) for u, v in uv]
            add_card(bm, uvl, pts, uv, 0)
        # ground disc
        zc = CAP_Z0 + CAP_DZ * j
        c, sn = math.cos(rot), math.sin(rot)
        half = ts * s / 2
        corners = [(-half, -half), (half, -half), (half, half), (-half, half)]
        pts = [(cx + px * c - py * sn, cy + px * sn + py * c, zc) for px, py in corners]
        add_card(bm, uvl, pts, [(0, 0), (1, 0), (1, 1), (0, 1)], 1)

    bm.to_mesh(me)
    bm.free()
    if hasattr(me, "use_auto_smooth"):
        me.use_auto_smooth = True
    me.normals_split_custom_set_from_vertices([Vector((0, 0, 1))] * len(me.vertices))

    ob = bpy.data.objects.new(key, me)
    scene.collection.objects.link(ob)
    ob.location = loc
    xs = [v.co.x for v in me.vertices]; ys = [v.co.y for v in me.vertices]; zs = [v.co.z for v in me.vertices]
    ob["extent_xy_m"] = round(max(max(xs) - min(xs), max(ys) - min(ys)), 2)
    ob["height_m"] = round(max(zs), 2)
    return ob


def export(ob, path):
    bpy.ops.object.select_all(action="DESELECT")
    ob.select_set(True)
    bpy.context.view_layer.objects.active = ob
    loc = ob.location.copy()
    ob.location = (0, 0, 0)
    bpy.ops.export_scene.gltf(filepath=path, export_format="GLB", use_selection=True,
                              export_apply=True, export_yup=True, export_normals=True,
                              export_texcoords=True, export_materials="EXPORT",
                              export_cameras=False, export_lights=False)
    ob.location = loc


objs = {}
for k, x in (("grass_tuft", -4.9), ("grass_patch_M", -1.6), ("grass_patch_L", 2.9)):
    objs[k] = build(k, (x, 0, 0))
for k, ob in objs.items():
    export(ob, os.path.join(OUT, k + ".glb"))
    tris = sum(len(p.vertices) - 2 for p in ob.data.polygons)
    print("EXPORTED", k, "tris", tris, "extent_m", ob["extent_xy_m"], "height_m", ob["height_m"])

bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, "grass.blend"))   # clean, before preview-only nodes

# ---------- preview ----------
if "--shadows" not in argv:          # recommended Godot setting for grass: cast_shadow = Off
    for _o in objs.values():
        _o.visible_shadow = False
for m in bpy.data.materials:           # Cycles ignores backface culling: emulate it (preview only)
    nt = m.node_tree
    bsdf, out = nt.nodes["Principled BSDF"], nt.nodes["Material Output"]
    geo, tr, mix = (nt.nodes.new(t) for t in ("ShaderNodeNewGeometry", "ShaderNodeBsdfTransparent", "ShaderNodeMixShader"))
    nt.links.new(geo.outputs["Backfacing"], mix.inputs["Fac"])
    nt.links.new(bsdf.outputs["BSDF"], mix.inputs[1])
    nt.links.new(tr.outputs["BSDF"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])

bpy.ops.mesh.primitive_plane_add(size=30, location=(0, 0, 0))   # neutral dark soil, preview only
gp = bpy.context.active_object
gm = bpy.data.materials.new("soil"); gm.use_nodes = True
gm.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.06, 0.04, 0.03, 1)
gm.node_tree.nodes["Principled BSDF"].inputs["Roughness"].default_value = 1
gp.data.materials.append(gm)

world = bpy.data.worlds.new("W"); scene.world = world; world.use_nodes = True
world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.012, 0.008, 0.010, 1)
sun = bpy.data.lights.new("Sun", "SUN"); sun.energy, sun.angle = 3.2, math.radians(8)
so = bpy.data.objects.new("Sun", sun); scene.collection.objects.link(so)
so.rotation_euler = (math.radians(50), math.radians(10), math.radians(-35))
fl = bpy.data.lights.new("Fill", "SUN"); fl.energy = 0.6
fo = bpy.data.objects.new("Fill", fl); scene.collection.objects.link(fo)
fo.rotation_euler = (math.radians(70), 0, math.radians(150))
cam = bpy.data.cameras.new("Cam"); cam.lens = 50
co = bpy.data.objects.new("Cam", cam); scene.collection.objects.link(co); scene.camera = co

scene.render.engine = "CYCLES"
scene.cycles.device, scene.cycles.samples, scene.cycles.use_denoising = "CPU", 40, False
scene.render.resolution_x, scene.render.resolution_y = 1600, 800
scene.view_settings.view_transform = "Standard"
for r in RENDERS:
    name, elev = r.split(":")
    e, d = math.radians(float(elev)), 17.0
    target = Vector((-1.0, 0, 0.1))
    co.location = target + Vector((0, -d * math.cos(e), d * math.sin(e)))
    co.rotation_euler = (target - co.location).to_track_quat("-Z", "Y").to_euler()
    scene.render.filepath = os.path.join(OUT, name + ".png")
    bpy.ops.render.render(write_still=True)
    print("RENDERED", name)
