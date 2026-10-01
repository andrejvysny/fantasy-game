---
name: parallel-agents-shared-dirs
description: Valley work runs parallel agents that rewrite assets/nature/*.json and world/generated/fields/ while you work; affects determinism checks and cleanup
metadata:
  type: project
---
Other agents regenerate `assets/nature/*/*.json` metadata (every few minutes) and write runtime stubs into `world/generated/fields/` (`_stub_*.res`) during placement-generator work.

**Why:** a determinism check across two runs looked broken (digests differed) until asset JSON mtimes showed a parallel Blender agent rewriting metadata; an `rm -rf world/generated` also deleted another agent's stub .res files.

**How to apply:** never delete `world/generated` wholesale — only `world/generated/<zone>/*.bin` + `manifest.json`. Prove byte-identity with back-to-back runs and compare `manifest.json` `inputs` sha1s before blaming the generator (`tools/environment/scatter.py`, see its README).
