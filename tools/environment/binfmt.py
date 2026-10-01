"""VPL1 placement files: world/generated/<zone>/<asset_id>.bin, little-endian.

    magic b"VPL1", uint32 count, then count records of 32 bytes:
    float32 x, y, z, yaw_rad, scale, tilt_x, tilt_z, uint32 id      (sorted by id)

Runtime basis: Rx(tilt_x) * Rz(tilt_z) * Ry(yaw) * scale, origin (x, y, z) in world metres.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np

MAGIC = b"VPL1"
RECORD = np.dtype([("x", "<f4"), ("y", "<f4"), ("z", "<f4"), ("yaw", "<f4"), ("scale", "<f4"),
                   ("tilt_x", "<f4"), ("tilt_z", "<f4"), ("id", "<u4")])
assert RECORD.itemsize == 32


def encode(rows: np.ndarray) -> bytes:
    rows = np.sort(np.asarray(rows, dtype=RECORD), order="id", kind="stable")
    return MAGIC + np.uint32(len(rows)).astype("<u4").tobytes() + rows.tobytes()


def decode(data: bytes) -> np.ndarray:
    if data[:4] != MAGIC:
        raise ValueError("not a VPL1 file")
    n = int(np.frombuffer(data[4:8], "<u4")[0])
    if len(data) != 8 + n * RECORD.itemsize:
        raise ValueError(f"VPL1 size mismatch: {len(data)} bytes for {n} records")
    return np.frombuffer(data[8:], dtype=RECORD, count=n)


def read(path: Path) -> np.ndarray:
    return decode(path.read_bytes())


def rows_of(insts: list) -> np.ndarray:
    rows = np.zeros(len(insts), dtype=RECORD)
    for i, s in enumerate(insts):
        rows[i] = (s.x, s.y, s.z, s.yaw, s.scale, s.tilt_x, s.tilt_z, s.iid)
    return rows
