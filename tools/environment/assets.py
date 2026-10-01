"""Asset registry: assets/nature/*/*.json metadata (contract: assets/nature/README.md) plus the
existing spruce library (spruce_trees/models/variants.json). Missing assets are simply absent;
callers skip and report them.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from common import ROOT, load_json, sha1_file

NATURE = ROOT / "assets" / "nature"
LIBRARY = ROOT / "spruce_trees" / "models"
ROCK_FAMILIES = {"rock_shelf", "boulder_large", "boulder_medium", "rubble_cluster", "cliff_face",
                 "cliff_corner", "shore_boulder"}
LIBRARY_SCALE = (0.9, 1.3)
LIBRARY_SINK = 0.2
MATURE_SINK = 0.25
TRUNK_CLEARANCE_M = 1.0  # walkable space kept around mature trunks (spacing radius)


@dataclass(frozen=True)
class Asset:
    asset_id: str
    family: str
    group: str
    bbox_min: tuple[float, float, float]
    bbox_max: tuple[float, float, float]
    embed_depth: float
    scale_range: tuple[float, float]
    max_tilt_deg: float
    trunk_radius: float  # collision trunk radius (trees), else 0
    crown_base: float  # lowest foliage height (m, unscaled); 0 when unknown
    library: bool

    @property
    def is_tree(self) -> bool:
        return self.group == "trees" or self.library

    @property
    def is_rock(self) -> bool:
        return self.group == "rocks" or self.family in ROCK_FAMILIES

    @property
    def is_mature(self) -> bool:
        return self.family == "spruce_mature"

    @property
    def height(self) -> float:
        return self.bbox_max[1]

    @property
    def radius(self) -> float:
        """Footprint / crown envelope radius from the pivot in x/z (unscaled)."""
        return max(abs(self.bbox_min[0]), abs(self.bbox_max[0]), abs(self.bbox_min[2]),
                   abs(self.bbox_max[2]))

    @property
    def sink(self) -> float:
        return MATURE_SINK if self.is_mature else LIBRARY_SINK

    def spacing_radius(self, scale: float) -> float:
        """Radius used by variable-radius tree spacing (plan 8.3)."""
        if self.is_mature:
            return self.trunk_radius * scale + TRUNK_CLEARANCE_M
        return self.radius * scale * 0.7

    def envelope_radius(self, scale: float, clearance_height: float) -> float:
        """Horizontal reach of the tree below clearance_height (route crown-envelope test)."""
        if self.crown_base * scale >= clearance_height or (self.is_mature and self.crown_base == 0):
            return self.trunk_radius * scale + 0.5
        return self.radius * scale


def _nature_asset(meta: dict) -> Asset:
    coll = meta.get("collision", {})
    crown_base = float(meta.get("lowest_foliage_z", meta.get("crown_base_m", 0.0)))
    params = meta.get("recipe", {}).get("params", {})
    if not crown_base and "crown_start" in params and "height" in params:
        crown_base = float(params["crown_start"]) * float(params["height"])
    return Asset(meta["asset_id"], meta.get("family", ""), meta.get("group", ""),
                 tuple(meta["bbox_min"]), tuple(meta["bbox_max"]), float(meta.get("embed_depth", 0.0)),
                 tuple(meta.get("scale_range", [1.0, 1.0])), float(meta.get("max_tilt_deg", 0.0)),
                 float(coll.get("radius", 0.0)) if coll.get("class") == "trunk" else 0.0,
                 crown_base, False)


def _library_asset(v: dict) -> Asset:
    r = float(v["crown_radius_m"])
    h = float(v["height"])
    # The library has no measured trunk radius: ~3 % of height matches the S/M/L GLB trunks.
    fam = "dead_library" if v.get("kind") == "dead" else "spruce_library"
    return Asset(v["name"], fam, "trees", (-r, 0.0, -r), (r, h, r), 0.0, LIBRARY_SCALE, 0.0,
                 0.03 * h, float(v["lowest_foliage_z"]), True)


def load_assets() -> tuple[dict[str, Asset], dict[str, str]]:
    """Returns (asset_id -> Asset, input path -> sha1) for every metadata file read."""
    assets: dict[str, Asset] = {}
    shas: dict[str, str] = {}
    for p in sorted(NATURE.glob("*/*.json")):
        meta = load_json(p)
        if "asset_id" not in meta or not p.with_suffix(".glb").exists():
            continue
        assets[meta["asset_id"]] = _nature_asset(meta)
        shas[_rel(p)] = sha1_file(p)
    vpath = LIBRARY / "variants.json"
    if vpath.exists():
        shas[_rel(vpath)] = sha1_file(vpath)
        for v in load_json(vpath)["variants"]:
            if (LIBRARY / f"{v['name']}.glb").exists() and v["name"] not in assets:
                assets[v["name"]] = _library_asset(v)
    return assets, shas


def family_assets(assets: dict[str, Asset], family: str) -> list[str]:
    return sorted(a for a, m in assets.items() if m.family == family and not m.library)


def _rel(p: Path) -> str:
    return str(p.relative_to(ROOT))
