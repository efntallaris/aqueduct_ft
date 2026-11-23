"""Figure 8: three replicas against five, all three pairs, plus a PROJECTION of five everywhere.

Panels (a) and (b) are measured. Only sg4 is widened in the D5 run -- sg5 and sg6 have the same
follower lists in both runs -- so pairs B and C are controls and must not move between them.

Panel (c) is NOT a measurement. No run exists with every recipient group at five replicas, so
it replays pair A's measured five-replica timeline for B and C, keeping the pairs back to back
with the inter-pair gaps of the three-replica run. It is drawn hatched and labelled as
projected. Note it does not equal three times pair A's penalty: pair A is the FASTEST pair at
three replicas, so tripling its delta overstates the total (9.16s here against 9.40s that way).

    paper_3vs5_projected.py D3.json D5.json out.pdf [WIDTH]
"""
import json, os, sys, glob
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.patches import Patch

fd = os.environ.get("FONT_DIR")
if fd:
    for f in glob.glob(fd + "/*.otf") + glob.glob(fd + "/*.ttf"):
        fm.fontManager.addfont(f)
    plt.rcParams["font.family"] = ["TeX Gyre Termes"]

SHADE = "#2b2f33,#55595e,#7e8389,#a8adb3".split(",")
INK, AXIS, COMMIT, MARK = "#1a1a1a", "#333333", "#3a3a3a", "#c0392b"
FS, FS_SM = 8.0, 7.0
D3_JSON, D5_JSON, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
WIDTH = float(sys.argv[4]) if len(sys.argv) > 4 else 7.0
HEIGHT = float(os.environ.get("HEIGHT", 2.95))

def by_pair(path):
    d = json.load(open(path))
    o = {}
    for r in d["rounds"]:
        o.setdefault(r["pair"], []).append(r)
    return ({p: sorted(v, key=lambda r: r["lo"]) for p, v in o.items()}, d.get("recv") or {})


def majority_end(pair, k, r, recv):
    """When group k of this pair reaches a MAJORITY of its recipient group.

    That, not the donor's TXN_DONE, is what the migration waits on, and it is what the dashed
    rule means. A 2f+1 group commits once f followers hold the batch. Per-replica receipts were
    recorded for sg4 only, so pair A at five replicas is read off them (the 2nd of 4 followers);
    every other pair runs at three replicas, where the breakdown json's repl end IS the majority
    hop (leader -> F1) and is correct as it stands (AqRaft 2026-11-22)."""
    if pair == WIDE_PAIR and recv:
        t = sorted(v[k] for v in recv.values() if k < len(v))
        f = len(t) // 2
        if f and len(t) >= f:
            return t[f - 1]
    return r["repl"][1] if r.get("repl") and r["repl"][1] is not None else r["done"]

WIDE_PAIR = os.environ.get("WIDE_PAIR", "A")
(D3, RECV3), (D5, RECV5) = by_pair(D3_JSON), by_pair(D5_JSON)
PAIRS = ["A", "B", "C"]

def spans(pair, rs, recv):
    return [(r["copy"][0], r["copy"][1], majority_end(pair, k, r, recv))
            for k, r in enumerate(rs)]

# the measured gap between consecutive pairs, taken from the 3-replica run
gaps = []
for a, b in zip(PAIRS, PAIRS[1:]):
    gaps.append(min(r["copy"][0] for r in D3[b])
                - max(m for _, _, m in spans(a, D3[a], RECV3)))

# PROJECTION: pair A's MEASURED five-replica timeline replayed for B and C, kept back to back.
tmplA = spans(WIDE_PAIR, D5[WIDE_PAIR], RECV5); t0 = tmplA[0][0]; tmpl = [(a - t0, b - t0, d - t0) for a, b, d in tmplA]
proj, cur = {}, 0.0
for i, p in enumerate(PAIRS):
    proj[p] = [(a + cur, b + cur, d + cur) for a, b, d in tmpl]
    cur = proj[p][-1][2] + (gaps[i] if i < len(gaps) else 0)

# Two panels: every group at three replicas, and every group at five. Pair A's five-replica
# row IS measured -- it is the only group the D5 run widens -- so it is drawn solid, while B
# and C were never run at five and are the projection, hatched. The panel this figure used to
# carry for sg4 alone at five is that same pair-A row, so it is dropped (AqRaft 2026-11-22).
panels = [("(a) measured: every group at 3 replicas",
           {p: spans(p, D3[p], RECV3) for p in PAIRS}, set()),
          ("(b) every group at 5 replicas: pair A measured, B and C projected",
           proj, {"B", "C"})]

fig = plt.figure(figsize=(WIDTH, HEIGHT))
# hspace has to clear a panel title AND the tick labels of the panel above it, and top
# has to leave the legend a band of its own (AqRaft 2026-11-22).
gs = fig.add_gridspec(len(panels), 1, hspace=float(os.environ.get("HSPACE", .95)),
                      top=float(os.environ.get("TOP", .865)), bottom=float(os.environ.get("BOTTOM", .16)),
                      left=.115, right=.995)
# the "5 replicas" tags sit to the right of each span, so the window has to clear them
xmax = max(d for v in proj.values() for _, _, d in v) + float(os.environ.get("XPAD_R", 1.45))
for row, (title, data, proj_pairs) in enumerate(panels):
    ax = fig.add_subplot(gs[row])
    for i, p in enumerate(PAIRS):
        y = len(PAIRS) - 1 - i
        rs = data[p]
        projected = p in proj_pairs
        # The transfers are pipelined, so a group reaches a majority AFTER the next group's
        # transfer has already started: drawn as a rule through the row, G1's majority lands
        # inside G2's bar and reads as G2's. Each group's wait is drawn as its own tail on a
        # lane below the bars instead, in the group's shade (AqRaft 2026-11-22).
        for k, (a, b, dn) in enumerate(rs):
            ax.barh(y + .22, b - a, left=a, height=.38,
                    color="none" if projected else SHADE[k % 4],
                    edgecolor=MARK if projected else "#555555",
                    hatch="////" if projected else None,
                    lw=.5 if projected else .4, zorder=3)
            ty = y - .12
            ax.plot([b, dn], [ty, ty], color=MARK if projected else SHADE[k % 4],
                    lw=1.0, zorder=4, solid_capstyle="butt")
            ax.plot([dn] * 2, [ty - .11, ty + .11],
                    color=MARK if projected else SHADE[k % 4], lw=1.2, zorder=5)
        st, en = rs[0][0], rs[-1][2]
        ax.annotate("", xy=(en, y - .46), xytext=(st, y - .46),
                    arrowprops=dict(arrowstyle="|-|,widthA=.2,widthB=.2",
                                    color=MARK if projected else COMMIT, lw=.7))
        ax.text((st + en) / 2, y - .53, "%.2f s" % (en - st), ha="center", va="top",
                fontsize=FS_SM, color=MARK if projected else COMMIT)
    ax.set_yticks(range(len(PAIRS)))
    ax.set_yticklabels(["pair %s" % p for p in PAIRS][::-1], fontsize=FS)
    for _lab, _p in zip(ax.get_yticklabels(), PAIRS[::-1]):
        if _p in proj_pairs:
            _lab.set_color(MARK)
    ax.tick_params(axis="y", length=0); ax.tick_params(axis="x", labelsize=FS_SM)
    ax.set_ylim(-1.05, len(PAIRS) - .25); ax.set_xlim(-.3, xmax)
    tot = max(d for v in data.values() for _, _, d in v)
    ax.set_title("%s  —  whole migration %.2f s" % (title, tot),
                 fontsize=FS, color=MARK if proj_pairs else INK)
    for sp in ax.spines.values():
        sp.set_color(AXIS); sp.set_linewidth(.6)
fig.legend(handles=[Patch(facecolor=SHADE[i], edgecolor="#555555", lw=.4, label="G%d" % (i + 1))
                    for i in range(4)] +
                   [Patch(facecolor="none", edgecolor=MARK, hatch="////", lw=.5,
                          label="projected, not measured")],
           loc="upper center", ncol=5, frameon=False, fontsize=FS_SM,
           bbox_to_anchor=(.5, 1.0), handlelength=1.1, handleheight=.9, columnspacing=1.3)
fig.text(.555, .012, "Time of migration (s)", ha="center", fontsize=FS, color=INK)
fig.savefig(OUT)
print("wrote", OUT)
for name, data in (("3 rep all", panels[0][1]), ("5 rep all (A measured)", panels[1][1])):
    print("  %-22s total %.2f s" % (name, max(d for v in data.values() for _, _, d in v)))
