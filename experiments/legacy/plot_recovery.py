"""Recovery timeline of one crash scenario, from its JSON trace.

    python3 experiments/plot_recovery.py experiments/C1_recovery.json \
        experiments/paper_C1_recovery_replica.pdf

Layout (one column, 239.76 x 257.688 pt):
  top    -- phases: recipient and donor groups, recovery, and per round the copy,
            replication and index update of the pair in flight at the crash
  bottom -- YCSB throughput, with the client outage marked
"""
import json
import sys

import matplotlib
matplotlib.use("pdf")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Rectangle

PT = 1 / 72  # inches per point
FIG_W, FIG_H = 239.76, 257.688  # pt

plt.rcParams.update({
    "font.family": "STIXGeneral",
    "mathtext.fontset": "stix",
    "font.size": 7.5,
    "axes.linewidth": 0.6,
    "hatch.linewidth": 0.5,
    "pdf.fonttype": 42,
})

INK = "#111111"
FAULT = "#c0392b"
BAND = "#f5f5f3"
EDGE = "#555555"
ROUND_FILL = ["#2e2e2e", "#646464", "#a3a3a3", "#d6d6d6"]  # rounds 1..4
ROUND_TEXT = ["white", "white", INK, INK]
RECOVERY_FILL = "#d4d4d4"
REFILL_FILL = "#e2e2e2"

XMIN, XMAX = -0.8, 4.0
# rows from the bottom: (label, y0, height); the recovery row has two lanes
ROWS = [("Index\nupdate", 0.0, 1.0), ("Replication", 1.0, 1.0),
        ("Copy\n(round)", 2.0, 1.0), ("Recovery", 3.0, 1.3),
        ("Donor", 4.3, 1.0), ("Recipient", 5.3, 1.0)]
BANDED = {"Recipient", "Recovery", "Replication"}
BOX_H = 0.56


def row(name):
    for label, y0, h in ROWS:
        if label.split("\n")[0] == name:
            return y0, h
    raise KeyError(name)


def secs(a, b):
    return f"{b - a:.2f} s"


def load(path):
    with open(path) as f:
        return json.load(f)


def fault_span(d):
    """failure detection + election of the crashed group -> (group, start, end)."""
    det = [r for r in d["rows"] if "failure detection" in r[0]]
    ele = [r for r in d["rows"] if r[0].split(":")[0] == det[0][0].split(":")[0]
           and "election" in r[0] and "failure" not in r[0]] if det else []
    if not det:
        return None
    end = ele[0][2] if ele else det[0][2]
    return det[0][0].split(":")[0], det[0][1], end


def donor_group(d):
    for r in d["rows"]:
        if "copy donor" in r[0]:
            return r[0].split()[0]
    return None


def client_outage(d):
    vals = [r[2] for r in d["rows"] if "served again" in r[0]]
    return max(vals) if vals else None


def main(src, dst):
    d = load(src)
    fig = plt.figure(figsize=(FIG_W * PT, FIG_H * PT))
    top = fig.add_axes([57.6 / FIG_W, 89.522089836 / FIG_H,
                        178.56 / FIG_W, 144.405910164 / FIG_H])
    bot = fig.add_axes([57.6 / FIG_W, 25.92 / FIG_H,
                        178.56 / FIG_W, 51.8280521001 / FIG_H], sharex=top)

    # ---- phases
    top.set_xlim(XMIN, XMAX)
    top.set_ylim(0, 6.3)
    for label, y0, h in ROWS:
        if label.split("\n")[0] in BANDED:
            top.add_patch(Rectangle((XMIN, y0), XMAX - XMIN, h, color=BAND, lw=0,
                                    zorder=0))
    top.set_yticks([y0 + h / 2 for _, y0, h in ROWS], [l for l, _, _ in ROWS])
    top.tick_params(axis="y", length=0, pad=2.0, colors=INK)
    for t in top.get_yticklabels():
        t.set_linespacing(0.8514)
    top.tick_params(axis="x", length=2.5, width=0.45, labelbottom=False)
    top.set_ylabel("Phase", color=INK, labelpad=2.0)

    def box(name, t0, t1, fill, text=None, tcolor=INK, edge=None, lw=0.0):
        y0, h = row(name)
        yc = y0 + h / 2
        top.add_patch(Rectangle((t0, yc - BOX_H / 2), t1 - t0, BOX_H, facecolor=fill,
                                edgecolor=edge if edge else fill, lw=lw, zorder=2))
        if text:
            top.text((t0 + t1) / 2, yc, text, ha="center", va="center", fontsize=5.5,
                     color=tcolor, zorder=3, linespacing=0.85)

    f = fault_span(d)
    if f:
        grp, t0, t1 = f
        name = "Donor" if grp == donor_group(d) else "Recipient"
        y0, h = row(name)
        yc = y0 + h / 2
        top.add_patch(Rectangle((t0, yc - BOX_H / 2), t1 - t0, BOX_H, facecolor="white",
                                edgecolor=FAULT, hatch="/////", lw=0.6, zorder=2))
        top.text((t0 + t1) / 2, yc, f"no leader {t1 - t0:.2f} s", ha="center",
                 va="center", fontsize=5.5, color=FAULT, zorder=3,
                 bbox=dict(facecolor="white", edgecolor="none", pad=0.44))

    rounds = [r for r in d.get("rounds", []) if r["pair"] == d["rounds"][0]["pair"]]
    for i, r in enumerate(rounds[:len(ROUND_FILL)]):
        fill, tc = ROUND_FILL[i], ROUND_TEXT[i]
        box("Replication", *r["repl"], fill, secs(*r["repl"]), tc)
        box("Index", *r["idx"], fill, secs(*r["idx"]), tc)
        edge = (INK, 1.0) if r.get("reship") else (None, 0.0)
        box("Copy", *r["copy"], fill, f"{i + 1}\n{secs(*r['copy'])}", tc,
            edge=edge[0], lw=edge[1])

    for ax in (top, bot):
        ax.axvline(0, color=FAULT, lw=0.8, ls=(0, (3, 2)), zorder=4)

    # ---- throughput
    pts = sorted(d["ycsb_kops"])
    bot.plot([p[0] for p in pts], [p[1] for p in pts], color=INK, lw=1.0,
             marker="o", ms=2, mew=1.0, zorder=3)
    bot.set_ylim(0, 440)
    bot.set_yticks([0, 150, 300])
    bot.set_xticks(range(0, int(XMAX) + 1))
    bot.tick_params(length=2.5, width=0.45, pad=1.5, labelsize=7, colors=INK)
    bot.tick_params(axis="x", colors="black", labelcolor=INK)
    bot.tick_params(axis="y", colors="black", labelcolor=INK)
    bot.set_xlabel("Time after the crash (s)", color=INK, labelpad=1)
    bot.set_ylabel("YCSB\nKops/s", color=INK, labelpad=2, linespacing=0.9)
    out = client_outage(d)
    if out is not None:
        bot.plot([out, out], [0, 400], color=INK, lw=0.5, zorder=2)
        bot.annotate("", xy=(0, 385), xytext=(out, 385),
                     arrowprops=dict(arrowstyle="<->", lw=0.6, color=INK,
                                     mutation_scale=7.5, shrinkA=0, shrinkB=0,
                                     capstyle="round"))
        bot.text(out + 0.08, 385, f"clients unavailable {out:.2f} s", fontsize=6.5,
                 color=INK, va="center")

    # ---- legend, drawn in figure points
    def fig_rect(x, y, w, h, **kw):
        fig.add_artist(Rectangle((x / FIG_W, y / FIG_H), w / FIG_W, h / FIG_H,
                                 transform=fig.transFigure, **kw))

    def fig_text(x, y, s):
        fig.text(x / FIG_W, y / FIG_H, s, fontsize=6, color="black", va="baseline")

    fig_rect(62.978437, 250.098, 9.6, 4.59, facecolor="white", edgecolor=FAULT,
             hatch="/////", lw=0.6)
    fig_text(74.9784375, 250.308, "fault")
    fig.add_artist(Line2D([62.978437 / FIG_W, 72.578437 / FIG_W],
                          [245.321125 / FIG_H] * 2, transform=fig.transFigure,
                          color=FAULT, lw=0.8, ls=(0, (3, 2))))
    fig_text(74.9784375, 243.131125, "crash")
    fig_rect(92.450312, 250.098, 9.6, 4.59, facecolor=ROUND_FILL[1], edgecolor=INK,
             lw=1.0)
    fig_text(104.4503125, 250.308, "re-ship")
    fig_rect(92.450312, 242.921125, 9.6, 4.59, facecolor=RECOVERY_FILL,
             edgecolor=EDGE, lw=0.4)
    fig_text(104.4503125, 243.131125, "recovery")
    fig_rect(130.265937, 250.098, 9.6, 4.59, facecolor=REFILL_FILL, edgecolor=EDGE,
             lw=0.4)
    fig_text(142.2659375, 250.308, "refill")
    fig.add_artist(Line2D([135.065937 / FIG_W] * 2, [242.321125 / FIG_H,
                          248.321125 / FIG_H], transform=fig.transFigure,
                          color=INK, lw=1.4, solid_capstyle="butt"))
    fig_text(142.2659375, 243.131125, "serve / in sync")

    fig.savefig(dst)


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
