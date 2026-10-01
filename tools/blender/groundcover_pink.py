"""flower_pink_A (plan 5.6, visual target R03): clustered pink spikes. Registered into groundcover_family.ASSETS.

Four stems of unequal height splay outward (different azimuth and lean, so no two spikes run parallel). Each stem is a
2-segment 3-sided prism; its upper segment carries the spike: a stack of blunt tufts (3 fan-shaped trapezoid petals
around a small shared ring, tips cut flat and wider than the base) that taper in radius and overlap vertically, so the
spike reads as one soft column of bells rather than a row of outward wedges. A small cone bud closes each spike; 5 narrow
basal leaves sit in two uneven clusters.
  stem   2 segments, bowed sideways at the knee; spike axis = upper segment
  tuft   `tuft_petals` quads [ring k, ring k+1, tip right, tip left]; tip width >= 50 % of the base chord (here ~150 %)
  colour per spike deep -> light pink up the spike (grouped per tuft), leaves/stems in the grass family
  normals petals shade with a radial (cup) normal blended toward +Z; stems/leaves/buds as in groundcover_kit
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nature_lib as nl  # noqa: E402
from groundcover_kit import TAU, UP, Parts, add_leaves, add_stem, lerp, smooth  # noqa: E402
from groundcover_meadow import add_bud, along, basis  # noqa: E402

PARAMS = {
    "flower_pink_A": {
        "seed": 5602,
        # lean_deg: tilt of the spike axis from vertical; az_deg from the clump axis. spike_frac = share of the stem
        # length the spike covers; shift moves that spike along the deep -> light gradient.
        "stems": [
            {"height_m": 0.49, "az_deg": 200.0, "lean_deg": 7.0, "tufts": 6, "spike_frac": 0.54, "shift": 0.0},
            {"height_m": 0.42, "az_deg": 20.0, "lean_deg": 14.0, "tufts": 6, "spike_frac": 0.52, "shift": 0.22},
            {"height_m": 0.36, "az_deg": 98.0, "lean_deg": 10.0, "tufts": 5, "spike_frac": 0.52, "shift": -0.12},
            {"height_m": 0.31, "az_deg": 152.0, "lean_deg": 15.0, "tufts": 5, "spike_frac": 0.50, "shift": 0.10},
        ],
        "az_jitter_deg": 8.0, "base_spread_m": 0.018, "knee_lean_frac": 0.5, "bow_m": 0.012,
        "stem_radius_m": [0.0040, 0.0021],
        # Tuft: 3 fan-shaped petals around a ring at ring_frac * R (small ring, wide blunt tip edge: tip width is ~150 % of
        # the base chord); the tip edge (half-angle tip_half) sits at R, H above the ring with H = tuft spacing x
        # height_over_spacing, so neighbours overlap. turn_deg (+ jitter) between tufts interleaves the petals;
        # radius_var / tip_skew break the box shape; tip_light lightens the petal tips, petal_in_scale darkens the ring;
        # petal_radial = share of the radial (cup) normal in the petal shading normal.
        "tuft_petals": 3, "tuft_radius_m": [0.030, 0.014], "tuft_radius_exp": 0.9, "tuft_ring_frac": 0.38,
        "tuft_tip_half_deg": 33.0, "tuft_height_over_spacing": 1.1, "tuft_turn_deg": 63.0, "tuft_turn_jitter_deg": 10.0,
        "petal_radius_var": 0.10, "petal_tip_skew": 0.16, "petal_tip_light": 0.25, "petal_in_scale": 0.82,
        "petal_radial": 1.0,
        "bud_len_m": 0.016, "bud_radius_frac": 0.5,
        "leaf_clusters": [{"n": 3, "centre_deg": 60.0, "span_deg": 80.0}, {"n": 2, "centre_deg": 255.0, "span_deg": 40.0}],
        "leaf_length_m": [0.14, 0.24], "leaf_width_m": [0.018, 0.026], "leaf_lean_deg": [16.0, 40.0], "leaf_bend_deg": [14.0, 30.0],
        "value_jitter": 0.03, "stem_up_blend": 0.6, "petal_up_blend": 0.45,
    },
}


# ------------------------------------------------------------------ geometry

def add_tuft(P: Parts, r, C: Vector, axis: Vector, R: float, H: float, p: dict, rot: float, part: int, t: float) -> None:
    """Blunt tuft: ring at ring_frac*R in the plane through C, petal tips cut on an edge at about radius R, H above it.
    Per petal the tip radius varies and the edge is cut at a slant (skew), so the tuft is not a regular box."""
    e1, e2 = basis(axis)
    n = p["tuft_petals"]

    def vert(theta: float, rad: float, h: float, kind: str):
        radial = e1 * math.cos(theta) + e2 * math.sin(theta)
        v = P.vert(C + radial * rad + axis * h, kind, part, t)
        P.vinfo[-1]["radial"] = radial  # shading normal base: the tuft reads as a rounded cup, not as flat tags
        return v

    ring = [vert(rot + TAU * k / n, R * p["tuft_ring_frac"], 0.0, "petal_in") for k in range(n)]
    half = math.radians(p["tuft_tip_half_deg"])
    for k in range(n):
        c = rot + TAU * (k + 0.5) / n
        rad, slant = R * (1.0 + p["petal_radius_var"] * r.uniform(-1.0, 1.0)), p["petal_tip_skew"] * r.uniform(-1.0, 1.0)
        left, right = (vert(c + s * half, rad, H * (1.0 - s * slant), "petal_out") for s in (-1.0, 1.0))
        outward = e1 * math.cos(c) + e2 * math.sin(c)
        # Front = outer side, so the spike lights like a column (sun side lit) instead of like the inside of a cup.
        P.face([ring[k], ring[(k + 1) % n], right, left], outward + axis * 0.2, "petal", part)


def add_spike(P: Parts, r, p: dict, spec: dict, pts: list[Vector], part: int) -> None:
    """Tufts evenly up the upper stem segment: radius tapers, height = spacing x factor so neighbours overlap."""
    n, s0 = spec["tufts"], 1.0 - spec["spike_frac"]
    length = sum((b - a).length for a, b in zip(pts, pts[1:])) * (0.97 - s0) / n
    rot = r.uniform(0.0, TAU)
    for j in range(n):
        f = (j + 0.5) / n
        s = lerp(s0, 0.97, f)
        C, axis = along(pts, s)
        R = lerp(*p["tuft_radius_m"], f ** p["tuft_radius_exp"]) * r.uniform(0.94, 1.06)
        add_tuft(P, r, C, axis, R, length * p["tuft_height_over_spacing"] * r.uniform(0.92, 1.08), p, rot, part, s)
        rot += math.radians(p["tuft_turn_deg"] + r.uniform(-p["tuft_turn_jitter_deg"], p["tuft_turn_jitter_deg"]))
    C, axis = along(pts, 1.0)
    add_bud(P, C, axis, p["tuft_radius_m"][1] * p["bud_radius_frac"], p["bud_len_m"], part)


def stem_points(r, p: dict, spec: dict, base: Vector, d: Vector) -> list[Vector]:
    """base, knee, tip. The upper half leans lean_deg toward d; the lower half leans knee_lean_frac of that
    and bows sideways a little, so the spike axis is a straight segment."""
    half, lean = 0.5 * spec["height_m"], math.radians(spec["lean_deg"])
    perp = Vector((-d.y, d.x, 0.0)) * r.choice((-1.0, 1.0)) * p["bow_m"] * r.uniform(0.6, 1.3)
    knee = base + Vector((0.0, 0.0, half)) + d * (half * math.tan(lean * p["knee_lean_frac"])) + perp
    tip = knee + Vector((0.0, 0.0, half)) + d * (half * math.tan(lean)) - perp * 0.3
    return [base, knee, tip]


def build_pink(p: dict) -> Parts:
    r, P = nl.rng(p["seed"]), Parts()
    az0 = r.uniform(0, TAU)
    for spec in p["stems"]:
        part = P.part(k=1.0 + r.uniform(-p["value_jitter"], p["value_jitter"]), rand=r.random(),
                      s0=1.0 - spec["spike_frac"], shift=spec["shift"])
        ang = az0 + math.radians(spec["az_deg"] + r.uniform(-p["az_jitter_deg"], p["az_jitter_deg"]))
        d = Vector((math.cos(ang), math.sin(ang), 0.0))
        base = Vector((r.uniform(-1, 1), r.uniform(-1, 1), 0.0)) * p["base_spread_m"]
        pts = stem_points(r, p, spec, base, d)
        add_stem(P, pts, tuple(p["stem_radius_m"]), part)
        add_spike(P, r, p, spec, pts, part)
    add_leaves(P, r, p, az0)
    return P


# ------------------------------------------------------------------ normals / colour / data

def set_pink_normals(obj, P: Parts, up_blend: dict, p: dict) -> None:
    """Like kit.set_custom_normals (strips/stems/buds smooth their face normal across a part, blended toward +Z), but
    petal loops start from the radial direction of their vertex around the tuft axis (mixed with the face normal by
    petal_radial), so three flat quads shade like one rounded cup."""
    me = obj.data
    acc: dict = {}
    for poly in me.polygons:
        key = P.finfo[poly.index]["smooth"]
        if key is not None:
            for vi in poly.vertices:
                acc[(vi, key)] = acc.get((vi, key), Vector()) + poly.normal
    normals = [(0.0, 0.0, 1.0)] * len(me.loops)
    for poly in me.polygons:
        fi = P.finfo[poly.index]
        w = up_blend[fi["kind"]]
        for li in poly.loop_indices:
            vi = me.loops[li].vertex_index
            nf = acc[(vi, fi["smooth"])].normalized() if fi["smooth"] is not None else poly.normal
            if fi["kind"] == "petal":
                nf = (nf.lerp(P.vinfo[vi]["radial"], p["petal_radial"])).normalized()
            normals[li] = tuple((UP * w + nf * (1.0 - w)).normalized())
    for poly in me.polygons:
        poly.use_smooth = True
    me.normals_split_custom_set(normals)



def pink_color(v: dict, fi: dict, P: Parts, p: dict) -> tuple:
    part, t, kind = P.parts[v["part"]], v["t"], v["kind"]
    root, stem, grass = nl.pal("grass_root"), nl.pal("stem"), nl.pal("grass")
    if kind == "stem":
        return (*nl.scale_rgb(nl.mix(root, stem, smooth(t / 0.6)), part["k"]), t ** 1.2)
    if fi["kind"] == "leaf":
        c = nl.mix(root, nl.mix(stem, grass, 0.5), t ** 0.9)
        return (*nl.scale_rgb(c, part["k"]), 0.55 * t ** 1.5)
    deep, pink = nl.pal("flower_pink_deep"), nl.pal("flower_pink")
    f = max(0.0, min(1.0, (t - part["s0"]) / (1.0 - part["s0"]) + part["shift"]))
    c = nl.mix(deep, pink, smooth(f))
    if kind == "bud":
        c = nl.mix(pink, stem, 0.3)
    elif kind == "petal_in":
        c = nl.scale_rgb(c, p["petal_in_scale"])
    elif kind == "petal_out":
        c = nl.mix(deep, pink, smooth(f + p["petal_tip_light"]))
    return (*nl.scale_rgb(c, part["k"]), t ** 1.2)


def pink_data(v: dict, fi: dict, P: Parts, p: dict) -> tuple:
    t, kind = v["t"], v["kind"]
    cav = {"stem": 0.85 + 0.15 * smooth(t / 0.4), "petal_in": 0.9, "petal_out": 1.0, "bud": 1.0}.get(kind, 0.8 + 0.2 * t)
    return (cav, P.parts[v["part"]]["rand"])


ASSETS = {
    "flower_pink_A": {
        "build": build_pink, "color": pink_color, "data": pink_data, "family": "flower_pink", "normals": set_pink_normals,
        "habitats": ["meadow", "trail_margin", "rock_foot"], "budget": (80, 250), "scale": (0.8, 1.3), "tilt": 15.0,
        "wind": "flower",
        "up_blend": lambda p: {"stem": p["stem_up_blend"], "leaf": p["stem_up_blend"], "petal": p["petal_up_blend"], "bud": p["petal_up_blend"]},
        "notes": "Pink spike clump: 4 splayed 2-segment stems of unequal height, each with a spike of 5-6 stacked blunt 3-petal tufts (tapering, overlapping, deeper pink at the bottom) and a cone bud, 5 narrow basal leaves.",
    },
}
