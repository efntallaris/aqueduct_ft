PDF=paper.pdf
TEX=paper.tex

.PHONY: all clean

all: $(PDF)

$(PDF): $(TEX)
	latexmk -pdf -silent $(TEX)

clean:
	latexmk -C

