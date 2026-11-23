# Crash-suite figures: raw CloudLab logs in data/ -> the PDFs in figures/.
#
# Driven by the paper's top-level Makefile, so a `make` of the paper regenerates any
# figure whose data or script changed and leaves the rest alone. Run it on its own with
#
#   make -C experiments/crash_recovery          # only what is out of date
#   make -C experiments/crash_recovery force    # everything, from the logs up
#
# Two settings are not optional, and both are set here rather than left to the shell:
#
#   TZ=Etc/GMT+7  The redis logs carry the CloudLab hosts' local time (UTC-7) with no
#                 offset and recovery_breakdown.py parses them as local time. In any
#                 other timezone the YCSB overlay, the recovery rows and the x axis are
#                 displaced by the difference, which does not look like an error -- it
#                 looks like a nearly empty figure spanning tens of thousands of seconds.
#
#   no CMU_DIR    The scripts render in Computer Modern when CMU_DIR points at one.
#                 This paper is USENIX, which is Times (mathptmx), so we let them fall
#                 back to Times/STIX and the labels match the body type.
#
# BLOCK_MIB is the SAMM block size the figure's volumes and rates are computed from. It is
# the real 2 MiB, so those numbers are measured. It defaulted to 9.700638 while the titles
# rescaled these runs' volumes, which the paper no longer does, and
# anything other than 2 here is an extrapolation that has to be declared wherever it is used.

SCEN      := HEALTHY S1 S2 S5 S10 S11 S12
CRASH     := S1 S2 S5 S10 S11 S12   # the suite without the no-fault baseline
PY        := python3
BLOCK_MIB ?= 2
# seconds of the run the grid figure shows. The migration and the recovery are over by
# ~30 s and the tail is flat, so a narrower window gives the interesting part more width.
GRID_XLIM ?= 5,40
# two numbers on the time axis are enough at this size, and the rows are a little shorter
# than the script's default 1.8 in so the figure takes less of the page
GRID_XTICK ?= 20
# two columns rather than three: six panels across 7 in give each about 1.85 in of plot,
# two columns give each about 2.9 in, at the cost of a third row
GRID_NCOL ?= 6
# One full-width figure: six scenarios across, each a throughput panel over a latency panel,
# with no per-panel stats line -- the duration and the volume per scenario are in Table 2.
# GRID_LAT=0 drops the latency row (figures/lat6.pdf is then the strip that carries it), and
# GRID_NCOL=2 GRID_FIG_W=3.33 gives a one-column form.
GRID_LAT ?= 1
# The YCSB mean runs 0.64-402 ms across the six crash runs, so the strip is logarithmic
# over 0.5-600 ms with a decade ladder.
GRID_LAT_YLIM ?= 0.5,600
GRID_LAT_YTICKS ?= 1,10,100
GRID_TITLE_STATS ?= 0
GRID_FIG_W ?= 7.0
GRID_ROW_IN ?= 1.35
WIDTH     := 4.55        # the standalone phase figure: 12 bars wide enough to carry a duration
# the baseline figure's own lane height, so scaling it does not drag the crash grid
BASE_LANE_H ?= 0.30
# a bar's share of its lane: enough that a two-line label clears the rectangle's edges
BASE_BAR_H  ?= 0.74
# a band naming the G1..G4 shades, since Figure 5's caption no longer does
BASE_GLEG   ?= 1
# the axis title of the phase figure
BASE_XLAB   ?= Time (s)

# The paper is Times through mathptmx, which is URW Nimbus Roman. TeX Gyre Termes is that
# same face as OpenType and ships with TeX Live, so the figures are set in the paper's own
# type rather than in Monotype's Times New Roman, which is a different drawing of Times and
# does not match it on the page. With no TeX Live the variable stays empty and the scripts
# fall back to Times/STIX as before.
FONT_DIR ?= $(patsubst %/,%,$(dir $(shell kpsewhich texgyretermes-regular.otf 2>/dev/null)))
ifneq ($(FONT_DIR),)
export FONT_DIR
endif

export TZ := Etc/GMT+7
unexport CMU_DIR

# Two variants of the same breakdown, neither with the YCSB throughput panel, which the
# paper carries once in the throughput + latency grid instead of once per scenario:
#
#   figures/<SC>.pdf       standalone: the same lanes as a grid panel, with the lane names
#                          and the time-axis title of its own, at one column. The paper uses
#                          it for the no-fault baseline. No flow arrows: every bar names its
#                          group, which follows a group down the lanes without drawing a
#                          line for it.
#   figures/grid/<SC>.pdf  a panel of the six-scenario figure: no arrows and no axis title,
#                          since the grid states those once. 2.21 in tall.
#                          Only the panels in GRID_LEFT carry the lane names, and they are
#                          rendered GRID_WL wide against GRID_W for the rest -- wider by
#                          exactly the label gutter, so every panel ends up with the same
#                          1.83 in of plot area and one shared time scale.
#
# SHOW_YCSB=1 brings the throughput panel back.
SHOW_YCSB ?= 0
# The four latency ticks of figures/healthy_ycsb.pdf. Its 1.2-60 ms range would otherwise
# get the 1-2-5 ladder's five.
HEALTHY_LAT_YTICKS ?= 2,5,10
# (b) is drawn to the same height as (a), which is 1.80 in since it gained the legend
# band. The script's height is ROW_IN * 1.17 for a single compact panel.
HEALTHY_ROW_IN ?= 1.364
# LANE_H: one lane's height in inches, 0.33 in the script's own default. Shorter here so the
# floats stop taking a page each. Too far down and the two-line "G1 / 0.51s" labels stop
# fitting and fall back to the duration alone.
LANE_H    ?= 0.33
# A bar of the six-scenario panels as a fraction of its lane. The script's own default is
# 0.56, which left 0.146in of the 0.332in lane empty above and below every bar. A lane that
# stacks several steps is capped at 0.82 of its row instead, so raising this thickens only the
# one-bar lanes (AqRaft 2026-11-22).
GRID_BAR_H ?= 0.72
# Type on paper. FS is the in-bar annotations, FT the lane and axis labels, and FS_FLOOR
# the floor under the label ladder: a label that does not fit at the floor is left out
# rather than set at a size nobody can read. Before this the grid panels carried 112
# characters at 4.7 pt, against a 10 pt body and 9 pt captions.
FS_TXT    ?= 7.0
FT_TXT    ?= 8.0
FS_FLOOR  ?= 6.0
# The no-fault baseline drops the two lanes that say nothing in a run without a fault: the
# Recipient lane, which is where faults are drawn, and the Donor lane, which repeats
# Recipient (L) transfer exactly. The crash panels keep both.
BASE_DROP ?= copy,recip
# Three panels and the figure's rotated y title come to 7.61 in: 0.16 for the title, then
# 2.83 + 2.31 + 2.31. That is 0.61 in WIDER than the 7.00 in text width, so the figure is
# centred in a \makebox and bleeds about 0.3 in into each margin -- deliberate, to buy the
# panels width. Check your venue's margin rule before submitting. The left column carries
# the lane names in a GRID_LEFTIN gutter, the others a bare 0.10 in, and each width is its
# gutter + 2.16 in of plot + 0.05 in, so every panel has the same plot area and time scale. The axis titles
# are set once by the figure in LaTeX rather than six times here, which is why the panels
# are rendered with XLABEL=0 YLABEL=0.
GRID_W      := 2.26
GRID_WL     := 2.78
GRID_LEFTIN := 0.62
GRID_LEFT   := S1 S10
# one window for all six panels, wide enough on the left to hold the earliest round any of
# them draws (-1.22 s) so no bar is clipped out of its own duration label
GRID_XMIN   := -1.35
GRID_XMAX   := 4.75
GRID_DUR    ?= %.1f
# the transfer lane repeats the donor lane: the same writes, seen from the other side
GRID_DROP   ?= copy

PHASE_PDF := $(SCEN:%=figures/%.pdf)
SMALL_PDF := $(SCEN:%=figures/grid/%.pdf)
PHASE_JSON:= $(SCEN:%=derived/F_%.json)
CSV       := derived/ycsb/ycsb_per_second.csv

.PHONY: all force clean
.SECONDARY: $(PHASE_JSON)

# A clone without the raw logs still builds the paper: the PDFs are committed, and with
# no data/ there is nothing to regenerate them from, so do nothing rather than fail.
ifeq ($(wildcard data/HEALTHY),)
all:
	@echo "experiments/crash_recovery: no data/, keeping the committed PDFs"
else

all: $(PHASE_PDF) $(SMALL_PDF) figures/grid6.pdf figures/lat6.pdf figures/healthy_ycsb.pdf $(CSV)

derived/F_%.json: data/% scripts/recovery_breakdown.py scripts/add_recv_durable.py
	@mkdir -p derived
	$(PY) scripts/recovery_breakdown.py $* data/$*/lincheck data/$*/exp derived/F_$*.png \
	    > derived/F_$*.table.txt 2>&1
	@$(PY) scripts/add_recv_durable.py data/$* sg4 $@ >/dev/null 2>&1 || \
	    echo "  ($*: no recv/durable fields)"
	@rm -f derived/F_$*.png

# Drawn at its final size with 7-9 pt type. Include it with no width= -- rescaling in
# LaTeX throws the type sizes off.
figures/HEALTHY.pdf: BASE_PAIR := ALL
figures/HEALTHY.pdf: BASE_XPAD := XPAD_L=0.25 XPAD_R=0.20
# the client panel beside it counts from the start of the YCSB run: the migration begins 19 s in
figures/HEALTHY.pdf: BASE_XOFF := XOFF=19 XSTEP=1
figures/HEALTHY.pdf: BASE_XLAB := Time of migration (s)
figures/%.pdf: derived/F_%.json scripts/paper_recovery.py
	@mkdir -p figures
	SHOW_REC=0 SHOW_YCSB=$(SHOW_YCSB) SHOW_IDXREP=0 FLOW_ARROWS=0 UNIT=s LANE_H=$(LANE_H) \
	    FS=$(FS_TXT) FT=$(FT_TXT) FS_MIN=$(FS_FLOOR) XLAB="$(BASE_XLAB)" BOTTOM_IN=0.274 \
	    LANE_H=$(BASE_LANE_H) BAR_H=$(BASE_BAR_H) GLEG=$(BASE_GLEG) WRAP=1 $(BASE_XPAD) $(BASE_XOFF) \
	    DROP_LANES=$(BASE_DROP) \
	    $(PY) scripts/paper_recovery.py $< $@ $(WIDTH) $(BASE_PAIR) >/dev/null
	@rm -f figures/$*.png

# A panel of the six-scenario figure. The arrows are dropped because a panel this size reads
# better without them, and the axis title because the grid gives it once under the bottom row.
figures/grid/%.pdf: derived/F_%.json scripts/paper_recovery.py
	@mkdir -p figures/grid
	@if echo " $(GRID_LEFT) " | grep -q " $* "; then lbl=1; w=$(GRID_WL); g=$(GRID_LEFTIN); \
	 else lbl=0; w=$(GRID_W); g=0.10; fi; \
	 SHOW_REC=0 SHOW_YCSB=$(SHOW_YCSB) SHOW_IDXREP=0 XLABEL=0 YLABEL=0 FLOW_ARROWS=0 \
	 LANE_H=$(LANE_H) \
	 FS=$(FS_TXT) FT=$(FT_TXT) FS_MIN=$(FS_FLOOR) \
	 XMIN=$(GRID_XMIN) XMAX=$(GRID_XMAX) UNIT=s DUR=$(GRID_DUR) FRAME=1 GAP_IN=0.026 \
	 DROP_LANES=$(GRID_DROP) BAR_H=$(GRID_BAR_H) \
	 ROW_LABELS=$$lbl LEFT_IN=$$g $(PY) scripts/paper_recovery.py $< $@ $$w >/dev/null
	@rm -f figures/grid/$*.png

# The latency of the same six runs, as one full-width row. It is a strip rather than a row
# under each throughput panel: side by side the six panels cost about 1.2 in of page where
# stacking them under the throughput cost 2.6 in.
figures/lat6.pdf: scripts/plot_scaleout_ycsb.py $(CRASH:%=data/%)
	@mkdir -p figures
	@tmp=$$(mktemp -d); for s in $(CRASH); do ln -s "$$PWD/data/$$s/exp" "$$tmp/$$s"; done; \
	 BLOCK_MIB=$(BLOCK_MIB) XLIM=$(GRID_XLIM) XTICK=$(GRID_XTICK) ROW_IN=$(GRID_ROW_IN) \
	 NCOL=6 FIG_W=7.0 SHOW_TPUT=0 TITLE_STATS=0 TITLE_ID=1 \
	 $(PY) scripts/plot_scaleout_ycsb.py "$$tmp" data/lincheck_runs $@ \
	     >/dev/null; rc=$$?; rm -rf "$$tmp"; exit $$rc

# The six crash scenarios. HEALTHY is not one of them: its throughput panel belongs beside
# the no-fault phase breakdown, which is what figures/healthy_ycsb.pdf is for.
figures/grid6.pdf: scripts/plot_scaleout_ycsb.py $(CRASH:%=data/%)
	@mkdir -p figures
	@tmp=$$(mktemp -d); for s in $(CRASH); do ln -s "$$PWD/data/$$s/exp" "$$tmp/$$s"; done; \
	 BLOCK_MIB=$(BLOCK_MIB) XLIM=$(GRID_XLIM) XTICK=$(GRID_XTICK) ROW_IN=$(GRID_ROW_IN) \
	 NCOL=$(GRID_NCOL) FIG_W=$(GRID_FIG_W) SHOW_LAT=$(GRID_LAT) TITLE_STATS=$(GRID_TITLE_STATS) \
	 SHOW_MEAN=1 SHOW_P99=0 LAT_YLIM=$(GRID_LAT_YLIM) LAT_YTICKS=$(GRID_LAT_YTICKS) \
	 TITLE_ID=1 FRAME=1 \
	 $(PY) scripts/plot_scaleout_ycsb.py "$$tmp" data/lincheck_runs $@ \
	     >/dev/null; rc=$$?; rm -rf "$$tmp"; exit $$rc

# The same per-second throughput and latency for the no-fault run alone, one column wide, to
# sit beside the no-fault phase breakdown. The trailing scenario list puts the script in its
# one-column mode.
figures/healthy_ycsb.pdf: scripts/plot_scaleout_ycsb.py data/HEALTHY
	@mkdir -p figures
	@tmp=$$(mktemp -d); ln -s "$$PWD/data/HEALTHY/exp" "$$tmp/HEALTHY"; \
	 BLOCK_MIB=$(BLOCK_MIB) XLIM=$(GRID_XLIM) XTICK=$(GRID_XTICK) ROW_IN=$(HEALTHY_ROW_IN) FIG_W=2.38 SHOW_MEAN=1 SHOW_P99=0 LAT_YLIM=1.5,12 LAT_YTICKS=$(HEALTHY_LAT_YTICKS) \
	 TITLE_STATS=0 FRAME=1 PANEL_TITLE=0 \
	 $(PY) scripts/plot_scaleout_ycsb.py "$$tmp" data/lincheck_runs $@ HEALTHY \
	     >/dev/null; rc=$$?; rm -rf "$$tmp"; exit $$rc

$(CSV): scripts/ycsb_csv.py $(SCEN:%=data/%)
	@mkdir -p derived/ycsb
	$(PY) scripts/ycsb_csv.py data derived/ycsb | sed 's/^/  /'

endif

force:
	@rm -f $(PHASE_JSON) $(PHASE_PDF) $(SMALL_PDF) figures/grid6.pdf figures/lat6.pdf figures/healthy_ycsb.pdf $(CSV)
	@$(MAKE) all

clean:
	rm -f derived/F_*.json derived/F_*.table.txt derived/F_*.png
