"""Spruce painting: colour (linear rgb + flex alpha) and UV2 data (cavity, part random) per part kind. Mixed into
spruce_gen.Tree. Bark/stubs are painted per trunk strip, boughs deep at the trunk and tip green outward/upward."""
from __future__ import annotations

import math

from mathutils import Vector

import nature_lib as nl
from spruce_math import clamp, hash01, lerp, smoothstep


def make_palette(t: dict) -> dict:
    """Linear foliage colours from the shared palette. `cool` shifts toward blue-green for mature trees."""
    def tint(c, k):
        return (c[0] * (1.0 - 0.07 * t["cool"]) * k, c[1] * (1.0 - 0.02 * t["cool"]) * k,
                c[2] * (1.0 + 0.10 * t["cool"]) * k)
    return {"deep": tint(nl.pal("conifer_deep"), t["deep_k"]),
            "mid": tint(nl.mix(nl.pal("conifer"), nl.pal("conifer_tip"), t["mid_mix"]), t["mid_k"]),
            "tip": nl.scale_rgb(nl.mix(nl.pal("conifer"), nl.pal("conifer_tip"), t["tip_mix"]), t["tip_k"])}


BARK = (nl.pal("bark_dark"), nl.pal("bark"), nl.pal("bark_ridge"))


class PaintMixin:
    def bark_color(self, co: Vector) -> tuple:
        n = self.sides
        ax = self.axis(co.z)
        col = round((math.atan2(co.y - ax.y, co.x - ax.x) - 0.035 * co.z) / (2 * math.pi / n)) % n
        a = co.z / 3.2
        k, fr = math.floor(a), a - math.floor(a)
        noise = lerp(hash01(col, k), hash01(col, k + 1), smoothstep(0.0, 1.0, fr))
        tone = 0.6 * noise + 0.4 * hash01(col, 99)
        c = nl.mix(BARK[0], BARK[1], tone / 0.45) if tone < 0.45 else nl.mix(BARK[1], BARK[2], (tone - 0.45) / 0.55)
        return nl.scale_rgb(c, lerp(0.82, 1.0, smoothstep(-0.3, 0.6, co.z)))

    def color(self, part: dict, poly, co: Vector) -> tuple:
        kind, pal = part["kind"], self.pal
        if kind == "trunk":
            return (*self.bark_color(co), 0.0)
        if kind == "buttress":
            up = clamp(poly.normal.z)
            return (*nl.scale_rgb(nl.mix(BARK[1], BARK[2], 0.65 * up), lerp(0.8, 1.0, smoothstep(-0.2, 0.5, co.z))), 0.0)
        if kind == "stub":
            c = nl.mix(nl.pal("deadwood"), nl.pal("wood_exposed"), 0.3 * smoothstep(0.4, 1.0, part["rand"]))
            return (*nl.scale_rgb(c, lerp(0.85, 1.05, part["rand"])), 0.0)
        ax = self.axis(co.z)
        up = clamp(poly.normal.z * 1.3)
        tone = self.P["tone"]
        if kind == "core":
            hf = clamp((co.z - self.zb) / max(self.z_crown_top - self.zb, 0.1))
            c = nl.mix(pal["deep"], pal["mid"], tone["core_mix"])
            c = nl.mix(c, pal["tip"], tone["core_tip"] * up)
            return (*nl.scale_rgb(c, 0.9 + 0.1 * up), 0.1 + 0.25 * hf)
        if kind == "leader":
            u = clamp((co.z - part["z0"]) / part["span"])
            return (*nl.mix(pal["mid"], pal["tip"], clamp(u * 1.2) * (0.35 + 0.65 * up)), 0.95 * smoothstep(0.0, 1.0, u))
        d = math.hypot(co.x - ax.x, co.y - ax.y)
        u = clamp((d - part["d0"]) / (part["d1"] - part["d0"]))
        base = nl.mix(pal["deep"], pal["mid"], smoothstep(0.0, 0.6, u))
        tf = smoothstep(tone["tip_from"], 1.0, u) * (0.1 + 0.9 * up) * part["tipk"] * tone["tip_gain"]
        c = nl.scale_rgb(nl.mix(base, pal["tip"], clamp(tf)), part["val"])
        c = (c[0] * (1.0 + 0.06 * part["warm"]), c[1], c[2] * (1.0 - 0.08 * part["warm"]))   # per-bough hue grouping
        hf = clamp((co.z - self.zb) / max(self.z_crown_top - self.zb, 0.1))
        flex = smoothstep(0.12, 0.95, d / part["d1"]) * (0.3 + 0.7 * hf ** 0.7)
        return (*c, flex)

    def data(self, part: dict, poly, co: Vector) -> tuple:
        kind, up = part["kind"], clamp(poly.normal.z)
        if kind == "trunk":
            cav = 0.92 - 0.22 * smoothstep(self.zb - 0.5, self.zb + 1.5, co.z) - 0.1 * (1.0 - smoothstep(0.0, 1.0, co.z))
        elif kind == "bough":
            ax = self.axis(co.z)
            u = clamp((math.hypot(co.x - ax.x, co.y - ax.y) - part["d0"]) / max(part["d1"] - part["d0"], 0.1))
            cav = (0.74 + 0.26 * up) * (0.78 + 0.22 * smoothstep(0.0, 0.4, u))
        else:
            cav = {"buttress": 0.74 + 0.2 * up, "stub": 0.9, "leader": 0.85 + 0.1 * up, "core": 0.62}[kind]
        return (clamp(cav, 0.55, 1.0), part["rand"])
