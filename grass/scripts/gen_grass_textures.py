#!/usr/bin/env python3
"""
Paints the 2D short-grass sprites (RGBA PNG), same painterly style as the bushes.

  grass_side.png : wide strip of blade clumps, base at the bottom edge (vertical cards)
  grass_top.png  : top-down view of short grass with a ragged round silhouette (ground layer)

Blade size is constant in world units (see make_grass.py): wider areas are covered by
duplicating the same sprites, not by stretching the texture.

Usage: python3 gen_grass_textures.py OUT_DIR      (needs numpy, pillow, gen_textures.py next to it)
"""
import json, math, os, random, sys
from PIL import Image, ImageDraw
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gen_textures import bleed_colors, outline, lerp

SS = 2
DARK, MID, BRIGHT = (12, 58, 8), (38, 146, 14), (125, 224, 42)


def ramp(t):
    t = min(max(t, 0.0), 1.0)
    return lerp(DARK, MID, t / 0.5) if t < 0.5 else lerp(MID, BRIGHT, (t - 0.5) / 0.5)


def col(c, k=1.0):
    return tuple(int(min(255, max(0, v * k))) for v in c) + (255,)


def draw_blade(d, pts, w0, t0, t1, seg=8):
    """Tapered blade along a centre-line. Colour runs base(t0) -> tip(t1); left half highlighted."""
    n = len(pts) - 1
    L, R, C = [], [], []
    for i, (x, y) in enumerate(pts):
        a, b = pts[max(i - 1, 0)], pts[min(i + 1, n)]
        tx, ty = b[0] - a[0], b[1] - a[1]
        m = math.hypot(tx, ty) or 1.0
        nx, ny = -ty / m, tx / m
        w = w0 * 0.5 * (1 - i / n) ** 0.85
        L.append((x + nx * w, y + ny * w))
        R.append((x - nx * w, y - ny * w))
        C.append((x, y))
    for i in range(n):
        tt = t0 + (t1 - t0) * (i + 0.5) / n
        base = ramp(tt)
        d.polygon([L[i], L[i + 1], R[i + 1], R[i]], fill=col(base))
        d.polygon([L[i], L[i + 1], C[i + 1], C[i]], fill=col(ramp(tt + 0.14)))


def curve(x0, y0, dx, dy, bend, n=8):
    """Centre-line from (x0,y0) toward (dx,dy) with a sideways bend."""
    m = math.hypot(dx, dy) or 1.0
    px, py = -dy / m, dx / m
    return [(x0 + dx * (i / n) + px * bend * (i / n) ** 2,
             y0 + dy * (i / n) + py * bend * (i / n) ** 2) for i in range(n + 1)]


def paint_side(W=1024, H=256, seed=3):
    rng = random.Random(seed)
    w, h = W * SS, H * SS
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    # solid, wavy dark base so the card never looks see-through at the ground line
    base_pts = [(0, h + 5)]
    for i in range(0, 65):
        x = w * i / 64
        base_pts.append((x, h - h * (0.10 + 0.04 * math.sin(i * 1.7) + 0.03 * rng.random())))
    base_pts.append((w, h + 5))
    d.polygon(base_pts, fill=col(MID, 0.55))

    blades = []
    n_clumps = 46
    for _ in range(n_clumps):
        cx = rng.uniform(0.04, 0.96) * w
        env = math.sin(math.pi * cx / w) ** 0.55            # shorter toward the card ends
        hc = h * (0.40 + 0.58 * env) * rng.uniform(0.75, 1.0)
        for _ in range(rng.randint(6, 13)):
            off = rng.gauss(0, 0.012 * w)
            blades.append((cx + off, hc * rng.uniform(0.6, 1.0), off / (0.02 * w)))
    rng.shuffle(blades)
    for x0, bh, fan in blades:
        lean = max(-0.4, min(0.4, fan * 0.25 + rng.uniform(-0.25, 0.25)))
        depth = rng.random()
        y0 = h + 0.02 * h
        pts = curve(x0, y0, lean * bh * 0.55, -bh, lean * bh * 0.35)
        w0 = w * rng.uniform(0.010, 0.016)
        t0 = 0.24 + 0.22 * depth
        draw_blade(d, pts, w0, t0, t0 + rng.uniform(0.40, 0.60))
    img = img.resize((W, H), Image.LANCZOS)
    return bleed_colors(img)


def paint_top(W=1024, seed=8):
    rng = random.Random(seed)
    w = W * SS
    img = Image.new("RGBA", (w, w), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx = cy = w / 2
    a = 0.44 * w
    poly = outline(rng, cx, cy, a, a, a, 2.0)
    # dark core so the centre is solid
    d.polygon([(cx + (x - cx) * 0.68, cy + (y - cy) * 0.68) for x, y in poly], fill=col(DARK, 0.9))

    clumps = []
    for _ in range(1000):
        r = a * math.sqrt(rng.random()) * 1.02
        if r > 0.80 * a and rng.random() < 0.75 * (r / a - 0.80) / 0.22:
            continue                                   # thin out the rim -> ragged, see-through fringe
        th = rng.uniform(0, 2 * math.pi)
        x, y = cx + r * math.cos(th), cy + r * math.sin(th)
        clumps.append((x, y, r / a))
    rng.shuffle(clumps)
    for x, y, rho in clumps:
        # baked look: bright rim, darker core, light from the top-left, soft patchiness
        patch = 0.5 + 0.22 * math.sin(x / w * 11.0 + 1.3) * math.sin(y / w * 9.0 + 0.4)
        light = 0.5 + 0.5 * ((-(x - cx) + -(y - cy)) / (2 * a)) * 0.6
        k = (0.15 + 0.55 * patch + 0.3 * light) * (0.6 + 0.4 * rho) + rng.gauss(0, 0.05)
        nb = rng.randint(4, 7)
        a0 = rng.uniform(0, 2 * math.pi)            # clumps sweep one way (no star pattern)
        for i in range(nb):
            ang = a0 + rng.uniform(-1.0, 1.0)
            ln = w * rng.uniform(0.060, 0.100)
            pts = curve(x, y, math.cos(ang) * ln, math.sin(ang) * ln, rng.uniform(-0.35, 0.35) * ln)
            draw_blade(d, pts, w * rng.uniform(0.010, 0.014), k - 0.12, k + 0.30)
    img = img.resize((W, W), Image.LANCZOS)
    return bleed_colors(img)


def bbox(img):
    import numpy as np
    m = np.array(img)[..., 3] > 127
    ys, xs = np.nonzero(m)
    return [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "."
    os.makedirs(out, exist_ok=True)
    meta = {}
    for name, img in (("grass_side", paint_side()), ("grass_top", paint_top())):
        img.save(os.path.join(out, name + ".png"))
        meta[name] = {"w": img.width, "h": img.height, "bbox": bbox(img)}
        print(name, img.size, meta[name]["bbox"])
    json.dump(meta, open(os.path.join(out, "meta.json"), "w"), indent=1)
