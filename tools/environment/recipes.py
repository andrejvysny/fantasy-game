"""Locked scene-assembly recipes (world/recipes/valley_recipes.json, plan section 7).

Frame: local +z points from 'anchor' toward 'face' (Godot Basis(UP, yaw) convention, so local
+x is the right-hand side seen by a viewer facing the asset front). 'space': 'world' members
use world x, z directly; their yaw is still added to the frame yaw. Rocks get deterministic
fracture jitter seeded by recipe id + member index only (locked anchors never move when
fill rules change).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from assets import Asset
from common import bilinear, hash_parts, rotate, str_hash, to_u32, unit
from dataclasses import replace

from rockground import RockFit, ground_rock
from rockground import metrics as rock_metrics
from spatial import Box, Inst, ground_height, terrain_tilt, zone_of


@dataclass
class RecipeResult:
    instances: list[Inst] = field(default_factory=list)
    reserves: list[Box] = field(default_factory=list)
    locked: dict[str, list[int]] = field(default_factory=dict)
    skipped: list[dict] = field(default_factory=list)
    patches: list[dict] = field(default_factory=list)
    members_total: int = 0
    rock_report: list[dict] = field(default_factory=list)


def _frame_yaw(rec: dict) -> float:
    ax, az = rec["anchor"]
    fx, fz = rec.get("face", [ax, az + 1.0])
    return math.atan2(fx - ax, fz - az)


def _member(rid: str, rec: dict, i: int, m: dict, a: Asset, t: dict, f: dict,
            zones: list[dict]) -> tuple[Inst, Box, RockFit | None]:
    yaw0 = _frame_yaw(rec)
    if m.get("space") == "world":
        x, z = float(m["at"][0]), float(m["at"][1])
    else:
        ox, oz = rotate(np.float64(m["at"][0]), np.float64(m["at"][1]), yaw0)
        x, z = rec["anchor"][0] + float(ox), rec["anchor"][1] + float(oz)
    key = hash_parts(str_hash("recipe:" + rid), i)
    yaw = yaw0 + math.radians(float(m.get("yaw", 0.0)))
    jit = float(rec.get("fracture_yaw_jitter", 0.0))
    if a.is_rock and jit > 0:
        yaw += math.radians(jit) * (2.0 * float(unit(key, 0)) - 1.0)
    yaw = math.remainder(yaw, math.tau)
    s = float(m.get("scale", 1.0))
    box = Box.of(a, x, z, yaw, s)
    sink = float(m.get("sink", 0.0))
    rule = m.get("ground", "center")
    # 'contact': as high as the no-float bound allows, then sink (recipe rocks on steep shoulders
    # otherwise end up buried by 'min', which ignores how far the base already reaches down).
    y = math.inf if rule == "contact" else ground_height(t["height"], box, rule) - sink
    tx = tz = 0.0
    fit = None
    if a.is_rock:
        fit = ground_rock(t["height"], a, x, z, yaw, s, y, sink, fill=False)
        y, tx, tz = fit.y, fit.tilt_x, fit.tilt_z
        if rule == "contact":
            y -= sink
            gap, exposure = rock_metrics(t["height"], a, x, y, z, yaw, s, tx, tz)
            fit = replace(fit, y=y, float_gap=gap, exposure=exposure)
    elif not a.is_tree:
        gx = bilinear(f["grad_x"], np.array([x]), np.array([z]))
        gz = bilinear(f["grad_z"], np.array([x]), np.array([z]))
        tx_a, tz_a = terrain_tilt(gx, gz, a.max_tilt_deg)
        tx, tz = float(tx_a[0]), float(tz_a[0])
    zone = str(zone_of(zones, np.array([x]), np.array([z]))[0])
    radius = a.spacing_radius(s) if a.is_tree else a.radius * s
    inst = Inst(int(to_u32(hash_parts(str_hash("recipe:" + rid), i, 0, 0))), a.asset_id, a.family,
                x, y, z, yaw, s, tx, tz, zone, True, rid, radius)
    return inst, box, fit


def resolve_recipes(data: dict, assets: dict[str, Asset], t: dict, f: dict,
                    zones: list[dict]) -> RecipeResult:
    res = RecipeResult()
    for rid, rec in data.get("recipes", {}).items():
        res.locked[rid] = []
        reserve = float(rec.get("reserve", 0.0))
        for i, m in enumerate(rec.get("members", [])):
            res.members_total += 1
            a = assets.get(m["asset"])
            if a is None:
                res.skipped.append({"recipe": rid, "member": i, "asset": m["asset"],
                                    "reason": "asset metadata/GLB not found"})
                continue
            inst, box, fit = _member(rid, rec, i, m, a, t, f, zones)
            if fit is not None:
                res.rock_report.append({"recipe": rid, "member": i, "asset": a.asset_id, "id": inst.iid,
                                        "exposure": round(fit.exposure, 3), "float_gap_m": round(fit.float_gap, 3)})
            res.instances.append(inst)
            res.locked[rid].append(inst.iid)
            box.grow, box.tag = reserve, f"{rid}#{i}"
            res.reserves.append(box)
        for p in rec.get("patches", []):
            res.patches.append(dict(p, recipe=rid))
    return res
