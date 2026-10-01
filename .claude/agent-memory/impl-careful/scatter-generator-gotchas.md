---
name: scatter-generator-gotchas
description: tools/environment placement generator gotchas - habitats edits re-seed all trees, custom capture views, running scratch scripts against the generator
metadata:
  type: project
---

- The placement seed = terrain_revision + sha1 of valley_habitats.json re-serialised (json.dumps indent=2) WITHOUT its `banks` section (generate._seed_sha). Editing any other habitats section re-seeds every tree/prop; write the file with `json.dumps(o, indent=2)` (no trailing newline) or the seed changes. Bank tuning is seed-neutral.
- Prove "trees unchanged" with an in-process A/B (generate.run with/without the new section, compare group_files) - the lead edits anchors/recipes in parallel, so before/after published sha1s can differ for unrelated reasons (cliff_face/rock_shelf changed under me 2026-10-01).
- Scratch scripts importing the generator: `uv run --with numpy --with scipy --with pillow python script.py` (scatter.py carries its deps inline; plain `uv run python` has none).
- Custom capture views without touching tools/capture: capture.sh reads `$root/tools/capture/$VIEWS`, so `VIEWS=../../../../../../private/tmp/.../views.tsv` works (6 x `..` from tools/capture to /).
- Bank-type rules on a narrow strip (shore_distance window) need candidates snapped into the window (bank_props._snap); plain cell candidates mostly miss the strip.

**Why:** each cost a debugging round during the bank-character work (2026-10-01).
**How to apply:** check before editing habitats JSON or claiming tree identity. See [[parallel-agents-shared-dirs]].
