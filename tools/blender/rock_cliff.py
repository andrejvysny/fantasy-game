"""Cliff modules, revision 2: cliff_face_A and cliff_corner_A. Dispatched from rock_family.py main().

Same construction language as rock_family.py (planes from the fracture frame first, convex cutters, noise last), plus:
  * end tapers: each lateral end recedes into the slope. Extra mass planes turn the lowest stratum's front back
    (30-55 deg off the front plane) and close it with steep out-front / back-out facets; step cutters end the middle
    and crown strata earlier in hip-shaped risers (front-out, out, back-out joints), so seen along the wall the module
    steps down and back into the terrain instead of ending in a vertical rectangle.
  * broken top-back: the bedding top dips toward the back before a ramp of several facets (different strike and
    dip) plus notches, so the top-back edge has no long straight run and a partly exposed back reads as rock.
  * panels: tilted ledge floors (rock_family_b.bench_b), ledges that end before the module ends, diagonal fractures
    with 0.2-0.6 m set-backs across the lower stratum.
End geometry is authored per end in that end's own plan frame: `out` = azimuth pointing away from the module along
the wall, `front` = azimuth of the front faces there (plane azimuths: 0 = front -Y, 90 = +X).
    blender -b --factory-startup -P tools/blender/rock_family.py -- cliff_face_A cliff_corner_A
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent if "__file__" in globals() else "/Users/andrejvysny/Developer/godot/tools/blender"))

import bpy  # noqa: E402

import nature_lib as nl  # noqa: E402
import rock_family as rf  # noqa: E402
import rock_family_b as rfb  # noqa: E402  (v1 corner_params is the base of the v2 corner; make() swaps rf.PARAMS)


def _vec(az: float) -> tuple[float, float]:
    a = math.radians(az)
    return math.sin(a), -math.cos(a)


def _at(end: dict, along: float, side: float) -> tuple[float, float]:
    """Plan point `along` m in from the end's front corner (toward the module centre) and `side` m in front of the
    front line there (negative = behind it)."""
    (ux, uy), (fx, fy) = _vec(end["out"]), _vec(end["front"])
    return end["p"][0] - ux * along + fx * side, end["p"][1] - uy * along + fy * side


def taper(end: dict, cuts: list) -> list:
    """Mass planes for one end. cut = (blend, tilt, along, side, z): the plane's azimuth runs from the front (blend 0)
    to straight out along the wall (1) and beyond toward the back (> 1); tilt from +Z (90 = vertical); it passes
    through the end-frame point (along, side) at height z. Rock stays below/behind it."""
    out = []
    for blend, tilt, along, side, z in cuts:
        x, y = _at(end, along, side)
        out.append(("flat", round(end["front"] + blend * (end["out"] - end["front"]), 2), tilt, round(x, 3), round(y, 3), z))
    return out


def step(end: dict, floor: float, joints: list, floor_tilt: float = 10.0) -> list:
    """Stratum end: cutters removing everything above a floor at `floor` (dipping `floor_tilt` deg outward) that lies
    outside ANY of the joints, so the riser left behind is a convex hip of the joint planes. joint = (blend, lean,
    along, side): a fracture facing the blended azimuth (see taper), top leaning back `lean` deg, through (along, side)
    at the floor height."""
    x0, y0 = _at(end, joints[0][2], 0.0)
    fl = ("!flat", end["out"], floor_tilt, round(x0, 3), round(y0, 3), floor)
    out = []
    for blend, lean, along, side in joints:
        x, y = _at(end, along, side)
        out.append([("!wall", round(end["front"] + blend * (end["out"] - end["front"]), 2), lean, round(x, 3), round(y, 3), floor), fl])
    return out


def face_params() -> dict:
    """cliff_face_A. Aligned frame as rock_family.PARAMS: x along the face (+-4.8), -y front, z along the bedding normal;
    the frame dips 11 deg toward the right-back, so the left end is the high one."""
    P = dict(family="cliff_face", seed=1107, tilt=11.0, azimuth=35.0, yaw=5.0, height=6.0, embed=1.5, front=1.45,
             bevel=0.05, edge_len=0.95, distort=0.07, distort_freq=0.23)
    left, right = dict(p=(-4.8, -1.6), front=0.0, out=-90.0), dict(p=(4.8, -1.65), front=0.0, out=90.0)
    P["ends"] = dict(left=left, right=right)
    P["mass"] = [("flat", 0, 1.0, 0, 0, 6.0), ("!flat", 0, 0, 0, 0, -3.6),                  # bedding top, flat bottom
                 ("wall", -100, 4, -4.8, -0.7, 0), ("wall", 100, 4, 4.8, -0.65, 0),          # residual end walls
                 ("wall", -140, 10, -3.3, 2.0, 0), ("wall", 140, 18, 3.5, 2.0, 0),           # back corners (buried), broken
                 ("wall", -122, 24, -3.9, 1.3, 1.6), ("wall", 126, 30, 4.0, 1.2, 2.8),      # by steeper joints and
                 ("flat", -134, 62, -3.4, 1.5, 2.5),                                         # inclined upper facets
                 ("flat", -152, 52, -2.6, 2.2, 3.4), ("flat", 148, 46, 3.0, 2.0, 4.4),
                 ("wall", 176, 3, 0, 3.95, 0),                                               # buried back wall
                 # top dips toward the back, then a ramp of five facets turning with the plan (left ones face
                 # back-left), so the top-back edge is a broken polyline
                 ("flat", 188, 12, -2.5, -0.3, 6.0), ("flat", 171, 9, 1.8, -0.5, 6.0),
                 ("flat", 214, 30, -3.4, 0.9, 5.55), ("flat", 197, 35, -1.6, 1.25, 5.5), ("flat", 181, 25, 0.0, 1.4, 5.4),
                 ("flat", 164, 33, 1.7, 1.05, 5.45), ("flat", 149, 28, 3.3, 0.75, 5.35)]
    # The frame dip leans left-facing planes up to ~11 deg further back and right-facing ones ~10 deg forward, so
    # right-hand leans are authored larger. Lowest stratum: the front turns back ~40-45 deg, then a steep out-front
    # facet and a back-out facet close the end.
    P["mass"] += taper(left, [(0.5, 90, 1.2, 0.0, 0.0), (0.85, 80, 0.4, -0.9, 0.0), (1.4, 78, 0.6, -2.0, 0.0)])
    P["mass"] += taper(right, [(0.6, 86, 1.6, 0.0, 1.4), (0.85, 74, 0.4, -0.9, 1.4), (1.4, 70, 0.6, -2.0, 1.4)])
    P["arc"] = dict(points=[(-2.6, -1.6), (1.7, -1.7)], leans=[4])                            # dominant front plane
    P["benches"] = [  # ledges at different heights, floors tilted off the bedding, none spanning the whole width
        dict(points=[(-4.8, -0.75), (-2.4, -1.05), (1.0, -0.85), (3.2, -0.15), (4.9, 0.95)],    # mid ledge: inactive on
             floor=3.5, floor_az=90, floor_tilt=2.0, leans=[4, 3, 5, 6]),                       # the left (low ledge there)
        dict(points=[(-4.8, -0.3), (-2.4, -0.6), (1.0, -0.3), (3.2, 0.45), (4.9, 1.5)],         # crown ledge, left/centre
             floor=4.85, floor_az=-80, floor_tilt=9.0, leans=[4, 3, 6, 5], joint=("wall", 118, 2, 1.2, 0, 0)),
    ]
    P["carves"] = [
        [("wall", 112, 2, -2.6, -1.4, 0), ("!wall", -14, 5, -2.6, -1.25, 0)],                # left panel set back
        [("wall", -112, 12, 1.7, -1.4, 0), ("!wall", 10, 6, 1.7, -1.15, 0)],                 # right panel set back
        [("flat", 90, 52, -1.2, 0, 1.2), ("!wall", -6, 4, -1.0, -1.38, 0)],                   # diagonal fracture, 0.25 set-back
        [("flat", -90, 40, 3.0, 0, 1.6), ("!wall", 18, 5, 2.6, -1.0, 0)],                     # diagonal fracture, 0.5 set-back
        [("!flat", -100, 6, -2.6, -0.95, 2.2), ("!wall", -12, 4, -2.6, -0.95, 0),             # low ledge, left of an oblique
         ("wall", 105, 35, -1.0, 0, 2.2)],                                                  # joint (ramps up to the mid ledge)
        [("wall", -95, -35, -1.0, 0, 5.3), ("wall", 70, -40, -0.3, 0, 5.3), ("!wall", 165, 3, 0, 1.0, 0),  # V-notches in
         ("!flat", 185, 16, -0.6, 1.3, 5.3)],                                                            # the top-back edge
        [("wall", -70, -38, 1.3, 0, 5.1), ("wall", 100, -32, 1.9, 0, 5.1), ("!wall", 192, 4, 0, 1.2, 0),
         ("!flat", 170, 22, 1.6, 1.6, 5.1)],
    ]
    P["chips"] = [((-0.55, -0.3, 0.78), 0.4), ((0.5, -0.3, 0.8), 0.25), ((0.35, -0.6, 0.72), 0.3)]
    # upper strata end earlier (crown at s ~2.4, middle at s ~1.3), each riser a hip of 3-4 joints (front-out, out,
    # back-out), so the end steps down and back toward the ground in broken stages
    P["steps"] = (step(left, 4.3, [(0.55, 2, 2.6, 0.0), (1.0, 12, 2.2, -1.1), (1.3, 14, 2.3, -2.0), (1.6, 20, 2.6, -2.8)],
                       floor_tilt=10)
                  + step(left, 2.4, [(0.45, 2, 1.5, 0.0), (1.0, 10, 1.2, -1.0), (1.45, 14, 1.4, -2.2)], floor_tilt=12)
                  + step(right, 4.9, [(0.6, 10, 2.3, 0.0), (1.0, 24, 1.9, -1.1), (1.45, 26, 2.1, -2.3)], floor_tilt=9)
                  + step(right, 2.8, [(0.5, 8, 1.2, 0.0), (1.05, 20, 0.9, -1.0), (1.45, 22, 1.1, -2.1)], floor_tilt=11))
    P.update(habitats=["rocky_slope", "canyon"], collision={"class": "trimesh"}, budget=(1500, 5000), max_tilt=8.0,
             scale=(0.8, 1.3),
             notes="One mass: dominant front plane with unequal set-back panels (0.15-0.5 m) and diagonal fractures, "
                   "three tilted ledges at different heights (low left 2.2 m, mid centre/right 3.5 m, crown left/centre "
                   "4.85 m), none across the whole width. Ends recede into the slope: the lowest stratum's front turns "
                   "back ~40-45 deg, crown and middle strata end ~2.4 / ~1.3 m before each end in hip-shaped risers, so "
                   "the end height falls from ~5.5 m to < 2 m over the last ~2-3 m. Top dips toward the back into a "
                   "broken 5-facet ramp with two V-notches + buried wall: bury with terrain rising behind >= ~35 deg. "
                   "Origin 1 m behind the front base, face toward -Y.")
    return P


def corner_params() -> dict:
    """cliff_corner_A: rock_family_b.corner_params (7-facet convex front chain round a broken arris, inset ledge chains)
    with the face's revisions: arm ends recede into the slope in stratum steps, the top dips toward the back into a
    broken ramp, and each arm's lower panel takes a diagonal fracture. Arms are shorter than the face, so the steps
    are tighter (crown ends ~1.9 m, middle ~1.1 m in from each arm end)."""
    P = rfb.corner_params()
    # arm ends pushed 0.4 / 0.7 m further out than v1 (the taper takes the visible tip back; the buried base keeps the bbox)
    left, right = dict(p=(-3.69, 3.19), front=-52.0, out=-128.0), dict(p=(4.45, 4.07), front=50.0, out=134.0)
    P["ends"] = dict(left=left, right=right)
    P["mass"] = [("flat", 0, 1.0, 0, 0, 6.0), ("!flat", 0, 0, 0, 0, -3.6), ("flat", 135, 5.0, 0.2, 1.6, 5.98),  # right top facet
                 ("wall", 134, 0, 4.45, 4.07, 0), ("wall", -128, 0, -3.69, 3.19, 0),                           # residual arm ends
                 ("wall", 176, 3, 0, 4.7, 0),                                                                  # buried back wall
                 ("flat", 170, 10, -1.2, 1.5, 6.0), ("flat", 194, 12, 1.3, 1.3, 6.0),                          # top dips back
                 ("flat", 208, 31, -2.2, 3.1, 5.6), ("flat", 186, 35, -0.3, 3.4, 5.5), ("flat", 160, 27, 1.9, 3.3, 5.5)]  # ramp
    # arm ends are only ~1.1 m deep (the arms run back to the buried wall): the front turns back and one out-front
    # facet closes the base; crown and middle strata end in two-facet hips
    P["mass"] += taper(left, [(0.5, 90, 1.0, 0.0, 0.4), (0.85, 80, 0.4, -0.5, 0.4)])
    P["mass"] += taper(right, [(0.5, 86, 1.3, 0.0, 0.4), (0.85, 76, 0.7, -0.5, 0.4)])
    pl = rfb.lean_for(-52.0, 4.5, P["tilt"], P["azimuth"])
    P["carves"] = [  # v1's right recessed panel is replaced by the diagonal fracture (it left a slit at the end step)
        [("wall", 105, 1, -2.69, 2.07, 0), ("!wall", -52.0, pl, -2.47, 2.27, 0), ("flat", 0, 1.0, 0, 0, 3.35)],  # left panel
        [("flat", -51.6, 45, 1.6, 1.26, 1.7), ("!wall", 38.4, 4, 1.37, 1.53, 0)],      # right arm: diagonal fracture, 0.35 set-back
        [("flat", 56, 50, -1.0, 0.66, 1.4), ("!wall", -34, 3, -0.86, 0.85, 0)],        # left arm: diagonal fracture, 0.25 set-back
    ]
    P["steps"] = (step(left, 4.0, [(0.55, 2, 1.9, 0.0), (1.0, 12, 1.6, -0.7)], floor_tilt=10)
                  + step(left, 2.1, [(0.45, 2, 1.1, 0.0), (1.0, 10, 0.9, -0.6)], floor_tilt=12)
                  + step(right, 4.0, [(0.6, 8, 2.2, 0.0), (1.0, 20, 1.9, -0.7)], floor_tilt=9)
                  + step(right, 2.3, [(0.5, 6, 1.4, 0.0), (1.05, 16, 1.2, -0.6)], floor_tilt=11))
    P["notes"] = ("Convex corner module: two faces ~108 deg apart (each a 3-facet chain, unequal widths) around a broken "
                  "arris facet. Strata match cliff_face_A: a 0.65-0.95 m ledge at ~3.2 m wraps the arris and both arms "
                  "(tilted floor), a smaller upper ledge fades out along the right arm, diagonal fractures (0.25-0.35 m "
                  "set-back) on both arms' lower stratum plus a recessed left panel, one nose-crown spall. Arm ends "
                  "recede into the slope: the front turns back ~45 deg and crown/middle strata end ~1.9 / ~1.1 m before "
                  "the arm end in hip-shaped risers. Top dips toward the back into a broken 3-facet ramp + buried wall: "
                  "bury with terrain rising behind. Origin ~1.5 m behind the arris, arris bisector toward -Y. Pairs with "
                  "cliff_face_A ends rotated about +38 / -34 deg.")
    return P


PARAMS = {"cliff_face_A": face_params(), "cliff_corner_A": corner_params()}
METHOD = {
    "cliff_face_A": "one convex mass from fracture-frame planes with tapered ends (oblique front turn-backs, falling "
                    "top facets, end steps) and a broken back ramp, carved by tilted-floor ledges, set-backs, diagonal "
                    "fractures and two back notches, corner spalls, narrow chamfer, refine, distort",
    "cliff_corner_A": "one convex mass from fracture-frame planes: a 7-facet front chain with tapered arm ends (oblique "
                      "turn-backs, stratum end steps) and a broken back ramp, two inset ledge chains (tilted floors, "
                      "varying tread), a diagonal fracture per arm, a recessed left panel, one nose-crown spall, narrow chamfer",
}


def make(asset_id: str) -> bpy.types.Object:
    """rf.make_object with tilted-floor benches; the end steps are appended to the carves."""
    P = dict(PARAMS[asset_id])
    P["carves"] = P.get("carves", []) + P.get("steps", [])
    saved_bench, saved = rf.bench, rf.PARAMS.get(asset_id)
    rf.bench, rf.PARAMS[asset_id] = rfb.bench_b, P
    try:
        return rf.make_object(asset_id)
    finally:
        rf.bench = saved_bench
        if saved is None:
            rf.PARAMS.pop(asset_id)
        else:
            rf.PARAMS[asset_id] = saved


def build(asset_id: str) -> dict:
    P = PARAMS[asset_id]
    obj = make(asset_id)
    skip = ("family", "seed", "habitats", "collision", "budget", "max_tilt", "scale", "notes")
    recipe = {"seed": P["seed"], "method": METHOD[asset_id], "params": {k: v for k, v in P.items() if k not in skip}}
    meta = nl.export_asset(obj, rf.GROUP, asset_id, family=P["family"], habitats=P["habitats"],
                           collision=P["collision"], budget_tris=P["budget"], embed_depth=P["embed"],
                           scale_range=P["scale"], max_tilt_deg=P["max_tilt"], recipe=recipe, notes=P["notes"])
    nl.render_previews(obj, rf.GROUP, asset_id)
    nl.save_blend(rf.GROUP, asset_id)
    return meta
