"""Pine family (plan 5.3): pine_open_A, open-canopy pine for ridges, rocky slopes and meadows.
Blender 5.2, headless (repo root):

  Blender -b --factory-startup -P tools/blender/pine_family.py -- [pine_open_A]
  PINE_EXTRA_DIR=<dir> ...   also renders review views (four azimuths level with the crown) into <dir>

Construction (pine_tree.py, pine_geo.py): tapered 8-sided trunk with a gentle non-periodic S-bend, root ribs merging
into a flare, dead stubs and a bare lower 60 %; 4 irregular elbowed lateral arms (two fork) plus the leader carry 7 DISTINCT
foliage pads with a size hierarchy (2 dominant pads R~1.9 in the upper crown, 3 medium, 2 small lower pads; two are
long shelves). A pad is a few
faceted dome lobes with a flat underside and crisp rim, satellites clustered on the outward side, and angular wedge tufts
pointing out of the rim. The crown is widest at the top and asymmetric. Bark = M_solid (grey-brown foot -> orange-brown
crown), pads = M_foliage. Pad normals are mostly flat-faceted (spruce bough language), bark stays flat. Colour is grouped
per pad; COLOR_0.a = flex 0 trunk -> 1 outer pad edges and tuft tips.
"""
from __future__ import annotations

import math
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(globals().get("__file__", "/Users/andrejvysny/Developer/godot/tools/blender/x.py")).resolve().parent))

from mathutils import Vector  # noqa: E402

import nature_lib as nl  # noqa: E402
from pine_geo import FOLIAGE  # noqa: E402
from pine_tree import PART_ATTR, Pine  # noqa: E402

GROUP = "trees"

# Finite, documented parameter set per asset (written to metadata via export_asset(recipe=...)).
# Pads: R = main lobe radius (m), thick = main lobe height / (1.3 R), n = lobes incl. main and crest, elong = main lobe
# aspect, yaw = deg from the pad's outward azimuth, tilt deg, tone 0 (pine_deep) .. 1 (pine), tip = pine_tip mix on
# up-facing faces, sides = main lobe plan sides, crest = extra dome on the main one, spread = deg half-width of the
# satellite cluster around the outward direction, tufts / tuft_spread = wedge tufts on the rim.
PARAMS = {
    "pine_open_A": {
        "seed": 5301,
        "embed": 0.25,
        "trunk": {"r0": 0.34, "r1": 0.15, "taper": 1.1, "top": 14.55, "flare": 0.30, "flare_h": 1.0,
                  # S-bend knots (height m, x m, y m): irregular spacing, one sweep each way
                  "bend": [(0.0, 0.0, 0.0), (2.6, 0.16, -0.05), (5.4, 0.34, 0.10), (8.9, -0.06, 0.26),
                           (11.6, -0.30, 0.12), (14.55, -0.12, -0.08)],
                  "ribs": 3, "rib_reach": (3.4, 2.7, 3.0), "rib_h": 0.52, "rib_w": 0.34,
                  "stubs": [(3.3, 0.42), (5.3, 0.30), (6.9, 0.50)]},   # (height m, visible length m)
        # z = root height on the trunk, az deg, reach = horizontal run to the tip, s0/s1 = initial slope and up-curl
        # (rise/run), sway m sideways, r = root radius, elbow = (arm fraction, up-turn deg, sideways kink deg).
        # forks: at = arm fraction, turn deg from the arm azimuth, run/rise m.
        # Arms spiral round the trunk (270, 110, 215, 350 deg; forks 170 and 40): lower pads small and close, upper pads
        # large and far out, so the crown is widest at the top and never symmetric.
        "arms": [
            {"z": 8.8, "az": 275, "reach": 1.7, "s0": 0.10, "s1": 0.22, "sway": 0.25, "r": 0.15, "elbow": (0.62, 24, 16),
             "pad": {"R": 1.10, "thick": 0.60, "n": 4, "elong": 1.30, "yaw": 35, "tilt": 6, "tone": 0.75, "tip": 0.30,
                     "sides": 10, "crest": True, "spread": 60, "tufts": 2, "tuft_spread": 60},
             "forks": [{"at": 0.50, "turn": -100, "run": 1.8, "rise": 0.08, "r": 0.10,
                        "pad": {"R": 0.75, "thick": 0.75, "n": 3, "elong": 1.2, "yaw": -30, "tilt": -6, "tone": -0.15, "tip": 0.40,
                                "sides": 9, "crest": False, "spread": 60, "tufts": 1, "tuft_spread": 60}}]},
            {"z": 9.9, "az": 130, "reach": 2.0, "s0": 0.06, "s1": 0.22, "sway": -0.35, "r": 0.15, "elbow": (0.66, 22, -20),
             "pad": {"R": 1.30, "thick": 0.44, "n": 4, "elong": 1.85, "yaw": 20, "tilt": -5, "tone": 0.35, "tip": 0.35,
                     "sides": 11, "crest": False, "spread": 65, "tufts": 3, "tuft_spread": 85},
             "forks": [{"at": 0.50, "turn": -110, "run": 1.95, "rise": -0.25, "r": 0.10,
                        "pad": {"R": 0.85, "thick": 0.70, "n": 3, "elong": 1.3, "yaw": 50, "tilt": 8, "tone": 0.45, "tip": 0.45,
                                "sides": 9, "crest": False, "spread": 60, "tufts": 2, "tuft_spread": 60}}]},
            {"z": 11.3, "az": 240, "reach": 2.6, "s0": 0.14, "s1": 0.20, "sway": 0.30, "r": 0.14, "elbow": (0.60, 26, 18),
             "pad": {"R": 1.90, "thick": 0.55, "n": 5, "elong": 1.45, "yaw": 50, "tilt": 5, "tone": 0.00, "tip": 0.40,
                     "sides": 12, "crest": True, "spread": 75, "tufts": 4, "tuft_spread": 90},
             "forks": []},
            {"z": 12.3, "az": 320, "reach": 3.1, "s0": 0.06, "s1": 0.14, "sway": -0.30, "r": 0.14, "elbow": (0.62, 24, -16),
             "pad": {"R": 1.90, "thick": 0.44, "n": 5, "elong": 1.85, "yaw": -55, "tilt": -4, "tone": 1.05, "tip": 0.50,
                     "sides": 12, "crest": False, "spread": 70, "tufts": 4, "tuft_spread": 90},
             "forks": []},
        ],
        # leader pad: near the trunk top (the trunk ends inside it); its base plane is z_b; out = az its satellites face
        "leader": {"z_b": 13.85, "off": (-0.15, 0.65), "out": 95,
                   "pad": {"R": 1.30, "thick": 0.52, "n": 4, "elong": 1.65, "yaw": -10, "tilt": 4, "tone": 0.60, "tip": 0.50,
                           "sides": 11, "crest": True, "spread": 70, "tufts": 2, "tuft_spread": 80}},
        "flex": {"root_min": 0.10, "root_max": 0.40, "full_dist": 5.5},
    },
}


# ---------------------------------------------------------------- measure / previews
def to_srgb_hex(c) -> str:
    v = [12.92 * x if x <= 0.0031308 else 1.055 * x ** (1 / 2.4) - 0.055 for x in c[:3]]
    return "#" + "".join(f"{round(max(0.0, min(1.0, x)) * 255):02x}" for x in v)


def pad_stats(obj, tree: Pine, ids: list[int]) -> tuple[list[float], dict, dict]:
    """Per pad: sky gap to the nearest other pad (closest vertex pair, m), top height, mean colour (area weighted)."""
    me = obj.data
    col = me.color_attributes[nl.COLOR_ATTR].data
    verts: dict[int, set[int]] = {}
    acc: dict[int, list[float]] = {}
    for poly in me.polygons:
        part = tree.parts[ids[poly.index]]
        if part["kind"] not in ("lobe", "tuft"):
            continue
        verts.setdefault(part["pad"], set()).update(poly.vertices)
        a = acc.setdefault(part["pad"], [0.0, 0.0, 0.0, 0.0])
        for li in poly.loop_indices:
            w = poly.area / len(poly.loop_indices)
            a[0] += w
            for k in range(3):
                a[k + 1] += w * col[li].color[k]
    pts = {k: [me.vertices[i].co for i in v] for k, v in verts.items()}
    gaps = [round(min((a - b).length for j, pb in pts.items() if j != k for a in pa for b in pb), 2) for k, pa in pts.items()]
    tops = {k: round(max(c.z for c in v), 2) for k, v in pts.items()}
    means = {k: to_srgb_hex([x / a[0] for x in a[1:]]) for k, a in acc.items()}
    return gaps, tops, means


def foliage_mean(obj) -> tuple[str, str]:
    """Area-weighted mean of all foliage colour, and of its up-facing part (normal.z > 0.5), as sRGB hex."""
    me = obj.data
    col = me.color_attributes[nl.COLOR_ATTR].data
    tot, up = [0.0] * 4, [0.0] * 4
    for poly in me.polygons:
        if poly.material_index != FOLIAGE:
            continue
        for li in poly.loop_indices:
            w = poly.area / len(poly.loop_indices)
            for acc in ([tot, up] if poly.normal.z > 0.5 else [tot]):
                acc[0] += w
                for k in range(3):
                    acc[k + 1] += w * col[li].color[k]
    return to_srgb_hex([x / tot[0] for x in tot[1:]]), to_srgb_hex([x / up[0] for x in up[1:]])


def plan_width(pts: list[Vector]) -> dict:
    if not pts:
        return {}
    return {"x": round(max(p.x for p in pts) - min(p.x for p in pts), 2), "y": round(max(p.y for p in pts) - min(p.y for p in pts), 2),
            "diam": round(max(math.hypot(a.x - b.x, a.y - b.y) for a in pts for b in pts), 2)}


def measure(obj, tree: Pine, ids: list[int]) -> dict:
    """Crown extents from the foliage vertices (recorded in the recipe for review)."""
    me = obj.data
    vs = {me.loops[li].vertex_index for p in me.polygons if p.material_index == FOLIAGE for li in p.loop_indices}
    co = [me.vertices[i].co for i in vs]
    height = max(v.co.z for v in me.vertices)
    zmin = min(c.z for c in co)
    rad = [math.hypot(c.x - tree.axis(c.z).x, c.y - tree.axis(c.z).y) for c in co]
    gaps, tops, means = pad_stats(obj, tree, ids)
    mean, mean_up = foliage_mean(obj)
    return {"height": round(height, 2), "crown_start": round(zmin / height, 3), "crown_base_z": round(zmin, 2),
            "crown_radius": round(max(rad), 2), "crown_width_x": round(max(c.x for c in co) - min(c.x for c in co), 2),
            "crown_width_y": round(max(c.y for c in co) - min(c.y for c in co), 2),
            "width_above_12m": plan_width([c for c in co if c.z > 12.0]), "width_below_10_5m": plan_width([c for c in co if c.z < 10.5]),
            "pads": len(gaps), "arms": len(tree.P["arms"]), "pad_gap_min": min(gaps), "pad_gaps": gaps,
            "pad_tops": sorted(tops.values(), reverse=True), "pad_mean_srgb": list(means.values()),
            "foliage_mean_srgb": mean, "foliage_up_mean_srgb": mean_up}


def render_framed(obj, name: str, box: tuple, views: tuple, out: str | None = None) -> None:
    """Preview views through a proxy bbox so the lib camera frames `box` (crown, trunk foot) instead of the whole tree."""
    real_bounds, real_dir = nl.bounds, nl.preview_dir
    nl.bounds = lambda o: (Vector(box[0]), Vector(box[1]))
    if out:
        nl.preview_dir = lambda g: Path(out)
    try:
        nl.render_previews(obj, GROUP, name, views=views)
    finally:
        nl.bounds, nl.preview_dir = real_bounds, real_dir


def render_views(obj, asset_id: str) -> None:
    """Shipped: trunk foot and crown seen from the ground. PINE_EXTRA_DIR adds unshipped review azimuths."""
    crown = ((-6.2, -6.2, 7.5), (6.2, 6.2, 15.5))
    render_framed(obj, f"{asset_id}_base", ((-1.4, -1.4, 0.0), (1.4, 1.4, 4.5)), (("low", 30.0, 2.0),))
    render_framed(obj, f"{asset_id}_crown", crown, (("up", 40.0, 2.0),))
    if os.environ.get("PINE_EXTRA_DIR"):
        render_framed(obj, f"{asset_id}_crown", crown, tuple((f"a{a}", float(a), 6.0) for a in (0, 90, 180, 270)),
                      out=os.environ["PINE_EXTRA_DIR"])


# ---------------------------------------------------------------- build / export
def apply_normals(obj, tree: Pine, ids: list[int]) -> None:
    me = obj.data
    out = [(0.0, 0.0, 1.0)] * len(me.loops)
    for poly in me.polygons:
        part = tree.parts[ids[poly.index]]
        for li in poly.loop_indices:
            out[li] = tuple(tree.shade_normal(part, poly, me.vertices[me.loops[li].vertex_index].co))
    me.normals_split_custom_set(out)
    me.update()


def build_mesh(asset_id: str):
    """Geometry, UVs, colours, custom normals. Returns (object, tree, per-face part ids)."""
    P = PARAMS[asset_id]
    nl.reset_scene()
    tree = Pine(P)
    tree.build()
    obj = nl.mesh_object(asset_id, tree.bm, (nl.SOLID, nl.FOLIAGE))
    nl.finalize(obj, custom_normals=True)
    nl.uv_unwrap(obj)
    me = obj.data
    ids = [d.value for d in me.attributes[PART_ATTR].data]
    assert len(ids) == len(me.polygons), "face order changed"
    nl.paint(obj, lambda poly, li, co: tree.color(tree.parts[ids[poly.index]], poly, co))
    nl.paint_data(obj, lambda poly, li, co: tree.data(tree.parts[ids[poly.index]], poly, co))
    apply_normals(obj, tree, ids)
    return obj, tree, ids


def build_asset(asset_id: str) -> dict:
    P = PARAMS[asset_id]
    obj, tree, ids = build_mesh(asset_id)
    measured = measure(obj, tree, ids)
    obj.data.attributes.remove(obj.data.attributes[PART_ATTR])
    meta = nl.export_asset(
        obj, GROUP, asset_id, family="pine_open", habitats=["rocky_slope", "exposed", "open_meadow"],
        collision={"class": "trunk", "radius": 0.35, "height": 8.0}, budget_tris=(3000, 6000),
        embed_depth=P["embed"], scale_range=(0.85, 1.2), max_tilt_deg=4.0, wind="trunk_static_crown_sway",
        pivot="ground_contact",
        recipe={"seed": P["seed"], "script": "tools/blender/pine_family.py", "params": P, "measured": measured,
                "crown_start": measured["crown_start"], "crown_radius": measured["crown_radius"]},
        notes="Open-canopy pine: bare S-bent warm-bark trunk, 4 elbowed lateral arms (2 fork) + leader carrying "
              f"{measured['pads']} distinct faceted foliage pads (2 dominant, 3 medium, 2 small) with sky gaps; crown in the "
              f"top ~40% of height, widest at the top. Mesh reaches {P['embed']} m below the pivot (buried on slopes).")
    nl.render_previews(obj, GROUP, asset_id)
    render_views(obj, asset_id)
    nl.save_blend(GROUP, asset_id)
    return meta


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    for asset_id in argv or list(PARAMS):
        meta = build_asset(asset_id)
        print(f"[pine_family] {asset_id}: tris={meta['tris']} within_budget={meta['within_budget']} "
              f"bbox_min={meta['bbox_min']} bbox_max={meta['bbox_max']} non_manifold={meta['non_manifold_edges']} "
              f"{meta['recipe']['measured']}")


if __name__ == "__main__":
    main()
