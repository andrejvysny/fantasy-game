"""Deterministic candidate cells: one hashed stream per (revision, zone, family, cell, slot).

Cells are a grid of size spacing / sqrt(2) over the whole map; the candidate point is the
cell centre plus hashed jitter. Instance ids hash (family, cell ix, iz, slot) only, so they
survive revision and zone edits. Draw indices below are fixed per purpose.
"""
from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
from scipy import ndimage as ndi

from common import MAP_MIN, RES, bilinear, hash_parts, str_hash, to_u32, unit
from spatial import zone_of

D_JX, D_JZ, D_ACCEPT, D_PRIORITY, D_VARIANT, D_SCALE, D_YAW, D_GROUP, D_GROUP_N, D_EXTRA = range(10)


@dataclass
class Cands:
    fam: str
    cell: float
    ix: np.ndarray
    iz: np.ndarray
    slot: np.ndarray
    x: np.ndarray
    z: np.ndarray
    key: np.ndarray  # uint64 stream keys
    iid: np.ndarray  # uint32 stable ids

    def u(self, k: int) -> np.ndarray:
        return unit(self.key, k)

    def take(self, m: np.ndarray) -> "Cands":
        return Cands(self.fam, self.cell, self.ix[m], self.iz[m], self.slot[m], self.x[m], self.z[m],
                     self.key[m], self.iid[m])

    def __len__(self) -> int:
        return len(self.x)


def zone_hashes(zones: list[dict], x: np.ndarray, z: np.ndarray) -> np.ndarray:
    ids = zone_of(zones, x, z)
    table = {zid: str_hash("zone:" + zid) for zid in set(ids.tolist())}
    return np.array([table[i] for i in ids.tolist()], dtype=np.uint64)


def cells(fam: str, spacing: float, density: np.ndarray, seed: int, zones: list[dict]) -> Cands:
    """Jittered candidates for cells whose neighbourhood has density > 0."""
    c = spacing / math.sqrt(2.0)
    n = int(math.ceil(RES / c))
    iz, ix = np.meshgrid(np.arange(n), np.arange(n), indexing="ij")
    ix, iz = ix.ravel(), iz.ravel()
    cx, cz = MAP_MIN + (ix + 0.5) * c, MAP_MIN + (iz + 0.5) * c
    grown = ndi.maximum_filter(density, size=int(math.ceil(c)) + 2)
    keep = (bilinear(grown, cx, cz) > 0) & (cx < -MAP_MIN) & (cz < -MAP_MIN)
    ix, iz, cx, cz = ix[keep], iz[keep], cx[keep], cz[keep]
    fam_h = str_hash("family:" + fam)
    slot = np.zeros(len(ix), dtype=np.int64)
    key = hash_parts(seed, zone_hashes(zones, cx, cz), fam_h, ix, iz, slot)
    x = cx + (unit(key, D_JX) - 0.5) * 0.9 * c
    z = cz + (unit(key, D_JZ) - 0.5) * 0.9 * c
    iid = to_u32(hash_parts(fam_h, ix, iz, slot))
    return Cands(fam, c, ix, iz, slot, x, z, key, iid)


def group_members(leaders: Cands, prob: float, size: tuple[int, int], radius: tuple[float, float],
                  seed: int, zones: list[dict]) -> tuple[Cands, np.ndarray]:
    """Extra members around leaders (slots 1..n); returns members and each member's leader index."""
    has = leaders.u(D_GROUP) < prob
    extra = size[0] + np.floor(leaders.u(D_GROUP_N) * (size[1] - size[0] + 1)).astype(np.int64) - 1
    extra = np.where(has, np.maximum(extra, 0), 0)
    lead = np.repeat(np.arange(len(leaders)), extra)
    slot = np.concatenate([np.arange(1, e + 1) for e in extra]) if extra.sum() else np.zeros(0, np.int64)
    fam_h = str_hash("family:" + leaders.fam)
    lx, lz = leaders.x[lead], leaders.z[lead]
    ix, iz = leaders.ix[lead], leaders.iz[lead]
    cz_zone = zone_hashes(zones, lx, lz) if len(lead) else np.zeros(0, np.uint64)
    key = hash_parts(seed, cz_zone, fam_h, ix, iz, slot)
    ang = unit(key, D_JX) * math.tau
    dist = radius[0] + unit(key, D_JZ) * (radius[1] - radius[0])
    x, z = lx + np.cos(ang) * dist, lz + np.sin(ang) * dist
    iid = to_u32(hash_parts(fam_h, ix, iz, slot))
    return Cands(leaders.fam, leaders.cell, ix, iz, slot.astype(np.int64), x, z, key, iid), lead


def pick_weighted(u: np.ndarray, names: list[str], weights: list[float]) -> np.ndarray:
    """Variant index per draw u from relative weights."""
    cum = np.cumsum(np.asarray(weights, dtype=np.float64))
    return np.minimum(np.searchsorted(cum / cum[-1], u, side="right"), len(names) - 1)
