#!/usr/bin/env python3
"""Redraw the all-pairs breakdown from the CSV that fig_allpairs.py wrote beside it.

usage: fig_allpairs_from_csv.py <in.csv> <out.pdf> [width_in]

Two differences from fig_allpairs.py, both asked for on the paper figure:

  * no recipient-group brackets. The repeating dark -> light round rhythm already marks
    each pair's boundary, and the paper's prose names the pairs.
  * TeX Gyre Termes with STIX math instead of CMU Serif, so the figure carries the same
    typeface as the body text (IEEEtran sets Times, paper.tex loads newtxmath) and as
    every other figure in the paper, all of which embed TeXGyreTermes.

Everything else -- lane order, greedy track stacking, bar height, the per-bar duration
labels, the durable markers, the grey bands, the geometry -- is fig_allpairs.py's, so the
two generators draw the same picture from the same rows. It reads the CSV rather than
bd/<tag>_<group>.json because the CSV holds one row per rectangle and the json run data
does not travel with the paper.
"""
import sys, os, csv, glob, collections
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.patches import Patch
from matplotlib.patheffects import withStroke

src, out = sys.argv[1], sys.argv[2]
W = float(sys.argv[3]) if len(sys.argv) > 3 else 6.9
COMPACT = W < 4.0

TERMES = os.environ.get(
    "TERMES_DIR",
    "/usr/local/texlive/2024/texmf-dist/fonts/opentype/public/tex-gyre")
found = sorted(glob.glob(os.path.join(TERMES, "texgyretermes-*.otf")))
if not found:
    sys.exit("no texgyretermes-*.otf under %s (set TERMES_DIR)" % TERMES)
for p in found:
    fm.fontManager.addfont(p)
plt.rcParams["font.family"] = "TeX Gyre Termes"
plt.rcParams["mathtext.fontset"] = "stix"
plt.rcParams["pdf.fonttype"] = plt.rcParams["ps.fonttype"] = 42

FS = 7.0 if COMPACT else 8.5
FS_SM = 5.8 if COMPACT else 7.0
INK, GRID = "#1a1a1a", "#d8d8d8"
SHADE = ["#1d1f21", "#4a4e52", "#6b7075", "#a2a7ac"]
COMMIT = "#111111"
LANES = ["Donor to recipient\ntransfer", "Index update\non leader",
         "Chain replication", "Async chain\nreplication"]
FLAT = {L.replace("\n", " "): L for L in LANES}


def ink_on(hexcol):
    c = hexcol.lstrip("#")
    r, g, b = (int(c[i:i + 2], 16) / 255.0 for i in (0, 2, 4))
    return "#ffffff" if (0.299 * r + 0.587 * g + 0.114 * b) < 0.56 else "#111111"


def tracks(items):
    """Greedy interval colouring: overlapping spans in one lane get stacked sub-rows."""
    ends, row = [], {}
    for i, (a, b) in sorted(((i, (x[2], x[3])) for i, x in enumerate(items)),
                            key=lambda kv: kv[1][0]):
        for t, e in enumerate(ends):
            if a >= e - 1e-9:
                ends[t] = b
                row[i] = t
                break
        else:
            row[i] = len(ends)
            ends.append(b)
    return row, max(len(ends), 1)


panels, order = collections.defaultdict(lambda: ([], [])), []
for r in csv.DictReader(open(src)):
    t = r["panel"]
    if t not in order:
        order.append(t)
    spans_, durs_ = panels[t]
    if r["lane"] == "round durable":
        durs_.append(float(r["start_s"]))
    else:
        spans_.append((FLAT[r["lane"]], int(r["round"]) - 1,
                       float(r["start_s"]), float(r["end_s"])))
if len(order) != 2:
    sys.exit("expected 2 panels in %s, found %d" % (src, len(order)))


def layout(title):
    sp, durs = panels[title]
    per_lane = {L: [x for x in sp if x[0] == L] for L in LANES}
    rows, ntr = {}, {}
    for L in LANES:
        rows[L], ntr[L] = tracks(per_lane[L])
    return sp, durs, per_lane, rows, ntr, sum(ntr[L] for L in LANES)


def draw(ax, title, xmax, lay):
    sp, durs, per_lane, rows, ntr, total = lay
    y, centres = 0.0, {}
    for i, L in enumerate(reversed(LANES)):
        if i % 2 == 0:
            ax.axhspan(y, y + ntr[L], color="#000000", alpha=0.035, lw=0, zorder=1)
        y += ntr[L]
    y = 0.0
    for L in reversed(LANES):                       # bottom-up so LANES reads top-down
        n = ntr[L]
        centres[L] = y + n / 2.0
        for i, (lane, k, a, b) in enumerate(per_lane[L]):
            yy = y + n - 1 - rows[L][i] + 0.5
            c = SHADE[k % len(SHADE)]
            ax.barh(yy, b - a, 0.80, left=a, color=c, zorder=3, lw=0)
            if b > a:
                ax.text((a + b) / 2, yy, "%.2f" % (b - a), ha="center", va="center",
                        fontsize=FS_SM - 1.2, color=ink_on(c), zorder=6,
                        path_effects=[withStroke(linewidth=1.5, foreground=c)])
        y += n
    for t in durs:
        ax.plot([t], [total + 0.18], marker="v", ms=3.0, color=COMMIT,
                clip_on=False, zorder=7)
    ax.set_yticks([centres[L] for L in LANES])
    ax.set_yticklabels(LANES, fontsize=FS, linespacing=1.05)
    ax.set_ylim(0, total + 0.55)                    # was 1.18 + 0.42/bracket level
    ax.set_xlim(-0.12, xmax)
    ax.set_title(title, fontsize=FS + 0.5, color=INK, pad=3)
    ax.grid(True, axis="x", color=GRID, ls=":", lw=0.6, zorder=0)
    ax.set_axisbelow(True)
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_linewidth(0.6)
    ax.tick_params(labelsize=FS_SM, length=2.5, width=0.6)


LA, LB = layout(order[0]), layout(order[1])
xmax = max(x[3] for x in LA[0] + LB[0]) * 1.02
na, nb = LA[5], LB[5]
ROW_IN = 0.155 if COMPACT else 0.215
H = 1.35 + (na + nb) * ROW_IN
fig, (aa, ab) = plt.subplots(2, 1, figsize=(W, H), sharex=True,
                             gridspec_kw={"hspace": 0.30, "height_ratios": [na, nb]})
draw(aa, order[0], xmax, LA)
draw(ab, order[1], xmax, LB)
ab.set_xlabel("Time of migration (s)", fontsize=FS, color=INK)
h = [Patch(facecolor=SHADE[k], label="round %d" % (k + 1)) for k in range(4)]
h.append(plt.Line2D([], [], marker="v", ms=3.0, ls="none", color=COMMIT,
                    label="round durable"))
fig.tight_layout(pad=0.3)
fig.legend(handles=h, fontsize=FS_SM, loc="upper center", bbox_to_anchor=(0.5, -0.025),
           ncol=5, frameon=False, handlelength=1.0, borderpad=0.1, columnspacing=1.4,
           handletextpad=0.45)
base = os.path.splitext(out)[0]
for ext in ("pdf", "png"):
    fig.savefig(base + "." + ext, dpi=360, bbox_inches="tight", pad_inches=0.015)
print("wrote %s.{pdf,png}  (%d+%d spans, %d+%d rows, xmax %.2f s, height %.2f in)"
      % (base, len(LA[0]), len(LB[0]), na, nb, xmax, H))
