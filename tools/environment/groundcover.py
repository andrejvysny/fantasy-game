"""Groundcover density fields 0..1 (valley_habitats.json 'fields', plan 8.2 step 5) and the
RGBA8 field images consumed by the runtime (tools/environment/export_fields.gd).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PIL import Image

from common import RES, disc_stamp, noise, smoothstep
from fields import HABITATS

FLOWERS = ["flower_white", "flower_pink", "flower_yellow", "flower_blue"]
FLOWER_SEPARATION_POW = 4.0


def _field(name: str, rule: dict, f: dict) -> np.ndarray:
    d = np.zeros((RES, RES))
    for key, v in rule.items():
        if key in HABITATS or key == "rock_foot":
            d += f[key] * float(v)
    if "patch_m" in rule:
        thr = float(rule.get("patch_threshold", 0.5))
        d *= smoothstep(thr - 0.05, thr + 0.05, noise("field_patch:" + name, rule["patch_m"]))
    d *= 1.0 - f["path_core"] * (1.0 - float(rule.get("path_core", 0.0)))
    d *= 1.0 - f["path_shoulder"] * (1.0 - float(rule.get("path_shoulder", 1.0)))
    if "max_slope_deg" in rule:
        ms = float(rule["max_slope_deg"])
        d *= 1.0 - smoothstep(ms - 4.0, ms + 2.0, f["slope_deg"])
    d *= smoothstep(0.0, 0.8, f["shore_distance"])
    d *= 1.0 - f["rock_exposure"]
    return d


def _stamp(d: np.ndarray, name: str, patches: list[dict], f: dict) -> np.ndarray:
    s = np.zeros((RES, RES))
    for p in patches:
        if p["field"] == name:
            disc_stamp(s, p["at"][0], p["at"][1], float(p["radius"]), float(p["strength"]), mode="max")
    d = d + s * (1.0 - f["path_core"]) * smoothstep(0.0, 0.8, f["shore_distance"])
    return np.clip(d, 0.0, 1.0)


def groundcover(rules: dict, f: dict, patches: list[dict], fern_density: np.ndarray | None,
                fern_peak: float) -> dict[str, np.ndarray]:
    out = {name: _field(name, rule, f) for name, rule in rules.items()}
    flowers = [n for n in FLOWERS if n in out]
    if len(flowers) > 1:
        # Keep the colours in separate drifts: the locally dominant colour suppresses the others.
        top = np.maximum.reduce([out[n] for n in flowers])
        for n in flowers:
            out[n] = out[n] * (out[n] / np.maximum(top, 1e-6)) ** FLOWER_SEPARATION_POW
    names = set(out) | {p["field"] for p in patches}
    res = {n: _stamp(out.get(n, np.zeros((RES, RES))), n, patches, f).astype(np.float32) for n in sorted(names)}
    if fern_density is not None:  # the fern prop density already carries its recipe patches
        res["fern"] = np.clip(fern_density / max(fern_peak, 1e-6), 0.0, 1.0).astype(np.float32)
    return res


def _u8(a: np.ndarray) -> np.ndarray:
    return np.clip(np.rint(np.asarray(a, dtype=np.float64) * 255.0), 0, 255).astype(np.uint8)


def field_images(gc: dict[str, np.ndarray], f: dict, canopy: np.ndarray) -> dict[str, np.ndarray]:
    z = np.zeros((RES, RES), dtype=np.float32)
    g = lambda n: gc.get(n, z)  # noqa: E731
    forest = np.clip(f["mature_forest"] + 0.5 * f["forest_edge"], 0, 1)
    return {
        "ground": np.dstack([_u8(g("grass_short")), _u8(g("grass_tall")), _u8(f["wear"]), _u8(canopy / 1.5)]),
        "flowers": np.dstack([_u8(g(n)) for n in FLOWERS]),
        "habitat": np.dstack([_u8(forest), _u8(f["rock_exposure"]), _u8(f["wetness"]), _u8(g("fern"))]),
    }


def write_field_pngs(images: dict[str, np.ndarray], dest: Path) -> dict[str, Path]:
    dest.mkdir(parents=True, exist_ok=True)
    paths = {}
    for name, arr in images.items():
        p = dest / f"{name}.png"
        Image.fromarray(arr, "RGBA").save(p, optimize=False, compress_level=6)
        paths[name] = p
    return paths
