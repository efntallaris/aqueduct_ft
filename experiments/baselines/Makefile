
PY := python3

FONT_DIR ?= $(patsubst %/,%,$(dir $(shell kpsewhich texgyretermes-regular.otf)))
ifneq ($(FONT_DIR),)
export FONT_DIR
endif

FIG_W       ?= 3.22        # just inside a usenix2019_v3 column; the pair fits the 7in width
ROW_IN      ?= 1.35        # height of the throughput row, matched by the latency row
TPUT_YTICKS ?= 200,400,800
TPUT_YMAX   ?= 800
TPUT_LOG    ?= 1           # log throughput axis, so panels carry measured kops/s unscaled
SHOW_WRITE  ?= 0
BASELINE_SAME_TESTBED ?= aqueduct
BASELINE_AXES         ?=
XLIM  ?= 0,110
XTICK ?= 0,30,60,100

SYSTEMS_955      ?= aqueduct aqueduct_ft rocksteady
SYSTEMS_5050     ?= aqueduct aqueduct_ft rocksteady
LEGEND_955       ?= 0
LEGEND_5050      ?= 0
MIG_WINDOWS_955  ?= rocksteady:20-102
MIG_WINDOWS_5050 ?= rocksteady:20-102
NODATA_5050      ?= 1

.PHONY: all force clean norepl wl5050 legend

PAPER_FIGS := figures/baselines.pdf figures/baselines_5050.pdf figures/baselines_legend.pdf

# Guard, matching experiments/crash_recovery and experiments/replica_count: the raw
# logs under data/ are not in git, so in a plain clone there is nothing to redraw and
# the committed PDFs under figures/ are what the paper uses. Without this, `make
# figures` (and therefore every latexmk run, via .latexmkrc) stops with
# "No rule to make target 'data/955/aqueduct_ft.csv'".
ifeq ($(wildcard data/955),)
all:
	@echo experiments/baselines: no data/, keeping the committed PDFs
else

all: $(PAPER_FIGS)

figures/baselines.pdf: scripts/plot_baselines.py $(wildcard data/955/*.csv)
	@mkdir -p figures
	SYSTEMS="$(SYSTEMS_955)" WORKLOAD=955 FIG_W=$(FIG_W) ROW_IN=$(ROW_IN) \
	    XLIM=$(XLIM) XTICK=$(XTICK) TPUT_YTICKS=$(TPUT_YTICKS) TPUT_YMAX=$(TPUT_YMAX) SHOW_TAIL=1 FRAME=1 \
	    LEGEND=$(LEGEND_955) SHOW_WRITE=$(SHOW_WRITE) \
	    MIG_WINDOWS="$(MIG_WINDOWS_955)" \
	    BASELINE_SAME_TESTBED="$(BASELINE_SAME_TESTBED)" \
	    BASELINE_AXES="$(BASELINE_AXES)" TPUT_LOG=$(TPUT_LOG) \
	    $(PY) scripts/plot_baselines.py data $@

wl5050: figures/baselines_5050.pdf

figures/baselines_5050.pdf: scripts/plot_baselines.py $(wildcard data/5050/*.csv)
	@mkdir -p figures
	SYSTEMS="$(SYSTEMS_5050)" WORKLOAD=5050 FIG_W=$(FIG_W) ROW_IN=$(ROW_IN) \
	    XLIM=$(XLIM) XTICK=$(XTICK) TPUT_YTICKS=$(TPUT_YTICKS) TPUT_YMAX=$(TPUT_YMAX) SHOW_TAIL=1 FRAME=1 \
	    LEGEND=$(LEGEND_5050) \
	    MIG_WINDOWS="$(MIG_WINDOWS_5050)" NODATA=$(NODATA_5050) \
	    SHOW_WRITE=$(SHOW_WRITE) \
	    BASELINE_SAME_TESTBED="$(BASELINE_SAME_TESTBED)" \
	    BASELINE_AXES="$(BASELINE_AXES)" TPUT_LOG=$(TPUT_LOG) \
	    $(PY) scripts/plot_baselines.py data $@

legend: figures/baselines_legend.pdf

figures/baselines_legend.pdf: scripts/plot_baselines.py data/955/aqueduct_ft.csv
	@mkdir -p figures
	SYSTEMS="$(SYSTEMS_955)" WORKLOAD=955 FIG_W=6.6 ROW_IN=$(ROW_IN) \
	    XLIM=$(XLIM) XTICK=$(XTICK) TPUT_YTICKS=$(TPUT_YTICKS) TPUT_YMAX=$(TPUT_YMAX) SHOW_TAIL=1 \
	    LEGEND=only LEG_TAIL_PLAIN=1 LEG_NCOL=6 SHOW_WRITE=$(SHOW_WRITE) \
	    NODATA=0 \
	    $(PY) scripts/plot_baselines.py data $@

norepl: figures/norepl_vs_3rep.pdf

figures/norepl_vs_3rep.pdf: scripts/plot_norepl_vs_3rep.py \
        data/5050/aqueduct.csv data/5050/aqueduct_ft.csv
	@mkdir -p figures
	FIG_W=$(FIG_W) $(PY) scripts/plot_norepl_vs_3rep.py data $@

endif

force:
	@rm -f $(PAPER_FIGS)
	@$(MAKE) all

clean:
	rm -f $(PAPER_FIGS) figures/norepl_vs_3rep.pdf
