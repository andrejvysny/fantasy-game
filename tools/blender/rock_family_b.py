"""Geology family, second wave: cliff_corner_A and boulder_medium_A live here; rubble_cluster_A and shore_boulder_A in
rock_family_c.py (merged into PARAMS_B / MAKERS below, so rock_family.py dispatches all four from here).

Same construction language as rock_family.py (imported, never modified, so the approved cliff_face_A /
rock_shelf_A / boulder_large_A stay byte-stable): planes from a per-asset fracture frame (bedding + joint
sets) first, noise last. cliff_corner_A runs through rf.make_object with a tilted-floor bench (make_corner);
boulder_medium_A runs through rf.make_object unchanged.
    blender -b --factory-startup -P tools/blender/rock_family.py -- cliff_corner_A boulder_medium_A ...
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent if "__file__" in globals() else "/Users/andrejvysny/Developer/godot/tools/blender"))

import bpy  # noqa: E402

import nature_lib as nl  # noqa: E402
import rock_family as rf  # noqa: E402
import rock_family_c as rfc  # noqa: E402

GROUP = rf.GROUP


def lean_for(az: float, world: float, tilt: float, dip: float) -> float:
    """Authored wall lean (deg, top inward) that leaves `world` deg of lean after the frame tilts `tilt` deg toward `dip`.
    The tilt would otherwise add up to `tilt` deg of back-lean (or overhang) to every wall, depending on its azimuth."""
    th, a, d = math.radians(tilt), math.radians(az), math.radians(dip)
    k = math.sin(a) * math.cos(d) - math.cos(a) * math.sin(d)  # horizontal wall normal . dip direction
    A, B = math.cos(th), -math.sin(th) * k
    return math.degrees(math.asin(math.sin(math.radians(world)) / math.hypot(A, B)) - math.atan2(B, A))


def chain_az(points: list) -> list:
    return [math.degrees(math.atan2(y2 - y1, x2 - x1)) for (x1, y1), (x2, y2) in zip(points, points[1:])]


def inset(points: list, setback: list) -> list:
    """Plan chain (left to right, front side) moved back by setback[i] (perpendicular) at vertex i, so the tread
    between a lower face and the face above it varies along the arm instead of being a constant offset."""
    norms = []
    for (x1, y1), (x2, y2) in zip(points, points[1:]):
        ln = math.hypot(x2 - x1, y2 - y1)
        norms.append(((y2 - y1) / ln, -(x2 - x1) / ln))
    out = []
    for i, (x, y) in enumerate(points):
        na, nb = norms[max(i - 1, 0)], norms[min(i, len(norms) - 1)]
        m = (na[0] + nb[0], na[1] + nb[1])
        k = math.hypot(*m)
        m = (m[0] / k, m[1] / k)
        h = na[0] * m[0] + na[1] * m[1]
        out.append((x - m[0] * setback[i] / h, y - m[1] * setback[i] / h))
    az = chain_az(out)
    if any(b <= a for a, b in zip(az, az[1:])):  # an inverted facet (set-back > facet width) turns the cutter non-convex
        raise ValueError(f"inset chain is not convex: facet azimuths {[round(a, 1) for a in az]}")
    return out


def leans_for(points: list, world: list, P: dict) -> list:
    return [round(lean_for(az, w, P["tilt"], P["azimuth"]), 2) for az, w in zip(chain_az(points), world)]


def corner_params() -> dict:
    """cliff_corner_A. Aligned frame, arris near plan (0, 0), left arm toward -x/+y, right arm toward +x/+y (faces ~108 deg
    apart). The front is ONE convex chain of seven facets (3 + broken arris + 3, unequal widths, each turning 5-8 deg) so the
    nose is faceted, not two flat walls. Strata match cliff_face_A: lower stratum ~3.3 m, middle ~1.5 m, top ~1.15 m; the
    ledges are the same chain moved back by a varying tread (0.45-0.95 m), so ledge faces are never parallel to the faces
    below. Bedding dips toward the hill and the left arm, so the right arm stays full height (cliff_face_A's high end) and
    the left arm sinks ~0.5 m (its low end)."""
    P = dict(family="cliff_corner", seed=4409, tilt=8.0, azimuth=110.0, yaw=-5.0, height=5.85, embed=1.5, front=1.5,
             bevel=0.05, edge_len=0.85, distort=0.06, distort_freq=0.23)
    chain = [(-3.37, 2.94), (-2.69, 2.07), (-1.58, 1.07), (-0.38, 0.256), (0.42, 0.33), (2.78, 2.20), (3.60, 3.08), (3.94, 3.58)]
    world = [8.0, 3.0, 9.0, 5.0, 1.0, 7.0, 2.0]               # back-lean of each front facet in the world, deg
    P["arc"] = dict(points=chain, leans=leans_for(chain, world, P))
    tread1 = [0.8, 0.75, 0.7, 0.95, 0.95, 0.75, 0.7, 0.7]            # lower ledge, measured from the faces below
    tread2 = [0.5, 0.45, 0.3, 0.0, -0.1, -0.15, -0.2, -0.3]          # upper ledge: left arm only, fades out toward the arris/right
    step1 = inset(chain, tread1)
    step2 = inset(chain, [a + b for a, b in zip(tread1, tread2)])
    P["mass"] = [("flat", 0, 1.0, 0, 0, 6.0), ("!flat", 0, 0, 0, 0, -3.6), ("flat", 135, 5.0, 0.2, 1.6, 5.98),  # right top facet
                 ("wall", 134, 0, 3.94, 3.58, 0), ("wall", -128, 0, -3.37, 2.94, 0),                           # arm ends
                 ("flat", 180, 28, 0, 3.6, 6.0), ("wall", 176, 3, 0, 4.4, 0)]                                  # back ramp + buried wall
    P["benches"] = [dict(points=step1, floor=3.35, floor_az=100, floor_tilt=4.0,
                         leans=leans_for(step1, [4.0, 2.5, 5.0, 3.5, 2.0, 4.0, 1.5], P)),
                    dict(points=step2, floor=4.85, floor_az=-80, floor_tilt=3.0,
                         leans=leans_for(step2, [1.5, 4.0, 2.5, 6.0, 3.0, 1.0, 4.0], P))]
    pl, pr = lean_for(-52.0, 4.5, P["tilt"], P["azimuth"]), lean_for(46.4, 3.0, P["tilt"], P["azimuth"])
    P["carves"] = [[("wall", 105, 1, -2.69, 2.07, 0), ("!wall", -52.0, pl, -2.47, 2.27, 0),    # left outer panel recessed 0.3,
                    ("flat", 0, 1.0, 0, 0, 3.35)],                                              # lower stratum only
                   [("wall", -62, 1, 2.2, 1.75, 0), ("!wall", 46.4, pr, 2.563, 2.407, 0),     # right outer panel recessed 0.3 beyond an
                    ("flat", 0, 1.0, 0, 0, 3.35)]]                                              # oblique joint, lower stratum only
    P["chips"] = [((0.1, -0.7, 0.7), 0.4)]  # one broken nose crown; never an arm end (those keep full height)
    P.update(habitats=["rocky_slope", "canyon"], collision={"class": "trimesh"}, budget=(1000, 4000), max_tilt=8.0,
             scale=(0.8, 1.3),
             notes="Convex corner module: two faces ~108 deg apart (right arm ~5.3 m, left ~4.5 m; each a 3-facet chain, unequal "
                   "widths, leans 1-9 deg) around a broken arris facet. Strata match cliff_face_A (lower ~3.2 m, middle ~1.5, "
                   "crown ~1.1): a 0.65-0.95 m ledge at ~3.2 m wraps the arris and both arms (floor tilted 4 deg off the bedding, "
                   "so strata thickness varies), a smaller upper ledge fades out along the right arm, one recessed panel on each "
                   "arm's lower stratum, one nose-crown spall. Top follows the 8 deg bedding dip toward the hill/left arm; both arm "
                   "ends stay >= 5.3 m. Back = 28 deg ramp + buried wall: bury with terrain rising behind. Origin ~1.5 m behind "
                   "the arris, arris bisector toward -Y. Pairs with cliff_face_A ends rotated about +38 / -34 deg.")
    return P


def bench_b(r, b: dict):
    """rf.bench with an optional floor tilt (`floor_az`, `floor_tilt`): strata thickness then varies along the arms
    instead of every ledge running parallel to the top."""
    floor = ("!flat", b.get("floor_az", 0), b.get("floor_tilt", 1.0), 0, 0, b["floor"])
    slab = rf.polytope(r, [floor] + ([b["joint"]] if "joint" in b else []), half=70.0)
    return rf.boolean(slab, rf.polytope(r, rf.facets(b["points"], b["leans"])), "DIFFERENCE")


def make_corner(asset_id: str) -> bpy.types.Object:
    saved, rf.bench = rf.bench, bench_b  # restored below: cliff_face_A must keep the stock bench
    try:
        return rf.make_object(asset_id)
    finally:
        rf.bench = saved


# Plane spec: see rock_family.PARAMS (kind, azimuth, lean_or_tilt, x, y, z); az 0 = front (-Y), 90 = +X.
PARAMS_B = {
    "cliff_corner_A": corner_params(),
    "boulder_medium_A": dict(
        # Frame tilt 0: the bedding dip is authored on the top/step planes themselves so wall leans are world leans.
        family="boulder_medium", seed=5503, tilt=0.0, azimuth=30.0, yaw=-4.0, height=0.70, embed=0.15, front=None,
        bevel=0.025, edge_len=0.24, distort=0.012, distort_freq=1.0,
        # Asymmetric wedge on the bedding dip: W1 (left) and F (front) are near vertical, R (right) and B1/B2 (back, split by a joint
        # 14 deg off) are 18-27 deg ramps; W0 = chipped front-left corner. Bedding top dips 7 deg toward the back-right.
        mass=[("flat", 150, 7.0, 0, 0, 0.74), ("!flat", 0, 0, 0, 0, -0.6),
              ("wall", -90, 1.0, -0.50, 0, 0), ("wall", 98, 27.0, 0.56, 0.0, 0),
              ("wall", 8, 3.0, 0, -0.41, 0), ("wall", -52, 7.0, -0.38, -0.25, 0),
              ("wall", 172, 18.0, 0, 0.40, 0), ("wall", 158, 24.0, 0.20, 0.36, 0)],
        carves=[[("!flat", 150, 7.0, 0, 0, 0.30), ("!wall", -5, 3.0, 0.30, -0.368, 0),   # bedding step: the front face above 0.3 m is
                 ("wall", 120, 6.0, 0.05, 0, 0)]],                                        # set back 0.17 m, fading to 0.05 at an oblique joint
        chips=[((0.5, -0.5, 0.7), 0.12)],
        habitats=["rocky_slope", "forest_edge", "open_meadow", "sheltered_bank", "trail_border"],
        collision={"class": "convex"}, budget=(150, 700), max_tilt=15.0, scale=(0.6, 1.5),
        notes="Simplified boulder on the cliff fracture family: long vertical left wall, 27 deg ramp opposite, front bedding step "
              "(0.05-0.17 m at 0.3 m, fading out), split back wall, bedding top dipping 7 deg, one chipped corner; origin at the contact "
              "centre, 0.15 m buried.",
    ),
}
rf.PARAMS.update({k: PARAMS_B[k] for k in ("cliff_corner_A", "boulder_medium_A")})
METHOD = {
    "cliff_corner_A": "one convex mass from fracture-frame planes: a 7-facet front chain, two inset ledge chains (tilted floors, "
                      "varying tread), one nose-crown spall, a recessed panel per arm, narrow chamfer",
    "boulder_medium_A": "one convex mass on the bedding dip (vertical front/left, 22-33 deg ramps right/back), toe step, split "
                        "back wall, chip, narrow chamfer, refine, distort",
}
MAKERS = {"cliff_corner_A": make_corner}
PARAMS_B.update(rfc.PARAMS_C)  # rubble_cluster_A, shore_boulder_A (rock_family_c.py keeps this file < 500 lines)
METHOD.update(rfc.METHOD_C)
MAKERS.update(rfc.MAKERS_C)


def build(asset_id: str) -> dict:
    P = PARAMS_B[asset_id]
    obj = MAKERS.get(asset_id, rf.make_object)(asset_id)
    skip = ("family", "seed", "habitats", "collision", "budget", "max_tilt", "scale", "notes")
    recipe = {"seed": P["seed"], "method": METHOD[asset_id], "params": {k: v for k, v in P.items() if k not in skip}}
    meta = nl.export_asset(obj, GROUP, asset_id, family=P["family"], habitats=P["habitats"],
                           collision=P["collision"], budget_tris=P["budget"], embed_depth=P["embed"],
                           scale_range=P["scale"], max_tilt_deg=P["max_tilt"], recipe=recipe, notes=P["notes"])
    nl.render_previews(obj, GROUP, asset_id)
    nl.save_blend(GROUP, asset_id)
    return meta
