"""Shared meadow-groundcover primitives (moved verbatim out of groundcover_family.py to keep scripts < 500 lines).

Parts (bmesh + per-vertex/face/part info), add_strip (tapered blade/leaf), add_stem (3-sided prism),
bezier stems, clump layout helpers (footprint_slots, blade_heights), the grass colour/data functions and
the custom-normal pass. Used by groundcover_family.py and groundcover_meadow.py; needs nature_lib.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import bmesh
from mathutils import Vector

sys.path.insert(0, str(Path(__file__).resolve().parent))
import nature_lib as nl  # noqa: E402

UP = Vector((0.0, 0.0, 1.0))
TAU = math.tau


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def smooth(t: float) -> float:
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


# ------------------------------------------------------------------ mesh container

class Parts:
    """bmesh plus per-vertex / per-face / per-part info, index-aligned with the final mesh."""

    def __init__(self) -> None:
        self.bm = bmesh.new()
        self.vinfo: list[dict] = []
        self.finfo: list[dict] = []
        self.parts: list[dict] = []

    def part(self, **kw) -> int:
        self.parts.append(kw)
        return len(self.parts) - 1

    def vert(self, co: Vector, kind: str, part: int, t: float):
        self.vinfo.append({"kind": kind, "part": part, "t": t})
        return self.bm.verts.new(co)

    def face(self, verts: list, expect: Vector, kind: str, part: int, smooth_key=None) -> None:
        f = self.bm.faces.new(verts)
        f.normal_update()
        if f.normal.dot(expect) < 0.0:
            f.normal_flip()
        self.finfo.append({"kind": kind, "part": part, "smooth": smooth_key})


def add_strip(P: Parts, base: Vector, az: float, lean0: float, bend: float, widths: tuple,
              ref: Vector, kind: str, part: int, *, height=None, length=None, twist=0.0) -> None:
    """Tapered blade/leaf: len(widths) rows of 2 verts, then one tip vertex. The spine curls from
    `lean0` (radians from vertical) by `bend` toward azimuth `az`; `ref` picks the front side."""
    segs = len(widths)
    dirs = []
    for k in range(segs):
        th = lean0 + bend * ((k + 0.5) / segs) ** 1.3
        dirs.append(Vector((math.sin(th) * math.cos(az), math.sin(th) * math.sin(az), math.cos(th))))
    if height is not None:  # tip z is linear in length, so solve it exactly
        length = height * segs / sum(d.z for d in dirs)
    pts = [Vector(base)]
    for d in dirs:
        pts.append(pts[-1] + d * (length / segs))
    rows = []
    for k in range(segs + 1):
        T = dirs[min(k, segs - 1)] if k in (0, segs) else (dirs[k - 1] + dirs[k]).normalized()
        front = (ref - T * ref.dot(T)).normalized()
        side = T.cross(front)
        if k == 0:
            side.z = 0.0  # base row stays flat on the ground plane
            side.normalize()
        phi = twist * k / segs
        side = side * math.cos(phi) + front * math.sin(phi)
        t = k / segs
        if k == segs:
            rows.append([P.vert(pts[k], kind, part, 1.0)])
        else:
            hw = widths[k] * 0.5
            rows.append([P.vert(pts[k] - side * hw, kind, part, t), P.vert(pts[k] + side * hw, kind, part, t)])
    for k in range(segs - 1):
        a, b = rows[k], rows[k + 1]
        P.face([a[0], a[1], b[1], b[0]], ref, kind, part, part)
    P.face([rows[segs - 1][0], rows[segs - 1][1], rows[segs][0]], ref, kind, part, part)


def footprint_slots(r, p: dict) -> list[tuple]:
    """Base layout on a wobbling, yawed ellipse; alternating outer/inner radii avoid a ring."""
    n, (fw, fl) = p["blades"], p["footprint_m"]
    yaw = math.radians(p["footprint_yaw_deg"])
    p1, p2, off = r.uniform(0, TAU), r.uniform(0, TAU), r.uniform(0, TAU)
    c, s = math.cos(yaw), math.sin(yaw)
    slots = []
    for i in range(n):
        th = off + TAU * (i + r.uniform(-0.3, 0.3)) / n
        rn = r.uniform(0.74, 1.0) if i % 2 == 0 else r.uniform(0.12, 0.55)
        wob = 1.0 + 0.14 * math.sin(2 * th + p1) + 0.09 * math.sin(3 * th + p2)
        x = 0.5 * fw * rn * wob * math.cos(th)
        y = 0.5 * fl * rn * wob * math.sin(th)
        slots.append((x * c - y * s, x * s + y * c, rn, th))
    return slots


def blade_heights(r, p: dict, slots: list) -> list[float]:
    """Heights by rank so the spread is always the full range; weak centre bias, one tall side."""
    lo, hi = p["height_m"]
    tall = math.radians(p["tall_side_deg"])
    cb, hn = p["centre_bias"], p["height_noise"]
    raw = [(1.0 - cb * rn) + r.uniform(-hn, hn) + 0.12 * math.cos(th - tall) for _, _, rn, th in slots]
    order = sorted(range(len(slots)), key=lambda i: raw[i])
    n = len(slots)
    heights = [0.0] * n
    for rank, i in enumerate(order):
        h = lerp(lo, hi, (rank / (n - 1)) ** 0.85) + r.uniform(-0.006, 0.006)
        heights[i] = max(lo, min(hi, h))
    return heights


def grass_color(v: dict, fi: dict, P: Parts, p: dict) -> tuple:
    part, t = P.parts[v["part"]], v["t"]
    root, mid, tip = nl.pal("grass_root"), nl.pal("grass"), nl.pal("grass_tip")
    c = nl.mix(root, mid, smooth(t / 0.45)) if t < 0.45 else nl.mix(mid, tip, smooth((t - 0.45) / 0.55))
    if part["dry"] > 0.0:
        c = nl.mix(c, nl.pal("grass_dry"), part["dry"] * smooth((t - 0.25) / 0.75))
    c = nl.scale_rgb(c, part["k"])
    return (*c, t ** 1.5)


def grass_data(v: dict, fi: dict, P: Parts, p: dict) -> tuple:
    return (1.0 - 0.22 * (1.0 - v["t"]) ** 2, P.parts[v["part"]]["rand"])


def bezier(p0: Vector, p1: Vector, p2: Vector, p3: Vector, t: float) -> Vector:
    u = 1.0 - t
    return p0 * (u ** 3) + p1 * (3 * u * u * t) + p2 * (3 * u * t * t) + p3 * (t ** 3)


def add_stem(P: Parts, pts: list[Vector], radii: tuple, part: int) -> None:
    """3-sided tapered prism along `pts` (parallel-transported frame)."""
    n = len(pts)
    tans = []
    for k in range(n):
        a, b = pts[max(k - 1, 0)], pts[min(k + 1, n - 1)]
        tans.append((b - a).normalized())
    u = tans[0].cross(Vector((1.0, 0.0, 0.0))).normalized()
    rings = []
    for k in range(n):
        u = (u - tans[k] * u.dot(tans[k])).normalized()
        w = tans[k].cross(u)
        t = k / (n - 1)
        rad = lerp(radii[0], radii[1], t)
        dirs = [u * math.cos(TAU * j / 3 + 0.4) + w * math.sin(TAU * j / 3 + 0.4) for j in range(3)]
        cos = [pts[k] + d * rad for d in dirs]
        if k == 0:
            for c in cos:
                c.z = 0.0  # base ring sits exactly on the ground plane
        rings.append([(P.vert(c, "stem", part, t), d) for c, d in zip(cos, dirs)])
    for k in range(n - 1):
        for j in range(3):
            (a0, d0), (a1, d1) = rings[k][j], rings[k][(j + 1) % 3]
            (b0, _), (b1, _) = rings[k + 1][j], rings[k + 1][(j + 1) % 3]
            P.face([a0, a1, b1, b0], d0 + d1, "stem", part, part)


def stem_controls(r, p: dict, spec: dict, base: Vector, d: Vector) -> list[Vector]:
    """Bezier controls: near-vertical stem, one gentle bow, head offset `reach` toward d."""
    h = spec["height_m"]
    reach = lerp(*spec["reach_m"], r.random())
    perp = Vector((-d.y, d.x, 0.0)) * r.choice((-1.0, 1.0))
    bow = p["bow_m"] * r.uniform(0.6, 1.3)
    p3 = base + d * reach + Vector((0, 0, h))
    p1 = base + Vector((0, 0, 0.40 * h)) + d * 0.10 * reach + perp * bow
    p2 = p3 - Vector((0, 0, 0.28 * h)) - d * 0.45 * reach + perp * bow * 0.5
    return [base, p1, p2, p3]


def add_leaves(P: Parts, r, p: dict, az0: float) -> None:
    """Basal leaves in uneven clusters; no even radial spacing, so no rosette from above."""
    for c in p["leaf_clusters"]:
        for j in range(c["n"]):
            frac = j / (c["n"] - 1) - 0.5 if c["n"] > 1 else 0.0
            az = az0 + math.radians(c["centre_deg"] + frac * c["span_deg"] + r.uniform(-7.0, 7.0))
            part = P.part(k=1.0 + r.uniform(-0.05, 0.05), rand=r.random())
            base = Vector((r.uniform(-1, 1), r.uniform(-1, 1), 0.0)) * p["base_spread_m"] * 0.8
            w = lerp(*p["leaf_width_m"], r.random())
            add_strip(P, base, az, math.radians(lerp(*p["leaf_lean_deg"], r.random())),
                      math.radians(lerp(*p["leaf_bend_deg"], r.random())), (w * 0.45, w, w * 0.7),
                      UP, "leaf", part, length=lerp(*p["leaf_length_m"], r.random()),
                      twist=math.radians(r.uniform(-12, 12)))


def set_custom_normals(obj, P: Parts, up_blend: dict) -> None:
    """Loop normal = lerp(face normal, +Z, up_blend[kind]). Strips/stems smooth their face normal
    across a part (shared vertices); petals keep flat face normals."""
    me = obj.data
    acc: dict = {}
    for poly in me.polygons:
        key = P.finfo[poly.index]["smooth"]
        if key is not None:
            for vi in poly.vertices:
                acc[(vi, key)] = acc.get((vi, key), Vector()) + poly.normal
    normals = [(0.0, 0.0, 1.0)] * len(me.loops)
    for poly in me.polygons:
        fi = P.finfo[poly.index]
        w = up_blend[fi["kind"]]
        for li in poly.loop_indices:
            nf = poly.normal
            if fi["smooth"] is not None:
                nf = acc[(me.loops[li].vertex_index, fi["smooth"])].normalized()
            normals[li] = tuple((UP * w + nf * (1.0 - w)).normalized())
    for poly in me.polygons:
        poly.use_smooth = True  # custom loop normals are only honoured on smooth faces
    me.normals_split_custom_set(normals)

