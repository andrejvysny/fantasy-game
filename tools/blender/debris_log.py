"""fallen_log_A geometry (plan 5.3), built from the PARAMS in debris_family.py.
One closed 10-sided shell along Blender X (front = -Y): tapered, barely bent in plan, flat underside sunk 0.1 m,
three long bark seams (groove + grouped bark_dark/bark_ridge), a dished rotted butt end (-X) and a one-sided torn
break (+X): pale stepped wood on the front, a long tongue with three flat shards on the back/top, dark heart.
"""
from __future__ import annotations

import math

import bmesh
from mathutils import Vector

from debris_mesh import DARK, HEART, LENS, MID, RIDGE, ROT, ROT_HEART, WOOD, X, Z, Builder, lerp, smoothstep


class LogGeom:
    """Axis, radius and ring positions of the log body (t = 0 rotted butt .. 1 snapped end)."""

    def __init__(self, P: dict, rng):
        self.P, self.N, self.K = P, P["sides"], P["rings"]
        self.ph = rng.uniform(0.0, 6.28)
        self.ja = [rng.uniform(-0.10, 0.10) for _ in range(self.N)]
        self.jr = [rng.uniform(0.95, 1.05) for _ in range(self.N)]

    def radius(self, t: float) -> float:
        P = self.P
        return lerp(P["r_butt"], P["r_top"], t ** 1.1) + P["butt_flare"] * max(0.0, 1.0 - t / 0.07) ** 2

    def axis(self, t: float) -> Vector:
        P = self.P
        y = -P["bend_y"] * math.sin(math.pi * t) - P["wobble_y"] * math.sin(2.3 * math.pi * t + self.ph)
        z = -P["underside"] + P["flat"] * self.radius(t) + P["lift"] * smoothstep(0.5, 1.0, t)
        return Vector(((t - 0.5) * P["length"], y, z))

    def theta(self, j: int) -> float:
        return 2.0 * math.pi * (j + self.ja[j]) / self.N

    def seam_w(self, k: int, k0: int, k1: int) -> float:
        """Groove weight at vertex ring k for a seam painted on face rings k0 .. k1 - 1 (ramps over two rings)."""
        return smoothstep(k0 - 1, k0 + 1, k) * (1.0 - smoothstep(k1 - 1, k1 + 1, k))

    def ring(self, k: int) -> list[Vector]:
        P, N = self.P, self.N
        t = k / self.K
        a, r = self.axis(t), self.radius(t)
        pts = []
        for j in range(N):
            m = self.jr[j] * (1.0 + 0.035 * math.sin(t * 9.0 + j * 1.7)) * (1.0 + 0.05 * math.sin(3.1 * t + self.ph))
            for sj, k0, k1, depth in P["seams"]:
                w = self.seam_w(k, k0, k1)
                off = (j - sj + N // 2) % N - N // 2
                if off == 0:
                    m *= 1.0 - depth * w
                elif abs(off) == 1:
                    m *= 1.0 + 0.55 * depth * w
            th = self.theta(j)
            pts.append(Vector((a.x, a.y + math.cos(th) * r * 1.04 * m,
                               max(a.z + math.sin(th) * r * 0.97 * m, a.z - P["flat"] * r))))
        return pts

    def face_tone(self, j: int, k: int) -> int:
        """Colour class of body face (column j, ring k): lens, then seams (lower groove wall DARK, upper wall RIDGE
        on all but the end rings), else MID."""
        N = self.N
        if (j, k) in self.P["lens"]:
            return LENS
        for sj, k0, k1, _ in self.P["seams"]:
            if not k0 <= k < k1:
                continue
            lo, hi = sorted(((sj - 1) % N, sj), key=lambda f: math.sin(2.0 * math.pi * (f + 0.5) / N))
            if j == lo:
                return DARK
            if j == hi and k0 + 1 <= k < k1 - 1:
                return RIDGE
        return MID


def butt_end(b: Builder, g: LogGeom, ring0: list) -> None:
    """Rotted end: ragged bark lip, dished weathered face with broken-away chunks, small dark core. Never flat."""
    P, a = g.P["butt"], g.axis(0.0)
    pl, pf = b.new_part("butt_shell"), b.new_part("butt_face")
    lip, face, core = [], [], []

    def at(v, x: float, k: float):
        return b.vert(Vector((x, a.y + (v.co.y - a.y) * k, a.z + 0.03 + (v.co.z - a.z) * k)))

    for j, v in enumerate(ring0):
        d = P["slant"] * (1.0 + math.cos(g.theta(j) - math.radians(P["slant_az"]))) + b.rng.uniform(0.0, P["jitter"])
        lip.append(at(v, a.x - d, 0.96))
        dish = P["dish"] + (P["chunk_depth"] if j in P["chunks"] else 0.0) + b.rng.uniform(-0.02, 0.03)
        face.append(at(v, a.x + dish, P["inner"]))
        core.append(at(v, a.x + P["heart"] + b.rng.uniform(-0.02, 0.02), P["core"]))
    centre = b.vert(Vector((a.x + P["heart"] + 0.04, a.y, a.z + 0.03)))
    n = g.N
    for j in range(n):
        k = (j + 1) % n
        b.face([ring0[j], ring0[k], lip[k], lip[j]], pl, DARK)
        b.face([lip[j], lip[k], face[k], face[j]], pf, ROT)
        b.face([face[j], face[k], core[k], core[j]], pf, ROT)
        b.face([core[j], core[k], centre], pf, ROT_HEART)


def wood_extent(g: LogGeom, th: float, step: float = 0.0) -> float:
    """How far the pale wood reaches past the last ring at azimuth th: short stepped break on the front, long tongue
    on the tear side (`tear_az`)."""
    P = g.P["break"]
    tongue = smoothstep(0.35, 0.95, math.cos(th - math.radians(P["tear_az"])))
    return P["front"] + step + P["tongue"] * tongue


def break_end(b: Builder, g: LogGeom, ring1: list) -> None:
    """One-sided tear: bark shell stops just short of the wood, wood face is stepped on the front and runs into a
    tongue on the back, with a recessed dark heart. The underside keeps the body's z so the end never floats."""
    P, a = g.P["break"], g.axis(1.0)
    ps, pf = b.new_part("break_shell", x1=a.x), b.new_part("break_face")
    lip, wood, core = [], [], []

    def at(v, x: float, k: float, dz: float = 0.0, keep_low: bool = False):
        dzv = v.co.z - a.z
        return b.vert(Vector((x, a.y + (v.co.y - a.y) * k, a.z + dz + (dzv if keep_low and dzv < 0.0 else dzv * k))))

    for j, v in enumerate(ring1):
        e = wood_extent(g, g.theta(j), P["steps"][j % len(P["steps"])]) + b.rng.uniform(-0.015, 0.015)
        lip.append(at(v, a.x + max(e - P["bark_set"], 0.03), 0.97, keep_low=True))   # underside stays on the body
        wood.append(at(v, a.x + e, P["inner"]))
        core.append(at(v, a.x + P["core_e"] + b.rng.uniform(-0.015, 0.015), P["core"], 0.03))
    centre = b.vert(Vector((a.x + P["core_e"] - 0.03, a.y, a.z + 0.04)))
    n = g.N
    for j in range(n):
        k = (j + 1) % n
        b.face([ring1[j], ring1[k], lip[k], lip[j]], ps, DARK)
        b.face([lip[j], lip[k], wood[k], wood[j]], pf, WOOD)
        b.face([wood[j], wood[k], core[k], core[j]], pf, WOOD)
        b.face([core[j], core[k], centre], pf, HEART)


def add_shards(b: Builder, g: LogGeom) -> None:
    """Flat torn slabs of the outer shell: bark on the outside, pale wood on the edges/inside; each rooted inside the
    trunk, leaning out slightly, ending in a blunt chisel. Sizes are unequal and all sit on the tear side."""
    a, r = g.axis(1.0), g.radius(1.0)
    for S in g.P["break"]["shards"]:
        th = math.radians(S["az"])
        radial, tang = Vector((0.0, math.cos(th), math.sin(th))), Vector((0.0, -math.sin(th), math.cos(th)))
        x_face = wood_extent(g, th)
        base = a + radial * (S["rho"] * r) + Z * 0.02
        pid, rings = b.new_part("shard"), []
        for sv, wm, tm in ((-0.35, 1.0, 1.0), (0.0, 1.0, 1.0), (0.45, 0.92, 0.9), (0.8, 0.7, 0.75), (1.0, 0.4, 0.6)):
            # splay turns each shard a little in the tear plane so they fan out instead of standing parallel
            c = (base + X * (x_face + S["length"] * sv) + radial * (S["lean"] * S["length"] * max(sv, 0.0) ** 1.4)
                 + tang * (S["splay"] * S["length"] * max(sv, 0.0) ** 1.4))
            hw, ht = 0.5 * S["width"] * wm, 0.5 * S["thick"] * tm
            cut = X * (S["cut"] if sv == 1.0 else 0.0)   # slanted chisel end: one edge reaches further
            rings.append([c - tang * hw - radial * ht, c + tang * hw - radial * ht + cut,
                          c + tang * hw + radial * ht + cut, c - tang * hw + radial * ht])
        b.tube(rings, pid, face_tones=[WOOD, WOOD, MID, WOOD], cap_tone=WOOD, caps=(True, True))


def add_stubs(b: Builder, g: LogGeom) -> None:
    for s in g.P["stubs"]:
        t = s["t"]
        a, r, th = g.axis(t), g.radius(t), math.radians(s["az"])
        radial = Vector((0.0, math.cos(th), math.sin(th)))
        al = math.radians(s["pitch"])
        d = (X * math.cos(al) + radial * math.sin(al)).normalized()
        length = s["length"] + 0.45 * r / math.sin(al)   # plus the buried part
        u = d.cross(Z)
        u = u.normalized() if u.length > 1e-3 else Vector((0.0, 1.0, 0.0))
        w = d.cross(u)
        rings = []
        for sv, m in zip((0.0, 0.3, 0.68, 1.0), (1.35, 1.0, 0.8, 0.62)):
            c = a + radial * (0.55 * r) + d * (length * sv)
            rings.append([c + d * (b.rng.uniform(0.0, 0.05) if sv == 1.0 else 0.0)
                          + (u * math.cos(q) + w * math.sin(q)) * s["r"] * m
                          for q in (math.tau * i / 5 for i in range(5))])
        rings.append([a + radial * (0.55 * r) + d * (length + 0.05)])   # splintered point, not a flat cut
        b.tube(rings, b.new_part("stub"), tones=s.get("tones", [MID, MID, ROT, WOOD]), caps=(True, False))


def log_stats(b: Builder, g: LogGeom) -> dict:
    """Numbers the review checks: straightness of the axis, body colour shares, seam lengths."""
    c0, c1 = g.axis(0.0), g.axis(1.0)
    chord = (c1 - c0).normalized()
    devs = []
    for k in range(g.K + 1):
        q = g.axis(k / g.K) - c0
        devs.append((q - chord * q.dot(chord)).length)
    tones = [g.face_tone(j, k) for k in range(g.K) for j in range(g.N)]
    n = float(len(tones))
    return {"max_axis_dev_m": round(max(devs), 3), "mid_share": round(tones.count(MID) / n, 3),
            "dark_share": round(tones.count(DARK) / n, 3), "ridge_share": round(tones.count(RIDGE) / n, 3),
            "lens_faces": tones.count(LENS), "seam_len_frac": [round((k1 - k0) / g.K, 2) for _, k0, k1, _ in g.P["seams"]]}


def build_log(P: dict) -> Builder:
    b = Builder(P["seed"])
    g = LogGeom(P, b.rng)
    K, N = g.K, g.N
    rings = [[b.vert(p) for p in g.ring(k)] for k in range(K + 1)]
    body = b.new_part("body")
    for k in range(K):
        for j in range(N):
            b.face([rings[k][j], rings[k][(j + 1) % N], rings[k + 1][(j + 1) % N], rings[k + 1][j]], body,
                   g.face_tone(j, k))
    butt_end(b, g, rings[0])
    break_end(b, g, rings[K])
    b.close_piece()
    add_stubs(b, g)
    add_shards(b, g)
    xs = [v.co.x for v in b.bm.verts]
    bmesh.ops.translate(b.bm, vec=(-0.5 * (min(xs) + max(xs)), 0.0, 0.0), verts=b.bm.verts)   # pivot at mid length
    b.stats = log_stats(b, g)
    return b
