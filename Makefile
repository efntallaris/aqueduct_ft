PDF=paper.pdf
TEX=paper.tex

# Each experiment directory regenerates its own figures from its own raw logs and
# scripts. Both are driven here, so compiling the paper redraws any figure whose data or
# script changed and leaves the rest alone. A clone without the raw logs skips the step
# and uses the committed PDFs.
FIGDIRS=experiments/crash_recovery experiments/replica_count

# latexmk tracks every \input file (design.tex, protocol.tex, illustrations/, pseudocodes/),
# so always let it decide what to rebuild.
.PHONY: all clean figures figures-force $(PDF)

all: $(PDF)

figures:
	@for d in $(FIGDIRS); do $(MAKE) --no-print-directory -C $$d; done

figures-force:
	@for d in $(FIGDIRS); do $(MAKE) --no-print-directory -C $$d force; done

$(PDF): figures
	latexmk -pdf -silent $(TEX)

clean:
	latexmk -C
