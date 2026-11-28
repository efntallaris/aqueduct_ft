#!/bin/sh
# Export each panel of the topology figure to illustrations/out/ as PDF and PNG.
#
# Each panel is built through export.tex, which carries the paper's Times + newtxmath
# preamble, so an exported panel is the same drawing that lands in paper.pdf and not a
# Computer Modern lookalike. Run from anywhere: the script cd's to its own directory
# because topology.tex is \input by a relative path.
set -e
cd "$(dirname "$0")"
mkdir -p out
: "${DPI:=300}"

# name:body pairs. The name becomes out/<name>.pdf and out/<name>.png.
set -- \
  "topo-norep:\\topopanel{1}" \
  "topo-layered:\\topopanel{2}" \
  "topo-chain:\\topopanel{3}" \
  "topo-front-layered:\\topopanelfront{2}" \
  "topo-front-chain:\\topopanelfront{3}" \
  "topo-model:\\topoplot" \
  "topo-legend:\\topolegend"

for pair in "$@"; do
  name=${pair%%:*}
  body=${pair#*:}
  printf '  %s\n' "$name"
  pdflatex -interaction=batchmode -halt-on-error \
    -jobname="out/$name" \
    "\\def\\PANELBODY{$body}\\input{export.tex}" >/dev/null
  pdftoppm -r "$DPI" -png -singlefile "out/$name.pdf" "out/$name"
done

rm -f out/*.aux out/*.log
echo "panels written to $(pwd)/out"
