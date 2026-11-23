# Three replicas per group against five: raw logs in data/ -> figures/replicas_3v5.pdf.
#
#   make -C experiments/replica_count          # only if the data or the scripts changed
#   make -C experiments/replica_count force    # from the logs up
#
# TZ and CMU_DIR are set for the same two reasons as in experiments/crash_recovery/Makefile:
# the redis logs carry the hosts' local time (UTC-7) with no offset, and this paper is
# Times, not Computer Modern.
#
# The knobs on paper_3vs5_breakdown.py are the figure as it appears in the paper:
#   ROW_H=0.26       lane height (the script's default 1.75 is for a full-width figure)
#   FS=8 FS_SM=6.5   type sizes in pt, which is what they are on paper
#   LEG_NCOL=3       legend in three columns, so it fits above the blocks
#   SHOW_HANDOVER=0  drop the "handover complete (donor NARROW)" marker
# The trailing "A 7.0" is the pair drawn and the width in inches.

PY    := python3
PAIR  := A
# SIDE=1 puts the two topologies next to each other across the full text width, which is a
# comparison read as a comparison. SIDE=0 WIDTH=3.33 stacks them in one column instead.
SIDE  ?= 1
WIDTH := 7.0

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

.PHONY: all force clean
.SECONDARY: derived/N_D3.json derived/N_D5.json

ifeq ($(wildcard data/D3_r1),)
all:
	@echo "experiments/replica_count: no data/, keeping the committed PDF"
else

all: figures/replicas_3v5.pdf figures/replicas_allpairs.pdf figures/replicas_projected.pdf

# Both runs are no-fault migrations, so they are extracted as HEALTHY: t=0 is the
# migration start rather than a crash.
derived/N_D%.json: data/D%_r1 scripts/recovery_breakdown.py scripts/add_recv_durable.py
	@mkdir -p derived
	$(PY) scripts/recovery_breakdown.py HEALTHY data/D$*_r1/lincheck data/D$*_r1/exp \
	    derived/N_D$*.png > derived/N_D$*.table.txt 2>&1
	@$(PY) scripts/add_recv_durable.py data/D$*_r1 sg4 $@ >/dev/null 2>&1 || \
	    echo "  (D$*: no recv/durable fields)"
	@rm -f derived/N_D$*.png

figures/replicas_3v5.pdf: derived/N_D3.json derived/N_D5.json scripts/paper_3vs5_breakdown.py
	@mkdir -p figures
	SIDE=$(SIDE) ROW_H=0.30 EXTRA_H=1.26 SIDE_H=1.62 FS=8.0 FS_SM=7.0 LEG_NCOL=5 LEFT=0.165 \
	  BOT_PAD=1.55 TOTAL_Y=0.30 \
	  FRAME=1 MIN_TRACK=0.48 SHOW_HANDOVER=0 LEGEND=1 PROP_W=0 MS_V=4.5 LW_MAJ=1.0 COMMIT=#3a3a3a \
	  $(PY) scripts/paper_3vs5_breakdown.py derived/N_D3.json derived/N_D5.json $@ \
	      $(PAIR) $(WIDTH)
	@rm -f figures/replicas_3v5.png

# All three pairs, transfer lane and DONE only. The per-lane breakdown above can only be drawn
# for pair A, because only sg4's per-replica receipts were recorded; this one carries what is
# measured for every pair and shows B and C holding still while A stretches.
figures/replicas_allpairs.pdf: derived/N_D3.json derived/N_D5.json scripts/paper_3vs5_allpairs.py
	@mkdir -p figures
	HEIGHT=2.25 FS=8.0 FS_SM=7.0 LEFT=0.115 \
	  $(PY) scripts/paper_3vs5_allpairs.py derived/N_D3.json derived/N_D5.json $@ $(WIDTH)

# The two measured panels plus a projection of five replicas everywhere. The projection is
# drawn hatched: no such run exists, it replays pair A's measured 5-replica timeline for B
# and C. See the script's docstring for why that is not 3x pair A's penalty.
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
