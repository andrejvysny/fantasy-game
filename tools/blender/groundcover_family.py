"""Meadow groundcover: grass_short_A/B/C, grass_tall_A, flower_white_A, flower_pink_A (plan 5.5 / 5.6, visual target R03).

Run (repo root):
  /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup \
      -P tools/blender/groundcover_family.py -- [asset_id ...]

Each asset is one mesh, one M_foliage surface, built from bmesh strips/prisms with a fixed seed
and the PARAMS dict (stored into the metadata `recipe`). No ground card, no radial skirt:
every part is a free-standing blade, leaf, stem or petal.
  COLOR_0  rgb = grouped base colour (part gradient + per-part value jitter), a = wind flex weight
  UV2      x = restrained cavity (never below ~0.75), y = per-part random
  normals  custom split normals, blended toward +Z so thin parts light like the terrain
Layout: groundcover_kit.py = shared primitives; this file = grass_short_A, flower_white_A, registry and
export pipeline; groundcover_meadow.py = grass_short_B/C, grass_tall_A; groundcover_pink.py = flower_pink_A.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

from mathutils import Vector

_HERE = Path(globals().get("__file__", "/Users/andrejvysny/Developer/godot/tools/blender/x.py")).resolve().parent
sys.path.insert(0, str(_HERE))
import nature_lib as nl  # noqa: E402
import groundcover_meadow as meadow  # noqa: E402
import groundcover_pink as pink  # noqa: E402
from groundcover_kit import (  # noqa: E402,F401
    TAU, UP, Parts, add_leaves, add_stem, add_strip, bezier, blade_heights, footprint_slots,
    grass_color, grass_data, lerp, set_custom_normals, smooth, stem_controls)

GROUP = "groundcover"

PARAMS = {
    "grass_short_A": {
        "seed": 5501, "blades": 12,
        "footprint_m": [0.14, 0.22],        # irregular base area (x, y) before the yaw below
        "footprint_yaw_deg": 24.0,
        "height_m": [0.15, 0.30],           # blade tip height range; unequal by construction
        "width_m": [0.030, 0.046],          # base width; taller blades are a little broader
        "profile_3seg": [1.0, 0.80, 0.46],  # row widths / base width: gradual taper, then one tip vertex
        "profile_2seg": [1.0, 0.52],
        "lean_base_deg": [2.0, 14.0],       # from vertical; grows toward the clump edge
        "bend_deg": [8.0, 38.0],            # extra curl toward the tip
        "face_yaw_deg": 25.0, "twist_deg": 14.0,
        "outward": 0.4, "scatter": 0.6,     # lean direction: away from centre vs random
        "sweep": 0.4, "sweep_dir_deg": 35.0, "tall_side_deg": 200.0,  # mild asymmetry
        "centre_bias": 0.2, "height_noise": 0.45,  # low bias: tall blades may stand on the rim (no dome)
        "three_segment_fraction": 0.6, "value_jitter": 0.07,
        "dry_blades": 2, "dry_mix": 0.38,
        "arch_bend_deg": [38.0, 48.0], "arch_height_m": 0.22,  # one mid-height rim blade arches over (keeps the clump compact)
        "up_blend": 0.7,
    },
    "flower_white_A": {
        "seed": 5601,
        # Stem layout: three heads share one ~115 deg sector (az from the clump axis), the tallest stands
        # almost upright on the far side, so the top view is neither a cross nor a diamond. Reach is the
        # horizontal head offset; heads 1 and 2 are 3-4 cm apart at different heights and merge visually.
        # face_az_deg: heads look in spread-out directions so from any side some face the viewer
        # (back faces of a thin head read dark or edge-on); tilt_deg is the head normal's tilt from vertical.
        "stems": [
            {"height_m": 0.365, "az_deg": 200.0, "reach_m": [0.006, 0.014], "face_az_deg": 270.0, "tilt_deg": 24.0},
            {"height_m": 0.322, "az_deg": 0.0, "reach_m": [0.032, 0.042], "face_az_deg": 20.0, "tilt_deg": 28.0},
            {"height_m": 0.292, "az_deg": 55.0, "reach_m": [0.018, 0.026], "face_az_deg": 150.0, "tilt_deg": 26.0},
            {"height_m": 0.252, "az_deg": 115.0, "reach_m": [0.040, 0.054], "face_az_deg": 85.0, "tilt_deg": 30.0},
        ],
        "az_jitter_deg": 10.0, "base_spread_m": 0.016,
        "stem_radius_m": [0.0058, 0.0036], "stem_segments": 3, "bow_m": 0.020,
        "petals": [5, 6, 5, 6], "head_radius_m": [0.038, 0.048], "eye_radius_frac": 0.3,
        "eye_height_m": 0.006, "petal_half": 0.74, "petal_side_r": 0.75,
        # Basal leaves in two uneven clusters (3 within 70 deg, 2 within 50 deg) on roughly opposite sides.
        "leaf_clusters": [{"n": 3, "centre_deg": 85.0, "span_deg": 70.0},
                          {"n": 2, "centre_deg": 250.0, "span_deg": 50.0}],
        "leaf_length_m": [0.15, 0.22], "leaf_width_m": [0.028, 0.040],
        "leaf_lean_deg": [10.0, 28.0], "leaf_bend_deg": [15.0, 30.0],
        # Small stem leaves on the two tallest stems at 35-55 % height.
        "stem_leaf_t": [0.42, 0.52], "stem_leaf_length_m": [0.06, 0.075], "stem_leaf_width_m": [0.014, 0.018],
        "stem_leaf_lean_deg": [50.0, 66.0], "stem_leaf_bend_deg": [10.0, 22.0],
        "value_jitter": 0.03, "stem_up_blend": 0.6, "petal_up_blend": 0.45,
    },
}


# ------------------------------------------------------------------ grass


def build_grass(p: dict) -> Parts:
    r, P = nl.rng(p["seed"]), Parts()
    slots = footprint_slots(r, p)
    heights = blade_heights(r, p, slots)
    sweep_a = math.radians(p["sweep_dir_deg"])
    sweep = Vector((math.cos(sweep_a), math.sin(sweep_a))) * p["sweep"]
    hlo, hhi = p["height_m"]
    outer_short = sorted((i for i, s in enumerate(slots) if s[2] > 0.6), key=lambda i: heights[i])
    dry = set(outer_short[:p["dry_blades"]])
    arch = min((i for i, s in enumerate(slots) if s[2] > 0.6 and i not in dry),
               key=lambda i: abs(heights[i] - p["arch_height_m"]))
    for i, (x, y, rn, _th) in enumerate(slots):
        h = heights[i]
        out = Vector((x, y)).normalized() if rn > 0.3 else Vector((r.uniform(-1, 1), r.uniform(-1, 1))).normalized()
        v = out * (p["outward"] * (0.6 + 0.4 * rn)) + sweep + Vector((r.uniform(-1, 1), r.uniform(-1, 1))) * p["scatter"]
        az = math.atan2(v.y, v.x)
        lean0 = math.radians(lerp(*p["lean_base_deg"], rn * r.uniform(0.6, 1.0)))
        bend = math.radians(lerp(*p["bend_deg"], 0.6 * rn + 0.4 * r.random()))
        if i == arch:
            bend = math.radians(lerp(*p["arch_bend_deg"], r.random()))
        azf = az + math.radians(r.uniform(-p["face_yaw_deg"], p["face_yaw_deg"]))
        width = lerp(*p["width_m"], r.random()) * (0.85 + 0.3 * (h - hlo) / (hhi - hlo))
        segs = 3 if (h > 0.24 or r.random() < p["three_segment_fraction"]) else 2
        jit = p["value_jitter"]
        part = P.part(k=1.0 + r.uniform(-jit, jit), dry=p["dry_mix"] if i in dry else 0.0, rand=r.random())
        add_strip(P, Vector((x, y, 0.0)), az, lean0, bend, tuple(width * f for f in p[f"profile_{segs}seg"]),
                  Vector((math.cos(azf), math.sin(azf), 0.0)), "blade", part, height=h,
                  twist=math.radians(r.uniform(-p["twist_deg"], p["twist_deg"])))
    return P


# ------------------------------------------------------------------ flower

def add_head(P: Parts, r, p: dict, H: Vector, nrm: Vector, radius: float, n: int, part: int) -> None:
    """Flat-ish flower head: raised eye, n wedge petals sharing the eye ring (no gaps), tips drooped."""
    e1 = UP.cross(nrm)
    e1 = (e1 if e1.length > 1e-3 else Vector((1.0, 0.0, 0.0))).normalized()
    e2 = nrm.cross(e1)
    rot0 = r.uniform(0.0, TAU)

    def at(theta: float, rad: float, h: float) -> Vector:
        return H + (e1 * math.cos(theta) + e2 * math.sin(theta)) * rad + nrm * h

    r_eye = radius * p["eye_radius_frac"]
    centre = P.vert(H + nrm * p["eye_height_m"], "eye_c", part, 0.0)
    ring = [P.vert(at(rot0 + (j - 0.5) * TAU / n, r_eye, 0.0), "eye_r", part, 0.0) for j in range(n)]
    for j in range(n):
        P.face([centre, ring[j], ring[(j + 1) % n]], nrm, "eye", part)
    half = p["petal_half"] * math.pi / n
    for i in range(n):
        th, rad = rot0 + i * TAU / n, radius * r.uniform(0.92, 1.08)
        side_h = 0.05 * radius
        pl = P.vert(at(th - half, rad * p["petal_side_r"], side_h), "petal", part, 0.75)
        pr = P.vert(at(th + half, rad * p["petal_side_r"], side_h), "petal", part, 0.75)
        tip = P.vert(at(th, rad, r.uniform(-0.14, -0.02) * radius), "petal", part, 1.0)
        P.face([ring[i], ring[(i + 1) % n], pr, tip, pl], nrm, "petal", part)


def add_stem_leaf(P: Parts, r, p: dict, ctl: list[Vector], az: float, stem_part: int, t_attach: float) -> None:
    """Small leaf on the stem; its flex starts at the stem's flex at the attachment point."""
    f0 = t_attach ** 1.2
    part = P.part(k=P.parts[stem_part]["k"], rand=r.random(), f0=f0)
    w = lerp(*p["stem_leaf_width_m"], r.random())
    add_strip(P, bezier(*ctl, t_attach), az, math.radians(lerp(*p["stem_leaf_lean_deg"], r.random())),
              math.radians(lerp(*p["stem_leaf_bend_deg"], r.random())), (w * 0.55, w, w * 0.6), UP, "sleaf", part,
              length=lerp(*p["stem_leaf_length_m"], r.random()))


def build_flower(p: dict) -> Parts:
    r, P = nl.rng(p["seed"]), Parts()
    az0 = r.uniform(0, TAU)
    tallest = sorted(range(len(p["stems"])), key=lambda i: -p["stems"][i]["height_m"])[:2]
    segs = p["stem_segments"]
    for k, spec in enumerate(p["stems"]):
        part = P.part(k=1.0 + r.uniform(-p["value_jitter"], p["value_jitter"]), rand=r.random())
        ang = az0 + math.radians(spec["az_deg"] + r.uniform(-p["az_jitter_deg"], p["az_jitter_deg"]))
        d = Vector((math.cos(ang), math.sin(ang), 0.0))
        base = Vector((r.uniform(-1, 1), r.uniform(-1, 1), 0.0)) * p["base_spread_m"]
        ctl = stem_controls(r, p, spec, base, d)
        pts = [bezier(*ctl, i / segs) for i in range(segs + 1)]
        add_stem(P, pts, tuple(p["stem_radius_m"]), part)
        tilt, face = math.radians(spec["tilt_deg"]), az0 + math.radians(spec["face_az_deg"])
        nrm = UP * math.cos(tilt) + Vector((math.cos(face), math.sin(face), 0.0)) * math.sin(tilt)
        add_head(P, r, p, pts[-1], nrm, lerp(*p["head_radius_m"], r.random()), p["petals"][k % len(p["petals"])], part)
        if k in tallest:
            ti = p["stem_leaf_t"][tallest.index(k)]
            add_stem_leaf(P, r, p, ctl, ang + math.radians(r.uniform(-40.0, 40.0)), part, ti)
    add_leaves(P, r, p, az0)
    return P


def flower_color(v: dict, fi: dict, P: Parts, p: dict) -> tuple:
    part, t, kind = P.parts[v["part"]], v["t"], fi["kind"]
    root, stem, grass = nl.pal("grass_root"), nl.pal("stem"), nl.pal("grass")
    white, eye = nl.pal("flower_white"), nl.pal("flower_white_eye")
    if kind == "stem":
        return (*nl.scale_rgb(nl.mix(root, stem, smooth(t / 0.6)), part["k"]), t ** 1.2)
    if kind == "leaf":
        c = nl.mix(root, nl.mix(stem, grass, 0.5), t ** 0.9)
        return (*nl.scale_rgb(c, part["k"]), 0.55 * t ** 1.5)
    if kind == "sleaf":
        c = nl.mix(nl.mix(root, stem, 0.7), nl.mix(stem, grass, 0.5), t)
        return (*nl.scale_rgb(c, part["k"]), part["f0"] + (0.8 - part["f0"]) * t ** 1.3)
    if kind == "petal":
        c = nl.mix(nl.mix(white, eye, 0.14), white, smooth(t / 0.7))
        return (*nl.scale_rgb(c, part["k"]), 1.0)
    c = eye if v["kind"] == "eye_c" else nl.mix(eye, white, 0.3)
    return (*c, 1.0)


def flower_data(v: dict, fi: dict, P: Parts, p: dict) -> tuple:
    t, kind = v["t"], fi["kind"]
    cav = {"stem": 0.85 + 0.15 * smooth(t / 0.4), "leaf": 0.8 + 0.2 * t, "sleaf": 0.85 + 0.15 * t,
           "petal": 0.9 + 0.1 * t, "eye": 0.95}[kind]
    return (cav, P.parts[v["part"]]["rand"])


# ------------------------------------------------------------------ shared pipeline

ASSETS = {
    "grass_short_A": {
        "build": build_grass, "color": grass_color, "data": grass_data, "family": "grass_short",
        "habitats": ["meadow", "forest_edge"], "budget": (30, 100), "scale": (0.8, 1.3), "tilt": 15.0,
        "wind": "grass", "up_blend": lambda p: {"blade": p["up_blend"]},
        "notes": "Upright variant A: asymmetric handful of broad blades, no ground card or radial skirt.",
    },
    "flower_white_A": {
        "build": build_flower, "color": flower_color, "data": flower_data, "family": "flower_white",
        "habitats": ["meadow", "trail_margin"], "budget": (60, 220), "scale": (0.8, 1.2), "tilt": 10.0,
        "wind": "flower",
        "up_blend": lambda p: {"stem": p["stem_up_blend"], "leaf": p["stem_up_blend"],
                               "sleaf": p["stem_up_blend"], "petal": p["petal_up_blend"], "eye": p["petal_up_blend"]},
        "notes": "White flower clump: 4 stems (3 grouped in a sector, 1 upright) with 5-6 petal heads at unequal heights, basal leaf clusters and two stem leaves.",
    },
}
PARAMS.update(meadow.PARAMS)
PARAMS.update(pink.PARAMS)
ASSETS.update(meadow.ASSETS)
ASSETS.update(pink.ASSETS)


def build_object(asset_id: str):
    """Geometry, unwrap, custom normals and vertex data; everything short of export."""
    a, p = ASSETS[asset_id], PARAMS[asset_id]
    P = a["build"](p)
    obj = nl.mesh_object(asset_id, P.bm, (nl.FOLIAGE,))
    nl.finalize(obj)
    nl.uv_unwrap(obj)
    me, loops = obj.data, obj.data.loops
    if len(me.vertices) != len(P.vinfo) or len(me.polygons) != len(P.finfo):
        raise RuntimeError(f"{asset_id}: mesh order drifted from build info")
    if "normals" in a:
        a["normals"](obj, P, a["up_blend"](p), p)
    else:
        set_custom_normals(obj, P, a["up_blend"](p))
    nl.paint(obj, lambda poly, li, v: a["color"](P.vinfo[loops[li].vertex_index], P.finfo[poly.index], P, p))
    nl.paint_data(obj, lambda poly, li, v: a["data"](P.vinfo[loops[li].vertex_index], P.finfo[poly.index], P, p))
    return obj


def measure(obj) -> dict:
    lo, hi = nl.bounds(obj)
    base = [v.co for v in obj.data.vertices if v.co.z < 0.002]
    xs, ys = [c.x for c in base], [c.y for c in base]
    return {"size_m": [round(hi.x - lo.x, 3), round(hi.y - lo.y, 3), round(hi.z - lo.z, 3)],
            "min_z_m": round(lo.z, 4), "base_footprint_m": [round(max(xs) - min(xs), 3), round(max(ys) - min(ys), 3)]}


def export_one(asset_id: str) -> dict:
    a, p = ASSETS[asset_id], PARAMS[asset_id]
    nl.reset_scene()
    obj = build_object(asset_id)
    meta = nl.export_asset(
        obj, GROUP, asset_id, family=a["family"], habitats=a["habitats"], collision={"class": "none"},
        budget_tris=a["budget"], scale_range=a["scale"], max_tilt_deg=a["tilt"], wind=a["wind"],
        recipe={"seed": p["seed"], "params": p, "measured": measure(obj)}, notes=a["notes"])
    nl.render_previews(obj, GROUP, asset_id)
    nl.save_blend(GROUP, asset_id)
    print(f"[groundcover] {asset_id}: tris={meta['tris']} verts={meta['verts']} in_budget={meta['within_budget']} "
          f"bbox={meta['bbox_min']}..{meta['bbox_max']} {measure(obj)}")
    return meta


def main() -> None:
    ids = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    for asset_id in ids or list(ASSETS):
        export_one(asset_id)


if __name__ == "__main__":
    main()
