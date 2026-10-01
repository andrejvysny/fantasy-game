---
name: rock-cliff-modules
description: Blender rock family layout and plane-spec gotchas for the procedural cliff modules (tools/blender/rock_*.py)
metadata:
  type: reference
---

- cliff_face_A + cliff_corner_A (rev 2, tapered ends) live in tools/blender/rock_cliff.py; rock_family.py main() dispatches there first. rock_family_b still holds the stale v1 corner_params (used as the base of v2).
- Running rock_family.py with -P makes it `__main__`; rock_family_b/rock_cliff import a second copy `rock_family` (rf). Params must be swapped into rf.PARAMS / rf.bench, not into the __main__ copy.
- Plane jitter draws from the asset rng in plane order: adding/removing any plane reshuffles every later plane slightly. Iterate visually after each change.
- A leaning "wall"/"!wall" spec rotates about its given z: put a joint's point at the floor height or a 20-30 deg lean shifts it metres inward at the top.
- The frame tilt changes world leans: on cliff_face_A (tilt 11 toward az 35), left-facing planes lean ~10 deg further back and right-facing planes ~10 deg toward overhang. Author right-hand leans larger.
- Only rebuild named assets: `Blender -b --factory-startup -P tools/blender/rock_family.py -- cliff_face_A cliff_corner_A`. Prove the other rocks are byte-identical with shasum before/after.

See [[parallel-agents-shared-dirs]].
