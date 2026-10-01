"""Pine geometry and painting for pine_family: trunk with S-bend, root ribs, dead stubs, elbowed lateral arms, and
foliage pads (pads themselves: pine_geo.PadMixin). Colours are linear RGB + flex alpha; normals are custom."""
from __future__ import annotations

import math

import bmesh
from mathutils import Matrix, Vector

import nature_lib as nl
from pine_geo import Z, PadMixin, clamp, hash01, hermite, lerp, smoothstep, unit

SOLID = 0
PART_ATTR = "part"
FACET = 0.85   # share of the flat face normal in pad shading normals (spruce boughs are fully flat)

# ---------------------------------------------------------------- palette
WARM = nl.srgb("#8a5732")   # orange-brown mixed into bark; the foot stays grey-brown so the warmth builds with height
BARK_FOOT = nl.mix(nl.mix(nl.pal("bark_dark"), nl.pal("rock_dark"), 0.42), nl.pal("bark"), 0.12)
BARK_LO = nl.mix(nl.mix(nl.pal("bark_dark"), nl.pal("bark"), 0.5), WARM, 0.28)
BARK_MID = nl.mix(nl.pal("bark"), WARM, 0.40)
BARK_HI = nl.mix(nl.pal("bark_ridge"), WARM, 0.50)
PINE_DEEP, PINE_MID, PINE_TIP = nl.pal("pine_deep"), nl.pal("pine"), nl.pal("pine_tip")
COOL = nl.pal("conifer")   # mixed into pad bodies so the pine mass reads as a conifer, not meadow yellow-green


class Pine(PadMixin):
    def __init__(self, P: dict):
        self.P, self.T = P, P["trunk"]
        self.rng = nl.rng(P["seed"])
        self.bm = bmesh.new()
        self.layer = self.bm.faces.layers.int.new(PART_ATTR)
        self.parts: list[dict] = []
        self.top = self.T["top"]
        self.knx = [(z, x) for z, x, _ in self.T["bend"]]
        self.kny = [(z, y) for z, _, y in self.T["bend"]]

    def axis(self, z: float) -> Vector:
        return Vector((hermite(self.knx, z), hermite(self.kny, z), z))

    def radius(self, z: float) -> float:
        T = self.T
        r = T["r1"] + (T["r0"] - T["r1"]) * (1.0 - clamp(z / self.top)) ** T["taper"]
        if z < T["flare_h"]:
            r *= 1.0 + T["flare"] * (1.0 - max(z, 0.0) / T["flare_h"]) ** 2
        return r

    def root_flex(self, p: Vector) -> float:
        f, ax = self.P["flex"], self.axis(p.z)
        return lerp(f["root_min"], f["root_max"], clamp(math.hypot(p.x - ax.x, p.y - ax.y) / f["full_dist"]))

    def new_part(self, kind: str, **info) -> int:
        self.parts.append({"kind": kind, "rand": self.rng.random(), **info})
        return len(self.parts) - 1

    def tube(self, rings, mat: int, pid: int, caps=(False, False)) -> None:
        """Closed solid from rings (a 1-vertex ring is a point). Faces tagged with material + part."""
        bm = self.bm
        vr = [[bm.verts.new(p) for p in ring] for ring in rings]
        faces = []
        for a, b in zip(vr, vr[1:]):
            for i in range(max(len(a), len(b))):
                j = (i + 1) % max(len(a), len(b))
                quad = [a[0], b[j], b[i]] if len(a) == 1 else [a[i], a[j], b[0]] if len(b) == 1 else [a[i], a[j], b[j], b[i]]
                faces.append(bm.faces.new(quad))
        if caps[0]:
            faces.append(bm.faces.new(vr[0]))
        if caps[1]:
            faces.append(bm.faces.new(vr[-1][::-1]))
        self.tag(faces, mat, pid)

    def limb(self, pts: list[Vector], radii: list[float], pid: int, sides: int = 6) -> None:
        """Capped round tube along a spine (branch, twig, stub); an elbow in `pts` becomes a mitred bend."""
        rings = []
        for i, p in enumerate(pts):
            tan = (pts[min(i + 1, len(pts) - 1)] - pts[max(i - 1, 0)]).normalized()
            lat = tan.cross(Z)
            lat = lat.normalized() if lat.length > 1e-4 else Vector((1.0, 0.0, 0.0))
            up = lat.cross(tan)
            rings.append([p + (lat * math.cos(a) + up * math.sin(a)) * radii[i]
                          for a in (2 * math.pi * k / sides for k in range(sides))])
        self.tube(rings, SOLID, pid, caps=(True, True))

    # -- trunk, root ribs, stubs
    def add_trunk(self) -> None:
        r, sides = self.rng, 8
        zs = [-self.P["embed"], 0.0, 0.4, 0.9, 1.7, 2.8, 4.0, 5.2, 6.4, 7.6, 8.6, 9.8, 11.0, 12.2, 13.2, self.top]
        ja = [r.uniform(-0.12, 0.12) for _ in range(sides)]
        jr = [r.uniform(0.95, 1.05) for _ in range(sides)]
        rings = []
        for z in zs:
            rr, ax = self.radius(z), self.axis(z)
            ring = []
            for j in range(sides):
                a = 2 * math.pi * (j + ja[j]) / sides + 0.03 * z
                k = rr * jr[j] * (1.0 + 0.025 * math.sin(z * 1.3 + j * 1.7))
                ring.append(ax + Vector((math.cos(a) * k, math.sin(a) * k, 0.0)))
            rings.append(ring)
        self.tube(rings, SOLID, self.new_part("trunk"), caps=(True, True))

    def add_rib(self, az: float, reach: float, h0: float, hw: float) -> None:
        """Root rib: hump section on a spine that starts buried inside the trunk at h0 and runs out and down.
        Ring offsets are measured from the ground (z = 0), so the crest peaks at h0 and never outside the trunk."""
        emb, r0 = self.P["embed"], self.T["r0"]
        d = unit(az)
        lat = d.cross(Z)
        start = 0.72 * self.radius(h0)
        a0 = self.axis(0.0)
        rings = [[Vector((a0.x, a0.y, 0.0)) + d * (0.45 * start) + Z * (0.6 * h0)]]
        for t in (0.0, 0.10, 0.25, 0.45, 0.70, 1.0):
            zc = h0 * (1.0 - t) ** 1.8
            w = hw * (1.0 - 0.55 * t) * (0.80 + 0.20 * smoothstep(0.0, 0.3, t))
            ax = self.axis(zc)
            c = Vector((ax.x, ax.y, 0.0)) + d * lerp(start, reach * r0, t ** 0.85)
            rings.append([c + Z * zc, c + lat * (0.75 * w) + Z * (0.6 * zc), c + lat * w - Z * 0.08,
                          c - Z * (0.9 * emb), c - lat * w - Z * 0.08, c - lat * (0.75 * w) + Z * (0.6 * zc)])
        tip = a0 + d * (reach * r0 + 0.06)
        rings.append([Vector((tip.x, tip.y, -0.08))])
        self.tube(rings, SOLID, self.new_part("rib"))

    def add_ribs(self) -> None:
        T, r = self.T, self.rng
        az = r.uniform(0.0, 360.0)
        for k in range(T["ribs"]):
            az += 360.0 / T["ribs"] + r.uniform(-28.0, 28.0)
            self.add_rib(az, T["rib_reach"][k], T["rib_h"] * r.uniform(0.85, 1.15), T["rib_w"])

    def add_stubs(self) -> None:
        r = self.rng
        az = r.uniform(0.0, 360.0)
        for z, vis in self.T["stubs"]:
            az += 137.5 + r.uniform(-30.0, 30.0)
            pitch = math.radians(r.uniform(18.0, 40.0))
            d, R = unit(az), self.radius(z)
            length = vis + 0.35 * R / math.cos(pitch)
            start = self.axis(z) + d * (0.65 * R)
            pts = [start + d * (s * length * math.cos(pitch)) - Z * (s * length * math.sin(pitch)) for s in (0.0, 0.35, 0.7, 1.0)]
            rb = r.uniform(0.06, 0.075)
            self.limb(pts, [rb * k for k in (1.0, 0.82, 0.62, 0.45)], self.new_part("stub"), sides=5)

    # -- lateral arms: a gently curved run, one elbow (up-turn + sideways kink), optional forks
    def arm_path(self, a: dict):
        d = unit(a["az"])
        side = d.cross(Z)
        c0 = self.axis(a["z"]) + d * (0.45 * self.radius(a["z"]))
        L = a["reach"]
        at, up_deg, yaw_deg = a["elbow"]

        def pre(s: float) -> Vector:
            return c0 + d * (L * s) + side * (a["sway"] * s * s) + Z * (L * (a["s0"] * s + a["s1"] * s * s))
        pe = pre(at)
        te = pre(at + 1e-3) - pre(at - 1e-3)
        run = Vector((te.x, te.y, 0.0))
        d2 = Matrix.Rotation(math.radians(yaw_deg), 3, "Z") @ run.normalized()
        climb = te.z / run.length + math.tan(math.radians(up_deg))

        def pos(s: float) -> Vector:
            if s <= at:
                return pre(s)
            u = L * (s - at)
            return pe + d2 * u + Z * (climb * u + 0.5 * a["s1"] * u * u / L)
        return c0, pos, at

    def add_arm(self, a: dict) -> None:
        c0, pos, at = self.arm_path(a)
        ss = (0.0, 0.2, 0.4, at, 0.5 * (at + 1.0), 1.0)
        tip = pos(1.0)
        pid = self.new_part("arm", c0=c0, L=a["reach"] + 0.3, fr=self.root_flex(tip))
        radii = [max(a["r"] * (1.0 - 0.55 * s), 0.065) for s in ss] + [0.06]
        self.limb([pos(s) for s in ss] + [tip + Z * 0.3], radii, pid)
        for f in a["forks"]:
            self.add_fork(f, pos, a["az"])
        self.add_pad(tip, a["pad"], a["az"])

    def add_fork(self, f: dict, pos, arm_az: float) -> None:
        az = arm_az + f["turn"]
        d2 = unit(az)
        side = d2.cross(Z)
        p0 = pos(f["at"])
        bow = self.rng.uniform(-0.2, 0.2) * f["run"]

        def pos2(s: float) -> Vector:
            return p0 + d2 * (f["run"] * s) + side * (bow * s * s) + Z * (f["rise"] * (0.35 * s + 0.65 * s * s))
        ss = (0.0, 0.3, 0.6, 1.0)
        tip = pos2(1.0)
        pid = self.new_part("arm", c0=p0, L=f["run"] + 0.3, fr=self.root_flex(tip))
        self.limb([pos2(s) for s in ss] + [tip + Z * 0.3], [max(f["r"] * (1.0 - 0.45 * s), 0.065) for s in ss] + [0.055], pid, sides=5)
        self.add_pad(tip, f["pad"], az)

    def build(self) -> None:
        self.add_trunk()
        self.add_ribs()
        self.add_stubs()
        for a in self.P["arms"]:
            self.add_arm(a)
        L = self.P["leader"]
        ax = self.axis(L["z_b"])
        self.add_pad(Vector((ax.x + L["off"][0], ax.y + L["off"][1], L["z_b"] + 0.08)), L["pad"], L["out"], z_b=L["z_b"])

    # -- shading normals, painting (linear rgb + flex alpha; UV2 cavity + part random)
    def radial_normal(self, part: dict, co: Vector) -> Vector:
        """Smooth lobe normal: ellipsoid gradient, lifted upward so undersides do not go black."""
        rad, rot = part["r"], part["rot"]
        loc = rot.inverted() @ (co - part["c"])
        n = rot @ Vector((loc.x / rad[0] ** 2, loc.y / rad[1] ** 2, loc.z / rad[2] ** 2))
        n = n.normalized() if n.length > 1e-6 else Z.copy()
        return (n + Z * 0.18).normalized()

    def shade_normal(self, part: dict, poly, co: Vector) -> Vector:
        """Bark stays flat; lobes are mostly flat-faceted with a little smoothing; tufts flat with a small lift."""
        if part["kind"] == "lobe":
            return (self.radial_normal(part, co) * (1.0 - FACET) + poly.normal * FACET).normalized()
        if part["kind"] == "tuft":
            return (poly.normal + Z * 0.15).normalized()
        return poly.normal.copy()

    def bark_color(self, co: Vector) -> tuple:
        ax = self.axis(co.z)
        col = round((math.atan2(co.y - ax.y, co.x - ax.x) - 0.03 * co.z) / (2 * math.pi / 8)) % 8
        a = co.z / 3.0
        k, fr = math.floor(a), a - math.floor(a)
        noise = lerp(hash01(col, k), hash01(col, k + 1), smoothstep(0.0, 1.0, fr))
        tone = 0.6 * noise + 0.4 * hash01(col, 77)
        c = nl.mix(BARK_LO, BARK_MID, tone / 0.45) if tone < 0.45 else nl.mix(BARK_MID, BARK_HI, (tone - 0.45) / 0.55)
        warm = smoothstep(1.2, 8.5, co.z)   # grey-brown, darker foot -> orange-brown upper trunk
        foot = nl.scale_rgb(nl.mix(BARK_FOOT, c, 0.18 + 0.22 * tone), lerp(0.80, 0.92, smoothstep(-0.3, 1.5, co.z)))
        return nl.mix(foot, nl.scale_rgb(nl.mix(c, BARK_HI, 0.25), 1.02), warm)

    def pad_color(self, part: dict, poly, co: Vector) -> tuple:
        pad = self.parts[part["pad"]]
        up = clamp(poly.normal.z * 1.25)   # per-face, so the brush facets also read in colour
        sm = smoothstep(-0.5, 0.9, self.radial_normal(part, co).z) if part["kind"] == "lobe" else up
        hor = math.hypot(co.x - pad["c"].x, co.y - pad["c"].y) / pad["ext"]
        t = clamp(0.80 * (0.6 * up + 0.4 * sm) + 0.14 * clamp(hor * 1.2))
        base = nl.scale_rgb(nl.mix(nl.mix(PINE_DEEP, PINE_MID, pad["tone"]), COOL, 0.36), pad["val"] * (1.0 + part.get("dv", 0.0)))
        base = (base[0] * (0.96 + 0.10 * pad["warm"]), base[1], base[2] * (1.10 - 0.14 * pad["warm"]))   # cool cast + per-pad hue
        lo = nl.scale_rgb(base, 0.78)
        hi = nl.scale_rgb(nl.mix(base, PINE_TIP, pad["tip"]), 0.98)
        if part["kind"] == "tuft":
            u = clamp((co - part["c0"]).length / part["L"])
            return (*nl.mix(nl.mix(lo, hi, t), PINE_TIP, 0.18 * u), 0.55 + 0.45 * u)
        w = clamp(hor + 0.3 * (co.z - pad["zb"]) / pad["thick"])
        return (*nl.mix(lo, hi, t), pad["fr"] + (1.0 - pad["fr"]) * smoothstep(0.2, 0.85, w))

    def color(self, part: dict, poly, co: Vector) -> tuple:
        kind = part["kind"]
        if kind == "trunk":
            return (*self.bark_color(co), 0.0)
        if kind == "rib":
            up = clamp(poly.normal.z)
            return (*nl.scale_rgb(nl.mix(BARK_FOOT, BARK_LO, 0.4 + 0.6 * up), lerp(0.88, 1.02, smoothstep(-0.2, 0.5, co.z))), 0.0)
        if kind == "stub":
            return (*nl.scale_rgb(nl.mix(nl.pal("deadwood"), nl.pal("wood_exposed"), 0.25 * part["rand"]), lerp(0.85, 1.05, part["rand"])), 0.0)
        if kind == "arm":
            u = clamp((co - part["c0"]).length / part["L"])
            return (*nl.scale_rgb(nl.mix(BARK_MID, BARK_HI, 0.3 + 0.5 * u), lerp(0.88, 1.0, part["rand"])), part["fr"] * u ** 1.2)
        return self.pad_color(part, poly, co)

    def data(self, part: dict, poly, co: Vector) -> tuple:
        kind = part["kind"]
        if kind == "lobe":
            pad = self.parts[part["pad"]]
            cav = 0.62 + 0.38 * smoothstep(-0.7, 0.6, self.radial_normal(part, co).z)
            return (clamp(cav, 0.55, 1.0), clamp(pad["rand"] * 0.88 + part["rand"] * 0.12))
        if kind == "tuft":
            return (0.86, clamp(self.parts[part["pad"]]["rand"] * 0.88 + part["rand"] * 0.12))
        cav = {"trunk": 0.92 - 0.12 * smoothstep(8.0, 10.5, co.z) - 0.1 * (1.0 - smoothstep(0.0, 1.0, co.z)),
               "rib": 0.74 + 0.2 * clamp(poly.normal.z), "stub": 0.9, "arm": 0.78}[kind]
        return (clamp(cav, 0.55, 1.0), part["rand"])
