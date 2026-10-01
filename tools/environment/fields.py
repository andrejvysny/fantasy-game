"""1 m data fields for placement (plan 8.1), all float32 RES x RES in world metres, row 0 north.

Habitats are soft weights summing to <= 1 (valley_habitats.json 'habitat_field'). Wetness and
shore classes are authored bands around inland water, not a hydrology simulation.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import numpy as np
from PIL import Image
from scipy import ndimage as ndi
from scipy.signal import fftconvolve

from common import TERRAIN_OUT, load_json, noise, smoothstep

if TYPE_CHECKING:
    from routes import Routes

HABITATS = ["mature_forest", "forest_edge", "open_meadow", "rocky_slope", "sheltered_bank", "exposed"]
SHELTER_RADIUS_M = 12.0
SHELTER_SHARE = 0.35
COVE_RADIUS_M = 20.0
COVE_LAND_SHARE = 0.78  # rivers: median 0.73, so only narrows, tight bends and lake inlets count
WET_BAND_M = 4.0
PAINTED_PATH_WATER_M = 3.0
# Painted-map dirt wider than this (half width, m) is a bare patch, not a trail: it only gets
# light trampling so the valley does not show broad brown swaths (plan finding 09).
PAINTED_PATH_MAX_HALF_WIDTH_M = 2.5
PAINTED_PATCH_WEAR = 0.3

Fields = dict[str, np.ndarray]


def load_terrain() -> Fields:
    """Protected terrain: heights (m), water masks and the 9 splat layer weights."""
    t: Fields = {"height": np.load(TERRAIN_OUT / "heightmap.npy").astype(np.float32)}
    masks = np.load(TERRAIN_OUT / "terrain_masks.npz")
    for k in ("water", "sea", "lake", "cliff", "level"):
        t[k] = masks[k]
    names = [layer["name"] for layer in load_json(TERRAIN_OUT / "splat.json")["layers"]]
    chans = [np.asarray(Image.open(TERRAIN_OUT / f"splat_{i}.png").convert("RGB"), np.float32) / 255.0
             for i in range(3)]
    stack = np.concatenate(chans, axis=2)
    for i, n in enumerate(names):
        t["splat_" + n] = stack[:, :, i]
    return t


def _signed(mask: np.ndarray) -> np.ndarray:
    """Signed distance (m) to a mask boundary: positive outside the mask, negative inside."""
    outside = ndi.distance_transform_edt(~mask)
    inside = ndi.distance_transform_edt(mask)
    return np.where(mask, -(inside - 0.5), outside - 0.5).astype(np.float32)


def _disc_share(mask: np.ndarray, radius: float) -> np.ndarray:
    r = int(np.ceil(radius))
    g = np.arange(-r, r + 1)
    k = (np.hypot(*np.meshgrid(g, g)) <= radius).astype(np.float64)
    share = fftconvolve(mask.astype(np.float64), k / k.sum(), mode="same")
    return np.clip(share, 0.0, 1.0)


def _terrain_shape(t: Fields, f: Fields) -> None:
    hs = ndi.gaussian_filter(t["height"].astype(np.float64), 1.0)
    gz, gx = np.gradient(hs)
    f["grad_x"], f["grad_z"] = gx.astype(np.float32), gz.astype(np.float32)
    f["slope_deg"] = np.degrees(np.arctan(np.hypot(gx, gz))).astype(np.float32)


def _water(t: Fields, f: Fields) -> None:
    water = t["water"].astype(bool)
    inland = water & ~t["sea"].astype(bool)
    f["shore_distance"] = _signed(water)
    f["inland_distance"] = _signed(inland)
    f["sea_distance"] = ndi.distance_transform_edt(~t["sea"].astype(bool)).astype(np.float32)
    share = _disc_share(inland, SHELTER_RADIUS_M)
    land_share = 1.0 - _disc_share(water, COVE_RADIUS_M)
    cove_water = inland & (land_share > COVE_LAND_SHARE)
    cove_d = ndi.distance_transform_edt(~cove_water)
    sheltered = np.maximum(smoothstep(SHELTER_SHARE - 0.05, SHELTER_SHARE + 0.05, share),
                           1.0 - smoothstep(4.0, 8.0, cove_d))
    f["sheltered"] = sheltered.astype(np.float32)
    f["wetness"] = (1.0 - smoothstep(0.0, WET_BAND_M, f["inland_distance"])).astype(np.float32)


def _forest(t: Fields, f: Fields, cfg: dict) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    ff = ndi.gaussian_filter(t["splat_forest_floor"], cfg["forest_blur_m"])
    thr = cfg["clearing_threshold"]
    clearing = smoothstep(thr - 0.04, thr + 0.04, noise("clearing", cfg["clearing_noise_m"]))
    clearing *= smoothstep(0.35, 0.6, ff)
    forest_eff = ff * (1.0 - clearing)
    sdf = -_signed(forest_eff > 0.5)  # positive inside
    lo, hi = cfg["edge_band_m"]
    deep = max(2.0 * cfg["mature_depth_m"] - hi, hi + 2.0)
    mature = smoothstep(hi, deep, sdf)
    edge = smoothstep(lo - 2.0, lo + 2.0, sdf) * (1.0 - mature)
    f["forest"] = ff.astype(np.float32)
    f["forest_sdf"] = sdf
    f["clearing"] = clearing.astype(np.float32)
    return mature, edge, clearing


def _habitats(t: Fields, f: Fields, cfg: dict) -> None:
    mature, edge, clearing = _forest(t, f, cfg)
    grass = t["splat_grass"] + t["splat_grass_dry"]
    meadow = np.clip(grass + clearing * f["forest"], 0, 1) * np.clip(1.0 - edge - mature, 0, 1)
    rd = cfg["rocky_slope_deg"]
    rocky = np.maximum(np.clip(t["splat_rock"] + t["splat_scree"], 0, 1),
                       smoothstep(rd - 4.0, rd + 4.0, f["slope_deg"]))
    isd = f["inland_distance"]
    b_lo, b_hi = cfg["bank_distance_m"]
    band = smoothstep(b_lo - 3.0, b_lo - 1.5, isd) * (1.0 - smoothstep(b_hi - 2.0, b_hi + 1.0, isd))
    bank = band * f["sheltered"]
    land = ~t["water"].astype(bool)
    h = t["height"]
    p = float(np.percentile(h[land & (h > 0.8)], cfg["exposed_height_percentile"]))
    ds = cfg["exposed_sea_distance_m"]
    exp_sea = 1.0 - smoothstep(0.7 * ds, ds, f["sea_distance"])
    exposed = np.maximum(smoothstep(p - 3.0, p + 3.0, h), exp_sea)
    on_land = smoothstep(-0.5, 0.5, f["shore_distance"])
    raw = [mature * on_land, edge * on_land, meadow * on_land, rocky * on_land, bank, exposed * on_land]
    total = np.sum(raw, axis=0)
    norm = np.where(total > 1.0, 1.0 / np.maximum(total, 1e-9), 1.0)
    for name, w in zip(HABITATS, raw):
        f[name] = (w * norm).astype(np.float32)
    f["exposed_shore"] = (exp_sea * (1.0 - smoothstep(3.0, 6.0, f["shore_distance"]))).astype(np.float32)
    f["exposed_height_m"] = np.float32(p)
    f["meadow_rock"] = _meadow_rock(t, f, cfg.get("meadow_rock")) * on_land
    f["rocky_raw"] = rocky.astype(np.float32)


def _meadow_rock(t: Fields, f: Fields, cfg: dict | None) -> np.ndarray:
    """Moderate slopes near rock/scree exposure. An overlay weight: it is not part of the
    six-habitat normalisation, so adding it moves no tree."""
    if not cfg:
        return np.zeros(f["slope_deg"].shape, dtype=np.float32)
    lo, hi = cfg["slope_deg"]
    band = smoothstep(lo - 3.0, lo + 3.0, f["slope_deg"]) * (1.0 - smoothstep(hi - 3.0, hi + 3.0, f["slope_deg"]))
    rockish = (t["splat_rock"] + t["splat_scree"]) > 0.5
    d = float(cfg["rock_distance_m"])
    near = 1.0 - smoothstep(0.6 * d, d, ndi.distance_transform_edt(~rockish))
    return (band * near).astype(np.float32)


def _rock(t: Fields, f: Fields, cfg: dict) -> None:
    rd = cfg["rocky_slope_deg"]
    exp = np.clip(t["splat_rock"] + 0.6 * t["splat_scree"] + smoothstep(rd - 6.0, rd + 6.0, f["slope_deg"]),
                  0, 1)
    f["rock_exposure"] = np.maximum(exp, np.clip(t["cliff"], 0, 1)).astype(np.float32)
    rockm = f["rocky_raw"] > 0.5
    dist = ndi.distance_transform_edt(~rockm)
    h = t["height"].astype(np.float64)
    wsum = ndi.gaussian_filter(rockm.astype(np.float64), 4.0)
    rock_h = ndi.gaussian_filter(h * rockm, 4.0) / np.maximum(wsum, 1e-6)
    below = smoothstep(0.0, 0.6, rock_h - h) * (wsum > 0.02)
    foot = (1.0 - smoothstep(2.5, 5.0, dist)) * (dist > 0) * (1.0 - f["rocky_raw"]) * below
    f["rock_foot"] = (foot * smoothstep(-0.5, 0.5, f["shore_distance"])).astype(np.float32)


def _painted_paths(t: Fields, f: Fields) -> None:
    dirt = (t["splat_dirt"] > 0.5) & (f["shore_distance"] > PAINTED_PATH_WATER_M)
    core = ndi.distance_transform_edt(dirt) > PAINTED_PATH_MAX_HALF_WIDTH_M
    wide = dirt & (ndi.distance_transform_edt(~core) <= PAINTED_PATH_MAX_HALF_WIDTH_M + 0.5)
    narrow = dirt & ~wide
    f["painted_path"] = np.clip(ndi.gaussian_filter(narrow.astype(np.float32), 0.7) * 1.4, 0, 1)
    f["painted_patch"] = np.clip(ndi.gaussian_filter(wide.astype(np.float32), 1.5), 0, 1).astype(np.float32)


def compute_fields(t: Fields, habitat_cfg: dict, routes: Routes) -> Fields:
    """All placement fields."""
    f: Fields = {}
    _terrain_shape(t, f)
    _water(t, f)
    _habitats(t, f, habitat_cfg)
    _rock(t, f, habitat_cfg)
    _painted_paths(t, f)
    core, shoulder, core_e, sh_e = routes.rasters()
    f["path_core"], f["path_shoulder"] = core, shoulder
    f["core_edge"], f["shoulder_edge"] = core_e, sh_e
    f["turn_stones"] = routes.turn_stones
    wear = np.maximum.reduce([np.clip(core + 0.5 * shoulder, 0, 1), 0.6 * f["painted_path"],
                              PAINTED_PATCH_WEAR * f["painted_patch"]])
    f["wear"] = wear.astype(np.float32)
    return f
