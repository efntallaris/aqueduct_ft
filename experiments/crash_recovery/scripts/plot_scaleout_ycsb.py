#!/usr/bin/env python3
"""3 -> 6 scale-out, one panel pair per scenario: total YCSB throughput (all clients summed)
and, below it, latency over time, with the migration window shaded and the crash marked.

Latency has two sources:
  - mean read / update latency per second, from the YCSB status lines (the runs use
    measurementtype=timeseries, which records no percentiles);
  - p99 read / write latency per second, from the per-operation history of the
    linearizability client (32 threads x 50 ops/s, running next to YCSB on ycsb0).

usage: plot_scaleout_ycsb.py <ycsb-root> <lincheck-root> <out.png> [<scenarios>]
  <ycsb-root>      has HEALTHY/, S1/ ... (this experiment's logs/) or scaleout3to6_lin_healthy/,
                   scaleout3to6_crash_s1/ ... (/tmp/experiments, overwritten by every new run);
                   each with ycsb/ and migration_window.txt
  <lincheck-root>  has HEALTHY_q*_*/, S1_q*_*/ ... at any depth (run.log with the kill time, history.jsonl)
  <scenarios>      e.g. HEALTHY,S6,S7: compact single-column version (3.33 in wide) with just these
                   scenarios side by side, throughput on top and latency below
"""
import os, re, sys, json, datetime, pathlib, collections
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

ycsb_root, lin_root, out = pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]), sys.argv[3]
PANELS = [
    ("scaleout3to6_lin_healthy", "HEALTHY", "No fault"),
    ("scaleout3to6_crash_s1", "S1", "S1: recipient leader"),
    ("scaleout3to6_crash_s2", "S2", "S2: donor leader"),
    # S3 (donor follower) and S4 (recipient follower) removed 2026-11-06
    ("scaleout3to6_crash_s5", "S5", "S5: both leaders"),   # called S8 until 2026-10-05
    ("scaleout3to6_crash_s8", "S8", "S8: donor leader, registered"),
    ("scaleout3to6_crash_s9", "S9", "S9: two leaders, two pairs"),
    ("scaleout3to6_crash_s10", "S10", "S10: no majority"),              # recipient leader, round only on it
    ("scaleout3to6_crash_s11", "S11", "S11: majority, after durable"),  # recipient leader after RECP_DURABLE
    ("scaleout3to6_crash_s12", "S12", "S12: majority, data on F1"),     # recipient leader, round on F1 not F2
]
# SETUP=3to4 in the environment: the single-recipient runs (lin_healthy, crash_s1 ... or HEALTHY, S1 ...).
if os.environ.get("SETUP") == "3to4":
    PANELS = [("lin_healthy", "HEALTHY", "No fault"), ("crash_s1", "S1", "S1: recipient leader"),
              ("crash_s2", "S2", "S2: donor leader"), ("crash_s3", "S3", "S3: donor follower"),
              ("crash_s4", "S4", "S4: recipient follower"),
              ("crash_s5", "S5", "S5: both leaders")]      # S5 was called S8 until 2026-10-05
def run_dir(name, sc): return ycsb_root / name if (ycsb_root / name).exists() else ycsb_root / sc
PANELS = [p for p in PANELS if run_dir(p[0], p[1]).exists()]        # only the scenarios that were run
COMPACT = sys.argv[4].split(",") if len(sys.argv) > 4 else None
if COMPACT:
    SHORT = {"HEALTHY": "No fault", "S1": "S1: recip. leader", "S2": "S2: donor leader", "S3": "S3: donor follower",
             "S4": "S4: recip. follower", "S5": "S5: both leaders", "S6": "S6: recipient host", "S7": "S7: donor host",
             "S8": "S8: donor leader", "S9": "S9: two leaders",
             "S10": "S10: no majority", "S11": "S11: majority", "S12": "S12: data on F1"}
    PANELS = [(n, sc, SHORT[sc]) for want in COMPACT for n, sc, _ in PANELS if sc == want]
    NCOL, WIDTH = len(PANELS), 3.33                                  # USENIX column width
else:
    NCOL, WIDTH = (3, 6.0) if len(PANELS) <= 6 else (4, 7.0)
# NCOL/FIG_W override the shape. Six panels default to three columns at 6.0 in, which leaves
# a text-width float an inch short; the paper sets FIG_W=7.0 (AqRaft 2026-11-20).
NCOL = int(os.environ.get("NCOL", NCOL))
WIDTH = float(os.environ.get("FIG_W", WIDTH))
# Type sizes (pt): panel titles, axis titles and legend, tick labels.
# the smaller set whenever the figure is a one-column float, however that came about
FS_TITLE, FS_LABEL, FS_TICK = (7.5, 7, 6.5) if (COMPACT or WIDTH < 4.5) else (8.5, 8, 7.5)
INK, MUTED, AXIS, CRASH = "#1a1a1a", "#555555", "#333333", "#c0392b"
LINE, BAND = "#000000", "#e9e9e9"
FAILC = "#c0392b"   # failed reads: the fault color
READ, WRITE = ("#111111", "#8c8c8c") if os.environ.get("GRAY") else ("#0072B2", "#D55E00")
P99_LS = (0, (1, 1.2))
# The read mean is dashed and the write mean solid, so the two are told apart by style as
# well as by colour -- the figure survives being printed in greyscale (AqRaft 2026-11-22).
READ_LS = (0, (1.8, 1.1))
# Stroke widths (pt), one hierarchy: data > p99 > crash marker > axes.
LW_DATA, LW_P99, LW_CRASH, LW_AXIS = (0.9, 0.8, 0.7, 0.5) if COMPACT else (1.1, 0.9, 0.8, 0.6)
# the bridge over a second with no completed operation: thinner than the data, and grey, so it
# never passes for a measured value
GAPC, LW_GAP = "#9a9a9a", (0.6 if COMPACT else 0.7)
# seconds shown; the quick runs last about 90 s. XLIM=30,110 in the environment for the 3-minute 30M runs.
XLIM = tuple(int(v) for v in os.environ.get("XLIM", "10,60").split(","))
pat = re.compile(r'^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d):\d+ \d+ sec: \d+ operations; ([\d.]+) current ops/sec')
lat_pat = {op: re.compile(r'\[%s AverageLatency\(us\)=([\d.]+)\]' % op) for op in ("READ", "UPDATE", "READ-FAILED")}
FMT = "%Y-%m-%d %H:%M:%S"

def load(run):
    clients, lats = [], {"READ": {}, "UPDATE": {}, "READ-FAILED": {}}
    for f in sorted(run.glob("ycsb/*/tmp/ycsb_output_ycsb*")):
        if "load" in f.name: continue
        d = {}
        for l in open(f, errors="ignore"):
            m = pat.match(l)
            if not m: continue
            t = datetime.datetime.strptime(m.group(1), FMT)
            d[t] = float(m.group(2))
            for op, p in lat_pat.items():
                lm = p.search(l)
                if lm: lats[op].setdefault(t, []).append((float(lm.group(1)) / 1000, d[t]))
        clients.append(d)
    ts = sorted(set().union(*[set(d) for d in clients]))
    t0 = next(t for t in ts if any(d.get(t, 0) > 0 for d in clients))
    ts = [t for t in ts if t >= t0]
    total = [sum(d.get(t, 0) for d in clients) / 1000 for t in ts]
    # Mean latency (ms) across clients, weighted by each client's throughput in that second;
    # a second in which no client completed an operation of that type has no value.
    def mean(v):
        w = sum(k for _, k in v)
        return sum(a * k for a, k in v) / w if w else float("nan")
    lat = {op: [mean(lats[op].get(t, [])) for t in ts] for op in lats}
    return t0, [(t - t0).total_seconds() for t in ts], total, lat

def near(t0, hms, off_h=0):
    h, mi, se = map(int, hms.split(":"))
    t = t0.replace(hour=h, minute=mi, second=se) + datetime.timedelta(hours=off_h)
    while t < t0 - datetime.timedelta(hours=12): t += datetime.timedelta(days=1)
    while t > t0 + datetime.timedelta(hours=12): t -= datetime.timedelta(days=1)
    return (t - t0).total_seconds()

def p99_series(lin, t0):
    """Per-second p99 (ms) of the linearizability client's completed operations.
    Its timestamps are ns since the client started; run.log gives that start to the second,
    so these series are aligned with YCSB to about +-1 s."""
    m = re.search(r"\[lin (\d\d:\d\d:\d\d)\] history client started", (lin / "run.log").read_text(errors="ignore"))
    if not m or not (lin / "history.jsonl").exists(): return {}
    off = near(t0, m.group(1))
    b = {"read": collections.defaultdict(list), "write": collections.defaultdict(list)}
    for l in open(lin / "history.jsonl", errors="ignore"):
        try: r = json.loads(l)
        except ValueError: continue                      # a line cut short when the client was stopped
        # every attempt that returned, ok or not: a read that fails during a crash (a double read
        # with one leg down) took that long too, and leaving it out hid the outage (2026-11-07)
        if r.get("phase") != "run" or not r.get("ret"): continue
        sec = int(r["ret"] // 10**9 + off)
        b["read" if r["op"] == "get" else "write"][sec].append((r["ret"] - r["inv"]) / 1e6)
    res = {}
    for op, d in b.items():
        xs = sorted(d)
        res[op] = (xs, [sorted(d[s])[min(len(d[s]) - 1, int(0.99 * len(d[s])))] for s in xs])
    return res

def read_fail_share(lin, t0):
    """Per second: share of the probe client's reads that did not succeed (a double read with a
    leg down, a timeout). YCSB's status lines give the mean of its successful and of its failed
    reads but not how many of each, so this share weights the two (see below)."""
    m = re.search(r"\[lin (\d\d:\d\d:\d\d)\] history client started", (lin / "run.log").read_text(errors="ignore"))
    if not m or not (lin / "history.jsonl").exists(): return {}
    off = near(t0, m.group(1))
    n, f = collections.Counter(), collections.Counter()
    for l in open(lin / "history.jsonl", errors="ignore"):
        try: r = json.loads(l)
        except ValueError: continue
        if r.get("phase") != "run" or r.get("op") != "get" or not r.get("ret"): continue
        sec = int(r["ret"] // 10**9 + off)
        n[sec] += 1
        if r.get("status") != "ok": f[sec] += 1
    return {sec: f[sec] / n[sec] for sec in n}

DREW_GAP = []


def bridge(a, xs, ys, color=None, lw=None, z=2, ls="-"):
    """Join a latency line across the seconds it has no value for.

    A second in which no client completed an operation of that type has no mean, so the line
    breaks there (AqRaft 2026-11-20: at the crash, throughput reaches 0.00 kops/s for one second
    in S2, S5, S11 and S12, and the break read as a plotting fault).

    AqRaft 2026-11-22: the bridge used to be a faint grey dashed segment, so that no measurement
    could be read off it. It is now drawn in the series' own colour, width and solid style, on
    the series' own layer, so each line is continuous across the crash. The cost is that the
    interpolated second is no longer distinguishable from a measured one."""
    i, n = 0, len(ys)
    while i < n:
        if ys[i] == ys[i]:                                  # a value: look for the next gap
            i += 1; continue
        j = i
        while j < n and ys[j] != ys[j]: j += 1
        if i > 0 and j < n:                                 # a gap with a value on either side
            a.plot([xs[i - 1], xs[j]], [ys[i - 1], ys[j]], color=color or GAPC,
                   lw=lw or LW_GAP, zorder=z, ls=ls,
                   solid_capstyle="round", solid_joinstyle="round", dash_capstyle="round")
            DREW_GAP.append(True)      # so the legend names it only if it is on the page
        i = j


tz = round((datetime.datetime.utcnow() - datetime.datetime.now()).total_seconds() / 3600)
# Drawn at print size (6 or 7 in wide; the USENIX text width is 7 in), so 7-9 pt here is 7-9 pt on paper.
plt.rcParams.update({"font.family": ["Times New Roman", "Times", "STIXGeneral"], "mathtext.fontset": "stix", "font.size": FS_LABEL,
                     "axes.edgecolor": AXIS, "axes.linewidth": LW_AXIS,
                     "xtick.color": AXIS, "ytick.color": AXIS, "xtick.labelcolor": INK,
                     "ytick.labelcolor": INK, "xtick.labelsize": FS_TICK, "ytick.labelsize": FS_TICK,
                     "pdf.fonttype": 42, "ps.fonttype": 42})
import os as _os, glob as _glob, matplotlib.font_manager as _fm
if _os.environ.get("CMU_DIR"):     # Computer Modern (CMU Serif) for every label, LaTeX-style math
    for _f in _glob.glob(_os.environ["CMU_DIR"] + "/*.ttf"): _fm.fontManager.addfont(_f)
    plt.rcParams.update({"font.family": ["CMU Serif"], "mathtext.fontset": "cm"})
# FONT_DIR / FONT_FAMILY: the serif the labels are set in. A USENIX paper is Times through
# mathptmx, which is URW Nimbus Roman, while matplotlib's "Times New Roman" is Monotype's
# different drawing of it. TeX Gyre Termes is Nimbus Roman as OpenType, so pointing FONT_DIR
# at it puts the figure in the paper's own face (AqRaft 2026-11-20).
elif _os.environ.get("FONT_DIR"):
    for _f in (_glob.glob(_os.environ["FONT_DIR"] + "/*.otf") +
               _glob.glob(_os.environ["FONT_DIR"] + "/*.ttf")):
        _fm.fontManager.addfont(_f)
    plt.rcParams["font.family"] = [_os.environ.get("FONT_FAMILY", "TeX Gyre Termes")]
nrow = -(-len(PANELS) // NCOL)
# Rows alternate throughput / latency, so each scenario is a throughput panel with its latency below.
spare = nrow * NCOL - len(PANELS)             # empty grid cells: room for the legend
_ROW_IN = float(os.environ.get("ROW_IN", 1.8))   # height of one scenario row, in inches
# SHOW_LAT=0 drops the latency panel under each scenario. It halves the figure, and what it
# costs is a curve whose numbers the text already states (AqRaft 2026-11-20).
SHOW_LAT = os.environ.get("SHOW_LAT", "1") not in ("0", "no", "")
SHOW_TPUT = os.environ.get("SHOW_TPUT", "1") not in ("0", "no", "")
# The per-second mean latency is off (AqRaft 2026-11-21): the p99 is what the text argues
# from, two series per operation crowded the panel, and the mean was the only series that
# needed the no-ops-completed bridge. SHOW_MEAN=1 brings it and the bridge back.
SHOW_MEAN = os.environ.get("SHOW_MEAN", "0") in ("1", "yes")
# SHOW_P99=0 drops the linearizability client's p99. That client issues a fixed trickle of
# operations for the correctness check, so its latency does not fall when the cluster scales
# out, and a flat curve under a throughput that doubles reads as a broken measurement. The
# YCSB mean does fall, 4.95 ms to 2.78 ms on the no-fault run (AqRaft 2026-11-22).
SHOW_P99 = os.environ.get("SHOW_P99", "1") not in ("0", "no", "")
# TITLE_ID=1 titles each panel with the scenario's name alone. At six panels across a text
# width there is about an inch each, which "S11: majority, after durable" does not fit.
TITLE_ID = os.environ.get("TITLE_ID") in ("1", "yes")
# The runs are named for the crash suite's own numbering (S1, S2, S5, S10, S11, S12), which has
# gaps because the suite has scenarios the paper does not report. The paper numbers them
# contiguously instead, so the panel titles are translated here rather than renaming the data
# directories (AqRaft 2026-11-22).
PAPER_ID = {"S1": "S1", "S2": "S2", "S5": "S3", "S10": "S4", "S11": "S5", "S12": "S6"}
# PANEL_TITLE=0: no title over the panel. For a single-panel figure whose subcaption
# already names the run, the title is a repeat that pushes the plot frame down and
# out of line with the figure beside it (AqRaft 2026-11-20).
PANEL_TITLE = os.environ.get("PANEL_TITLE", "1") not in ("0", "no", "")
# FRAME=1 boxes each panel. Off by default, which is how this figure has always been
# drawn; the paper turns it on so the three evaluation figures are framed alike.
FRAME = os.environ.get("FRAME") in ("1", "yes")
# TITLE_STATS=0 drops the "9.2 s, 83.3 GB, 72.8 Gb/s" line under each panel title. The
# duration is the Migration column of the scenario table and the volume is the same in
# every run, so in the paper the line is one more thing to read in six places.
TITLE_STATS = os.environ.get("TITLE_STATS", "1") not in ("0", "no", "")
if SHOW_LAT and SHOW_TPUT:          # both series: two axes per scenario, stacked
    fig, axes = plt.subplots(2 * nrow, NCOL,
                             figsize=(WIDTH, (_ROW_IN * 1.17 if COMPACT else
                                              _ROW_IN * nrow + (0.2 if spare else 0.5))), sharex=True,
                             layout="constrained", gridspec_kw={"height_ratios": [1.2, 1] * nrow},
                             squeeze=False)
    pairs = [(axes[2 * r][c], axes[2 * r + 1][c]) for r in range(nrow) for c in range(NCOL)]
else:
    # one axis per scenario. The axes of the half that is not shown are not merely hidden --
    # a hidden axis still holds its slot in the layout, which left a band of white under
    # every row -- they are created on a throwaway figure that is never saved, so the code
    # below can go on filling them while this figure shows one series per scenario.
    fig, axes = plt.subplots(nrow, NCOL,
                             figsize=(WIDTH, _ROW_IN * 0.62 * nrow + 0.42), sharex=True,
                             layout="constrained", squeeze=False)
    _sink, _sax = plt.subplots(nrow, NCOL, squeeze=False)
    if SHOW_TPUT:
        pairs = [(axes[r][c], _sax[r][c]) for r in range(nrow) for c in range(NCOL)]
    else:
        pairs = [(_sax[r][c], axes[r][c]) for r in range(nrow) for c in range(NCOL)]
for top, bot in pairs[1:]: top.sharey(pairs[0][0]); bot.sharey(pairs[0][1])
ymax = xmax = 0
DREW_CRASH = []            # whether any panel has a crash line to name in a legend
for i, ((ax, lax), (name, sc, title)) in enumerate(zip(pairs, PANELS)):
    run = run_dir(name, sc)
    if not run.exists():
        ax.set_title(title + " (no data)", fontsize=FS_TITLE, loc="center", color=MUTED); lax.set_axis_off(); continue
    t0, x, total, lat = load(run)
    # The last samples are the clients shutting down, not the system: drop them.
    tail = sorted(total[-12:-2])[5] if len(total) > 14 else 0
    while len(total) > 2 and total[-1] < 0.9 * tail:
        x.pop(); total.pop(); lat["READ"].pop(); lat["UPDATE"].pop(); lat["READ-FAILED"].pop()
    ymax, xmax = max(ymax, max(total)), max(xmax, x[-1])
    m = re.search(r"FULL.*\[(\d\d:\d\d:\d\d)\.\d+ -> (\d\d:\d\d:\d\d)\.\d+\]", (run / "migration_window.txt").read_text())
    md = re.search(r"FULL[^\n]*?([\d.]+)s", (run / "migration_window.txt").read_text())
    if md and float(md.group(1)) > 0:
        # nominal data moved (every slot is one 2 MiB block) over the whole migration window;
        # after a crash some rounds are sent twice, which this does not count
        gib = (3 * 1365 if os.environ.get("SETUP") == "3to4" else 3 * 2730) * float(os.environ.get("BLOCK_MIB", "2")) / 1024
        dur = float(md.group(1))
        if os.environ.get("RDMA_GBPS"):   # the rate while the RDMA transfers run, not the window average
            title += "\n%.1f s, %.1f GiB, RDMA %s Gb/s" % (dur, gib, os.environ["RDMA_GBPS"]) if TITLE_STATS else ""
        else:
            title += ("\n%.1f s, %.1f GB, %.1f Gb/s" % (dur, gib * 1.073741824, gib * 8 * 1.073741824 / dur)) if TITLE_STATS else ""
    if m:
        w0, w1 = near(t0, m.group(1), tz), near(t0, m.group(2), tz)   # redis logs: local time
        for a in (ax, lax): a.axvspan(w0, w1, color=BAND, lw=0, zorder=0)
    # The lincheck run of this YCSB run: the latest one of this scenario started before it (within 15 min).
    lins = [(datetime.datetime.strptime(d.name[-15:], "%Y%m%d_%H%M%S"), d) for d in lin_root.glob(f"**/{sc}_q*_*") if d.is_dir()]
    lins = sorted((t, d) for t, d in lins if 0 <= (t0 - t).total_seconds() < 900)
    lin = lins[-1][1] if lins else None
    if lin is not None:
        for hms, _ in re.findall(r"\[crash_inject (\d\d:\d\d:\d\d)\] KILLED (\S+)", (lin / "run.log").read_text(errors="ignore")):
            for a in (ax, lax): a.axvline(near(t0, hms), color=CRASH, lw=LW_CRASH, ls=(0, (3, 2)), zorder=2)   # injector: UTC, like YCSB
            DREW_CRASH.append(True)
        for op, c in (("write", WRITE), ("read", READ)):
            if not SHOW_P99: break
            px, py = p99_series(lin, t0).get(op, ([], []))
            keep = [(a, b) for a, b in zip(px, py) if a <= x[-1]]
            if keep: lax.plot(*zip(*keep), color=c, lw=LW_P99, ls=P99_LS, zorder=3)
    ax.plot(x, total, color=LINE, lw=LW_DATA, solid_capstyle="round", solid_joinstyle="round", zorder=3)
    if SHOW_MEAN:
        bridge(lax, x, lat["UPDATE"], color=WRITE, lw=LW_DATA, z=4)
        lax.plot(x, lat["UPDATE"], color=WRITE, lw=LW_DATA, solid_capstyle="round", solid_joinstyle="round", zorder=4)
    # Mean read latency over ALL reads, failed ones included (2026-11-07): in a second with failed
    # reads, mean = (1-f)*mean_ok + f*mean_failed, with f the share of the probe client's reads that
    # failed in that second. Failed reads faster than 1 ms are reads of absent keys (YCSB counts them
    # as failed all run long) and are left out.
    share = read_fail_share(lin, t0) if lin is not None else {}
    rd = []
    for a, ok_ms, f_ms in zip(x, lat["READ"], lat["READ-FAILED"]):
        f = share.get(int(round(a)), 0.0)
        if f_ms == f_ms and f_ms >= 1.0 and f > 0:
            rd.append((1 - f) * ok_ms + f * f_ms if ok_ms == ok_ms else f_ms)
        else:
            rd.append(ok_ms)
    if SHOW_MEAN:
        bridge(lax, x, rd, color=READ, lw=LW_DATA, z=5, ls=READ_LS)
        lax.plot(x, rd, color=READ, lw=LW_DATA, ls=READ_LS, dash_capstyle="round", zorder=5)
    _ttl = (PAPER_ID.get(sc, sc) if TITLE_ID else title) if PANEL_TITLE else ""
    ax.set_title(_ttl, fontsize=FS_TITLE, loc="center", color=INK,
                 pad=3 if COMPACT else 4)
    if not SHOW_TPUT:          # the shown axis is the latency one: title it instead
        lax.set_title(_ttl, fontsize=FS_TITLE, loc="center",
                      color=INK, pad=3 if COMPACT else 4)
        ax.set_title("")
    col = i % NCOL
    for a in (ax, lax):
        a.tick_params(length=2 if COMPACT else 2.5, width=LW_AXIS, pad=1.5 if COMPACT else 2, labelleft=col == 0, labelbottom=False)
        if FRAME:
            # box every panel, as the phase figures are boxed
            for s_ in ("top", "right", "bottom", "left"):
                a.spines[s_].set_visible(True)
                a.spines[s_].set(color="#000000", linewidth=0.6)
        else:
            for s_ in ("top", "right"): a.spines[s_].set_visible(False)
    lax.tick_params(labelbottom=True)                           # under every scenario: all rows get the same gap
    ax.tick_params(labelbottom=not SHOW_LAT)
    if not SHOW_TPUT:
        lax.tick_params(labelbottom=True)
    if col == 0:
        # The axis titles are rotated, so their LENGTH is a height. "YCSB throughput" is
        # taller than a 1.5 in row's upper panel and ran into the latency title below it, so
        # the long form is kept only while the rows are tall enough for it (AqRaft 2026-11-20).
        ax.set_ylabel("YCSB th/put\n(kops/s)" if (COMPACT or _ROW_IN < 1.7) else "YCSB throughput\n(kops/s)",
                      color=INK, linespacing=0.9)
        lax.set_ylabel("Latency\n(ms)", color=INK, linespacing=0.9)
        for a in (ax, lax): a.yaxis.set_label_coords(-0.12 * NCOL if COMPACT else -0.22 if NCOL == 3 else -0.27, 0.5)        # same x for both: labels line up
# Latency goes from under 1 ms to seconds after a crash: log scale. LAT_YLIM narrows the
# range for a figure that has no crash in it -- the no-fault run never leaves 3-30 ms, and
# on the full 0.3-3000 range two thirds of its panel is empty decades (AqRaft 2026-11-21).
_LY = [float(v) for v in os.environ.get("LAT_YLIM", "0.3,3000").split(",")]
_LT = [t for t in (1, 2, 5, 10, 20, 50, 100, 200, 500, 1000, 2000) if _LY[0] < t < _LY[1]]
# a narrow range has only one power of ten in it, so fall back to a 1-2-5 ladder
if len([t for t in (1, 10, 100, 1000) if _LY[0] < t < _LY[1]]) > 1:
    _LT = [t for t in (1, 10, 100, 1000) if _LY[0] < t < _LY[1]]
# LAT_YTICKS=2,5,10,20 in the environment: exactly those latency ticks, nothing inferred.
# The 1-2-5 ladder puts five on a narrow range such as 1.2-60, which is one more than a
# panel this size reads comfortably (AqRaft 2026-11-21).
_lyt = os.environ.get("LAT_YTICKS", "")
if _lyt:
    _LT = [float(v) for v in _lyt.split(",")]
lax0 = pairs[0][1]
lax0.set_yscale("log"); lax0.set_ylim(*_LY); lax0.set_yticks(_LT)
lax0.yaxis.set_major_formatter(matplotlib.ticker.FormatStrFormatter("%g"))
for _, a in pairs: a.minorticks_off()
pairs[0][0].set_ylim(0, ymax * 1.08); pairs[0][0].yaxis.set_major_locator(matplotlib.ticker.MaxNLocator(3))
# YTICKS=100,200 in the environment: those throughput ticks (plus 0), the axis reaching the last one.
# Default for the 3 -> 4 figure, whose data tops out near 115 kops/s (it showed 0 / 50 / 100).
_yt = os.environ.get("YTICKS", "100,200" if os.environ.get("SETUP") == "3to4" else "")
if _yt:
    _yt = [float(v) for v in _yt.split(",")]
    pairs[0][0].set_ylim(0, max(ymax * 1.08, _yt[-1] * 1.08))
    pairs[0][0].set_yticks([0] + _yt)
# XTICK is the spacing of the time axis, 20 s by default: at this panel size two or three
# numbers are enough to read the axis, and more of them crowd it (AqRaft 2026-11-20)
# set it on BOTH axes of the pair: when one of the two series is drawn on the throwaway
# figure, the shown axis is the other one and sharex does not cross figures
for _a in (pairs[0][0], pairs[0][1]):
    _a.set_xlim(*XLIM)
    _a.xaxis.set_major_locator(
        matplotlib.ticker.MultipleLocator(float(os.environ.get("XTICK", 20))))
for p in pairs[len(PANELS):]:
    for a in p: a.set_axis_off()
# The bridge over a second with no completed operation is NOT named in the legend: it is
# explained in the caption instead, which keeps the legend to the series themselves.
# GAP_LEGEND=1 puts the entry back, and then only when a bridge was actually drawn.
_GAPH = ([Line2D([], [], color=GAPC, lw=LW_GAP, ls=(0, (2.2, 1.6)), label="No ops completed")]
         if (DREW_GAP and os.environ.get("GAP_LEGEND") in ("1", "yes")) else [])
# With the p99 gone the mean is the only latency series, so it is named "Read"/"Write"
# rather than "Avg read"/"Avg write": there is nothing left to average against.
_MLAB = ("Avg read", "Avg write") if SHOW_P99 else ("Read", "Write")
_AVGH = ([Line2D([], [], color=READ, lw=LW_DATA, ls=READ_LS, label=_MLAB[0]),
          Line2D([], [], color=WRITE, lw=LW_DATA, label=_MLAB[1])] if SHOW_MEAN else [])
_P99H = ([Line2D([], [], color=READ, lw=LW_P99, ls=P99_LS, label="p99 read"),
          Line2D([], [], color=WRITE, lw=LW_P99, ls=P99_LS, label="p99 write")] if SHOW_P99 else [])
handles = [] if not SHOW_LAT else [*_AVGH, *_P99H,
           *_GAPH,
           Patch(facecolor=BAND, edgecolor="none", label="Migration"),
           Line2D([], [], color=CRASH, lw=LW_CRASH, ls=(0, (3, 2)), label="Crash")]
if not SHOW_LAT:
    handles = [Patch(facecolor=BAND, edgecolor="none", label="Migration"),
               Line2D([], [], color=CRASH, lw=LW_CRASH, ls=(0, (3, 2)), label="Crash")]
kw = dict(frameon=False, fontsize=FS_LABEL, handlelength=2.0, borderaxespad=0)
fig.supxlabel("Time (s)", fontsize=FS_LABEL, color=INK)
# AqRaft 2026-11-20 COMPAT: Figure.get_layout_engine() is matplotlib >= 3.6; this host has
# 3.5.1, where the constrained-layout pads are set through set_constrained_layout_pads()
# (w_pad/h_pad in inches there, and wspace/hspace as fractions). Without this the script
# dies at the first call and writes nothing.
def _layout_set(fig, **kw):
    getter = getattr(fig, "get_layout_engine", None)
    if getter is not None:
        eng = getter()
        if eng is not None:
            eng.set(**kw)
            return
    setter = getattr(fig, "set_constrained_layout_pads", None)
    if setter is not None:
        try:
            setter(**kw)
        except Exception:
            pass

_layout_set(fig, w_pad=0.03, h_pad=0.03, wspace=0.03, hspace=0.02)
if COMPACT:
    # No room for a legend row: small keys inside the first and last panels, in the area that is
    # empty after the migration (a long migration window in those two would collide with them).
    _layout_set(fig, w_pad=0.015, h_pad=0.015, wspace=0.02, hspace=0.03)
    GREY = "#444444"
    ikw = dict(frameon=False, fontsize=FS_TICK, handlelength=1.5, handletextpad=0.4, labelspacing=0.2, borderaxespad=0.2, borderpad=0)
    last = len(PANELS) - 1
    # A run with no fault has no crash line, so naming one in the legend points at
    # something that is not in the figure (AqRaft 2026-11-20).
    _any_crash = bool(DREW_CRASH)
    keys = [(0, 0, "lower right", [Patch(facecolor=BAND, edgecolor=MUTED, lw=0.4, label="Migration")])]   # edged: it can sit on the band
    if _any_crash:
        keys.append((last, 0, "lower right",
                     [Line2D([], [], color=CRASH, lw=LW_CRASH, ls=(0, (3, 2)), label="Crash")]))
    # With the mean gone the only latency series is the p99, so the read/write key is drawn in
    # the p99's own style and the Mean-vs-p99 key has nothing left to distinguish (AqRaft 2026-11-21).
    _klw, _kls = (LW_DATA, "-") if SHOW_MEAN else (LW_P99, P99_LS)
    keys += [(0, 1, "upper right", [Line2D([], [], color=READ, lw=_klw, ls=(READ_LS if SHOW_MEAN else _kls), label="Read"), Line2D([], [], color=WRITE, lw=_klw, ls=_kls, label="Write")])]
    # The Mean-vs-p99 key is drawn only when both series are in the figure. With one of them
    # off it names a style the reader will never meet (AqRaft 2026-11-22).
    if SHOW_MEAN and SHOW_P99:
        keys += [(last, 1, "upper right", [Line2D([], [], color=GREY, lw=LW_DATA, label="Mean"), Line2D([], [], color=GREY, lw=LW_P99, ls=P99_LS, label="p99")])]
    # one panel: first and last are the same, and a second legend() would replace the first
    merged = {}
    for i, row, loc, h in keys:
        merged.setdefault((i, row), [loc, []])[1].extend(h)
    for (i, row), (loc, h) in merged.items():
        pairs[i][row].legend(handles=h, loc=loc, ncol=2 if len(h) > 2 else 1, columnspacing=1.0, **ikw)
elif spare:
    # Centre the legend in the empty cells (their position is known only after the layout has run).
    fig.canvas.draw()
    boxes = [a.get_position() for p in pairs[len(PANELS):] for a in p]
    cx = (min(b.x0 for b in boxes) + max(b.x1 for b in boxes)) / 2
    cy = (min(b.y0 for b in boxes) + max(b.y1 for b in boxes)) / 2
    fig.legend(handles=handles, loc="center", bbox_to_anchor=(cx, cy), ncol=1 if spare == 1 else 2,
               columnspacing=1.6, labelspacing=0.7, **kw).set_in_layout(False)
else:
    # AqRaft 2026-11-20 COMPAT: the "outside ..." figure-legend locations are matplotlib >= 3.7;
    # this host has 3.5.1 and raises ValueError, so the grid layout produced no file at all.
    # Fall back to an equivalent placement above the axes.
    try:
        fig.legend(handles=handles, loc="outside upper center", ncol=len(handles),
                   columnspacing=1.2, labelspacing=0.3, **kw)
    except ValueError:
        # Anchor ABOVE the axes, not on them: at (0.5, 1.0) the legend landed on the
        # first row's titles. Nothing is clipped because the save below switches to
        # bbox_inches="tight" whenever this fallback runs.
        fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, 1.005),
                   ncol=len(handles), columnspacing=1.2, labelspacing=0.3, **kw)
        globals()["_LEGEND_OUTSIDE_FALLBACK"] = True
_sv = {"bbox_inches": "tight"} if globals().get("_LEGEND_OUTSIDE_FALLBACK") else {}
fig.savefig(out, dpi=400, **_sv)
if out.endswith(".png"): fig.savefig(out[:-4] + ".pdf", **_sv)
print("wrote", out)
