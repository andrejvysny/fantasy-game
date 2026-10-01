"""Shared helpers for the valley placement generator: paths, hashing, noise, sampling.

World mapping (same as scripts/valley_terrain.gd): pixel (ix, iz) sits at world
x = ix - 511.5, z = iz - 511.5 (Godot: +x east, +z south, row 0 = north).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import numpy as np
from scipy import ndimage as ndi

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent.parent
TERRAIN_OUT = ROOT / "tools" / "terrain" / "out"
WORLD = ROOT / "world"
GENERATED = WORLD / "generated"
OVERRIDES = WORLD / "overrides" / "valley_overrides.json"
OUT = HERE / "out"
RES = 1024
HALF = (RES - 1) * 0.5
MAP_MIN = -RES * 0.5  # world edge of the map (-512 m)

GOLDEN = np.uint64(0x9E3779B97F4A7C15)
M1 = np.uint64(0xBF58476D1CE4E5B9)
M2 = np.uint64(0x94D049BB133111EB)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text())


def sha1_file(path: Path) -> str:
    return hashlib.sha1(path.read_bytes()).hexdigest()


def sha1_bytes(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


def str_hash(s: str) -> int:
    """Stable 64-bit hash of a string (never Python's salted hash())."""
    return int.from_bytes(hashlib.sha1(s.encode()).digest()[:8], "little")


def mix(x: np.ndarray) -> np.ndarray:
    """splitmix64 finalizer on uint64 arrays (wrapping arithmetic)."""
    x = np.asarray(x, dtype=np.uint64)
    with np.errstate(over="ignore"):
        x = x ^ (x >> np.uint64(30))
        x = x * M1
        x = x ^ (x >> np.uint64(27))
        x = x * M2
        x = x ^ (x >> np.uint64(31))
    return x


def hash_parts(*parts: Any) -> np.ndarray:
    """Combine integer scalars/arrays into one uint64 hash array (order matters)."""
    h = np.uint64(0x243F6A8885A308D3)
    for p in parts:
        v = np.asarray(p).astype(np.int64).astype(np.uint64)
        with np.errstate(over="ignore"):
            h = mix(h ^ mix(v + GOLDEN))
    return np.asarray(h, dtype=np.uint64)


def unit(h: np.ndarray, k: int) -> np.ndarray:
    """k-th uniform [0, 1) draw from per-instance stream keys h."""
    with np.errstate(over="ignore"):
        v = mix(h ^ mix(np.uint64(k) * GOLDEN + np.uint64(1)))
    return (v >> np.uint64(11)).astype(np.float64) * (1.0 / 9007199254740992.0)


def to_u32(h: np.ndarray) -> np.ndarray:
    return (mix(h) >> np.uint64(32)).astype(np.uint32)


def smoothstep(e0: float, e1: float, x: np.ndarray) -> np.ndarray:
    t = np.clip((np.asarray(x, dtype=np.float64) - e0) / (e1 - e0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def noise(name: str, scale_m: float, res: int = RES) -> np.ndarray:
    """Deterministic low-frequency value noise, mean 0.5, std 0.15, clipped to 0..1.

    Seeded only by the field name (stable string hash); feature size ~ scale_m.
    """
    rng = np.random.default_rng(str_hash("noise:" + name))
    white = rng.standard_normal((res, res))
    n = ndi.gaussian_filter(white, sigma=max(scale_m * 0.4, 0.5), mode="wrap")
    n = (n - n.mean()) / max(n.std(), 1e-12)
    return np.clip(0.5 + 0.15 * n, 0.0, 1.0).astype(np.float32)


def world_to_px(x: np.ndarray, z: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    return np.asarray(x, dtype=np.float64) + HALF, np.asarray(z, dtype=np.float64) + HALF


def px_centres() -> tuple[np.ndarray, np.ndarray]:
    """World x, z of every pixel (arrays shaped RES x RES, [iz, ix])."""
    c = np.arange(RES, dtype=np.float64) - HALF
    return np.meshgrid(c, c)


def bilinear(field: np.ndarray, x: np.ndarray, z: np.ndarray) -> np.ndarray:
    """Bilinear sample like ValleyTerrain.get_height (clamp to res - 1.001, float64)."""
    fx, fz = world_to_px(x, z)
    fx = np.clip(fx, 0.0, RES - 1.001)
    fz = np.clip(fz, 0.0, RES - 1.001)
    ix = fx.astype(np.int64)
    iz = fz.astype(np.int64)
    tx = fx - ix
    tz = fz - iz
    f = field
    top = f[iz, ix].astype(np.float64) * (1 - tx) + f[iz, ix + 1].astype(np.float64) * tx
    bot = f[iz + 1, ix].astype(np.float64) * (1 - tx) + f[iz + 1, ix + 1].astype(np.float64) * tx
    return top * (1 - tz) + bot * tz


def nearest(field: np.ndarray, x: np.ndarray, z: np.ndarray) -> np.ndarray:
    fx, fz = world_to_px(x, z)
    ix = np.clip(np.rint(fx).astype(np.int64), 0, RES - 1)
    iz = np.clip(np.rint(fz).astype(np.int64), 0, RES - 1)
    return field[iz, ix]


def in_polygon(poly: list[list[float]], x: np.ndarray, z: np.ndarray) -> np.ndarray:
    """Even-odd point-in-polygon test, vectorised over points."""
    x = np.asarray(x, dtype=np.float64)
    z = np.asarray(z, dtype=np.float64)
    inside = np.zeros(x.shape, dtype=bool)
    n = len(poly)
    for i in range(n):
        x1, z1 = poly[i]
        x2, z2 = poly[(i + 1) % n]
        cross = (z1 > z) != (z2 > z)
        with np.errstate(divide="ignore", invalid="ignore"):
            xi = x1 + (z - z1) * (x2 - x1) / (z2 - z1)
        inside ^= cross & (x < xi)
    return inside


def segment_distance(x: np.ndarray, z: np.ndarray, a: tuple[float, float],
                     b: tuple[float, float]) -> tuple[np.ndarray, np.ndarray]:
    """Distance from points to segment a-b and the clamped parameter t (0..1)."""
    ax, az = a
    dx, dz = b[0] - ax, b[1] - az
    ll = dx * dx + dz * dz
    t = np.clip(((x - ax) * dx + (z - az) * dz) / max(ll, 1e-12), 0.0, 1.0)
    return np.hypot(x - (ax + t * dx), z - (az + t * dz)), t


def rotate(lx: np.ndarray, lz: np.ndarray, yaw: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Godot Basis(UP, yaw) applied to local (x, z): +z -> (sin yaw, cos yaw)."""
    c, s = np.cos(yaw), np.sin(yaw)
    return lx * c + lz * s, -lx * s + lz * c


def disc_stamp(field: np.ndarray, x: float, z: float, r: float, value: float, profile: str = "dome",
               mode: str = "add") -> None:
    """Add (or max) a disc of radius r at world (x, z) into a RES x RES raster in place.

    profile: 'dome' (1 - d^2, smooth patch), 'flat' (1 inside, ~1 m antialiased rim), 'hard'.
    """
    if r <= 0:
        return
    cx, cz = x + HALF, z + HALF
    x0, x1 = max(int(np.floor(cx - r)), 0), min(int(np.ceil(cx + r)) + 1, RES)
    z0, z1 = max(int(np.floor(cz - r)), 0), min(int(np.ceil(cz + r)) + 1, RES)
    if x0 >= x1 or z0 >= z1:
        return
    gx, gz = np.meshgrid(np.arange(x0, x1) - cx, np.arange(z0, z1) - cz)
    dist = np.hypot(gx, gz)
    d = dist / r
    if profile == "dome":
        w = np.clip(1.0 - d * d, 0.0, 1.0)
    elif profile == "flat":
        w = np.clip(r - dist + 0.5, 0.0, 1.0)
    else:
        w = (d <= 1.0).astype(np.float64)
    if mode == "max":
        np.maximum(field[z0:z1, x0:x1], (w * value).astype(field.dtype), out=field[z0:z1, x0:x1])
    else:
        field[z0:z1, x0:x1] += (w * value).astype(field.dtype)
