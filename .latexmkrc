# Regenerate the experiment figures before every compile, so that `latexmk paper.tex`
# and an editor that calls latexmk behave the same as `make`. The figure Makefiles are
# timestamp-driven, so this is a no-op unless the raw logs or the plotting scripts
# changed, and it prints a line and does nothing in a clone without the raw logs.
system("make -s figures") == 0 or warn "figure regeneration failed, using the committed PDFs\n";

$pdf_mode = 1;

# paper.bbl is maintained BY HAND and is tracked in git. Never regenerate it: bibtex
# rewrites the entries, which among other things puts back the \newblock commands that
# were deliberately removed. 0 means "never run bibtex, use the .bbl that is there".
# Set it back to 1 only if the bibliography is to be rebuilt from paper.bib on purpose.
$bibtex_use = 0;
