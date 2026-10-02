# Integration

AssetStudio addon is vendored in `addons/assetstudio/` exactly as built upstream. Pin: `integration.lock.json`.
Never edit the addon here. Fix upstream (andrejvysny/asset-studio `integrations/godot`), rebuild the archive, repin.

## Repin
1. Upstream: rebuild `dist/assetstudio-addon-<ver>.zip`; note commit sha and `shasum -a 256`.
2. `rm -rf addons/assetstudio && unzip <zip> -d .`
3. Update `integration.lock.json` (source_commit, package_version, archive, archive_sha256).
4. `godot --headless --path . --script res://addons/assetstudio/cli.gd -- verify --locked --offline`, then headless import, run `scripts/integration/verify_integration.gd`.

## Layout
- `assetstudio.project.json`, `assetstudio.lock.json`: addon-owned, tracked.
- `assets/library/`, `.assetstudio/`: git-ignored; `restore --locked` + headless import rebuilds them.
- `assets/prefabs/*.tscn`: generated wrappers (tracked, do not edit).
- `integration/material_profiles/`: game-owned material profiles.
- `integration/collision_policy.json` + `scripts/integration/integration_asset.gd`: game-owned collision.

Details and results: `docs/integration/fg-01-02.md`.
