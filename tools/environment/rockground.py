"""Rock grounding: plane-fit tilt, no-float base, exposure and shelf/cliff front-edge rules.

Runtime basis Rx(tilt_x) * Rz(tilt_z) * Ry(yaw) * scale; the buried base is the footprint at
local y = -embed_depth, carried through that basis. Exposure = share of the bbox height
above the terrain at the origin (0..1).
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from assets import Asset
from common import bilinear, rotate
from spatial import Box, terrain_tilt

MIN_EXPOSURE = 0.5  # fill boulders / rubble / shore rocks
HARD_MIN_EXPOSURE = 0.35  # validation floor for every fill rock
FRONT_LIFT_M = 0.1  # shelf / cliff front-bottom may sit this far above the lowest front terrain
FLOAT_TOL_M = {"boulder": 0.02, "shelf": FRONT_LIFT_M, "cliff": FRONT_LIFT_M}
RISE_LIMIT = {"shelf": 0.85, "cliff": 0.9}
GRID_STEP_M = 0.5
MAX_RULE_TILT_DEG = 20.0


@dataclass
class RockFit:
    y: float
    tilt_x: float
    tilt_z: float
    exposure: float
    float_gap: float  # max (base - terrain) over the footprint, m (> 0 floats)
    reject: str = ""  # reason when the spot cannot hold the rock


def rock_kind(a: Asset) -> str:
    if a.family == "rock_shelf":
        return "shelf"
    if a.family in ("cliff_face", "cliff_corner"):
        return "cliff"
    return "boulder"


CLIFF_MAX_BACK_EXPOSURE = 0.3
CLIFF_MAX_END_EXPOSURE = 0.6


def _rot(tx: float, tz: float) -> np.ndarray:
    cx, sx, cz, sz = math.cos(tx), math.sin(tx), math.cos(tz), math.sin(tz)
    rx = np.array([[1, 0, 0], [0, cx, -sx], [0, sx, cx]])
    rz = np.array([[cz, -sz, 0], [sz, cz, 0], [0, 0, 1]])
    return rx @ rz


def _base(h: np.ndarray, a: Asset, x: float, z: float, yaw: float, s: float, r: np.ndarray,
          lx: np.ndarray, lz: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(terrain under, base dy) for local footprint points (scaled local x/z) at y = 0."""
    wx, wz = rotate(lx, lz, yaw)
    v = np.stack([wx, np.full(wx.shape, -a.embed_depth * s), wz])
    w = r @ v
    return bilinear(h, x + w[0], z + w[2]), w[1]


def _fit_tilt(h: np.ndarray, a: Asset, box: Box, max_tilt: float) -> tuple[float, float]:
    gx_pts, gz_pts = box.grid(GRID_STEP_M)
    hs = bilinear(h, gx_pts, gz_pts)
    m = np.stack([np.ones_like(gx_pts), gx_pts - box.x, gz_pts - box.z], axis=1)
    coef = np.linalg.lstsq(m, hs, rcond=None)[0]
    tx, tz = terrain_tilt(np.array([coef[1]]), np.array([coef[2]]), max_tilt)
    return float(tx[0]), float(tz[0])


def _local_grid(box: Box) -> tuple[np.ndarray, np.ndarray]:
    nx = max(int(math.ceil((box.x1 - box.x0) / GRID_STEP_M)) + 1, 3)
    nz = max(int(math.ceil((box.z1 - box.z0) / GRID_STEP_M)) + 1, 3)
    lx, lz = np.meshgrid(np.linspace(box.x0, box.x1, nx), np.linspace(box.z0, box.z1, nz))
    return lx.ravel(), lz.ravel()


def _edge(box: Box, z: float) -> tuple[np.ndarray, np.ndarray]:
    nx = max(int(math.ceil((box.x1 - box.x0) / GRID_STEP_M)) + 1, 3)
    lx = np.linspace(box.x0, box.x1, nx)
    return lx, np.full(nx, z)


def metrics(h: np.ndarray, a: Asset, x: float, y: float, z: float, yaw: float, s: float,
            tx: float, tz: float) -> tuple[float, float]:
    """(float gap, exposure) of a placed rock; used by grounding and by validation."""
    box = Box.of(a, x, z, yaw, s)
    r = _rot(tx, tz)
    terr, dy = _base(h, a, x, z, yaw, s, r, *_local_grid(box))
    gap = float(np.max(y + dy - terr))
    top = y + float((r @ np.array([0.0, a.bbox_max[1] * s, 0.0]))[1])
    tc = float(bilinear(h, np.array([x]), np.array([z]))[0])
    height = (a.bbox_max[1] - a.bbox_min[1]) * s
    return gap, float(np.clip((top - tc) / max(height, 1e-6), 0.0, 1.0))


def _exposure_y(h: np.ndarray, a: Asset, x: float, z: float, s: float, r: np.ndarray, e: float) -> float:
    """y at which the exposure equals e."""
    top_dy = float((r @ np.array([0.0, a.bbox_max[1] * s, 0.0]))[1])
    tc = float(bilinear(h, np.array([x]), np.array([z]))[0])
    return tc + e * (a.bbox_max[1] - a.bbox_min[1]) * s - top_dy


def _side_exposure(h: np.ndarray, a: Asset, x: float, z: float, yaw: float, s: float, r: np.ndarray,
                   lx: np.ndarray, lz: np.ndarray, y: float) -> float:
    """Share of the module height standing above the terrain along a side edge (0 = buried)."""
    terr, _ = _base(h, a, x, z, yaw, s, r, lx, lz)
    top = y + float((r @ np.array([0.0, a.bbox_max[1] * s, 0.0]))[1])
    height = (a.bbox_max[1] - a.bbox_min[1]) * s
    return float(np.clip((top - np.mean(terr)) / max(height, 1e-6), 0.0, 1.0))


def _hidden_sides(h: np.ndarray, a: Asset, x: float, z: float, yaw: float, s: float, r: np.ndarray,
                  box: Box, y: float) -> str:
    """Cliff modules are faces, not free-standing blocks: their flat connection back and their
    cut ends must sit inside the slope (gorges otherwise show slab backs, 18_east_falls_gorge)."""
    back = _side_exposure(h, a, x, z, yaw, s, r, *_edge(box, box.z0), y)
    if back > CLIFF_MAX_BACK_EXPOSURE:
        return "cliff: back exposed"
    nz = max(int(math.ceil((box.z1 - box.z0) / GRID_STEP_M)) + 1, 3)
    lz = np.linspace(box.z0, (box.z0 + box.z1) * 0.5, nz)
    for ex in (box.x0, box.x1):
        if _side_exposure(h, a, x, z, yaw, s, r, np.full(nz, ex), lz, y) > CLIFF_MAX_END_EXPOSURE:
            return "cliff: end exposed"
    return ""


def ground_rock(h: np.ndarray, a: Asset, x: float, z: float, yaw: float, s: float, y_pref: float,
                sink: float, fill: bool, max_tilt: float | None = None, rise_limit: float | None = None,
                min_exposure: float = HARD_MIN_EXPOSURE) -> RockFit:
    """Tilted, non-floating placement. fill=False (recipes) never rejects: y = min(pref, bound).

    max_tilt / rise_limit override the asset tilt and the shelf/cliff rise factor (fill rules);
    min_exposure is the fill rejection floor for shelves / cliffs.
    """
    box = Box.of(a, x, z, yaw, s)
    tilt_cap = a.max_tilt_deg if max_tilt is None else min(float(max_tilt), MAX_RULE_TILT_DEG)
    tx, tz = _fit_tilt(h, a, box, tilt_cap)
    r = _rot(tx, tz)
    kind = rock_kind(a)
    terr, dy = _base(h, a, x, z, yaw, s, r, *_local_grid(box))
    y_nofloat = float(np.min(terr - dy)) + (FLOAT_TOL_M[kind] if kind != "boulder" else 0.0)
    reject = ""
    if kind == "boulder":
        y_need = _exposure_y(h, a, x, z, s, r, MIN_EXPOSURE)
        y = min(max(y_pref, y_need), y_nofloat) if fill else min(y_pref, y_nofloat)
        if fill and y_need > y_nofloat:
            reject = "boulder: no-float and exposure >= 0.5 incompatible"
    else:
        tf, dyf = _base(h, a, x, z, yaw, s, r, *_edge(box, box.z1))
        tb, dyb = _base(h, a, x, z, yaw, s, r, *_edge(box, box.z0))
        y_front = float(np.min(tf)) + FRONT_LIFT_M - float(np.max(dyf))
        y = min(y_front - sink, y_nofloat) if fill else min(y_pref, y_nofloat)
        rise = float(np.mean(tb - dyb) - np.mean(tf - dyf))
        shelf_rise = (a.bbox_max[1] - a.bbox_min[1] - a.embed_depth) * s
        limit = RISE_LIMIT[kind] if rise_limit is None else float(rise_limit)
        if fill and rise > limit * shelf_rise:
            reject = f"{kind}: terrain rise > {limit:.2f} x shelf rise"
        elif fill and kind == "cliff":
            reject = _hidden_sides(h, a, x, z, yaw, s, r, box, y)
    gap, exposure = metrics(h, a, x, y, z, yaw, s, tx, tz)
    if fill and not reject and exposure < min_exposure:  # also the validation floor
        reject = f"{kind}: exposure < {min_exposure}"
    return RockFit(y, tx, tz, exposure, gap, reject)
