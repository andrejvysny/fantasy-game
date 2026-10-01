"""Tree family (Blender 5.2, headless): spruce growth forms for the valley. One parametric generator (spruce_gen.py),
a finite documented PARAMS set per variant, group "trees".
Run (repo root): /Applications/Blender.app/Contents/MacOS/Blender -b --factory-startup -P tools/blender/tree_family.py -- [id ...]
Plan: docs/valley_environment_plan.md 4.3 / 5.2 / 6. Contract: assets/nature/README.md.

Forms (visible without textures):
  spruce_mature_A  18 m, crown from ~40 %, broad 6.5 m base, closed dark cone to a clear leader, upright.
  spruce_mature_B  20 m, crown from ~46 %, narrower 5.5 m, 2-3 deg lean, fuller on one side, more dead stubs.
  spruce_edge_A    12 m, crown from ~15 %, 4.8 m skirt reaching low, clustered masses, fuller toward the meadow.
  spruce_young_A   3.6 m, dense youthful cone from ~5 %, few tiers, brighter/yellower tips, thin trunk.
PARAMS semantics: crown_start = live foliage base as a fraction of height (`sag` = how far the lowest boughs hang below
their root, so the lowest tier roots at crown_start * height + sag); tier_count = boughs per tier (branch clusters),
bottom -> top; stubs = dead lower branch stubs; asym = (amplitude, azimuth deg of the fuller side); cluster =
(amplitude, azimuth harmonics) of the slow grouping that keeps tiers from repeating.
Optional (default off, so older variants stay byte-identical): hem_jitter = lowest two tiers may root up to this many m
below the tier base (ragged hem); hem_cluster_dz = their root height follows the cluster rhythm by +-this; droop_cluster =
droop swing per cluster; gap_soft = reach factor inside a gap (0 = no boughs); inter_choices / inter_reach = count and relative reach of the
filler boughs between tiers; spacing_jit = (min, max) multiplier on tier spacing; tier_amp = +-fraction of reach between adjacent tiers; core_floor / core_drop = interior core
minimum radius / how far it starts below the lowest tier root.
"""
from __future__ import annotations

import math
import sys

sys.path.insert(0, "/Users/andrejvysny/Developer/godot/tools/blender")

from mathutils import Vector  # noqa: E402

import nature_lib as nl  # noqa: E402
import spruce_gen as sg  # noqa: E402

GROUP = "trees"
MATERIALS = (nl.SOLID, nl.FOLIAGE)

MATURE_TONE = {"cool": 1.0, "deep_k": 0.90, "mid_k": 0.86, "mid_mix": 0.0, "tip_mix": 0.85, "tip_k": 0.88,
               "tip_from": 0.50, "tip_gain": 0.8, "core_mix": 0.25, "core_tip": 0.0}
EDGE_TONE = {"cool": 0.60, "deep_k": 0.85, "mid_k": 0.85, "mid_mix": 0.12, "tip_mix": 1.0, "tip_k": 0.85,
             "tip_from": 0.40, "tip_gain": 0.9, "core_mix": 0.35, "core_tip": 0.12}
YOUNG_TONE = {"cool": 0.0, "deep_k": 0.90, "mid_k": 0.90, "mid_mix": 0.40, "tip_mix": 1.0, "tip_k": 0.74,
              "tip_from": 0.22, "tip_gain": 1.5, "core_mix": 0.40, "core_tip": 0.0}

# Finite, documented parameter set per asset (written to metadata via export_asset(recipe=...)).
PARAMS = {
    "spruce_mature_A": {
        "seed": 1701, "height": 18.0, "crown_width": 6.85, "crown_start": 0.40, "sag": 2.0,
        "peak_frac": 0.12, "base_reach": 0.90, "top_taper": 0.95, "reach_floor": 0.35, "reach_max": 3.45,
        "bough_wmax": 1.25, "thick": 0.15, "thick0": 0.12, "wfac": 0.92, "cup": 0.35, "tip_b": 1.0, "droop": (0.60, 0.50), "pitch_top": 0.12, "droop_jitter": 0.15,
        "trunk_sides": 8, "trunk_r0": 0.34, "trunk_r1": 0.05, "taper": 1.15, "trunk_step": 1.2,
        "lean": 0.30, "lean_dir": 35.0, "bend": 0.2,
        "flare": 1.7, "flare_lobes": 6, "flare_spurs": 3, "spur_reach": 2.2, "flare_h": 0.9, "embed": 0.3,
        "tier_spacing": (0.85, 0.34), "tier_count": (9.5, 7.0), "tier_top": 0.8, "z_jitter": 0.5,
        "leader": 2.6, "leader_w": 0.7,
        "gaps": [(205.0, 42.0, 0.24, 0.40), (60.0, 36.0, 0.58, 0.72)], "gap_edge": 20.0, "gap_edge_reach": 0.6,
        "asym": (0.10, 40.0), "cluster": (0.10, 3),
        "stubs": 5, "stub_z": (3.3, 7.0), "stub_len": (0.25, 0.70), "stub_r": (0.06, 0.08),
        "lobe_min_reach": 1.3, "hex_min_reach": 2.3, "st6_min_reach": 1.6, "st_small": 5, "core_k": (0.36, 0.16), "core_scallop": 0.10, "core_period": 0.9, "tone": MATURE_TONE,
    },
    "spruce_mature_B": {
        "seed": 2207, "height": 20.0, "crown_width": 5.5, "crown_start": 0.46, "sag": 1.3,
        "peak_frac": 0.10, "base_reach": 0.88, "top_taper": 0.92, "reach_floor": 0.32, "reach_max": 3.5,
        "bough_wmax": 1.15, "thick": 0.15, "thick0": 0.12, "wfac": 0.90, "cup": 0.35, "tip_b": 1.0,
        "droop": (0.58, 0.48), "pitch_top": 0.12, "droop_jitter": 0.15,
        "trunk_sides": 9, "trunk_r0": 0.36, "trunk_r1": 0.05, "taper": 1.2, "trunk_step": 1.3,
        "lean": 1.10, "lean_dir": 160.0, "bend": 0.28,
        "flare": 1.6, "flare_lobes": 5, "flare_spurs": 2, "spur_reach": 2.0, "flare_h": 0.85, "embed": 0.3,
        "tier_spacing": (0.85, 0.36), "tier_count": (8.5, 6.5), "tier_top": 0.8, "z_jitter": 0.5,
        "leader": 2.8, "leader_w": 0.7,
        "gaps": [(300.0, 48.0, 0.18, 0.36), (115.0, 36.0, 0.60, 0.78)], "gap_edge": 20.0, "gap_edge_reach": 0.6,
        "asym": (0.28, 70.0), "cluster": (0.14, 2),
        "stubs": 9, "stub_z": (2.6, 9.0), "stub_len": (0.25, 0.80), "stub_r": (0.055, 0.085),
        "lobe_min_reach": 1.3, "hex_min_reach": 2.3, "st6_min_reach": 1.6, "st_small": 5, "core_k": (0.36, 0.16), "core_scallop": 0.10, "core_period": 0.9,
        "tone": {**MATURE_TONE, "cool": 1.15, "deep_k": 0.90, "mid_k": 0.88},
    },
    "spruce_edge_A": {
        "seed": 3303, "height": 12.0, "crown_width": 4.8, "crown_start": 0.08, "sag": 1.0,
        "peak_frac": 0.05, "base_reach": 1.0, "top_taper": 0.95, "reach_floor": 0.45, "reach_max": 2.8,
        "bough_wmax": 1.15, "thick": 0.15, "thick0": 0.12, "wfac": 1.08, "cup": 0.30, "tip_b": 1.0,
        "droop": (0.60, 0.48), "pitch_top": 0.12, "droop_jitter": 0.15,
        "hem_jitter": 0.30, "hem_cluster_dz": 0.25, "droop_cluster": 0.15,
        "trunk_sides": 8, "trunk_r0": 0.24, "trunk_r1": 0.04, "taper": 1.1, "trunk_step": 1.0,
        "lean": 0.35, "lean_dir": 250.0, "bend": 0.15,
        "flare": 1.45, "flare_lobes": 5, "flare_spurs": 2, "spur_reach": 1.8, "flare_h": 0.6, "embed": 0.3,
        "tier_spacing": (0.80, 0.46), "tier_count": (10.0, 5.0), "tier_top": 0.6, "z_jitter": 0.4,
        "leader": 2.0, "leader_w": 0.55,
        "gaps": [(120.0, 50.0, 0.30, 0.48)], "gap_edge": 20.0, "gap_edge_reach": 0.6,
        "asym": (0.14, 250.0), "cluster": (0.20, 3),
        "stubs": 2, "stub_z": (0.5, 1.2), "stub_len": (0.2, 0.45), "stub_r": (0.04, 0.06),
        "lobe_min_reach": 1.5, "hex_min_reach": 2.4, "st6_min_reach": 1.5, "st_small": 5, "core_k": (0.30, 0.10), "core_scallop": 0.10, "core_period": 0.8,
        "tone": EDGE_TONE,
    },
    "spruce_young_A": {
        "seed": 4409, "height": 3.6, "crown_width": 1.9, "crown_start": 0.05, "sag": 0.48,
        "peak_frac": 0.08, "base_reach": 0.92, "top_taper": 0.55, "reach_floor": 0.42, "reach_max": 1.1,
        "bough_wmax": 0.80, "thick": 0.24, "thick0": 0.12, "wfac": 1.35, "cup": 0.30, "tip_b": 1.0,
        "droop": (0.85, 0.66), "pitch_top": 0.06, "droop_jitter": 0.12, "tier_amp": 0.18,
        "inter_choices": (3, 4, 4, 5), "inter_reach": (0.6, 0.85),
        "trunk_sides": 6, "trunk_r0": 0.05, "trunk_r1": 0.015, "taper": 1.0, "trunk_step": 0.6,
        "lean": 0.12, "lean_dir": 20.0, "bend": 0.05,
        "flare": 0.0, "flare_lobes": 0, "flare_spurs": 0, "spur_reach": 0.0, "flare_h": 0.2, "embed": 0.12,
        "tier_spacing": (0.50, 0.40), "spacing_jit": (0.72, 1.15), "tier_count": (9.0, 8.0), "tier_top": 0.2, "z_jitter": 0.10,
        "leader": 0.35, "leader_w": 0.22,
        "gaps": [(150.0, 70.0, 0.38, 0.58)], "gap_soft": 0.6, "gap_edge": 25.0, "gap_edge_reach": 0.75,
        "asym": (0.10, 0.0), "cluster": (0.28, 3),
        "stubs": 0, "stub_z": (0.3, 0.8), "stub_len": (0.1, 0.2), "stub_r": (0.01, 0.015),
        "lobe_min_reach": 9.0, "hex_min_reach": 9.0, "st6_min_reach": 9.0, "st_small": 4, "core_k": (0.12, 0.10), "core_floor": 0.03, "core_scallop": 0.14, "core_period": 0.45,
        "tone": YOUNG_TONE,
    },
}

ASSETS = {
    "spruce_mature_A": {
        "family": "spruce_mature", "habitats": ["mature_forest"], "budget": (4000, 8000),
        "collision": {"class": "trunk", "radius": 0.34, "height": 7.2}, "scale": (0.85, 1.2), "tilt": 3.0,
        "base_frame": (1.4, 4.5),
        "notes": "Open-trunk mature spruce: substantial elevated cone from ~40% height (longest, densest tiers at the "
                 "crown base), dead stubs below, rounded root flare, spire leader.",
    },
    "spruce_mature_B": {
        "family": "spruce_mature", "habitats": ["mature_forest"], "budget": (4000, 8000),
        "collision": {"class": "trunk", "radius": 0.36, "height": "crown_base"}, "scale": (0.85, 1.2), "tilt": 3.0,
        "base_frame": (1.4, 4.5),
        "notes": "Taller, narrower mature spruce: crown from ~46% height, mild lean, crown fuller on one side, many "
                 "dead stubs on the open trunk.",
    },
    "spruce_edge_A": {
        "family": "spruce_edge", "habitats": ["forest_edge", "open_meadow", "sheltered_bank"], "budget": (2500, 6000),
        "collision": {"class": "trunk", "radius": 0.24, "height": 1.0}, "scale": (0.85, 1.25), "tilt": 4.0,
        "base_frame": (2.2, 3.5),
        "notes": "Forest-edge spruce: full lower crown from ~15% height, broad skirt of grouped boughs, shorter trunk.",
    },
    "spruce_young_A": {
        "family": "spruce_young", "habitats": ["forest_edge", "open_meadow"], "budget": (500, 1800),
        "collision": {"class": "trunk", "radius": 0.08, "height": 1.0}, "scale": (0.8, 1.4), "tilt": 6.0,
        "base_frame": None,
        "notes": "Regeneration spruce: dense youthful cone from ~5% height, few tiers, brighter yellower tips, thin trunk.",
    },
}


# ---------------------------------------------------------------- build / export
def measure(obj, P: dict) -> dict:
    """Crown base, radius and width from the foliage vertices (recorded in the recipe for review)."""
    me = obj.data
    vs = {me.loops[li].vertex_index for p in me.polygons if p.material_index == sg.FOLIAGE for li in p.loop_indices}
    co = [me.vertices[i].co for i in vs]
    az = math.radians(P["asym"][1])
    side = [c.x * math.cos(az) + c.y * math.sin(az) for c in co]   # extent along the fuller-side azimuth
    tip = max((v.co for v in me.vertices), key=lambda c: c.z)
    top = tip.z
    zmin = min(c.z for c in co)
    return {"crown_base_z": round(zmin, 2), "crown_base_frac": round(zmin / top, 3),
            "crown_radius": round(max(math.hypot(c.x, c.y) for c in co), 2),
            "crown_width_x": round(max(c.x for c in co) - min(c.x for c in co), 2),
            "crown_width_y": round(max(c.y for c in co) - min(c.y for c in co), 2),
            "crown_reach_full_side": round(max(side), 2), "crown_reach_thin_side": round(-min(side), 2),
            "lean_deg": round(math.degrees(math.atan2(math.hypot(tip.x, tip.y), top)), 2)}


def foliage_stats(obj, P: dict) -> dict:
    """Console-only review numbers (not written to the recipe): area-weighted mean linear foliage colour, and the
    lowest foliage z on the fuller / thinner side of the crown (hem height)."""
    me = obj.data
    col = me.color_attributes[nl.COLOR_ATTR].data
    acc, tot = [0.0, 0.0, 0.0], 0.0
    az = math.radians(P["asym"][1])
    hem = {"full": 99.0, "thin": 99.0}
    for p in me.polygons:
        if p.material_index != sg.FOLIAGE:
            continue
        a = p.area
        for li in p.loop_indices:
            c = col[li].color
            for k in range(3):
                acc[k] += c[k] * a / len(p.loop_indices)
            v = me.vertices[me.loops[li].vertex_index].co
            if math.hypot(v.x, v.y) > 0.5:
                side = (v.x * math.cos(az) + v.y * math.sin(az)) / math.hypot(v.x, v.y)
                key = "full" if side > 0.5 else ("thin" if side < -0.5 else None)
                if key:
                    hem[key] = min(hem[key], v.z)
        tot += a
    return {"mean_rgb": [round(x / tot, 4) for x in acc], "hem_full_z": round(hem["full"], 2),
            "hem_thin_z": round(hem["thin"], 2)}


def render_base_views(obj, asset_id: str, frame: tuple) -> None:
    """Near player-height views (root flare, trunk, stubs) via a small proxy bbox so the lib camera closes in.
    The lib's own `low` view frames the whole crown from ~33 m, where the flare is a few pixels."""
    real = nl.bounds
    half, h = frame
    nl.bounds = lambda o: (Vector((-half, -half, 0.0)), Vector((half, half, h)))
    try:
        nl.render_previews(obj, GROUP, f"{asset_id}_base", views=(("low", 30.0, 2.0),))
    finally:
        nl.bounds = real


def fit_sag(P: dict) -> dict:
    """Random draws make the lowest bough's hang vary with the other params, so `sag` is refined (deterministically,
    same seed) until the live foliage base sits at crown_start * height. Returns the params actually built."""
    P = dict(P)
    target = P["crown_start"] * P["height"]
    for _ in range(4):
        t = sg.Tree(P)
        t.build()
        err = target - t.foliage_base()
        t.bm.free()
        if abs(err) < 0.04:
            break
        P["sag"] = round(P["sag"] + err, 3)
    return P


def build_asset(asset_id: str) -> dict:
    A = ASSETS[asset_id]
    P = fit_sag(PARAMS[asset_id])
    nl.reset_scene()
    tree = sg.Tree(P)
    tree.build()
    obj = nl.mesh_object(asset_id, tree.bm, MATERIALS)
    nl.finalize(obj)
    nl.uv_unwrap(obj)
    me = obj.data
    ids = [d.value for d in me.attributes[sg.PART_ATTR].data]
    assert len(ids) == len(me.polygons), "face order changed"
    nl.paint(obj, lambda poly, li, co: tree.color(tree.parts[ids[poly.index]], poly, co))
    nl.paint_data(obj, lambda poly, li, co: tree.data(tree.parts[ids[poly.index]], poly, co))
    me.attributes.remove(me.attributes[sg.PART_ATTR])
    measured = measure(obj, P)
    print(f"[tree_family] {asset_id} review stats: {foliage_stats(obj, P)} sag={P['sag']}")
    collision = dict(A["collision"])
    if collision.get("height") == "crown_base":
        collision["height"] = round(measured["crown_base_z"], 1)
    gpu_verts = 3 * sum(len(p.vertices) - 2 for p in me.polygons)   # flat shading splits every triangle
    meta = nl.export_asset(
        obj, GROUP, asset_id, family=A["family"], habitats=A["habitats"], collision=collision,
        budget_tris=A["budget"], embed_depth=P["embed"], scale_range=A["scale"], max_tilt_deg=A["tilt"],
        wind="trunk_static_crown_sway", pivot="ground_contact",
        recipe={"seed": P["seed"], "script": "tools/blender/tree_family.py", "generator": "tools/blender/spruce_gen.py",
                "crown_start": measured["crown_base_frac"], "crown_radius": measured["crown_radius"], "plan": tree.plan_summary(),
                "params": P, "measured": measured},
        notes=A["notes"] + f" Mesh reaches {P['embed']} m below the pivot (buried on slopes). `verts` is the welded "
              f"count; the flat-shaded GLB has {gpu_verts} GPU verts.")
    nl.render_previews(obj, GROUP, asset_id)
    if A["base_frame"]:
        render_base_views(obj, asset_id, A["base_frame"])
    nl.save_blend(GROUP, asset_id)
    return meta


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    for asset_id in argv or list(PARAMS):
        meta = build_asset(asset_id)
        print(f"[tree_family] {asset_id}: tris={meta['tris']} within_budget={meta['within_budget']} "
              f"bbox_min={meta['bbox_min']} bbox_max={meta['bbox_max']} non_manifold={meta['non_manifold_edges']} "
              f"{meta['recipe']['measured']}")


if __name__ == "__main__":
    main()
