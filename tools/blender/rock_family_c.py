"""Geology family, second wave (part 2): rubble_cluster_A and shore_boulder_A. Imported by rock_family_b.py, which
registers PARAMS_C / MAKERS_C / METHOD_C next to cliff_corner_A and boulder_medium_A (same construction language as
rock_family.py: planes from a fracture frame first, noise last; rock_family.py itself is never modified).

rubble_cluster_A: ten separate convex stones in ONE mesh, all on the cliff fracture frame (+-5 deg yaw scatter). Stones are
slabs and wedges (non-parallel joint pairs, tilted tops), settled against each other by bisection so the core really touches.
shore_boulder_A: a convex dome from planes (crown, shoulders, per-spoke flanks with a steeper foot), rounded by 2-segment
bevels and angle-smoothed, with a level wet-line made by horizontal bisects (no skirt union, no Catmull-Clark).
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent if "__file__" in globals() else "/Users/andrejvysny/Developer/godot/tools/blender"))

import bmesh  # noqa: E402
import bpy  # noqa: E402
from mathutils import Matrix, Vector, noise  # noqa: E402

import nature_lib as nl  # noqa: E402
import rock_family as rf  # noqa: E402


def stone(pos, size, top, d, embed, **kw) -> dict:
    """pos (x, y) world plan; size (length x, width y, height above ground at the highest point); top = (tilt deg, toward
    azimuth deg in plan, 0 = -Y, 90 = +X) of the bedding top inside the frame; d = (front/back, left/right) joint-pair
    non-parallelism in deg; lean = (deg, plan direction in deg CCW from +X) tips the whole stone toward an anchor."""
    return dict(pos=pos, size=size, top=top, d=d, embed=embed, **kw)


PARAMS_C = {
    "rubble_cluster_A": dict(
        family="rubble_cluster", seed=7711, tilt=11.0, azimuth=35.0, yaw=5.0, embed=0.1,
        bevel=0.012, chamfer_len=0.14, edge_len=0.2, distort=0.01, distort_freq=1.3,
        # Core uphill (+y): anchor 1 (chunky), anchor 2 (low slab), three stones tucked against them (uphill, side, front)
        # and one leaning 20 deg on anchor 1. Tail downhill (-y): four small wedges in a ~0.6 m strip, gaps 0.15 -> 0.45 m.
        # touch = (index of the stone it is settled against, wanted gap in m; < 0 = slight interpenetration).
        stones=[
            stone((-0.28, 0.20), (0.42, 0.30, 0.34), (14, 20), (16, -12), 0.10),                          # 0 anchor 1
            stone((0.28, 0.08), (0.42, 0.28, 0.18), (9, 100), (-14, 18), 0.07, touch=(0, 0.012)),           # 1 anchor 2, slab
            stone((-0.30, 0.52), (0.28, 0.20, 0.15), (20, 180), (-17, 11), 0.05, touch=(0, 0.0)),           # 2 uphill of 0
            stone((0.64, 0.18), (0.22, 0.18, 0.15), (18, 90), (12, -20), 0.05, touch=(1, 0.018)),           # 3 beside 1
            stone((-0.70, 0.12), (0.27, 0.21, 0.26), (12, 60), (-13, 15), 0.06, lean=(20, 0), touch=(0, -0.012)),  # 4 leans on 0
            stone((0.0, -0.17), (0.20, 0.14, 0.10), (22, 0), (19, -16), 0.05, touch=(1, 0.01)),             # 5 front tuck
            stone((-0.04, -0.45), (0.23, 0.16, 0.11), (22, 0), (-12, 14), 0.05),                          # 6 tail 1
            stone((0.15, -0.80), (0.18, 0.13, 0.09), (18, 20), (15, -11), 0.05),                          # 7 tail 2
            stone((-0.20, -1.23), (0.14, 0.11, 0.08), (20, 330), (-18, 12), 0.05),                        # 8 tail 3
            stone((0.10, -1.72), (0.12, 0.10, 0.07), (16, 10), (13, -19), 0.05),                          # 9 tail 4
        ],
        habitats=["rocky_slope", "rock_foot"], collision={"class": "none"},
        budget=(300, 1000), max_tilt=10.0, scale=(0.7, 1.4),
        notes="Ten separate angular stones in one mesh: two anchors (chunky block + low slab), three stones tucked against them, "
              "one leaning 20 deg on an anchor, and a four-stone wedge tail fanning downhill (-Y, gaps 0.15 -> 0.45 m). Stones "
              "are slabs/wedges with non-parallel joint pairs and tilted tops, all on the cliff_face_A fracture frame; each has "
              "its own flat embed cut (-0.05..-0.10 m) so none floats. Non-blocking (collision none).",
    ),
    "shore_boulder_A": dict(
        family="shore_boulder", seed=6607, tilt=4.0, azimuth=70.0, yaw=-6.0, height=0.80, embed=0.3, front=None,
        top=0.80, ring_z=(0.38, 0.62), wet_z=0.20, blend=0.04, wet_mix=0.45, blend_mix=0.22,
        bevel_up=0.13, bevel_lo=0.06, bevel_crown=0.2, segments_up=2, segments_crown=3, smooth=38.0, edge_len=0.5, distort=0.01, distort_freq=0.7,
        # spokes: (plan azimuth deg, base radius m at the waterline, crown radius / base radius, lean weight of the lower ring,
        # lean weight of the upper ring). The three flank rings of a spoke lean in proportion (w1, 1, w3) so that they reach the
        # crown rim exactly: convex (leans grow with height, 22-40 deg), and the crown stays 36-52 % of the base radius.
        spokes=[(-12, 0.66, 0.38, 0.80, 1.40), (34, 0.74, 0.44, 0.85, 1.30), (82, 0.88, 0.50, 0.78, 1.35),
                (132, 0.78, 0.42, 0.82, 1.45), (178, 0.62, 0.36, 0.80, 1.30), (-140, 0.74, 0.46, 0.85, 1.35),
                (-98, 0.84, 0.52, 0.75, 1.30), (-54, 0.70, 0.40, 0.82, 1.40)],
        habitats=["sheltered_bank", "exposed_shore"], collision={"class": "convex"},
        budget=(250, 1000), max_tilt=10.0, scale=(0.5, 1.4),
        notes="Water-worn member: low broad dome (flanks lean 25-40 deg, a steeper foot below 0.3 m so it reads partly submerged), "
              "bedding crown plane with rounded rims (2-segment bevels), smoothed normals; a level wet-line (rock_wet, 0.2 m "
              "above the waterline, 4 cm blend) made by horizontal bisects. 0.3 m buried.",
    ),
}
METHOD_C = {
    "rubble_cluster_A": "ten convex stones (non-parallel joint pairs, tilted tops) on one fracture frame, settled against each "
                        "other by bisection, flat embed cut per stone, chamfer, refine",
    "shore_boulder_A": "convex dome from crown/shoulder/flank/foot planes, 2-segment rounding bevels, level wet-line bisects, "
                       "angle-smoothed normals",
}
MAKERS_C = {}


def az_of(x: float, y: float) -> float:
    """Plan direction -> plane() azimuth (0 = -Y)."""
    return math.degrees(math.atan2(x, -y))


# ---------------------------------------------------------------- rubble

def stone_specs(r, S: dict) -> list:
    """One stone, aligned frame, centred on the origin: bedding top (tilted wedge), two non-parallel joint pairs, two broken
    corners. The top passes through the origin; the bottom is deep, the embed cut is made after placement."""
    a, b, h = S["size"]
    hx, hy = a / 2, b / 2
    j1, j2 = r.uniform(-4, 4), r.uniform(-4, 4)
    d1, d2 = S["d"]
    t, az = S["top"]
    specs = [("flat", az, t, 0, 0, 0), ("!flat", 0, 0, 0, 0, -(h + S["embed"] + 0.6)),
             ("wall", j1, r.uniform(3, 11), 0, -hy, 0), ("wall", 180 + j1 + d1, r.uniform(3, 11), 0, hy, 0),
             ("wall", -90 + j2, r.uniform(3, 11), -hx, 0, 0), ("wall", 90 + j2 + d2, r.uniform(3, 11), hx, 0, 0)]
    corners = [(sx, sy) for sx in (-1, 1) for sy in (-1, 1)]
    r.shuffle(corners)
    for sx, sy in corners[:2]:
        k = r.uniform(0.6, 0.78)
        specs.append(("wall", az_of(sx * hx, sy * hy) + r.uniform(-10, 10), r.uniform(8, 32), sx * hx * k, sy * hy * k, 0))
    return specs


def lean_matrix(S: dict) -> Matrix:
    deg, toward = S.get("lean", (0.0, 0.0))
    a = math.radians(toward)
    return Matrix.Rotation(math.radians(deg), 3, Vector((-math.sin(a), math.cos(a), 0.0)))


def place_stone(bm: bmesh.types.BMesh, rot: Matrix, pos, height: float, embed: float) -> bmesh.types.BMesh:
    """Rotate into the frame, centre over `pos`, top at `height`, cut flat at -embed (a stone can not float)."""
    bmesh.ops.transform(bm, matrix=rot.to_4x4(), verts=bm.verts)
    lo, hi = rf.extent(bm)
    bmesh.ops.translate(bm, vec=Vector((pos[0] - (lo.x + hi.x) / 2, pos[1] - (lo.y + hi.y) / 2, height - hi.z)), verts=bm.verts)
    return rf.clip(bm, Vector((0, 0, -1)), embed)


def gap(a: bmesh.types.BMesh, b: bmesh.types.BMesh, shift: Vector) -> float:
    """Face-normal separation of two convex shells with `a` moved by `shift`: > 0 apart, < 0 interpenetrating."""
    best = -1e9
    for src, dst, sgn in ((a, b, 1.0), (b, a, -1.0)):
        src.normal_update()
        for f in src.faces:
            n, d = f.normal, f.normal.dot(f.verts[0].co)
            if sgn > 0:
                d += n.dot(shift)
                best = max(best, min(n.dot(v.co) - d for v in dst.verts))
            else:
                best = max(best, min(n.dot(v.co + shift) - d for v in dst.verts))
    return best


def settle(stones: list, specs: list) -> None:
    """Slide each stone with a `touch` toward its target (in plan) until the wanted gap: contact is exact, not hand-tuned."""
    for i, S in enumerate(specs):
        if "touch" not in S:
            continue
        j, want = S["touch"]
        ci, cj = (Vector(rf.extent(stones[k])[0] + rf.extent(stones[k])[1]) * 0.5 for k in (i, j))
        u = Vector((cj.x - ci.x, cj.y - ci.y, 0.0))
        dist = u.length
        u.normalize()
        if gap(stones[i], stones[j], Vector()) <= want:
            continue
        lo, hi = 0.0, dist
        for _ in range(40):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if gap(stones[i], stones[j], u * mid) > want else (lo, mid)
        bmesh.ops.translate(stones[i], vec=u * ((lo + hi) / 2), verts=stones[i].verts)


def merge(dst: bmesh.types.BMesh, src: bmesh.types.BMesh, layer, sid: int) -> None:
    m = {v: dst.verts.new(v.co) for v in src.verts}
    for f in src.faces:
        dst.faces.new([m[v] for v in f.verts])[layer] = sid


def chamfer_edges(bm: bmesh.types.BMesh, w: float, min_len: float) -> list:
    bm.normal_update()
    edges = [e for e in bm.edges if len(e.link_faces) == 2 and e.calc_length() >= min_len
             and e.calc_face_angle_signed(0.0) >= math.radians(50) and (e.verts[0].co.z + e.verts[1].co.z) * 0.5 >= -0.02]
    res = bmesh.ops.bevel(bm, geom=edges, offset=w, offset_type="OFFSET", segments=1, profile=0.5, affect="EDGES",
                          clamp_overlap=True)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1.5e-3)
    return [f for f in res["faces"] if f.is_valid]


def make_rubble(asset_id: str) -> bpy.types.Object:
    P = PARAMS_C[asset_id]
    nl.reset_scene()
    noise.seed_set(P["seed"])
    r = nl.rng(P["seed"])
    off = Vector((r.uniform(0, 90), r.uniform(0, 90), r.uniform(0, 90)))
    rot = rf.frame_matrix(P)
    stones = []
    for S in P["stones"]:
        body = rf.polytope(r, stone_specs(r, S))
        yaw = Matrix.Rotation(math.radians(r.uniform(-5, 5)), 3, "Z")
        stones.append(place_stone(body, lean_matrix(S) @ yaw @ rot, S["pos"], S["size"][2], S["embed"]))
    settle(stones, P["stones"])
    bm = bmesh.new()
    layer = bm.faces.layers.int.new("stone")
    for i, st in enumerate(stones):
        merge(bm, st, layer, i)
        st.free()
    bev = chamfer_edges(bm, P["bevel"], P["chamfer_len"])
    rf.classify(bm, rot, bev, r)
    rf.refine(bm, P["edge_len"])
    rf.distort(bm, P, off)
    bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method="BEAUTY")
    obj = nl.mesh_object(asset_id, bm)
    nl.finalize(obj)
    nl.uv_unwrap(obj)
    me, rnd = obj.data, [nl.rng(P["seed"] + 1 + i).random() for i in range(len(P["stones"]))]
    base, stone_of = rf.colour_fn(me, off), me.attributes["stone"].data

    def stone_colour(poly, li, v):
        c = base(poly, li, v)
        return (*nl.scale_rgb(c[:3], 0.92 + 0.14 * rnd[stone_of[poly.index].value]), 0.0)  # value step per stone
    nl.paint(obj, stone_colour)
    cav = rf.vertex_cavity(obj)
    nl.paint_data(obj, lambda poly, li, v: (cav[me.loops[li].vertex_index], rnd[stone_of[poly.index].value]))
    for name in ("cls", "grp", "warm", "stone"):
        me.attributes.remove(me.attributes[name])
    return obj


MAKERS_C["rubble_cluster_A"] = make_rubble


# ---------------------------------------------------------------- shore boulder

def dome_specs(P: dict, r) -> list:
    """Crown plane + per spoke three flank planes. Each spoke's total inset (base radius - crown radius) is shared out over
    the three rings in proportion to (w1, 1, w3) x ring height, so the leans grow with height (convex everywhere: no skirt,
    no crease that can fold or pinch) and the rings end exactly at the crown rim."""
    top = P["top"]
    specs = [("flat", 0, 1.0, 0, 0, top), ("!flat", 0, 0, 0, 0, -1.0)]
    for az, rad, ratio, w1, w3 in P["spokes"]:
        z1, z2 = (z + r.uniform(-0.09, 0.09) for z in P["ring_z"])  # ring seams never line up around the rock
        m = rad * (1.0 - ratio) / (z1 * w1 + (z2 - z1) + (top - z2) * w3)
        t1, t2, t3 = m * w1, m, m * w3
        radii = (rad, rad + z1 * (t2 - t1), rad + z1 * (t2 - t1) + z2 * (t3 - t2))  # plane radii extrapolated to z = 0
        dx, dy = math.sin(math.radians(az)), -math.cos(math.radians(az))
        specs += [("wall", az, math.degrees(math.atan(t)), dx * rr, dy * rr, 0) for t, rr in zip((t1, t2, t3), radii)]
    return specs


def round_edges(bm: bmesh.types.BMesh, P: dict) -> list:
    """Water-worn: nearly every convex edge rounded. Crown rim widest (3 segments), flank edges 2 segments, edges within
    the wet band narrow (1 segment)."""
    faces = []
    mid = lambda e: (e.verts[0].co.z + e.verts[1].co.z) * 0.5  # noqa: E731
    passes = (("crown", P["bevel_crown"], P["segments_crown"], lambda e: any(f.normal.z > 0.97 for f in e.link_faces)),
              ("flank", P["bevel_up"], P["segments_up"], lambda e: mid(e) >= 0.02),
              ("wet", P["bevel_lo"], 1, lambda e: mid(e) < 0.02))
    for _, width, segments, pick in passes:
        bm.normal_update()
        edges = [e for e in bm.edges if len(e.link_faces) == 2 and e.calc_face_angle_signed(0.0) >= math.radians(12)
                 and mid(e) >= -0.12 and pick(e)]
        res = bmesh.ops.bevel(bm, geom=edges, offset=width, offset_type="OFFSET", segments=segments, profile=0.5,
                              affect="EDGES", clamp_overlap=True)
        faces += list(res["faces"])
        bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=2e-3)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return [f for f in faces if f.is_valid]


def wet_zones(bm: bmesh.types.BMesh, P: dict) -> None:
    """Level wet-line: cut the mesh at wet_z and wet_z + blend, then tag faces by zone (2 wet, 1 blend, 0 dry)."""
    for z in (P["wet_z"], P["wet_z"] + P["blend"]):
        bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], dist=1e-5,
                               plane_co=Vector((0, 0, z)), plane_no=Vector((0, 0, 1)))
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=2e-3)  # a cut a hair from a vertex leaves mm slivers; tidy() would
    # also dissolve the (coplanar) wet-line edges, so only weld here
    zone = bm.faces.layers.int.new("zone")
    for f in bm.faces:
        cz = f.calc_center_median().z
        f[zone] = 2 if cz < P["wet_z"] else 1 if cz < P["wet_z"] + P["blend"] else 0


def sstep(a: float, b: float, x: float) -> float:
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3.0 - 2.0 * t)


def shore_colour(me: bpy.types.Mesh, P: dict, off: Vector, spoke_value: list):
    """Light on the crown, mid on the flanks, blended by the smoothed corner normal (no per-ring value steps: a water-worn
    boulder must not read as tiered); a small value step per spoke sector; the one weathered plane picked by classify();
    the wet band blends toward rock_wet by zone (only ~0.45 at full wet, so it reads as wet stone, never as a shadow)."""
    rock, light, dark, wet, weath = (nl.pal(n) for n in ("rock", "rock_light", "rock_dark", "rock_wet", "rock_weathered"))
    zone, warm = me.attributes["zone"].data, me.attributes["warm"].data
    mix_wet = (0.0, P["blend_mix"], P["wet_mix"])
    sectors = [s[0] for s in P["spokes"]]

    def fn(poly, li, v):
        n, pn = me.corner_normals[li].vector, poly.normal
        top = sstep(0.45, 0.85, n.z)
        az = math.degrees(math.atan2(pn.x, -pn.y))
        k = min(range(len(sectors)), key=lambda i: abs((sectors[i] - az + 180) % 360 - 180))
        col = nl.scale_rgb(nl.mix(nl.mix(rock, dark, 0.2), light, top), spoke_value[k])
        col = nl.scale_rgb(col, 0.94 + 0.06 * (1.0 + noise.noise((Vector(v) + off) * 0.3)))  # broad patches, never speckle
        if warm[poly.index].value:
            col = nl.mix(col, weath, 0.6)
        return (*nl.mix(col, wet, mix_wet[zone[poly.index].value]), 0.0)
    return fn


def make_shore(asset_id: str) -> bpy.types.Object:
    P = PARAMS_C[asset_id]
    nl.reset_scene()
    noise.seed_set(P["seed"])
    r = nl.rng(P["seed"])
    off = Vector((r.uniform(0, 90), r.uniform(0, 90), r.uniform(0, 90)))
    rot = rf.frame_matrix(P)
    bm = rf.place(rf.polytope(r, dome_specs(P, r)), P, rot)
    rf.tidy(bm, weld=6e-3)
    rim = bm.faces.layers.int.new("rim")  # survives the wet-line bisects (which split bevel faces)
    for f in round_edges(bm, P):
        f[rim] = 1
    wet_zones(bm, P)
    rf.classify(bm, rot, [f for f in bm.faces if f[rim]], r)  # only its weathered-plane pick is used (rim strips excluded)
    rf.refine(bm, P["edge_len"])
    rf.distort(bm, P, off)
    bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method="BEAUTY")
    obj = nl.mesh_object(asset_id, bm)
    nl.finalize(obj, smooth_angle_deg=P["smooth"])
    nl.uv_unwrap(obj)
    me = obj.data
    fn = shore_colour(me, P, off, [r.uniform(0.96, 1.04) for _ in P["spokes"]])
    nl.paint(obj, fn)
    cav = rf.vertex_cavity(obj)
    nl.paint_data(obj, lambda poly, li, v: (cav[me.loops[li].vertex_index], 0.5))
    for name in ("cls", "grp", "warm", "zone", "rim"):
        me.attributes.remove(me.attributes[name])
    return obj


MAKERS_C["shore_boulder_A"] = make_shore
