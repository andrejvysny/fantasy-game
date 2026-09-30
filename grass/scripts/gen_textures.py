#!/usr/bin/env python3
"""
Paints the 2D bush sprites (RGBA PNG) by stamping lobed leaf shapes.
Matches the reference: hard-edged painterly leaves, dark core, bright top-left,
ragged silhouette, dark pockets inside.

Usage: python3 gen_textures.py OUT_DIR
Needs: numpy, pillow
"""
import json, math, os, random, sys
import numpy as np
from PIL import Image, ImageDraw

SS = 2  # supersampling for clean edges

# name: (tex_w, tex_h, bush aspect w/h measured from reference, seed)
SPECS = {
    "bush_S": (512, 512, 1.00, 11),
    "bush_M": (768, 768, 1.07, 23),
    "bush_L": (1024, 768, 1.34, 37),
}
CAP = ("bush_cap", 512, 512)

DARK, MID, BRIGHT = (8, 52, 10), (28, 140, 14), (92, 225, 32)


def lerp(a, b, t):
    return tuple(a[i] + (b[i] - a[i]) * t for i in range(3))


def ramp(t):
    t = min(max(t, 0.0), 1.0)
    return lerp(DARK, MID, t / 0.5) if t < 0.5 else lerp(MID, BRIGHT, (t - 0.5) / 0.5)


def outline(rng, cx, cy, a, b_top, b_bot, n_exp, n=200):
    ph = [rng.uniform(0, 6.283) for _ in range(4)]
    e = 2.0 / n_exp
    pts = []
    for i in range(n):
        t = 2 * math.pi * i / n
        c, s = math.cos(t), math.sin(t)
        f = (1 + 0.05 * math.sin(2 * t + ph[0]) + 0.035 * math.sin(3 * t + ph[1])
             + 0.025 * math.sin(5 * t + ph[2]) + 0.015 * math.sin(9 * t + ph[3]))
        x = a * math.copysign(abs(c) ** e, c) * f
        b = b_top if s > 0 else b_bot
        y = -b * math.copysign(abs(s) ** e, s) * f
        pts.append((cx + x, cy + y))
    return pts


def leaf_poly(rng, x, y, r, ang):
    p1, p2, p3 = (rng.uniform(0, 6.283) for _ in range(3))
    ca, sa = math.cos(ang), math.sin(ang)
    pts = []
    for i in range(30):
        t = 2 * math.pi * i / 30
        rr = r * (1 + 0.28 * math.sin(3 * t + p1) + 0.14 * math.sin(5 * t + p2) + 0.08 * math.sin(7 * t + p3))
        lx, ly = rr * 1.25 * math.cos(t), rr * math.sin(t)
        pts.append((x + lx * ca - ly * sa, y + lx * sa + ly * ca))
    return pts


def shifted(pts, dx, dy, scale=1.0, about=None):
    if about is None:
        about = (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
    return [(about[0] + (p[0] - about[0]) * scale + dx, about[1] + (p[1] - about[1]) * scale + dy) for p in pts]


def bleed_colors(img):
    """Push opaque colour into transparent texels so mip/filter never shows dark halos."""
    arr = np.array(img).astype(np.float32)
    a, rgb = arr[..., 3], arr[..., :3]
    known = a > 8
    for _ in range(10):
        acc = np.zeros_like(rgb)
        cnt = np.zeros(a.shape, np.float32)
        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue
                k = np.roll(known, (dy, dx), (0, 1))
                acc += np.roll(rgb, (dy, dx), (0, 1)) * k[..., None]
                cnt += k
        fill = (~known) & (cnt > 0)
        rgb[fill] = acc[fill] / cnt[fill][:, None]
        known |= fill
    arr[..., :3] = rgb
    # slightly harden alpha for Alpha Scissor (keeps ~1px antialiasing)
    al = arr[..., 3] / 255.0
    arr[..., 3] = np.clip((al - 0.5) * 2.2 + 0.5, 0, 1) * 255
    return Image.fromarray(arr.astype(np.uint8), "RGBA")


def paint(name, W, H, aspect, seed, kind="side"):
    rng = random.Random(seed)
    w, h = W * SS, H * SS
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    if kind == "side":
        a = 0.5 * w * 0.86
        total_h = min(2 * a / aspect, h * 0.78)
        b_bot = 0.12 * total_h
        b_top = 0.88 * total_h
        cy = h - 0.075 * h - b_bot
        cx = w / 2
        poly = outline(rng, cx, cy, a, b_top, b_bot, 2.2)
    else:  # top-down disc for the optional cap card
        a = b_top = b_bot = 0.40 * w
        cx, cy = w / 2, h / 2
        poly = outline(rng, cx, cy, a, b_top, b_bot, 2.0)
        total_h = 2 * a

    # dark core fill so the interior is never see-through
    d.polygon(shifted(poly, 0, 0, 0.62, (cx, cy)), fill=(*DARK, 255))

    mask = Image.new("L", (w, h), 0)
    ImageDraw.Draw(mask).polygon(poly, fill=255)
    m = np.array(mask) > 0
    area = m.sum()
    r_mean = 0.085 * a
    n_leaves = int(2.4 * area / (math.pi * r_mean ** 2 * 1.25))

    ys, xs = np.nonzero(m)
    leaves = []
    for _ in range(n_leaves):
        i = rng.randrange(len(xs))
        x, y = float(xs[i]), float(ys[i])
        u = (x - cx) / a
        v = (cy - y) / (b_top if y < cy else b_bot)
        rho = min(math.hypot(u, v), 1.0)
        leaves.append((rho, x, y, u, v))
    leaves.sort(key=lambda t: t[0])  # core first, rim last

    for rho, x, y, u, v in leaves:
        r = r_mean * rng.uniform(0.7, 1.3) * (1.0 - 0.25 * rho)
        ang = rng.uniform(0, math.pi)
        hf = 1.0 - (y - (cy - b_top)) / total_h if kind == "side" else 1 - rho
        if kind == "side":
            light = min(max(0.5 + 0.5 * (-0.45 * u + 0.75 * v), 0), 1)
            q = min(max(hf, 0) / 0.75, 1.0); ao_h = 0.30 + 0.70 * q * q * (3 - 2 * q)
        else:
            light = min(max(1.0 - 0.45 * rho - 0.15 * u, 0), 1)
            ao_h = 1.0
        t = (0.06 + 0.90 * light) * (0.55 + 0.45 * rho ** 0.7) * ao_h + rng.gauss(0, 0.06)
        base = ramp(t)
        pts = leaf_poly(rng, x, y, r, ang)
        d.polygon(shifted(pts, 0, 0.14 * r), fill=(*[int(c * 0.5) for c in base], 255))   # contact shadow
        d.polygon(pts, fill=(*[int(c) for c in base], 255))                                  # body
        d.polygon(shifted(pts, -0.18 * r, -0.22 * r, 0.6),
                  fill=(*[int(c) for c in ramp(t + 0.22)], 255))                            # highlight
        ca, sa = math.cos(ang), math.sin(ang)
        d.line([(x - 0.9 * r * 1.25 * ca, y - 0.9 * r * 1.25 * sa),
                (x + 0.9 * r * 1.25 * ca, y + 0.9 * r * 1.25 * sa)],
               fill=(*[int(c) for c in ramp(t - 0.15)], 255), width=max(1, int(0.07 * r)))   # vein

    img = img.resize((W, H), Image.LANCZOS)
    img = bleed_colors(img)
    bbox = np.array(img)[..., 3] > 127
    ys, xs = np.nonzero(bbox)
    return img, [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]


def main(out):
    os.makedirs(out, exist_ok=True)
    meta = {}
    for name, (W, H, aspect, seed) in SPECS.items():
        img, bb = paint(name, W, H, aspect, seed)
        img.save(os.path.join(out, name + ".png"))
        meta[name] = {"w": W, "h": H, "bbox": bb}
        print(name, (W, H), "bbox", bb, "aspect %.2f" % ((bb[2] - bb[0]) / (bb[3] - bb[1])))
    name, W, H = CAP
    img, bb = paint(name, W, H, 1.0, 5, kind="top")
    img.save(os.path.join(out, name + ".png"))
    meta[name] = {"w": W, "h": H, "bbox": bb}
    json.dump(meta, open(os.path.join(out, "meta.json"), "w"), indent=1)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else ".")
