# /// script
# requires-python = ">=3.11"
# dependencies = ["numpy", "scipy", "pillow"]
# ///
"""Offline, deterministic placement generator for the valley (plan section 8).

    uv run scatter.py [--dry-run] [--zone ID ...]

Reads the protected terrain (tools/terrain/out), world/anchors, world/routes, world/recipes and
asset metadata; writes world/generated/<zone>/<asset_id>.bin (VPL1), world/generated/manifest.json
and tools/environment/out/fields/{ground,flowers,habitat}.png. --dry-run computes everything and
writes only tools/environment/out (report, log, previews). --zone regenerates only those zones'
files; other zones are left untouched. Exit 1 on hard validation failures (nothing is published).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import generate  # noqa: E402
import report  # noqa: E402
from common import GENERATED, OUT, OVERRIDES, load_json  # noqa: E402
from groundcover import write_field_pngs  # noqa: E402
from preview import write_previews  # noqa: E402
from validate import Validation, validate  # noqa: E402


def _args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--dry-run", action="store_true", help="compute, diff and report; write nothing to world/")
    p.add_argument("--zone", action="append", default=[], metavar="ID", help="regenerate only this zone (repeatable)")
    return p.parse_args()


def _publish(files: dict[str, dict[str, bytes]], zones: list[str]) -> None:
    """Write the selected zones' files and delete their stale .bin files."""
    for z in zones:
        d = GENERATED / z
        new = files.get(z, {})
        for old in sorted(d.glob("*.bin")) if d.exists() else []:
            if old.stem not in new:
                old.unlink()
        if new:
            d.mkdir(parents=True, exist_ok=True)
        for a, data in new.items():
            p = d / f"{a}.bin"
            if not p.exists() or p.read_bytes() != data:
                p.write_bytes(data)
        if d.exists() and not any(d.iterdir()):
            d.rmdir()


def _write_overrides_stub() -> None:
    if not OVERRIDES.exists():
        OVERRIDES.parent.mkdir(parents=True, exist_ok=True)
        OVERRIDES.write_text(json.dumps({"remove": [], "move": {}, "add": []}, indent=1) + "\n")


def _field_shas(images: dict) -> dict[str, dict]:
    return {n: {"file": f"tools/environment/out/fields/{n}.png", "format": "RGBA8 1024x1024 row0=north",
                "sha1_rgba": hashlib.sha1(images[n].tobytes()).hexdigest()} for n in sorted(images)}


def main() -> int:
    args = _args()
    t0 = time.perf_counter()
    timing: dict[str, float] = {}
    inp = generate.load_inputs()
    res = generate.run(inp)
    timing["generate"] = round(time.perf_counter() - t0, 2)
    files = generate.group_files(res.instances)
    res_b = generate.run(inp)  # determinism self-check: a second independent in-process run
    dig = (generate.digest(files, res.images), generate.digest(generate.group_files(res_b.instances), res_b.images))
    timing["generate_twice"] = round(time.perf_counter() - t0, 2)
    val = validate(res, dig)
    all_zones = [z["id"] for z in inp.anchors["zones"]] + ["fill"]
    bad = [z for z in args.zone if z not in all_zones]
    if bad:
        print(f"unknown zone(s) {bad}; known: {all_zones}", file=sys.stderr)
        return 2
    sel = args.zone or sorted(set(all_zones) | set(report.existing_files()))
    old = {z: {a: p.read_bytes() for a, p in assets.items()} for z, assets in report.existing_files(sel).items()}
    new = {z: v for z, v in files.items() if z in sel}
    dfx = report.diff(old, new)
    before = {k: v for k, v in report.file_sha_map().items() if k.split("/")[0] not in sel}
    published = False
    if not args.dry_run and val.ok:
        man_path = GENERATED / "manifest.json"
        keep = None
        if args.zone and man_path.exists():
            keep = {z: v for z, v in load_json(man_path).get("zones", {}).items() if z not in sel}
        _publish(files, sel)
        man = report.manifest(res, new, _field_shas(res.images), val, keep if args.zone else None)
        GENERATED.mkdir(parents=True, exist_ok=True)
        man_path.write_bytes(report.dump_json(man))
        write_field_pngs(res.images, OUT / "fields")
        _write_overrides_stub()
        published = True
    after = report.file_sha_map()
    sha_check = {k: after.get(k) == v for k, v in before.items()}
    ids = {i.iid for i in res.instances}
    ov = report.overrides_check(ids)
    timing["total"] = round(time.perf_counter() - t0, 2)
    mode = "dry-run" if args.dry_run else ("published" if published else "NOT published (hard failures)")
    if args.zone:
        mode += " zones=" + ",".join(sel)
    md = report.markdown(res, val, dfx, sha_check, ov, mode, timing)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "scatter_report.md").write_text(md)
    previews = write_previews(res, OUT)
    _log(timing, mode, dig, val, previews)
    print(md)
    return 0 if val.ok else 1


def _log(timing: dict, mode: str, dig: tuple[str, str], val: Validation, previews: list[Path]) -> None:
    lines = [time.strftime("%Y-%m-%d %H:%M:%S"), f"mode: {mode}", f"timing: {json.dumps(timing)}",
             f"digest: {dig[0]} / {dig[1]}", f"hard failures: {len(val.hard)}, warnings: {len(val.soft)}"]
    lines += [f"preview: {p}" for p in previews]
    with (OUT / "scatter_log.txt").open("a") as fh:
        fh.write("\n".join(lines) + "\n\n")


if __name__ == "__main__":
    sys.exit(main())
