# /// script
# requires-python = ">=3.11"
# ///
"""Waterfall lines for the runtime splash mist (scripts/valley_falls.gd).

    uv run export_falls.py

Writes the FALLS lines of terrain_features.py in world metres (x right, z south; sample i
sits at i - 511.5, as in the heightmap) to out/falls.json and copies it to
res://terrains/valley/falls.json. The runtime finds each fall's actual face and foot in the
water levels near the line, so only the lines are exported.
"""
import json
import shutil
from pathlib import Path

import terrain_features as F

HERE = Path(__file__).parent
OUT = HERE / "out"
DEST = HERE.parent.parent / "terrains" / "valley" / "falls.json"
RES = 1024  # heightmap samples per side, 1 m apart
K = RES / F.REF_SIZE  # ref px -> sample


def world(p: tuple[float, float]) -> list[float]:
    return [round(p[0] * K - (RES - 1) * 0.5, 3), round(p[1] * K - (RES - 1) * 0.5, 3)]


def main() -> None:
    falls = [{"name": f["name"], "pts": [world(p) for p in f["pts"]], "drop": f["drop"]} for f in F.FALLS]
    OUT.mkdir(exist_ok=True)
    out = OUT / "falls.json"
    out.write_text(json.dumps({"falls": falls}, indent=1) + "\n")
    shutil.copyfile(out, DEST)
    print(f"exported {len(falls)} falls -> {DEST}")


if __name__ == "__main__":
    main()
