"""Placed instances, oriented footprints, exclusion tests and the spacing hash."""
from __future__ import annotations

import math
from dataclasses import dataclass, field

import numpy as np

from assets import Asset
from common import bilinear, in_polygon, rotate, segment_distance


@dataclass(slots=True)
class Inst:
    iid: int
    asset: str
    family: str  # rule / family id that produced it
    x: float
    y: float
    z: float
    yaw: float
    scale: float
    tilt_x: float = 0.0
    tilt_z: float = 0.0
    zone: str = "fill"
    locked: bool = False
    source: str = ""
    radius: float = 0.0  # spacing / solid radius used at placement
    allow_water: bool = False


@dataclass
class Box:
    """Oriented footprint: local x/z extents (already scaled) around (x, z) rotated by yaw."""
    x: float
    z: float
    yaw: float
    x0: float
    x1: float
    z0: float
    z1: float
    grow: float = 0.0
    tag: str = ""

    @staticmethod
    def of(a: Asset, x: float, z: float, yaw: float, s: float, grow: float = 0.0, tag: str = "") -> "Box":
        return Box(x, z, yaw, a.bbox_min[0] * s, a.bbox_max[0] * s, a.bbox_min[2] * s, a.bbox_max[2] * s,
                   grow, tag)

    def distance(self, px: np.ndarray, pz: np.ndarray) -> np.ndarray:
        """Distance from world points to the (grown) box; 0 inside."""
        wx, wz = np.asarray(px) - self.x, np.asarray(pz) - self.z
        c, s = math.cos(self.yaw), math.sin(self.yaw)
        lx, lz = wx * c - wz * s, wx * s + wz * c
        dx = np.maximum(np.maximum(self.x0 - lx, lx - self.x1), 0.0)
        dz = np.maximum(np.maximum(self.z0 - lz, lz - self.z1), 0.0)
        return np.maximum(np.hypot(dx, dz) - self.grow, 0.0)

    def grid(self, step: float = 0.5) -> tuple[np.ndarray, np.ndarray]:
        """World points on a grid covering the (ungrown) footprint, >= 3 x 3."""
        nx = max(int(math.ceil((self.x1 - self.x0) / step)) + 1, 3)
        nz = max(int(math.ceil((self.z1 - self.z0) / step)) + 1, 3)
        lx, lz = np.meshgrid(np.linspace(self.x0, self.x1, nx), np.linspace(self.z0, self.z1, nz))
        ox, oz = rotate(lx.ravel(), lz.ravel(), self.yaw)
        return ox + self.x, oz + self.z


def ground_height(height: np.ndarray, box: Box, rule: str) -> float:
    if rule == "center":
        return float(bilinear(height, np.array([box.x]), np.array([box.z]))[0])
    hx, hz = box.grid()
    hs = bilinear(height, hx, hz)
    return float(hs.min() if rule == "min" else np.median(hs))


def terrain_tilt(gx: np.ndarray, gz: np.ndarray, max_deg: float) -> tuple[np.ndarray, np.ndarray]:
    """Tilt (rad) about x / z so +y follows the terrain normal, clamped to max_deg total.

    Runtime basis: Rx(tilt_x) * Rz(tilt_z) * Ry(yaw) * scale.
    """
    tx = np.arctan(-np.asarray(gz, dtype=np.float64))
    tz = np.arctan(np.asarray(gx, dtype=np.float64))
    mag = np.hypot(tx, tz)
    lim = math.radians(max_deg)
    k = np.where(mag > lim, lim / np.maximum(mag, 1e-12), 1.0)
    return tx * k, tz * k


@dataclass
class Exclusions:
    """Hard placement exclusions: spawn clear radii, view corridors, recipe reserves."""
    spawns: list[tuple[float, float, float]] = field(default_factory=list)
    corridors: list[tuple[tuple[float, float], tuple[float, float], float]] = field(default_factory=list)
    reserves: list[Box] = field(default_factory=list)

    def blocked(self, x: np.ndarray, z: np.ndarray, r: np.ndarray | float,
                reserve_r: np.ndarray | float | None = None, corridors: bool = True) -> np.ndarray:
        """True where a disc of radius r at (x, z) touches any exclusion.

        reserve_r (default r) is the radius tested against recipe reserves; corridors=False
        skips view corridors (cliff dressing sits on terrain that already blocks the view).
        """
        x = np.asarray(x, dtype=np.float64)
        z = np.asarray(z, dtype=np.float64)
        rr = r if reserve_r is None else reserve_r
        out = np.zeros(x.shape, dtype=bool)
        for sx, sz, rad in self.spawns:
            out |= np.hypot(x - sx, z - sz) < rad + r
        for a, b, w in self.corridors if corridors else []:
            d, _ = segment_distance(x, z, a, b)
            out |= d < w * 0.5
        for box in self.reserves:
            out |= box.distance(x, z) < rr
        return out


class SpacingHash:
    """Uniform grid hash of accepted discs for variable-radius rejection."""

    def __init__(self, cell: float = 8.0) -> None:
        self.cell = cell
        self.grid: dict[tuple[int, int], list[tuple[float, float, float, float]]] = {}
        self.max_reach = 0.0

    def add(self, x: float, z: float, r: float, s: float = 0.0) -> None:
        key = (int(math.floor(x / self.cell)), int(math.floor(z / self.cell)))
        self.grid.setdefault(key, []).append((x, z, r, s))
        self.max_reach = max(self.max_reach, r, s)

    def clear(self, x: float, z: float, r: float, s: float, k: float = 0.8) -> bool:
        """No disc within max(min(s, s_b), (r + r_b) * k) of (x, z)."""
        reach = max(s, (r + self.max_reach) * k, self.max_reach)
        n = int(math.ceil(reach / self.cell))
        cx, cz = int(math.floor(x / self.cell)), int(math.floor(z / self.cell))
        for ix in range(cx - n, cx + n + 1):
            for iz in range(cz - n, cz + n + 1):
                for bx, bz, br, bs in self.grid.get((ix, iz), ()):
                    need = max(min(s, bs), (r + br) * k)
                    if (bx - x) ** 2 + (bz - z) ** 2 < need * need:
                        return False
        return True


def zone_of(zones: list[dict], x: np.ndarray, z: np.ndarray) -> np.ndarray:
    """Zone id per point: first anchors zone whose bounds contain it, else 'fill'."""
    out = np.full(np.shape(x), "fill", dtype=object)
    free = np.ones(np.shape(x), dtype=bool)
    for zn in zones:
        hit = free & in_polygon(zn["bounds"], x, z)
        out[hit] = zn["id"]
        free &= ~hit
    return out
