"""Prop fill (valley_habitats.json 'props'): rocks, logs, root flares, shrubs, ferns, reeds.

Order: rock families, fallen_log, root_flare, then the rest in file order. Every family has its
own hashed stream; spacing is footprint based against the same family and against all
already placed trees (trunks) and rocks/logs ('solids').
"""
from __future__ import annotations

import math

import numpy as np
from scipy import ndimage as ndi

import candidates as cd
from assets import ROCK_FAMILIES, Asset, family_assets
from common import RES, bilinear, disc_stamp, hash_parts, noise, smoothstep, str_hash, to_u32, unit
from rockground import ground_rock
from spatial import Box, Inst, SpacingHash, ground_height, terrain_tilt, zone_of

TURN_STONE_FAMILIES = ("boulder_medium", "rubble_cluster")
TURN_STONE_RULE = {"spacing": 1.8, "ground": "median", "sink": 0.05}
TURN_STONE_DENSITY = 8.0  # per 100 m2 inside the route 'stones_on_turns' band
TALL_PROP_M = 0.5  # taller props also keep out of the route shoulder (clearance envelope)
OUTCROP_RADIUS_M = (2.0, 4.5)
DOWNHILL_JITTER_DEG = 8.0
OUTCROP_JITTER_DEG = 12.0


def prop_order(rules: dict) -> list[str]:
    rocks = [k for k in rules if k in ROCK_FAMILIES]
    mid = [k for k in ("fallen_log", "root_flare") if k in rules]
    return rocks + mid + [k for k in rules if k not in rocks and k not in mid]


def _proximity(mask: np.ndarray, r0: float, r1: float) -> np.ndarray:
    if not mask.any():
        return np.zeros(mask.shape)
    return 1.0 - smoothstep(r0, r1, ndi.distance_transform_edt(~mask))


def _mask_of(insts: list[Inst], radius: bool = True) -> np.ndarray:
    m = np.zeros((RES, RES), dtype=np.float32)
    for i in insts:
        disc_stamp(m, i.x, i.z, max(i.radius if radius else 0.6, 0.6), 1.0, profile="hard", mode="max")
    return m > 0.5


def prop_density(fam: str, rule: dict, ctx: dict) -> np.ndarray:
    """Instances per 100 m2 for one family (before exclusions and spacing)."""
    f = ctx["f"]
    d = np.zeros((RES, RES))
    for hab, v in rule.get("habitats", {}).items():
        w = f["rock_foot"] if rule.get("at_rock_foot") and hab == "rocky_slope" else f.get(hab)
        if w is not None:
            d += w * float(v)
    if "patch_m" in rule:
        d *= 1.6 * smoothstep(0.42, 0.62, noise("prop_patch:" + fam, rule["patch_m"]))
    if "near_rock_boost" in rule:
        rocks = (ctx["t"]["splat_rock"] > 0.5) | _mask_of(ctx["solids_rock"])
        d *= 1.0 + (float(rule["near_rock_boost"]) - 1.0) * _proximity(rocks, 0.5, 4.0)
    if "near_trunk_boost" in rule:
        d *= 1.0 + (float(rule["near_trunk_boost"]) - 1.0) * _proximity(_mask_of(ctx["trees"], False), 0.5, 3.5)
    if "near_log_boost" in rule:
        d *= 1.0 + (float(rule["near_log_boost"]) - 1.0) * _proximity(_mask_of(ctx["logs"]), 0.3, 3.0)
    if "needs_canopy" in rule:
        nc = float(rule["needs_canopy"])
        d *= smoothstep(nc - 0.1, nc + 0.1, ctx["canopy"])
    if "shore_distance_m" in rule:
        a, b = rule["shore_distance_m"]
        sd = f["shore_distance"]
        d *= smoothstep(a - 0.3, a + 0.3, sd) * (1.0 - smoothstep(b - 0.3, b + 0.3, sd))
    if rule.get("sheltered_only"):
        d *= smoothstep(0.4, 0.6, f["sheltered"])
    peak = max([float(v) for v in rule.get("habitats", {}).values()] or [0.0])
    for p in ctx["patches"]:
        if p["field"] == fam:
            disc_stamp(d, p["at"][0], p["at"][1], float(p["radius"]), float(p["strength"]) * peak)
    return d


def _yaws(c: cd.Cands, rule: dict, f: dict, lead: np.ndarray | None, lead_yaw: np.ndarray | None) -> np.ndarray:
    jit = c.u(cd.D_EXTRA) * 2.0 - 1.0
    if rule.get("face") == "downhill":
        gx, gz = bilinear(f["grad_x"], c.x, c.z), bilinear(f["grad_z"], c.x, c.z)
        yaw = np.arctan2(-gx, -gz) + np.radians(DOWNHILL_JITTER_DEG) * jit
    else:
        yaw = c.u(cd.D_YAW) * math.tau - math.pi
    if lead is not None and lead_yaw is not None and len(lead):
        yaw = lead_yaw[lead] + np.radians(OUTCROP_JITTER_DEG) * jit
    return yaw


def _allowed(c: cd.Cands, r: np.ndarray, tall: np.ndarray, rule: dict, ctx: dict) -> np.ndarray:
    f = ctx["f"]
    core, shoulder, _ = ctx["routes"].edges(c.x, c.z)
    ok = (core >= r) & (~tall | (shoulder >= r))
    ok &= bilinear(f["painted_path"], c.x, c.z) <= 0.5
    ok &= ~ctx["excl"].blocked(c.x, c.z, r)
    lo = rule.get("shore_distance_m", [0.3, 0])[0]
    ok &= bilinear(f["shore_distance"], c.x, c.z) >= min(lo, 0.3)
    return ok


def _batch(fam: str, rule: dict, names: list[str], dens: np.ndarray, ctx: dict) -> list[tuple]:
    assets = ctx["assets"]
    c = cd.cells("prop:" + fam, float(rule["spacing"]), dens, ctx["seed"], ctx["zones"])
    c = c.take(c.u(cd.D_ACCEPT) < bilinear(dens, c.x, c.z) * c.cell * c.cell / 100.0)
    parts: list[tuple[cd.Cands, np.ndarray | None]] = [(c, None)]
    if "outcrop_group" in rule:
        m, lead = cd.group_members(c, 1.0, tuple(rule["outcrop_group"]), OUTCROP_RADIUS_M,
                                   ctx["seed"], ctx["zones"])
        parts.append((m, lead))
    lead_prio, lead_yaw = c.u(cd.D_PRIORITY), _yaws(c, rule, ctx["f"], None, None)
    rows = []
    for pi, (cc, lead) in enumerate(parts):
        vi = np.minimum((cc.u(cd.D_VARIANT) * len(names)).astype(np.int64), len(names) - 1)
        lo = np.array([assets[n].scale_range[0] for n in names])[vi]
        hi = np.array([assets[n].scale_range[1] for n in names])[vi]
        s = lo + cc.u(cd.D_SCALE) * (hi - lo)
        corner = np.array([_corner(assets[n]) for n in names])[vi] * s
        tall = np.array([assets[n].height >= TALL_PROP_M for n in names])[vi]
        yaw = lead_yaw if pi == 0 else _yaws(cc, rule, ctx["f"], lead, lead_yaw)
        prio = lead_prio if pi == 0 else lead_prio[lead]
        ok = _allowed(cc, corner, tall, rule, ctx)
        sp = float(rule["spacing"]) if pi == 0 else 0.0
        for j in np.nonzero(ok)[0]:
            leader = int(c.iid[lead[j]]) if lead is not None else -1
            rows.append((float(prio[j]), int(cc.slot[j]), int(cc.iid[j]), names[vi[j]], float(cc.x[j]),
                         float(cc.z[j]), float(s[j]), float(yaw[j]), float(corner[j]), sp, leader))
    rows.sort(key=lambda r: (r[0], r[1], r[2]))
    return rows


def _corner(a: Asset) -> float:
    return math.hypot(max(abs(a.bbox_min[0]), abs(a.bbox_max[0])), max(abs(a.bbox_min[2]), abs(a.bbox_max[2])))


def _ground(a: Asset, rule: dict, x: float, z: float, yaw: float, s: float,
            ctx: dict) -> tuple[float, float, float] | str:
    """(y, tilt_x, tilt_z), or the rejection reason for a rock that the spot cannot hold."""
    t, f = ctx["t"], ctx["f"]
    box = Box.of(a, x, z, yaw, s)
    rule_g = rule.get("ground", "median" if a.is_rock else "center")
    sink = float(rule.get("sink", 0.0))
    y = ground_height(t["height"], box, rule_g) - sink
    if a.is_rock:
        fit = ground_rock(t["height"], a, x, z, yaw, s, y, sink, fill=True, max_tilt=rule.get("max_tilt"),
                          rise_limit=rule.get("rise_limit"))
        return fit.reject or (fit.y, fit.tilt_x, fit.tilt_z)
    gx = bilinear(f["grad_x"], np.array([x]), np.array([z]))
    gz = bilinear(f["grad_z"], np.array([x]), np.array([z]))
    tx, tz = terrain_tilt(gx, gz, a.max_tilt_deg)
    return y, float(tx[0]), float(tz[0])


def _place_family(fam: str, rule: dict, names: list[str], dens: np.ndarray, ctx: dict) -> list[Inst]:
    assets = ctx["assets"]
    own = ctx["family_hash"].setdefault(fam, SpacingHash(8.0))
    solid = ctx["solid"]
    out: list[Inst] = []
    accepted: set[int] = set()
    for prio, slot, iid, name, x, z, s, yaw, r, sp, leader in _batch(fam, rule, names, dens, ctx):
        a = assets[name]
        if leader >= 0 and leader not in accepted:
            continue
        rs = r * (0.9 if a.is_rock else 0.5)
        if not own.clear(x, z, r, sp, 0.8) or not solid.clear(x, z, rs, 0.0, 1.0):
            continue
        g = _ground(a, rule, x, z, yaw, s, ctx)
        if isinstance(g, str):
            ctx["rock_rejects"][f"{fam}: {g}"] += 1
            continue
        y, tx, tz = g
        own.add(x, z, r, sp)
        accepted.add(iid)
        inst = Inst(iid, name, fam, x, y, z, math.remainder(yaw, math.tau), s, tx, tz,
                    source="props." + fam, radius=r, allow_water="shore_distance_m" in rule)
        if a.is_rock or fam == "fallen_log":
            solid.add(x, z, r * 0.9, 0.0)
            (ctx["solids_rock"] if a.is_rock else ctx["logs"]).append(inst)
        out.append(inst)
    return out


def _root_flares(fam: str, rule: dict, names: list[str], ctx: dict) -> list[Inst]:
    out = []
    fam_h = str_hash("family:prop:" + fam)
    for tr in ctx["trees"]:
        if ctx["assets"][tr.asset].family != rule["at_tree"]:
            continue
        key = hash_parts(ctx["seed"], str_hash("zone:" + tr.zone), fam_h, tr.iid)
        if float(unit(key, cd.D_ACCEPT)) >= float(rule.get("probability", 1.0)):
            continue
        a = ctx["assets"][names[min(int(float(unit(key, cd.D_VARIANT)) * len(names)), len(names) - 1)]]
        lo, hi = a.scale_range
        s = lo + float(unit(key, cd.D_SCALE)) * (hi - lo)
        yaw = float(unit(key, cd.D_YAW)) * math.tau - math.pi
        g = _ground(a, rule, tr.x, tr.z, yaw, s, ctx)
        if isinstance(g, str):
            continue
        y, tx, tz = g
        out.append(Inst(int(to_u32(hash_parts(fam_h, tr.iid, 0, 0))), a.asset_id, fam, tr.x, y, tr.z,
                        yaw, s, tx, tz, source="props." + fam, radius=a.radius * s))
    return out


def _turn_stones(ctx: dict) -> list[Inst]:
    """Stones on the outer side of sharp route bends (routes 'stones_on_turns')."""
    band = ctx["f"].get("turn_stones")
    if band is None or not band.any():
        return []
    names = sorted(n for fam in TURN_STONE_FAMILIES for n in family_assets(ctx["assets"], fam))
    if not names:
        ctx["skipped"].append({"asset": "/".join(f + "_*" for f in TURN_STONE_FAMILIES),
                               "rule": "routes.stones_on_turns", "reason": "no asset of family"})
        return []
    return _place_family("turn_stones", TURN_STONE_RULE, names, band * TURN_STONE_DENSITY, ctx)


def place_props(ctx: dict, rules: dict) -> list[Inst]:
    out: list[Inst] = []
    order = prop_order(rules)
    n_rocks = sum(1 for k in order if k in ROCK_FAMILIES)
    for k, fam in enumerate(order):
        if k == n_rocks:
            out += _zone_tag(_turn_stones(ctx), ctx)
        rule = rules[fam]
        if fam == "fallen_log":  # logs lie across the slope contour: front (+z) faces downhill
            rule = dict(rule, face=rule.get("face", "downhill"))
        names = family_assets(ctx["assets"], fam)
        dens = None if "at_tree" in rule else prop_density(fam, rule, ctx)
        if dens is not None:
            ctx["densities"][fam] = dens
        if not names:
            ctx["skipped"].append({"asset": fam + "_*", "rule": "props." + fam, "reason": "no asset of family"})
            continue
        got = _root_flares(fam, rule, names, ctx) if dens is None else _place_family(fam, rule, names, dens, ctx)
        out += _zone_tag(got, ctx)
    if n_rocks == len(order):
        out += _zone_tag(_turn_stones(ctx), ctx)
    return out


def _zone_tag(got: list[Inst], ctx: dict) -> list[Inst]:
    zones = zone_of(ctx["zones"], np.array([i.x for i in got]), np.array([i.z for i in got]))
    for inst, zn in zip(got, zones):
        inst.zone = str(zn)
    return got
