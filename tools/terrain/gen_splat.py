# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "scipy", "pillow"]
# ///
"""Paint the terrain: per-layer weight maps from ref/painted.png + terrain shape.

    uv run gen_splat.py        (after gen_heightmap.py)

Ground classes (grass, dry grass, forest floor, dirt paths, rock) come from the painted
map's colors; water, sand, rock faces and scree come from the generated terrain
(water masks, depth, slope, cliff mask, distance to the sea), so paint and geometry agree.
Objects in the painting (trees, lodge, props) are not painted; tree cover becomes forest floor.

Outputs (out/): splat_0/1/2.png (RGB = 3 layer weights each, summing to 1 over all
layers), splat_ids.png (dominant layer index), splat.json (layer order + palette),
albedo.png (flat color preview / Terrain3D color map), preview_paint_compare.png.
"""
import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy import ndimage as ndi

HERE = Path(__file__).parent
OUT = HERE / "out"
SEED = 11

# Priority order: each layer takes its share of whatever the layers before it left.
# Colors are sRGB (dark, light); the light/dark mix is driven by noise.
LAYERS = [
    ("water_deep", (18, 48, 72), (28, 66, 92)),
    ("water_shallow", (44, 92, 104), (66, 120, 128)),
    ("rock", (84, 82, 78), (148, 142, 128)),
    ("sand", (190, 172, 128), (222, 206, 160)),
    ("scree", (118, 110, 94), (156, 146, 124)),
    ("dirt", (138, 108, 70), (184, 156, 104)),
    ("forest_floor", (46, 62, 38), (78, 86, 48)),
    ("grass_dry", (134, 128, 66), (166, 156, 88)),
    ("grass", (84, 108, 48), (120, 138, 62)),
]


def smoothstep(a: float, b: float, x: np.ndarray) -> np.ndarray:
    t = np.clip((x - a) / (b - a), 0.0, 1.0)
    return t * t * (3 - 2 * t)


def band(x: np.ndarray, a: float, b: float, soft: float) -> np.ndarray:
    return smoothstep(a - soft, a, x) * (1 - smoothstep(b, b + soft, x))


def to_hsv(img: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    r, g, b = img[..., 0], img[..., 1], img[..., 2]
    v = img.max(-1)
    c = v - img.min(-1)
    s = np.where(v > 0, c / np.maximum(v, 1e-6), 0)
    cc = np.maximum(c, 1e-6)
    h = np.where(v == r, (g - b) / cc % 6, np.where(v == g, (b - r) / cc + 2, (r - g) / cc + 4)) * 60
    return np.where(c > 1e-6, h, 0), s, v


def painted_classes(res: int) -> dict:
    """Soft class memberships from the painted map, blurred to ground-scale areas."""
    img = Image.open(HERE / "ref/painted.png").convert("RGB").resize((res, res), Image.LANCZOS)
    a = ndi.gaussian_filter(np.asarray(img, np.float32) / 255, (1.2, 1.2, 0))
    h, s, v = to_hsv(a)
    cls = {
        "forest": (1 - smoothstep(0.30, 0.40, v)) * band(h, 75, 185, 10),
        "grass": smoothstep(0.36, 0.44, v) * band(h, 62, 110, 8) * smoothstep(0.28, 0.38, s),
        "dry": smoothstep(0.52, 0.60, v) * band(h, 46, 64, 6) * smoothstep(0.34, 0.42, s),
        "path": smoothstep(0.58, 0.68, v) * band(h, 30, 50, 6) * smoothstep(0.24, 0.32, s),
        "rock": (1 - smoothstep(0.13, 0.22, s)) * smoothstep(0.34, 0.44, v) * (1 - smoothstep(0.80, 0.88, v)),
        "sand": smoothstep(0.44, 0.52, v) * band(h, 34, 56, 6) * band(s, 0.15, 0.34, 0.04),
    }
    sig = {"forest": 5.0, "grass": 3.0, "dry": 3.0, "path": 1.0, "rock": 2.0, "sand": 2.0}
    return {k: ndi.gaussian_filter(m, sig[k]) for k, m in cls.items()}


def fbm(shape, rng, scales_amps) -> np.ndarray:
    out = np.zeros(shape)
    for sc, amp in scales_amps:
        n = ndi.gaussian_filter(rng.standard_normal(shape), sc, mode="wrap")
        out += amp * n / (n.std() + 1e-9)
    return out


def terrain_masks(h: np.ndarray, m: dict, px: float, rng) -> dict:
    """Layer masks (0..1, before priority compositing) from the terrain + painted classes."""
    P = painted_classes(h.shape[0])
    gy, gx = np.gradient(ndi.gaussian_filter(h, 2 / px), px)  # mid-scale slope, ignores 1 m noise
    slope = np.degrees(np.arctan(np.hypot(gx, gy)))
    water, sea, cliff = m["water"], m["sea"], m["cliff"]
    inland = water & ~sea
    depth = np.where(water, np.where(sea, -h, m["level"] - h), 0)
    d_sea = ndi.distance_transform_edt(~sea) * px
    d_wat = ndi.distance_transform_edt(~inland) * px
    jit = fbm(h.shape, rng, [(12, 1.0), (3, 0.5)])  # breaks up straight mask edges
    wsoft = ndi.gaussian_filter(water.astype(float), 0.8)
    talus = ndi.gaussian_filter(cliff, 6 / px)
    # the relief is steep overall (median ~28 deg): bare rock only on cliffs and the steepest faces
    rock = np.maximum.reduce([smoothstep(52, 62, slope + 4 * jit), np.clip(cliff * 1.2, 0, 1),
                              smoothstep(0.3, 0.5, P["rock"]) * smoothstep(42, 55, slope),
                              smoothstep(0.2, 0.4, P["rock"]) * (1 - smoothstep(3, 10, d_sea))])
    sand_zone = (1 - smoothstep(8, 18, d_sea + 3 * jit)) * (1 - smoothstep(4.0, 8.0, h))
    sand_pick = np.maximum(smoothstep(0.12, 0.28, P["sand"]), smoothstep(30, 15, slope)) * (1 - P["rock"])
    return {
        "water_deep": wsoft * np.where(sea, smoothstep(3.0, 12.0, depth), smoothstep(1.5, 7.0, depth)),
        "water_shallow": wsoft,
        "rock": rock,
        "sand": sand_zone * sand_pick * smoothstep(55, 40, slope),  # coast geometry is steep
        "scree": np.maximum(smoothstep(45, 55, slope + 3 * jit) * 0.7,
                            smoothstep(0.08, 0.2, talus) * smoothstep(20, 35, slope)),
        "dirt": np.maximum.reduce([smoothstep(0.18, 0.35, P["path"]),
                                   (1 - smoothstep(1.0, 3.5, d_wat + jit)) * 0.8,
                                   smoothstep(38, 48, slope + 3 * jit) * 0.4]),
        "forest_floor": smoothstep(0.35, 0.6, P["forest"] + 0.08 * jit),
        "grass_dry": smoothstep(0.12, 0.3, P["dry"] + 0.05 * jit) * 0.9,
        "grass": np.ones_like(h),
    }


def composite(masks: dict) -> np.ndarray:
    """Priority 'over' compositing -> weights [L, H, W] summing to 1."""
    remaining = np.ones_like(masks["grass"])
    out = []
    for name, _, _ in LAYERS:
        w = remaining * np.clip(masks[name], 0, 1)
        remaining = remaining - w
        out.append(w)
    return np.stack(out)


def albedo(weights: np.ndarray, rng) -> np.ndarray:
    n = np.clip(0.5 + 0.35 * fbm(weights.shape[1:], rng, [(20, 0.6), (4, 0.4)]), 0, 1)[..., None]
    col = np.zeros(weights.shape[1:] + (3,))
    for w, (_, dark, light) in zip(weights, LAYERS):
        col += w[..., None] * (np.array(dark) + (np.array(light) - np.array(dark)) * n)
    return col


def save(weights: np.ndarray, h: np.ndarray, col: np.ndarray, px: float) -> None:
    for i in range(3):
        rgb = np.moveaxis(weights[3 * i:3 * i + 3], 0, -1)
        Image.fromarray((rgb * 255 + 0.5).astype(np.uint8)).save(OUT / f"splat_{i}.png")
    Image.fromarray(weights.argmax(0).astype(np.uint8)).save(OUT / "splat_ids.png")
    (OUT / "splat.json").write_text(json.dumps(
        {"images": ["splat_0.png", "splat_1.png", "splat_2.png"], "row0": "north",
         "layers": [{"name": n, "dark": d, "light": li} for n, d, li in LAYERS]}, indent=2))
    Image.fromarray(np.clip(col, 0, 255).astype(np.uint8)).save(OUT / "albedo.png")
    gy, gx = np.gradient(h, px)
    shade = np.clip(0.75 + 0.6 * (gx * 0.5 - gy * 0.5) / np.sqrt(1 + gx**2 + gy**2), 0.35, 1.25)
    lit = Image.fromarray(np.clip(col * shade[..., None], 0, 255).astype(np.uint8))
    res = h.shape[0]
    ref = Image.open(HERE / "ref/painted.png").convert("RGB").resize((res, res))
    pair = Image.new("RGB", (res * 2, res)); pair.paste(ref, (0, 0)); pair.paste(lit, (res, 0))
    pair.save(OUT / "preview_paint_compare.png")


def main() -> None:
    meta = json.loads((OUT / "heightmap.json").read_text())
    h = np.load(OUT / "heightmap.npy").astype(np.float64)
    m = dict(np.load(OUT / "terrain_masks.npz"))
    rng = np.random.default_rng(SEED)
    weights = composite(terrain_masks(h, m, meta["spacing_m"], rng))
    save(weights, h, albedo(weights, rng), meta["spacing_m"])
    share = {n: f"{w.mean() * 100:.1f}%" for (n, _, _), w in zip(LAYERS, weights)}
    print("layer coverage:", share)


if __name__ == "__main__":
    main()
