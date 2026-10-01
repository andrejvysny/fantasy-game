#!/bin/zsh
# Usage: capture.sh <out_dir> [name_glob] [-- extra user args applied to every view]
# Env: RES (1152x648), FRAME (89; quits after FRAME+1), DRIVER (optional --rendering-driver),
#      SCENE (res://scenes/main.tscn), VIEWS (views.tsv; e.g. views_valley.tsv with SCENE=res://scenes/valley.tscn).
setopt extendedglob
here=${0:A:h}
root=${here:h:h}
out=${1:?usage: capture.sh <out_dir> [name_glob] [-- extra args]}; shift
glob='*'
[[ $# -gt 0 && $1 != -- ]] && { glob=$1; shift }
[[ ${1:-} == -- ]] && shift
extra=("$@")
RES=${RES:-1152x648}; FRAME=${FRAME:-89}; FPS=30
SCENE=${SCENE:-res://scenes/main.tscn}; VIEWS=${VIEWS:-views.tsv}
mkdir -p $out/logs
out=${out:A}
frame=$(printf 'f%08d.png' $FRAME)
drv=(); [[ -n ${DRIVER:-} ]] && drv=(--rendering-driver $DRIVER)
tmp=$(mktemp -d)
views=()
{
  echo "capture_time: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo "git: $(git -C $root rev-parse HEAD) dirty=$([[ -n $(git -C $root status --porcelain) ]] && echo yes || echo no)"
  echo "godot: $(godot --version)"
  echo "gpu: $(system_profiler SPDisplaysDataType 2>/dev/null | grep 'Chipset Model' | head -1 | sed 's/^ *//')"
  echo "macos: $(sw_vers -productVersion)"
  echo "scene: $SCENE  views: $VIEWS"
  echo "res: $RES  frame: $FRAME  fixed_fps: $FPS  driver: ${DRIVER:-default}"
  echo "extra_args: ${extra[*]}"
  echo
} > $out/manifest.txt
tail -n +2 $root/tools/capture/$VIEWS | while IFS=$'\t' read -r name preset args; do
  [[ $name == ${~glob} ]] || continue
  d=$tmp/$name; mkdir -p $d
  log=$out/logs/$name.log
  (cd $root && godot --path . $SCENE --resolution $RES $drv \
    --write-movie $d/f.png --fixed-fps $FPS --quit-after $((FRAME + 1)) \
    -- --preset=$preset ${=args} $extra) < /dev/null > $log 2>&1
  if [[ -f $d/$frame ]]; then cp $d/$frame $out/$name.png; else echo "MISSING frame for $name"; fi
  grep -E 'ERROR|SCRIPT ERROR|SHADER ERROR' $log | grep -v -e 'RID allocations' -e leaked | sed "s/^/[$name] /"
  {
    echo "view: $name"
    echo "  preset: $preset"
    echo "  args: $args"
    echo "  $(grep -m1 '^RENDER' $log)"
    dbg=$(grep -m1 'DEBUG' $log); [[ -n $dbg ]] && echo "  $dbg"
  } >> $out/manifest.txt
done
rm -rf $tmp
echo "done -> $out"
