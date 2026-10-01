"""Meadow groundcover additions (plan 5.5, visual target R03): grass_short_B (swept), grass_short_C
(low spreading), grass_tall_A (margin grass with seed stalks). flower_pink_A lives in groundcover_pink.py.

They continue grass_short_A: broad tapered blades, 2-4 rows, custom normals toward +Z, flex 0 root -> 1 tip,
no ground disc, no radial skirt. Registered into groundcover_family.ASSETS; run through that script.
  blade   tapered strip (add_blade): width axis stays horizontal so lying blades never stand on edge
  stalk   bowed 2-quad strip ending in a 3-sided seed head (grass_tall_A)
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nature_lib as nl  # noqa: E402
from groundcover_kit import (  # noqa: E402
    TAU, Parts, blade_heights, footprint_slots, grass_color, grass_data, lerp, smooth)

PROFILES = {"profile_3seg": [1.0, 0.80, 0.46], "profile_2seg": [1.0, 0.52], "profile_4seg": [1.0, 0.88, 0.68, 0.42],
            "profile_5seg": [1.0, 0.92, 0.78, 0.60, 0.38]}

PARAMS = {
    # Coherent lean toward sweep_az, taller blades arch further; counter blades on the lee side lean back.
    "grass_short_B": {
        "seed": 5502, "blades": 11,
        "footprint_m": [0.14, 0.17], "footprint_yaw_deg": 24.0,
        "height_m": [0.18, 0.30], "width_m": [0.032, 0.050], **PROFILES, "four_row_above_m": 0.26,
        "sweep_az_deg": 14.0, "sweep_jitter_deg": 19.0,
        "lean_base_deg": [10.0, 22.0], "bend_deg": [18.0, 36.0], "bend_exp": 1.2,
        "counter": 3, "counter_height_m": 0.22, "counter_lean_deg": [12.0, 20.0], "counter_bend_deg": [10.0, 22.0],
        "tall_side_deg": 194.0, "centre_bias": 0.2, "height_noise": 0.45,
        "roll_deg": 25.0, "twist_deg": 14.0, "swirl_deg": [0.0, 12.0], "three_segment_fraction": 0.6,
        "value_jitter": 0.07, "dry_blades": 1, "dry_mix": 0.38, "up_blend": 0.7,
    },
    # Three sub-tufts along a short root line (yaw 30 deg, ~0.1 m) share one sprawl: 7 of 12 blades fall in a 140 deg
    # sector perpendicular to the line, the rest lie the other way or flare off the line ends, shorter. crown =
    # slim arching fountain blade (0.20-0.24 m, ~0.15 m tall), mid = drooping, low = outermost blade, nearly lying,
    # arched and banked so it shows area from the side. Every class is >= 5:1 length to base width and rises from a
    # low lean (no upright blade); blades curve in plan (swirl) and wind uniformly (top_facing).
    "grass_short_C": {
        "seed": 5503, "sector_az_deg": 115.0, "sector_span_deg": 140.0, "az_jitter_deg": 7.0, "sector_len_gain": 0.07,
        "tufts": [
            {"c": [-0.040, -0.023], "blades": [["crown", 128.0], ["mid", 176.0], ["low", 210.0], ["mid", 82.0]]},
            {"c": [0.0, 0.0], "blades": [["crown", 62.0], ["mid", 240.0], ["low", 300.0], ["mid", 140.0]]},
            {"c": [0.040, 0.023], "blades": [["crown", 20.0], ["mid", 104.0], ["low", 70.0], ["low", 330.0]]},
        ],
        "classes": {
            "crown": {"lean_deg": [20.0, 27.0], "bend_deg": [42.0, 56.0], "bend_exp": 1.0, "length_m": [0.20, 0.23],
                      "width_m": [0.026, 0.032], "root_out_m": 0.004, "segs": 4, "bank_deg": [0.0, 8.0]},
            "mid": {"lean_deg": [38.0, 48.0], "bend_deg": [30.0, 42.0], "bend_exp": 1.0, "length_m": [0.16, 0.20],
                    "width_m": [0.024, 0.029], "root_out_m": 0.008, "segs": 3, "bank_deg": [6.0, 16.0]},
            "low": {"lean_deg": [54.0, 62.0], "bend_deg": [16.0, 28.0], "bend_exp": 1.0, "length_m": [0.14, 0.18],
                    "width_m": [0.024, 0.028], "root_out_m": 0.014, "segs": 4, "bank_deg": [20.0, 30.0]},
        },
        **PROFILES, "zmin_m": 0.022, "twist_deg": 10.0, "swirl_deg": [18.0, 42.0],
        "value_jitter": 0.07, "dry_blades": 1, "dry_mix": 0.34, "up_blend": 0.7,
    },
    # Fountain of long narrow blades (darker base, cooler green, dry tips), four of them folding over at the
    # top, plus seed stalks that stand clear of the blades.
    "grass_tall_A": {
        "seed": 5504, "blades": 13,
        "footprint_m": [0.085, 0.110], "footprint_yaw_deg": 28.0,
        "height_m": [0.30, 0.54], "width_m": [0.018, 0.028],
        "profile_5seg": [1.0, 0.97, 0.86, 0.66, 0.40], "profile_4seg": [1.0, 0.95, 0.74, 0.42], "profile_3seg": [1.0, 0.82, 0.48],
        "lean_base_deg": [3.0, 14.0], "bend_deg": [14.0, 34.0], "bend_exp": 1.6, "outward": 0.6, "scatter": 0.5,
        "tall_side_deg": 70.0, "centre_bias": 0.35, "height_noise": 0.4,
        "bent": 4, "bent_height_m": 0.44, "bent_lean_deg": [4.0, 12.0], "bent_bend_deg": [50.0, 70.0], "bent_exp": 2.3,
        "roll_deg": 25.0, "twist_deg": 12.0, "swirl_deg": [0.0, 10.0], "value_jitter": 0.06, "dry_blades": 3, "dry_mix": 0.85, "up_blend": 0.7,
        "stalk_base_spread_m": 0.016, "stalk_width_m": [0.0075, 0.0055, 0.0042], "stalk_up_blend": 0.6,
        # Colour: root held dark to t = hold_t, mid pulled toward fern_deep/pine (cooler), tip toward pine_tip.
        "colour": {"root_fern": 0.5, "root_scale": 0.63, "hold_t": 0.35, "mid_fern": 0.5, "mid_pine": 0.7,
                   "mid_scale": 1.0, "tip_pine": 0.6},
        "stalks": [
            {"az_deg": 215.0, "height_m": 0.535, "lean_deg": 5.0, "bend_deg": 22.0, "head_len_m": 0.074, "head_r_m": 0.0105, "nod_deg": 26.0},
            {"az_deg": 330.0, "height_m": 0.475, "lean_deg": 7.0, "bend_deg": 30.0, "head_len_m": 0.064, "head_r_m": 0.0095, "nod_deg": 32.0},
            {"az_deg": 95.0, "height_m": 0.425, "lean_deg": 9.0, "bend_deg": 34.0, "head_len_m": 0.056, "head_r_m": 0.0090, "nod_deg": 38.0},
        ],
    },
}


# ------------------------------------------------------------------ geometry

def _spine(base: Vector, az: float, lean0: float, bend: float, exp: float, segs: int, length: float, swirl: float = 0.0):
    """Per-segment directions, points and azimuths; the direction swings from lean0 by `bend` toward
    azimuth az, which itself drifts by `swirl` along the blade so it curves in plan view."""
    dirs, azs = [], []
    for k in range(segs):
        f = (k + 0.5) / segs
        th, a = lean0 + bend * f ** exp, az + swirl * f
        dirs.append(Vector((math.sin(th) * math.cos(a), math.sin(th) * math.sin(a), math.cos(th))))
        azs.append(a)
    pts = [Vector(base)]
    for d in dirs:
        pts.append(pts[-1] + d * (length / segs))
    return dirs, pts, azs


def _face_fixed(P: Parts, verts: list, kind: str, part: int) -> None:
    """Face with the vertex order as given (no per-face flip), so winding stays uniform along a blade."""
    P.bm.faces.new(verts)
    P.finfo.append({"kind": kind, "part": part, "smooth": part})


def add_blade(P: Parts, base: Vector, az: float, lean0: float, bend: float, widths: tuple, part: int, *,
              length=None, height=None, zmin=None, bend_exp=1.3, roll=0.0, twist=0.0, swirl=0.0, tip=True, kind="blade",
              bank=0.0, top_facing=False):
    """Tapered blade. tip=True: len(widths) rows then one tip vertex; tip=False: len(widths) rows, all quads
    (stalks). `height` fixes the highest spine point (arching blades peak below their tip); `zmin` shrinks the
    bend until the spine beyond its first segment stays above the ground; `bank` rolls every row but the root about the blade axis so a
    lying blade shows width from the side as well as from above. `top_facing`: every face winds so its geometric normal
    is the blade's upper side (T x side), also where the blade has bent past horizontal; the default tests each face against a
    fixed outward vector, which flips faces of strongly arching blades. Returns (end point, end direction)."""
    segs = len(widths) if tip else len(widths) - 1
    if height is not None:
        length = height / max(q.z for q in _spine(base, az, lean0, bend, bend_exp, segs, 1.0)[1])
    dirs, pts, azs = _spine(base, az, lean0, bend, bend_exp, segs, length, swirl)
    while zmin is not None and bend > 0.02 and min(q.z for q in pts[2:]) < zmin:
        bend *= 0.92
        dirs, pts, azs = _spine(base, az, lean0, bend, bend_exp, segs, length, swirl)
    expect = Vector((math.cos(az), math.sin(az), 0.35))
    rows = []
    for k in range(segs + 1):
        T = dirs[min(k, segs - 1)] if k in (0, segs) else (dirs[k - 1] + dirs[k]).normalized()
        ak = azs[min(k, segs - 1)] if k in (0, segs) else 0.5 * (azs[k - 1] + azs[k])
        w0 = Vector((-math.sin(ak + roll), math.cos(ak + roll), 0.0))
        side = (w0 - T * w0.dot(T)).normalized()
        if k == 0:
            side.z = 0.0  # base row stays on the ground plane
            side.normalize()
        phi = twist * k / segs + (bank if k > 0 else 0.0)
        side = side * math.cos(phi) + T.cross(side) * math.sin(phi)
        if tip and k == segs:
            rows.append([P.vert(pts[k], kind, part, 1.0)])
        else:
            hw = widths[k] * 0.5
            rows.append([P.vert(pts[k] - side * hw, kind, part, k / segs), P.vert(pts[k] + side * hw, kind, part, k / segs)])
    for k in range(segs - (1 if tip else 0)):
        a, b = rows[k], rows[k + 1]
        if top_facing:
            _face_fixed(P, [a[0], b[0], b[1], a[1]], kind, part)
        else:
            P.face([a[0], a[1], b[1], b[0]], expect, kind, part, part)
    if tip:
        r = rows[segs - 1]
        if top_facing:
            _face_fixed(P, [r[1], r[0], rows[segs][0]], kind, part)
        else:
            P.face([r[0], r[1], rows[segs][0]], expect, kind, part, part)
    return pts[-1], dirs[-1]


def basis(axis: Vector) -> tuple[Vector, Vector]:
    e1 = axis.cross(Vector((1.0, 0.0, 0.0)))
    e1 = (e1 if e1.length > 1e-3 else axis.cross(Vector((0.0, 1.0, 0.0)))).normalized()
    return e1, axis.cross(e1)


def add_spindle(P: Parts, base: Vector, d: Vector, length: float, radius: float, part: int) -> None:
    """3-sided seed head: point, ring at 42 % of the length, point."""
    e1, e2 = basis(d)
    mid = base + d * (length * 0.42)
    dirs = [e1 * math.cos(TAU * j / 3) + e2 * math.sin(TAU * j / 3) for j in range(3)]
    bot, top = P.vert(base, "head", part, 0.0), P.vert(base + d * length, "head", part, 1.0)
    ring = [P.vert(mid + u * radius, "head", part, 0.45) for u in dirs]
    for j in range(3):
        n = (j + 1) % 3
        outward = dirs[j] + dirs[n]
        P.face([bot, ring[j], ring[n]], outward, "head", part, part)
        P.face([ring[j], ring[n], top], outward, "head", part, part)


def add_bud(P: Parts, C: Vector, axis: Vector, radius: float, length: float, part: int) -> None:
    e1, e2 = basis(axis)
    dirs = [e1 * math.cos(TAU * j / 3) + e2 * math.sin(TAU * j / 3) for j in range(3)]
    ring = [P.vert(C + u * radius, "bud", part, 1.0) for u in dirs]
    apex = P.vert(C + axis * length, "bud", part, 1.0)
    for j in range(3):
        P.face([ring[j], ring[(j + 1) % 3], apex], dirs[j] + dirs[(j + 1) % 3], "bud", part, part)


def along(pts: list[Vector], s: float) -> tuple[Vector, Vector]:
    """Point and tangent on the polyline `pts` (equal parameter per segment) at s in 0..1."""
    n = len(pts) - 1
    k = min(int(s * n), n - 1)
    f = s * n - k
    return pts[k].lerp(pts[k + 1], f), (pts[k + 1] - pts[k]).normalized()


# ------------------------------------------------------------------ grass B / C

def _swirl(r, p: dict, scale: float = 1.0) -> float:
    return math.radians(lerp(*p["swirl_deg"], r.random())) * r.choice((-1.0, 1.0)) * scale


def _blade_widths(r, p: dict, u: float, segs: int) -> tuple:
    w = lerp(*p["width_m"], r.random()) * (0.85 + 0.3 * u)
    return tuple(w * f for f in p[f"profile_{segs}seg"])


def build_swept(p: dict) -> Parts:
    r, P = nl.rng(p["seed"]), Parts()
    slots = footprint_slots(r, p)
    heights = blade_heights(r, p, slots)
    sweep, (hlo, hhi) = math.radians(p["sweep_az_deg"]), p["height_m"]
    lee = [i for i, s in enumerate(slots) if s[0] * math.cos(sweep) + s[1] * math.sin(sweep) > 0.0]
    counter = set(sorted(lee, key=lambda i: abs(heights[i] - p["counter_height_m"]))[:p["counter"]])
    outer_short = sorted((i for i, s in enumerate(slots) if s[2] > 0.6 and i not in counter), key=lambda i: heights[i])
    dry = set(outer_short[:p["dry_blades"]])
    for i, (x, y, rn, _th) in enumerate(slots):
        h = heights[i]
        u = (h - hlo) / (hhi - hlo)
        if i in counter:
            az = sweep + math.pi + math.radians(r.uniform(-28.0, 28.0))
            lean0, bend = (math.radians(lerp(*p[k], r.random())) for k in ("counter_lean_deg", "counter_bend_deg"))
        else:
            az = sweep + math.radians(r.uniform(-p["sweep_jitter_deg"], p["sweep_jitter_deg"]))
            lean0 = math.radians(lerp(*p["lean_base_deg"], 0.5 * u + 0.5 * r.random()))
            bend = math.radians(lerp(*p["bend_deg"], 0.6 * u + 0.4 * r.random()))
        segs = 4 if h > p["four_row_above_m"] else 3 if (h > 0.24 or r.random() < p["three_segment_fraction"]) else 2
        part = P.part(k=1.0 + r.uniform(-p["value_jitter"], p["value_jitter"]),
                      dry=p["dry_mix"] if i in dry else 0.0, rand=r.random())
        add_blade(P, Vector((x, y, 0.0)), az, lean0, bend, _blade_widths(r, p, u, segs), part, height=h,
                  bend_exp=p["bend_exp"], roll=math.radians(r.uniform(-p["roll_deg"], p["roll_deg"])),
                  twist=math.radians(r.uniform(-p["twist_deg"], p["twist_deg"])), swirl=_swirl(r, p))
    return P


def build_spread(p: dict) -> Parts:
    r, P = nl.rng(p["seed"]), Parts()
    sector = math.radians(p["sector_az_deg"])
    specs = [(t["c"], cls, az) for t in p["tufts"] for cls, az in t["blades"]]
    dry = r.choice([i for i, (_c, cls, _a) in enumerate(specs) if cls == "low"])
    for i, (c0, name, az_deg) in enumerate(specs):
        c = p["classes"][name]
        az = math.radians(az_deg + r.uniform(-p["az_jitter_deg"], p["az_jitter_deg"]))
        length = lerp(*c["length_m"], r.random()) * (1.0 + p["sector_len_gain"] * math.cos(az - sector))
        base = Vector((c0[0] + math.cos(az) * c["root_out_m"], c0[1] + math.sin(az) * c["root_out_m"], 0.0))
        part = P.part(k=1.0 + r.uniform(-p["value_jitter"], p["value_jitter"]),
                      dry=p["dry_mix"] if i == dry else 0.0, rand=r.random())
        width = lerp(*c["width_m"], r.random())
        add_blade(P, base, az, math.radians(lerp(*c["lean_deg"], r.random())),
                  math.radians(lerp(*c["bend_deg"], r.random())),
                  tuple(width * f for f in p[f"profile_{c['segs']}seg"]), part, length=length,
                  zmin=p["zmin_m"], bend_exp=c["bend_exp"],
                  bank=math.radians(lerp(*c["bank_deg"], r.random())) * r.choice((-1.0, 1.0)), top_facing=True,
                  twist=math.radians(r.uniform(-p["twist_deg"], p["twist_deg"])), swirl=_swirl(r, p))
    return P


# ------------------------------------------------------------------ grass tall

def add_stalk(P: Parts, r, p: dict, s: dict) -> None:
    """Seed stalk: bowed 2-quad strip, then a nodding 3-sided head in the dry colour."""
    sk = P.part(k=1.0 + r.uniform(-0.04, 0.04), rand=r.random())
    base = Vector((r.uniform(-1, 1), r.uniform(-1, 1), 0.0)) * p["stalk_base_spread_m"]
    az = math.radians(s["az_deg"])
    end, d = add_blade(P, base, az, math.radians(s["lean_deg"]), math.radians(s["bend_deg"]),
                       tuple(p["stalk_width_m"]), sk, height=s["height_m"], bend_exp=2.0, tip=False, kind="stalk",
                       roll=math.radians(r.uniform(-30.0, 30.0)))
    th = math.acos(max(-1.0, min(1.0, d.z))) + math.radians(s["nod_deg"])
    head_dir = Vector((math.sin(th) * math.cos(az), math.sin(th) * math.sin(az), math.cos(th)))
    add_spindle(P, end, head_dir, s["head_len_m"], s["head_r_m"], P.part(k=1.0 + r.uniform(-0.05, 0.05), rand=r.random()))


def build_tall(p: dict) -> Parts:
    r, P = nl.rng(p["seed"]), Parts()
    slots = footprint_slots(r, p)
    heights = blade_heights(r, p, slots)
    hlo, hhi = p["height_m"]
    outer = [i for i, s in enumerate(slots) if s[2] > 0.5]
    bent = set(sorted(outer, key=lambda i: abs(heights[i] - p["bent_height_m"]))[:p["bent"]])
    dry = set(sorted((i for i in outer if i not in bent), key=lambda i: -heights[i])[:p["dry_blades"]])
    for i, (x, y, rn, _th) in enumerate(slots):
        h, u = heights[i], (heights[i] - hlo) / (hhi - hlo)
        out = Vector((x, y)).normalized() if rn > 0.3 else Vector((r.uniform(-1, 1), r.uniform(-1, 1))).normalized()
        v = out * (p["outward"] * (0.6 + 0.4 * rn)) + Vector((r.uniform(-1, 1), r.uniform(-1, 1))) * p["scatter"]
        if i in bent:
            lean0, bend, exp = (math.radians(lerp(*p["bent_lean_deg"], r.random())),
                                math.radians(lerp(*p["bent_bend_deg"], r.random())), p["bent_exp"])
        else:
            lean0 = math.radians(lerp(*p["lean_base_deg"], rn * r.uniform(0.6, 1.0)))
            bend = math.radians(lerp(*p["bend_deg"], 0.6 * rn + 0.4 * r.random()))
            exp = p["bend_exp"]
        segs = 5 if i in bent else 4 if h > 0.40 else 3
        part = P.part(k=1.0 + r.uniform(-p["value_jitter"], p["value_jitter"]),
                      dry=p["dry_mix"] if i in dry else 0.0, rand=r.random())
        add_blade(P, Vector((x, y, 0.0)), math.atan2(v.y, v.x), lean0, bend, _blade_widths(r, p, u, segs), part,
                  height=h, bend_exp=exp, roll=math.radians(r.uniform(-p["roll_deg"], p["roll_deg"])),
                  twist=math.radians(r.uniform(-p["twist_deg"], p["twist_deg"])), swirl=_swirl(r, p, 2.0 if i in bent else 1.0))
    for s in p["stalks"]:
        add_stalk(P, r, p, s)
    return P


def tall_palette(p: dict) -> dict:
    """Cooler, bluer and darker than short grass: greens pulled toward fern_deep/pine, root held dark."""
    c = p["colour"]
    mid = nl.mix(nl.mix(nl.pal("grass"), nl.pal("fern_deep"), c["mid_fern"]), nl.pal("pine"), c["mid_pine"])
    return {"root": nl.scale_rgb(nl.mix(nl.pal("grass_root"), nl.pal("fern_deep"), c["root_fern"]), c["root_scale"]),
            "mid": nl.scale_rgb(mid, c["mid_scale"]),
            "tip": nl.mix(nl.pal("grass_tip"), nl.pal("pine_tip"), c["tip_pine"])}


def tall_color(v: dict, fi: dict, P: Parts, p: dict) -> tuple:
    part, t, kind = P.parts[v["part"]], v["t"], fi["kind"]
    if kind == "head":
        return (*nl.scale_rgb(nl.mix(nl.scale_rgb(nl.pal("grass_dry"), 0.9), nl.scale_rgb(nl.pal("grass_dry"), 1.06), t), part["k"]), 1.0)
    pal, hold = tall_palette(p), p["colour"]["hold_t"]
    if kind == "stalk":
        c = nl.mix(nl.mix(pal["root"], pal["mid"], smooth((t - hold) / 0.5)), nl.pal("grass_dry"), smooth((t - 0.45) / 0.55))
        return (*nl.scale_rgb(c, part["k"]), t ** 1.2)
    c = nl.mix(pal["root"], pal["mid"], smooth((t - hold) / 0.4)) if t < 0.75 else nl.mix(pal["mid"], pal["tip"], smooth((t - 0.75) / 0.25))
    if part["dry"] > 0.0:
        c = nl.mix(c, nl.pal("grass_dry"), part["dry"] * smooth((t - 0.5) / 0.4))
    return (*nl.scale_rgb(c, part["k"]), t ** 1.3)


def tall_data(v: dict, fi: dict, P: Parts, p: dict) -> tuple:
    cav = 1.0 if fi["kind"] == "head" else 1.0 - 0.25 * (1.0 - v["t"]) ** 2
    return (cav, P.parts[v["part"]]["rand"])


ASSETS = {
    "grass_short_B": {
        "build": build_swept, "color": grass_color, "data": grass_data, "family": "grass_short",
        "habitats": ["meadow", "forest_edge"], "budget": (30, 100), "scale": (0.8, 1.3), "tilt": 15.0,
        "wind": "grass", "up_blend": lambda p: {"blade": p["up_blend"]},
        "notes": "Swept variant B: blades lean coherently to one side, taller blades arch further, 3 counter blades on the lee side.",
    },
    "grass_short_C": {
        "build": build_spread, "color": grass_color, "data": grass_data, "family": "grass_short",
        "habitats": ["meadow", "forest_edge"], "budget": (30, 100), "scale": (0.8, 1.3), "tilt": 15.0,
        "wind": "grass", "up_blend": lambda p: {"blade": p["up_blend"]},
        "notes": "Low spreading variant C: 3 sub-tufts sharing one sprawl sector; 3 arching crown blades (~0.15 m tall), drooping mid blades, banked near-lying outer blades; no upright blade; uniform blade winding.",
    },
    "grass_tall_A": {
        "build": build_tall, "color": tall_color, "data": tall_data, "family": "grass_tall",
        "habitats": ["sheltered_bank", "forest_edge", "meadow_edge"], "budget": (60, 160), "scale": (0.8, 1.3), "tilt": 10.0,
        "wind": "grass", "up_blend": lambda p: {"blade": p["up_blend"], "stalk": p["stalk_up_blend"], "head": 0.5},
        "notes": "Tall margin grass: fountain of narrow blades (4 fold over), darker cooler colour with dry tips, 3 seed stalks with nodding heads.",
    },
}
