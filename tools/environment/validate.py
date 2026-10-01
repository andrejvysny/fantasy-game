"""Placement validation (hard failures fail the run; soft checks are reported)."""
from __future__ import annotations

from typing import TYPE_CHECKING

import math
from dataclasses import dataclass, field

import numpy as np

from banks import COAST_LABEL_OFFSET, LABELS
from common import bilinear
from rockground import FLOAT_TOL_M, HARD_MIN_EXPOSURE, rock_kind
from rockground import metrics as rock_metrics
from spatial import Box

if TYPE_CHECKING:
    from generate import Result

TREE_RANGE = (12000, 25000)
CURRENT_TREES = 18545


@dataclass
class Validation:
    hard: list[str] = field(default_factory=list)
    soft: list[str] = field(default_factory=list)
    info: dict = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.hard


def _recipes(res: Result, v: Validation) -> None:
    rec = res.recipes
    resolved = sum(len(ids) for ids in rec.locked.values())
    v.info["recipe_members"] = {"total": rec.members_total, "resolved": resolved, "skipped": len(rec.skipped)}
    if resolved + len(rec.skipped) != rec.members_total:
        v.hard.append(f"recipe members unaccounted: {rec.members_total - resolved - len(rec.skipped)}")


def _water(res: Result, v: Validation) -> None:
    ins = [i for i in res.instances if not i.allow_water]
    if not ins:
        return
    sd = bilinear(res.fields["shore_distance"], np.array([i.x for i in ins]), np.array([i.z for i in ins]))
    bad = [(i, d) for i, d in zip(ins, sd) if d < 0.0]
    v.info["origins_in_water"] = len(bad)
    for i, d in bad[:10]:
        v.hard.append(f"origin in water: {i.source} {i.asset} id {i.iid} at ({i.x:.1f}, {i.z:.1f}), {d:.2f} m")


def _route_core(res: Result, v: Validation) -> None:
    assets = res.inputs.assets
    worst = math.inf
    per: dict[str, float] = {}
    for i in res.instances:
        a = assets[i.asset]
        if a.is_tree:
            core, _, _ = res.routes.edges(np.array([i.x]), np.array([i.z]))
            gap = float(core[0]) - a.trunk_radius * i.scale
        elif a.is_rock:
            gx, gz = Box.of(a, i.x, i.z, i.yaw, i.scale).grid(0.25)
            core, _, _ = res.routes.edges(gx, gz)
            gap = float(core.min())
        else:
            continue
        worst = min(worst, gap)
        if i.locked:
            per[i.source] = round(min(per.get(i.source, math.inf), gap), 3)
        if gap < 0:
            v.hard.append(f"route core intersected: {i.source} {i.asset} id {i.iid} by {-gap:.2f} m")
    v.info["route_core_min_clearance_m"] = round(worst, 3) if math.isfinite(worst) else None
    v.info["route_core_min_clearance_by_recipe_m"] = dict(sorted(per.items()))


def _spawn(res: Result, v: Validation) -> None:
    assets = res.inputs.assets
    n = 0
    for sx, sz, rad in res.excl.spawns:
        for i in res.instances:
            a = assets[i.asset]
            r = a.trunk_radius * i.scale if a.is_tree else a.radius * i.scale
            if math.hypot(i.x - sx, i.z - sz) < rad + r:
                n += 1
                v.hard.append(f"spawn clear radius violated: {i.source} {i.asset} id {i.iid}")
    v.info["spawn_violations"] = n


def _rocks(res: Result, v: Validation) -> None:
    """Tilt-aware float gap and exposure per rock (same maths as the grounding)."""
    assets, h = res.inputs.assets, res.terrain["height"]
    stats: dict[str, dict[str, list[float]]] = {"fill": {}, "recipe": {}}
    worst = {"fill": (-math.inf, None), "recipe": (-math.inf, None)}
    bad = 0
    cliff_floor = float((res.inputs.habitats.get("cliff_dressing") or {}).get("min_exposure", HARD_MIN_EXPOSURE))
    for i in res.instances:
        a = assets[i.asset]
        if not a.is_rock:
            continue
        gap, exp = rock_metrics(h, a, i.x, i.y, i.z, i.yaw, i.scale, i.tilt_x, i.tilt_z)
        k = "recipe" if i.locked else "fill"
        label = f"{a.family} ({i.source})" if i.source.startswith("cliffs.") else a.family
        stats[k].setdefault(label, []).append(exp)
        if gap > worst[k][0]:
            worst[k] = (gap, i)
        floor = cliff_floor if i.source.startswith("cliffs.") else HARD_MIN_EXPOSURE
        if k == "fill" and (exp < floor or gap > FLOAT_TOL_M[rock_kind(a)] + 1e-3):
            bad += 1
            if bad <= 20:
                v.hard.append(f"fill rock {i.asset} id {i.iid}: exposure {exp:.2f}, float gap {gap:.3f} m")
    v.info["rock_exposure"] = {k: {fam: {"n": len(e), "min": round(float(np.min(e)), 3),
                                         "p10": round(float(np.percentile(e, 10)), 3),
                                         "median": round(float(np.median(e)), 3)} for fam, e in sorted(fs.items())}
                               for k, fs in stats.items()}
    v.info["rock_rejected_candidates"] = res.rock_rejects
    v.info["recipe_rock_members"] = res.recipes.rock_report
    for k, (gap, i) in worst.items():
        if i is None:
            continue
        v.info[f"floating_worst_{k}"] = {"gap_m": round(gap, 3), "id": i.iid, "asset": i.asset, "source": i.source}
        if k == "recipe" and gap > FLOAT_TOL_M[rock_kind(assets[i.asset])] + 1e-3:
            v.soft.append(f"floating recipe rock: {i.source} {i.asset} id {i.iid} base {gap:.2f} m above terrain")
    if bad > 20:
        v.hard.append(f"... {bad - 20} more fill rocks below exposure {HARD_MIN_EXPOSURE} or floating")


def _counts(res: Result, v: Validation) -> None:
    n = sum(1 for i in res.instances if res.inputs.assets[i.asset].is_tree and not i.locked)
    v.info["trees_fill"] = n
    v.info["trees_current_runtime"] = CURRENT_TREES
    if not TREE_RANGE[0] <= n <= TREE_RANGE[1]:
        v.soft.append(f"tree count {n} outside sane range {TREE_RANGE} (current runtime {CURRENT_TREES})")


def _bank_character(rule: dict) -> str:
    keys = sorted(rule.get("fields", {}), key=lambda k: -float(rule["fields"][k]))
    return "coast" if keys and keys[0].startswith("coast_") else (keys[0].removeprefix("bank_") if keys else "?")


def _banks(res: Result, v: Validation) -> None:
    """Counts per character and zone, shore length per character, in-water depth limits."""
    rules = ((res.inputs.habitats.get("banks") or {}).get("props")) or {}
    if not rules:
        return
    t = res.terrain
    counts: dict[str, dict[str, int]] = {}
    depth_max: dict[str, float] = {}
    for i in res.instances:
        if not i.source.startswith("banks."):
            continue
        rule = rules[i.source.removeprefix("banks.")]
        ch = counts.setdefault(_bank_character(rule), {})
        ch[i.zone] = ch.get(i.zone, 0) + 1
        if not i.allow_water:
            continue
        x, z = np.array([i.x]), np.array([i.z])
        depth = float(bilinear(t["level"], x, z)[0] - bilinear(t["height"], x, z)[0])
        key = f"{i.source}/{i.asset}"
        depth_max[key] = round(max(depth_max.get(key, -math.inf), depth), 3)
        if depth > float(rule["in_water"][i.asset]) + 0.02:
            v.hard.append(f"bank {i.asset} id {i.iid} in water {depth:.2f} m deep (max {rule['in_water'][i.asset]})")
    v.info["banks"] = {"counts": {k: dict(sorted(z.items())) for k, z in sorted(counts.items())},
                       "max_depth_m": dict(sorted(depth_max.items())), "shore_m": _shore_lengths(res)}


def _shore_lengths(res: Result) -> dict[str, dict[str, int]]:
    """Shore pixels (~ metres of shoreline) per character; plain = open access."""
    lab = res.fields.get("bank_label")
    if lab is None:
        return {}
    out = {}
    for name, off in (("inland", 0), ("coast", COAST_LABEL_OFFSET)):
        out[name] = {k: int((lab == n + off).sum()) for k, n in LABELS.items() if k != "none"}
    return out


def validate(res: Result, determinism: tuple[str, str]) -> Validation:
    v = Validation()
    _recipes(res, v)
    _water(res, v)
    _route_core(res, v)
    _spawn(res, v)
    _rocks(res, v)
    _counts(res, v)
    _banks(res, v)
    v.info["determinism"] = {"run_a": determinism[0], "run_b": determinism[1], "equal": determinism[0] == determinism[1]}
    if determinism[0] != determinism[1]:
        v.hard.append("determinism self-check failed: two in-process runs differ")
    return v
