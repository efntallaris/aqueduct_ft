PDF=paper.pdf
TEX=paper.tex

FIGDIRS=experiments/crash_recovery experiments/replica_count experiments/baselines

FIGFORCE=$(FIGDIRS:%=%/.force)

.PHONY: all clean figures figures-force $(PDF) $(FIGDIRS) $(FIGFORCE)

all: $(PDF)

# Recursing through phony per-directory targets rather than `@for d in ...; do ... done`.
# .latexmkrc runs `make -s figures` through the system shell, which is cmd.exe on Windows
# (VS Code / LaTeX Workshop builds), and cmd.exe has no POSIX `for`, so the loop version
# failed there with "d was unexpected at this time" and every compile warned. These rules
# are pure make, so they behave the same under sh and cmd.exe.
figures: $(FIGDIRS)

$(FIGDIRS):
	@$(MAKE) --no-print-directory -C $@

figures-force: $(FIGFORCE)

$(FIGFORCE):
	@$(MAKE) --no-print-directory -C $(@D) force

$(PDF): figures
	latexmk -pdf -silent $(TEX)

clean:
	latexmk -C
