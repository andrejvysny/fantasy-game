"""Maths helpers and the foliage-pad builder for pine_family.

A pad is a cloud of a few faceted dome lobes (flat underside, crisp rim edge, belly, domed top) whose satellites are
clustered on the pad's outward side, plus angular wedge tufts pointing out of the rim (spruce bough-tip language).
PadMixin expects the host to provide bm, layer, rng, new_part(), root_flex(), tube().
"""
from __future__ import annotations

import math

import bmesh
from mathutils import Matrix, Vector

Z = Vector((0.0, 0.0, 1.0))
# Lobe profile from the underside up to the top ring: (plan radius, height) fractions of the lobe size. The first ring
# is a shallow under-belly (faceted, flat-ish when seen from the ground), the second the crisp flat-underside rim.
LOBE_RINGS = ((0.52, -0.06), (0.94, 0.0), (1.0, 0.30), (0.80, 0.70), (0.44, 0.96))
FOLIAGE = 1


def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def smoothstep(a: float, b: float, x: float) -> float:
    t = clamp((x - a) / (b - a))
    return t * t * (3.0 - 2.0 * t)


def hash01(a: int, b: int) -> float:
    """Deterministic pseudo random 0..1 for bark strip noise."""
    return (math.sin(a * 127.1 + b * 311.7) * 43758.5453) % 1.0


def unit(az_deg: float) -> Vector:
    a = math.radians(az_deg)
    return Vector((math.cos(a), math.sin(a), 0.0))


def hermite(knots: list[tuple[float, float]], z: float) -> float:
    """C1 cubic through (z, value) knots with Catmull-Rom tangents; clamped outside the range."""
    z = clamp(z, knots[0][0], knots[-1][0])
    n = len(knots)
    i = max(k for k in range(n - 1) if knots[k][0] <= z)

    def tangent(k: int) -> float:
        a, b = knots[max(k - 1, 0)], knots[min(k + 1, n - 1)]
        return (b[1] - a[1]) / (b[0] - a[0])
    (z0, v0), (z1, v1) = knots[i], knots[i + 1]
    h, t = z1 - z0, (z - z0) / (z1 - z0)
    return ((2 * t**3 - 3 * t**2 + 1) * v0 + (t**3 - 2 * t**2 + t) * h * tangent(i)
            + (-2 * t**3 + 3 * t**2) * v1 + (t**3 - t**2) * h * tangent(i + 1))


class PadMixin:
    def add_pad(self, tip: Vector, spec: dict, out_az: float, z_b: float | None = None) -> None:
        """Pad whose flat base plane sits just under the branch tip (or at z_b), centred above it. `yaw` is relative
        to the outward azimuth, so pad orientation follows its arm."""
        r = self.rng
        R = spec["R"]
        h = 1.3 * R * spec["thick"]
        rx, ry = R * math.sqrt(spec["elong"]), R / math.sqrt(spec["elong"])
        z_b = tip.z - 0.08 if z_b is None else z_b
        base = Vector((tip.x, tip.y, z_b))
        rot = Matrix.Rotation(math.radians(out_az + spec["yaw"]), 3, "Z") @ Matrix.Rotation(math.radians(spec["tilt"]), 3, "Y")
        cid = self.new_part("pad", c=base + Z * (0.5 * h), ext=max(rx, ry) * 1.6, zb=z_b, tone=spec["tone"], tip=spec["tip"],
                            val=r.uniform(0.94, 1.06), warm=r.uniform(-1.0, 1.0), fr=self.root_flex(tip), thick=h, R=R)
        back = rot.inverted() @ unit(out_az)
        out = math.atan2(back.y, back.x)   # outward direction in the pad's own frame
        self.add_lobe(cid, base, (rx, ry, h), rot, spec["sides"])
        self.add_satellites(cid, base, (rx, ry, h), rot, out, spec)
        if spec["crest"]:
            ang = r.uniform(0.0, math.tau)
            off = Vector((math.cos(ang) * rx * r.uniform(0.10, 0.30), math.sin(ang) * ry * r.uniform(0.10, 0.30), 0.52 * h))
            k = r.uniform(0.46, 0.56)
            rc = rot @ Matrix.Rotation(r.uniform(-0.5, 0.5), 3, "Z")
            self.add_lobe(cid, base + rot @ off, (rx * k, ry * k, h * 0.62), rc, 8)
        self.add_tufts(cid, base, (rx, ry, h), rot, out, spec)

    def add_satellites(self, cid: int, base: Vector, size: tuple, rot: Matrix, out: float, spec: dict) -> None:
        """Smaller lobes on the outward side only (never evenly ringed), their undersides near the pad's base plane."""
        r, (rx, ry, h) = self.rng, size
        n = spec["n"] - 1 - (1 if spec["crest"] else 0)
        for i in range(n):
            u = 2.0 * (i + 0.5) / n - 1.0 + r.uniform(-0.3, 0.3) / n
            ang = out + math.radians(spec["spread"]) * u
            f, k = r.uniform(0.50, 0.72), r.uniform(0.62, 0.84)
            off = Vector((math.cos(ang) * rx * k, math.sin(ang) * ry * k, r.uniform(0.0, 0.12)))
            rs = rot @ Matrix.Rotation(math.radians(r.uniform(-35.0, 35.0)), 3, "Z")
            self.add_lobe(cid, base + rot @ off, (rx * f, ry * f * r.uniform(0.9, 1.15), h * r.uniform(0.62, 0.92)), rs, 8)

    def add_lobe(self, cid: int, base: Vector, size: tuple, rot: Matrix, sides: int) -> None:
        """Closed dome: flat underside fan, then LOBE_RINGS, then a top fan. Plan outline is lumpy and per-vertex jittered
        so the planes come out unequal (broad faceted brushwork, not a sphere)."""
        r, bm = self.rng, self.bm
        rx, ry, h = size
        pid = self.new_part("lobe", pad=cid, c=base + rot @ Vector((0.0, 0.0, 0.5 * h)), r=(rx, ry, 0.55 * h), rot=rot,
                            dv=r.uniform(-0.05, 0.05))
        a0, a2, a3 = (r.uniform(0.0, math.tau) for _ in range(3))
        sk = (r.uniform(-0.18, 0.18) * rx, r.uniform(-0.18, 0.18) * ry)   # dome drifts off-centre: lopsided top
        ang = [a0 + math.tau * (j + r.uniform(-0.2, 0.2)) / sides for j in range(sides)]
        rings = []
        for rho, eta in LOBE_RINGS:
            ring = []
            for th in ang:
                w = (1.0 + 0.10 * math.sin(2 * th + a2) + 0.07 * math.sin(3 * th + a3)) * r.uniform(0.92, 1.08)
                z = eta * h * r.uniform(0.85, 1.15) if eta < 0.0 else eta * h * (r.uniform(0.95, 1.05) if eta > 0.0 else 1.0)
                q = Vector((math.cos(th) * rx * rho * w + sk[0] * eta * eta, math.sin(th) * ry * rho * w + sk[1] * eta * eta, z))
                ring.append(bm.verts.new(base + rot @ q))
            rings.append(ring)
        bottom = bm.verts.new(base + rot @ Vector((0.0, 0.0, -0.11 * h)))
        top = bm.verts.new(base + rot @ Vector((sk[0], sk[1], h)))
        faces = []
        for j in range(sides):
            k = (j + 1) % sides
            faces.append(bm.faces.new([rings[0][k], rings[0][j], bottom]))
            faces.append(bm.faces.new([rings[-1][j], rings[-1][k], top]))
            for a, b in zip(rings, rings[1:]):
                faces.append(bm.faces.new([a[j], a[k], b[k], b[j]]))
        self.tag(faces, FOLIAGE, pid)

    def tag(self, faces: list, mat: int, pid: int) -> None:
        for f in faces:
            f.material_index = mat
            f[self.layer] = pid
        bmesh.ops.recalc_face_normals(self.bm, faces=faces)

    def add_tufts(self, cid: int, base: Vector, size: tuple, rot: Matrix, out: float, spec: dict) -> None:
        """Angular wedges pointing outward from the rim, each a different length and droop (spruce bough tips)."""
        r, (rx, ry, h) = self.rng, size
        n = spec["tufts"]
        up = (rot @ Z).normalized()
        for i in range(n):
            u = 2.0 * (i + 0.5) / n - 1.0 + r.uniform(-0.25, 0.25) / n
            ang = out + math.radians(spec["tuft_spread"]) * u
            nrm = rot @ Vector((math.cos(ang) / rx, math.sin(ang) / ry, 0.0))
            d = Vector((nrm.x, nrm.y, 0.0)).normalized()
            rim = base + rot @ Vector((math.cos(ang) * rx * 0.97, math.sin(ang) * ry * 0.97, r.uniform(0.22, 0.34) * h))
            L = r.uniform(0.70, 1.10) * (0.46 + 0.26 * spec["R"])
            drop = r.uniform(0.05, 0.40) * L
            roll = r.uniform(-0.55, 0.55)
            lat = d.cross(up).normalized()
            up_t = (up * math.cos(roll) - lat * math.sin(roll)).normalized()
            lat = (lat * math.cos(roll) + up * math.sin(roll)).normalized()
            wd, th = L * r.uniform(0.36, 0.46), L * r.uniform(0.15, 0.20)
            stations = ((-0.35, 0.8, 1.0), (0.12, 1.0, 1.0), (0.55, 0.85, 0.8))
            rings = []
            for s, kw, kt in stations:
                p = rim + d * (s * L) - Z * (drop * max(s, 0.0))
                rings.append([p + up_t * th * kt, p + lat * wd * kw, p - up_t * th * 0.7 * kt, p - lat * wd * kw])
            rings.append([rim + d * L - Z * drop])
            pid = self.new_part("tuft", pad=cid, c0=rim - d * (0.35 * L), L=1.35 * L)
            self.tube(rings, FOLIAGE, pid, caps=(True, False))
