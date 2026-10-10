PDF=paper.pdf
TEX=paper.tex

# latexmk tracks every \input file (design.tex, protocol.tex, figs/, pseudocodes/),
# so always let it decide what to rebuild.
.PHONY: all clean $(PDF)

all: $(PDF)

$(PDF):
	latexmk -pdf -silent $(TEX)

clean:
	latexmk -C
