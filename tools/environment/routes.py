"""Visual routes (world/routes/valley_routes.json): exact point queries and 1 m rasters.

Core half width = core_width / 2 * (1 + width_jitter * n(along)), n a smooth 1-D noise in
-1..1; both margins are broken by ~1.5 m 2-D noise. Edges are signed distances (m),
negative inside, so footprint tests are `edge < radius`.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from scipy import ndimage as ndi

from common import RES, bilinear, noise, px_centres, segment_distance, smoothstep, str_hash

MARGIN_NOISE_M = 1.5
TURN_WINDOW_M = 8.0  # bend angle measured over this length (heading at +-4 m)
TURN_BEND_DEG = 25.0
TURN_BAND_M = (1.5, 3.5)  # stones band outside the core edge, outer side of bends
MARGIN_AMPLITUDE_M = 0.3  # per noise sigma
FAR = 1.0e4


@dataclass
class Route:
    rid: str
    pts: np.ndarray  # (n, 2) world x, z
    core_width: float
    width_jitter: float
    shoulder: float
    clearance_height: float
    cum: np.ndarray  # cumulative length at each point
    jitter: np.ndarray  # 1-D noise per metre along the route, -1..1
    bend: np.ndarray  # signed bend angle (deg) per metre along the route
    stones_on_turns: bool
    roots: bool

    @staticmethod
    def from_json(r: dict) -> "Route":
        pts = np.asarray(r["points"], dtype=np.float64)
        seg = np.hypot(*np.diff(pts, axis=0).T)
        cum = np.concatenate([[0.0], np.cumsum(seg)])
        rng = np.random.default_rng(str_hash("route_width:" + r["id"]))
        n = ndi.gaussian_filter1d(rng.standard_normal(int(cum[-1]) + 16), 4.0, mode="nearest")
        n = np.clip(n / max(n.std(), 1e-9) * 0.5, -1.0, 1.0)
        return Route(r["id"], pts, float(r["core_width"]), float(r.get("width_jitter", 0.0)),
                     float(r["shoulder"]), float(r.get("clearance_height", 2.5)), cum, n,
                     _bends(pts, cum), bool(r.get("stones_on_turns", False)), bool(r.get("roots", False)))

    def metric(self, x: np.ndarray, z: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """Distance to the polyline, distance along it at the closest point, and side
        (+1 right / -1 left of the walking direction)."""
        best = np.full(np.shape(x), FAR)
        along = np.zeros(np.shape(x))
        side = np.ones(np.shape(x))
        for i in range(len(self.pts) - 1):
            a, b = self.pts[i], self.pts[i + 1]
            d, t = segment_distance(x, z, tuple(a), tuple(b))
            closer = d < best
            best = np.where(closer, d, best)
            along = np.where(closer, self.cum[i] + t * (self.cum[i + 1] - self.cum[i]), along)
            cross = (b[0] - a[0]) * (z - a[1]) - (b[1] - a[1]) * (x - a[0])
            side = np.where(closer, np.where(cross >= 0, 1.0, -1.0), side)
        return best, along, side

    def bend_at(self, along: np.ndarray) -> np.ndarray:
        return np.interp(along, np.arange(len(self.bend), dtype=np.float64), self.bend)

    def turns(self) -> list[dict]:
        """Contiguous stretches with |bend| > TURN_BEND_DEG and their outer side."""
        out, start = [], None
        hot = np.abs(self.bend) > TURN_BEND_DEG
        for k in range(len(hot) + 1):
            on = k < len(hot) and hot[k]
            if on and start is None:
                start = k
            elif not on and start is not None:
                mid = self.bend[start:k]
                out.append({"from_m": start, "to_m": k - 1, "max_bend_deg": round(float(np.abs(mid).max()), 1),
                            "outer_side": "right" if mid.mean() < 0 else "left"})
                start = None
        return out

    def half_core(self, along: np.ndarray) -> np.ndarray:
        j = np.interp(along, np.arange(len(self.jitter), dtype=np.float64), self.jitter)
        return self.core_width * 0.5 * (1.0 + self.width_jitter * j)


class Routes:
    def __init__(self, data: dict) -> None:
        self.routes = [Route.from_json(r) for r in data.get("routes", [])]
        self.core_noise = noise("route_core_margin", MARGIN_NOISE_M)
        self.shoulder_noise = noise("route_shoulder_margin", MARGIN_NOISE_M)

    def by_id(self, rid: str) -> Route | None:
        return next((r for r in self.routes if r.rid == rid), None)

    def edges(self, x: np.ndarray, z: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
        """(core edge, shoulder edge, clearance height) at points; edges < 0 = inside."""
        x = np.asarray(x, dtype=np.float64)
        z = np.asarray(z, dtype=np.float64)
        core = np.full(x.shape, FAR)
        shoulder = np.full(x.shape, FAR)
        clear = np.zeros(x.shape)
        if not self.routes:
            return core, shoulder, clear
        mc = (bilinear(self.core_noise, x, z) - 0.5) / 0.15 * MARGIN_AMPLITUDE_M
        ms = (bilinear(self.shoulder_noise, x, z) - 0.5) / 0.15 * MARGIN_AMPLITUDE_M
        for r in self.routes:
            d, along, _ = r.metric(x, z)
            hc = r.half_core(along)
            ce = d - hc - mc
            se = d - hc - r.shoulder - ms
            clear = np.where(se < shoulder, r.clearance_height, clear)
            core = np.minimum(core, ce)
            shoulder = np.minimum(shoulder, se)
        return core, shoulder, clear

    def rasters(self) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
        """1 m rasters: path_core, path_shoulder (0..1), core edge and shoulder edge (m)."""
        core_e = np.full((RES, RES), FAR, dtype=np.float32)
        sh_e = np.full((RES, RES), FAR, dtype=np.float32)
        wx, wz = px_centres()
        for r in self.routes:
            pad = r.core_width + r.shoulder + 4.0
            lo, hi = r.pts.min(axis=0) - pad, r.pts.max(axis=0) + pad
            box = (wx >= lo[0]) & (wx <= hi[0]) & (wz >= lo[1]) & (wz <= hi[1])
            c, s, _ = self.edges(wx[box], wz[box])
            core_e[box] = np.minimum(core_e[box], c)
            sh_e[box] = np.minimum(sh_e[box], s)
        core = 1.0 - smoothstep(-0.3, 0.3, core_e)
        self.turn_stones = self._turn_band(wx, wz)
        shoulder = (1.0 - smoothstep(-0.5, 0.5, sh_e)) * (1.0 - core)
        return core.astype(np.float32), shoulder.astype(np.float32), core_e, sh_e

    def _turn_band(self, wx: np.ndarray, wz: np.ndarray) -> np.ndarray:
        """0..1 band TURN_BAND_M outside the core edge on the outer side of sharp bends."""
        band = np.zeros((RES, RES), dtype=np.float32)
        for r in self.routes:
            if not r.stones_on_turns:
                continue
            pad = r.core_width + TURN_BAND_M[1] + 4.0
            lo, hi = r.pts.min(axis=0) - pad, r.pts.max(axis=0) + pad
            box = (wx >= lo[0]) & (wx <= hi[0]) & (wz >= lo[1]) & (wz <= hi[1])
            x, z = wx[box], wz[box]
            d, along, side = r.metric(x, z)
            mc = (bilinear(self.core_noise, x, z) - 0.5) / 0.15 * MARGIN_AMPLITUDE_M
            ce = d - r.half_core(along) - mc
            b0, b1 = TURN_BAND_M
            w = smoothstep(b0 - 0.3, b0, ce) * (1.0 - smoothstep(b1, b1 + 0.3, ce))
            bend = r.bend_at(along)
            w *= smoothstep(TURN_BEND_DEG - 5.0, TURN_BEND_DEG + 5.0, np.abs(bend))
            w *= (side * np.sign(bend)) < 0  # outer side: opposite to the turning direction
            band[box] = np.maximum(band[box], w)
        return band


def _bends(pts: np.ndarray, cum: np.ndarray) -> np.ndarray:
    """Signed heading change (deg) over TURN_WINDOW_M, sampled every metre along the route.

    Positive = turning toward the walker's right (+cross side)."""
    s = np.arange(0.0, cum[-1] + 1.0)
    d = pts[1:] - pts[:-1]
    heading = np.arctan2(d[:, 1], d[:, 0])
    half = TURN_WINDOW_M * 0.5

    def head(v: np.ndarray) -> np.ndarray:
        return heading[np.clip(np.searchsorted(cum, np.clip(v, 0, cum[-1]), side="right") - 1, 0, len(pts) - 2)]

    return np.degrees(np.angle(np.exp(1j * (head(s + half) - head(s - half)))))
