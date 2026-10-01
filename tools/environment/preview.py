"""Debug previews: a 1 px/m map composite and 4 px/m zoom crops of the spawn slice."""
from __future__ import annotations

from typing import TYPE_CHECKING

import math
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from common import HALF
from spatial import Box

if TYPE_CHECKING:
    from generate import Result

HAB_COLOURS = {"mature_forest": (24, 72, 34), "forest_edge": (92, 150, 62), "open_meadow": (196, 214, 112),
               "rocky_slope": (150, 142, 132), "sheltered_bank": (214, 110, 196), "exposed": (232, 196, 150)}
SPAWN_SLICE = (-110.0, 0.0, -215.0, -118.0)  # x0, x1, z0, z1
ZOOM = 4
CANYON_SLICE = (250.0, 420.0, -420.0, -150.0)
CANYON_ZOOM = 2
WEST_RIVER_SLICE = (-330.0, -150.0, -80.0, 90.0)
BANK_COLOURS = {"bank_gravel": (226, 196, 120), "bank_rock": (120, 116, 112), "bank_sedge": (40, 170, 90),
                "coast_gravel": (240, 222, 170), "coast_rock": (96, 96, 108)}


def _habitat_rgb(res: Result) -> np.ndarray:
    f = res.fields
    img = np.zeros(f["mature_forest"].shape + (3,))
    for k, c in HAB_COLOURS.items():
        img += f[k][..., None] * np.array(c, dtype=np.float64)
    img[res.terrain["water"]] = (46, 86, 140)
    for k, c in (("path_shoulder", (170, 140, 90)), ("path_core", (120, 80, 40))):
        a = f[k][..., None]
        img = img * (1 - a) + np.array(c) * a
    return np.clip(img, 0, 255).astype(np.uint8)


def _ground_rgb(res: Result) -> np.ndarray:
    g = res.groundcover
    z = np.zeros_like(res.fields["wear"])
    base = np.dstack([z + 40, 60 + 150 * g.get("grass_short", z), z + 40]).astype(np.float64)
    tall = g.get("grass_tall", z)[..., None]
    base = base * (1 - tall) + np.array((30, 110, 70)) * tall
    for n, c in (("flower_white", (250, 250, 245)), ("flower_pink", (240, 120, 180)),
                 ("flower_yellow", (250, 220, 60)), ("flower_blue", (90, 120, 250)), ("fern", (20, 160, 150))):
        a = np.clip(g.get(n, z) * 1.5, 0, 1)[..., None]
        base = base * (1 - a) + np.array(c) * a
    w = res.fields["wear"][..., None]
    base = base * (1 - w) + np.array((150, 110, 70)) * w
    base[res.terrain["water"]] = (46, 86, 140)
    return np.clip(base, 0, 255).astype(np.uint8)


def _slope_rgb(res: Result) -> np.ndarray:
    """Grey slope shading (darker = steeper) with the terrain cliff mask / dressing mask in red."""
    sl = np.clip(res.fields["slope_deg"] / 60.0, 0, 1)[..., None]
    img = (1.0 - 0.75 * sl) * np.array((225.0, 225.0, 215.0))
    cfg = res.inputs.habitats.get("cliff_dressing") or {}
    mask = (res.terrain["cliff"] > 0.3) | (res.fields["slope_deg"] > float(cfg.get("min_slope_deg", 90.0)))
    img[mask] = img[mask] * 0.5 + np.array((200.0, 40.0, 40.0)) * 0.5
    img[res.terrain["water"]] = (46, 86, 140)
    return np.clip(img, 0, 255).astype(np.uint8)


def _bank_rgb(res: Result) -> np.ndarray:
    """Bank characters over slope shading; plain (open access) shore pixels magenta."""
    f = res.fields
    sl = np.clip(f["slope_deg"] / 50.0, 0, 1)[..., None]
    img = (1.0 - 0.6 * sl) * np.array((150.0, 170.0, 120.0))
    for k, c in BANK_COLOURS.items():
        if k in f:
            a = f[k][..., None]
            img = img * (1 - a) + np.array(c, dtype=np.float64) * a
    img[res.terrain["water"]] = (46, 86, 140)
    if "bank_label" in f:
        img[(f["bank_label"] == 1) | (f["bank_label"] == 5)] = (255, 60, 200)
    return np.clip(img, 0, 255).astype(np.uint8)


def _px(x: float, z: float, x0: float, z0: float, k: float) -> tuple[float, float]:
    return (x - x0) * k, (z - z0) * k


def _draw(img: Image.Image, res: Result, x0: float, z0: float, k: float, detail: bool) -> None:
    d = ImageDraw.Draw(img)
    assets = res.inputs.assets
    for a, b, w in res.excl.corridors:
        for side in (-1, 1):
            ang = math.atan2(b[1] - a[1], b[0] - a[0]) + side * math.pi / 2
            ox, oz = math.cos(ang) * w / 2, math.sin(ang) * w / 2
            d.line([_px(a[0] + ox, a[1] + oz, x0, z0, k), _px(b[0] + ox, b[1] + oz, x0, z0, k)], fill=(255, 255, 0))
    for sx, sz, r in res.excl.spawns:
        cx, cz = _px(sx, sz, x0, z0, k)
        d.ellipse([cx - r * k, cz - r * k, cx + r * k, cz + r * k], outline=(255, 255, 255))
    for i in sorted(res.instances, key=lambda i: assets[i.asset].is_tree):
        a = assets[i.asset]
        cx, cz = _px(i.x, i.z, x0, z0, k)
        if a.is_tree:
            col = (10, 40, 20) if not i.locked else (255, 40, 40)
            if detail:
                r = a.radius * i.scale * k
                d.ellipse([cx - r, cz - r, cx + r, cz + r], outline=col)
            d.ellipse([cx - 1.5, cz - 1.5, cx + 1.5, cz + 1.5], fill=col)
        elif detail or a.is_rock:
            box = Box.of(a, i.x, i.z, i.yaw, i.scale)
            corners = [(box.x0, box.z0), (box.x1, box.z0), (box.x1, box.z1), (box.x0, box.z1)]
            c, s = math.cos(i.yaw), math.sin(i.yaw)
            pts = [_px(i.x + lx * c + lz * s, i.z - lx * s + lz * c, x0, z0, k) for lx, lz in corners]
            col = (255, 40, 40) if i.locked else ((120, 120, 120) if a.is_rock else (60, 200, 90))
            if i.source.startswith("cliffs."):
                col = (255, 140, 0) if i.source == "cliffs.face" else (0, 200, 255)
            elif i.source.startswith("banks."):
                col = (255, 255, 255) if a.is_rock else ((200, 255, 0) if a.family == "reed" else (0, 255, 255))
            d.polygon(pts, outline=col)
            if a.is_rock and detail:  # +z front arrow
                arrow = max(1.5, 8.0 / k)
                fx, fz = _px(i.x + s * arrow, i.z + c * arrow, x0, z0, k)
                d.line([(cx, cz), (fx, fz)], fill=col, width=2)


def write_previews(res: Result, out: Path) -> list[Path]:
    out.mkdir(parents=True, exist_ok=True)
    paths = []
    base = Image.fromarray(_habitat_rgb(res))
    _draw(base, res, -HALF - 0.5, -HALF - 0.5, 1.0, False)
    paths.append(out / "fields_preview.png")
    base.save(paths[-1])
    crops = [("fields_zoom_spawn.png", SPAWN_SLICE, ZOOM, _habitat_rgb(res)),
             ("fields_zoom_spawn_ground.png", SPAWN_SLICE, ZOOM, _ground_rgb(res)),
             ("fields_zoom_ne_canyon.png", CANYON_SLICE, CANYON_ZOOM, _slope_rgb(res)),
             ("fields_zoom_west_river_banks.png", WEST_RIVER_SLICE, ZOOM, _bank_rgb(res))]
    for name, (x0, x1, z0, z1), zoom, rgb in crops:
        box = (int(x0 + HALF), int(z0 + HALF), int(x1 + HALF), int(z1 + HALF))
        size = (int((x1 - x0) * zoom), int((z1 - z0) * zoom))
        crop = Image.fromarray(rgb).crop(box).resize(size, Image.BILINEAR)
        _draw(crop, res, box[0] - HALF - 0.5, box[1] - HALF - 0.5, zoom, True)
        paths.append(out / name)
        crop.save(paths[-1])
    return paths
