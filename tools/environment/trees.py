"""Tree fill per habitat (valley_habitats.json 'trees') and the canopy raster (plan 8.2 step 3-4)."""
from __future__ import annotations

from typing import TYPE_CHECKING

import math

import numpy as np

import candidates as cd
from assets import Asset
from common import RES, bilinear, disc_stamp, nearest, noise, smoothstep
from spatial import Exclusions, Inst, SpacingHash, zone_of

if TYPE_CHECKING:
    from routes import Routes

MAX_SLOPE = 0.85  # rise / run
MIN_HEIGHT = 0.8
WATER_MARGIN_M = 1.0
GROUP_RADIUS_M = (2.5, 6.0)
CANOPY_REF_HEIGHT_M = 12.0


def _density(f: dict, hab: str, rule: dict) -> np.ndarray:
    d = f[hab].astype(np.float64) * float(rule["density"])
    if "gap_noise_m" in rule:
        thr = float(rule["gap_threshold"])
        d *= 1.0 - smoothstep(thr - 0.03, thr + 0.03, noise("tree_gap:" + hab, rule["gap_noise_m"]))
    return d


def _variants(rule: dict, assets: dict[str, Asset], report: list[dict], hab: str) -> tuple[list[str], list[float]]:
    names, weights = [], []
    for name, w in rule.get("weights", {}).items():
        if name in assets and assets[name].is_tree:
            names.append(name)
            weights.append(float(w))
        else:
            report.append({"asset": name, "rule": f"trees.{hab}", "reason": "tree asset not found"})
    return names, weights


def _attrs(c: cd.Cands, names: list[str], weights: list[float], assets: dict[str, Asset],
           routes: Routes, spacing: float) -> dict:
    vi = cd.pick_weighted(c.u(cd.D_VARIANT), names, weights)
    lo = np.array([assets[n].scale_range[0] for n in names])[vi]
    hi = np.array([assets[n].scale_range[1] for n in names])[vi]
    s = lo + c.u(cd.D_SCALE) * (hi - lo)
    _, sh_edge, clear = routes.edges(c.x, c.z)
    clear = np.where(clear > 0, clear, 2.5)
    r_sp = np.array([assets[names[v]].spacing_radius(sc) for v, sc in zip(vi, s)])
    r_env = np.array([assets[names[v]].envelope_radius(sc, cl) for v, sc, cl in zip(vi, s, clear)])
    r_trunk = np.array([assets[names[v]].trunk_radius * sc for v, sc in zip(vi, s)])
    sp = np.where(c.slot == 0, spacing, 0.0)
    return {"vi": vi, "s": s, "r_sp": r_sp, "r_env": r_env, "r_trunk": r_trunk, "sh_edge": sh_edge, "sp": sp}


def _allowed(c: cd.Cands, a: dict, t: dict, f: dict, excl: Exclusions, rule: dict) -> np.ndarray:
    h = bilinear(t["height"], c.x, c.z)
    sd = bilinear(f["shore_distance"], c.x, c.z)
    wet = nearest(t["water"], c.x, c.z) & (h < nearest(t["level"], c.x, c.z) + 0.3)
    slope = np.tan(np.radians(bilinear(f["slope_deg"], c.x, c.z)))
    ok = ~wet & (sd >= WATER_MARGIN_M) & (slope <= MAX_SLOPE) & (h >= MIN_HEIGHT)
    ok &= a["sh_edge"] >= a["r_env"]
    ok &= bilinear(f["painted_path"], c.x, c.z) <= 0.5
    ok &= ~excl.blocked(c.x, c.z, a["r_env"], a["r_trunk"])
    if rule.get("needs_soil"):
        ok &= bilinear(t["splat_rock"], c.x, c.z) < 0.4
    if "setback_m" in rule:
        ok &= bilinear(f["inland_distance"], c.x, c.z) >= float(rule["setback_m"])
    return ok


def _rule_candidates(hab: str, rule: dict, ctx: dict) -> list[tuple]:
    """Accepted-by-roll, exclusion-filtered candidates of one habitat rule as sortable rows."""
    names, weights = _variants(rule, ctx["assets"], ctx["skipped"], hab)
    if not names:
        return []
    dens = _density(ctx["f"], hab, rule)
    c = cd.cells("tree:" + hab, float(rule["spacing"]), dens, ctx["seed"], ctx["zones"])
    p = bilinear(dens, c.x, c.z) * c.cell * c.cell / 100.0
    c = c.take(c.u(cd.D_ACCEPT) < p)
    parts = [(c, np.full(len(c), -1))]
    if "group_prob" in rule:
        m, lead = cd.group_members(c, float(rule["group_prob"]), tuple(rule["group_size"]),
                                   GROUP_RADIUS_M, ctx["seed"], ctx["zones"])
        parts.append((m, lead))
    rows = []
    lead_prio = c.u(cd.D_PRIORITY)
    for pi, (cc, lead) in enumerate(parts):
        a = _attrs(cc, names, weights, ctx["assets"], ctx["routes"], float(rule["spacing"]))
        ok = _allowed(cc, a, ctx["t"], ctx["f"], ctx["excl"], rule)
        prio = lead_prio if pi == 0 else lead_prio[np.maximum(lead, 0)]
        yaw = cc.u(cd.D_YAW) * math.tau - math.pi
        for j in np.nonzero(ok)[0]:
            leader = int(c.iid[lead[j]]) if lead[j] >= 0 else -1
            rows.append((float(prio[j]), int(cc.slot[j]), int(cc.iid[j]), hab, names[a["vi"][j]],
                         float(cc.x[j]), float(cc.z[j]), float(a["s"][j]), float(yaw[j]),
                         float(a["r_sp"][j]), float(a["sp"][j]), leader))
    return rows


def place_trees(ctx: dict, locked: list[Inst]) -> list[Inst]:
    """Variable-radius spacing in hashed-priority order across all habitat rules."""
    rows = []
    for hab, rule in ctx["rules"].items():
        rows += _rule_candidates(hab, rule, ctx)
    rows.sort(key=lambda r: (r[0], r[1], r[2]))
    grid = SpacingHash(8.0)
    for inst in locked:
        if ctx["assets"][inst.asset].is_tree:
            grid.add(inst.x, inst.z, inst.radius, 0.0)
    accepted: set[tuple[str, int]] = set()
    out: list[Inst] = []
    t, assets = ctx["t"], ctx["assets"]
    for prio, slot, iid, hab, name, x, z, s, yaw, r, sp, leader in rows:
        if leader >= 0 and (hab, leader) not in accepted:
            continue
        if not grid.clear(x, z, r, sp, 0.8):
            continue
        grid.add(x, z, r, sp)
        accepted.add((hab, iid))
        y = float(bilinear(t["height"], np.array([x]), np.array([z]))[0]) - assets[name].sink
        out.append(Inst(iid, name, "tree:" + hab, x, y, z, yaw, s, source="trees." + hab, radius=r))
    zones = zone_of(ctx["zones"], np.array([i.x for i in out]), np.array([i.z for i in out]))
    for inst, zn in zip(out, zones):
        inst.zone = str(zn)
    return out


def canopy_raster(trees: list[Inst], assets: dict[str, Asset]) -> np.ndarray:
    """Sum of soft crown discs weighted by tree height fraction, clamped 0..1.5."""
    can = np.zeros((RES, RES), dtype=np.float32)
    for tr in trees:
        a = assets[tr.asset]
        w = min(1.0, a.height * tr.scale / CANOPY_REF_HEIGHT_M)
        disc_stamp(can, tr.x, tr.z, a.radius * tr.scale, w, profile="flat")
    return np.clip(can, 0.0, 1.5)
