# Regenerate the experiment figures before every compile, so that `latexmk paper.tex`
# and an editor that calls latexmk behave the same as `make`. The figure Makefiles are
# timestamp-driven, so this is a no-op unless the raw logs or the plotting scripts
# changed, and it prints a line and does nothing in a clone without the raw logs.
system("make -s figures") == 0 or warn "figure regeneration failed, using the committed PDFs\n";

$pdf_mode = 1;
