"""Cliff dressing (valley_habitats.json 'cliff_dressing', plan 7G): cliff_face / cliff_corner
modules on the terrain cliff mask and steep slopes, then rock_shelf modules on treads near them.

Placed after every other family with their own hash streams, so trees and props never move.
Spacing is footprint based: oriented-box overlap against all placed rocks, trunks inside a
module footprint reject it. Fronts (+z) face downhill along the smoothed gradient.
"""
from __future__ import annotations

import math
from collections import Counter

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage as ndi

import candidates as cd
from assets import Asset, family_assets
from common import HALF, RES, bilinear
from rockground import ground_rock
from spatial import Box, Inst, SpacingHash, zone_of

CLIFF_MASK_MIN = 0.3
GRAD_SIGMA_M = 3.0
CORNER_WINDOW_M = 10.0
CORNER_BOOST = 4.0  # corner weight multiplier where the face contour bends
OBB_SHRINK = 0.85  # neighbouring modules may interlock slightly so faces read continuous


def _corners(b: Box, shrink: float) -> np.ndarray:
    mx, mz = (b.x0 + b.x1) * 0.5, (b.z0 + b.z1) * 0.5
    hx, hz = (b.x1 - b.x0) * 0.5 * shrink, (b.z1 - b.z0) * 0.5 * shrink
    lx = np.array([mx - hx, mx + hx, mx + hx, mx - hx])
    lz = np.array([mz - hz, mz - hz, mz + hz, mz + hz])
    c, s = math.cos(b.yaw), math.sin(b.yaw)
    return np.stack([b.x + lx * c + lz * s, b.z - lx * s + lz * c], axis=1)


def _overlap(a: np.ndarray, b: np.ndarray) -> bool:
    """Separating-axis test for two convex quads (4 x 2 corner arrays)."""
    for quad in (a, b):
        for k in range(2):
            e = quad[k + 1] - quad[k]
            axis = np.array([-e[1], e[0]])
            pa, pb = a @ axis, b @ axis
            if pa.max() < pb.min() or pb.max() < pa.min():
                return False
    return True


class Registry:
    """Oriented footprints of every placed rock, for overlap tests."""

    def __init__(self) -> None:
        self.quads: list[np.ndarray] = []
        self.centres: list[tuple[float, float, float]] = []

    def add(self, b: Box) -> None:
        q = _corners(b, OBB_SHRINK)
        self.quads.append(q)
        cx, cz = q.mean(axis=0)
        self.centres.append((cx, cz, float(np.max(np.hypot(q[:, 0] - cx, q[:, 1] - cz)))))

    def hits(self, b: Box) -> bool:
        if not self.quads:
            return False
        q = _corners(b, OBB_SHRINK)
        cx, cz = q.mean(axis=0)
        r = float(np.max(np.hypot(q[:, 0] - cx, q[:, 1] - cz)))
        c = np.asarray(self.centres)
        near = np.nonzero(np.hypot(c[:, 0] - cx, c[:, 1] - cz) < c[:, 2] + r)[0]
        return any(_overlap(q, self.quads[k]) for k in near)


def _bend_field(gx: np.ndarray, gz: np.ndarray) -> np.ndarray:
    """Spread (deg) of downhill directions within CORNER_WINDOW_M: high where the face bends."""
    mag = np.hypot(gx, gz)
    w = (mag > 0.2).astype(np.float64)
    ux, uz = -gx / np.maximum(mag, 1e-9) * w, -gz / np.maximum(mag, 1e-9) * w
    size = int(CORNER_WINDOW_M) + 1
    mx, mz, mw = (ndi.uniform_filter(a, size) for a in (ux, uz, w))
    r = np.hypot(mx, mz) / np.maximum(mw, 1e-9)
    return np.where(mw > 0.05, 2.0 * np.degrees(np.arccos(np.clip(r, 0.0, 1.0))), 0.0)


def _smoothed_gradient(h: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    gz, gx = np.gradient(ndi.gaussian_filter(h.astype(np.float64), GRAD_SIGMA_M))
    return gx, gz


def _trunks(ctx: dict) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    trees = ctx["trees"] + [i for i in ctx["recipe_insts"] if ctx["assets"][i.asset].is_tree]
    x = np.array([t.x for t in trees])
    z = np.array([t.z for t in trees])
    r = np.array([ctx["assets"][t.asset].trunk_radius * t.scale for t in trees])
    return x, z, r


def _tree_inside(b: Box, trunks: tuple[np.ndarray, np.ndarray, np.ndarray]) -> bool:
    x, z, r = trunks
    near = np.hypot(x - b.x, z - b.z) < max(b.x1 - b.x0, b.z1 - b.z0) + 1.0
    return bool(np.any(b.distance(x[near], z[near]) < r[near])) if near.any() else False


def _excluded(c: cd.Cands, radius: np.ndarray, ctx: dict) -> np.ndarray:
    core, _, _ = ctx["routes"].edges(c.x, c.z)
    bad = core < radius
    bad |= bilinear(ctx["f"]["shore_distance"], c.x, c.z) < 0.3
    bad |= ctx["excl"].blocked(c.x, c.z, radius, corridors=False)
    return bad


class _Placer:
    """Shared accept loop for cliff modules and tread shelves."""

    def __init__(self, ctx: dict, cfg: dict, reg: Registry, trunks: tuple, rejects: Counter) -> None:
        self.ctx, self.cfg, self.reg, self.trunks, self.rejects = ctx, cfg, reg, trunks, rejects

    def run(self, c: cd.Cands, pick: list[tuple[Asset, float]], yaw: np.ndarray, spacing: float,
            tag: str) -> list[Inst]:
        radius = np.array([_corner_r(a) * s for a, s in pick])
        bad = _excluded(c, radius, self.ctx)
        self.rejects[f"{tag}: excluded (water/route core/spawn/reserve)"] += int(bad.sum())
        own = SpacingHash(16.0)
        out: list[Inst] = []
        prio = c.u(cd.D_PRIORITY)
        for j in sorted(np.nonzero(~bad)[0], key=lambda k: (prio[k], int(c.iid[k]))):
            inst = self._try(c, int(j), pick[j], float(yaw[j]), spacing, own, tag)
            if inst is not None:
                out.append(inst)
        return out

    def _try(self, c: cd.Cands, j: int, pick: tuple[Asset, float], yaw: float, spacing: float,
             own: SpacingHash, tag: str) -> Inst | None:
        a, s = pick
        x, z = float(c.x[j]), float(c.z[j])
        box = Box.of(a, x, z, yaw, s)
        reason = ""
        if not own.clear(x, z, 0.0, spacing, 1.0):
            reason = "spacing"
        elif self.reg.hits(box):
            reason = "overlaps placed rock"
        elif _tree_inside(box, self.trunks):
            reason = "tree trunk in footprint"
        if reason:
            self.rejects[f"{tag}: {reason}"] += 1
            return None
        cfg, h = self.cfg, self.ctx["t"]["height"]
        fit = ground_rock(h, a, x, z, yaw, s, 0.0, 0.0, fill=True, max_tilt=cfg.get("max_tilt"),
                          rise_limit=cfg.get("rise_limit"), min_exposure=float(cfg.get("min_exposure", 0.35)))
        if fit.reject:
            self.rejects[f"{tag}: {fit.reject}"] += 1
            return None
        own.add(x, z, 0.0, spacing)
        self.reg.add(box)
        return Inst(int(c.iid[j]), a.asset_id, a.family, x, fit.y, z, math.remainder(yaw, math.tau), s,
                    fit.tilt_x, fit.tilt_z, source=f"cliffs.{tag}", radius=_corner_r(a) * s)


def _corner_r(a: Asset) -> float:
    return math.hypot(max(abs(a.bbox_min[0]), abs(a.bbox_max[0])), max(abs(a.bbox_min[2]), abs(a.bbox_max[2])))


def _downhill_yaw(gx: np.ndarray, gz: np.ndarray, x: np.ndarray, z: np.ndarray) -> np.ndarray:
    return np.arctan2(-bilinear(gx, x, z), -bilinear(gz, x, z))


def _families(cfg: dict, ctx: dict) -> dict[str, tuple[float, list[str]]]:
    out = {}
    for fam, w in cfg.get("assets", {}).items():
        names = family_assets(ctx["assets"], fam)
        if names:
            out[fam] = (float(w), names)
        else:
            ctx["skipped"].append({"asset": fam + "_*", "rule": "cliff_dressing", "reason": "no asset of family"})
    return out


def _pick_modules(c: cd.Cands, fams: dict, bend: np.ndarray, cfg: dict, ctx: dict) -> list[tuple[Asset, float]]:
    names = sorted(fams)
    base = np.array([fams[n][0] for n in names])
    corner = np.array(["corner" in n for n in names])
    bent = bilinear(bend, c.x, c.z) > float(cfg.get("corner_bend_deg", 25.0))
    lo, hi = cfg.get("scale", [1.0, 1.0])
    u_f, u_a, u_s = c.u(cd.D_VARIANT), c.u(cd.D_EXTRA), c.u(cd.D_SCALE)
    out = []
    for j in range(len(c)):
        w = np.where(corner, base * (CORNER_BOOST if bent[j] else 1.0), base)
        fam = names[int(cd.pick_weighted(np.array([u_f[j]]), names, list(w))[0])]
        assets = fams[fam][1]
        a = ctx["assets"][assets[min(int(u_a[j] * len(assets)), len(assets) - 1)]]
        out.append((a, float(lo + u_s[j] * (hi - lo))))
    return out


def _face_raster(insts: list[Inst], assets: dict) -> np.ndarray:
    img = Image.new("L", (RES, RES), 0)
    d = ImageDraw.Draw(img)
    for i in insts:
        q = _corners(Box.of(assets[i.asset], i.x, i.z, i.yaw, i.scale), 1.0) + HALF
        d.polygon([tuple(p) for p in q], fill=255)
    return np.asarray(img) > 0


def _treads(ctx: dict, cfg: dict, faces: list[Inst], placer: _Placer, gx: np.ndarray, gz: np.ndarray) -> list[Inst]:
    tc = cfg.get("shelf_on_treads")
    if not tc or not faces:
        return []
    names = family_assets(ctx["assets"], tc.get("asset_family", "rock_shelf"))
    if not names:
        ctx["skipped"].append({"asset": tc.get("asset_family", "rock_shelf") + "_*",
                               "rule": "cliff_dressing.shelf_on_treads", "reason": "no asset of family"})
        return []
    lo, hi = tc["tread_slope_deg"]
    slope = ctx["f"]["slope_deg"]
    near = ndi.distance_transform_edt(~_face_raster(faces, ctx["assets"])) <= float(tc["within_m_of_face"])
    mask = ((slope >= lo) & (slope <= hi) & near).astype(np.float64)
    c = cd.cells("cliff_treads", float(tc["spacing"]), mask, ctx["seed"], ctx["zones"])
    c = c.take(bilinear(mask, c.x, c.z) >= 0.5)
    pick = []
    for j in range(len(c)):
        a = ctx["assets"][names[min(int(c.u(cd.D_VARIANT)[j] * len(names)), len(names) - 1)]]
        pick.append((a, float(a.scale_range[0] + c.u(cd.D_SCALE)[j] * (a.scale_range[1] - a.scale_range[0]))))
    return placer.run(c, pick, _downhill_yaw(gx, gz, c.x, c.z), float(tc["spacing"]), "tread")


def place_cliffs(ctx: dict, cfg: dict | None) -> tuple[list[Inst], dict[str, int]]:
    rejects: Counter = Counter()
    if not cfg:
        return [], {}
    fams = _families(cfg, ctx)
    gx, gz = _smoothed_gradient(ctx["t"]["height"])
    reg = Registry()
    for i in ctx["solids_rock"]:
        reg.add(Box.of(ctx["assets"][i.asset], i.x, i.z, i.yaw, i.scale))
    placer = _Placer(ctx, cfg, reg, _trunks(ctx), rejects)
    faces: list[Inst] = []
    if fams:
        mask = ((ctx["t"]["cliff"] > CLIFF_MASK_MIN) | (ctx["f"]["slope_deg"] > float(cfg["min_slope_deg"])))
        mask = mask.astype(np.float64)
        c = cd.cells("cliff_dressing", float(cfg["spacing"]), mask, ctx["seed"], ctx["zones"])
        c = c.take(bilinear(mask, c.x, c.z) >= 0.5)
        pick = _pick_modules(c, fams, _bend_field(gx, gz), cfg, ctx)
        faces = placer.run(c, pick, _downhill_yaw(gx, gz, c.x, c.z), float(cfg["spacing"]), "face")
    out = faces + _treads(ctx, cfg, faces, placer, gx, gz)
    zones = zone_of(ctx["zones"], np.array([i.x for i in out]), np.array([i.z for i in out]))
    for inst, zn in zip(out, zones):
        inst.zone = str(zn)
    return out, dict(sorted(rejects.items()))
