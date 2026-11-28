
PY    := python3
PAIR  := A
SIDE  ?= 1
WIDTH := 7.0

FONT_DIR ?= $(patsubst %/,%,$(dir $(shell kpsewhich texgyretermes-regular.otf)))
ifneq ($(FONT_DIR),)
export FONT_DIR
endif

export TZ := Etc/GMT+7
unexport CMU_DIR

.PHONY: all force clean
.SECONDARY: derived/N_D3.json derived/N_D5.json

ifeq ($(wildcard data/D3_r1),)
all:
	@echo experiments/replica_count: no data/, keeping the committed PDF
else

all: figures/replicas_3v5.pdf figures/replicas_allpairs.pdf figures/replicas_projected.pdf

derived/N_D%.json: data/D%_r1 scripts/recovery_breakdown.py scripts/add_recv_durable.py
	@mkdir -p derived
	$(PY) scripts/recovery_breakdown.py HEALTHY data/D$*_r1/lincheck data/D$*_r1/exp \
	    derived/N_D$*.png > derived/N_D$*.table.txt 2>&1
	@$(PY) scripts/add_recv_durable.py data/D$*_r1 sg4 $@ >/dev/null 2>&1 || \
	    echo "  (D$*: no recv/durable fields)"
	@rm -f derived/N_D$*.png

ROW_H  ?= 0.24
SIDE_H ?= 1.40

figures/replicas_3v5.pdf: derived/N_D3.json derived/N_D5.json scripts/paper_3vs5_breakdown.py
	@mkdir -p figures
	SIDE=$(SIDE) ROW_H=$(ROW_H) EXTRA_H=1.26 SIDE_H=$(SIDE_H) FS=8.0 FS_SM=7.0 LEG_NCOL=5 LEFT=0.165 \
	  BOT_PAD=1.55 TOTAL_Y=0.30 \
	  FRAME=1 MIN_TRACK=0.48 SHOW_HANDOVER=0 LEGEND=1 PROP_W=0 MS_V=4.5 LW_MAJ=1.0 COMMIT=#3a3a3a \
	  $(PY) scripts/paper_3vs5_breakdown.py derived/N_D3.json derived/N_D5.json $@ \
	      $(PAIR) $(WIDTH)
	@rm -f figures/replicas_3v5.png

figures/replicas_allpairs.pdf: derived/N_D3.json derived/N_D5.json scripts/paper_3vs5_allpairs.py
	@mkdir -p figures
	HEIGHT=2.25 FS=8.0 FS_SM=7.0 LEFT=0.115 \
	  $(PY) scripts/paper_3vs5_allpairs.py derived/N_D3.json derived/N_D5.json $@ $(WIDTH)

figures/replicas_projected.pdf: derived/N_D3.json derived/N_D5.json scripts/paper_3vs5_projected.py
	@mkdir -p figures
	HEIGHT=2.95 \
	  $(PY) scripts/paper_3vs5_projected.py derived/N_D3.json derived/N_D5.json $@ $(WIDTH)

endif

force:
	@rm -f derived/N_D3.json derived/N_D5.json figures/replicas_3v5.pdf figures/replicas_allpairs.pdf
	@$(MAKE) all

clean:
	rm -f derived/N_D*.json derived/N_D*.table.txt derived/N_D*.png
