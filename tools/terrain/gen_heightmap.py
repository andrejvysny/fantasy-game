# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "scipy", "pillow"]
# ///
"""Generate the terrain heightmap from ref/topo.png + terrain_features.py.

    uv run gen_heightmap.py

Pipeline:
  1. Classify topo colors -> relief index (hypsometric ramp) + water/sea/lake masks.
  2. Water levels: shortest path from the sea over the water network (river slope,
     flat lakes, explicit waterfall drops) -> monotonic level per water pixel.
  3. Valley floor: harmonic interpolation of water levels over the land.
  4. Height = valley floor + relief + low-amplitude noise.
  5. Cliffs: authored bands are re-profiled into talus + terraced riser + rim.
  6. Carve river/lake beds, banks, coast and sea floor.

Outputs (out/): heightmap.npy (float32 meters, row 0 = north, sea level = 0),
heightmap_16.png + heightmap.json (normalized 16-bit + range), mask_*.png, preview_*.png.
"""
import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage as ndi
from scipy import sparse
from scipy.sparse import csgraph
from scipy.sparse.linalg import spsolve

import terrain_features as F

HERE = Path(__file__).parent
OUT = HERE / "out"
SIZE_M = 1024.0  # world size (m)
RES = 1024  # heightmap samples per side (1 m spacing)
PX = SIZE_M / RES  # meters per sample
K = RES / F.REF_SIZE  # ref px -> sample

RIVER_SLOPE = 0.030  # level rise per m along rivers
LAKE_SLOPE = 0.0005
LAND_SLOPE = 0.5  # high: water must follow rivers/connectors, not shortcut over land
RELIEF_SCALE = 1.35
SEED = 7

# Hypsometric ramp of the topo image (RGB -> relief index). -1 contour line, -2 water.
RAMP = [((109, 147, 95), 0), ((125, 162, 102), 1), ((143, 174, 107), 2), ((160, 183, 112), 3),
        ((178, 192, 118), 4), ((194, 201, 126), 5), ((217, 206, 139), 6), ((228, 205, 175), 7.5),
        ((211, 180, 140), 8), ((194, 159, 124), 9), ((174, 140, 110), 10), ((152, 123, 100), 11),
        ((130, 106, 87), 12), ((84, 91, 81), -1), ((84, 167, 220), -2), ((128, 202, 242), -2)]


def smoothstep(a: float, b: float, x: np.ndarray) -> np.ndarray:
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def disk(r: int) -> np.ndarray:
    y, x = np.ogrid[-r:r + 1, -r:r + 1]
    return x * x + y * y <= r * r


def classify(img: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return (relief index [RES,RES] float, water mask)."""
    cols = np.array([c for c, _ in RAMP], np.float32)
    vals = np.array([v for _, v in RAMP], np.float32)
    idx = np.empty(img.shape[:2], np.int32)
    for r in range(0, img.shape[0], 128):  # chunked to bound memory
        d = ((img[r:r + 128, :, None, :] - cols[None, None]) ** 2).sum(-1)
        idx[r:r + 128] = d.argmin(-1)
    v = vals[idx]
    water = ndi.binary_opening(ndi.binary_closing(v == -2, disk(1)), disk(1))
    land = v >= 0
    _, near = ndi.distance_transform_edt(~land, return_indices=True)
    rel = ndi.median_filter(v[near[0], near[1]], 5)
    return ndi.gaussian_filter(rel, 7.0 / PX), water


def split_water(water: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Sea = wide water touching the map border; lakes = wide inland water."""
    r = int(10 / PX)
    wide = ndi.binary_opening(np.pad(water, r, mode="edge"), disk(r))[r:-r, r:-r]
    lab, _ = ndi.label(wide)
    m = 4  # morphology leaves a thin unset frame at the image edge
    border = np.unique(np.concatenate([lab[:m].ravel(), lab[-m:].ravel(),
                                       lab[:, :m].ravel(), lab[:, -m:].ravel()]))
    sea = np.isin(lab, border[border > 0])
    sea = ndi.binary_dilation(sea, disk(int(10 / PX))) & water
    lake = ndi.binary_opening(water & ~sea, disk(int(6 / PX)))
    lake = ndi.binary_dilation(lake, disk(int(6 / PX))) & water & ~sea
    return sea, lake


def polyline_field(pts_ref, shape):
    """Per-pixel (m): lateral signed offset s, distance d, end overshoot e, unit normal, arc length."""
    P = np.array(pts_ref, np.float64) * K * PX
    yy, xx = np.mgrid[0:shape[0], 0:shape[1]]
    px, py = (xx + 0.5) * PX, (yy + 0.5) * PX
    best = np.full(shape, np.inf)
    s, e, nx, ny, along = (np.zeros(shape) for _ in range(5))
    arc = 0.0
    for i in range(len(P) - 1):
        a, b = P[i], P[i + 1]
        ab = b - a
        ln = np.hypot(*ab)
        t_raw = ((px - a[0]) * ab[0] + (py - a[1]) * ab[1]) / ln**2
        t = np.clip(t_raw, 0, 1)
        d = np.hypot(px - (a[0] + t * ab[0]), py - (a[1] + t * ab[1]))
        m = d < best
        best[m] = d[m]
        s[m] = ((ab[0] * (py - a[1]) - ab[1] * (px - a[0])) / ln)[m]
        over = np.zeros(shape)
        if i == 0:
            over = np.maximum(over, -t_raw * ln)
        if i == len(P) - 2:
            over = np.maximum(over, (t_raw - 1) * ln)
        e[m] = over[m]
        nx[m], ny[m] = -ab[1] / ln, ab[0] / ln
        along[m] = (arc + t * ln)[m]
        arc += ln
    return s, best, e, nx, ny, along


def fall_cost(shape) -> np.ndarray:
    cost = np.zeros(shape)
    band = 2.5  # m, half thickness of the fall line
    for f in F.FALLS:
        d = polyline_field(f["pts"], shape)[1]
        cost[d < band] += f["drop"] / (2 * band)
    return cost


def water_levels(water, sea, lake) -> np.ndarray:
    """Shortest-path level from the sea (0 m) over water; land bridges gaps."""
    h, w = water.shape
    link = np.zeros(water.shape, bool)
    for cn in F.CONNECTORS:
        link |= polyline_field(cn["pts"], water.shape)[1] < 2.0
    c = np.where(lake, LAKE_SLOPE, np.where(water | link, RIVER_SLOPE, LAND_SLOPE))
    c = (c + fall_cost(water.shape)) * PX
    ids = np.arange(h * w).reshape(h, w)
    rows, cols, wts = [], [], []
    for dy, dx, ln in [(0, 1, 1.0), (1, 0, 1.0), (1, 1, 1.414), (1, -1, 1.414)]:
        x0, x1 = max(0, -dx), w - max(0, dx)
        a = ids[0:h - dy, x0:x1].ravel()
        b = ids[dy:h, x0 + dx:x1 + dx].ravel()
        cw = 0.5 * (c.ravel()[a] + c.ravel()[b]) * ln
        rows += [a, b]; cols += [b, a]; wts += [cw, cw]
    g = sparse.csr_matrix((np.concatenate(wts), (np.concatenate(rows), np.concatenate(cols))),
                          shape=(h * w, h * w))
    src = ids[sea]
    lvl = csgraph.dijkstra(g, indices=src, min_only=True)
    return lvl.reshape(h, w)


def harmonic_fill(level: np.ndarray, fixed: np.ndarray, n: int = 256) -> np.ndarray:
    """Solve Laplace(V)=0 on an n x n grid with water cells fixed; upsample to full res."""
    f = level.shape[0] // n
    fx = fixed.reshape(n, f, n, f)
    cnt = fx.sum((1, 3))
    vsum = np.where(fixed, level, 0).reshape(n, f, n, f).sum((1, 3))
    known = cnt > 0
    kv = np.where(known, vsum / np.maximum(cnt, 1), 0)
    free = ~known
    fid = -np.ones((n, n), int); fid[free] = np.arange(free.sum())
    rows, cols, vals = [], [], []
    rhs = np.zeros(free.sum())
    for dy, dx in [(0, 1), (0, -1), (1, 0), (-1, 0)]:
        ys, xs = np.nonzero(free)
        ny, nx = ys + dy, xs + dx
        ok = (ny >= 0) & (ny < n) & (nx >= 0) & (nx < n)  # Neumann at map edges
        ys, xs, ny, nx = ys[ok], xs[ok], ny[ok], nx[ok]
        me = fid[ys, xs]
        rows.append(me); cols.append(me); vals.append(np.ones(len(me)))
        nb_free = free[ny, nx]
        rows.append(me[nb_free]); cols.append(fid[ny, nx][nb_free]); vals.append(-np.ones(nb_free.sum()))
        np.add.at(rhs, me[~nb_free], kv[ny, nx][~nb_free])
    A = sparse.csr_matrix((np.concatenate(vals), (np.concatenate(rows), np.concatenate(cols))),
                          shape=(len(rhs),) * 2)
    V = kv.copy()
    V[free] = spsolve(A.tocsc(), rhs)
    return ndi.gaussian_filter(ndi.zoom(V, f, order=1), 2.0 * f)


def fbm(shape, rng, scales_amps) -> np.ndarray:
    out = np.zeros(shape)
    for sc, amp in scales_amps:
        n = ndi.gaussian_filter(rng.standard_normal(shape), sc / PX, mode="wrap")
        out += amp * n / (n.std() + 1e-9)
    return out


def cliff_profile(u, steps: int, jitter, t0: float = 0.38, t1: float = 0.62):
    """0 at the low edge, 1 at the high edge: concave talus, terraced riser, rounded rim."""
    talus = 0.10 * (u / t0) ** 2
    q = np.clip((u - t0) / (t1 - t0), 0, 1) * steps
    fl = np.minimum(np.floor(q), steps - 1)
    riser = 0.10 + 0.85 * (fl + smoothstep(0.25 + jitter, 1.0, q - fl)) / steps
    v = np.clip((u - t1) / (1 - t1), 0, 1)
    rim = 0.95 + 0.05 * (1 - (1 - v) ** 2)
    return np.where(u < t0, talus, np.where(u < t1, riser, rim))


def high_side(hs, s, e, w) -> float:
    """+1 when the terrain on the +s side of the cliff line is higher, else -1."""
    core = e < 1.0
    pos = hs[core & (s > w) & (s < 2.5 * w)].mean()
    neg = hs[core & (s < -w) & (s > -2.5 * w)].mean()
    return 1.0 if pos >= neg else -1.0


def gully_noise(rng, length: float) -> tuple[np.ndarray, np.ndarray]:
    """1D noise along the cliff line (m) -> chutes and buttresses across the face."""
    g = ndi.gaussian_filter1d(rng.standard_normal(int(length) + 2), 5.0)
    return np.arange(len(g), dtype=float), g / (g.std() + 1e-9)


def apply_cliffs(h: np.ndarray, d_water: np.ndarray, rng) -> tuple[np.ndarray, np.ndarray]:
    """Sharpen the authored cliff bands and lift their high side by `drop` (fading over `back`)."""
    hs = ndi.gaussian_filter(h, 3.0 / PX)
    wob_big = fbm(h.shape, rng, [(30, 1.0)])
    wob_small = fbm(h.shape, rng, [(6, 1.0)])
    mask = np.zeros_like(h)
    lift_all = np.zeros_like(h)  # max-combined so overlapping cliffs do not stack into spikes
    for c in F.CLIFFS:
        w, back, drop, taper = float(c["w"]), float(c.get("back", 200)), float(c["drop"]), float(c.get("taper", 50))
        s, _, e, nx, ny, along = polyline_field(c["pts"], h.shape)
        side = c.get("side") or high_side(hs, s, e, w)
        sh = s * side
        sel = np.nonzero((sh > -w) & (sh < w + back) & (e < taper))
        shs = sh[sel]
        py, px = (sel[0] + 0.5) * PX, (sel[1] + 0.5) * PX
        nxs, nys = nx[sel] * side, ny[sel] * side

        def sample(off):
            return ndi.map_coordinates(hs, [(py + nys * off) / PX - 0.5, (px + nxs * off) / PX - 0.5],
                                       order=1, mode="nearest")
        gx, gy = gully_noise(rng, along.max())
        sh2 = shs + wob_big[sel] * 0.25 * w + wob_small[sel] + np.interp(along[sel], gx, gy) * 3.0
        u = np.clip((sh2 + w) / (2 * w), 0, 1)
        prof = cliff_profile(u, int(c["steps"]), np.clip(0.2 + 0.2 * wob_small[sel], 0, 0.45))
        h_hi, h_lo = sample(w - shs), sample(-w - shs)
        sharp = np.minimum(h_hi, h_lo) + np.abs(h_hi - h_lo) * prof
        endfade = 1 - smoothstep(0, taper, e[sel])
        band = (1 - smoothstep(0.75, 1.0, np.abs(shs) / w)) * endfade
        lift = drop * prof * (1 - smoothstep(w, w + back, shs)) * endfade * smoothstep(8, 45, d_water[sel])
        h[sel] += band * (sharp - h[sel])
        lift_all[sel] = np.maximum(lift_all[sel], lift)
        face = endfade * smoothstep(0.34, 0.38, u) * (1 - smoothstep(0.62, 0.66, u))
        mask[sel] = np.maximum(mask[sel], face)
    h += lift_all
    # remove needles/knife ridges narrower than ~7 m left where cliff bands meet or end
    opened = ndi.grey_opening(h, size=(int(7 / PX),) * 2)
    h = np.minimum(h, opened + 2.0)
    soft = ndi.gaussian_filter(h, 0.8 / PX)  # anti-alias the risers on the 1 m grid
    zone = np.clip(ndi.gaussian_filter(mask, 3 / PX) * 4, 0, 1)
    return h + zone * (soft - h), mask


def smin(a, b, k: float):
    """Polynomial smooth minimum."""
    t = np.clip(0.5 + 0.5 * (b - a) / k, 0, 1)
    return b + (a - b) * t - k * t * (1 - t)


def effective_level(h, level, water, lake) -> np.ndarray:
    """Water level clamped below the surrounding banks, so no bank has to rise above the
    ground behind it (that produced levee rims). Lakes stay flat."""
    land_h = np.where(water, np.inf, h)
    ring = ndi.minimum_filter(land_h, size=int(9 / PX))
    eff = np.where(water, np.minimum(level, ring - 0.4), np.nan)
    lab, n = ndi.label(lake)
    if n:
        # 10th percentile of the shore, not the minimum: the outlet notch alone must not drain a lake
        lvl = np.array([np.percentile(eff[(lab == i) & np.isfinite(eff)], 10) for i in range(1, n + 1)])
        eff = np.where(lake, lvl[np.maximum(lab - 1, 0)], eff)
    wf = water.astype(float)
    sm = ndi.gaussian_filter(np.where(water, eff, 0), 6 / PX) / np.maximum(ndi.gaussian_filter(wf, 6 / PX), 1e-6)
    return np.where(water, np.where(lake, eff, np.minimum(eff, sm)), level)


def carve_water(h, level, water, lake, cliff) -> tuple[np.ndarray, np.ndarray]:
    level = effective_level(h, level, water, lake)
    d_in = ndi.distance_transform_edt(water) * PX
    d_out, near = ndi.distance_transform_edt(~water, return_indices=True)
    d_out *= PX
    L = np.where(water, level, ndi.gaussian_filter(level[near[0], near[1]], 10 / PX))
    steep = np.clip(ndi.gaussian_filter(cliff, 4 / PX) * 3, 0, 1)
    bank = 1.0 + (0.12 + 2.0 * steep) * d_out + 0.012 * d_out**2  # flat floodplain, widening valley
    h = L + smin(h - L, bank, 5.0)
    dd = ndi.gaussian_filter(d_in, 3 / PX)
    depth = np.where(lake, np.minimum(1.0 + 0.3 * dd, 14.0), np.minimum(0.8 + 0.45 * d_in, 3.0))
    h = np.where(water, L - depth, h)
    edge = 1 - smoothstep(2.0, 6.0, np.minimum(d_in, d_out))  # round off the bank lip
    return h + edge * (ndi.gaussian_filter(h, 2.0 / PX) - h), level


def carve_coast(h, sea, water, rel) -> np.ndarray:
    d_out = ndi.distance_transform_edt(~sea) * PX
    d_in = ndi.distance_transform_edt(sea) * PX
    rock = np.clip((rel - 4) / 8, 0, 1)  # rocky shores are drawn brown in the topo
    cap = 0.3 + 3.5 * rock**2 + (0.6 + 1.0 * rock) * d_out + 0.02 * d_out**2
    wt = 1 - smoothstep(30, 55, d_out)
    h = h + wt * (smin(h, cap, 2.0) - h)
    h = np.where(~water & (d_out < 20), np.maximum(h, 0.5 + 0.05 * d_out), h)
    floor = ndi.gaussian_filter(-(0.6 + 15 * (1 - np.exp(-d_in / 60))), 3 / PX)
    h = np.where(sea, floor, h)
    edge = 1 - smoothstep(2.0, 6.0, np.minimum(d_in, d_out))  # blend the shoreline step
    return h + edge * (ndi.gaussian_filter(h, 2.0 / PX) - h)


def build() -> dict:
    rng = np.random.default_rng(SEED)
    img = Image.open(HERE / "ref/topo.png").convert("RGB").resize((RES, RES), Image.LANCZOS)
    rel, water = classify(np.asarray(img, np.float32))
    sea, lake = split_water(water)
    level = water_levels(water, sea, lake)
    valley = harmonic_fill(level, water)
    relief = RELIEF_SCALE * (1 + 2.6 * rel + 0.2 * rel**2)
    noise = fbm(rel.shape, rng, [(60, 3.0), (20, 1.0), (7, 0.3)]) * (0.4 + rel / 12)
    h = valley + relief + noise
    d_water = ndi.distance_transform_edt(~(water & ~sea)) * PX
    h, cliff = apply_cliffs(h, d_water, rng)
    h, level = carve_water(h, level, water & ~sea, lake, cliff)
    h = carve_coast(h, sea, water, rel)
    return {"h": h.astype(np.float32), "level": level, "water": water, "sea": sea,
            "lake": lake, "cliff": cliff, "valley": valley}


def hillshade(h: np.ndarray, az: float = 315, alt: float = 40) -> np.ndarray:
    gy, gx = np.gradient(h, PX)
    a, b = np.radians(az), np.radians(alt)
    slope = np.arctan(np.hypot(gx, gy))
    aspect = np.arctan2(-gx, gy)
    return np.clip(np.sin(b) * np.cos(slope) + np.cos(b) * np.sin(slope) * np.cos(a - aspect), 0, 1)


def save_previews(r: dict) -> None:
    h, water = r["h"], r["water"]
    hs = hillshade(h)
    Image.fromarray((hs * 255).astype(np.uint8)).save(OUT / "preview_hillshade.png")
    stops = np.array([[70, 120, 70], [150, 185, 110], [215, 205, 140], [185, 150, 115], [120, 95, 80]], float)
    t = np.clip(h / max(h.max(), 1), 0, 1) * (len(stops) - 1)
    i = np.minimum(t.astype(int), len(stops) - 2)
    col = stops[i] + (stops[i + 1] - stops[i]) * (t - i)[..., None]
    col *= (0.45 + 0.65 * hs)[..., None]
    contour = np.abs((h / 5.0) - np.round(h / 5.0)) * 5.0 < 0.12 * np.hypot(*np.gradient(h)) + 0.05
    col[contour & ~water] *= 0.7
    col[water] = [80, 150, 215]
    tint = Image.fromarray(np.clip(col, 0, 255).astype(np.uint8))
    tint.save(OUT / "preview_tint.png")
    ref = Image.open(HERE / "ref/topo.png").convert("RGB").resize((RES, RES))
    pair = Image.new("RGB", (RES * 2, RES)); pair.paste(ref, (0, 0)); pair.paste(tint, (RES, 0))
    pair.resize((RES, RES // 2)).save(OUT / "preview_compare.png")
    lv = np.where(water, r["level"], np.nan)
    print("level range on water:", np.nanmin(lv), np.nanmax(lv))


def save_outputs(r: dict) -> None:
    OUT.mkdir(exist_ok=True)
    h = r["h"]
    np.save(OUT / "heightmap.npy", h)
    h.astype("<f4").tofile(OUT / "heightmap.f32")  # raw row-major float32 for export_godot.gd
    lo, hi = float(h.min()), float(h.max())
    Image.fromarray(((h - lo) / (hi - lo) * 65535).astype(np.uint16)).save(OUT / "heightmap_16.png")
    (OUT / "heightmap.json").write_text(json.dumps(
        {"size_m": SIZE_M, "res": RES, "spacing_m": PX, "min_m": lo, "max_m": hi,
         "sea_level_m": 0.0, "row0": "north"}, indent=2))
    for name in ("water", "cliff"):
        Image.fromarray((np.clip(r[name].astype(np.float32), 0, 1) * 255).astype(np.uint8)).save(
            OUT / f"mask_{name}.png")
    np.savez_compressed(OUT / "terrain_masks.npz", water=r["water"], sea=r["sea"], lake=r["lake"],
                        cliff=r["cliff"].astype(np.float32), level=r["level"].astype(np.float32))
    save_previews(r)
    for k, (x, y) in F.PROBES.items():
        iy, ix = int(y * K), int(x * K)
        print(f"  {k:24s} h={h[iy, ix]:7.1f}  level={r['level'][iy, ix]:6.1f}  valley={r['valley'][iy, ix]:6.1f}")
    print(f"height range {lo:.1f} .. {hi:.1f} m")


if __name__ == "__main__":
    save_outputs(build())
