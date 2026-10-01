"""Shared mesh builder, colour classes and face painting for debris_family.py (fallen_log_A, root_flare_A).
Every face carries a part id (per-part random, cavity rules) and a colour class (broad grouped colour, no speckle);
closed pieces get outward normals from their signed volume. Colours are linear rgb from the nature_lib palette.
"""
from __future__ import annotations

import math
import sys

sys.path.insert(0, "/Users/andrejvysny/Developer/godot/tools/blender")

import bmesh  # noqa: E402
from mathutils import Vector  # noqa: E402

import nature_lib as nl  # noqa: E402

MATERIALS = (nl.SOLID,)

Z, X = Vector((0.0, 0.0, 1.0)), Vector((1.0, 0.0, 0.0))
PART_ATTR, TONE_ATTR = "part", "tone"
DARK, MID, RIDGE, WOOD, HEART, ROT, ROT_HEART, LENS = range(8)   # face colour classes
CLASS_COLOR = {
    DARK: nl.pal("bark_dark"), MID: nl.pal("bark"), RIDGE: nl.pal("bark_ridge"), WOOD: nl.pal("wood_exposed"),
    HEART: nl.scale_rgb(nl.mix(nl.pal("wood_exposed"), nl.pal("bark_dark"), 0.62), 0.92),
    ROT: nl.mix(nl.pal("deadwood"), nl.pal("bark"), 0.3),
    ROT_HEART: nl.mix(nl.pal("deadwood"), nl.pal("bark_dark"), 0.6),
    LENS: nl.mix(nl.mix(nl.pal("deadwood"), nl.pal("bark"), 0.3), nl.pal("bark"), 0.5),   # weathered bark, half way back
}


# ---------------------------------------------------------------- small math
def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def smoothstep(a: float, b: float, x: float) -> float:
    t = clamp((x - a) / (b - a))
    return t * t * (3.0 - 2.0 * t)


# ---------------------------------------------------------------- mesh builder
class Builder:
    """bmesh with part/colour-class face layers; closed pieces get outward normals from their signed volume."""

    def __init__(self, seed: int):
        self.rng = nl.rng(seed)
        self.bm = bmesh.new()
        self.part_l = self.bm.faces.layers.int.new(PART_ATTR)
        self.tone_l = self.bm.faces.layers.int.new(TONE_ATTR)
        self.parts: list[dict] = []
        self.piece: list = []

    def new_part(self, kind: str, **info) -> int:
        self.parts.append({"kind": kind, "rand": self.rng.random(), **info})
        return len(self.parts) - 1

    def vert(self, co: Vector):
        return self.bm.verts.new(co)

    def face(self, vs: list, pid: int, tone: int = MID) -> None:
        f = self.bm.faces.new(vs)
        f[self.part_l], f[self.tone_l] = pid, tone
        self.piece.append(f)

    def close_piece(self) -> None:
        """Consistent + outward: recalc, then flip the piece if its signed volume is negative (jagged ends can fool
        the farthest-face heuristic)."""
        bmesh.ops.recalc_face_normals(self.bm, faces=self.piece)
        vol = 0.0
        for f in self.piece:
            c = [v.co for v in f.verts]
            vol += sum(c[0].dot(c[i].cross(c[i + 1])) for i in range(1, len(c) - 1))
        if vol < 0.0:
            bmesh.ops.reverse_faces(self.bm, faces=self.piece)
        self.piece = []

    def tube(self, rings: list, pid: int, tones: list | None = None, cap_tone: int = MID, caps=(False, False),
             face_tones: list | None = None) -> None:
        """Closed solid from rings (a 1-vertex ring is a point); tones[i] colours segment i, face_tones[k] (when
        given) colours side k of every segment instead (slabs: bark outside, wood on the edges)."""
        vr = [[self.vert(p) for p in ring] for ring in rings]
        for i, (a, c) in enumerate(zip(vr, vr[1:])):
            tone = tones[i] if tones else MID
            for k in range(max(len(a), len(c))):
                n = (k + 1) % max(len(a), len(c))
                if face_tones:
                    tone = face_tones[k]
                if len(a) == 1:
                    quad = [a[0], c[n], c[k]]
                elif len(c) == 1:
                    quad = [a[k], a[n], c[0]]
                else:
                    quad = [a[k], a[n], c[n], c[k]]
                self.face(quad, pid, tone)
        if caps[0]:
            self.face(vr[0], pid, cap_tone)
        if caps[1]:
            self.face(vr[-1][::-1], pid, cap_tone)
        self.close_piece()


# ---------------------------------------------------------------- painting
def bark_shade(c: tuple, nz: float) -> tuple:
    """Bark classes: underside toward bark_dark and darker, up-facing planes catch a little bark_ridge."""
    dn, up = smoothstep(0.1, -0.5, nz), smoothstep(0.5, 0.95, nz)
    c = nl.mix(nl.mix(c, CLASS_COLOR[DARK], 0.6 * dn), CLASS_COLOR[RIDGE], 0.3 * up)
    return nl.scale_rgb(c, 1.0 - 0.22 * dn)


def root_colour(nz: float, z: float, part: dict) -> tuple:
    c = nl.mix(CLASS_COLOR[MID], CLASS_COLOR[RIDGE], smoothstep(0.4, 0.75, nz) * part["ridge"])
    c = nl.mix(c, CLASS_COLOR[DARK], 0.7 * smoothstep(0.35, -0.15, nz))
    return nl.scale_rgb(c, lerp(0.8, 1.0, smoothstep(-0.05, 0.2, z)))


def colour(part: dict, tone: int, poly) -> tuple:
    nz, kind = poly.normal.z, part["kind"]
    if kind == "root":
        c = root_colour(nz, poly.center.z, part)
    else:
        c = CLASS_COLOR[tone]
        if tone <= RIDGE or tone == LENS:
            c = bark_shade(c, nz)
        if kind == "body":   # slow weathering drift along the log: smooth, never a plate or a speckle
            c = nl.scale_rgb(c, 1.0 + 0.035 * math.sin(2.1 * poly.center.x + part["rand"] * 6.28))
        if kind == "break_shell":   # bark shell thins to pale inner bark at the tooth tips
            c = nl.mix(c, CLASS_COLOR[ROT], 0.55 * clamp((poly.center.x - part["x1"]) / 0.3))
    return (*nl.scale_rgb(c, lerp(0.94, 1.04, part["rand"])), 0.0)


def cavity(part: dict, tone: int, poly) -> float:
    nz, kind = poly.normal.z, part["kind"]
    if kind == "root":
        rho = math.hypot(poly.center.x, poly.center.y)
        return clamp(lerp(0.6, 0.95, smoothstep(-0.3, 0.7, nz)) * lerp(0.78, 1.0, smoothstep(0.3, 0.8, rho)), 0.5, 1.0)
    if tone in (HEART, ROT_HEART):
        return 0.62
    base = lerp(0.72, 0.96, smoothstep(-0.6, 0.6, nz))
    return clamp(base * (0.85 if tone in (WOOD, ROT) else 1.0), 0.5, 1.0)


def finish(b: Builder, asset_id: str):
    obj = nl.mesh_object(asset_id, b.bm, MATERIALS)
    nl.finalize(obj)
    nl.uv_unwrap(obj)
    me = obj.data
    pids = [d.value for d in me.attributes[PART_ATTR].data]
    tones = [d.value for d in me.attributes[TONE_ATTR].data]
    assert len(pids) == len(me.polygons), "face order changed"
    nl.paint(obj, lambda poly, li, co: colour(b.parts[pids[poly.index]], tones[poly.index], poly))
    nl.paint_data(obj, lambda poly, li, co: (cavity(b.parts[pids[poly.index]], tones[poly.index], poly),
                                             b.parts[pids[poly.index]]["rand"]))
    me.attributes.remove(me.attributes[PART_ATTR])
    me.attributes.remove(me.attributes[TONE_ATTR])
    return obj
