"""Spruce crown planning: where every bough starts, points and how far it reaches. Mixed into spruce_gen.Tree."""
from __future__ import annotations

import math

from spruce_math import clamp, lerp, smoothstep


class PlanMixin:
    def profile(self, f: float) -> float:
        """Reach relative to the longest bough at crown fraction f (0 = lowest tier root, 1 = last tier)."""
        pk, b = self.P["peak_frac"], self.P["base_reach"]
        if f < pk:
            return lerp(b, 1.0, smoothstep(0.0, 1.0, f / pk))
        return max(0.0, 1.0 - (f - pk) / (1.0 - pk)) ** self.P["top_taper"]

    def gap_factor(self, az: float, f: float) -> float:
        """0 (or gap_soft) inside a missing-growth gap, a reduced factor for boughs flanking it, else 1."""
        P = self.P
        for c, w, lo, hi in P["gaps"]:
            if lo <= f <= hi:
                off = abs((az - c + 180.0) % 360.0 - 180.0) - w * 0.5
                if off < 0.0:
                    return P.get("gap_soft", 0.0)   # soft gap: shortened boughs instead of none
                if off < P["gap_edge"]:
                    return P["gap_edge_reach"]
        return 1.0

    def plan_tier(self, z: float, az0: float, tier_i: int, r) -> tuple[list[dict], float]:
        """Boughs of one tier plus the spacing to the next. Lower tiers stay long and even; variation grows upward."""
        P = self.P
        a_amp, a_az = P["asym"]
        c_amp, c_m = P["cluster"]
        f = clamp((z - self.zb) / (self.z_top - self.zb))
        n = max(3, round(lerp(*P["tier_count"], f)) + r.choice((-2, -1, 0, 0, 1)))
        spacing = lerp(*P["tier_spacing"], f) * r.uniform(*P.get("spacing_jit", (0.72, 1.4)))
        zj = P["z_jitter"] * clamp(spacing / 0.9, 0.6, 1.0)
        hem = P.get("hem_jitter", 0.0) if tier_i < 2 else 0.0   # ragged lower edge: lowest two tiers may root below zb
        zj, floor = max(zj, hem), self.zb - hem
        var = smoothstep(0.0, 0.5, f)
        tier = r.uniform(0.9, 1.08) * (0.78 if (f > 0.25 and r.random() < 0.2) else 1.0)   # occasional short tier
        if P.get("tier_amp", 0.0):   # adjacent tiers differ in reach (own stream: main draws stay unchanged)
            tier *= 1.0 + P["tier_amp"] * (2.0 * self.sub_rng(3, tier_i).random() - 1.0)
        step, tier_az = 360.0 / n, az0 + r.uniform(-25.0, 25.0)
        mains = [(max(z + r.uniform(-zj, zj), floor), tier_az + k * step + r.uniform(-0.4, 0.4) * step,
                  tier * r.uniform(lerp(0.80, 0.66, var), lerp(1.08, 1.18, var)), "main") for k in range(n)]
        extra = [(z + spacing * r.uniform(0.35, 0.65), r.uniform(0.0, 360.0), r.uniform(*P.get("inter_reach", (0.5, 0.72))), "inter")
                 for _ in range(r.choice(P.get("inter_choices", (1, 2, 2, 3))))]
        specs = []
        for zz, az, k, kind in mains + extra:
            gn = math.sin(math.radians(c_m * az) + self.cph + 0.85 * tier_i)   # -1..1 position inside the cluster rhythm
            if hem and kind == "main":
                zz += P.get("hem_cluster_dz", 0.0) * gn   # hem rides up/down with the cluster: grouped masses
            ff = clamp((zz - self.zb) / (self.z_top - self.zb))
            g = self.gap_factor(az % 360.0, ff)
            asym = 1.0 + a_amp * math.cos(math.radians(az - a_az))
            if g == 0.0 or (kind == "inter" and ((g < 1.0 and not P.get("gap_soft")) or asym < 1.0 - a_amp * 0.55)):
                continue
            grp = 1.0 + c_amp * gn
            specs.append({"z": zz, "az": az, "f": ff, "kind": kind, "tier": tier_i, "gn": gn,
                          "reach": self.profile(ff) * k * asym * g * grp})
        return specs, spacing

    def plan_crown(self) -> list[dict]:
        specs, z, az0, i = [], self.zb, self.rng.uniform(0.0, 360.0), 0
        while z <= self.z_top:
            r = self.sub_rng(1, i)
            tier, spacing = self.plan_tier(z, az0, i, r)
            specs += tier
            z += spacing
            az0 += r.uniform(35.0, 140.0)
            i += 1
        self.specs = self.fit_width(specs)
        return self.specs

    def fit_width(self, specs: list[dict]) -> list[dict]:
        """Rescale reaches so the tip bbox (mean of x and y extents) equals crown_width, then apply the limits."""
        def tips():
            for s in specs:
                a = math.radians(s["az"])
                c = self.axis(s["z"])
                yield c.x + math.cos(a) * s["reach"], c.y + math.sin(a) * s["reach"]
        xs, ys = zip(*tips())
        scale = self.P["crown_width"] / (0.5 * (max(xs) - min(xs) + max(ys) - min(ys)))
        rm = self.P["reach_max"]
        for s in specs:
            r = s["reach"] * scale
            if r > 0.85 * rm:   # soft knee: long boughs stay ordered instead of piling up at the cap
                r = 0.85 * rm + 0.15 * rm * math.tanh((r - 0.85 * rm) / (0.15 * rm))
            s["reach"] = max(r, self.P["reach_floor"])
        return specs

    def plan_summary(self) -> dict:
        """Numbers for the recipe: bough count and, for the three lowest tiers, boughs per tier and reach range (m)."""
        tiers = []
        for i in range(3):
            reach = [sp["reach"] for sp in self.specs if sp["kind"] == "main" and sp["tier"] == i]
            if reach:
                tiers.append({"boughs": len(reach), "reach_m": [round(min(reach), 2), round(max(reach), 2)]})
        return {"boughs": len(self.specs), "tiers": 1 + max(sp["tier"] for sp in self.specs), "lowest_tiers": tiers}
