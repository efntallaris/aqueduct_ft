"""Figure 8: all three donor-recipient pairs, three replicas against five, on one time scale.

Why this and not the per-lane breakdown: only sg4's per-replica receipts were recorded, so the
chain-replication and async lanes can be rebuilt for pair A alone. Drawing them for B and C
crosses pair B's transfers with pair A's replication, which renders as replication finishing
before the transfer starts. This figure therefore carries only what is measured per pair --
the donor-to-recipient transfer, each group's DONE, and the pair's span -- which is also what
makes the point: sg4 is the only group widened, so B and C are controls and must not move.

    paper_3vs5_allpairs.py D3.json D5.json out.pdf [WIDTH]
"""
import json, os, sys, glob
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.patches import Patch

D3_JSON, D5_JSON, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
WIDTH = float(sys.argv[4]) if len(sys.argv) > 4 else 7.0
HEIGHT = float(os.environ.get("HEIGHT", 2.25))

# A USENIX paper is Times throughout. TeX Gyre Termes is Nimbus Roman as OpenType, so pointing
# FONT_DIR at it makes the figure's type the same drawing as the body text's.
if os.environ.get("FONT_DIR"):
    for f in (glob.glob(os.environ["FONT_DIR"] + "/*.otf") +
              glob.glob(os.environ["FONT_DIR"] + "/*.ttf")):
        fm.fontManager.addfont(f)
    plt.rcParams["font.family"] = [os.environ.get("FONT_FAMILY", "TeX Gyre Termes")]
else:
    plt.rcParams["font.family"] = ["Times New Roman", "Times", "STIXGeneral"]

SHADE = (os.environ.get("SHADE") or "#2b2f33,#55595e,#7e8389,#a8adb3").split(",")
INK, AXIS, COMMIT, MARK = "#1a1a1a", "#333333", "#3a3a3a", "#c0392b"
FS = float(os.environ.get("FS", 8.0))
FS_SM = float(os.environ.get("FS_SM", 7.0))
PAIRS = (os.environ.get("PAIRS") or "A,B,C").split(",")
WIDE = os.environ.get("WIDE_SG", "sg4")          # the recipient group the D5 run widens
WIDE_PAIR = os.environ.get("WIDE_PAIR", "A")     # and the pair it belongs to


def rounds_by_pair(path):
    d = json.load(open(path))
    by = {}
    for r in d["rounds"]:
        by.setdefault(r["pair"], []).append(r)
    return {p: sorted(v, key=lambda r: r["lo"]) for p, v in by.items()}


runs = {"3": rounds_by_pair(D3_JSON), "5": rounds_by_pair(D5_JSON)}

fig = plt.figure(figsize=(WIDTH, HEIGHT))
gs = fig.add_gridspec(1, 2, wspace=.06, top=.78, bottom=.26,
                      left=float(os.environ.get("LEFT", .115)), right=.995)
axes = [fig.add_subplot(gs[0])]
axes.append(fig.add_subplot(gs[1], sharex=axes[0], sharey=axes[0]))

xmax = max(r["done"] for rs in runs["5"].values() for r in rs) + .3
for ax, tag, title in ((axes[0], "3", "(a) %s at 3 replicas" % WIDE),
                       (axes[1], "5", "(b) %s at 5 replicas" % WIDE)):
    for i, p in enumerate(PAIRS):
        y = len(PAIRS) - 1 - i
        rs = runs[tag][p]
        for k, r in enumerate(rs):
            a, b = r["copy"]
            ax.barh(y, b - a, left=a, height=.52, color=SHADE[k % len(SHADE)],
                    edgecolor="#555555", lw=.4, zorder=3)
            ax.plot([r["done"]] * 2, [y - .30, y + .30], color=COMMIT, lw=1.1,
                    ls=(0, (2.4, 1.6)), zorder=5)
        st, en = min(r["copy"][0] for r in rs), max(r["done"] for r in rs)
        ax.annotate("", xy=(en, y - .42), xytext=(st, y - .42),
                    arrowprops=dict(arrowstyle="|-|,widthA=.2,widthB=.2", color=COMMIT, lw=.7))
        ax.text((st + en) / 2, y - .50, "%.2f s" % (en - st), ha="center", va="top",
                fontsize=FS_SM, color=COMMIT)
    # The panels share a y axis, so a per-panel label list leaks from one panel to the other:
    # name the rows once and mark the widened group inside the panel that widens it.
    ax.set_yticks(range(len(PAIRS)))
    ax.set_yticklabels(["pair %s" % p for p in PAIRS][::-1], fontsize=FS)
    if tag == "5":
        _y = len(PAIRS) - 1 - PAIRS.index(WIDE_PAIR)
        _en = max(r["done"] for r in runs["5"][WIDE_PAIR])
        ax.text(_en + .25, _y, "5 replicas", va="center", ha="left", fontsize=FS_SM, color=MARK)
    ax.tick_params(axis="y", length=0)
    ax.tick_params(axis="x", labelsize=FS_SM)
    ax.set_ylim(-.85, len(PAIRS) - .4)
    ax.set_xlim(-.25, xmax)
    ax.set_title(title, fontsize=FS, color=INK)
    for sp in ax.spines.values():
        sp.set_color(AXIS); sp.set_linewidth(.6)
axes[1].tick_params(axis="y", labelleft=False)

fig.legend(handles=[Patch(facecolor=SHADE[i % len(SHADE)], edgecolor="#555555", lw=.4,
                          label="G%d" % (i + 1)) for i in range(4)],
           loc="upper center", ncol=5, frameon=False, fontsize=FS_SM,
           bbox_to_anchor=(.5, 1.01), handlelength=1.1, handleheight=.9, columnspacing=1.4)
fig.text(.555, .02, os.environ.get("XLAB", "Time of migration (s)"),
         ha="center", fontsize=FS, color=INK)
fig.savefig(OUT)
spans = {t: {p: max(r["done"] for r in runs[t][p]) - min(r["copy"][0] for r in runs[t][p])
             for p in PAIRS} for t in ("3", "5")}
print("wrote %s  " % OUT + "  ".join(
    "%s %.2f->%.2f" % (p, spans["3"][p], spans["5"][p]) for p in PAIRS))
