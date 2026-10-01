# Capture tooling

Launches `$SCENE` (default `res://scenes/main.tscn`) with views from `$VIEWS` (default `views.tsv`).
Valley: `SCENE=res://scenes/valley.tscn VIEWS=views_valley.tsv zsh tools/capture/capture.sh <out>` (16 zone views; positions from tools/environment/probe.py).

- `views.tsv`: view manifest (`name<TAB>preset<TAB>args`); preset 0 dawn, 1 midday, 2 evening.
- `zsh tools/capture/capture.sh <out_dir> [name_glob] [-- extra args]` renders views to `<out_dir>/<name>.png`,
  logs to `<out_dir>/logs/`, and writes `<out_dir>/manifest.txt` (git hash+dirty, godot, GPU, macOS, args, RENDER line per view).
  Env: `RES=1152x648`, `FRAME=89`, `DRIVER=metal|vulkan`. Example: `capture.sh out 'midday_*' -- --msaa=4`.
- `zsh tools/capture/walk.sh <out.mp4> <preset> <seconds> [args]` scripted straight walk (`--walk=1`, optional `--turn=left|right`) to mp4 (env `SCENE` like capture.sh), plus `<out>.txt` RENDER line.
- `uv run --with pillow python tools/capture/contact_sheet.py <dir>` builds `00_contact_sheet.png`.
- Runtime args (scripts/main.gd): `--msaa=0|2|4|8`, `--walk=<delay_s>`, `--turn=`; a `RENDER ...` line is printed at startup.

Deterministic: TIME (movie mode + fixed fps), seeded scatter (forest/grass/mist `world_seed`).
Not deterministic: GPU particle random seeds (dust, fireflies, fire), campfire flicker phase (`randf()`).

forest_edge (16,-12) / forest_tactical (-12,12) chosen with a headless probe replicating the forest glade
noise (FastNoiseLite seed world_seed+1, freq 0.02, glade where > 0.45): edge = ~50% glade within 10 m, dense = 0% glade.
