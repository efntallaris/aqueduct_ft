#!/usr/bin/env python3
"""Aqueduct without replication against Aqueduct with 3 replicas, one series per run.

Two MEASURED runs, each from its own CSV, overlaid rather than put in separate panels:
the question is the gap between them, and a gap is read off one pair of axes.

  data/5050/aqueduct.csv     NR_NOREPL,    2026-11-24, no replication
  data/5050/aqueduct_ft.csv  R3_3REPLICAS, 2026-11-20, 3 replicas

Both are shifted so their logged migration window starts at second 20 (see
experimental_fast/.../scripts/955/import_3rep_vs_norepl.py --mig-start), so the x axis
is not seconds since the client started. Neither run records a percentile, so this
draws the throughput and the read mean only. Nothing here is projected or invented:
the runs are 90s and the axes end where they end.

usage: plot_norepl_vs_3rep.py <data dir> <out.pdf>
"""
import csv, os, sys
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

DATA, OUT = sys.argv[1], sys.argv[2]
FIG_W = float(os.environ.get("FIG_W", 3.22))
ROW_IN = float(os.environ.get("ROW_IN", 1.15))
INK, MUTED, BAND = "#1A1A1A", "#6B6B6B", "#E8E8E8"
FS_LABEL, FS_TICK = 8.0, 7.0
SERIES = [("aqueduct.csv", "no replication", "#1B7F3B", "-"),
          ("aqueduct_ft.csv", "3 replicas", "#7A3FA0", "--")]

plt.rcParams.update({"font.family": "serif", "font.serif": ["Times New Roman", "DejaVu Serif"],
                     "font.size": FS_LABEL, "axes.linewidth": 0.6})
fig, (ax_t, ax_l) = plt.subplots(2, 1, figsize=(FIG_W, ROW_IN * 2), sharex=True,
                                 layout="constrained", gridspec_kw={"height_ratios": [1.2, 1]})
win = []
for fname, label, colour, dash in SERIES:
    rows = list(csv.DictReader(open(os.path.join(DATA, "5050", fname), newline="")))
    sec = [float(r["second"]) for r in rows]
    ax_t.plot(sec, [float(r["current_ops"]) / 1000.0 for r in rows],
              color=colour, lw=1.0, ls=dash, label=label)
    ax_l.plot(sec, [float(r["latency_median"]) / 1000.0 for r in rows],
              color=colour, lw=1.0, ls=dash)
    w = [float(r["second"]) for r in rows if r["in_migration_window"] == "1"]
    if w:
        win += [min(w), max(w)]
if win:
    for ax in (ax_t, ax_l):
        ax.axvspan(min(win), max(win), color=BAND, lw=0, zorder=0)
ax_t.set_ylabel("YCSB th/put\n(kops/s)", fontsize=FS_LABEL, color=INK)
ax_l.set_ylabel("Read mean\n(ms)", fontsize=FS_LABEL, color=INK)
ax_l.set_xlabel("Time (s)", fontsize=FS_LABEL, color=INK)
for ax in (ax_t, ax_l):
    ax.tick_params(labelsize=FS_TICK, colors=MUTED, width=0.6)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
ax_t.legend(frameon=False, fontsize=FS_TICK, loc="lower right", handlelength=1.8,
            borderaxespad=0.2)
fig.savefig(OUT, dpi=400, bbox_inches="tight")

for fname, label, _, _ in SERIES:
    rows = list(csv.DictReader(open(os.path.join(DATA, "5050", fname), newline="")))
    k = [float(r["current_ops"]) / 1000.0 for r in rows]
    print("%-16s %5.0f -> %5.0f kops/s over %d seconds" % (label, k[0], k[-1], len(k)))
