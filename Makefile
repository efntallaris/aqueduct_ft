PDF=paper.pdf
TEX=paper.tex

FIGDIRS=experiments/crash_recovery experiments/replica_count experiments/baselines

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
