"""reed_A (sheltered-shallows reed / sedge clump) for the understory family (plan 5.7). The shared Builder / finish
pipeline lives in understory_family.py; reed geometry is built on a Builder instance passed in by that script
(vertex, face, embed). The PARAMS table is finite and deterministic and is written to the metadata `recipe`.
"""
from __future__ import annotations

import math
import statistics

from mathutils import Vector

import nature_lib as nl

UP = Vector((0.0, 0.0, 1.0))
TAU = math.tau

# ---------------------------------------------------------------- reed_A (sheltered shallows)

REED_A = {
    "seed": 4509,
    "embed": 0.04,            # blade / stalk roots reach this far below z = 0 (waterline / bank)
    "blades": 18,
    # three sub-tufts inside the 0.30 x 0.40 m root area (footprint space: x across, y along): centre + blade count
    "tufts": [{"c": (-0.095, -0.135), "n": 6}, {"c": (0.095, 0.0), "n": 6}, {"c": (-0.075, 0.135), "n": 6}],
    "tuft_radius_m": 0.08, "min_spacing_m": 0.04,
    "footprint_yaw_deg": 28.0, "footprint_curve_m": 0.04,   # the root area is a slightly curved strip, not a disc
    "height_m": [0.42, 0.80],  # blade tip z range, ranked so the spread is always complete
    "centre_bias": 0.5, "height_noise": 0.3,    # taller toward each sub-tuft centre, but noisy
    "lean_dir_deg": 35.0, "lean_spread_deg": 20.0,   # shared lean azimuth of most blades
    "outlier_offsets_deg": [140.0, -125.0, 170.0],   # the short blades that lean another way
    "lean_base_deg": [1.5, 4.5], "bend_deg": [10.0, 34.0], "bend_pow": 1.4, "outlier_bend": 0.6,
    "joint_max_deg": 15.0,     # no joint kinks more than this: total bend is capped per segment count
    "splay_deg": [4.0, 21.0],  # extra lean away from the blade's own sub-tuft centre; outer blades splay most (V fan)
    "width_m": [0.028, 0.044],
    # width / base width per row (row 0 is the root), then a tip vertex; roots sheath into the base
    "profiles": {5: [0.6, 1.0, 0.9, 0.72, 0.5], 4: [0.6, 1.0, 0.85, 0.55], 3: [0.6, 1.0, 0.55], 2: [0.6, 0.85]},
    "seg5_above_m": 0.7, "seg4_above_m": 0.56, "seg3_above_m": 0.46, "face_yaw_deg": 30.0, "twist_deg": 16.0,
    # colour: root -> reed body over t < hold_root, body (reed pulled toward grass_root) to hold_body, then a short
    # blend to reed_tip; two dry blades are the only straw accents
    "value_jitter": 0.06, "body_mix": 0.28, "hold_root": 0.3, "hold_body": 0.65, "tip_mix": [0.35, 0.55],
    "dry_blades": 2, "dry_mix": 0.85,
    "up_blend": 0.6,
    "stalks": [   # base (x, y), apex z of the seed head, azimuth offset from the lean dir, final bend, head length
        {"base": (0.075, 0.04), "apex_m": 0.93, "az_off_deg": -4.0, "bend_deg": 22.0, "head_m": 0.10, "segs": 4},
        {"base": (-0.10, 0.08), "apex_m": 0.80, "az_off_deg": 14.0, "bend_deg": 20.0, "head_m": 0.085, "segs": 3},
        {"base": (-0.02, -0.14), "apex_m": 0.66, "az_off_deg": -18.0, "bend_deg": 22.0, "head_m": 0.07, "segs": 2},
    ],
    "stalk_lean_base_deg": 3.0, "stalk_bend_pow": 1.2, "stalk_radius_m": [0.010, 0.006], "head_radius_m": 0.0165,
}

REED_A_META = dict(
    family="reed", habitats=["sheltered_bank"], scale_range=(0.75, 1.3), max_tilt_deg=6, wind="reed",
    pivot="ground_contact", budget_tris=(80, 220),
    notes="Reed / sedge clump ~0.9 m: 18 tapered blades (roots sheath into the base) from three sub-tufts inside a compact "
          "0.3 x 0.4 m curved root strip (not a disc), unequal heights 0.42-0.80 m, each blade splayed 4-10 deg away "
          "from its sub-tuft so the clump fans into a V, most leaning the same way (~10-20 deg chord) with tips curving "
          "(bend capped per joint, no elbows); 3 thicker stalks with brown cattail-style seed heads (M_solid). Green "
          "reed body, short blend to reed_tip over the top third, two dry straw blades as the only pale accents. Roots "
          "start 4 cm below y=0 (embed_depth); place at the waterline, the lowest 0.1-0.2 m may sit under water. Custom "
          "normals 60% toward +Z, blade front faces the upper (inner) side. Flex 0 at the roots, 1 at the tips.")


def smooth(t: float) -> float:
    t = min(1.0, max(0.0, t))
    return t * t * (3.0 - 2.0 * t)


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def horiz(az: float) -> Vector:
    return Vector((math.cos(az), math.sin(az), 0.0))


# ---------------------------------------------------------------- reed geometry

def spine(base: Vector, az: float, lean0: float, bend: float, pow_: float, segs: int, z_top: float,
          side: Vector | None = None):
    """Curling spine: direction leans from `lean0` (rad from vertical) by `bend` toward azimuth `az`;
    `side` (horizontal) adds a constant splay. Returns points and per-segment directions; tip z is solved (z_top)."""
    dirs = []
    for k in range(segs):
        th = lean0 + bend * ((k + 0.5) / segs) ** pow_
        h = horiz(az) * math.sin(th) + (side if side is not None else Vector())
        dirs.append(Vector((h.x, h.y, math.cos(th))).normalized())
    seg_len = (z_top - base.z) / sum(d.z for d in dirs)
    pts = [Vector(base)]
    for d in dirs:
        pts.append(pts[-1] + d * seg_len)
    return pts, dirs


def root_points(r, p: dict) -> list[dict]:
    """Root positions: each blade belongs to one sub-tuft (disc around its centre, min-spaced), the strip is bent
    by `footprint_curve_m` and rotated by `footprint_yaw_deg`. `rn` = 0 at the sub-tuft centre .. 1 at its rim,
    `out` = unit vector away from the sub-tuft centre (world xy)."""
    raw: list[tuple[float, float, int, float, float]] = []
    for ti, T in enumerate(p["tufts"]):
        count = 0
        while count < T["n"]:
            ang, rad = r.uniform(0.0, TAU), p["tuft_radius_m"] * math.sqrt(r.random())
            ox, oy = rad * math.cos(ang), rad * math.sin(ang)
            q = (T["c"][0] + ox, T["c"][1] + oy)
            if all(math.hypot(q[0] - a[0], q[1] - a[1]) >= p["min_spacing_m"] for a in raw):
                raw.append((q[0], q[1], ti, ox, oy))
                count += 1
    yaw = math.radians(p["footprint_yaw_deg"])
    c, s = math.cos(yaw), math.sin(yaw)
    out = []
    for x, y, ti, ox, oy in raw:
        x += p["footprint_curve_m"] * ((y / 0.2) ** 2 - 0.33)
        o = Vector((ox * c - oy * s, ox * s + oy * c, 0.0))
        out.append({"x": x * c - y * s, "y": x * s + y * c, "fx": x, "fy": y, "tuft": ti,
                    "rn": min(1.0, o.length / p["tuft_radius_m"]), "out": o.normalized() if o.length > 0.012 else None})
    return out


def blade_heights(r, p: dict, pts: list[dict]) -> list[float]:
    """Heights by rank (full spread guaranteed); taller toward each sub-tuft centre but noisy, so no dome."""
    lo, hi = p["height_m"]
    raw = [(1.0 - p["centre_bias"] * q["rn"]) + r.uniform(-p["height_noise"], p["height_noise"]) for q in pts]
    order = sorted(range(len(pts)), key=lambda i: raw[i])
    out = [0.0] * len(pts)
    for rank, i in enumerate(order):
        out[i] = lerp(lo, hi, (rank / (len(pts) - 1)) ** 0.9)
    return out


def blade_colour(p: dict, t: float, tip: float, k: float, dry: float) -> tuple[float, float, float]:
    """Dark wet root -> green reed body -> short blend to reed_tip; dry blades go straw over the upper half."""
    body = nl.mix(nl.pal("reed"), nl.pal("grass_root"), p["body_mix"])
    root = nl.mix(nl.scale_rgb(body, 0.78), nl.pal("soil"), 0.12)
    if t < p["hold_root"]:
        c = nl.mix(root, body, smooth(t / p["hold_root"]))
    elif t < p["hold_body"]:
        c = body
    else:
        c = nl.mix(body, nl.pal("reed_tip"), tip * smooth((t - p["hold_body"]) / (1.0 - p["hold_body"])))
    if dry > 0.0:
        straw = nl.mix(nl.pal("reed_tip"), nl.pal("reed"), 0.3)
        c = nl.mix(c, straw, dry * smooth((t - 0.25) / 0.5))
    return nl.scale_rgb(c, k)


def capped_bend(p: dict, bend: float, segs: int) -> float:
    """Largest joint angle of a spine is bend * max increment of ((k + .5) / segs) ** pow."""
    f = [((k + 0.5) / segs) ** p["bend_pow"] for k in range(segs)]
    inc = max(f[i + 1] - f[i] for i in range(segs - 1))
    return min(bend, math.radians(p["joint_max_deg"]) / inc)


def add_blade(b, p: dict, base: Vector, az: float, lean0: float, bend: float, width: float, h: float,
              ref_az: float, twist: float, part: dict, side: Vector) -> Vector:
    segs = 5 if h > p["seg5_above_m"] else 4 if h > p["seg4_above_m"] else 3 if h > p["seg3_above_m"] else 2
    pts, dirs = spine(base, az, lean0, capped_bend(p, bend, segs), p["bend_pow"], segs, h, side)
    ref = horiz(ref_az)
    rows, widths = [], p["profiles"][segs]
    for k in range(segs + 1):
        T = dirs[0] if k == 0 else dirs[-1] if k == segs else (dirs[k - 1] + dirs[k]).normalized()
        front = (ref - T * ref.dot(T)).normalized()
        side_v = T.cross(front)
        phi = twist * k / segs
        side_v = side_v * math.cos(phi) + front * math.sin(phi)
        t = k / segs
        nrm = (UP * p["up_blend"] + front * (1.0 - p["up_blend"])).normalized()
        cav, flex = 1.0 - 0.22 * (1.0 - t) ** 2, t ** 1.3
        rgb = blade_colour(p, t, part["tip"], part["k"], part["dry"])
        if k == segs:
            rows.append([b.vert(pts[k], rgb, 1.0, cav, part["rnd"], nrm)])
        else:
            hw = widths[k] * width * 0.5
            rows.append([b.vert(pts[k] - side_v * hw, rgb, flex, cav, part["rnd"], nrm),
                         b.vert(pts[k] + side_v * hw, rgb, flex, cav, part["rnd"], nrm)])
    for a, c in zip(rows[:-2], rows[1:-1]):
        b.face([a[0], a[1], c[1], c[0]], b.fs, toward=ref)
    b.face([rows[-2][0], rows[-2][1], rows[-1][0]], b.fs, toward=ref)
    return pts[-1] - pts[0]


def add_blades(b, r, p: dict) -> tuple[list[dict], list[float]]:
    pts = root_points(r, p)
    heights = blade_heights(r, p, pts)
    lo, hi = p["height_m"]
    order = sorted(range(len(pts)), key=lambda i: heights[i])
    short = order[: int(len(pts) * 0.55)]
    outliers = dict(zip(r.sample(short, len(p["outlier_offsets_deg"])), p["outlier_offsets_deg"]))
    dry = set(r.sample(order[: len(pts) // 2], p["dry_blades"]))
    az0 = math.radians(p["lean_dir_deg"])
    chords = []
    for i, q in enumerate(pts):
        h = heights[i]
        f = (h - lo) / (hi - lo)
        off = outliers.get(i)
        az = az0 + math.radians(off + r.uniform(-12.0, 12.0) if off is not None
                                else r.uniform(-p["lean_spread_deg"], p["lean_spread_deg"]))
        bend = math.radians(lerp(*p["bend_deg"], min(1.0, 0.75 * f + 0.25 * r.random())))
        bend *= p["outlier_bend"] if off is not None else 1.0
        lean0 = math.radians(lerp(*p["lean_base_deg"], r.random()))
        splay_dir = q["out"] if q["out"] is not None else horiz(r.uniform(0.0, TAU))
        side = splay_dir * math.sin(math.radians(lerp(*p["splay_deg"], 0.3 * r.random() + 0.7 * q["rn"])))
        width = lerp(*p["width_m"], r.random()) * (0.85 + 0.3 * f)
        part = {"k": 1.0 + r.uniform(-p["value_jitter"], p["value_jitter"]), "tip": lerp(*p["tip_mix"], r.random()),
                "dry": p["dry_mix"] if i in dry else 0.0, "rnd": r.random()}
        ref_az = az + math.pi + math.radians(r.uniform(-p["face_yaw_deg"], p["face_yaw_deg"]))
        chord = add_blade(b, p, Vector((q["x"], q["y"], -p["embed"])), az, lean0, bend, width, h, ref_az,
                          math.radians(r.uniform(-p["twist_deg"], p["twist_deg"])), part, side)
        chords.append(math.degrees(math.acos(chord.normalized().z)))
    return pts, chords


def ring(centre: Vector, axis: Vector, radius: float, sides: int, rot: float):
    """Ring points plus their outward unit vectors, perpendicular to `axis`."""
    e1 = axis.cross(UP)
    e1 = (e1 if e1.length > 1e-3 else Vector((1.0, 0.0, 0.0))).normalized()
    e2 = axis.cross(e1)
    dirs = [e1 * math.cos(rot + TAU * k / sides) + e2 * math.sin(rot + TAU * k / sides) for k in range(sides)]
    return [centre + d * radius for d in dirs], dirs


def outward(verts: list, origin: Vector, axis: Vector) -> Vector:
    """Direction from the axis through `origin` to the centre of `verts` (radial part only)."""
    d = sum((v.co for v in verts), Vector()) / len(verts) - origin
    return d - axis * d.dot(axis)


def head_colours(p: dict) -> tuple[tuple, tuple]:
    base = nl.mix(nl.pal("soil"), nl.pal("bark_dark"), 0.25)
    return base, nl.mix(nl.pal("soil"), nl.pal("reed_tip"), 0.3)


def add_head(b, r, p: dict, S: dict, top: Vector, axis: Vector, rnd: float) -> None:
    """Cattail-style seed head, 14 tris: a short base cap just wider than the stalk, a near-cylinder up to a blunt
    apex (M_solid). The cap sits on the stalk top, so it is never seen as an open rim."""
    R, ln = p["head_radius_m"] * (S["head_m"] / 0.1) ** 0.5, S["head_m"]
    base, tipc = head_colours(p)
    spec = [(0.0, 0.8, base, 0.9), (0.82, 0.95, nl.mix(base, tipc, 0.4), 1.0)]
    rot = r.uniform(0.0, TAU)
    rings = []
    for u, rad, rgb, cav in spec:
        pts, dirs = ring(top + axis * (ln * u), axis, R * rad, 4, rot)
        rings.append([b.vert(pt, rgb, 1.0, cav, rnd, (UP * 0.5 + d * 0.5).normalized()) for pt, d in zip(pts, dirs)])
    apex = b.vert(top + axis * ln, tipc, 1.0, 1.0, rnd, axis)
    for k in range(4):
        quad = [rings[0][k], rings[0][(k + 1) % 4], rings[1][(k + 1) % 4], rings[1][k]]
        b.face(quad, 0, toward=outward(quad, top, axis))
        tri = [rings[1][k], rings[1][(k + 1) % 4], apex]
        b.face(tri, 0, toward=outward(tri, top, axis) + axis * 0.3)
    b.face(rings[0], 0, toward=-axis)


def add_stalk(b, r, p: dict, S: dict, az0: float) -> None:
    az = az0 + math.radians(S["az_off_deg"])
    bend, lean0, sides = math.radians(S["bend_deg"]), math.radians(p["stalk_lean_base_deg"]), 3
    final_dir = Vector((math.sin(lean0 + bend) * math.cos(az), math.sin(lean0 + bend) * math.sin(az),
                        math.cos(lean0 + bend)))
    z_top = S["apex_m"] - S["head_m"] * final_dir.z   # stalk ends where the head starts
    pts, dirs = spine(Vector((S["base"][0], S["base"][1], -p["embed"])), az, lean0, bend, p["stalk_bend_pow"],
                      S["segs"], z_top)
    rnd, rot = r.random(), r.uniform(0.0, TAU)
    body = nl.mix(nl.pal("reed"), nl.pal("grass_root"), p["body_mix"])
    low = nl.mix(body, nl.pal("soil"), 0.1)
    high = nl.mix(head_colours(p)[0], body, 0.2)   # darkens toward the head so the two read as one piece
    rings = []
    for k, pt in enumerate(pts):
        t = k / S["segs"]
        T = dirs[0] if k == 0 else dirs[-1] if k == S["segs"] else (dirs[k - 1] + dirs[k]).normalized()
        ps, ds = ring(pt, T, lerp(*p["stalk_radius_m"], t), sides, rot)
        rings.append([b.vert(q, nl.mix(low, high, smooth(t)), t ** 1.3, 0.9, rnd,
                             (UP * p["up_blend"] + d * (1.0 - p["up_blend"])).normalized())
                      for q, d in zip(ps, ds)])
    for i, (ra, rb) in enumerate(zip(rings[:-1], rings[1:])):
        for k in range(sides):
            quad = [ra[k], ra[(k + 1) % sides], rb[(k + 1) % sides], rb[k]]
            b.face(quad, b.fs, toward=outward(quad, pts[i], dirs[i]))
    add_head(b, r, p, S, pts[-1], dirs[-1], rnd)


def build_reed_mesh(b, p: dict) -> dict:
    """Blades, then stalks with heads. Returns measurements for the metadata recipe."""
    r = nl.rng(p["seed"])
    pts, chords = add_blades(b, r, p)
    for S in p["stalks"]:
        add_stalk(b, r, p, S, math.radians(p["lean_dir_deg"]))
    fx, fy = [q["fx"] for q in pts], [q["fy"] for q in pts]
    return {"root_area_oriented_m": [round(max(fx) - min(fx), 3), round(max(fy) - min(fy), 3)],
            "blade_chord_lean_deg": [round(min(chords), 1), round(statistics.median(chords), 1), round(max(chords), 1)]}
