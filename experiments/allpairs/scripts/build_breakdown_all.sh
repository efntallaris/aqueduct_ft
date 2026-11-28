#!/usr/bin/env bash
# Phase breakdown for ALL THREE recipient groups, from every node of each.
#
# WHY THIS EXISTS. paper_3vs5_breakdown.py takes `pair` as argv[4] and defaults to A
# (line 27, filter at line 123), and add_recv_durable.py takes ONE group. So every
# breakdown figure so far covered pair A / sg4 only -- 4 of the migration's 12 rounds.
# This builds a json per (run, group), each carrying that group's own recv/durable, and
# draws A, B and C.
#
#   pair A  sg1 -> sg4     B  sg2 -> sg5     C  sg3 -> sg6
#
# ONLY sg4 IS WIDENED. topology_spread5.yml gives sg4 five nodes; sg5 and sg6 keep three
# in BOTH arms. So the B and C figures are not 3-vs-5 comparisons -- they put the same
# 3-node configuration side by side, and what they test is whether widening sg4 disturbs
# the pairs that follow it. Their titles say so rather than implying a width difference.
set -uo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
T=/users/entall/rd/experiments/tools/scaleout
AR=/users/entall/rd/experiments/2026-11-19_link_disjoint/add_recv_durable.py
export CMU_DIR=/users/entall/rd/experiments/tools/fonts/cmu
mkdir -p "$HERE/bd" "$HERE/figs/breakdown_all"

# Representative rep per arm: the one nearest that arm's three-rep mean (see README).
A3=S3_r2 A5=S5_r3 B3=D3_r2 B5=D5_r1

mkgroup() {   # mkgroup <tag> <group>   -- base json must already exist in bd/
  local tag="$1" g="$2"
  [ -f "$HERE/bd/$tag.json" ] || { echo "  !! no bd/$tag.json (run build_breakdown.sh first)"; return 1; }
  cp "$HERE/bd/$tag.json" "$HERE/bd/${tag}_${g}.json"
  python3 -I "$AR" "$HERE/data/$tag" "$g" "$HERE/bd/${tag}_${g}.json" >/dev/null 2>&1 \
    || { echo "  !! $tag $g: recv/durable failed"; return 1; }
  echo "  ok ${tag}_${g}"
}

fig() {   # fig <out> <jsonA> <titleA> <jsonB> <titleB> <pair>
  local out="$1" ja="$2" ta="$3" jb="$4" tb="$5" p="$6"
  local pbx="" lbl=1; [ "$p" != A ] && { pbx=1; lbl=0; }
  ( export ROW_H=0.26 FS=8 FS_SM=6.5 LEG_NCOL=3 SHOW_HANDOVER=0 PER_BLOCK_X="$pbx" BAR_LABELS="$lbl"
    for e in pdf png svg; do
      TITLE_A="$ta" TITLE_B="$tb" python3 "$T/paper_3vs5_breakdown.py" \
        "$HERE/bd/$ja.json" "$HERE/bd/$jb.json" "$HERE/figs/breakdown_all/${out}_column.$e" "$p" 3.33 2>&1 | tail -1
    done )
  ( export ROW_H=0.55 FS=9 FS_SM=7.5
    for e in pdf png svg; do
      TITLE_A="$ta" TITLE_B="$tb" python3 "$T/paper_3vs5_breakdown.py" \
        "$HERE/bd/$ja.json" "$HERE/bd/$jb.json" "$HERE/figs/breakdown_all/${out}_wide.$e" "$p" 6.9 2>&1 | tail -1
    done )
}

echo "== per-group receipts =="
for t in $A3 $A5 $B3 $B5; do for g in sg4 sg5 sg6; do mkgroup "$t" "$g"; done; done

echo "== figures =="
fig pairwise_sg4 "${A3}_sg4" "pairwise — sg4, 3 nodes" "${A5}_sg4" "pairwise — sg4, 5 nodes" A
fig pairwise_sg5 "${A3}_sg5" "pairwise — sg5, 3 nodes (3-rep run)" "${A5}_sg5" "pairwise — sg5, 3 nodes (5-rep run)" B
fig pairwise_sg6 "${A3}_sg6" "pairwise — sg6, 3 nodes (3-rep run)" "${A5}_sg6" "pairwise — sg6, 3 nodes (5-rep run)" C
fig deep_sg4 "${B3}_sg4" "deep — sg4, 3 nodes" "${B5}_sg4" "deep — sg4, 5 nodes (depth 3)" A
fig deep_sg5 "${B3}_sg5" "deep — sg5, 3 nodes (3-rep run)" "${B5}_sg5" "deep — sg5, 3 nodes (5-rep run)" B
fig deep_sg6 "${B3}_sg6" "deep — sg6, 3 nodes (3-rep run)" "${B5}_sg6" "deep — sg6, 3 nodes (5-rep run)" C
echo; ls "$HERE/figs/breakdown_all"/*.png | sed 's|.*/|  |'
