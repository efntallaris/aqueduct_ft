#!/usr/bin/env python3
"""Phase breakdown of one donor->recipient handover, three replicas against five.

usage: paper_3vs5_breakdown.py <3rep.json> <5rep.json> <out.png|pdf> [pair] [width_in]
  the json files are written by recovery_breakdown.py next to its figure
  pair       A|B|C (default A -- the pair whose recipient is widened)

Same lanes in both blocks, one shared time axis, so the rounds line up and the extra
hop is visible as displacement rather than as a number. Set CMU_DIR for Computer Modern.

What the figure argues: the phases are identical in both topologies. What changes is
where the round COMMITS. A batch is durable once a majority of the recipient group holds
it, so three replicas stop at F1 and five stop at F2 -- and the F1->F2 relay, which is
off the critical path at three, is on it at five. Chain replication is store and forward:
a follower must hold the whole batch before relaying, so that second hop costs a full
transfer, while the leader's hop to F1 overlaps the donor's send and is nearly free."""
import sys, os, json, glob
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
SHOW_OVERLAP = os.environ.get("SHOW_OVERLAP", "") not in ("", "0", "no")
from matplotlib.patches import Patch
from matplotlib.lines import Line2D
import matplotlib.patheffects as pe

j3, j5, out = sys.argv[1], sys.argv[2], sys.argv[3]
PAIR  = sys.argv[4] if len(sys.argv) > 4 else "A"
# the two blocks are not always 3-vs-5 replicas (e.g. pairwise vs deep pipelining)
TITLE_A = os.environ.get("TITLE_A", "(a) 3 replicas")
TITLE_B = os.environ.get("TITLE_B", "(b) 5 replicas")
# when the two runs differ by an order of magnitude, a shared axis squashes the
# faster one into a sliver: give each block its own x scale instead.
PER_BLOCK_X = bool(os.environ.get("PER_BLOCK_X"))
WIDTH = float(sys.argv[5]) if len(sys.argv) > 5 else 13.0

plt.rcParams.update({"font.family": ["Times New Roman", "Times", "STIXGeneral"],
                     "mathtext.fontset": "stix", "axes.linewidth": .8,
                     "savefig.bbox": "tight", "savefig.pad_inches": .02})
_BOLD_FNAME = None
import matplotlib.font_manager as fm
if os.environ.get("CMU_DIR"):
    for f in glob.glob(os.environ["CMU_DIR"] + "/*.ttf"): fm.fontManager.addfont(f)
    plt.rcParams.update({"font.family": ["CMU Serif"], "mathtext.fontset": "cm"})
    # CMU ships each weight as its own file and findfont will not pick the 700 face by
    # weight= (it returns the 500 roman for "bold", 700 and 800 alike), so name the file.
    _b = glob.glob(os.environ["CMU_DIR"] + "/*700*.ttf")
    if _b:
        _BOLD_FNAME = _b[0]
# FONT_DIR / FONT_FAMILY: the serif the labels are set in. A USENIX paper is Times through
# mathptmx, which is URW Nimbus Roman, while matplotlib's "Times New Roman" is Monotype's
# different drawing of it. TeX Gyre Termes is Nimbus Roman as OpenType, so pointing FONT_DIR
# at it puts this figure in the paper's own face. Math (the arrows) stays with STIX, which is
# Times-metric (AqRaft 2026-11-20).
elif os.environ.get("FONT_DIR"):
    for f in (glob.glob(os.environ["FONT_DIR"] + "/*.otf") +
              glob.glob(os.environ["FONT_DIR"] + "/*.ttf")):
        fm.fontManager.addfont(f)
    plt.rcParams["font.family"] = [os.environ.get("FONT_FAMILY", "TeX Gyre Termes")]

# AqRaft 2026-11-20: sized for PRINT. The canvas is 13 in wide and a paper places it at
# ~7 in, so everything on it is scaled by ~0.54 -- at the old FS=15/12 the in-bar durations
# landed near 6.5 pt on the page. Raised so the smallest text survives that reduction at
# about 8.5 pt, and the bars thickened to match. Override per figure with FS/FS_SM/BAR_H.
FS     = float(os.environ.get("FS", 23))
FS_SM  = float(os.environ.get("FS_SM", 20))
BAR_H  = float(os.environ.get("BAR_H", 0.86))   # lane height used by the bars (was 0.68)
MIN_TRACK = float(os.environ.get("MIN_TRACK", 0.34))  # floor for one track of a split lane
INSIDE_MIN_H = float(os.environ.get("INSIDE_MIN_H", 0.26))  # bar height that still holds a centred label
# Vertical room for the legend, titles and axis label. Tuned for the 13 in canvas; a figure
# rendered natively at one paper column (3.33 in) needs far less, so it is overridable.
EXTRA_H = float(os.environ.get("EXTRA_H", 2.4))
# BAR_LABELS=0 drops the per-bar durations. At one column the plot area is ~2 in wide, so
# four groups across the axis leave each bar ~0.2 in -- the numbers then collide with each
# other and with the commit rules. The bar lengths already encode duration against the
# axis, so dropping the numbers is what makes a one-column version readable; quote the
# values in the caption instead.
BAR_LABELS = os.environ.get("BAR_LABELS", "1") not in ("0", "no", "")
# At one column each bar is ~0.2 in wide, and "0.51 s" does not fit where "0.51" does.
# The x-axis is already labelled "Time of migration (s)", so the unit inside every bar is
# redundant there; keep it on the wide canvas where there is room.
BAR_UNIT = os.environ.get("BAR_UNIT", "s")   # as in the other breakdowns: "0.51s"
# SHOW_HANDOVER=0 drops the donor-NARROW rules and their legend entry. The triangles and
# the dashed rules already mark where each group commits on the recipient; the handover is
# a second, nearly coincident instant that mostly adds clutter at one column.
SHOW_HANDOVER = os.environ.get("SHOW_HANDOVER", "1") not in ("0", "no", "")
# Line weights and marker sizes were tuned on the 13 in canvas. Rendered at one column they
# are proportionally ~4x heavier: the commit rules then cut straight through the durations
# they sit beside. Scale them with the canvas, with a floor so they stay visible in print.
_LWS = 1.0 if WIDTH >= 6 else max(0.55, WIDTH / 13.0 * 2.2)
LW_MAJ = float(os.environ.get("LW_MAJ") or 0) or 1.4 * _LWS   # group durable (recipient)
LW_MIN = 1.0 * _LWS          # handover complete (donor NARROW)
MS_V   = float(os.environ.get("MS_V") or 0) or \
         7.0 * (1.0 if WIDTH >= 6 else max(0.5, WIDTH / 13.0 * 2.0))
# TITLE_BOLD=1 sets the panel titles in bold. Off by default: they sit next to the figure's
# own caption, which is not bold, and the "(a)"/"(b)" in front of them is what tells the two
# panels apart (AqRaft 2026-11-20). fontproperties overrides fontsize, so the size goes in it.
_TB = os.environ.get("TITLE_BOLD", "0") not in ("0", "no", "")
TITLE_FP = (dict(fontproperties=__import__("matplotlib.font_manager", fromlist=["x"])
                 .FontProperties(fname=_BOLD_FNAME, size=FS + 1))
            if (_TB and _BOLD_FNAME) else dict(fontsize=FS + 1, fontweight="bold" if _TB else "normal"))
SHOW_YCSB = False      # the window is entirely pre-handover, so the curve is flat; set True to restore
SHOW_REPLICAS = False  # per-replica receipt rows (F1..F4); set True to restore
# AqRaft 2026-11-20: groups 3 and 4 were #8b8f93 and #b9bdc0, light enough that the white
# duration written inside their bars washed out, and a label written OUTSIDE a bar in the
# bar's own shade was barely on the page at all. Darkened the two light steps so every bar
# still reads as its own shade while carrying legible text, and text colour is now chosen
# from the fill's luminance rather than assumed white (see ink_on).
# Group 3 was #767b80, where white text sits at 4.27:1 -- a coin-flip against black and
# under the 4.5:1 usually taken as the floor for body text. #6b7075 puts it at 5.07:1 while
# staying clearly distinct from group 4, which now takes dark ink at 7.42:1.
SHADE = (os.environ.get("SHADE") or "#2b2f33,#55595e,#7e8389,#a8adb3").split(",")
# group 1..4, dark to light. The ramp is deliberately short: at the old light end the
# fourth group was nearly the colour of the page (AqRaft 2026-11-21).
COMMIT = os.environ.get("COMMIT") or "#111111"
LABEL_INK = "#24272a"        # durations written beside a bar: fixed dark, never the shade

_DARK_INK = "#14171a"

def _lum(hexcol):
    r, g, b = (int(hexcol[i:i + 2], 16) / 255 for i in (1, 3, 5))
    f = lambda c: c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b)

def ink_on(fill):
    """Whichever of white / near-black has the higher WCAG contrast ratio on `fill`.

    AqRaft 2026-11-20: this used a luminance CUTOFF (white below 0.42), which is the usual
    shortcut and is wrong in the middle of the range. Group 4 (#a2a7ac, luminance 0.38) fell
    just under it and got white text at a 2.4:1 ratio, while black would have given 7.4:1 --
    so the two lanes whose rounds overlap, chain replication and its async tail, carried the
    least readable numbers on the figure. Comparing the ratios directly has no cutoff to
    misplace and holds for any palette.
    """
    L = _lum(fill)
    return "#ffffff" if (1.05 / (L + 0.05)) >= ((L + 0.05) / (_lum(_DARK_INK) + 0.05)) else _DARK_INK

def load(p):
    d = json.load(open(p))
    rs = [r for r in d["rounds"] if r["pair"] == PAIR]
    rs.sort(key=lambda r: r["copy"][0])
    return d, rs

d3, r3 = load(j3)
d5, r5 = load(j5)

def hosts_of(d, rs):
    """Followers in chain order, by when the batch actually REACHES them.

    Deliberately keyed on receipt (CHAIN-FORWARDED), not on the index update the
    breakdown json records: a follower relays the batch before applying its own
    index, so its index timestamp lands a whole hop late and makes the commit look
    as though it waited for one fewer replica than it did."""
    recv = d.get("recv", {})
    return [(h, "F%d" % (i + 1)) for i, h in
            enumerate(sorted(recv, key=lambda h: recv[h][0]))]

H3, H5 = hosts_of(d3, r3), hosts_of(d5, r5)
# AqRaft 2026-11-20: on a one-column canvas the single-line lane names ("Async chain
# replication" is ~1.3 in at 8 pt) do not fit the left margin and were clipped, so wrap
# them there. The margin itself is a FRACTION of the figure, which is why this only shows
# up when rendering small: 0.125 is 1.6 in at WIDTH=13 but 0.4 in at 3.33.
# The lane names of the other two breakdown figures, so the three read as one family. This
# figure draws the donor's transfer once, where those two draw the same span twice, once per
# side (AqRaft 2026-11-20).
# At one column the lanes sit ~0.25 in apart, which is less than two lines of 7.5 pt type,
# so all but the longest name is kept on one line and the left margin is widened for them
# rather than wrapping them into each other (AqRaft 2026-11-20).
# "Donor to recipient transfer", not just "Donor": this figure draws that transfer once,
# where the crash-suite panels draw the same span twice, once per side.
LANES = (["Donor to recipient\ntransfer", "Index update", "Chain replication", "Async chain replication"]
         if WIDTH >= 6 else
         ["Donor to recipient\ntransfer", "Index update", "Chain replication", "Async chain\nreplication"])
# DROP_LANES leaves lanes out by key, as paper_recovery.py's knob of the same name does.
# The lane names and the four spans are positional, so both are filtered together. The
# paper drops "idx": the index update reads 0.51 s four times in BOTH blocks, which is the
# same thing the transfer lane above it already says, and a lane is a quarter of the height
# of a figure this short (AqRaft 2026-11-20).
LANE_KEYS = ["copy", "idx", "repl", "async"]
_drop = {k for k in (os.environ.get("DROP_LANES") or "").replace(" ", "").split(",") if k}
if _drop:
    _keep = [i for i, k in enumerate(LANE_KEYS) if k not in _drop]
    LANES = [LANES[i] for i in _keep]
    LANE_KEYS = [LANE_KEYS[i] for i in _keep]

_TW = {}


def _fits_in(txt, span_s, ax, pad=0.03):
    """The largest of FS_SM / FS_SM-1 at which txt fits inside a bar span_s seconds wide, or
    None. The width is MEASURED in the font in use: the old test was "wider than 0.18 s",
    which took no account of the label or the type size, so at five replicas 1.07s, 1.22s and
    1.10s were written across their bars' edges (AqRaft 2026-11-20)."""
    t0, t1 = ax.get_xlim()
    # the axes' width from the GRIDSPEC, not from get_window_extent(): the extent is the
    # pre-layout guess at this point in the drawing and savefig crops the canvas afterwards,
    # so measuring against it let labels through that then overflowed (AqRaft 2026-11-20)
    in_per_s = (ax.figure.get_size_inches()[0] * ax.get_position().width) / (t1 - t0)
    for fs in (FS_SM, FS_SM - 1):
        key = (txt, round(fs, 2))
        if key not in _TW:
            _t = ax.figure.text(0, 0, txt, fontsize=fs)
            try:
                _TW[key] = _t.get_window_extent(
                    renderer=ax.figure.canvas.get_renderer()).width / ax.figure.dpi
            except Exception:
                _TW[key] = len(txt) * fs * 0.40 / 72
            finally:
                _t.remove()
        if _TW[key] + pad <= span_s * in_per_s:
            return fs
    return None


def block_span(rs, d):
    """(lo, hi): the time a block actually occupies, over every lane it draws."""
    starts, ends = [], []
    for r in rs:
        for x in (r.get("copy"), r.get("idx"), r.get("repl"), r.get("async")):
            if x and x[0] is not None:
                starts.append(x[0])
            if x and x[1] is not None:
                ends.append(x[1])
        if r.get("done") is not None:
            ends.append(r["done"])
    ends += [t for v in (d.get("recv") or {}).values() for t in v]
    lo = min(min(starts) if starts else 0.0, -.15) - .12
    return lo, (max(ends) if ends else 5) * 1.04


def block_rows(hosts):            # lane rows + one sub-row per replica
    return len(LANES) + (len(hosts) if SHOW_REPLICAS else 0)

n3, n5 = block_rows(H3), block_rows(H5)
ROW_H = float(os.environ.get("ROW_H", ".78" if SHOW_REPLICAS else "1.75"))  # inches per row: stretches every bar, split lanes included
HS = .50                                   # breathing room between the two topologies
SIDE = os.environ.get("SIDE", "") not in ("", "0", "no")   # side by side, not stacked
# PROP_W=1: each panel as wide as its own run is long. Equal halves leave the shorter
# run a third of empty panel, and the two still share a scale because the width is
# proportional to the span (AqRaft 2026-11-20).
PROP_W = os.environ.get("PROP_W", "0") not in ("0", "no", "")
# (bool() of the string "0" is True, which is how SIDE=0 from a Makefile used to mean yes)
if SHOW_YCSB:
    fig = plt.figure(figsize=(WIDTH, ROW_H * (n3 + n5) + 4.4))
    gs = fig.add_gridspec(3, 1, height_ratios=[n3, n5, 0.52 * (n3 + n5) / 2.6], hspace=HS)
    axes = [fig.add_subplot(gs[0]), None, None]
    axes[1] = fig.add_subplot(gs[1], sharex=None if PER_BLOCK_X else axes[0])
    axes[2] = fig.add_subplot(gs[2], sharex=None if PER_BLOCK_X else axes[0])
elif SIDE:
    # SIDE=1: the two topologies next to each other rather than stacked. Three replicas
    # against five is a comparison, and side by side a reader sees the five-replica blocks
    # reaching further right instead of having to carry the first panel in their head down
    # to the second. One row of lanes instead of two also halves the height, and the lane
    # names are drawn once, on the left panel (AqRaft 2026-11-20).
    fig = plt.figure(figsize=(WIDTH, ROW_H * max(n3, n5) + float(os.environ.get("SIDE_H", 1.30))))
    _s3, _s5 = block_span(r3, d3), block_span(r5, d5)
    _w = ([_s3[1] - _s3[0], _s5[1] - _s5[0]] if PROP_W else [1, 1])
    gs = fig.add_gridspec(1, 2, wspace=float(os.environ.get("WS", .06)), top=.80, bottom=.20,
                          left=float(os.environ.get("LEFT", .135)), right=.995,
                          width_ratios=_w)
    axes = [fig.add_subplot(gs[0]), None, None]
    axes[1] = fig.add_subplot(gs[1], sharex=None if (PER_BLOCK_X or PROP_W) else axes[0],
                              sharey=axes[0])
else:
    fig = plt.figure(figsize=(WIDTH, ROW_H * (n3 + n5) + EXTRA_H))
    gs = fig.add_gridspec(2, 1, height_ratios=[n3, n5], hspace=HS, top=.855,
                          left=(.125 if WIDTH >= 6 else float(os.environ.get("LEFT", .30))),
                          right=(.99 if WIDTH < 6 else None))
    axes = [fig.add_subplot(gs[0]), None, None]
    axes[1] = fig.add_subplot(gs[1], sharex=None if PER_BLOCK_X else axes[0])

# FIX 2026-11-19: a round the kill interrupted has done=None (every crash scenario has
# one or two). These used to reach max() and raise TypeError, so no crash-suite figure
# could be rendered at all. A round that never finished contributes no right-hand edge.
XMAX = max(max((h["t"] for r in r5 for h in (r.get("idx_done") or [])), default=5),
           max((r["done"] for r in r5 if r["done"] is not None), default=5)) + .35

d_of = {}
def recv_at(d, hosts, k):
    return [d["recv"][h][k] for h, _ in hosts if k < len(d["recv"].get(h, []))]

def draw(ax, rs, hosts, title, note, d, bottom=False, ylabels=True):
    d_of[id(rs)] = d
    rows = LANES + (["    %s  %s" % (ro, h) for h, ro in hosts] if SHOW_REPLICAS else [])
    nr = len(rows)
    ypos = {name: nr - 1 - i for i, name in enumerate(rows)}
    lbl_of = {h: "    %s  %s" % (ro, h) for h, ro in hosts}
    chain_spans, lane_spans = [], {}
    for k, r in enumerate(rs):
        c = SHADE[k % len(SHADE)]
        # The breakdown json's repl/async assume majority = leader + F1, which only holds at
        # n=3. Rebuild both from the per-replica receipts: a 2f+1 group commits once f
        # followers hold the batch, so the majority hop runs to F_f and everything after it
        # -- F_f -> ... -> tail -- is the part that is genuinely asynchronous.
        rec = sorted((v[k], h) for h, v in d.get("recv", {}).items() if k < len(v))
        f_need = len(rec) // 2                        # followers in a majority of 2f+1
        maj_end = rec[f_need - 1][0] if f_need and len(rec) >= f_need else None
        tail_end = rec[-1][0] if rec else None
        chain = [r["repl"][0], maj_end] if (r["repl"] and maj_end is not None) else None
        asyn = [maj_end, tail_end] if (maj_end is not None and tail_end is not None
                                       and tail_end > maj_end + .02) else None
        chain_spans.append(chain)
        # index into LANES rather than repeating the names: they differ between the wide
        # and one-column variants, and a literal here silently KeyErrors on the narrow one.
        _spans = {"copy": r["copy"], "idx": r["idx"], "repl": chain, "async": asyn}
        for lane, _k in zip(LANES, LANE_KEYS):
            span = _spans[_k]
            # FIX 2026-11-19: a round interrupted by the kill yields a span with a
            # missing endpoint; it cannot be laid out and must not reach the sort.
            if span and span[0] is not None and span[1] is not None:
                lane_spans.setdefault(lane, []).append((k, span))
        if SHOW_REPLICAS:
            need = (len(hosts) + 1) // 2                      # followers needed for a majority of 2f+1
            for host, _ in hosts:                             # when each replica RECEIVED the batch
                ts = d_of[id(rs)].get("recv", {}).get(host, [])
                if k >= len(ts): continue
                y = ypos[lbl_of[host]]
                waited = sorted(recv_at(d_of[id(rs)], hosts, k))[:need]
                on_path = ts[k] <= (waited[-1] + 1e-9) if waited else False
                ax.plot([ts[k]], [y], marker="|", ms=15, mew=3.0 if on_path else 1.6,
                        color=c, alpha=1.0 if on_path else .45, zorder=3)
        # The group commits when MGN_RECP_DURABLE applies on the RECIPIENT. r["done"] is
        # the donor's DONE, i.e. when the donor's poll noticed -- up to 0.4 s later under
        # a deep pipeline, which drew the commit line well right of the bars it follows.
        # Two distinct instants, 0.02 s apart under pairwise but up to 0.40 s under a deep
        # pipeline, so draw both rather than pick one:
        #   durable  - MGN_RECP_DURABLE applies on the RECIPIENT. Local Raft apply, no RPC.
        #              A recipient leader promoted after this has nothing to resume.
        #   handover - the donor's poll notices, MGN_TXN_DONE commits on the DONOR and
        #              NARROW hands the slots over. This is what gates the next round.
        _dur = d.get("durable") or []
        commit = _dur[k] if k < len(_dur) else r["done"]
        # FIX 2026-11-19: a round the kill interrupted never committed -- no durable entry
        # and no done -- so there is no instant to mark. Draw the round without a marker
        # rather than failing the whole figure.
        if commit is not None:
            # zorder 1 keeps the rule BEHIND the bars (zorder 3) and their labels (4), so a
            # commit that lands inside a block no longer draws a dash across it. The marker
            # and its label stay on top, above the top lane, and say which group committed.
            # drawn in data coordinates rather than with axvline, so the rule stops below
            # the marker instead of running through its label
            ax.plot([commit, commit], [-.45, nr - .30], color=COMMIT, lw=LW_MAJ,
                    ls=(0, (5, 3)), zorder=1, solid_capstyle="butt")
            ax.plot([commit], [nr - .17], marker="v", ms=MS_V, color=COMMIT, zorder=6, clip_on=False)
            ax.text(commit, nr + .02, "G%d" % (k + 1), ha="center", va="bottom",
                    fontsize=FS_SM - .5, color=COMMIT, zorder=7, clip_on=False)
        if SHOW_HANDOVER and r["done"] is not None and commit is not None and r["done"] > commit + .015:
            ax.axvline(r["done"], color=COMMIT, lw=LW_MIN, ls=(0, (1.5, 2.5)), alpha=.55,
                       ymin=.02, ymax=.98, zorder=4)
    for lane, items in lane_spans.items():
        items.sort(key=lambda kv: kv[1][0])
        tracks = []                       # greedy interval colouring: end time of each track
        placed = []
        for k, (a, b) in items:
            t = next((i for i, e in enumerate(tracks) if a >= e - 1e-9), len(tracks))
            if t == len(tracks): tracks.append(b)
            else: tracks[t] = b
            placed.append((k, a, b, t))
        n = max(1, len(tracks))
        full, y0 = BAR_H, ypos[lane]
        h = full / n
        # AqRaft 2026-11-20: a lane whose rounds overlap is split into n stacked tracks, so
        # each bar is only BAR_H/n tall. Chain replication at five replicas needs three
        # tracks -- 0.27 against the 0.80 of a single-track lane -- which made it the
        # thinnest thing on the page precisely where the five-replica cost is being shown.
        # Row pitch is 1.0 and BAR_H leaves slack, so let a split lane borrow it and keep
        # each track at MIN_TRACK where that fits.
        if n > 1 and h < MIN_TRACK:
            full = min(0.96, MIN_TRACK * n)
            h = full / n
        for k, a, b, t in placed:
            # one track: unchanged. Several: stacked top-down, so the earliest group is on top
            yy = y0 if n == 1 else y0 + full / 2 - h / 2 - t * h
            ax.barh(yy, b - a, left=a, height=h * (.92 if n > 1 else 1.0),
                    color=SHADE[k % len(SHADE)], zorder=3)
            # AqRaft 2026-11-20: INSIDE_MIN_H decides inside-vs-beside. It was a bare
            # `h > .3`, and with MIN_TRACK now holding a split track at exactly 0.30 every
            # chain-replication bar missed it by nothing and took the beside-the-bar path.
            # That left one figure with two label styles -- "0.51 s" centred in most lanes,
            # "g1  1.07 s" hanging off the bar in the two that overlap. A track 0.30 of a
            # row tall is 0.42 in here, ample for the text, so the threshold sits below it
            # and every lane labels the same way.
            _dl = "%.2f%s" % (b - a, BAR_UNIT)
            _dfs = _fits_in(_dl, b - a, ax) if BAR_LABELS else None
            if _dfs and h >= INSIDE_MIN_H:
                # inside the bar: the bar itself says which group, so the duration alone
                ax.text((a + b) / 2, yy, _dl, ha="center", va="center",
                        color=ink_on(SHADE[k % len(SHADE)]), fontsize=_dfs, zorder=4)
            elif BAR_LABELS and b - a > .18:
                # AqRaft 2026-11-20: name the group. A lane whose rounds overlap is split
                # into stacked tracks, each too short to hold its label, so every duration
                # is written outside its bar -- and at five replicas the chain-replication
                # row ends up with four loose numbers (1.07, 1.15, 1.22, 1.26) whose owners
                # can only be matched by tracing shades back to the legend. Prefix the
                # group so each number is self-describing.
                # A label written beside a bar often lands on the NEXT group's bar rather
                # than on white (the lanes overlap), so give it a thin light halo: dark ink
                # stays readable on the page and on a mid-grey fill alike.
                ax.text(b + .04, yy, "G%d  %.2f%s" % (k + 1, b - a, BAR_UNIT), ha="left", va="center",
                        color=LABEL_INK, fontsize=FS_SM - 1, zorder=7,
                        path_effects=[pe.withStroke(linewidth=1.8, foreground="#ffffff")])

    # AqRaft 2026-11-20: the commit-overlap marker is OFF by default (SHOW_OVERLAP=1 to
    # restore it). It began as a hatched rectangle over the chain-replication row, which
    # hid the bars and their durations at five replicas; redrawn as a bracket under the
    # row it was legible but still competed with the bars for attention. The overlap is
    # already evident from the bars themselves -- consecutive groups visibly running at
    # the same time -- so the marker earns no space it does not take from the data.
    y = ypos[LANES[LANE_KEYS.index("repl")]]
    for i in range(len(chain_spans) - 1 if SHOW_OVERLAP else 0):
        a, b = chain_spans[i] or (None, None)
        a2, _ = chain_spans[i + 1] or (None, None)
        if a2 is None or b is None or a2 >= b:
            continue
        # AqRaft 2026-11-20: draw the overlap as a slim bracket UNDER the row, not as a
        # hatched rectangle over it. The hatch spanned the full row height (y+-0.40), so at
        # five replicas -- where the overlap covers most of the row -- it sat on top of the
        # bars and their durations: 1.07 and 1.15 were drawn through the hatching and 1.22
        # and 1.26 ended up outside their bars, all four unreadable at print size. The
        # overlap is already legible from the bars themselves (consecutive groups visibly
        # running at the same time); the bracket marks its extent without hiding anything.
        yb = y - .52
        ax.plot([a2, b], [yb, yb], color=COMMIT, lw=1.2, solid_capstyle="butt", zorder=6,
                clip_on=False)
        for xe in (a2, b):
            ax.plot([xe, xe], [yb - .055, yb + .055], color=COMMIT, lw=1.2, zorder=6,
                    clip_on=False)
    ax.set_yticks(range(nr)); ax.set_yticklabels(rows[::-1], fontsize=FS)
    ax.tick_params(axis="y", length=0)      # the bars mark the lanes; the dashes only add ink
    if not ylabels:
        # the panels share a y axis, so blanking the labels here would blank them on the
        # left panel too: hide this axis's copy of the NAMES instead. The tick marks stay,
        # so both panels show where each lane sits (AqRaft 2026-11-20).
        ax.tick_params(axis="y", labelleft=False)
    # The bottom of the range carries the total-duration rule under the last lane, so it is a
    # knob rather than a constant: BOT_PAD in row units (AqRaft 2026-11-22).
    # The top of the range leaves room for the commit markers and their group labels.
    _bot = float(os.environ.get("BOT_PAD", .6))
    ax.set_ylim(-_bot, nr + .38)
    # How long the whole migration takes: a rule from the first transfer to the last group's
    # DONE, drawn in the space below the last lane. It is the one number the two blocks are
    # being compared on, and before this the reader had to subtract two bar ends by eye.
    if os.environ.get("TOTAL_RULE", "1") not in ("0", "no", ""):
        # the migration waits on the MAJORITY, not on the donor's TXN_DONE, so the rule
        # ends at the last group's majority hop (AqRaft 2026-11-22)
        _dones = [c[1] for c in chain_spans if c and c[1] is not None] or \
                 [r["done"] for r in rs if r.get("done") is not None]
        _starts = [r["copy"][0] for r in rs if r.get("copy") and r["copy"][0] is not None]
        if _dones and _starts:
            _a, _b = min(_starts), max(_dones)
            _y = -_bot + float(os.environ.get("TOTAL_Y", .22))
            ax.plot([_a, _b], [_y, _y], color=COMMIT, lw=.9, zorder=6, clip_on=False)
            for _x in (_a, _b):
                ax.plot([_x, _x], [_y - .07, _y + .07], color=COMMIT, lw=.9, zorder=6, clip_on=False)
            # The figure follows ONE pair (PAIR, A by default), so this is that pair's four
            # groups and not the whole cluster's twelve. Said "all groups done" at first, which
            # a reader takes for the whole migration (AqRaft 2026-11-22).
            ax.text((_a + _b) / 2, _y + .10,
                    "four groups to majority: %.2f s" % (_b - _a),
                    ha="center", va="bottom", fontsize=FS_SM, color=COMMIT, zorder=7,
                    clip_on=False)
    if PER_BLOCK_X or PROP_W:
        # FIX 2026-11-19: a round the kill interrupted can carry a span with a missing
        # end (copy/idx) as well as done=None, so collect the ends that exist instead of
        # assuming every round has one. Without this no crash figure renders per-block.
        ends = []
        for r in rs:
            for x in (r["copy"], r["idx"]):
                if x and x[1] is not None:
                    ends.append(x[1])
            if r["done"] is not None:
                ends.append(r["done"])
        ends += [t for v in d.get("recv", {}).values() for t in v]
        # FIX 2026-11-20: derive the LEFT limit too. It was pinned at -0.15, but in a
        # crash figure t=0 is the kill, so a round already in flight starts negative
        # (S1: chain replication begins at -0.99). Its bar was drawn clipped and its
        # in-bar label lost its leading digits -- "0.49 s" rendered as "49 s". Take the
        # earliest start that exists and leave room for the label.
        starts = []
        for r in rs:
            for x in (r.get("copy"), r.get("idx"), r.get("repl"), r.get("async")):
                if x and x[0] is not None:
                    starts.append(x[0])
        _lo, _hi = block_span(rs, d)
        ax.set_xlim(_lo, _hi)
        # one tick spacing for both panels: left to itself matplotlib gives the shorter run
        # finer ticks (0.5 s against 1 s), and two panels on one scale then do not look it
        ax.xaxis.set_major_locator(
            matplotlib.ticker.MultipleLocator(float(os.environ.get("XTICK", 1.0))))
    else:
        starts = []
        for r in rs:
            for x in (r.get("copy"), r.get("idx"), r.get("repl"), r.get("async")):
                if x and x[0] is not None:
                    starts.append(x[0])
        lo = min(starts) if starts else 0.0
        # the shared right edge is the later of the two blocks, not the global XMAX, which
        # counts receipts drawn nowhere and left a third of the shorter panel blank
        _hi = max(block_span(r3, d3)[1], block_span(r5, d5)[1])
        ax.set_xlim(min(-.15, lo - .12), _hi)
        # whole seconds: left to itself matplotlib halves the step once the range shrinks,
        # and 0.0/0.5/1.0 across two panels is more ink than the axis is worth
        ax.xaxis.set_major_locator(
            matplotlib.ticker.MultipleLocator(float(os.environ.get("XTICK", 1.0))))
    ax.set_title(title, loc="center", pad=7, **TITLE_FP)
    # FRAME=1 boxes each panel, as the crash-suite panels are boxed, so the two blocks read
    # as two panels of one figure rather than as two drifting sets of bars. FRAME=0 goes
    # back to the bottom rule alone (AqRaft 2026-11-20).
    if os.environ.get("FRAME", "1") not in ("0", "no", ""):
        for sp in ("top", "right", "left", "bottom"):
            ax.spines[sp].set_visible(True)
            ax.spines[sp].set(color="#000000", linewidth=0.6)
    else:
        for sp in ("top", "right", "left"): ax.spines[sp].set_visible(False)
    ax.tick_params(axis="x", labelbottom=bottom or PER_BLOCK_X, labelsize=FS_SM)
    if (bottom or PER_BLOCK_X) and not SIDE:
        ax.set_xlabel("Time of migration (s)", fontsize=FS)
    # XGRID=1 puts the dotted vertical rules back. They are off by default: the bars carry
    # their own durations and the commit markers carry the instants, so the rules only add
    # ink behind the blocks (AqRaft 2026-11-20).
    if os.environ.get("XGRID", "0") not in ("0", "no", ""):
        ax.grid(True, axis="x", color="#c9cdd0", ls=":", lw=.7, zorder=0)
    ax.set_axisbelow(True)

tot3 = max((d3.get("durable") or [r["done"] for r in r3 if r["done"] is not None]), default=0)
tot5 = max((d5.get("durable") or [r["done"] for r in r5 if r["done"] is not None]), default=0)
draw(axes[0], r3, H3, TITLE_A,
     "commit does not wait for this relay", d3, bottom=SIDE)
draw(axes[1], r5, H5, TITLE_B,
     "the commit DOES wait for this relay — this is the whole difference", d5,
     bottom=SIDE or not SHOW_YCSB, ylabels=not SIDE)
if SIDE:
    fig.supxlabel("Time of migration (s)", fontsize=FS, y=.045)

if SHOW_YCSB:
    ax = axes[2]                                              # YCSB, both topologies
    for d, lab, st in ((d3, "3 replicas", dict(color="#1d1f21", ls="-")),
                       (d5, "5 replicas", dict(color="#6c7175", ls=(0, (3.5, 2))))):
        pts = [(t, v) for t, v in d.get("ycsb_kops", []) if -.3 <= t <= XMAX]
        if pts: ax.plot([p[0] for p in pts], [p[1] for p in pts], lw=1.6, label=lab, **st)
    ax.axvspan(0, tot3, color="#1d1f21", alpha=.07, lw=0)
    ax.axvspan(tot3, tot5, color="#6c7175", alpha=.13, lw=0)
    ax.set_ylabel("YCSB\nKops/s", fontsize=FS)
    ax.text(.012, .12, "serving is flat through the handover in both", transform=ax.transAxes, fontsize=FS_SM, color="#55585b"); ax.set_xlabel("Time of migration (s)", fontsize=FS)
    ax.tick_params(labelsize=FS_SM); ax.set_ylim(0, None)
    ax.legend(fontsize=FS_SM, frameon=False, loc="lower right", ncol=2)
    for sp in ("top", "right", "left"): ax.spines[sp].set_visible(False)
    if os.environ.get("XGRID", "0") not in ("0", "no", ""):
        ax.grid(True, axis="x", color="#c9cdd0", ls=":", lw=.7)
    ax.set_axisbelow(True)

HANDLES = ([Patch(fc=SHADE[i], label="G%d" % (i + 1)) for i in range(4)] +
           ([Line2D([], [], color=COMMIT, lw=1.2, marker="|", ms=7, mew=1.2,
                    label="two groups committing at once")] if SHOW_OVERLAP else []) +
           [
            Line2D([], [], color=COMMIT, lw=LW_MAJ, ls=(0, (5, 3)), label="group durable at the recipient"),
            ] + ([Line2D([], [], color=COMMIT, lw=LW_MIN, ls=(0, (1.5, 2.5)), alpha=.55,
                    label="handover complete (donor NARROW)")] if SHOW_HANDOVER else []) +
           ([Line2D([], [], color=SHADE[1], marker="|", ms=15, mew=3.0, ls="none",
                    label="replica has the batch (commit waits for it)"),
             Line2D([], [], color=SHADE[1], marker="|", ms=15, mew=1.6, alpha=.45, ls="none",
                    label="replica has the batch (not waited for)")] if SHOW_REPLICAS else []))
# AqRaft 2026-11-20: four legend columns are wider than a one-column figure, and with
# savefig.bbox="tight" that silently widens the whole PDF past the requested WIDTH (3.33 in
# came out 5.16 in). Wrap to two columns on a narrow canvas.
LEG_NCOL = int(os.environ.get("LEG_NCOL", 4 if WIDTH >= 6 else 2))
# LEGEND=0 drops the legend band. Every bar already carries its own group, G1..G4, so the
# band repeats what the bars say and costs ~0.3 in of a figure this short. What it alone
# explains, the dashed commit rule, goes in the caption (AqRaft 2026-11-20).
if os.environ.get("LEGEND", "1") not in ("0", "no", ""):
    fig.legend(handles=HANDLES, loc="upper center", ncol=LEG_NCOL, frameon=False, fontsize=FS_SM,
               bbox_to_anchor=(.5, 1.0))
# AqRaft 2026-11-20: rcParams sets savefig.bbox="tight", which GROWS the output past the
# requested WIDTH whenever an artist (the lane labels, the legend) sits outside the axes --
# a figure asked for at 3.33 in came out 3.92 in and would be rescaled again by the
# document. For a figure rendered at its final size, save the figsize exactly and let the
# constrained layout fit the labels inside it instead.
# NB bbox_inches=None does NOT disable the tight box -- None means "fall back to
# rcParams", which is "tight" here. The rcParam itself has to be cleared.
if WIDTH < 6:
    plt.rcParams["savefig.bbox"] = None
fig.savefig(out, dpi=300)
print("wrote", out, " 3rep %.2fs  5rep %.2fs  (+%.2f s)" % (tot3, tot5, tot5 - tot3))
