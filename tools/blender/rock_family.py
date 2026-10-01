"""Geology family (plan 5.1): rock_shelf_A, boulder_large_A. Second wave (boulder_medium_A, rubble_cluster_A,
shore_boulder_A) lives in rock_family_b.py, the cliff modules (cliff_face_A, cliff_corner_A, revision 2 with tapered
ends) in rock_cliff.py; both reuse the helpers below and main() dispatches to them.

Planes first, noise last. Each asset is ONE convex mass (half-spaces from a shared fracture frame: bedding
normal + joint sets) that is then CARVED with convex cutters (set-backs, bedding steps, lowered tops) and
nicked by a few corner spalls. All specs below live in an "aligned" frame (x along the face, -y front, z along
the bedding normal); the whole mass is rotated into the frame (tilt/azimuth/yaw), placed, cut flat at the
embed depth, chamfered on selected edges, refined and only then distorted (<= 2 % of size). Flat shading.
    blender -b --factory-startup -P tools/blender/rock_family.py -- [asset_id ...]
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

GROUP = "rocks"
TOP, FRONT, SIDE, UNDER, OTHER, BEVEL = range(6)  # face classes (colour groups)
JIT = 1.0  # deg of gaussian jitter on every authored plane normal

# Plane spec: (kind, azimuth, lean_or_tilt, x, y, z). "wall": near-vertical face facing `azimuth` (0 = front -Y,
# 90 = +X, 180 = back) whose top leans inward by `lean`; "flat": bedding-like face whose normal tilts `tilt`
# from +Z toward `azimuth`. Rock side is n.p <= n.at; a leading "!" flips it (used by cutters: the removed side).
# Cutters carve where ALL their planes hold. Each joint plane belongs to exactly one cutter (no coincident planes).
PARAMS = {
    "rock_shelf_A": dict(
        family="rock_shelf", seed=2203, tilt=9.5, azimuth=80.0, yaw=-4.0, height=1.6, embed=0.8, front=0.7,
        bevel=0.045, edge_len=0.6, distort=0.05, distort_freq=0.32,
        mass=[("flat", 0, 1.2, 0, 0, 2.0), ("!flat", 0, 0, 0, 0, -2.5),
              ("wall", -62, 4, -3.7, 0, 0), ("wall", 100, 3, 3.8, 0, 0), ("wall", 125, 6, 3.0, 0.8, 0),
              ("wall", -10, 6, -0.6, -1.5, 0), ("wall", 4, 8, -0.6, -1.5, 0),       # dominant riser, kinked 14 deg
              ("flat", 172, 30, -1, 0.4, 2.0), ("flat", 192, 30, -1, 0.4, 2.0),    # kinked top-back ramp
              ("wall", 168, 4, -1, 2.2, 0), ("wall", 194, 4, -1, 2.2, 0)],
        carves=[
            [("wall", 112, 2, -2.4, -1.4, 0), ("!wall", -18, 6, -2.4, -0.85, 0)],   # left wing recedes, set back 0.35
            [("wall", 100, 1, -2.9, 0, 0), ("!flat", 0, 1.2, 0, 0, 1.65)],          # left end steps down 0.35
            [("wall", -105, 1, 0.9, 0, 0), ("!flat", 0, 1.0, 0, 0, 1.75)],          # block 1 top 0.25 lower
            [("wall", -100, 1, 1.25, 0, 0), ("!wall", 8, 8, 1.25, -1.05, 0)],       # block 1 set back 0.45
            [("wall", -108, 1, 2.9, 0, 0), ("!flat", 0, 1.2, 0, 0, 1.4)],           # block 2 top 0.6 lower
            [("wall", -110, 1, 3.2, 0, 0), ("!wall", 20, 9, 3.2, -0.4, 0)],         # block 2 set back, tapers
        ],
        unions=[dict(points=[(-2.8, -0.8), (-2.35, -1.95), (-0.7, -2.1), (0.55, -1.4), (0.5, -0.8)],  # toe slab, tilted top
                     z_top=(0.85, -0.09, 0.12), z_bottom=-2.5)],
        chips=[((-0.6, -0.5, 0.6), 0.25), ((0.1, -0.9, 0.45), 0.2), ((0.65, -0.45, 0.6), 0.18)],
        habitats=["meadow_edge", "rocky_slope", "trail_border"], collision={"class": "trimesh"},
        budget=(800, 3000), max_tilt=6.0, scale=(0.8, 1.25),
        notes="Steep riser 1.1-1.6 m with set-back left wing and two stepped-down right blocks, broken-off toe slab, "
              "top dips back ~9 deg into a back ramp (terrain/grass meets it). Origin 0.7 m behind the front, riser "
              "toward -Y.",
    ),
    "boulder_large_A": dict(
        family="boulder_large", seed=3301, tilt=11.0, azimuth=35.0, yaw=5.0, height=1.9, embed=0.4, front=None,
        bevel=0.04, edge_len=0.42, distort=0.03, distort_freq=0.5,
        mass=[("flat", 0, 1.5, 0, 0, 1.0), ("!flat", 0, 0, 0, 0, -1.4), ("flat", 75, 9, 0.35, 0.1, 0.9),  # 2nd top facet
              ("wall", -14, 9, -0.37, -0.86, 0), ("wall", 22, 14, 0.66, -0.78, 0), ("wall", 88, 8, 1.15, 0, 0),
              ("wall", 140, 20, 0.74, 0.57, 0), ("wall", 178, 13, 0, 0.82, 0), ("wall", -152, 10, -0.74, 0.62, 0),
              ("wall", -92, 12, -1.11, 0, 0)],
        carves=[
            [("wall", -130, 1, -0.99, 0, 0), ("!flat", 0, 1.0, 0, 0, 0.25), ("!wall", 176, 13, 0, 0.59, 0)],   # back step
            [("wall", 135, 1, -0.8, 0, 0), ("!flat", 0, 1.0, 0, 0, -0.15), ("!wall", -14, 9, -0.37, -0.52, 0)],  # toe
        ],
        chips=[((0.5, -0.5, 0.7), 0.4), ((-0.4, 0.5, 0.75), 0.22), ((0.9, 0.2, 0.3), 0.25)],
        habitats=["meadow", "forest_edge", "rocky_slope", "shore"], collision={"class": "convex"},
        budget=(600, 2000), max_tilt=12.0, scale=(0.7, 1.4),
        notes="Primary foreground rock: steep planes (<= 24 deg lean), one ~1.2 m bedding top, toe step and "
              "stepped back; same fracture frame as the cliff.",
    ),
}


def frame_matrix(P: dict) -> Matrix:
    """Bedding normal leans `tilt` deg toward `azimuth` (CCW from +X); `yaw` turns the joint sets."""
    az = math.radians(P["azimuth"])
    tilt = Matrix.Rotation(math.radians(P["tilt"]), 3, Vector((-math.sin(az), math.cos(az), 0.0)))
    return Matrix.Rotation(math.radians(P["yaw"]), 3, "Z") @ tilt


def jitter_dir(r, base: Vector, sigma_deg: float) -> Vector:
    t1 = base.orthogonal().normalized()
    t2 = base.cross(t1)
    a1, a2 = (math.radians(r.gauss(0.0, sigma_deg)) for _ in range(2))
    return (base + t1 * math.tan(a1) + t2 * math.tan(a2)).normalized()


def plane(spec) -> tuple[Vector, float]:
    kind, az, k, x, y, z = spec
    flip = kind.startswith("!")
    a, t = math.radians(az), math.radians(k)
    if kind.lstrip("!") == "wall":
        n = Vector((math.sin(a) * math.cos(t), -math.cos(a) * math.cos(t), math.sin(t)))
    else:
        n = Vector((math.sin(t) * math.sin(a), -math.sin(t) * math.cos(a), math.cos(t)))
    d = n.dot(Vector((x, y, z)))
    return (-n, -d) if flip else (n, d)


def facets(points: list, leans: list, flip: bool = False) -> list:
    """Plan polyline (left to right, front side) -> one wall spec per segment, outward normal toward -Y."""
    return [(("!" if flip else "") + "wall", math.degrees(math.atan2(y2 - y1, x2 - x1)), lean, x1, y1, 0)
            for (x1, y1), (x2, y2), lean in zip(points, points[1:], leans)]


def _hull(points: list[Vector]) -> bmesh.types.BMesh:
    bm = bmesh.new()
    for p in points:
        bm.verts.new(p)
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=2e-4)
    bmesh.ops.convex_hull(bm, input=bm.verts[:])
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(0.5), verts=bm.verts[:], edges=bm.edges[:])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return bm


def _cube_hull(half: float = 60.0) -> bmesh.types.BMesh:
    return _hull([Vector((sx, sy, sz)) * half for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)])


def clip(bm: bmesh.types.BMesh, n: Vector, d: float) -> bmesh.types.BMesh:
    """Keep the half-space n.x <= d of a convex mesh."""
    bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], dist=1e-6,
                           plane_co=n * d, plane_no=n, clear_outer=True)
    pts = [v.co.copy() for v in bm.verts]
    bm.free()
    return _hull(pts)


def polytope(r, specs: list, jitter: bool = True, half: float = 60.0) -> bmesh.types.BMesh:
    """Convex region where every plane holds; authored normals are jittered about the plane's foot point."""
    bm = _cube_hull(half)
    for spec in specs:
        n, d = spec if isinstance(spec[0], Vector) else plane(spec)
        if jitter:  # bedding-parallel floors/tops stay nearly parallel: crossing floors would leave sliver wedges
            n2 = jitter_dir(r, n, JIT * (0.35 if abs(n.z) > 0.9 else 1.0))
            n, d = n2, d * n2.dot(n)
        bm = clip(bm, n, d)
    return bm


def canonical(bm: bmesh.types.BMesh) -> bmesh.types.BMesh:
    """Rebuild with position-sorted vertices/faces: the exact boolean returns elements in a thread-dependent
    order, and every later random pick / triangulation tie would otherwise change between runs."""
    key = lambda v: tuple(round(c, 5) for c in v.co)  # noqa: E731
    out = bmesh.new()
    nv = {v: out.verts.new(v.co) for v in sorted(bm.verts, key=key)}
    loops = []
    for f in bm.faces:
        vs = list(f.verts)
        k = min(range(len(vs)), key=lambda i: key(vs[i]))
        loops.append(vs[k:] + vs[:k])
    for vs in sorted(loops, key=lambda vs: [key(v) for v in vs]):
        out.faces.new([nv[v] for v in vs])
    bm.free()
    return out


def boolean(a: bmesh.types.BMesh, b: bmesh.types.BMesh, op: str) -> bmesh.types.BMesh:
    objs = []
    for bm in (a, b):
        me = bpy.data.meshes.new("tmp")
        bm.to_mesh(me)
        bm.free()
        o = bpy.data.objects.new("tmp", me)
        bpy.context.scene.collection.objects.link(o)
        objs.append(o)
    mod = objs[0].modifiers.new("b", "BOOLEAN")
    mod.operation, mod.object, mod.solver = op, objs[1], "EXACT"
    bpy.context.view_layer.update()
    ev = bpy.data.meshes.new_from_object(objs[0].evaluated_get(bpy.context.evaluated_depsgraph_get()))
    out = bmesh.new()
    out.from_mesh(ev)
    bpy.data.batch_remove([ev, *objs, *(o.data for o in objs)])
    return canonical(out)


def tidy(bm: bmesh.types.BMesh, weld: float = 1e-4) -> None:
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=weld)
    bmesh.ops.dissolve_degenerate(bm, dist=1e-4, edges=bm.edges[:])
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context="VERTS")
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(0.5), verts=bm.verts[:], edges=bm.edges[:])


def island_count(bm: bmesh.types.BMesh) -> int:
    seen, n = set(), 0
    for v0 in bm.verts:
        n += v0 not in seen
        stack = [v0] if v0 not in seen else []
        while stack:
            v = stack.pop()
            if v not in seen:
                seen.add(v)
                stack.extend(e.other_vert(v) for e in v.link_edges)
    return n


def extent(bm: bmesh.types.BMesh) -> tuple[Vector, Vector]:
    cs = [v.co for v in bm.verts]
    return (Vector(min(c[i] for c in cs) for i in range(3)), Vector(max(c[i] for c in cs) for i in range(3)))


def spall(bm: bmesh.types.BMesh, r, spec, depth: float) -> bmesh.types.BMesh:
    """Corner spall, a planar cut facing the corner's mean normal. `spec` is a direction (the extreme corner of
    the mass along it) or ("near", (x, y, z)): the convex corner nearest that point, with the depth capped so the
    plane crosses every incident edge before its midpoint (a clean chipped corner, never a pit or a slot)."""
    bm.normal_update()
    if spec[0] != "near":
        n = jitter_dir(r, Vector(spec).normalized(), 6.0)
        top = max(v.co.dot(n) for v in bm.verts)
        return boolean(bm, polytope(r, [(-n, -(top - depth))], jitter=False), "DIFFERENCE")

    def corner(v) -> tuple[Vector, float]:
        n = sum((f.normal for f in v.link_faces), Vector()).normalized()
        return n, min(-(e.other_vert(v).co - v.co).dot(n) for e in v.link_edges)  # <= 0: concave

    at = Vector(spec[1])
    cands = [v for v in bm.verts if (v.co - at).length < 1.0 and corner(v)[1] > 0.3]
    if not cands:
        print(f"[rock_family] spall near {spec[1]}: no convex corner in reach, skipped")
        return bm
    v = min(cands, key=lambda q: (q.co - at).length)
    n0, reach = corner(v)
    n, depth = jitter_dir(r, n0, 6.0), min(depth, 0.45 * reach)
    c, big = v.co.copy(), 3.0 * depth + 0.5
    cut = [(-n, -n.dot(c - n * depth))]
    for i in range(3):
        e = Vector(tuple(1.0 if j == i else 0.0 for j in range(3)))
        cut += [(e, e.dot(c) + big), (-e, -(e.dot(c) - big))]
    return boolean(bm, polytope(r, cut, jitter=False), "DIFFERENCE")


def prism(u: dict) -> bmesh.types.BMesh:
    """Vertical prism over a plan polygon with a planar, tilted top z = z0 + kx*x + ky*y (a broken-off slab)."""
    z0, kx, ky = u["z_top"]
    pts = [Vector((x, y, z0 + kx * x + ky * y)) for x, y in u["points"]]
    return _hull(pts + [Vector((p.x, p.y, u["z_bottom"])) for p in pts])


def bench(r, b: dict) -> bmesh.types.BMesh:
    """Cutter for a bedding step: the region above one floor plane and outside a receding convex arc. One floor
    plane (no per-facet floors) keeps the ledge clean; convex ridges come from the arc, not from cutter unions."""
    slab = polytope(r, [("!flat", 0, 1.0, 0, 0, b["floor"])] + ([b["joint"]] if "joint" in b else []), half=70.0)
    return boolean(slab, polytope(r, facets(b["points"], b["leans"])), "DIFFERENCE")


def mass(P: dict, r) -> bmesh.types.BMesh:
    arc = P.get("arc")
    bm = polytope(r, P["mass"] + (facets(arc["points"], arc["leans"]) if arc else []))
    for extra in P.get("unions", []):
        bm = boolean(bm, prism(extra), "UNION")
        tidy(bm)
    cutter_bms = [bench(r, b) for b in P.get("benches", [])] + [polytope(r, c) for c in P.get("carves", [])]
    for cutter in cutter_bms:
        bm = boolean(bm, cutter, "DIFFERENCE")
        tidy(bm)
    for spec, depth in P["chips"]:
        bm = spall(bm, r, spec, depth)
        tidy(bm, weld=2e-3)
    if island_count(bm) != 1:
        raise RuntimeError(f"{island_count(bm)} disconnected pieces: a cutter severed the mass")
    return bm


def place(bm: bmesh.types.BMesh, P: dict, rot: Matrix) -> bmesh.types.BMesh:
    """Rotate into the fracture frame, set x/y origin and the visible height, cut flat at the embed depth."""
    bmesh.ops.transform(bm, matrix=rot.to_4x4(), verts=bm.verts)
    lo, hi = extent(bm)
    dy = -(lo.y + hi.y) / 2 if P["front"] is None else -P["front"] - lo.y
    bmesh.ops.translate(bm, vec=Vector((-(lo.x + hi.x) / 2, dy, P["height"] - hi.z)), verts=bm.verts)
    cut = _cube_hull(1.0)
    bmesh.ops.transform(cut, matrix=Matrix.Diagonal((60.0, 60.0, 20.0, 1.0)), verts=cut.verts)
    bmesh.ops.translate(cut, vec=Vector((0, 0, -P["embed"] - 20.0)), verts=cut.verts)
    bm = boolean(bm, cut, "DIFFERENCE")
    tidy(bm)
    return bm


def plane_groups(bm: bmesh.types.BMesh) -> tuple[dict, list]:
    """Flood-fill coplanar neighbours: face -> group id, and the member list per group."""
    bm.normal_update()
    gid, groups = {}, []
    for f0 in bm.faces:
        if f0 in gid:
            continue
        gid[f0] = len(groups)
        members, stack = [f0], [f0]
        while stack:
            f = stack.pop()
            for e in f.edges:
                for o in e.link_faces:
                    if o not in gid and f.normal.dot(o.normal) > 0.99995 \
                            and abs((o.calc_center_median() - f.calc_center_median()).dot(f.normal)) < 0.02:
                        gid[o] = gid[f0]
                        members.append(o)
                        stack.append(o)
        groups.append(members)
    return gid, groups


def chamfer(bm: bmesh.types.BMesh, P: dict) -> list:
    """Narrow 1-segment chamfer on long, strongly convex, exposed edges (never on back/connection faces)."""
    w = P["bevel"]
    edges = [e for e in bm.edges
             if len(e.link_faces) == 2 and e.calc_length() >= max(3.0 * w, 0.45)
             and e.calc_face_angle_signed(0.0) >= math.radians(50)
             and (e.verts[0].co + e.verts[1].co).z * 0.5 >= -0.15 and not any(f.normal.y > 0.2 for f in e.link_faces)]
    res = bmesh.ops.bevel(bm, geom=edges, offset=w, offset_type="OFFSET", segments=1,
                          profile=0.5, affect="EDGES", clamp_overlap=True)
    faces = list(res["faces"])
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=4e-3)  # bevel leaves mm-sized slivers at corners
    return [f for f in faces if f.is_valid]


def pick_warm(bm, gid: dict, groups: list, cls_of: dict, r) -> set:
    """One secondary vertical plane group of 1.2-4.5 % of the exposed area takes the weathered tint."""
    area = [sum(f.calc_area() for f in m if f.calc_center_median().z > -0.1) for m in groups]
    total = sum(area) or 1.0
    ok = [i for i, m in enumerate(groups) if cls_of[m[0]] in (FRONT, SIDE, OTHER) and 0.012 <= area[i] / total <= 0.035]
    if not ok:
        ok = [min((i for i, m in enumerate(groups) if cls_of[m[0]] in (FRONT, SIDE, OTHER) and area[i] / total > 0.005),
                  key=lambda i: abs(area[i] / total - 0.03))]
    return set(groups[r.choice(ok)])


def classify(bm: bmesh.types.BMesh, rot: Matrix, bevel_faces: list, r) -> None:
    """Colour class (cls), per-plane random (grp) and the weathered flag (warm); all survive refinement."""
    cls, grp, warm = (bm.faces.layers.int.new("cls"), bm.faces.layers.float.new("grp"), bm.faces.layers.int.new("warm"))
    ex, ey = rot @ Vector((1, 0, 0)), rot @ Vector((0, 1, 0))
    bev, value = set(bevel_faces), {}
    gid, groups = plane_groups(bm)
    cls_of = {}
    for f in bm.faces:
        n, h = f.normal, Vector((f.normal.x, f.normal.y, 0.0))
        if f in bev:
            c = BEVEL
        elif n.z > 0.62:
            c = TOP
        elif n.z < -0.30:
            c = UNDER
        elif h.length > 1e-6 and max(abs(h.dot(ex)), abs(h.dot(ey))) / h.length < 0.86:
            c = OTHER
        else:
            c = FRONT if abs(h.dot(ey)) >= abs(h.dot(ex)) else SIDE
        cls_of[f] = f[cls] = c
        f[grp] = value.setdefault(gid[f], r.random())
    for f in pick_warm(bm, gid, groups, cls_of, r):
        f[warm] = 1


def refine(bm: bmesh.types.BMesh, max_len: float) -> None:
    bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method="BEAUTY", ngon_method="BEAUTY")
    for _ in range(4):
        long = [e for e in bm.edges if e.calc_length() > max_len]
        if long:
            bmesh.ops.subdivide_edges(bm, edges=long, cuts=1, use_grid_fill=True)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])


def distort(bm: bmesh.types.BMesh, P: dict, off: Vector) -> None:
    """Low-amplitude, position-only (so watertight) distortion; zero at the embed cut plane."""
    amp, f = P["distort"], P["distort_freq"]
    for v in bm.verts:
        p = v.co.copy()
        w = min(1.0, max(0.0, (p.z + P["embed"]) / 0.5))
        d = Vector(noise.noise_vector(p * f + off)) * amp + Vector(noise.noise_vector(p * f * 2.9 + off * 1.7)) * amp * 0.3
        d.z *= 0.7
        v.co += d * w


def colour_fn(me: bpy.types.Mesh, off: Vector):
    rock, light, dark = nl.pal("rock"), nl.pal("rock_light"), nl.pal("rock_dark")
    base = {TOP: light, FRONT: rock, SIDE: nl.mix(rock, dark, 0.55), OTHER: nl.mix(rock, light, 0.35),
            UNDER: rock, BEVEL: nl.mix(light, rock, 0.35)}  # undercuts darken through UV2 cavity only
    weathered = nl.pal("rock_weathered")
    cls, grp, warm = me.attributes["cls"].data, me.attributes["grp"].data, me.attributes["warm"].data

    def fn(poly, li, v):
        c, g = cls[poly.index].value, grp[poly.index].value
        col = nl.scale_rgb(base[c], 0.94 + 0.12 * g)  # value steps between planes
        if warm[poly.index].value:
            col = nl.mix(col, weathered, 0.6)  # the one weathered plane
        p = Vector(v) + off
        col = nl.scale_rgb(col, 0.94 + 0.06 * (1.0 + noise.noise(p * 0.3)))  # broad patches, never speckle
        return (*col, 0.0)
    return fn


def vertex_cavity(obj: bpy.types.Object) -> list[float]:
    """Restrained cavity: concave creases and downward-facing undercuts, never below 0.62."""
    bm = bmesh.new()
    bm.from_mesh(obj.data)
    bm.normal_update()
    out = []
    for v in bm.verts:
        conc = sum(max(0.0, -e.calc_face_angle_signed(0.0)) for e in v.link_edges if len(e.link_faces) == 2)
        down = -sum(f.normal.z for f in v.link_faces) / max(len(v.link_faces), 1)
        out.append(max(0.62, 1.0 - 0.18 * min(conc, 1.0) - 0.16 * min(max(down, 0.0) / 0.6, 1.0)))
    bm.free()
    return out


def data_fn(obj: bpy.types.Object):
    cav, me = vertex_cavity(obj), obj.data
    return lambda poly, li, v: (cav[me.loops[li].vertex_index], me.attributes["grp"].data[poly.index].value)


def make_object(asset_id: str) -> bpy.types.Object:
    P = PARAMS[asset_id]
    nl.reset_scene()
    noise.seed_set(P["seed"])  # seed 0 (the default) means time-based, which made the noise non-deterministic
    r = nl.rng(P["seed"])
    off = Vector((r.uniform(0, 90), r.uniform(0, 90), r.uniform(0, 90)))
    rot = frame_matrix(P)
    bm = place(mass(P, r), P, rot)
    bev = chamfer(bm, P)
    classify(bm, rot, bev, r)
    refine(bm, P["edge_len"])
    distort(bm, P, off)
    bmesh.ops.triangulate(bm, faces=bm.faces[:], quad_method="BEAUTY")  # subdivision leaves quads
    obj = nl.mesh_object(asset_id, bm)
    nl.finalize(obj)
    nl.uv_unwrap(obj)
    nl.paint(obj, colour_fn(obj.data, off))
    nl.paint_data(obj, data_fn(obj))
    for name in ("cls", "grp", "warm"):
        obj.data.attributes.remove(obj.data.attributes[name])
    return obj


def build(asset_id: str) -> dict:
    P = PARAMS[asset_id]
    obj = make_object(asset_id)
    meta_keys = ("family", "seed", "habitats", "collision", "budget", "max_tilt", "scale", "notes")
    recipe = {"seed": P["seed"], "method": "one convex mass from fracture-frame planes, carved by convex cutters "
              "(set-backs, bedding steps, lowered tops), corner spalls, narrow chamfer, refine, distort",
              "params": {k: v for k, v in P.items() if k not in meta_keys}}
    meta = nl.export_asset(obj, GROUP, asset_id, family=P["family"], habitats=P["habitats"],
                           collision=P["collision"], budget_tris=P["budget"], embed_depth=P["embed"],
                           scale_range=P["scale"], max_tilt_deg=P["max_tilt"], recipe=recipe, notes=P["notes"])
    nl.render_previews(obj, GROUP, asset_id)
    nl.save_blend(GROUP, asset_id)
    return meta


def main() -> None:
    import rock_cliff  # cliff modules, revision 2 (replaces rock_family_b's cliff_corner_A)
    import rock_family_b  # second-wave assets (medium boulder, rubble, shore); keeps this file < 500 lines
    ids = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    for asset_id in ids or dict.fromkeys([*rock_cliff.PARAMS, *PARAMS, *rock_family_b.PARAMS_B]):
        if asset_id in rock_cliff.PARAMS:
            m = rock_cliff.build(asset_id)
        else:
            m = rock_family_b.build(asset_id) if asset_id in rock_family_b.PARAMS_B else build(asset_id)
        print(f"[rock_family] {asset_id}: tris={m['tris']} budget={m['budget_tris']} ok={m['within_budget']} "
              f"bbox={m['bbox_min']}..{m['bbox_max']} non_manifold={m['non_manifold_edges']}")


if __name__ == "__main__":
    main()
