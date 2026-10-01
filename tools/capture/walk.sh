#!/bin/zsh
# Usage: walk.sh <out.mp4> <preset> <seconds> [user args...]   (env SCENE, RES)
out=${1:?usage: walk.sh <out.mp4> <preset> <seconds> [user args...]}
preset=${2:?}; secs=${3:?}; shift 3
root=${0:A:h:h:h}
RES=${RES:-1152x648}; SCENE=${SCENE:-res://scenes/main.tscn}
out=${out:A}
frames=$((secs * 30 + 30))
tmp=$(mktemp -d)
(cd $root && godot --path . $SCENE --resolution $RES \
  --write-movie $tmp/f.png --fixed-fps 30 --quit-after $frames \
  -- --preset=$preset --walk=1 "$@") < /dev/null > $tmp/log.txt 2>&1
grep -m1 '^RENDER' $tmp/log.txt > ${out%.mp4}.txt
grep -E 'ERROR|SCRIPT ERROR|SHADER ERROR' $tmp/log.txt | grep -v -e 'RID allocations' -e leaked
ffmpeg -y -loglevel error -framerate 30 -i $tmp/f%08d.png -c:v libx264 -pix_fmt yuv420p -crf 20 $out
rm -rf $tmp
echo "done -> $out"
