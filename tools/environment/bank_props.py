"""Bank dressing (valley_habitats.json 'banks.props', plan 7E/7F/7J): stones, rocks, reeds and
shrubs on the bank character fields (banks.py).

Placed after every other family (cliffs included) on their own hash streams ('bank:<rule>'),
so no tree, prop or cliff moves. Spacing is footprint based against all trunks, rocks and logs
(the shared solid hash), cliff module footprints, the rule itself and same-family plants.
Only assets listed in a rule's 'in_water' may stand in water, up to that depth (m).
"""
from __future__ import annotations

import math
from collections import Counter

import numpy as np

import candidates as cd
from assets import Asset
from cliffs import Registry
from common import RES, bilinear, hash_parts, str_hash, to_u32
from props import TALL_PROP_M, _corner, _ground, _zone_tag
from spatial import Box, Inst, SpacingHash

MIN_LAND_SD_M = 0.3  # assets not allowed in water keep this far from the water line
FOOTPRINT_K = 0.8  # same-rule overlap test: centres >= k x (r_a + r_b) apart (props default)
MEMBER_MIN_WEIGHT = 0.25
ALONG_JITTER_DEG = 20.0  # cluster members need this much of the rule's character field


def _density(rule: dict, f: dict) -> tuple[np.ndarray, np.ndarray]:
    """(instances per 100 m2, character weight 0..1) of one rule."""
    d = np.zeros((RES, RES))
    w = np.zeros((RES, RES))
    for key, v in rule["fields"].items():
        d += f[key] * float(v)
        w += f[key]
    if "require" in rule:
        d *= f[rule["require"]]
        w *= f[rule["require"]]
    return d, np.clip(w, 0.0, 1.0)


def _snap(c: cd.Cands, rule: dict, ctx: dict) -> cd.Cands:
    """Move each candidate across the shore to a hashed shore distance inside the rule's
    shore_distance_m window (two Newton steps on the signed shore distance): the window is a
    narrow strip along the water line, the density field a band several metres wide. Cluster
    members are snapped too, so a cluster spreads along the shore at varied distances."""
    f = ctx["f"]
    gx, gz = ctx["bank_sd_grad"]
    lo, hi = rule["shore_distance_m"]
    target = lo + c.u(cd.D_EXTRA) * (hi - lo)
    x, z = c.x.copy(), c.z.copy()
    for _ in range(2):
        ex, ez = bilinear(gx, x, z), bilinear(gz, x, z)
        k = (bilinear(f["shore_distance"], x, z) - target) / np.maximum(ex * ex + ez * ez, 0.25)
        x, z = x - k * ex, z - k * ez
    return cd.Cands(c.fam, c.cell, c.ix, c.iz, c.slot, x, z, c.key, c.iid)


def _candidates(name: str, rule: dict, dens: np.ndarray, ctx: dict) -> tuple[cd.Cands, cd.Cands, np.ndarray]:
    c = cd.cells("bank:" + name, float(rule["spacing"]), dens, ctx["seed"], ctx["zones"])
    c = _snap(c.take(c.u(cd.D_ACCEPT) < bilinear(dens, c.x, c.z) * c.cell * c.cell / 100.0), rule, ctx)
    lo, hi = rule.get("cluster", [1, 1])
    m, lead = cd.group_members(c, 1.0, (int(lo), int(hi)), tuple(rule.get("cluster_radius_m", [1.0, 2.0])),
                               ctx["seed"], ctx["zones"])
    return c, _snap(m, rule, ctx), lead


def _attrs(cc: cd.Cands, rule: dict, ctx: dict) -> dict:
    names = sorted(rule["assets"])
    vi = cd.pick_weighted(cc.u(cd.D_VARIANT), names, [float(rule["assets"][n]) for n in names])
    assets = [ctx["assets"][n] for n in names]
    lo = np.array([a.scale_range[0] for a in assets])[vi]
    hi = np.array([a.scale_range[1] for a in assets])[vi]
    s = lo + cc.u(cd.D_SCALE) * (hi - lo)
    if "scale" in rule:
        s = s * float(rule["scale"])
    return {"names": names, "vi": vi, "s": s, "r": np.array([_corner(a) for a in assets])[vi] * s,
            "tall": np.array([a.height for a in assets])[vi] * s >= TALL_PROP_M,
            "yaw": _yaw(cc, rule, ctx)}


def _yaw(cc: cd.Cands, rule: dict, ctx: dict) -> np.ndarray:
    """Random, or 'face': 'along_shore' (+z along the water line, either way, +-ALONG_JITTER_DEG):
    long low footprints (rubble) then lie on the contour instead of across the bank."""
    u = cc.u(cd.D_YAW)
    if rule.get("face") != "along_shore":
        return u * math.tau - math.pi
    gx, gz = ctx["bank_sd_grad"]
    inland = np.arctan2(bilinear(gx, cc.x, cc.z), bilinear(gz, cc.x, cc.z))
    flip = np.where(u < 0.5, 0.5, -0.5) * math.pi
    return inland + flip + np.radians(ALONG_JITTER_DEG) * (4.0 * np.abs(u - 0.5) - 1.0)


def _allowed(cc: cd.Cands, at: dict, rule: dict, weight: np.ndarray, member: bool, ctx: dict) -> np.ndarray:
    t, f = ctx["t"], ctx["f"]
    r = at["r"]
    core, shoulder, _ = ctx["routes"].edges(cc.x, cc.z)
    ok = (core >= r) & (~at["tall"] | (shoulder >= r))
    ok &= bilinear(f["painted_path"], cc.x, cc.z) <= 0.5
    ok &= ~ctx["excl"].blocked(cc.x, cc.z, r)
    sd = bilinear(f["shore_distance"], cc.x, cc.z)
    lo, hi = rule["shore_distance_m"]
    ok &= (sd >= lo) & (sd <= hi)
    wet = rule.get("in_water", {})
    max_depth = np.array([float(wet.get(n, -1.0)) for n in at["names"]])[at["vi"]]
    depth = bilinear(t["level"], cc.x, cc.z) - bilinear(t["height"], cc.x, cc.z)
    ok &= np.where(max_depth >= 0, depth <= max_depth, sd >= MIN_LAND_SD_M)
    if member:
        ok &= bilinear(weight, cc.x, cc.z) >= MEMBER_MIN_WEIGHT
    return ok


def _rows(name: str, rule: dict, ctx: dict) -> list[tuple]:
    dens, weight = _density(rule, ctx["f"])
    c, m, lead = _candidates(name, rule, dens, ctx)
    prio = c.u(cd.D_PRIORITY)
    rows = []
    for cc, ld in ((c, None), (m, lead)):
        at = _attrs(cc, rule, ctx)
        ok = _allowed(cc, at, rule, weight, ld is not None, ctx)
        sp = float(rule["spacing"]) if ld is None else 0.0
        for j in np.nonzero(ok)[0]:
            leader = int(c.iid[ld[j]]) if ld is not None else -1
            p = float(prio[j] if ld is None else prio[ld[j]])
            rows.append((p, int(cc.slot[j]), int(cc.iid[j]), at["names"][at["vi"][j]], float(cc.x[j]),
                         float(cc.z[j]), float(at["s"][j]), float(at["yaw"][j]), float(at["r"][j]), sp, leader))
    rows.sort(key=lambda r: (r[0], r[1], r[2]))
    return rows


class _State:
    """Shared spacing state of one bank placement run."""

    def __init__(self, ctx: dict, existing: list[Inst]) -> None:
        self.ctx = ctx
        self.reg = Registry()
        for i in existing:
            if i.source.startswith("cliffs."):
                self.reg.add(Box.of(ctx["assets"][i.asset], i.x, i.z, i.yaw, i.scale))
        self.taken = {i.iid for i in existing}
        self.rejects: Counter = Counter()

    def blocked(self, a: Asset, own: SpacingHash, fam: SpacingHash, x: float, z: float, yaw: float, s: float,
                r: float, sp: float, k: float) -> str:
        """Rejection reason against the rule (k: share of summed footprint radii kept clear), solids
        (trunks, rocks, logs), same-family plants and cliff modules; '' if free."""
        if not own.clear(x, z, r, sp, k):
            return "spacing"
        if not self.ctx["solid"].clear(x, z, r * (0.9 if a.is_rock else 0.5), 0.0, 1.0):
            return "trunk/rock/log too close"
        if not a.is_rock and not fam.clear(x, z, r, 0.0, k):
            return "same-family plant too close"
        return "cliff module footprint" if self.reg.hits(Box.of(a, x, z, yaw, s)) else ""

    def free_id(self, iid: int) -> int:
        """Bank ids never take an existing instance's id (that one would be renumbered)."""
        salt = 0
        while iid in self.taken:
            salt += 1
            iid = int(to_u32(hash_parts(iid, str_hash("bank collision"), salt)))
        self.taken.add(iid)
        return iid


def _place_rule(name: str, rule: dict, st: _State) -> list[Inst]:
    ctx = st.ctx
    own = SpacingHash(8.0)
    accepted: set[int] = set()
    out: list[Inst] = []
    wet = rule.get("in_water", {})
    k = float(rule.get("footprint_k", FOOTPRINT_K))
    for prio, slot, iid, aname, x, z, s, yaw, r, sp, leader in _rows(name, rule, ctx):
        a = ctx["assets"][aname]
        if leader >= 0 and leader not in accepted:
            continue
        fam_hash = ctx["family_hash"].setdefault(a.family, SpacingHash(8.0))
        reason = st.blocked(a, own, fam_hash, x, z, yaw, s, r, sp, k)
        g = reason or _ground(a, rule, x, z, yaw, s, ctx)
        if isinstance(g, str):
            st.rejects[f"banks.{name}: {g}"] += 1
            continue
        own.add(x, z, r, sp)
        accepted.add(iid)
        if a.is_rock:
            ctx["solid"].add(x, z, r * 0.9, 0.0)
        else:
            fam_hash.add(x, z, r, 0.0)
        out.append(Inst(st.free_id(iid), aname, "bank:" + name, x, g[0], z, math.remainder(yaw, math.tau), s,
                        g[1], g[2], source="banks." + name, radius=r, allow_water=aname in wet))
    return out


def place_banks(ctx: dict, cfg: dict | None, existing: list[Inst]) -> tuple[list[Inst], dict[str, int]]:
    """Bank rules in file order after every other placement (existing = all placed instances);
    returns the new instances and rejection counts by reason."""
    if not cfg or not cfg.get("props"):
        return [], {}
    st = _State(ctx, existing)
    gz, gx = np.gradient(ctx["f"]["shore_distance"].astype(np.float64))
    ctx["bank_sd_grad"] = (gx, gz)
    out: list[Inst] = []
    for name, rule in cfg["props"].items():
        if name.startswith("_"):
            continue
        missing = sorted(n for n in rule["assets"] if n not in ctx["assets"])
        if missing:
            ctx["skipped"].append({"asset": ",".join(missing), "rule": "banks." + name, "reason": "asset not found"})
            rule = dict(rule, assets={n: w for n, w in rule["assets"].items() if n in ctx["assets"]})
            if not rule["assets"]:
                continue
        out += _zone_tag(_place_rule(name, rule, st), ctx)
    return out, dict(sorted(st.rejects.items()))
