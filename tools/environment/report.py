"""Dry-run diff against world/generated, manifest assembly and the markdown report."""
from __future__ import annotations

from typing import TYPE_CHECKING

import json
import math
from collections import Counter
from pathlib import Path

import numpy as np

import binfmt
from common import GENERATED, OVERRIDES, ROOT, load_json, sha1_bytes, sha1_file
from routes import TURN_BAND_M

if TYPE_CHECKING:
    from generate import Result
    from validate import Validation

MOVE_EPS_M = 0.01
MOVE_EPS_DEG = 0.5


def existing_files(zones: list[str] | None = None) -> dict[str, dict[str, Path]]:
    """zone -> asset -> path for the currently published world/generated/*/*.bin."""
    out: dict[str, dict[str, Path]] = {}
    if not GENERATED.exists():
        return out
    for p in sorted(GENERATED.glob("*/*.bin")):
        z = p.parent.name
        if zones is None or z in zones:
            out.setdefault(z, {})[p.stem] = p
    return out


def _index(files: dict[str, dict[str, bytes]]) -> dict[int, tuple[str, str, np.void]]:
    idx = {}
    for z, assets in files.items():
        for a, data in assets.items():
            for row in binfmt.decode(data):
                idx[int(row["id"])] = (z, a, row)
    return idx


def diff(old: dict[str, dict[str, bytes]], new: dict[str, dict[str, bytes]]) -> dict:
    """added / moved / removed / preserved by id, totals and per zone/asset."""
    a, b = _index(old), _index(new)
    per: Counter = Counter()
    tot: Counter = Counter()
    for iid, (z, asset, row) in b.items():
        if iid not in a:
            kind = "added"
        else:
            oz, oa, orow = a[iid]
            dpos = math.dist((row["x"], row["y"], row["z"]), (orow["x"], orow["y"], orow["z"]))
            dyaw = abs(math.degrees(math.remainder(float(row["yaw"]) - float(orow["yaw"]), math.tau)))
            kind = "moved" if (dpos > MOVE_EPS_M or dyaw > MOVE_EPS_DEG or oa != asset or oz != z) else "preserved"
        tot[kind] += 1
        per[(z, asset, kind)] += 1
    for iid, (z, asset, _) in a.items():
        if iid not in b:
            tot["removed"] += 1
            per[(z, asset, "removed")] += 1
    return {"total": {k: tot[k] for k in ("added", "moved", "removed", "preserved")}, "per": per}


def overrides_check(ids: set[int]) -> dict:
    if not OVERRIDES.exists():
        return {"file": str(OVERRIDES.relative_to(ROOT)), "exists": False, "missing_ids": []}
    ov = load_json(OVERRIDES)
    refs = [int(i) for i in ov.get("remove", [])] + [int(k) for k in ov.get("move", {})]
    return {"file": str(OVERRIDES.relative_to(ROOT)), "exists": True,
            "missing_ids": sorted(i for i in refs if i not in ids)}


def manifest(res: Result, files: dict[str, dict[str, bytes]], field_shas: dict[str, str], validation: Validation,
             keep: dict | None) -> dict:
    zones = {z: {a: {"count": int(len(data) - 8) // binfmt.RECORD.itemsize,
                     "file": f"world/generated/{z}/{a}.bin", "sha1": sha1_bytes(data)}
                 for a, data in assets.items()} for z, assets in files.items()}
    if keep:
        zones = dict(sorted({**keep, **zones}.items()))
    return {
        "format": "VPL1 (magic, uint32 count, 32-byte records: f32 x y z yaw scale tilt_x tilt_z, u32 id)",
        "revision": res.inputs.revision,
        "inputs": res.inputs.shas,
        "zones": zones,
        "locked": res.recipes.locked,
        "skipped": res.skipped,
        "warnings": res.warnings + validation.soft,
        "fields": field_shas,
        "routes": [{"id": r.rid, "stones_on_turns": r.stones_on_turns, "roots": r.roots,
                    "clearance_height": r.clearance_height, "turn_band_m": list(TURN_BAND_M),
                    "turns": r.turns()} for r in res.routes.routes],
        "validation": {"ok": validation.ok, "hard_failures": validation.hard, **validation.info},
    }


def dump_json(obj: dict) -> bytes:
    return (json.dumps(obj, indent=1, sort_keys=False, default=_json_default) + "\n").encode()


def _json_default(o: object) -> object:
    if isinstance(o, (np.integer,)):
        return int(o)
    if isinstance(o, (np.floating,)):
        return round(float(o), 4)
    raise TypeError(type(o))


def counts_table(res: Result) -> list[str]:
    c = Counter((i.zone, i.source.split(".")[0] if i.locked else i.source, i.asset) for i in res.instances)
    lines = ["| zone | source | asset | count |", "|---|---|---|---:|"]
    lines += [f"| {z} | {s} | {a} | {n} |" for (z, s, a), n in sorted(c.items())]
    fam = Counter(i.source for i in res.instances)
    lines += ["", "| source | count |", "|---|---:|"] + [f"| {s} | {n} |" for s, n in sorted(fam.items())]
    return lines


def bank_table(validation: Validation) -> list[str]:
    """Bank dressing per character x zone and shoreline metres per character."""
    b = validation.info.get("banks")
    if not b:
        return ["(no banks section)"]
    zones = sorted({z for zs in b["counts"].values() for z in zs})
    lines = ["| character | " + " | ".join(zones) + " | total |", "|---|" + "---:|" * (len(zones) + 1)]
    for ch, zs in b["counts"].items():
        lines.append(f"| {ch} | " + " | ".join(str(zs.get(z, 0)) for z in zones) + f" | {sum(zs.values())} |")
    for kind, n in b["shore_m"].items():
        tot = max(sum(n.values()), 1)
        lines.append(f"\nshore {kind} (m ~ px): " + ", ".join(f"{k} {v} ({v / tot:.0%})" for k, v in n.items()))
    return lines


def markdown(res: Result, validation: Validation, dfx: dict, sha_check: dict, ov: dict, mode: str, timing: dict) -> str:
    L = [f"# Scatter report ({mode})", "", f"revision: `{res.inputs.revision}`", ""]
    L += ["## Validation", "", f"hard failures: {len(validation.hard)}"]
    L += [f"- FAIL {m}" for m in validation.hard[:40]]
    L += [f"- warn {m}" for m in validation.soft + res.warnings]
    L += ["", "```json", json.dumps(validation.info, indent=1, default=_json_default), "```", ""]
    L += ["## Diff vs world/generated", "", json.dumps(dfx["total"]), "",
          "| zone | asset | kind | n |", "|---|---|---|---:|"]
    L += [f"| {z} | {a} | {k} | {n} |" for (z, a, k), n in sorted(dfx["per"].items()) if k != "preserved" or n]
    L += ["", "## Untouched zones (sha1 before == after)", ""]
    L += [f"- {k}: {'unchanged' if v else 'CHANGED'}" for k, v in sorted(sha_check.items())] or ["- (all zones regenerated)"]
    L += ["", "## Banks", ""] + bank_table(validation)
    L += ["", "## Counts", ""] + counts_table(res)
    L += ["", "## Skipped assets", ""] + [f"- {json.dumps(s)}" for s in res.skipped]
    L += ["", "## Overrides", "", json.dumps(ov), "", "## Timing (s)", "", json.dumps(timing)]
    return "\n".join(L) + "\n"


def file_sha_map(zones: list[str] | None = None) -> dict[str, str]:
    return {f"{z}/{a}": sha1_file(p) for z, assets in existing_files(zones).items() for a, p in assets.items()}
