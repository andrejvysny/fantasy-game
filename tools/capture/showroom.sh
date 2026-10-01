#!/bin/zsh
# Usage: showroom.sh <out_dir> [asset_id ...]   (default: every assets/nature asset)
# Renders scenes/showroom.tscn per asset: <id>_high.png (35 deg 3/4) and <id>_low.png (eye height).
# Env: RES (960x640), VIEWS ("high low").
root=${0:A:h:h:h}
out=${1:?usage: showroom.sh <out_dir> [asset_id ...]}; shift
mkdir -p $out; out=${out:A}
RES=${RES:-960x640}; VIEWS=(${=VIEWS:-high low})
ids=("$@")
if (( ${#ids} == 0 )); then
  ids=(${(f)"$(cd $root/assets/nature && ls */*.glb | xargs -n1 basename | sed 's/\.glb$//' | sort)"})
fi
tmp=$(mktemp -d)
for id in $ids; do
  for v in $VIEWS; do
    (cd $root && godot --path . res://scenes/showroom.tscn --resolution $RES --write-movie $tmp/f.png \
      --fixed-fps 30 --quit-after 12 -- --focus=$id --view=$v) < /dev/null > $tmp/log.txt 2>&1
    last=$(ls $tmp/f*.png 2>/dev/null | tail -1)
    [[ -n $last ]] && cp $last $out/${id}_$v.png || echo "MISSING $id $v"
    grep -E 'SCRIPT ERROR|SHADER ERROR' $tmp/log.txt | sed "s/^/[$id $v] /"
    rm -f $tmp/f*.png
  done
done
rm -rf $tmp
echo "done -> $out"
