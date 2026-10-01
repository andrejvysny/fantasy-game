"""Bank character fields (valley_habitats.json 'banks.field', plan 7E/7F/7J).

Every shore pixel (land pixel next to water) gets one soft character from a low-frequency noise
along the shore, biased by cues: outer bends (water outline convex) and steeper banks lean to
gravel / rock, inner bends and flat banks to sedge; steep or rock-exposed banks are rock. Values between the class bands stay
plain (open access). Inland water (rivers, lakes) uses all three; the sea coast only rock and
gravel (no sedge: plan 7J). Band pixels take the character of their nearest shore pixel.

Overlay fields only: the six habitats and their normalisation are untouched, so no tree moves.
"""
from __future__ import annotations

import math

import numpy as np
from scipy import ndimage as ndi
from scipy.special import erf

from common import RES, noise, smoothstep

CHARACTERS = ("gravel", "rock", "sedge")
LABELS = {"none": 0, "plain": 1, "gravel": 2, "rock": 3, "sedge": 4}
COAST_LABEL_OFFSET = 4  # coast labels: 5 plain, 6 gravel, 7 rock
NOISE_STD = 0.15  # common.noise: mean 0.5, std 0.15
FINE_SCALE = 0.3  # fine character noise scale relative to char_noise_m
CURV_SIGMA_M = 5.0
CURV_CLIP_M = 12.0
WATER_SIDE_M = (-2.5, -1.5)  # shallow edge kept in the band (reeds, shore boulders)


def _char_noise(cfg: dict, name: str = "bank_char") -> np.ndarray:
    """Broad + fine common.noise (normal-ish, mean 0.5, std 0.15 each) -> roughly uniform 0..1.
    The fine part lets the two banks of a narrow straight reach differ."""
    k = float(cfg["fine_mix"])
    n = (1.0 - k) * (noise(name, cfg["char_noise_m"]).astype(np.float64) - 0.5)
    n += k * (noise(name + "_fine", cfg["char_noise_m"] * FINE_SCALE).astype(np.float64) - 0.5)
    std = NOISE_STD * math.hypot(1.0 - k, k)
    return 0.5 * (1.0 + erf(n / (std * math.sqrt(2.0))))


def _curvature(isd: np.ndarray) -> np.ndarray:
    """Level-set curvature (1/m) of the smoothed inland distance: > 0 where the water outline is
    convex (outer bends, lake bays seen from the bank), < 0 where land juts into the water."""
    phi = ndi.gaussian_filter(np.clip(isd.astype(np.float64), -CURV_CLIP_M, CURV_CLIP_M), CURV_SIGMA_M)
    gz, gx = np.gradient(phi)
    mag = np.maximum(np.hypot(gx, gz), 1e-6)
    return np.gradient(gx / mag, axis=1) + np.gradient(gz / mag, axis=0)


def _along(values: np.ndarray, shore: np.ndarray, sigma: float) -> np.ndarray:
    """Average of values over nearby shore pixels (smooths a cue along the shoreline)."""
    w = shore.astype(np.float64)
    return ndi.gaussian_filter(values * w, sigma) / np.maximum(ndi.gaussian_filter(w, sigma), 1e-9)


def _band_mean(values: np.ndarray, band: np.ndarray, size: int) -> np.ndarray:
    w = band.astype(np.float64)
    return ndi.uniform_filter(values * w, size) / np.maximum(ndi.uniform_filter(w, size), 1e-9)


def _cues(t: dict, f: dict, cfg: dict, shore: np.ndarray) -> dict[str, np.ndarray]:
    """Per pixel character cues, meaningful on shore pixels."""
    width = float(cfg["width_m"])
    land_band = (f["shore_distance"] >= 0) & (f["shore_distance"] <= 0.8 * width)
    size = int(2 * width) | 1
    slope = _band_mean(f["slope_deg"], land_band, size)
    rocky = _band_mean(np.maximum(f["rocky_raw"], f["rock_exposure"]), land_band, size)
    bend = np.clip(_along(_curvature(f["inland_distance"]), shore, cfg["bend_along_m"]) * cfg["bend_ref_m"],
                   -1.0, 1.0)
    m0, m1 = cfg["slope_bias_deg"]
    steep = np.clip((slope - 0.5 * (m0 + m1)) / (0.5 * (m1 - m0)), -1.0, 1.0)
    c = _char_noise(cfg)
    c = c + float(cfg["bend_bias"]) * bend + float(cfg["slope_bias"]) * steep
    lo, hi = cfg["rock_slope_deg"]
    r0, r1 = cfg["rock_exposure"]
    rock_cue = np.maximum(smoothstep(lo, hi, slope), smoothstep(r0, r1, rocky))
    return {"c": c, "bend": bend, "slope": slope, "rock_cue": rock_cue}


def _classes(cfg: dict, cue: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    """Soft class weights 0..1 from the biased noise and the rock cue."""
    k = float(cfg["soft"])
    c = cue["c"]
    cls = cfg["classes"]
    sedge = 1.0 - smoothstep(cls["sedge"][1] - k, cls["sedge"][1] + k, c)
    g0, g1 = cls["gravel"]
    gravel = smoothstep(g0 - k, g0 + k, c) * (1.0 - smoothstep(g1 - k, g1 + k, c))
    rock = np.maximum(smoothstep(cls["rock"][0] - k, cls["rock"][0] + k, c), cue["rock_cue"])
    s0, s1 = cfg["sedge_max_slope_deg"]
    sedge = sedge * (1.0 - rock) * (1.0 - smoothstep(s0, s1, cue["slope"]))
    return {"gravel": gravel * (1.0 - rock), "rock": rock, "sedge": sedge}


def _shores(t: dict, f: dict, cfg: dict) -> tuple[np.ndarray, np.ndarray]:
    """(inland shore pixels, coast shore pixels): land pixels 4-adjacent to the water."""
    land = ~t["water"].astype(bool)
    inland = land & (f["inland_distance"] < 1.0)
    coast = land & (f["sea_distance"] < 1.5) & (f["inland_distance"] > float(cfg["width_m"]))
    return inland, coast


def _band(sd: np.ndarray, width: np.ndarray) -> np.ndarray:
    """1 from the shallow edge to 0.6 x width inland, 0 by width (width per pixel)."""
    u = np.clip((sd - 0.6 * width) / (0.4 * width), 0.0, 1.0)
    land = 1.0 - u * u * (3.0 - 2.0 * u)
    return (land * smoothstep(WATER_SIDE_M[0], WATER_SIDE_M[1], sd)).astype(np.float32)


def bank_fields(t: dict, f: dict, cfg: dict | None) -> None:
    """Adds bank_band, coast_band, bank_{gravel,rock,sedge}, coast_{gravel,rock}, bank_label (per shore
    pixel, LABELS; coast + COAST_LABEL_OFFSET) and bank_c (biased noise, debug) to f."""
    if not cfg:
        return
    inland, coast = _shores(t, f, cfg)
    shore = inland | coast
    cue = _cues(t, f, cfg, inland)
    cls = _classes(cfg, cue)
    cls_coast = _classes(cfg, {**cue, "c": cue["c"] - float(cfg["bend_bias"]) * cue["bend"]})
    cls_coast["sedge"] = np.zeros_like(cls_coast["sedge"])  # no reeds on the coast (plan 7J)
    _, (iz, ix) = ndi.distance_transform_edt(~shore, return_indices=True)
    near_coast = coast[iz, ix]
    width = np.where(near_coast, float(cfg["coast_width_m"]), float(cfg["width_m"]))
    band = _band(f["shore_distance"], width)
    f["bank_band"] = (band * ~near_coast).astype(np.float32)
    f["coast_band"] = (band * near_coast).astype(np.float32)
    for k in CHARACTERS:
        f["bank_" + k] = (cls[k][iz, ix] * band * ~near_coast).astype(np.float32)
    for k in ("gravel", "rock"):
        f["coast_" + k] = (cls_coast[k][iz, ix] * band * near_coast).astype(np.float32)
    f["bank_label"] = _labels(cls, cls_coast, inland, coast)
    f["bank_c"] = cue["c"].astype(np.float32)


def _labels(cls: dict, cls_coast: dict, inland: np.ndarray, coast: np.ndarray) -> np.ndarray:
    out = np.zeros((RES, RES), dtype=np.int8)
    for mask, w, off in ((inland, cls, 0), (coast, cls_coast, COAST_LABEL_OFFSET)):
        stack = np.stack([w[k] for k in CHARACTERS])
        best = np.argmax(stack, axis=0)
        lab = np.where(stack.max(axis=0) >= 0.5, best + LABELS["gravel"], LABELS["plain"]) + off
        out[mask] = lab[mask]
    return out


def bank_groundcover(gc: dict[str, np.ndarray], f: dict, cfg: dict | None) -> None:
    """Tall grass / sedge along sedge banks, thinner short grass on gravel banks (in place)."""
    if not cfg or "groundcover" not in cfg:
        return
    g = cfg["groundcover"]
    sd = f["shore_distance"]
    keep = smoothstep(0.0, 0.8, sd) * (1.0 - f["path_core"]) * (1.0 - 0.5 * f["path_shoulder"])
    lo, hi = g["tall_near_water"]
    amount = lo + (hi - lo) * _char_noise({"fine_mix": 0.5, "char_noise_m": float(g["tall_patch_m"])}, "bank_tall")
    f0, f1 = g["tall_falloff_m"]
    tall = f["bank_sedge"] * amount * (1.0 - smoothstep(f0, f1, sd)) * keep
    if "grass_tall" in gc:
        gc["grass_tall"] = np.maximum(gc["grass_tall"], tall).astype(np.float32)
    gravel = _gravel(f, g)
    if "grass_short" in gc:
        gc["grass_short"] = (gc["grass_short"] * (1.0 - float(g["short_on_gravel_cut"]) * gravel)).astype(np.float32)


def _gravel(f: dict, g: dict) -> np.ndarray:
    """Exposed soil / gravel strength 0..1: gravel banks, strongest at the water line."""
    f0, f1 = g["gravel_falloff_m"]
    near = 1.0 - smoothstep(f0, f1, f["shore_distance"])
    return np.clip((f["bank_gravel"] + f["coast_gravel"]) * near, 0.0, 1.0)


def bank_image(f: dict, cfg: dict | None) -> np.ndarray | None:
    """RGBA for out/fields/bank.png: r gravel (exposed soil/gravel), g rock character, b sedge
    character, a bank band (inland + coast). None without a 'banks' section."""
    if not cfg or "bank_gravel" not in f:
        return None
    g = cfg.get("groundcover", {"gravel_falloff_m": [2.0, 5.0]})
    rock = np.clip(f["bank_rock"] + f["coast_rock"], 0.0, 1.0)
    band = np.clip(f["bank_band"] + f["coast_band"], 0.0, 1.0)
    rgba = np.dstack([_gravel(f, g), rock, f["bank_sedge"], band])
    return np.clip(np.rint(rgba * 255.0), 0, 255).astype(np.uint8)

