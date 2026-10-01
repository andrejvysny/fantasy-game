# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "pillow"]
# ///
"""Probe valley terrain at world points (x, z metres; origin = map centre, -z = north).

    uv run probe.py x,z [x,z ...]            height, slope, dominant layer, water level
    uv run probe.py --face x,z tx,tz         also yaw (deg) for --yaw= that faces tx,tz

Reads tools/terrain/out (heightmap.npy, terrain_masks.npz, splat_ids.png).
"""
import math
import sys
from pathlib import Path

import numpy as np
from PIL import Image

OUT = Path(__file__).resolve().parent.parent / "terrain" / "out"
LAYERS = ["water_deep", "water_shallow", "rock", "sand", "scree", "dirt", "forest_floor", "grass_dry", "grass"]

h = np.load(OUT / "heightmap.npy")
masks = np.load(OUT / "terrain_masks.npz")
ids = np.asarray(Image.open(OUT / "splat_ids.png"))
half = (h.shape[0] - 1) * 0.5


def sample(x: float, z: float) -> dict:
    ix, iz = int(round(x + half)), int(round(z + half))
    ix, iz = min(max(ix, 1), h.shape[1] - 2), min(max(iz, 1), h.shape[0] - 2)
    dx = (h[iz, ix + 1] - h[iz, ix - 1]) * 0.5
    dz = (h[iz + 1, ix] - h[iz - 1, ix]) * 0.5
    return {"h": float(h[iz, ix]), "slope": math.hypot(dx, dz), "layer": LAYERS[int(ids[iz, ix]) % 9],
            "water": bool(masks["water"][iz, ix]), "level": float(masks["level"][iz, ix])}


def yaw_to(px: float, pz: float, tx: float, tz: float) -> float:
    # Player forward is -Z rotated by yaw: (-sin y, -cos y).
    return math.degrees(math.atan2(-(tx - px), -(tz - pz)))


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "--face":
        (px, pz), (tx, tz) = (map(float, a.split(",")) for a in args[1:3])
        print(sample(px, pz), f"yaw={yaw_to(px, pz, tx, tz):.1f}")
    else:
        for a in args:
            x, z = map(float, a.split(","))
            print(f"({x:.0f},{z:.0f})", sample(x, z))
