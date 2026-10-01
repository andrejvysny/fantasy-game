"""Placement pipeline (plan 8.2): inputs -> fields -> recipes -> trees -> canopy -> props -> groundcover.

Pure function of the input files: no time, no OS randomness, no dict-order dependence beyond
the JSON files themselves.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

import binfmt
from assets import Asset, load_assets
from bank_props import place_banks
from banks import bank_fields, bank_groundcover, bank_image
from cliffs import place_cliffs
from common import ROOT, TERRAIN_OUT, WORLD, hash_parts, load_json, sha1_bytes, sha1_file, str_hash, to_u32
from fields import compute_fields, load_terrain
from groundcover import field_images, groundcover
from props import place_props
from recipes import RecipeResult, resolve_recipes
from routes import Routes
from spatial import Exclusions, Inst, SpacingHash
from trees import canopy_raster, place_trees

ANCHORS = WORLD / "anchors" / "valley_anchors.json"
ROUTES = WORLD / "routes" / "valley_routes.json"
RECIPES = WORLD / "recipes" / "valley_recipes.json"
HABITATS = WORLD / "recipes" / "valley_habitats.json"
TERRAIN_FILES = ["heightmap.npy", "terrain_masks.npz", "splat_0.png", "splat_1.png", "splat_2.png", "splat.json"]


@dataclass
class Inputs:
    anchors: dict
    routes: dict
    recipes: dict
    habitats: dict
    assets: dict[str, Asset]
    shas: dict[str, str]
    revision: str
    seed: int


@dataclass
class Result:
    inputs: Inputs
    terrain: dict
    fields: dict
    routes: Routes
    excl: Exclusions
    recipes: RecipeResult
    instances: list[Inst]
    canopy: np.ndarray
    groundcover: dict[str, np.ndarray]
    images: dict[str, np.ndarray]
    skipped: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    rock_rejects: dict[str, int] = field(default_factory=dict)


def load_inputs() -> Inputs:
    shas = {str(p.relative_to(ROOT)): sha1_file(p) for p in [TERRAIN_OUT / n for n in TERRAIN_FILES]}
    for p in (ANCHORS, ROUTES, RECIPES, HABITATS):
        shas[str(p.relative_to(ROOT))] = sha1_file(p)
    assets, asset_shas = load_assets()
    shas.update(asset_shas)
    anchors = load_json(ANCHORS)
    habitats = load_json(HABITATS)
    revision = f"{anchors['terrain_revision']} + habitats {_seed_sha(habitats)[:10]}"
    return Inputs(anchors, load_json(ROUTES), load_json(RECIPES), habitats, assets,
                  dict(sorted(shas.items())), revision, str_hash("revision:" + revision))


def _seed_sha(habitats: dict) -> str:
    """sha1 of the habitats JSON as written (indent 2) without its 'banks' section. Equals the
    file sha1 when the file has no 'banks'; bank tuning thus never re-seeds trees or props."""
    core = {k: v for k, v in habitats.items() if k != "banks"}
    return sha1_bytes(json.dumps(core, indent=2).encode())


def _exclusions(zones: list[dict]) -> Exclusions:
    ex = Exclusions()
    for zn in zones:
        for p in zn.get("protected", []):
            if p.get("kind") == "spawn" and "clear_radius" in p:
                ex.spawns.append((float(p["at"][0]), float(p["at"][1]), float(p["clear_radius"])))
        for c in zn.get("view_corridors", []):
            ex.corridors.append((tuple(c["from"]), tuple(c["to"]), float(c["width"])))
    return ex


def _shore_families(props: dict) -> set[str]:
    return {k for k, r in props.items() if r.get("shore_distance_m", [0])[0] < 0}


def _solids(ctx: dict, locked: list[Inst], trees: list[Inst]) -> None:
    assets = ctx["assets"]
    ctx["solid"] = SpacingHash(8.0)
    for tr in trees + [i for i in locked if assets[i.asset].is_tree]:
        ctx["solid"].add(tr.x, tr.z, assets[tr.asset].trunk_radius * tr.scale + 0.1, 0.0)
    for i in locked:
        a = assets[i.asset]
        ctx["family_hash"].setdefault(a.family, SpacingHash(8.0)).add(i.x, i.z, i.radius, 0.0)
        if a.is_rock or a.family == "fallen_log":
            ctx["solid"].add(i.x, i.z, i.radius * 0.9, 0.0)
            (ctx["solids_rock"] if a.is_rock else ctx["logs"]).append(i)


def _unique_ids(insts: list[Inst], warnings: list[str]) -> None:
    """Resolve 32-bit id collisions deterministically (locked recipe ids keep theirs)."""
    order = sorted(range(len(insts)), key=lambda k: (not insts[k].locked, insts[k].source, insts[k].iid,
                                                      insts[k].x, insts[k].z))
    seen: set[int] = set()
    for k in order:
        inst = insts[k]
        salt = 0
        while inst.iid in seen:
            salt += 1
            inst.iid = int(to_u32(hash_parts(inst.iid, str_hash("collision"), salt)))
        if salt:
            warnings.append(f"id collision resolved: {inst.source} {inst.asset} -> {inst.iid}")
        seen.add(inst.iid)


def run(inp: Inputs) -> Result:
    t = load_terrain()
    routes = Routes(inp.routes)
    f = compute_fields(t, inp.habitats["habitat_field"], routes)
    banks_cfg = inp.habitats.get("banks") or {}
    bank_fields(t, f, banks_cfg.get("field"))
    zones = inp.anchors["zones"]
    excl = _exclusions(zones)
    rec = resolve_recipes(inp.recipes, inp.assets, t, f, zones)
    shore = _shore_families(inp.habitats.get("props", {}))
    for i in rec.instances:
        i.allow_water = inp.assets[i.asset].family in shore
    excl.reserves = rec.reserves
    skipped = [dict(s) for s in rec.skipped]
    ctx = {"t": t, "f": f, "assets": inp.assets, "seed": inp.seed, "zones": zones, "routes": routes,
           "excl": excl, "skipped": skipped, "rules": inp.habitats.get("trees", {}), "patches": rec.patches,
           "family_hash": {}, "solids_rock": [], "logs": [], "densities": {},
           "rock_rejects": Counter()}
    trees = place_trees(ctx, rec.instances)
    canopy = canopy_raster(trees + [i for i in rec.instances if inp.assets[i.asset].is_tree], inp.assets)
    ctx["canopy"], ctx["trees"] = canopy, trees
    _solids(ctx, rec.instances, trees)
    props = place_props(ctx, inp.habitats.get("props", {}))
    ctx["recipe_insts"] = rec.instances
    cliffs, cliff_rejects = place_cliffs(ctx, inp.habitats.get("cliff_dressing"))
    ctx["rock_rejects"].update(cliff_rejects)
    banks, bank_rejects = place_banks(ctx, banks_cfg, rec.instances + trees + props + cliffs)
    ctx["rock_rejects"].update(bank_rejects)
    fern_rule = inp.habitats.get("props", {}).get("fern", {})
    fern_peak = max([float(v) for v in fern_rule.get("habitats", {}).values()] or [1.0])
    gc = groundcover(inp.habitats.get("fields", {}), f, rec.patches, ctx["densities"].get("fern"), fern_peak)
    bank_groundcover(gc, f, banks_cfg)
    images = field_images(gc, f, canopy)
    bank_rgba = bank_image(f, banks_cfg)
    if bank_rgba is not None:
        images["bank"] = bank_rgba
    insts = rec.instances + trees + props + cliffs + banks
    warnings: list[str] = []
    _unique_ids(insts, warnings)
    return Result(inp, t, f, routes, excl, rec, insts, canopy, gc, images, _dedupe(skipped), warnings,
                  dict(sorted(ctx["rock_rejects"].items())))


def _dedupe(skipped: list[dict]) -> list[dict]:
    seen, out = set(), []
    for s in skipped:
        k = tuple(sorted(s.items()))
        if k not in seen:
            seen.add(k)
            out.append(s)
    return out


def group_files(insts: list[Inst]) -> dict[str, dict[str, bytes]]:
    """zone -> asset -> encoded VPL1 bytes."""
    by: dict[str, dict[str, list[Inst]]] = {}
    for i in insts:
        by.setdefault(i.zone, {}).setdefault(i.asset, []).append(i)
    return {z: {a: binfmt.encode(binfmt.rows_of(v)) for a, v in sorted(assets.items())}
            for z, assets in sorted(by.items())}


def digest(files: dict[str, dict[str, bytes]], images: dict[str, np.ndarray]) -> str:
    h = hashlib.sha1()
    for z, assets in files.items():
        for a, data in assets.items():
            h.update(f"{z}/{a}".encode())
            h.update(data)
    for n in sorted(images):
        h.update(n.encode())
        h.update(np.ascontiguousarray(images[n]).tobytes())
    return h.hexdigest()


def rel(p: Path) -> str:
    return str(p.relative_to(ROOT))
