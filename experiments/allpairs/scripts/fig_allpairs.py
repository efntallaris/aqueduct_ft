#!/usr/bin/env python3
"""The whole migration in one figure: all three pairs, all four rounds of each.

usage: fig_allpairs.py <out> <3rep-tag> <5rep-tag> [width_in]
       e.g. fig_allpairs.py figs/allpairs/pairwise.png S3_r2 S5_r3 6.9

paper_3vs5_breakdown.py takes `pair` as argv[4] and filters to it (line 123), so it can
only ever draw 4 of the migration's 12 rounds. This draws all of them on one axis:

    pair A  sg1 -> sg4      pair B  sg2 -> sg5      pair C  sg3 -> sg6

Reads bd/<tag>_sg4.json, _sg5.json, _sg6.json -- the same per-group jsons
build_breakdown_all.sh makes, each carrying that group's own recv/durable.

Lane spans are rebuilt from the per-replica receipts exactly as
paper_3vs5_breakdown.py:205-222 does: the json's own repl/async assume majority =
leader + F1, true only at n=3. A 2f+1 group commits once f followers hold the batch, so
the majority hop runs to F_f and F_f -> ... -> tail is the genuinely asynchronous part.

Colour encodes the recipient group, lightness the round within it. Under deep the rounds
of one pair overlap, so each lane is split into as many stacked tracks as it needs.
"""
import sys, os, json, glob
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

out, T3, T5 = sys.argv[1], sys.argv[2], sys.argv[3]
W = float(sys.argv[4]) if len(sys.argv) > 4 else 6.9
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
COMPACT = W < 4.0

if os.environ.get("CMU_DIR"):
    import matplotlib.font_manager as fm
    for p in glob.glob(os.path.join(os.environ["CMU_DIR"], "*.ttf")):
        fm.fontManager.addfont(p)
    plt.rcParams["font.family"] = "CMU Serif"
    plt.rcParams["mathtext.fontset"] = "cm"
plt.rcParams["pdf.fonttype"] = plt.rcParams["ps.fonttype"] = 42

FS = 7.0 if COMPACT else 8.5
FS_SM = 5.8 if COMPACT else 7.0
INK, MUTED, GRID = "#1a1a1a", "#555555", "#d8d8d8"
GROUPS = [("A", "sg4"), ("B", "sg5"), ("C", "sg6")]
# The same four greys paper_3vs5_breakdown.py uses (round 1..4, dark to light), so this
# figure sits beside the per-pair ones without a palette change. Hue is NOT used for the
# recipient group: the three pairs run one after another, so position already separates
# them and the repeating dark->light rhythm makes each boundary obvious. They are named by
# a bracket over the top lane instead.
SHADE = ["#1d1f21", "#4a4e52", "#6b7075", "#a2a7ac"]
COMMIT = "#111111"
LANES = ["Donor to recipient\ntransfer", "Index update\non leader",
         "Chain replication", "Async chain\nreplication"]


def shade(g, k):
    return SHADE[k % len(SHADE)]


def ink_on(hexcol):
    c = hexcol.lstrip("#")
    r, g, b = (int(c[i:i+2], 16) / 255.0 for i in (0, 2, 4))
    return "#ffffff" if (0.299 * r + 0.587 * g + 0.114 * b) < 0.56 else "#111111"


def spans(tag):
    """[(lane, pair, group, round_k, a, b)] for all 12 rounds, the durable instants, and
    each group's node count (recv lists the chain FOLLOWERS, so n = len(recv) + 1)."""
    out, durs, nodes = [], [], {}
    for pair, g in GROUPS:
        p = os.path.join(HERE, "bd", "%s_%s.json" % (tag, g))
        d = json.load(open(p))
        rs = [r for r in d["rounds"] if r["pair"] == pair]
        rec_all, dur = d.get("recv", {}), d.get("durable") or []
        nodes[g] = len(rec_all) + 1
        for k, r in enumerate(rs):
            rec = sorted((v[k], h) for h, v in rec_all.items() if k < len(v))
            f = len(rec) // 2
            maj = rec[f - 1][0] if f and len(rec) >= f else None
            tail = rec[-1][0] if rec else None
            chain = [r["repl"][0], maj] if (r["repl"] and maj is not None) else None
            asyn = ([maj, tail] if (maj is not None and tail is not None
                                    and tail > maj + .02) else None)
            for lane, s in zip(LANES, (r["copy"], r["idx"], chain, asyn)):
                if s and s[0] is not None and s[1] is not None:
                    out.append((lane, pair, g, k, s[0], s[1]))
            if k < len(dur):
                durs.append((g, dur[k]))
    return out, durs, nodes


def tracks(items):
    """Greedy interval colouring: overlapping spans in one lane get stacked sub-rows."""
    ends, row = [], {}
    for i, (a, b) in sorted(((i, (x[4], x[5])) for i, x in enumerate(items)),
                            key=lambda kv: kv[1][0]):
        for t, e in enumerate(ends):
            if a >= e - 1e-9:
                ends[t] = b; row[i] = t; break
        else:
            row[i] = len(ends); ends.append(b)
    return row, max(len(ends), 1)


def layout(tag):
    sp, durs, nodes = spans(tag)
    per_lane = {L: [x for x in sp if x[0] == L] for L in LANES}
    rows, ntr = {}, {}
    for L in LANES:
        rows[L], ntr[L] = tracks(per_lane[L])
    return sp, durs, nodes, per_lane, rows, ntr, sum(ntr[L] for L in LANES)


def draw(ax, tag, title, xmax, lay):
    sp, durs, nodes, per_lane, rows, ntr, total = lay
    y, centres = 0.0, {}
    for i, L in enumerate(reversed(LANES)):      # alternate lanes get a faint band, so a
        if i % 2 == 0:                              # lane split into 3 tracks still reads as
            ax.axhspan(y, y + ntr[L], color="#000000",   # one lane
                       alpha=0.035, lw=0, zorder=1)
        y += ntr[L]                                 # (the first cut left this out, so every
    y = 0.0                                         #  band landed on top of the bottom lane)
    for L in reversed(LANES):                       # bottom-up so LANES reads top-down
        n = ntr[L]
        centres[L] = y + n / 2.0
        # 0.80 of ONE row, not of the whole lane. yy already advances by a full row per
        # track, so dividing by n as well made a 3-track lane draw bars a third as tall as
        # a 1-track one: in deep/5rep the chain bars came out 4.1 pt tall with a 5.8 pt
        # label, so "1.05" and "1.17" overflowed above and below the rectangle.
        h = 0.80
        for i, (lane, pair, g, k, a, b) in enumerate(per_lane[L]):
            yy = y + n - 1 - rows[L][i] + 0.5
            c = shade(g, k)
            ax.barh(yy, b - a, h, left=a, color=c, zorder=3, lw=0)
            # Every bar carries its duration. The threshold used to be 5.5% of the axis,
            # which labelled sg4's 1.05 s chain bars but not sg5's and sg6's 0.51 s ones in
            # the same lane -- it read as missing data rather than as a width cutoff. The
            # narrowest bar in either figure is 0.499 s, which is 0.25 in on paper at
            # W=6.9 and takes a label up to 9.5 pt; these are drawn at 5.8 pt.
            if (b - a) > 0:
                ax.text((a + b) / 2, yy, "%.2f" % (b - a), ha="center", va="center",
                        fontsize=FS_SM - 1.2, color=ink_on(c), zorder=6,
                        path_effects=[__import__("matplotlib.patheffects",
                                                 fromlist=["x"]).withStroke(
                            linewidth=1.5, foreground=c)])
        y += n
    for g, t in durs:
        ax.plot([t], [total + 0.18], marker="v", ms=3.0, color=COMMIT,
                clip_on=False, zorder=7)
    # name each recipient group over its own stretch of the axis
    ext, lvl, used = {}, {}, []
    for _, g in GROUPS:
        xs = [x for x in sp if x[2] == g]
        if xs:
            ext[g] = (min(x[4] for x in xs), max(x[5] for x in xs))
    for g, (a, b) in ext.items():
        k = 0
        while any(k == lvl[o] and not (b < ea or a > eb) for o, (ea, eb) in used):
            k += 1
        lvl[g] = k
        used.append((g, (a, b)))
        yb = total + 0.62 + 0.42 * k
        ax.plot([a, b], [yb, yb], color=COMMIT, lw=0.8, solid_capstyle="butt",
                clip_on=False, zorder=7)
        for xe in (a, b):
            ax.plot([xe, xe], [yb - 0.10, yb], color=COMMIT, lw=0.8, clip_on=False, zorder=7)
        ax.text((a + b) / 2, yb + 0.09, "%s  (%d nodes)" % (g, nodes.get(g, 0)),
                ha="center", va="bottom", fontsize=FS_SM,
                color=INK, clip_on=False, zorder=7)
    top_extra = 1.18 + 0.42 * (max(lvl.values()) if lvl else 0)
    ax.set_yticks([centres[L] for L in LANES])
    ax.set_yticklabels(LANES, fontsize=FS, linespacing=1.05)
    ax.set_ylim(0, total + top_extra)
    ax.set_xlim(-0.12, xmax)
    ax.set_title(title, fontsize=FS + 0.5, color=INK, pad=3)
    ax.grid(True, axis="x", color=GRID, ls=":", lw=0.6, zorder=0)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_linewidth(0.6)
    ax.tick_params(labelsize=FS_SM, length=2.5, width=0.6)
    return sp


L3, L5 = layout(T3), layout(T5)
xmax = max(x[5] for x in L3[0] + L5[0]) * 1.02
n3, n5 = L3[6], L5[6]
# 0.215 in per track row keeps the two-line y labels clear at FS 8.5; 1.05 in is the
# axes furniture (two titles, the x label, the gap).
ROW_IN = 0.155 if COMPACT else 0.215
H = 1.35 + (n3 + n5) * ROW_IN
fig, (a3, a5) = plt.subplots(2, 1, figsize=(W, H), sharex=True,
                             gridspec_kw={"hspace": 0.30, "height_ratios": [n3, n5]})
draw(a3, T3, os.environ.get("TITLE_A", T3), xmax, L3)
draw(a5, T5, os.environ.get("TITLE_B", T5), xmax, L5)
a5.set_xlabel("Time of migration (s)", fontsize=FS, color=INK)
h = [Patch(facecolor=SHADE[k], label="round %d" % (k + 1)) for k in range(4)]
h.append(plt.Line2D([], [], marker="v", ms=3.0, ls="none", color=COMMIT,
                    label="round durable"))
# Every span the figure draws, as CSV beside it, so the numbers in a table and the
# rectangles on the page come from one pass over the data.
import csv as _csv
with open(os.path.splitext(out)[0] + ".csv", "w", newline="") as _fh:
    _w = _csv.writer(_fh)
    _w.writerow(["panel", "run_tag", "pair", "group", "group_nodes", "round", "lane",
                 "start_s", "end_s", "duration_s"])
    for _tag, _lay, _title in ((T3, L3, os.environ.get("TITLE_A", T3)),
                               (T5, L5, os.environ.get("TITLE_B", T5))):
        _sp, _durs, _nodes = _lay[0], _lay[1], _lay[2]
        for _lane, _pair, _g, _k, _a, _b in sorted(_sp, key=lambda x: (x[4], x[0])):
            _w.writerow([_title, _tag, _pair, _g, _nodes.get(_g, ""), _k + 1,
                         _lane.replace("\n", " "), "%.3f" % _a, "%.3f" % _b,
                         "%.3f" % (_b - _a)])
        for _i, (_g, _t) in enumerate(_durs):
            _w.writerow([_title, _tag, "", _g, _nodes.get(_g, ""), "", "round durable",
                         "%.3f" % _t, "", ""])
print("wrote %s" % (os.path.splitext(out)[0] + ".csv"))

fig.tight_layout(pad=0.3)
fig.legend(handles=h, fontsize=FS_SM, loc="upper center", bbox_to_anchor=(0.5, -0.025),
           ncol=5, frameon=False, handlelength=1.0, borderpad=0.1, columnspacing=1.4,
           handletextpad=0.45)
for ext in ("pdf", "svg", "png"):
    fig.savefig(os.path.splitext(out)[0] + "." + ext, dpi=360, bbox_inches="tight",
                pad_inches=0.015)
print("wrote %s  (%d+%d spans, %d+%d rows, xmax %.2f s, height %.2f in)"
      % (os.path.splitext(out)[0] + ".{pdf,svg,png}", len(L3[0]), len(L5[0]), n3, n5, xmax, H))
