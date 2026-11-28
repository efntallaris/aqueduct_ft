
SCEN      := HEALTHY S1 S2 S5 S10 S11 S12
CRASH     := S1 S2 S5 S10 S11 S12   # the suite without the no-fault baseline
PY        := python3
BLOCK_MIB ?= 2
GRID_XLIM ?= 5,40
GRID_XTICK ?= 20
GRID_NCOL ?= 6
GRID_LAT ?= 1
GRID_LAT_YLIM ?= 0.5,600
GRID_LAT_YTICKS ?= 1,10,100
GRID_TITLE_STATS ?= 0
GRID_FIG_W ?= 7.0
GRID_ROW_IN ?= 1.35
WIDTH     := 4.55        # the standalone phase figure: 12 bars wide enough to carry a duration
BASE_LANE_H ?= 0.30
BASE_BAR_H  ?= 0.74
BASE_GLEG   ?= 1
BASE_XLAB   ?= Time (s)

FONT_DIR ?= $(patsubst %/,%,$(dir $(shell kpsewhich texgyretermes-regular.otf)))
ifneq ($(FONT_DIR),)
export FONT_DIR
endif

export TZ := Etc/GMT+7
unexport CMU_DIR

SHOW_YCSB ?= 0
HEALTHY_LAT_YTICKS ?= 2,5,10
HEALTHY_ROW_IN ?= 1.364
LANE_H    ?= 0.33
GRID_BAR_H ?= 0.72
GRID_LANE_H ?= 0.26
FS_TXT    ?= 7.0
FT_TXT    ?= 8.0
FS_FLOOR  ?= 6.0
BASE_DROP ?= copy,recip
GRID_W      := 2.26
GRID_WL     := 2.78
GRID_LEFTIN := 0.62
GRID_LEFT   := S1 S10
GRID_XMIN   := -1.35
GRID_XMAX   := 4.75
GRID_DUR    ?= %.1f
GRID_DROP   ?= copy

PHASE_PDF := $(SCEN:%=figures/%.pdf)
SMALL_PDF := $(SCEN:%=figures/grid/%.pdf)
PHASE_JSON:= $(SCEN:%=derived/F_%.json)
CSV       := derived/ycsb/ycsb_per_second.csv

.PHONY: all force clean
.SECONDARY: $(PHASE_JSON)

ifeq ($(wildcard data/HEALTHY),)
all:
	@echo experiments/crash_recovery: no data/, keeping the committed PDFs
else

all: $(PHASE_PDF) $(SMALL_PDF) figures/grid6.pdf figures/lat6.pdf figures/healthy_ycsb.pdf $(CSV)

derived/F_%.json: data/% scripts/recovery_breakdown.py scripts/add_recv_durable.py
	@mkdir -p derived
	$(PY) scripts/recovery_breakdown.py $* data/$*/lincheck data/$*/exp derived/F_$*.png \
	    > derived/F_$*.table.txt 2>&1
	@$(PY) scripts/add_recv_durable.py data/$* sg4 $@ >/dev/null 2>&1 || \
	    echo "  ($*: no recv/durable fields)"
	@rm -f derived/F_$*.png

figures/HEALTHY.pdf: BASE_PAIR := ALL
figures/HEALTHY.pdf: BASE_XPAD := XPAD_L=0.25 XPAD_R=0.20
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

figures/grid/%.pdf: derived/F_%.json scripts/paper_recovery.py
	@mkdir -p figures/grid
	@if echo " $(GRID_LEFT) " | grep -q " $* "; then lbl=1; w=$(GRID_WL); g=$(GRID_LEFTIN); \
	 else lbl=0; w=$(GRID_W); g=0.10; fi; \
	 SHOW_REC=0 SHOW_YCSB=$(SHOW_YCSB) SHOW_IDXREP=0 XLABEL=0 YLABEL=0 FLOW_ARROWS=0 \
	 LANE_H=$(GRID_LANE_H) \
	 FS=$(FS_TXT) FT=$(FT_TXT) FS_MIN=$(FS_FLOOR) \
	 XMIN=$(GRID_XMIN) XMAX=$(GRID_XMAX) UNIT=s DUR=$(GRID_DUR) FRAME=1 GAP_IN=0.026 \
	 DROP_LANES=$(GRID_DROP) BAR_H=$(GRID_BAR_H) \
	 ROW_LABELS=$$lbl LEFT_IN=$$g $(PY) scripts/paper_recovery.py $< $@ $$w >/dev/null
	@rm -f figures/grid/$*.png

figures/lat6.pdf: scripts/plot_scaleout_ycsb.py $(CRASH:%=data/%)
	@mkdir -p figures
	@tmp=$$(mktemp -d); for s in $(CRASH); do ln -s "$$PWD/data/$$s/exp" "$$tmp/$$s"; done; \
	 BLOCK_MIB=$(BLOCK_MIB) XLIM=$(GRID_XLIM) XTICK=$(GRID_XTICK) ROW_IN=$(GRID_ROW_IN) \
	 NCOL=6 FIG_W=7.0 SHOW_TPUT=0 TITLE_STATS=0 TITLE_ID=1 \
	 $(PY) scripts/plot_scaleout_ycsb.py "$$tmp" data/lincheck_runs $@ \
	     >/dev/null; rc=$$?; rm -rf "$$tmp"; exit $$rc

figures/grid6.pdf: scripts/plot_scaleout_ycsb.py $(CRASH:%=data/%)
	@mkdir -p figures
	@tmp=$$(mktemp -d); for s in $(CRASH); do ln -s "$$PWD/data/$$s/exp" "$$tmp/$$s"; done; \
	 BLOCK_MIB=$(BLOCK_MIB) XLIM=$(GRID_XLIM) XTICK=$(GRID_XTICK) ROW_IN=$(GRID_ROW_IN) \
	 NCOL=$(GRID_NCOL) FIG_W=$(GRID_FIG_W) SHOW_LAT=$(GRID_LAT) TITLE_STATS=$(GRID_TITLE_STATS) \
	 SHOW_MEAN=1 SHOW_P99=0 LAT_YLIM=$(GRID_LAT_YLIM) LAT_YTICKS=$(GRID_LAT_YTICKS) \
	 TITLE_ID=1 FRAME=1 \
	 $(PY) scripts/plot_scaleout_ycsb.py "$$tmp" data/lincheck_runs $@ \
	     >/dev/null; rc=$$?; rm -rf "$$tmp"; exit $$rc

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
