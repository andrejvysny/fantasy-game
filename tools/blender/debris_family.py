"""Debris family (plan 5.3): fallen_log_A, root_flare_A (group "debris").
Run (repo root): /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup -P tools/blender/debris_family.py -- [id ...]
Contract: assets/nature/README.md. Everything is M_solid; colour classes are assigned per face (no speckle).
Geometry: debris_log.py (fallen_log_A), debris_root.py (root_flare_A); mesh builder, colours, painting: debris_mesh.py.

fallen_log_A: a nearly straight (<= 0.10 m off the chord) 10-sided spruce log along Blender X (front = -Y), tapered,
flat underside sunk 0.1 m, three long bark seams, a dished rotted butt end (-X) and a one-sided torn break (+X).
root_flare_A: 6 uneven buttress roots (+2 forks) around an OPEN hole of the trunk radius, based on the real
spruce_mature_A trunk surface; coupled to its host tree by scale and yaw (see HOST).
"""
from __future__ import annotations

import json
import math
import sys

sys.path.insert(0, "/Users/andrejvysny/Developer/godot/tools/blender")

import nature_lib as nl  # noqa: E402
from debris_log import build_log  # noqa: E402,F401
from debris_mesh import MID, ROT, WOOD, finish  # noqa: E402
from debris_root import build_root  # noqa: E402,F401

GROUP = "debris"
# Finite, documented parameter sets (stored in the metadata recipe).
PARAMS = {
    "fallen_log_A": {
        "seed": 4101,
        "length": 3.45,                 # m between the two end rings; butt lip and the torn tongue add ~0.6
        "sides": 10, "rings": 22,
        "r_butt": 0.275, "r_top": 0.235, "butt_flare": 0.035,   # 0.55 m -> 0.47 m diameter
        "bend_y": 0.075, "wobble_y": 0.012,   # m, plan sag + small harmonic: at most ~0.10 m off the chord
        "underside": 0.10,              # m the flat underside sits below z = 0
        "lift": 0.02,                   # m the thin end rises (its underside stays below z = -0.07)
        "flat": 0.80,                   # underside clamp, fraction of the radius below the axis
        # vertex column, first face ring, end face ring, groove depth (fraction of radius). Each seam is painted
        # 9 of 22 rings (41 %): lower groove wall bark_dark, upper wall bark_ridge on all but the end rings.
        "seams": [(4, 1, 10, 0.15), (1, 8, 17, 0.15), (7, 12, 21, 0.15)],
        # one tapered weathered lens on the front: (column, ring) faces; ends sit 3 rings apart
        "lens": [(4, 13), (4, 14), (5, 14), (5, 15)],
        # rotted end: ragged bark lip, dished face (`inner` of the radius), dark core, chunks (columns) broken away
        "butt": {"jitter": 0.08, "slant": 0.05, "slant_az": 60.0, "dish": 0.06, "inner": 0.88, "core": 0.42,
                 "heart": 0.20, "chunks": [2, 3], "chunk_depth": 0.11},
        # torn end: wood reaches `front` (+ a per-column step from `steps`) m past the last ring, plus `tongue` m toward
        # `tear_az` (azimuth around the axis: 0 = +Y back, 90 = up, 180 = -Y front); bark stops `bark_set` short
        # of the wood. Shards: az, radius fraction, visible length m (past the wood face), width, thickness, lean.
        "break": {"front": 0.05, "tongue": 0.10, "tear_az": 30.0, "bark_set": 0.03, "inner": 0.80, "core": 0.36,
                  "core_e": 0.03, "steps": [0.035, 0.0, 0.06, 0.03, 0.07, 0.0, 0.04, 0.02, 0.07, 0.05],
                  "shards": [dict(az=52.0, rho=0.84, length=0.46, width=0.12, thick=0.032, lean=0.10, splay=0.04, cut=0.07),
                             dict(az=335.0, rho=0.82, length=0.28, width=0.09, thick=0.030, lean=0.03, splay=-0.12, cut=0.05),
                             dict(az=12.0, rho=0.80, length=0.21, width=0.08, thick=0.030, lean=0.16, splay=0.10, cut=-0.04)]},
        # t along the log, azimuth around the axis, visible length, radius, pitch from the axis (+X = crown end)
        "stubs": [dict(t=0.29, az=150.0, length=0.26, r=0.07, pitch=45.0),
                  dict(t=0.58, az=80.0, length=0.25, r=0.055, pitch=48.0),                       # leans to the crown
                  dict(t=0.83, az=40.0, length=0.12, r=0.055, pitch=70.0, tones=[MID, ROT, WOOD, WOOD]),   # snapped flush
                  dict(t=0.15, az=195.0, length=0.22, r=0.065, pitch=55.0)],   # last one props the log into the soil
    },
    "root_flare_A": {
        "seed": 5207,
        "r_in": 0.34,                   # m, inner ends hide inside the trunk (spruce_mature_A surface r 0.44-0.56)
        "depth": 0.10,                  # m, buried bottom
        "foot": -0.035,                 # m, z of the flank feet
        # az deg (CCW from +X), reach m from the trunk centre, crest height at r = 0.5 m / half width at the inner end /
        # tip half width, crest twist rad, plan wander m, round surface-root height m, optional fork (spine index,
        # side, angle deg, child length m, size factor, tip half width, surface-root height m)
        "roots": [
            dict(az=6, reach=1.12, h0=0.27, hw0=0.26, hw1=0.095, tw=0.36, wander=0.09, tail=0.065),
            dict(az=52, reach=0.90, h0=0.19, hw0=0.21, hw1=0.085, tw=-0.30, wander=-0.06, tail=0.055),
            dict(az=110, reach=1.05, h0=0.24, hw0=0.25, hw1=0.095, tw=0.40, wander=-0.10, tail=0.060,
                 fork=dict(at=4, side=1, ang=40.0, length=0.44, size=0.56, hw1=0.05, tail=0.05)),
            dict(az=178, reach=1.08, h0=0.18, hw0=0.20, hw1=0.085, tw=-0.26, wander=-0.08, tail=0.055),
            dict(az=258, reach=1.06, h0=0.30, hw0=0.27, hw1=0.100, tw=0.30, wander=0.09, tail=0.065,
                 fork=dict(at=4, side=-1, ang=36.0, length=0.38, size=0.52, hw1=0.05, tail=0.05)),
            dict(az=318, reach=0.92, h0=0.21, hw0=0.22, hw1=0.085, tw=-0.34, wander=0.06, tail=0.060),
        ],
    },
}
# Placement coupling (the placer multiplies, it does not sample independently): roots az 6/52/258/318 line up with
# spruce_mature_A's ground spurs (0-60, 240-270, 300-330 deg) when the flare takes the tree's yaw +- 10 deg.
HOST = {"family": "spruce_mature", "assets": ["spruce_mature_A"], "yaw_offset_deg": [-10.0, 10.0],
        "scale": "host_scale * scale_range", "scale_range": [0.95, 1.05],
        "aligned_spurs_deg": [[0, 60], [240, 270], [300, 330]]}


def measure(obj, kind: str, b) -> dict:
    lo, hi = nl.bounds(obj)
    out = {"size_x": round(hi.x - lo.x, 3), "size_y": round(hi.y - lo.y, 3),
           "z_min": round(lo.z, 3), "z_max": round(hi.z, 3), **b.stats}
    if kind == "root":
        out["hole_radius_min_vertex"] = round(min(math.hypot(v.co.x, v.co.y) for v in obj.data.vertices), 3)
    return out


def patch_meta(asset_id: str, extra: dict) -> None:
    """Keys export_asset does not write (host coupling) are added to the asset's own json."""
    path = nl.asset_dir(GROUP) / f"{asset_id}.json"
    meta = json.loads(path.read_text())
    meta.update(extra)
    path.write_text(json.dumps(meta, indent=2))


def build_asset(asset_id: str) -> dict:
    P = PARAMS[asset_id]
    nl.reset_scene()
    is_log = asset_id == "fallen_log_A"
    b = build_log(P) if is_log else build_root(P)
    obj = finish(b, asset_id)
    measured = measure(obj, "log" if is_log else "root", b)
    common = dict(habitats=["mature_forest"], embed_depth=0.1,
                  pivot="ground_contact")
    if is_log:
        meta = nl.export_asset(
            obj, GROUP, asset_id, family="fallen_log", collision={"class": "convex"}, budget_tris=(500, 1500),
            scale_range=(0.8, 1.25), max_tilt_deg=12.0,
            recipe={"seed": P["seed"], "script": "tools/blender/debris_family.py", "params": P, "measured": measured},
            notes="Spruce log along X (origin mid-length, front = -Y = Godot +Z, for logs lying across a slope): 10-sided, "
                  "tapered 0.55 -> 0.47 m, nearly straight (<= 0.10 m off the chord), flat underside 0.1 m below y=0 "
                  "(embed), 3 long bark seams, one weathered lens, torn +X end (stepped pale wood on the front, a "
                  "tongue with 3 flat shards on the back, dark heart), dished rotted -X end, 3 broken branch stubs + "
                  "one prop stub. Moss is shader-side.", **common)
        nl.render_previews(obj, GROUP, asset_id)
    else:
        meta = nl.export_asset(
            obj, GROUP, asset_id, family="root_flare", collision={"class": "none"}, budget_tris=(300, 1200),
            scale_range=tuple(HOST["scale_range"]), max_tilt_deg=6.0,
            recipe={"seed": P["seed"], "script": "tools/blender/debris_family.py", "params": P, "host": HOST,
                    "measured": measured},
            notes="Origin = trunk centre at ground. 6 uneven buttress roots (0.9-1.12 m reach, 0.18-0.30 m crest at "
                  "r = 0.5 m) with two small forks, round tips that sink into the soil, buried bottoms at y=-0.1. The "
                  "inner hole (r < 0.3) is open. HOST COUPLED: scale = host tree scale x scale_range (0.95-1.05), "
                  "yaw = host yaw +- 10 deg so the roots line up with spruce_mature_A's ground spurs.", **common)
        patch_meta(asset_id, {"host": HOST})
        nl.render_previews(obj, GROUP, asset_id, views=(("front34", 35.0, 18.0), ("low", 20.0, 4.0), ("top", 0.0, 86.0)))
    nl.save_blend(GROUP, asset_id)
    return meta


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    for asset_id in argv or list(PARAMS):
        meta = build_asset(asset_id)
        print(f"[debris_family] {asset_id}: tris={meta['tris']} within_budget={meta['within_budget']} "
              f"bbox_min={meta['bbox_min']} bbox_max={meta['bbox_max']} non_manifold={meta['non_manifold_edges']} "
              f"{meta['recipe']['measured']}")


if __name__ == "__main__":
    main()
