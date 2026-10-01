"""shrub_B (spreading, rock-hugging shrub) for the understory family (plan 5.4). The shared Builder / finish
pipeline and the lobe construction live in understory_family.py; this module holds the PARAMS table (finite,
deterministic, written to metadata `recipe`) and the shrub_B-only geometry helpers (wall clamp, mound normals,
surface clump placement).
"""
from __future__ import annotations

import math

from mathutils import Matrix, Vector

import nature_lib as nl

UP = Vector((0.0, 0.0, 1.0))

# ---------------------------------------------------------------- shrub_B (spreading, rock-hugging)

SHRUB_B = {
    "seed": 4312,
    "embed": 0.04,
    "jitter": 0.28, "wob_freq": 2.0, "vertex_noise": 0.22,   # every outline breaks into 4-8 cm clumps
    "tufts": {1: 0, 2: 2, 3: 0}, "tuft_gain": 0.16, "tuft_sigma": 0.5,   # 2 soft nubs on each sub-2 lobe
    "boxiness": 0.95,        # slightly squared: flat crowns instead of round domes
    "normal_up_bias": 0.18,  # flat lobes already shade upward; keep lobe seams readable
    "highlight_mix": 0.12,   # darker than shrub_A: upper surfaces barely move toward shrub_light
    "span": 0.95,            # radial normaliser of the flex / colour / cavity fields (shrub_A: 0.7)
    "cav_height": 0.3,       # height over which ground cavity fades out (low shrub: shorter than A's 0.42)
    "mound": {"c": (0.0, -0.02), "a": 1.0, "b": 0.7, "h": 0.55, "sink": 0.15, "blend": 0.08},
    # Crest = 3 stepped sub-2 lobes (tops ~0.52 / 0.45 / 0.37 m) falling from -x to the low shelf on +x (tucks against a
    # rock; its +x face is walled flat at x = 0.86). Skirt lobes sit with their equators on / below the ground so the rim
    # flares onto it, and thin spill lobes reach past the mass. rz/rx <= 0.6 everywhere. sq = lower-half scale.
    # Surface clumps (see clump_lobes): small lobes seated on the big ones, they turn the smooth lobe outlines into leafy bumps.
    "clumps": {"seed": 77, "count": 18, "radius": [0.11, 0.19], "vertex_noise": 0.6, "min_dz": 0.3, "min_z": 0.03, "max_top": 0.565, "sink": 0.05,
               "spacing": 0.8, "k_gain": 1.0, "wob": 0.9, "normal_blend": 0.55},
    "lobes": [
        {"c": (-0.42, 0.07, 0.31), "r": (0.37, 0.29, 0.21), "yaw": 20, "tilt": 4, "sub": 2, "sq": 1.0, "col": "shrub", "moss": 0.3, "k": 0.94, "wob": 0.9, "cw": 3.0},    # crest 1
        {"c": (-0.08, -0.05, 0.245), "r": (0.34, 0.27, 0.20), "yaw": -20, "tilt": -5, "sub": 2, "sq": 1.0, "col": "shrub_deep", "moss": 0.45, "k": 0.83, "wob": 1, "cw": 3.0},  # crest 2
        {"c": (0.25, 0.05, 0.185), "r": (0.30, 0.25, 0.18), "yaw": 30, "tilt": 5, "sub": 2, "sq": 1.0, "col": "shrub", "moss": 0.3, "k": 0.8, "wob": 1, "cw": 3.0},      # crest 3
        {"c": (-0.56, -0.02, -0.02), "r": (0.29, 0.27, 0.17), "yaw": 40, "tilt": -4, "sub": 2, "sq": 1.0, "col": "shrub_deep", "moss": 0.4, "k": 0.91, "wob": 1},  # -x end
        {"c": (-0.18, 0.31, -0.04), "r": (0.44, 0.25, 0.19), "yaw": 8, "tilt": 6, "sub": 2, "sq": 1.0, "col": "shrub", "moss": 0.2, "k": 0.82, "wob": 1},   # back skirt
        {"c": (-0.06, -0.31, -0.04), "r": (0.5, 0.25, 0.19), "yaw": -10, "tilt": -6, "sub": 2, "sq": 1.0, "col": "shrub", "moss": 0.3, "k": 0.82, "wob": 1},     # front skirt
        {"c": (0.66, -0.2, -0.04), "r": (0.32, 0.26, 0.15), "yaw": -15, "tilt": 3, "sub": 2, "sq": 1.0, "col": "shrub", "moss": 0.25, "k": 0.9, "wob": 0.8, "wall": 0.86},   # low shelf
        {"c": (0.68, 0.17, -0.04), "r": (0.30, 0.25, 0.14), "yaw": 18, "tilt": -3, "sub": 2, "sq": 1.0, "col": "shrub_deep", "moss": 0.4, "k": 0.87, "wob": 0.8, "wall": 0.86},
        # thin spill lobes reaching 0.10-0.15 m past the mass (low side corners and the front)
        {"c": (0.4, -0.44, -0.02), "r": (0.22, 0.14, 0.07), "yaw": -25, "tilt": 0, "sub": 1, "sq": 1.0, "col": "shrub_deep", "moss": 0.4, "k": 0.87, "wob": 1},
        {"c": (0.42, 0.44, -0.02), "r": (0.2, 0.14, 0.07), "yaw": 20, "tilt": 0, "sub": 1, "sq": 1.0, "col": "shrub", "moss": 0.3, "k": 0.87, "wob": 1},
        {"c": (-0.46, 0.42, -0.02), "r": (0.2, 0.14, 0.07), "yaw": 25, "tilt": 0, "sub": 1, "sq": 1.0, "col": "shrub_deep", "moss": 0.4, "k": 0.87, "wob": 1},
    ],
    # root crown: bases 0.10-0.25 m from the centre, tops outward and up, ending inside the foliage
    "stems": [
        {"base": (0.08, -0.08, 0.0), "top": (0.25, -0.18, 0.08), "r0": 0.034, "r1": 0.024},
        {"base": (0.08, 0.12, 0.0), "top": (0.30, 0.25, 0.09), "r0": 0.032, "r1": 0.022},
        {"base": (-0.15, 0.08, 0.0), "top": (-0.56, 0.33, 0.14), "r0": 0.03, "r1": 0.021},
    ],
    "stem_sides": 5,
}


def wall_clamp(p: Vector, n: Vector, wall: float, margin: float = 0.05) -> tuple[Vector, Vector]:
    """Soft clamp of x to `wall`: a near-flat +x face (the side that is pushed against a rock)."""
    over = p.x - (wall - margin)
    if over <= 0.0:
        return p, n
    q = Vector(p)
    q.x = wall - margin + margin * math.tanh(over / margin)
    t = min(1.0, over / margin)
    return q, (n * (1.0 - t) + Vector((1.0, 0.0, 0.25)).normalized() * t).normalized()


def mound_blend(n: Vector, p: Vector, M: dict) -> Vector:
    """Blend a lobe normal toward the gradient of one broad ellipsoid over the whole shrub."""
    g = Vector(((p.x - M["c"][0]) / M["a"] ** 2, (p.y - M["c"][1]) / M["b"] ** 2, (p.z + M["sink"]) / M["h"] ** 2))
    return (n * (1.0 - M["blend"]) + g.normalized() * M["blend"]).normalized()


def lobe_rot(L: dict) -> Matrix:
    return Matrix.Rotation(math.radians(L["yaw"]), 3, "Z") @ Matrix.Rotation(math.radians(L["tilt"]), 3, "Y")


def lobe_field(L: dict, q: Vector) -> float:
    """< 1 inside the lobe ellipsoid, > 1 outside (wobble ignored)."""
    l = lobe_rot(L).inverted() @ (q - Vector(L["c"]))
    r = L["r"]
    sz = L["sq"] if l.z < 0.0 else 1.0
    return math.sqrt((l.x / r[0]) ** 2 + (l.y / r[1]) ** 2 + (l.z / (r[2] * sz)) ** 2)


def clump_lobes(P: dict) -> list[dict]:
    """Small flat lobes seated on the upper surface of the big lobes: 4-8 cm leafy bumps on the silhouette
    and the surface. Each keeps its parent's colour group and mostly its parent's surface normal, so they
    break the outline without lighting as separate balls. Deterministic (own seed), rejection sampled."""
    C, rnd = P["clumps"], nl.rng(P["clumps"]["seed"])
    wall = next((L["wall"] for L in P["lobes"] if "wall" in L), 9.0)   # clumps stay off the flat +x face
    parents = [L for L in P["lobes"] if L["sub"] >= 2]
    out: list[dict] = []
    for _ in range(4000):
        if len(out) >= C["count"]:
            break
        hit = surface_point(rnd, parents, C["min_dz"])
        if hit is None:
            continue
        L, surf, nrm = hit
        rad = rnd.uniform(*C["radius"])
        centre = surf - nrm * rad * C["sink"]
        if centre.z < C["min_z"] or centre.z + rad * 0.6 > C["max_top"] or centre.x + rad > wall - 0.05:
            continue
        if any((centre - Vector(o["c"])).length < C["spacing"] * (rad + o["r"][0]) for o in out):
            continue
        yaw = math.degrees(math.atan2(nrm.y, nrm.x))
        tilt = math.degrees(math.acos(max(-1.0, min(1.0, nrm.z))))
        out.append({"c": tuple(round(c, 3) for c in centre), "r": (round(rad, 3), round(rad * 0.85, 3), round(rad * 0.59, 3)),
                    "yaw": round(yaw + rnd.uniform(-20, 20), 1), "tilt": round(tilt, 1), "sub": 1, "sq": 1.0,
                    "col": L["col"], "moss": L.get("moss", 0.0), "k": round(L["k"] * C["k_gain"], 3), "wob": C["wob"],
                    "nref": tuple(round(c, 3) for c in nrm), "nb": C["normal_blend"], "vn": C["vertex_noise"]})
    return out


def surface_point(rnd, parents: list[dict], min_dz: float):
    """Random point on the upper surface of a random big lobe (weighted by footprint x `cw`): (lobe, point, normal)."""
    L = rnd.choices(parents, [q["r"][0] * q["r"][1] * q.get("cw", 1.0) for q in parents])[0]
    d = Vector((rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(0, 1))).normalized()
    if d.z < min_dz:
        return None
    rot, r = lobe_rot(L), L["r"]
    surf = rot @ Vector((d.x * r[0], d.y * r[1], d.z * r[2])) + Vector(L["c"])
    nrm = (rot @ Vector((d.x / r[0], d.y / r[1], d.z / r[2]))).normalized()
    if any(lobe_field(M, surf) < 0.93 for M in parents if M is not L):
        return None  # buried inside a neighbour
    return L, surf, nrm


SHRUB_B_META = dict(
    max_tilt_deg=10, habitats=["forest_edge", "rock_foot", "meadow_edge"],
    notes="Spreading variant, ~1.8 x 1.2 x 0.58 m. 8 big flat lobes (rz/rx <= 0.6): a crest of 3 stepped lobes (tops "
          "~0.52 / 0.45 / 0.37 m, clump bumps up to 0.57) falling from -x to a low shelf of 2 lobes on +x whose face is walled flat (x ~ 0.86, "
          "pushed against a rock), a -x end lobe and front / back skirt lobes. Skirt lobes sit with their equators "
          "on or below the ground so the rim flares onto it; 3 thin spill lobes reach past the mass. 18 derived clump "
          "lobes (recipe.derived_clumps) are seated on the upper surface to break the outline into leafy bumps; each keeps "
          "its parent's colour group and 55% of its parent's normal. Same lobe construction as shrub_A (icosphere "
          "lobes, per-lobe colour group, radial normals +18% up), but darker and more olive: shrub / shrub_deep "
          "with 20-45% moss, highlight mix 12%, mean foliage luminance ~0.11 (shrub_A 0.14). 3 short bark stems "
          "radiate from the root crown and end inside the foliage; only a few cm show through gaps. Grounded "
          "undersides and stem bases reach 4 cm below y=0 (embed_depth).")
