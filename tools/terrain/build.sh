#!/usr/bin/env bash
# Regenerate heightmap, paint, Blender scene and Godot data (res://terrains/valley).
# Pass --render for clay + painted previews.
set -euo pipefail
cd "$(dirname "$0")"
BLENDER="${BLENDER:-/Applications/Blender.app/Contents/MacOS/Blender}"
uv run gen_heightmap.py
uv run gen_splat.py
"$BLENDER" -b -P build_blend.py -- "$@"
rm -f out/terrain.blend1
"${GODOT:-godot}" --headless --path ../.. --script "$PWD/export_godot.gd"
