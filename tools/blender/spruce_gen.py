"""Parametric spruce generator shared by all growth forms (Blender 5.2, headless). Driven by tree_family.py.
Plan: docs/valley_environment_plan.md 5.2. Contract: assets/nature/README.md.

Construction: closed tapered trunk (bend + lean) ending at the leader base, rounded buttress ribs + low ground spurs,
blunt dead stubs, a lumpy interior foliage core (keeps the crown closed and dark, mostly hidden), and a crown of solid
bough wedges (closed lens/diamond sections on a drooping spine, optional side lobes) in irregular overlapping tiers.
The longest, densest tier sits at the crown base and reach falls off steadily to a spire leader. Tiers are jittered in
height, azimuth and length; a slow azimuth harmonic groups boughs into clusters so no tier repeats the last; small
missing-growth gaps open the mid crown. Bark/stubs = M_solid, boughs/leader/core = M_foliage. Colour is painted per
bough (deep at the trunk, tip green outward/upward); flex alpha rises with radius/height.
"""
from __future__ import annotations

import math

import bmesh
from mathutils import Vector

import nature_lib as nl
from spruce_math import clamp, lerp, shape, smoothstep
from spruce_paint import PaintMixin, make_palette
from spruce_plan import PlanMixin

SOLID, FOLIAGE = 0, 1
Z = Vector((0.0, 0.0, 1.0))
PART_ATTR = "part"
STATIONS = {4: (0.0, 0.38, 0.75, 1.0), 5: (0.0, 0.30, 0.60, 0.85, 1.0), 6: (0.0, 0.18, 0.40, 0.65, 0.85, 1.0)}
LOBE_S = (0.0, 0.35, 0.70, 1.0)
P_CORE_SIDES = 8


# ---------------------------------------------------------------- tree
class Tree(PlanMixin, PaintMixin):
    def __init__(self, P: dict):
        self.P = P
        self.rng = nl.rng(P["seed"])
        self.bm = bmesh.new()
        self.layer = self.bm.faces.layers.int.new(PART_ATTR)
        self.parts: list[dict] = []
        self.pal = make_palette(P["tone"])
        self.H = P["height"]
        self.sides = P["trunk_sides"]
        self.zb = P["crown_start"] * self.H + P["sag"]   # root height of the lowest tier (live foliage hangs below it)
        self.z_trunk_top = self.H - P["leader"]          # trunk ends where the leader starts
        self.z_top = self.H - P["tier_top"]              # root height of the last tier
        self.z_crown_top = self.H - P["leader"] - 0.1
        self.ph = [self.rng.uniform(0.0, 6.28) for _ in range(4)]
        self.cph = self.rng.uniform(0.0, 6.28)           # cluster harmonic phase
        self.specs: list[dict] = []

    # -- trunk centre line and radius
    def axis(self, z: float) -> Vector:
        P, ph = self.P, self.ph
        t = max(z, 0.0) / self.H
        ld = math.radians(P["lean_dir"])
        lean = P["lean"] * t ** 1.5
        b = P["bend"] * min(1.0, t * 4.0)
        x = lean * math.cos(ld) + b * (0.65 * math.sin(3.1 * t + ph[0]) + 0.35 * math.sin(7.3 * t + ph[1]))
        y = lean * math.sin(ld) + b * (0.65 * math.sin(2.6 * t + ph[2]) + 0.35 * math.sin(6.1 * t + ph[3]))
        return Vector((x, y, z))

    def radius(self, z: float) -> float:
        P = self.P
        t = clamp(z / self.z_trunk_top)
        r = P["trunk_r1"] + (P["trunk_r0"] - P["trunk_r1"]) * (1.0 - t) ** P["taper"]
        if z < P["flare_h"]:
            r *= 1.0 + 0.18 * (1.0 - max(z, 0.0) / P["flare_h"]) ** 2
        return r

    # -- mesh primitives
    def new_part(self, kind: str, rng=None, **info) -> int:
        self.parts.append({"kind": kind, "rand": (rng or self.rng).random(), **info})
        return len(self.parts) - 1

    def sub_rng(self, salt: int, index: int):
        """Independent stream per tier/bough: changing the crown top or crown start must not reshuffle the boughs below."""
        return nl.rng(self.P["seed"] * 7919 + salt * 104729 + index)

    def tube(self, rings, mat: int, pid: int, caps=(False, False)) -> None:
        """Closed solid from rings (a 1-vertex ring is a point). Faces tagged with material + part."""
        bm = self.bm
        vr = [[bm.verts.new(p) for p in ring] for ring in rings]
        faces = []
        for a, b in zip(vr, vr[1:]):
            n = max(len(a), len(b))
            for i in range(n):
                j = (i + 1) % n
                if len(a) == 1:
                    quad = [a[0], b[j], b[i]]
                elif len(b) == 1:
                    quad = [a[i], a[j], b[0]]
                else:
                    quad = [a[i], a[j], b[j], b[i]]
                faces.append(bm.faces.new(quad))
        if caps[0]:
            faces.append(bm.faces.new(vr[0]))
        if caps[1]:
            faces.append(bm.faces.new(vr[-1][::-1]))
        for f in faces:
            f.material_index = mat
            f[self.layer] = pid
        bmesh.ops.recalc_face_normals(bm, faces=faces)

    @staticmethod
    def frame(pts, i: int) -> tuple[Vector, Vector, Vector]:
        """Tangent, lateral (horizontal) and up vectors at spine station i."""
        tan = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
        lat = tan.cross(Z)
        lat = lat.normalized() if lat.length > 1e-4 else Vector((1.0, 0.0, 0.0))
        return tan, lat, lat.cross(tan)

    def wedge(self, pid: int, pts, wl, wr, hu, hd, roll: float = 0.0, hexa: bool = False, cup: float = 0.0) -> None:
        """Solid along a spine; first/last station are points (widths ignored). The section is a diamond, or (hexa) a
        flat-topped lens that reads as a thick bough. `cup` drops the side edges below the spine (x hu) so the bough
        drapes like a tent. `roll` (rad) tilts the wide plane about the spine."""
        n = len(pts)
        rings = []
        for i, p in enumerate(pts):
            if i in (0, n - 1):
                rings.append([p.copy()])
                continue
            _, lat, up = self.frame(pts, i)
            if roll:
                lat, up = lat * math.cos(roll) + up * math.sin(roll), up * math.cos(roll) - lat * math.sin(roll)
            edge = -cup * hu[i] + 0.06 * hu[i]
            if hexa:
                rings.append([p + up * hu[i] - lat * (0.45 * wl[i]), p + up * hu[i] + lat * (0.45 * wr[i]),
                              p + up * edge + lat * wr[i], p - up * hd[i] + lat * (0.4 * wr[i]),
                              p - up * hd[i] - lat * (0.4 * wl[i]), p + up * edge - lat * wl[i]])
            else:
                rings.append([p + up * hu[i], p + up * edge + lat * wr[i], p - up * hd[i], p + up * edge - lat * wl[i]])
        self.tube(rings, FOLIAGE, pid)

    def stub_tube(self, pid: int, pts, rad, sides: int = 5) -> None:
        """Round broken branch: capped at the buried start and at the blunt end."""
        rings = []
        for i, p in enumerate(pts):
            _, lat, up = self.frame(pts, i)
            rings.append([p + (lat * math.cos(a) + up * math.sin(a)) * rad[i]
                          for a in (2 * math.pi * k / sides for k in range(sides))])
        self.tube(rings, SOLID, pid, caps=(True, True))

    # -- trunk, root flare, stubs
    def trunk_stations(self) -> list[float]:
        P = self.P
        zs = [-P["embed"], 0.0] + [P["flare_h"] * k for k in (0.33, 0.72, 1.1)]
        z = zs[-1] + P["trunk_step"]
        while z < self.z_trunk_top - 0.5 * P["trunk_step"]:
            zs.append(z)
            z += P["trunk_step"]
        return zs + [self.z_trunk_top]

    def add_trunk(self) -> None:
        P, r, n = self.P, self.rng, self.sides
        ja = [r.uniform(-0.12, 0.12) for _ in range(n)]
        jr = [r.uniform(0.95, 1.05) for _ in range(n)]
        rings = []
        for z in self.trunk_stations():
            rr = self.radius(z)
            ring = []
            for j in range(n):
                a = 2 * math.pi * (j + ja[j]) / n + 0.035 * z
                k = rr * jr[j] * (1.0 + 0.025 * math.sin(z * 1.3 + j * 1.7))
                ring.append(self.axis(z) + Vector((math.cos(a) * k, math.sin(a) * k, 0.0)))
            rings.append(ring)
        self.tube(rings, SOLID, self.new_part("trunk"), caps=(True, True))

    def add_root(self, pid: int, az: float, reach: float, h0: float, hw0: float, hw1: float) -> None:
        """Rounded rib: hump section (crest, shoulders, buried feet) on a spine that leaves the trunk at height h0
        and runs out and down to `reach` trunk radii; the first ring sits inside the trunk surface."""
        r0, emb = self.P["trunk_r0"], self.P["embed"]
        d = Vector((math.cos(az), math.sin(az), 0.0))
        lat = d.cross(Z)
        start = 0.88 * self.radius(h0)
        rings = [[self.axis(0.0) + d * (0.45 * start) + Z * (0.6 * h0)]]
        for t in (0.0, 0.08, 0.18, 0.32, 0.5, 0.72, 1.0):
            zc = h0 * (1.0 - t) ** 1.8
            hw = lerp(hw0, hw1, t) * (0.4 + 0.6 * smoothstep(0.0, 0.3, t))   # widens gradually: no arrow-head top
            c = self.axis(zc) + d * lerp(start, reach * r0, t ** 0.85)
            rings.append([c + Z * zc, c + lat * (0.75 * hw) + Z * (0.6 * zc), c + lat * hw - Z * 0.08,
                          c - Z * (0.9 * emb), c - lat * hw - Z * 0.08, c - lat * (0.75 * hw) + Z * (0.6 * zc)])
        tip = self.axis(0.0) + d * (reach * r0 + 0.06)
        rings.append([Vector((tip.x, tip.y, -0.08))])
        self.tube(rings, SOLID, pid)

    def add_buttresses(self) -> None:
        P, r = self.P, self.rng
        n, h = P["flare_lobes"], P["flare_h"]
        if n == 0:
            return
        k_w = P["trunk_r0"] / 0.34   # rib widths were tuned on a 0.34 m trunk
        spurs = set(r.sample(range(n), P["flare_spurs"]))
        az0 = r.uniform(0.0, 360.0)
        for k in range(n):
            az = math.radians(az0 + k * 360.0 / n + r.uniform(-14.0, 14.0))
            if k in spurs:   # low ground spur: long, flat, reads as a root gripping the soil
                self.add_root(self.new_part("buttress"), az, P["spur_reach"] * r.uniform(0.92, 1.0),
                              h * r.uniform(0.38, 0.5), 0.17 * k_w, 0.07 * k_w)
            else:
                self.add_root(self.new_part("buttress"), az, P["flare"] * r.uniform(0.85, 1.0), h, 0.35 * k_w, 0.10 * k_w)

    def add_stubs(self) -> None:
        P, r = self.P, self.rng
        lo, hi = P["stub_z"]
        if P["stubs"] == 0:
            return
        step = (hi - lo) / max(P["stubs"] - 1, 1)
        az = r.uniform(0.0, 360.0)
        for i in range(P["stubs"]):
            z = lo + i * step + r.uniform(-0.08, 0.08)
            az += 137.5 + r.uniform(-25.0, 25.0)
            a, pitch = math.radians(az), math.radians(r.uniform(22.0, 48.0))
            R = self.radius(z)
            length = r.uniform(*P["stub_len"]) + 0.35 * R / math.cos(pitch)   # visible length + buried part
            d = Vector((math.cos(a), math.sin(a), 0.0))
            start = self.axis(z) + d * (0.65 * R)
            bend = r.uniform(-0.04, 0.04)
            pts = [start + d * (s * length * math.cos(pitch)) + d.cross(Z) * bend * s * s
                   - Z * (s * length * math.sin(pitch)) for s in (0.0, 0.35, 0.7, 1.0)]
            rb = r.uniform(*P["stub_r"])
            self.stub_tube(self.new_part("stub"), pts, [rb * k for k in (1.0, 0.8, 0.58, 0.38)])

    # -- crown geometry
    def add_bough(self, spec: dict, r) -> None:
        P = self.P
        z0, az, Lh, f = spec["z"], math.radians(spec["az"]), spec["reach"], spec["f"]
        d = Vector((math.cos(az), math.sin(az), 0.0))
        side = d.cross(Z)
        c0, rho0 = self.axis(z0), 0.6 * self.radius(z0)
        pitch = lerp(0.0, P["pitch_top"], f) + r.uniform(-0.06, 0.06)
        droop = lerp(*P["droop"], f) + r.uniform(-P["droop_jitter"], P["droop_jitter"]) + P.get("droop_cluster", 0.0) * spec["gn"]
        lift = lerp(0.15, 0.06, smoothstep(0.4, 0.7, f))   # tips curl only slightly: no upward horns
        sway = r.uniform(-0.10, 0.10) * Lh

        def pos(s: float) -> Vector:
            dz = Lh * (pitch * s - droop * s ** 1.7 + lift * max(0.0, (s - 0.7) / 0.3) ** 2)
            return c0 + d * (rho0 + s * (Lh - rho0)) + side * (sway * s * s) + Z * dz

        w = smoothstep(0.35, 0.65, f)   # broader, overlapping masses in the upper crown
        wm = min(r.uniform(lerp(0.28, 0.40, w), lerp(0.40, 0.50, w)) * Lh * P["wfac"], P["bough_wmax"])
        thick = P["thick"] * Lh + P["thick0"]     # full thickness at the widest section
        hu0, hd0 = 0.58 * thick, 0.42 * thick
        asym = r.uniform(0.8, 1.25)
        pid = self.new_part("bough", r, d0=rho0, d1=Lh, val=r.uniform(0.90, 1.08), tipk=r.uniform(1.35, 2.0),
                            warm=r.uniform(-1.0, 1.0))
        S = STATIONS[6 if Lh >= P["st6_min_reach"] else P["st_small"]]
        ws = [wm * shape(s, 1.0, P["tip_b"]) for s in S]
        ts = [shape(s, 0.45, 1.0) for s in S]   # thickest near the root, feathering out toward the tip
        self.wedge(pid, [pos(s) for s in S], [x * asym for x in ws], [x / asym for x in ws],
                   [hu0 * t for t in ts], [hd0 * t for t in ts], roll=math.radians(r.uniform(-16.0, 16.0)),
                   hexa=Lh >= P["hex_min_reach"], cup=P["cup"])
        if Lh >= P["lobe_min_reach"]:
            self.add_lobes(pid, pos, d, Lh, wm, hu0, r)

    def add_lobes(self, pid: int, pos, d: Vector, Lh: float, wm: float, hu0: float, r) -> None:
        sides = (1.0, -1.0) if r.random() < 0.5 else (-1.0, 1.0)
        for sj, sd in zip((0.38, 0.62), sides):
            ang = math.radians(r.uniform(38.0, 58.0)) * sd
            d2 = Vector((d.x * math.cos(ang) - d.y * math.sin(ang), d.x * math.sin(ang) + d.y * math.cos(ang), 0.0))
            L2 = 0.8 * (1.0 - sj) * Lh * r.uniform(0.75, 1.0)
            start = pos(sj) + d.cross(Z) * (sd * 0.35 * wm * shape(sj)) - Z * (0.9 * hu0 * shape(sj, 0.8, 0.9))
            pts = [start + d2 * (s * L2) + Z * (L2 * (-0.10 * s - 0.28 * s ** 1.7 + 0.08 * max(0.0, s - 0.75)))
                   for s in LOBE_S]
            w2 = [0.40 * wm * shape(s, 0.9, 1.2) for s in LOBE_S]
            h2 = [0.42 * hu0 * shape(s, 0.8, 0.9) for s in LOBE_S]
            self.wedge(pid, pts, w2, w2, h2, [0.7 * h for h in h2])

    def add_core(self) -> None:
        """Interior foliage mass: a lumpy cone (radius ~core_k of the local reach, pinched at gaps) that stays mostly
        hidden under the boughs, so the crown reads closed and dark instead of showing trunk between tiers."""
        P, r, n = self.P, self.rng, P_CORE_SIDES
        half = 0.5 * P["crown_width"]
        z0, z1 = self.zb - P.get("core_drop", 0.3), self.z_top
        a_amp, a_az = P["asym"]
        m = max(4, round((z1 - z0) / 0.75))
        ja = [r.uniform(-0.15, 0.15) for _ in range(n)]
        rings = []
        for i in range(m + 1):
            z = lerp(z0, z1, i / m)
            f = clamp((z - self.zb) / (self.z_top - self.zb))
            scallop = 1.0 + P["core_scallop"] * math.sin(2 * math.pi * (z - self.zb) / P["core_period"])
            rad = lerp(*P["core_k"], f) * half * self.profile(f) * scallop * r.uniform(0.9, 1.1) + P.get("core_floor", 0.10)
            ring = []
            for j in range(n):
                a = 2 * math.pi * (j + ja[j]) / n
                g = self.gap_factor(math.degrees(a) % 360.0, f)
                asym = 1.0 + a_amp * math.cos(a - math.radians(a_az))
                k = rad * (0.35 + 0.65 * g) * asym * r.uniform(0.9, 1.1)
                ring.append(self.axis(z) + Vector((math.cos(a) * k, math.sin(a) * k, 0.0)))
            rings.append(ring)
        rings.append([self.axis(z1 + min(0.4, 0.5 * P["tier_top"]))])
        self.tube(rings, FOLIAGE, self.new_part("core"), caps=(True, False))

    def add_leader(self) -> None:
        """Spire rooted in the trunk top: starts buried, swells past the trunk end, flex grows from 0 at its base."""
        L, k = self.P["leader"], self.P["leader_w"]
        z0 = self.z_trunk_top
        dz = tuple(L * f for f in (-0.115, 0.0, 0.115, 0.29, 0.5, 0.73, 1.0))
        rad = tuple(k * x for x in (0.0, 0.085, 0.17, 0.25, 0.22, 0.12, 0.0))
        pid = self.new_part("leader", z0=z0 + dz[0], span=L - dz[0])
        self.wedge(pid, [self.axis(z0 + x) for x in dz], rad, rad, rad, rad)

    def foliage_base(self) -> float:
        """Lowest foliage vertex (live crown base), for fitting `sag` to the crown_start target."""
        return min(v.co.z for f in self.bm.faces if f.material_index == FOLIAGE for v in f.verts)

    def build(self) -> None:
        self.add_trunk()
        self.add_buttresses()
        self.add_stubs()
        self.add_core()
        for i, spec in enumerate(self.plan_crown()):
            self.add_bough(spec, self.sub_rng(2, i))
        self.add_leader()

