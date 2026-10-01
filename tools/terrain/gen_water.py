# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "scipy"]
# ///
"""Water surface data for the runtime water mesh (scripts/valley_water.gd).

    uv run gen_water.py

Reads out/terrain_masks.npz (water/sea/lake masks + effective water level per water pixel,
sea = 0 m) and out/heightmap.npy written by gen_heightmap.py; does not touch the terrain.

  level_ext: water level on water pixels, extended to every land pixel with the level of the
             nearest water pixel, so the surface meets the banks instead of stopping at the mask
             edge. Only river-owned pixels are smoothed (removes nearest-pixel steps and lateral
             tilt); lake and sea pixels keep their exact flat level.
  coverage:  1 on water, smooth falloff to 0 over FRINGE_M metres of land. Land lying well below
             the extended level (below a fall or a low bank) gets none, so no sheet floats there.

Outputs (out/): water.f32 (row-major float32, 2 channels interleaved: level, coverage;
row 0 = north, same grid as the heightmap) and water.json (res, level range).
Convert with export_water.gd.
"""
import json
from pathlib import Path

import numpy as np
from scipy import ndimage as ndi

HERE = Path(__file__).parent
OUT = HERE / "out"
FRINGE_M = 8.0  # land fringe that still carries a level (1 m pixels)
RIVER_SMOOTH_M = 1.5  # gaussian sigma along rivers; small so falls stay steep
DRY_DROP_M = (0.3, 1.0)  # land this far below the extended level fades to no coverage


def smoothstep(a: float, b: float, x: np.ndarray) -> np.ndarray:
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def extend_level(level: np.ndarray, water: np.ndarray, lake: np.ndarray, sea: np.ndarray):
    """Nearest-water level everywhere; smoothed where the nearest water is a river."""
    dist, (iy, ix) = ndi.distance_transform_edt(~water, return_indices=True)
    ext = level[iy, ix]
    owner_flat = (lake | sea)[iy, ix]
    river_zone = ~owner_flat & (dist <= FRINGE_M + 4)
    wt = river_zone.astype(np.float64)
    sm = ndi.gaussian_filter(np.where(river_zone, ext, 0.0), RIVER_SMOOTH_M)
    sm /= np.maximum(ndi.gaussian_filter(wt, RIVER_SMOOTH_M), 1e-6)
    ext = np.where(river_zone, sm, ext)
    return ext.astype(np.float32), dist


def coverage_of(ext: np.ndarray, h: np.ndarray, water: np.ndarray, dist: np.ndarray) -> np.ndarray:
    fringe = 1.0 - smoothstep(0.0, FRINGE_M, dist)
    dry = 1.0 - smoothstep(DRY_DROP_M[0], DRY_DROP_M[1], ext - h)
    return np.where(water, 1.0, fringe * dry).astype(np.float32)


def main() -> None:
    m = np.load(OUT / "terrain_masks.npz")
    h = np.load(OUT / "heightmap.npy")
    water, sea, lake, level = m["water"], m["sea"], m["lake"], m["level"]
    ext, dist = extend_level(level, water, lake, sea)
    # Guard the invariant the runtime relies on: every lake is one flat plane.
    lab, n = ndi.label(lake)
    for i in range(1, n + 1):
        vals = ext[lab == i]
        assert vals.min() == vals.max(), f"lake {i} not flat"
    assert np.all(ext[sea] == 0.0)
    cov = coverage_of(ext, h, water, dist)
    res = h.shape[0]
    np.stack([ext, cov], axis=-1).astype("<f4").tofile(OUT / "water.f32")
    wet = cov > 0
    meta = {"res": res, "channels": ["level", "coverage"], "row0": "north",
            "min_level_m": float(ext[wet].min()), "max_level_m": float(ext[wet].max()),
            "fringe_m": FRINGE_M}
    (OUT / "water.json").write_text(json.dumps(meta, indent=2))
    print(f"water {res}x{res}: {int(water.sum())} water px, {int((wet & ~water).sum())} fringe px, "
          f"{n} lakes, level {meta['min_level_m']:.2f} .. {meta['max_level_m']:.2f} m")


if __name__ == "__main__":
    main()
