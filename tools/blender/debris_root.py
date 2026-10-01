"""root_flare_A geometry (plan 5.3), built from the PARAMS in debris_family.py.
Buttress roots around an OPEN hole: every root is a closed wedge (crest, shoulders, feet, buried bottom) on a
ground-level spine. The crest is based on the real spruce_mature_A trunk surface (r 0.44-0.56 at z 0-0.3, ground
spurs to r 0.74): tall where the root leaves the trunk, relaxing to a low round surface root, then the whole section
sinks into the soil so each tip ends blunt, never as a flat blade.
"""
from __future__ import annotations

import math

from mathutils import Vector

from debris_mesh import Builder, clamp, smoothstep, Z

RING_U = (0.0, 0.30, 0.75, 1.0)    # hump section: lateral offset (half widths) of crest, upper, lower shoulder, foot
RING_F = (1.0, 0.90, 0.50, 0.0)    # ... and height as a fraction of the crest-over-foot span
R_REF = 0.5                        # m: radius where roots leave the trunk (measured on spruce_mature_A)
DIVE_FROM = 0.84                   # spine station where the section starts to sink
STATIONS = (0.0, 0.18, 0.36, 0.54, 0.68, 0.86, 1.0)    # root spine stations (fork leaves at index 4, s = 0.68)
FORK_STATIONS = (0.0, 0.22, 0.46, 0.70, 0.86, 1.0)


def root_profile(s: float, u: float, R: dict, ph: float) -> tuple:
    """Crest height, half width and crest twist (rad) at spine station s; u = 0 at the trunk surface .. 1 at the tip.
    Height falls almost linearly from h0 (at r = R_REF) to the round `tail` root, width tapers more slowly."""
    h = R["tail"] + (R["h0"] - R["tail"]) * (1.0 - u) ** 1.15 * (1.0 + 0.10 * math.sin(6.5 * s + ph)
                                                               * smoothstep(0.05, 0.3, s))
    hw = R["hw1"] + (R["hw0"] - R["hw1"]) * (1.0 - s) ** 1.7
    return h, hw, R["tw"] * math.sin(math.pi * s ** 0.8)


def root_rings(P: dict, pts: list, prof: list, stations: tuple, dive: float) -> list:
    """Hump rings on a ground-level spine, closed by a point at each end. From DIVE_FROM on the whole section sinks
    (crest first, feet and bottom follow) so the tip enters the soil blunt and round."""
    n, foot = len(pts), P["foot"]
    rings = [[pts[0] - (pts[1] - pts[0]).normalized() * 0.03 + Z * (0.4 * prof[0][0])]]
    zt = 0.0
    for i, (p, (h, hw, tw)) in enumerate(zip(pts, prof)):
        lat = Z.cross(pts[min(i + 1, n - 1)] - pts[max(i - 1, 0)]).normalized()
        zc = h - dive * smoothstep(DIVE_FROM, 1.0, stations[i])
        zf = min(foot, zc - 0.06)
        zb = min(-P["depth"] * (1.0 - 0.4 * stations[i]), zf - 0.02)
        sh, zt = math.sin(tw), zb

        def at(u: float, f: float, side: float = 1.0) -> Vector:
            z = zf + (zc - zf) * f
            return p + lat * (side * u * hw + (z - zf) * sh) + Z * z

        half = [at(u, f, 1.0) for u, f in zip(RING_U, RING_F)]
        other = [at(u, f, -1.0) for u, f in zip(RING_U, RING_F)]
        rings.append([half[0], half[1], half[2], half[3], p + Z * zb, other[3], other[2], other[1]])
    end = pts[-1] + (pts[-1] - pts[-2]).normalized() * 0.02
    rings.append([Vector((end.x, end.y, zt + 0.02))])
    return rings


def add_root(b: Builder, P: dict, R: dict) -> dict:
    az = math.radians(R["az"])
    d = Vector((math.cos(az), math.sin(az), 0.0))
    lat = Z.cross(d)
    ph = b.rng.uniform(0.0, 6.28)
    pts, prof = [], []
    for s in STATIONS:
        r = P["r_in"] + s * (R["reach"] - P["r_in"])
        pts.append(d * r + lat * (R["wander"] * math.sin(math.pi * (1.6 * s + 0.3)) * smoothstep(0.0, 0.3, s)))
        h, hw, tw = root_profile(s, clamp((r - R_REF) / (R["reach"] - R_REF)), R, ph)
        prof.append((h + 0.6 * max(R_REF - r, 0.0), hw, tw))   # inner end stays high, inside the trunk
    dive = R["tail"] + 0.03
    b.tube(root_rings(P, pts, prof, STATIONS, dive), b.new_part("root", ridge=b.rng.uniform(0.65, 1.0)))
    if "fork" in R:
        add_fork(b, P, R["fork"], pts, prof, ph)
    return {"az": R["az"], "reach": R["reach"], "h_at_trunk": round(R["h0"], 3)}


def add_fork(b: Builder, P: dict, F: dict, pts: list, prof: list, ph: float) -> None:
    """Child root leaving the parent's flank at spine index F['at'], about half its size, diverging by F['ang'] deg."""
    i = F["at"]
    tan = (pts[i + 1] - pts[i - 1]).normalized()
    ang = math.radians(F["ang"]) * F["side"]
    d = Vector((tan.x * math.cos(ang) - tan.y * math.sin(ang), tan.x * math.sin(ang) + tan.y * math.cos(ang), 0.0))
    lat = Z.cross(d)
    h, hw, _ = prof[i]
    child = dict(h0=h * F["size"], hw0=hw * F["size"], hw1=F["hw1"], tw=-0.3 * F["side"], tail=F["tail"])
    cpts = [pts[i] + d * (F["length"] * s) + lat * (0.05 * F["side"] * math.sin(math.pi * s)) for s in FORK_STATIONS]
    cprof = [root_profile(s, s, child, ph + 1.7) for s in FORK_STATIONS]
    dive = F["tail"] + 0.03
    b.tube(root_rings(P, cpts, cprof, FORK_STATIONS, dive), b.new_part("root", ridge=b.rng.uniform(0.65, 1.0)))


def build_root(P: dict) -> Builder:
    b = Builder(P["seed"])
    b.stats = {"roots": [add_root(b, P, R) for R in P["roots"]]}
    return b
