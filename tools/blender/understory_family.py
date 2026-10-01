"""Understory family (plan 5.4 / 5.7): shrub_A (round shrub), fern_A, shrub_B (spreading shrub, params in
understory_shrub_b.py) and reed_A (understory_reed.py). Blender 5.2, headless:

  Blender -b --factory-startup -P tools/blender/understory_family.py -- [shrub_A fern_A shrub_B reed_A]

Everything is built from PARAMS (finite, deterministic, written to metadata `recipe`).
Z-up metres, pivot at ground contact; grounded parts reach `embed` below z = 0 so slopes and
wind never expose an open rim. Per-vertex data travels through temporary bmesh layers
(nrm, pcol, cav, rnd) that are consumed by nl.paint / nl.paint_data and removed before export.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(globals().get("__file__", "tools/blender/x.py")).resolve().parent))

import bmesh  # noqa: E402
from mathutils import Matrix, Vector  # noqa: E402

import nature_lib as nl  # noqa: E402
import understory_reed as urd  # noqa: E402
import understory_shrub_b as usb  # noqa: E402

GROUP = "understory"
UP = Vector((0.0, 0.0, 1.0))
SOLID, FOLIAGE = nl.SOLID, nl.FOLIAGE

PARAMS = {
    "shrub_A": {
        "seed": 4107,
        "embed": 0.04,           # grounded lobe undersides and stub bases reach this far below z = 0
        "jitter": 0.16,          # low-frequency radial wobble of each lobe (fraction of radius)
        "vertex_noise": 0.16,    # per-vertex radius lumps, blended with neighbours (geometry only, never colour)
        "tufts": {2: 0, 3: 4},   # icosphere level -> vertices pushed out as soft nubs (dominant lobe only)
        "tuft_gain": 0.07,
        "boxiness": 0.98,        # 1 = ellipsoid; <1 drifts toward a rounded box (kept near 1: no facets)
        "lower_squash": 0.78,    # default flattening of a lobe's lower half (lobe "sq" overrides)
        "normal_up_bias": 0.18,  # mild lift of radial normals so undersides do not go black
        "highlight_mix": 0.4,    # how far a lobe's upper surface moves toward shrub_light
        # c = centre, r = radii, yaw/tilt = orientation (deg), sub = icosphere level (3 = 320 tris,
        # 2 = 80), sq = lower-half squash, k = value scale of the lobe's palette green, wob = wobble.
        # Undersides sit at c.z - r.z * sq: the dominant lobe is the only one that reaches the ground
        # (narrow contact), every other lobe is lifted ~0.10 m and rests on a bark stub.
        "lobes": [
            {"c": (0.18, -0.02, 0.3), "r": (0.4, 0.42, 0.46), "yaw": 55, "tilt": 8, "sub": 3, "sq": 0.85, "col": "shrub", "k": 0.96, "wob": 0.75},   # dominant
            {"c": (-0.26, 0.08, 0.63), "r": (0.26, 0.28, 0.28), "yaw": 60, "tilt": -10, "sub": 2, "sq": 0.78, "col": "shrub_light", "k": 1.1, "wob": 0.7},   # crest
            {"c": (-0.36, 0.16, 0.27), "r": (0.29, 0.26, 0.24), "yaw": -35, "tilt": 12, "sub": 2, "sq": 0.7, "col": "shrub_deep", "k": 0.8, "wob": 1},
            {"c": (0.46, 0.14, 0.26), "r": (0.27, 0.25, 0.23), "yaw": 50, "tilt": -10, "sub": 2, "sq": 0.7, "col": "shrub", "k": 1.05, "wob": 1},
            {"c": (0.26, -0.32, 0.27), "r": (0.29, 0.24, 0.23), "yaw": -25, "tilt": 15, "sub": 2, "sq": 0.7, "col": "shrub_light", "k": 1, "wob": 1},
            {"c": (-0.18, -0.3, 0.28), "r": (0.28, 0.25, 0.23), "yaw": -18, "tilt": -8, "sub": 2, "sq": 0.7, "col": "shrub_deep", "k": 0.9, "wob": 1},
            {"c": (0.02, -0.22, 0.5), "r": (0.22, 0.2, 0.19), "yaw": 10, "tilt": 5, "sub": 2, "sq": 0.78, "col": "shrub", "k": 1.12, "wob": 0.9},   # shoulder
        ],
        # branch stubs: ground point near the shrub centre, top point inside a lifted lobe, base/top radius.
        # They slant out from the root crown like branches, so every lifted lobe visibly rests on one.
        "stems": [
            {"base": (-0.18, 0.12, 0.0), "top": (-0.32, 0.16, 0.25), "r0": 0.045, "r1": 0.030},
            {"base": (-0.12, -0.24, 0.0), "top": (-0.17, -0.29, 0.26), "r0": 0.045, "r1": 0.030},
            {"base": (0.20, -0.24, 0.0), "top": (0.25, -0.30, 0.25), "r0": 0.042, "r1": 0.030},
            {"base": (0.40, 0.10, 0.0), "top": (0.45, 0.13, 0.24), "r0": 0.042, "r1": 0.028},
        ],
        "stem_sides": 5,
    },
    "fern_A": {
        "seed": 4202,
        "crown_radius": 0.05, "crown_height": 0.06, "r0": 0.03,
        "embed": 0.03,           # crown base ring sits this far below z = 0
        # length = leaflet length / frond length at the largest pair, sweep = forward angle from
        # lateral, fold = lift above the frond plane, droop = tip drop / length, widest_at = where the
        # blade stops widening (rest is the pointed tip), overlap = base width / pair spacing (>1 merges
        # the pairs into one blade). Lanceolate size profile over the pairs: size_base at the first pair,
        # 1 at size_peak_u, size_tip at the last.
        "leaflet": {"length": 0.20, "sweep": 50, "fold": 10, "droop": 0.08, "widest_at": 0.55,
                    "shoulder": 0.90, "overlap": 1.2, "size_base": 0.42, "size_peak_u": 0.5, "size_tip": 0.35},
        "stipe_bare": 0.24,      # fraction of a frond without leaflets (dark stalk)
        "normal_up_blend": 0.5,
        "rachis_width": 0.03,
        # az = azimuth, len = arc length m, elev = start elevation above horizontal,
        # bend = total bend (deg) applied as s^pow (arches up/out, droops late), drift = sideways curl
        "fronds": [
            {"az": 49, "len": 0.85, "elev": 80, "bend": 125, "pow": 1.7, "groups": 6, "tone": 1.08, "shift": 0.15, "drift": 12},
            {"az": 226, "len": 0.83, "elev": 78, "bend": 123, "pow": 1.7, "groups": 6, "tone": 0.92, "shift": 0.05, "drift": -16},
            {"az": 291, "len": 0.81, "elev": 80, "bend": 127, "pow": 1.7, "groups": 6, "tone": 1.04, "shift": 0.25, "drift": 9},
            {"az": 131, "len": 0.70, "elev": 66, "bend": 105, "pow": 1.5, "groups": 6, "tone": 0.88, "shift": 0.10, "drift": -8},
            {"az": 8, "len": 0.62, "elev": 64, "bend": 100, "pow": 1.5, "groups": 5, "tone": 1.10, "shift": 0.20, "drift": 14},
            {"az": 172, "len": 0.48, "elev": 54, "bend": 88, "pow": 1.4, "groups": 4, "tone": 0.95, "shift": 0.00, "drift": -10},
            {"az": 328, "len": 0.42, "elev": 50, "bend": 82, "pow": 1.4, "groups": 4, "tone": 1.02, "shift": 0.30, "drift": 6},
        ],
    },
}
PARAMS.update({"shrub_B": usb.SHRUB_B, "reed_A": urd.REED_A})


# ---------------------------------------------------------------- helpers

def smooth(a: float, b: float, x: float) -> float:
    t = min(1.0, max(0.0, (x - a) / (b - a)))
    return t * t * (3.0 - 2.0 * t)


def clamp01(x: float) -> float:
    return min(1.0, max(0.0, x))


class Builder:
    """bmesh plus per-vertex data layers (normal, colour+flex, cavity, part random)."""

    def __init__(self, embed: float, foliage_slot: int) -> None:
        self.bm = bmesh.new()
        self.embed, self.fs = embed, foliage_slot  # fs = material slot of M_foliage
        lay = self.bm.verts.layers
        self.nrm = lay.float_vector.new("nrm")
        self.col = lay.float_color.new("pcol")
        self.cav = lay.float.new("cav")
        self.rnd = lay.float.new("rnd")

    def vert(self, p, rgb, flex: float, cav: float, rnd: float, normal=None):
        p = Vector(p)
        p.z = max(p.z, -self.embed)  # nothing reaches below the buried floor
        v = self.bm.verts.new(p)
        v[self.col] = (rgb[0], rgb[1], rgb[2], flex)
        v[self.cav], v[self.rnd] = cav, rnd
        if normal is not None:
            v[self.nrm] = normal
        return v

    def face(self, verts, mat: int, toward=None):
        """New face; winding flipped so its normal points along `toward` when given."""
        f = self.bm.faces.new(verts)
        f.material_index = mat
        if toward is not None and f.normal.dot(toward) < 0.0:
            f.normal_flip()
        return f

    def recentre(self) -> None:
        """Centre the footprint on the pivot (bounding box in x/y)."""
        xs = [v.co.x for v in self.bm.verts]
        ys = [v.co.y for v in self.bm.verts]
        off = Vector(((max(xs) + min(xs)) * 0.5, (max(ys) + min(ys)) * 0.5, 0.0))
        bmesh.ops.translate(self.bm, vec=-off, verts=list(self.bm.verts))


def apply_vertex_normals(obj) -> None:
    me = obj.data
    me.polygons.foreach_set("use_smooth", [True] * len(me.polygons))
    data = me.attributes["nrm"].data
    me.normals_split_custom_set_from_vertices([tuple(data[i].vector) for i in range(len(me.vertices))])
    me.update()


def finish(b: Builder, asset_id: str, materials: tuple[str, ...], meta_kw: dict) -> dict:
    """finalize -> unwrap -> custom normals -> COLOR_0 / UV2 -> export -> previews -> .blend."""
    obj = nl.mesh_object(asset_id, b.bm, materials)
    nl.finalize(obj)
    nl.uv_unwrap(obj)
    apply_vertex_normals(obj)
    me = obj.data
    col = [tuple(d.color) for d in me.color_attributes["pcol"].data]
    cav = [d.value for d in me.attributes["cav"].data]
    rnd = [d.value for d in me.attributes["rnd"].data]
    vid = [l.vertex_index for l in me.loops]
    loops = {}
    for p in me.polygons:
        for li in p.loop_indices:
            loops[li] = vid[li]
    nl.paint(obj, lambda poly, li, v: col[loops[li]])
    nl.paint_data(obj, lambda poly, li, v: (cav[loops[li]], rnd[loops[li]]))
    me.color_attributes.remove(me.color_attributes["pcol"])
    for name in ("nrm", "cav", "rnd"):
        me.attributes.remove(me.attributes[name])
    me.color_attributes.active_color = me.color_attributes[nl.COLOR_ATTR]
    meta = nl.export_asset(obj, GROUP, asset_id, **meta_kw)
    nl.render_previews(obj, GROUP, asset_id)
    nl.save_blend(GROUP, asset_id)
    return meta


# ---------------------------------------------------------------- shrub

def _lobe_colour(base, d: Vector, out: float, k: float, hl_mix: float):
    """Darker toward the underside, lighter toward the upper/outer surface (form, not sun)."""
    t = clamp01(0.75 * smooth(-0.6, 0.9, d.z) + 0.25 * out)
    lo = nl.scale_rgb(base, 0.84 * k)
    hi = nl.scale_rgb(nl.mix(base, nl.pal("shrub_light"), hl_mix), 1.07 * k)
    return nl.mix(lo, hi, t)


def _shrub_flex(p: Vector, top: float, span: float = 0.7) -> float:
    """0 at the ground -> ~0.5 at the top outer lobes; stems use the same field so they stay inside lobes."""
    out = clamp01(math.hypot(p.x, p.y) / span)
    return 0.5 * smooth(0.0, 1.0, max(p.z, 0.0) / top) * (0.85 + 0.15 * out)


def _lobe_radial(d: Vector, ph: list[float], jitter: float, bump: float, freq: float = 1.0) -> float:
    """Smooth direction-based radius wobble (asymmetric) plus a neighbour-smoothed per-vertex bump.
    freq > 1 packs more undulations onto the lobe (ragged rim)."""
    d = d * freq
    wob = (0.55 * math.sin(2.4 * d.x + ph[0]) * math.cos(2.0 * d.y + ph[1])
           + 0.35 * math.sin(3.0 * d.z + 1.5 * d.x + ph[2])
           + 0.30 * math.sin(4.3 * d.x - 3.1 * d.y + ph[3]))
    return 1.0 + jitter * wob + bump


def _soft_noise(verts, rnd, amp: float) -> dict:
    """Random per-vertex values blended with their 1-ring mean: lumps, never isolated pits/spikes
    (a pit shades as a dark dot under radial normals)."""
    raw = {v: rnd.uniform(-1.0, 1.0) for v in verts}
    out = {}
    for v in verts:
        nb = [e.other_vert(v) for e in v.link_edges]
        out[v] = amp * (0.4 * raw[v] + 0.6 * sum(raw[n] for n in nb) / len(nb))
    return out


def _tuft_gain(v, tuft: set, gain: float, sigma) -> float:
    if sigma is None:
        return gain if v in tuft else 0.0
    d = v.co.normalized()
    return gain * sum(math.exp(-(d.angle(t.co.normalized()) / sigma) ** 2) for t in tuft)


def _add_lobe(b: Builder, L: dict, P: dict, rnd, top: float) -> None:
    g = bmesh.ops.create_icosphere(b.bm, subdivisions=L["sub"], radius=1.0)
    verts = g["verts"]
    faces = {f for v in verts for f in v.link_faces}
    ph = [rnd.uniform(0.0, math.tau) for _ in range(4)]
    c, r, sq = Vector(L["c"]), L["r"], L["sq"]
    rot = Matrix.Rotation(math.radians(L["yaw"]), 3, "Z") @ Matrix.Rotation(math.radians(L["tilt"]), 3, "Y")
    base, k, part = nl.pal(L["col"]), L["k"], rnd.random()
    if L.get("moss"):
        base = nl.mix(base, nl.pal("moss"), L["moss"])
    span, cav_h = P.get("span", 0.7), P.get("cav_height", 0.42)
    n_tuft = P["tufts"][L["sub"]]
    tuft = set(rnd.sample([v for v in verts if v.co.normalized().z > -0.25], n_tuft)) if n_tuft else set()
    sigma = P.get("tuft_sigma")  # soft lumps: gaussian falloff (radians) instead of single-vertex nubs
    bump = _soft_noise(verts, rnd, L.get("vn", P["vertex_noise"]))
    wr = {v: _lobe_radial(v.co.normalized(), ph, P["jitter"] * L["wob"], bump[v], P.get("wob_freq", 1.0))
          * (1.0 + _tuft_gain(v, tuft, P["tuft_gain"], sigma)) for v in verts}
    for v in verts:  # no vertex may sit below its neighbours' mean: pits shade as dark dots
        nb = sum(wr[e.other_vert(v)] for e in v.link_edges) / len(v.link_edges)
        wr[v] = max(wr[v], nb - 0.02)
    for v in verts:
        d = v.co.normalized()
        w = wr[v]
        sz = sq if d.z < 0.0 else 1.0
        q = Vector([math.copysign(abs(x) ** P["boxiness"], x) for x in d])
        p = rot @ Vector((q.x * r[0] * w, q.y * r[1] * w, q.z * r[2] * sz * w)) + c
        p.z = max(p.z, -b.embed)
        n = rot @ Vector((d.x / r[0], d.y / r[1], d.z / (r[2] * sz)))
        n = (n.normalized() + UP * P["normal_up_bias"]).normalized()
        if "wall" in L:
            p, n = usb.wall_clamp(p, n, L["wall"])
        if "nref" in L:  # surface clumps shade mostly like the mass they sit on
            n = (n * (1.0 - L["nb"]) + Vector(L["nref"]) * L["nb"]).normalized()
        if "mound" in P:
            n = usb.mound_blend(n, p, P["mound"])
        out = clamp01(math.hypot(p.x, p.y) / span)
        cav = 1.0 - 0.32 * (1.0 - smooth(0.0, cav_h, p.z)) - 0.07 * max(0.0, -d.z)
        v.co = p
        v[b.nrm] = n
        v[b.col] = (*_lobe_colour(base, d, out, k, P["highlight_mix"]), _shrub_flex(p, top, span))
        v[b.cav], v[b.rnd] = cav, part
    for f in faces:
        f.material_index = 1
    caps = [f for f in faces if all(v.co.z <= -b.embed + 1e-4 for v in f.verts)]
    bmesh.ops.delete(b.bm, geom=caps, context="FACES")  # flat underside stays buried


def _add_stem(b: Builder, S: dict, sides: int, part: float, top: float, span: float = 0.7) -> None:
    lo, hi = Vector(S["base"]), Vector(S["top"])
    lo.z = -b.embed
    axis = (hi - lo).normalized()
    e1 = axis.cross(UP).normalized()
    e2 = axis.cross(e1)
    bow = e1 * 0.03
    rings = []
    for i in range(3):
        u = i / 2.0
        centre = lo.lerp(hi, u) + bow * math.sin(math.pi * u)
        rad = S["r0"] + (S["r1"] - S["r0"]) * u
        rgb = nl.mix(nl.pal("bark_dark"), nl.pal("bark"), u)
        flex = _shrub_flex(centre, top, span)
        ring = []
        for k in range(sides):
            a = math.tau * k / sides
            off = e1 * math.cos(a) + e2 * math.sin(a)
            ring.append(b.vert(centre + off * rad, rgb, flex, 0.72, part, off))
        rings.append(ring)
    for ra, rb in zip(rings[:-1], rings[1:]):
        for k in range(sides):
            k2 = (k + 1) % sides
            quad = [ra[k], ra[k2], rb[k2], rb[k]]
            b.face(quad, 0, toward=sum((Vector(v[b.nrm]) for v in quad), Vector()))


def build_shrub(asset_id: str) -> dict:
    P = PARAMS[asset_id]
    rnd = nl.rng(P["seed"])
    b = Builder(P["embed"], foliage_slot=1)
    clumps = usb.clump_lobes(P) if "clumps" in P else []
    lobes = P["lobes"] + clumps
    top = max(L["c"][2] + L["r"][2] for L in lobes)
    for L in lobes:
        _add_lobe(b, L, P, rnd, top)
    for S in P["stems"]:
        _add_stem(b, S, P["stem_sides"], rnd.random(), top, P.get("span", 0.7))
    b.recentre()
    kw = dict(
        family="shrub", habitats=["forest_edge", "rock_foot", "meadow_edge"],
        collision={"class": "none"}, budget_tris=(250, 1000), scale_range=(0.7, 1.35),
        embed_depth=P["embed"], max_tilt_deg=8, wind="shrub",
        recipe={"seed": P["seed"], "params": P, **({"derived_clumps": clumps} if clumps else {})},
        notes="Round variant: 7 asymmetric lobes (dominant, crest, front shoulder, 4 lifted skirt lobes). Custom radial "
              "normals per lobe (+18% up). Only the dominant lobe touches the ground (narrow contact); the skirt lobes "
              "are lifted ~0.10 m and rest on 4 slanted bark stubs. Grounded undersides and stub bases reach 4 cm "
              "below y=0 (embed_depth).")
    kw.update({"shrub_B": usb.SHRUB_B_META}.get(asset_id, {}))
    return finish(b, asset_id, (SOLID, FOLIAGE), kw)


# ---------------------------------------------------------------- fern

def _frond_points(F: dict, P: dict, n_seg: int):
    """Rachis samples: (position, s, theta, phi) along an arching, late-drooping curve."""
    th0, bend = math.radians(F["elev"]), math.radians(F["bend"])
    phi0, drift = math.radians(F["az"]), math.radians(F["drift"])
    pos = Vector((math.cos(phi0), math.sin(phi0), 0.0)) * P["r0"]
    pts = [(pos.copy(), 0.0, th0, phi0)]
    ds = F["len"] / n_seg
    for i in range(1, n_seg + 1):
        s_mid, s = (i - 0.5) / n_seg, i / n_seg
        th = th0 - bend * s_mid ** F["pow"]
        phi = phi0 + drift * s_mid
        pos = pos + (Vector((math.cos(phi), math.sin(phi), 0.0)) * math.cos(th) + UP * math.sin(th)) * ds
        pts.append((pos.copy(), s, th0 - bend * s ** F["pow"], phi0 + drift * s))
    return pts


def _frame(th: float, phi: float):
    """Tangent T, upper-surface normal U, lateral S of a frond in its vertical plane."""
    R = Vector((math.cos(phi), math.sin(phi), 0.0))
    S = Vector((-math.sin(phi), math.cos(phi), 0.0))
    return R * math.cos(th) + UP * math.sin(th), -R * math.sin(th) + UP * math.cos(th), S


def _sample(pts, s: float):
    for (p0, s0, t0, f0), (p1, s1, t1, f1) in zip(pts[:-1], pts[1:]):
        if s <= s1 or s1 >= 1.0:
            u = clamp01((s - s0) / (s1 - s0))
            return p0.lerp(p1, u), t0 + (t1 - t0) * u, f0 + (f1 - f0) * u
    raise ValueError(s)


def _size(lf: dict, u: float) -> float:
    """Lanceolate profile: small basal pair, largest at size_peak_u, tapering to the last pair."""
    pk = lf["size_peak_u"]
    if u <= pk:
        return lf["size_base"] + (1.0 - lf["size_base"]) * math.sin(0.5 * math.pi * u / pk)
    return 1.0 - (1.0 - lf["size_tip"]) * smooth(pk, 1.0, u)


def _leaf_rgb(F: dict, u_frond: float, base_mix: float = 0.55):
    """fern_deep-tinted leaflet base, fern across it, fern_light toward tip / frond end."""
    fern, light = nl.pal("fern"), nl.pal("fern_light")
    mid = nl.mix(fern, light, F["shift"] + 0.35 * u_frond)
    return (nl.scale_rgb(nl.mix(nl.pal("fern_deep"), mid, base_mix), F["tone"]),
            nl.scale_rgb(mid, F["tone"]),
            nl.scale_rgb(nl.mix(mid, light, 0.45), F["tone"]))


def _lancet(b: Builder, lf: dict, F: dict, P0: Vector, D: Vector, B: Vector, U: Vector,
            ln: float, wb: float, s_att: float, part: float, base_mix: float = 0.55) -> None:
    """Pinna: base edge `wb` along B on the rachis, sides run forward to widest_at, then a
    pointed tip that droops slightly. Quad + triangle, no serration."""
    at = P0 + D * (ln * lf["widest_at"])
    wd = wb * lf["shoulder"]
    pos = [P0 - B * (wb * 0.5), P0 + B * (wb * 0.5), at + B * (wd * 0.5), at - B * (wd * 0.5),
           P0 + D * ln - U * (lf["droop"] * ln)]
    rgbs = _leaf_rgb(F, s_att, base_mix)
    vs = []
    for p, ti in zip(pos, [0, 0, 1, 1, 2]):
        s_v = clamp01(s_att + 0.3 * (p - P0).length / F["len"])
        cav = 0.68 + 0.32 * smooth(0.0, 0.45, s_v) - (0.06 if ti == 0 else 0.0)
        vs.append(b.vert(p, rgbs[ti], s_v ** 1.15, cav, part))
    b0, b1, r_, l_, t_ = vs
    b.face([b0, b1, r_, l_], b.fs, toward=U)
    b.face([l_, r_, t_], b.fs, toward=U)


def _rachis_ribbon(b: Builder, P: dict, F: dict, pts, part: float) -> None:
    ribbon = []
    for p, s, th, phi in pts:
        T, U, S = _frame(th, phi)
        w = P["rachis_width"] * (1.0 - 0.6 * s) * 0.5
        rgb = nl.scale_rgb(nl.mix(nl.pal("fern_deep"), nl.pal("fern"), 0.45 * s), F["tone"])
        cav = 0.72 + 0.25 * s
        ribbon.append((b.vert(p - S * w, rgb, s ** 1.15, cav, part),
                       b.vert(p + S * w, rgb, s ** 1.15, cav, part), U))
    for (l0, r0, U0), (l1, r1, _) in zip(ribbon[:-1], ribbon[1:]):
        b.face([l0, r0, r1, l1], b.fs, toward=U0)


def _add_frond(b: Builder, P: dict, F: dict, rnd, part: float) -> None:
    pts = _frond_points(F, P, 8 if F["len"] > 0.7 else 6)
    lf, g, L = P["leaflet"], F["groups"], F["len"]
    _rachis_ribbon(b, P, F, pts, part)
    s0, s1 = P["stipe_bare"], 0.9
    ss = [s0 + (s1 - s0) * (1.0 - (1.0 - j / (g - 1)) ** 1.2) for j in range(g)]  # crowd toward tip
    for j, s in enumerate(ss):
        size = _size(lf, j / (g - 1))
        gap = ss[min(j + 1, g - 1)] - ss[max(j - 1, 0)]
        wb = L * gap / (2.0 if 0 < j < g - 1 else 1.0) * lf["overlap"]
        for side in (1.0, -1.0):
            p, th, phi = _sample(pts, clamp01(s + side * 0.1 * wb / L))  # pairs are not quite opposite
            T, U, S = _frame(th, phi)
            sw = math.radians(lf["sweep"] + rnd.uniform(-4.0, 4.0))
            D = (S * side * math.cos(sw) + T * math.sin(sw) + U * math.sin(math.radians(lf["fold"]))).normalized()
            ln = L * lf["length"] * size * (0.93 + 0.14 * rnd.random())
            _lancet(b, lf, F, p, D, T, U, ln, wb, s, part)
    p, th, phi = pts[-1][0], pts[-1][2], pts[-1][3]
    T, U, S = _frame(th, phi)
    ln = L * lf["length"] * lf["size_tip"] * 1.6  # terminal blade continues the rachis
    _lancet(b, dict(lf, droop=0.0), F, p, T, S, U, ln, ln * 0.34, 1.0, part, base_mix=1.0)


def _add_crown(b: Builder, P: dict) -> None:
    rgb = nl.pal("fern_deep")
    sides, r, h = 6, P["crown_radius"], P["crown_height"]
    ring0 = [b.vert((r * math.cos(a), r * math.sin(a), -P["embed"]), rgb, 0.0, 0.7, 0.5)
             for a in (math.tau * k / sides for k in range(sides))]
    ring1 = [b.vert((r * 1.05 * math.cos(a), r * 1.05 * math.sin(a), h * 0.55), rgb, 0.0, 0.75, 0.5)
             for a in (math.tau * k / sides for k in range(sides))]
    apex = b.vert((0.0, 0.0, h), rgb, 0.0, 0.85, 0.5)
    for k in range(sides):
        k2 = (k + 1) % sides
        b.face([ring0[k], ring0[k2], ring1[k2], ring1[k]], b.fs, toward=ring0[k].co + ring0[k2].co)
        b.face([ring1[k], ring1[k2], apex], b.fs, toward=ring1[k].co + ring1[k2].co + UP)


def _smooth_fern_normals(b: Builder, blend: float) -> None:
    b.bm.normal_update()
    for v in b.bm.verts:
        n = sum((f.normal for f in v.link_faces), Vector()).normalized()
        v[b.nrm] = (n * (1.0 - blend) + UP * blend).normalized()


def build_fern(asset_id: str) -> dict:
    P = PARAMS[asset_id]
    rnd = nl.rng(P["seed"])
    b = Builder(P["embed"], foliage_slot=0)
    _add_crown(b, P)
    for F in P["fronds"]:
        _add_frond(b, P, F, rnd, rnd.random())
    _smooth_fern_normals(b, P["normal_up_blend"])
    return finish(b, asset_id, (FOLIAGE,), dict(
        family="fern", habitats=["mature_forest", "shaded_pocket", "log_side"],
        collision={"class": "none"}, budget_tris=(150, 500), scale_range=(0.75, 1.3),
        embed_depth=P["embed"], max_tilt_deg=10, wind="fern", recipe={"seed": P["seed"], "params": P},
        notes="7 fronds (3 dominant 0.8-0.85 m arc, 2 medium, 2 short; unequal azimuths). Each frond is one "
              "lanceolate feather blade: 4-6 swept leaflet pairs whose bases merge, small basal pair, largest "
              "at mid-frond. No tip points below ~-48 deg. Custom normals blended 50% toward +Z. Flex 0 at the "
              "crown, 1 at frond tips. Crown base ring sits 3 cm below y=0 (embed_depth)."))


# ---------------------------------------------------------------- reed

def build_reed(asset_id: str) -> dict:
    P = PARAMS[asset_id]
    b = Builder(P["embed"], foliage_slot=1)
    measured = urd.build_reed_mesh(b, P)
    root = [v.co for v in b.bm.verts if v.co.z < -P["embed"] + 1e-4]  # axis-aligned extent of the root ring
    mid = [v.co for v in b.bm.verts if 0.4 <= v.co.z <= 0.5]            # how far the clump has fanned out by mid-height
    ext = lambda pts: [round(max(c[i] for c in pts) - min(c[i] for c in pts), 3) for i in (0, 1)]  # noqa: E731
    perp = (-math.sin(math.radians(P["lean_dir_deg"])), math.cos(math.radians(P["lean_dir_deg"])))
    across = [v.x * perp[0] + v.y * perp[1] for v in mid]
    measured.update({"root_area_bbox_m": ext(root), "mid_height_extent_m": ext(mid),
                     "mid_height_width_across_lean_m": round(max(across) - min(across), 3), "blades": P["blades"],
                     "stalks": len(P["stalks"])})
    return finish(b, asset_id, (SOLID, FOLIAGE), dict(
        collision={"class": "none"}, embed_depth=P["embed"],
        recipe={"seed": P["seed"], "params": P, "measured": measured}, **urd.REED_A_META))


BUILDERS = {"shrub_A": build_shrub, "fern_A": build_fern, "shrub_B": build_shrub, "reed_A": build_reed}


def main() -> None:
    argv = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    for asset_id in argv or list(BUILDERS):
        nl.reset_scene()
        meta = BUILDERS[asset_id](asset_id)
        print(f"[understory] {asset_id}: tris={meta['tris']} within_budget={meta['within_budget']} "
              f"bbox_min={meta['bbox_min']} bbox_max={meta['bbox_max']} non_manifold={meta['non_manifold_edges']}")


if __name__ == "__main__":
    main()
