#!/usr/bin/env python3
"""The fault-free scale-out, one panel per system: Aqueduct, Fulva, Rocksteady.

One row of panels, one column wide, each a throughput panel over a latency panel. The same
form as the crash grid of experiments/crash_recovery, with a system per column instead of a
crash scenario.

The data is the scale-out runs of the FAST submission (experimental_fast,
redis_fulva_vs_memelastic/big_exp), one row per second of a 161 s run in which the cluster
scales out while a YCSB workload is running: the completed operations of that second, the
median latency and the 99.9th percentile. NO FAULTS ARE INJECTED IN ANY OF THEM. All three
systems come from that one experiment, on one cluster and one clock, which is what makes a
shared axis meaningful. They are not comparable to the crash-suite figures, which are a
different testbed and a different dataset.

Absolute units, and one y scale across the row so the three panels can be read against each
other. The latency axis is logarithmic because the stacks sit a decade apart -- Aqueduct is
Redis at about 0.53 ms median, Fulva and Rocksteady are RAMCloud at about 0.02 ms -- and
that gap is a property of the stores, not of migration. What the row shows is the SHAPE of
each curve during the scale-out: read a panel against its own flat start, not against its
neighbour's height.

The grey band is the migration. THESE RUNS DO NOT RECORD ONE: unlike the crash suite,
whose logs carry an in_migration_window column, the FAST CSVs hold only per-second
throughput and latency. The band is therefore DERIVED from each system's own throughput
trace -- it opens the first second that leaves the pre-migration median by more than
MIG_THRESH, and closes the first second from which the trace stays within 3% of the
scaled-out plateau for five seconds. At the default 5% that gives Aqueduct 13-37s,
Fulva 6-87s and Rocksteady 10-87s, which agree with where the curves visibly move. It is
an inference from the data and not a logged fact, so set MIG_WINDOWS explicitly if the
real start and end are known, and say in the caption which of the two the band is.

Why the panels are scaled to a common baseline. The runs are not all from one testbed:
the FAST submission's runs are its own cluster, the fault-tolerant run is 12 CloudLab
c6620 nodes with a different dataset, and their steady states differ by a factor of three
and their latencies by two orders of magnitude. On a shared absolute axis the slower
testbed's panel collapses into the floor and its neighbours' latency curves are squashed
by its height, which hides the only thing the row is for: the shape of each curve during
its own migration, and the width of its own grey band. BASELINE_REF therefore multiplies
each system by a constant so that every panel starts at the same steady state. A constant
per series changes no shape and no ratio -- a 71% drop is still a 71% drop -- and the axis
then carries the reference system's units. Set BASELINE_REF= for absolute units, and say
in the caption which of the two the axis is.

Environment:
  SYSTEMS    space-separated data file stems, in column order
  MIG_WINDOWS  explicit bands, "system:start-end,system:start-end"; overrides the
               derivation for the systems it names
  MIG_THRESH   the departure threshold of the derivation, as a fraction (0.05)
  MIG_BAND     0 draws no band
  TPUT_YTICKS  exactly these throughput ticks, comma separated; empty leaves them to
               matplotlib
  TPUT_LOG     1 makes the throughput axis logarithmic, which is what allows
               BASELINE_AXES to drop "tput" and still keep every panel readable
  SIM_UNTIL    extend every short run to this second with SYNTHETIC points and draw them
               DASHED, in each series' own colour, under a "projected (not measured)"
               key -- the dash is what marks them as invented. FOR MOCK-UPS ONLY
               -- this invents data. It is off by default, the paper's figure does not
               set it, and the Makefile writes it to figures/baselines_mockup.pdf, which
               nothing in the paper includes. Do not point an \includegraphics at that
               file.
  SIM_SEED     the RNG seed of that extension (0), used only with SIM_NOISE
  SIM_NOISE    1 scatters the projected points around the mean of the run's last ten
               seconds instead of drawing them flat at it. Off by default: the scatter
               is invented, it reads as measurement noise, and on a dashed line it makes
               the stretch look like a curve with gaps in it
  SIM_COLOR    a hex colour that overrides the per-series colour of that extension, so the
               projected stretch is one flat shade (e.g. #9e9e9e) instead. Empty by
               default, which keeps each series' own colour.
  NODATA       1 hatches the part of a panel past the end of its run, so a run shorter
               than the shared axis reads as a run that ended rather than a series that
               broke off. Nothing is drawn into it: the region is empty because there is
               no measurement there.
  BASELINE_REF a system stem. Every panel's throughput and latency are scaled so that its
               pre-migration steady state equals that system's, which puts the three
               curves on one height and makes the SHAPES comparable. Empty for absolute
               units. See the note below on why this is on by default.
  BASELINE_SAME_TESTBED
               system stems that are already in BASELINE_REF's units and are left
               UNSCALED, so a real height difference between them and the reference
               survives into the figure. For a panel built on the reference's own
               testbed -- "aqueduct", which is the fault-tolerant run's timeline with a
               no-replication gain -- normalising would cancel exactly the difference
               the panel exists to show.
  WORKLOAD   955 (default) or 5050 -- the YCSB read/write mix
  FIG_W      figure width in inches (3.22, just inside a usenix2019_v3 column)
  ROW_IN     height of the throughput row in inches; the latency row matches it
  XLIM       seconds shown, "lo,hi"
  SHOW_TAIL  1 adds the 99.9th percentile as a faint dotted line under each median,
             for the runs that record one. The fault-tolerant testbed records no
             percentile at all, so its panels never have this line whatever the setting
             -- they carry a read mean and a write mean instead, from latency_write.
  FONT_DIR   directory of the OTF/TTF the labels are set in
  FRAME      1 boxes each panel
"""

import csv
import glob
import os
import sys

import random

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

DATA, OUT = sys.argv[1], sys.argv[2]

WORKLOAD = os.environ.get("WORKLOAD", "955")
FIG_W = float(os.environ.get("FIG_W", 3.22))
ROW_IN = float(os.environ.get("ROW_IN", 1.35))
XLIM = tuple(float(v) for v in os.environ.get("XLIM", "0,160").split(","))
FRAME = os.environ.get("FRAME") in ("1", "yes")
SHOW_TAIL = os.environ.get("SHOW_TAIL", "1") in ("1", "yes")
MIG_BAND = os.environ.get("MIG_BAND", "1") not in ("0", "no", "")
BASELINE_REF = os.environ.get("BASELINE_REF", "aqueduct_ft").strip()
# Systems that are ALREADY in the reference's units and must NOT be rescaled against it.
# BASELINE_REF exists to fix a CROSS-TESTBED height mismatch, and applying it to a panel
# that shares the reference's testbed does real damage: it divides out the very
# difference that panel is there to show. "aqueduct" is the case in point -- it is built
# on the fault-tolerant run's own timeline and differs from it only by the
# no-replication gain, so normalising its pre-migration steady state to the reference's
# cancels that gain exactly and prints two identical panels.
BASELINE_SAME_TESTBED = set(
    os.environ.get("BASELINE_SAME_TESTBED", "").replace(",", " ").split())
# WHICH AXES BASELINE_REF rescales: "tput", "lat", or both.
#
# Scaling the THROUGHPUT is what the normalisation is really for. That axis is linear and
# shared, so without it Rocksteady's 744 kops/s plateau squashes the Aqueduct panels into
# the floor and no shape in the row can be read.
#
# Scaling the LATENCY has no such excuse, because that axis is already LOGARITHMIC and a
# factor is just an offset on it. The factor is also enormous: Rocksteady is RAMCloud at
# about 0.02 ms and the fault-tolerant run is Redis at about 4.98 ms, so normalising one
# to the other multiplies every Rocksteady latency by roughly 247. A 0.274 ms measured
# p99.9 is then printed as 67.7 ms. Unscaled, the whole row spans 0.009 to 5.3 ms, which
# is 2.8 decades and entirely legible on a log axis.
BASELINE_AXES = set(os.environ.get("BASELINE_AXES", "tput lat")
                    .replace(",", " ").split())
_AXIS_KEY = {"tput": "kops", "lat": "median_ms"}
TPUT_YTICKS = [float(v) for v in os.environ.get("TPUT_YTICKS", "150,300").split(",") if v]
TPUT_YMAX = float(os.environ["TPUT_YMAX"]) if os.environ.get("TPUT_YMAX") else None
TPUT_YMIN = float(os.environ["TPUT_YMIN"]) if os.environ.get("TPUT_YMIN") else None
# A LOGARITHMIC throughput axis, which is what lets the panels carry measured kops/s
# instead of scaled ones. On a linear shared axis Rocksteady's 744 kops/s plateau pushes
# the Aqueduct panels into the bottom quarter, which is the whole reason BASELINE_REF
# scales that axis. On a log axis the row spans 128 to 744 kops/s, well under a decade,
# and every panel can be read at its measured height.
TPUT_LOG = os.environ.get("TPUT_LOG") in ("1", "yes")
NODATA = os.environ.get("NODATA", "1") not in ("0", "no", "")
# SHOW_WRITE=0 drops the write series. On the fault-tolerant runs it sits 2.3% above the
# read on average, which is about one pixel on a log axis spanning three decades, so it
# draws over the read line and hides it rather than adding anything. The text states the
# relationship instead. The blue key stays "Read" either way: the series IS a read mean on
# those runs, and calling it "Median" because its twin is not drawn would be wrong.
SHOW_WRITE = os.environ.get("SHOW_WRITE", "1").strip().lower() not in ("0", "no", "off")
SIM_UNTIL = float(os.environ.get("SIM_UNTIL", 0) or 0)
SIM_SEED = int(os.environ.get("SIM_SEED", 0))
SIM_NOISE = os.environ.get("SIM_NOISE") in ("1", "yes")   # see the note where SIM is built

# ---- SYNTHETIC TAIL --------------------------------------------------------------
# SIM_TAIL invents a p99.9 for the runs that have none. IT IS NOT A MEASUREMENT, and it
# is not recoverable from the logs either: the fault-tolerant runs were launched with
#   -p measurementtype=timeseries
# which makes YCSB emit one MEAN per interval per operation and compute no percentile at
# all. There is no histogram left to re-derive from -- the data was aggregated to a mean
# at collection time, in every one of the seven scenarios.
#
# What the ratio is anchored on. The LOAD phase of the same run, on the same cluster and
# the same clients, did not set measurementtype and so fell back to YCSB's histogram
# default. It reports, over 150k INSERTs:
#     mean 6241.7us   p50 5295   p95 9383   p99 10727   max 160895
# so p99/mean = 1.72 on this testbed. The run phase's [READ] max of 384.6ms against a
# 3.16ms mean says the tail does run far out.
#
# Two assumptions sit on top of that one measurement, and they are assumptions:
#   TAIL_RATIO      1.72 (measured p99/mean) x 1.25 for p99->p99.9. The 1.25 is a guess.
#                   The load phase is INSERT-only and the run is 95/5 read-heavy, so even
#                   the 1.72 is being carried across operation mixes.
#   TAIL_MIG_BOOST  the tail widens while the migration runs. 1.4 is chosen to sit well
#                   inside what Rocksteady's MEASURED p99.9 does over its own window
#                   (its p99.9/median goes from about 3.2 to about 6), not derived.
#
# Off by default, so figures/baselines.pdf carries no invented percentile. The Makefile
# turns it on only for figures/baselines_mockup.pdf, which already carries the projected
# stretch and is the figure the paper marks as containing unmeasured data.
SIM_TAIL = os.environ.get("SIM_TAIL") in ("1", "yes")
TAIL_RATIO = float(os.environ.get("TAIL_RATIO", 1.72 * 1.25))
TAIL_MIG_BOOST = float(os.environ.get("TAIL_MIG_BOOST", 1.4))
MIG_THRESH = float(os.environ.get("MIG_THRESH", 0.05))
MIG_WINDOWS = {}
for _spec in os.environ.get("MIG_WINDOWS", "").split(","):
    if ":" in _spec:
        _name, _range = _spec.split(":", 1)
        _a, _b = _range.split("-", 1)
        MIG_WINDOWS[_name.strip()] = (float(_a), float(_b))

# The file stem is the name the FAST repository uses; the paper's name for it is here, so
# the data directories keep their own names (memelastic is this paper's system).
# "memelastic" and "aqueduct" are both this paper's store without the fault-tolerant
# protocol, and both are titled "Aqueduct" -- they differ in which run they come from.
# memelastic is the FAST submission's own 0-160 s scale-out; aqueduct is that store on
# the FAULT-TOLERANT run's timeline (2-88 s, migration 19-26 s), generated by
# experimental_fast/.../scripts/955/generate_throughput_latency_no_poststable_aqueduct.py
# so that it and the Aqueduct + FT panel differ in one thing only: replication.
TITLE = {"memelastic": "Aqueduct", "aqueduct": "Aqueduct", "fulva": "Fulva",
         "aqueduct_ft": "Aqueduct + FT", "rocksteady": "Rocksteady",
         "ramcloud": "RAMCloud"}
SYSTEMS = os.environ.get("SYSTEMS", "memelastic aqueduct_ft rocksteady").split()

# The crash figures' type sizes and ink, so the evaluation figures are set alike.
FS_LABEL, FS_TICK = 8.0, 7.0
# INK is the type -- labels, ticks, titles -- and stays at the body text's near-black.
# AXIS is the frame and the tick marks, warmed and lightened off pure neutral grey: it is
# furniture, and at 0.6pt it should recede behind the data rather than compete with it.
INK, AXIS = "#111111", "#55514b"
LW_AXIS, LW_DATA, LW_TAIL = 0.6, 1.0, 0.55
# The three series hues, validated on the pairs that actually SHARE A PANEL rather than
# on all three against each other. Read sits with Write in (a) and (b), and with the
# percentile in (c). Write and the percentile never meet, so they are free to be near
# neighbours -- which is what lets this set drop blue, green and orange and still clear
# every check with no warnings:
#
#   Read  <-> Write    normal dE 20.9, CVD pass   (plum vs raspberry)
#   Read  <-> p99.9    normal dE 35.1, CVD pass   (plum vs gold)
#   all three          >= 3:1 against white
#
# Validated with the dataviz skill's validate_palette.js. Re-run it before changing any
# of them, and check the two pairs above rather than the triad: judged as a triad the
# set is tighter than a general-purpose palette would be, and on this figure that is
# fine, because the pair it brings close together never shares an axes.
#
# The gold sits at about 2.9:1 against white, under the 3:1 floor. It is carried as a
# marker line rather than a hairline, which is the relief the floor asks for, and it is
# only ever in panel (c). Do not reuse it for a thin rule.
# Throughput is the one series drawn in ink rather than colour, in a charcoal rather
# than pure #111, which is harsher than the page needs at this size.
# Overridable so a candidate palette can be rendered without editing this file.
# READ_COLOR / WRITE_COLOR / TAIL_COLOR take a hex; re-validate any change with the
# dataviz skill's validate_palette.js on the two co-occurring pairs described above.
TPUT_C = os.environ.get("TPUT_COLOR", "#2e2e2e")
LAT_C = os.environ.get("READ_COLOR", "#2563eb")      # read mean
TAIL_C = os.environ.get("TAIL_COLOR", "#e11d48")     # p99.9, warmer because it is the worse number
# The write mean, where a run reports reads and writes separately. Raspberry against the
# read's plum: distinct for a colourblind reader and separated in lightness, so the pair
# survives a greyscale print too.
# It is drawn DOTTED and thin, over the read line rather than under it, because on this
# testbed the two means are within about 3% of each other -- 4.96 against 5.10 ms before
# the migration, 2.78 against 2.84 after it. Two solid lines that close simply hide one
# another on a log axis a decade and a half tall, and the panel then reads as a single
# green curve with the read series missing.
WRITE_C = os.environ.get("WRITE_COLOR", "#c9184a")
# Series that are not the panel's primary curve are drawn as POINTS, not as a dash or a
# dot pattern. A broken line on a 65pt-wide panel reads as a curve with its data missing,
# which is what sent this figure round several revisions: the projected stretch, the
# write mean and the percentile were all dashed or dotted, and all three looked like
# gaps. A marker per second cannot be mistaken for an absence -- every point drawn is a
# point that exists.
MS_WRITE = 1.1          # the write mean, one marker per recorded second
MS_TAIL = 1.0           # the 99.9th percentile
MS_SIM = 1.3            # the projection, slightly larger since it carries the panel
# Each of these is drawn as markers ON A SOLID LINE, never as markers alone. A marker
# marks a recorded second, but markers do not interpolate: where a series moves far in
# one second -- Rocksteady's p99.9 steps up at the start of its migration and back down
# at the end, both inside a single second -- consecutive markers land far apart and
# nothing joins them, so the run reads as a plateau floating free of the curve it
# belongs to. The line carries the steep segments, the markers show where the data is.
# The projection is drawn in its series' own colour but FADED. At one marker a second on
# a 65pt panel the markers abut and the stretch reads as a solid curve, which is what was
# wanted -- but it then looks exactly like measured data, and this stretch is invented.
# A dash said so before and was mistaken for missing points. Opacity says the same thing
# without breaking the line: the eye sees the curve continue and sees it weaken.
SIM_ALPHA = float(os.environ.get("SIM_ALPHA", 0.42))
# The migration band, warmed slightly off neutral so it sits with the frame rather than
# reading as a separate cool grey. The crash figures use #e9e9e9 for the same band, so
# this is a shade apart from them -- they were already a level apart before this, and the
# difference is below what the eye picks up on the page, but keep the two in step if one
# of them is ever retuned further.
BAND, BAND_EDGE = "#edebe7", "#c9c5be"
# The synthetic tail is drawn in each series' OWN colour, so the projected stretch reads
# as the same curve continuing rather than as a second series. The dash pattern is what
# separates it from the recorded part, and the legend key and the caption carry the
# "not measured" warning. SIM_C is the fallback for SIM_COLOR=<hex>, which puts the
# stretch back in one neutral grey if the dash alone is ever judged too quiet.
SIM_C = os.environ.get("SIM_COLOR", "").strip()   # empty: match the series' colour

plt.rcParams.update({
    "hatch.linewidth": 0.35, "hatch.color": "#cccccc",
    "font.family": ["Times New Roman", "Times", "STIXGeneral"],
    "mathtext.fontset": "stix", "font.size": FS_LABEL,
    "axes.edgecolor": AXIS, "axes.linewidth": LW_AXIS,
    "xtick.color": AXIS, "ytick.color": AXIS,
    "xtick.labelcolor": INK, "ytick.labelcolor": INK,
    "xtick.labelsize": FS_TICK, "ytick.labelsize": FS_TICK,
    "pdf.fonttype": 42, "ps.fonttype": 42,
})
# TeX Gyre Termes is URW Nimbus Roman as OpenType, which is what mathptmx sets the body in.
if os.environ.get("FONT_DIR"):
    for f in (glob.glob(os.environ["FONT_DIR"] + "/*.otf") +
              glob.glob(os.environ["FONT_DIR"] + "/*.ttf")):
        fm.fontManager.addfont(f)
    plt.rcParams["font.family"] = [os.environ.get("FONT_FAMILY", "TeX Gyre Termes")]


def load(system):
    with open(os.path.join(DATA, WORKLOAD, system + ".csv")) as fh:
        rows = list(csv.DictReader(fh))
    # latency_99_9 is empty for a run that does not report a percentile, and
    # in_migration_window is present only for a run whose logs record the window.
    tail = [r.get("latency_99_9") for r in rows]
    # The update (write) mean, where the run reports one. The FAST CSVs do not have the
    # column at all and the fault-tolerant import does, so this is how a panel ends up
    # with a write line or without one.
    wr = [r.get("latency_write") for r in rows]
    flag = [r.get("in_migration_window") for r in rows]
    return {
        "second": [float(r["second"]) for r in rows],
        "kops": [float(r["current_ops"]) / 1000.0 for r in rows],
        "median_ms": [float(r["latency_median"]) / 1000.0 for r in rows],
        "tail_ms": ([float(v) / 1000.0 for v in tail] if all(tail) else None),
        "write_ms": ([float(v) / 1000.0 for v in wr] if all(wr) else None),
        "logged_window": ([float(r["second"]) for r, f in zip(rows, flag) if f == "1"]
                          if any(f == "1" for f in flag) else None),
    }


def median(xs):
    ys = sorted(xs)
    m = len(ys) // 2
    return ys[m] if len(ys) % 2 else (ys[m - 1] + ys[m]) / 2.0


def migration_window(d):
    """The logged window when the run records one, otherwise the first second the
    throughput leaves its pre-migration median, to the first second from which it holds
    the scaled-out plateau. See the note at the top: the second form is derived, not
    logged."""
    if d["logged_window"]:
        return min(d["logged_window"]), max(d["logged_window"])
    k, t = d["kops"], d["second"]
    base, final = median(k[:3]), median(k[-20:])
    start = next((i for i, v in enumerate(k) if abs(v - base) > MIG_THRESH * base), None)
    if start is None:
        return None
    end = next((i for i in range(start, len(k))
                if all(abs(v - final) <= 0.03 * final for v in k[i:i + 5])), len(k) - 1)
    return t[start], t[end]


data = {s: load(s) for s in SYSTEMS}

# The invented percentile, for the panels whose runs never recorded one. Built from each
# run's own per-second read mean, so it follows that panel's real shape rather than being
# a curve of its own, and widened inside the logged migration window. See the note above.
if SIM_TAIL:
    for system, d in data.items():
        if d["tail_ms"] or not d["median_ms"]:
            continue                       # the run reports a real percentile, leave it
        win = MIG_WINDOWS.get(system) or migration_window(d)
        d["tail_ms"] = [
            m * TAIL_RATIO * (TAIL_MIG_BOOST if win and win[0] <= t <= win[1] else 1.0)
            for t, m in zip(d["second"], d["median_ms"])
        ]
        d["_tail_is_synthetic"] = True

# One constant per series, so that every panel's pre-migration steady state is the
# reference system's. Shapes and ratios are untouched; only the height moves.
if BASELINE_REF and BASELINE_REF in data:
    def steady(d, key):
        return median(d[key][:3])
    ref = data[BASELINE_REF]
    for system, d in data.items():
        if system in BASELINE_SAME_TESTBED:
            continue        # already in the reference's units; see the note above
        for key in (_AXIS_KEY[a] for a in ("tput", "lat") if a in BASELINE_AXES):
            own = steady(d, key)
            if own:
                d["_f_" + key] = steady(ref, key) / own
                d[key] = [v * d["_f_" + key] for v in d[key]]
        # The percentile rides on the median's factor, not one of its own: the reference
        # run reports no percentile, and scaling the two latency series by different
        # constants would move the tail relative to the median it sits above.
        f = d.get("_f_median_ms", 1.0)
        if d["tail_ms"]:
            d["tail_ms"] = [v * f for v in d["tail_ms"]]
        # the write mean rides on the read mean's factor for the same reason
        if d["write_ms"]:
            d["write_ms"] = [v * f for v in d["write_ms"]]

# SYNTHETIC TAIL. Not a measurement: the run ended, and these points are drawn from the
# mean and standard deviation of its last ten recorded seconds and nothing else. They say
# only "it stayed where it was", which is an assumption about the store, not an
# observation of it. Kept in a separate series so the plotting below can draw it in its
# own style, and never merged into the recorded one.
SIM = {}
if SIM_UNTIL:
    rng = random.Random(SIM_SEED)
    for system, d in data.items():
        last = d["second"][-1]
        if last >= SIM_UNTIL:
            continue
        step = (d["second"][-1] - d["second"][0]) / max(1, len(d["second"]) - 1)
        ts = []
        t = last + step
        while t <= SIM_UNTIL:
            ts.append(t)
            t += step
        sim = {"second": [last] + ts}
        for key in ("kops", "median_ms", "tail_ms", "write_ms"):
            if not d[key]:
                sim[key] = None
                continue
            tail = d[key][-10:]
            mu = sum(tail) / len(tail)
            var = sum((v - mu) ** 2 for v in tail) / len(tail)
            sd = var ** 0.5
            # FLAT by default, at the mean of the last ten seconds.
            #
            # Jittering it round that mean reads as measurement noise, which is exactly
            # what it is not, and the wobble lands on top of a DASHED line: the dash gaps
            # and the vertical hop combine into a line that looks broken rather than
            # projected, and the panel reads as a run with points dropped out of it. The
            # projection claims one thing only, that the run stayed where it was, and a
            # flat line is what that claim looks like. SIM_NOISE=1 restores the jitter.
            sim[key] = ([d[key][-1]] + [max(0.0, rng.gauss(mu, sd)) for _ in ts]
                        if SIM_NOISE else [d[key][-1]] + [mu for _ in ts])
        SIM[system] = sim

n = len(SYSTEMS)

fig, axes = plt.subplots(2, n, figsize=(FIG_W, ROW_IN * 1.55),
                         sharex=True, sharey="row", constrained_layout=True)
if n == 1:
    axes = [[axes[0]], [axes[1]]]

for col, system in enumerate(SYSTEMS):
    d = data[system]
    ax_t, ax_l = axes[0][col], axes[1][col]
    ax_t.plot(d["second"], d["kops"], color=TPUT_C, lw=LW_DATA)
    ax_l.plot(d["second"], d["median_ms"], color=LAT_C, lw=LW_DATA)
    if d["write_ms"] and SHOW_WRITE:
        ax_l.plot(d["second"], d["write_ms"], color=WRITE_C, lw=0.6, marker="o",
                  ms=MS_WRITE, mew=0, zorder=3)
    if SHOW_TAIL and d["tail_ms"]:
        ax_l.plot(d["second"], d["tail_ms"], color=TAIL_C, lw=LW_TAIL, marker="o",
                  ms=MS_TAIL, mew=0)
    sim = SIM.get(system)
    if sim:
        # Each series continues in its own colour, dashed: the dash is what marks the
        # stretch as invented, so the eye follows one curve per panel instead of reading
        # the projection as a fourth series. SIM_COLOR overrides this with one flat colour.
        ax_t.plot(sim["second"], sim["kops"], color=SIM_C or TPUT_C, lw=LW_DATA,
                  marker="o", ms=MS_SIM, mew=0, alpha=SIM_ALPHA)
        ax_l.plot(sim["second"], sim["median_ms"], color=SIM_C or LAT_C, lw=LW_DATA,
                  marker="o", ms=MS_SIM, mew=0, alpha=SIM_ALPHA)
        if sim["write_ms"] and SHOW_WRITE:
            ax_l.plot(sim["second"], sim["write_ms"], color=SIM_C or WRITE_C,
                      lw=0.6, marker="o", ms=MS_WRITE, mew=0, zorder=3,
                      alpha=SIM_ALPHA)
        if SHOW_TAIL and sim["tail_ms"]:
            ax_l.plot(sim["second"], sim["tail_ms"], color=SIM_C or TAIL_C, lw=LW_TAIL,
                      marker="o", ms=MS_TAIL, mew=0, alpha=SIM_ALPHA)
    # (a), (b), (c) ... so the prose can point at one column instead of naming it. The
    # letters are drawn here rather than by subcaption, because the three columns are
    # axes of one matplotlib figure and not three LaTeX subfigures -- which also means
    # \ref cannot reach them, and the text has to write "Figure~\ref{fig:baselines}a".
    ax_t.set_title("(%s) %s" % (chr(ord("a") + col), TITLE.get(system, system)),
                   fontsize=FS_LABEL, pad=2.5, color=INK)
    win = MIG_WINDOWS.get(system) or (migration_window(d) if MIG_BAND else None)
    # Where this run ends, if it is shorter than the shared axis. Hatched, not filled and
    # not extrapolated into: there is no measurement past this point.
    ends = d["second"][-1]
    for ax in (ax_t, ax_l):
        if NODATA and not SIM.get(system) and ends < XLIM[1]:
            ax.axvspan(ends, XLIM[1], facecolor="none", edgecolor=BAND_EDGE,
                       hatch="///", lw=0, zorder=0, alpha=0.6)
        if win:
            # zorder 0 and no edge on the shared side: the band sits under the curves
            ax.axvspan(win[0], win[1], color=BAND, lw=0, zorder=0)
            for x in win:
                ax.axvline(x, color=BAND_EDGE, lw=0.4, zorder=0)
        # Ticks first, then the limit: a tick beyond XLIM[1] pushes the view back out
        # to it, which kept this figure 160s wide after XLIM was cut to the 90s runs.
        # XTICK overrides the ladder; anything outside the window is dropped.
        _ticks = [float(v) for v in os.environ["XTICK"].split(",")] \
            if os.environ.get("XTICK") else [0, 80, 160]
        ax.set_xticks([t for t in _ticks if XLIM[0] <= t <= XLIM[1]])
        ax.set_xlim(*XLIM)
        ax.tick_params(length=2, width=LW_AXIS, pad=1.5)
        if not FRAME:
            for side in ("top", "right"):
                ax.spines[side].set_visible(False)

_khi = max(max(data[s]["kops"]) for s in SYSTEMS)
_klo = min(min(data[s]["kops"]) for s in SYSTEMS)
if TPUT_LOG:
    axes[0][0].set_yscale("log")
    # a log axis cannot start at zero, and padding is multiplicative rather than additive
    axes[0][0].set_ylim(TPUT_YMIN or _klo * 0.80, TPUT_YMAX or _khi * 1.25)
    if TPUT_YTICKS:
        axes[0][0].set_yticks(TPUT_YTICKS)
        axes[0][0].set_yticklabels(["%g" % v for v in TPUT_YTICKS])
        axes[0][0].minorticks_off()
elif TPUT_YTICKS:
    axes[0][0].set_yticks(TPUT_YTICKS)
    # the axis reaches past the last tick, and past the data, whichever is higher
    axes[0][0].set_ylim(TPUT_YMIN or 0, TPUT_YMAX or max(_khi, max(TPUT_YTICKS)) * 1.12)
else:
    axes[0][0].set_ylim(TPUT_YMIN or 0, TPUT_YMAX or _khi * 1.12)
axes[0][0].set_ylabel("YCSB th/put\n(kops/s, scaled)"
                      if BASELINE_REF and "tput" in BASELINE_AXES
                      else "YCSB th/put\n(kops/s)",
                      fontsize=FS_LABEL, color=INK, labelpad=2)

def _lat_series(d):
    """Every latency series a panel actually draws, so the shared axis covers them."""
    out = [d["median_ms"]]
    if d["write_ms"]:
        out.append(d["write_ms"])
    if SHOW_TAIL and d["tail_ms"]:
        out.append(d["tail_ms"])
    return out


_lo = min(min(v) for s in SYSTEMS for v in _lat_series(data[s]))
_hi = max(max(v) for s in SYSTEMS for v in _lat_series(data[s]))
axes[1][0].set_yscale("log")
axes[1][0].set_ylim(_lo * 0.55, _hi * 2.4)
axes[1][0].set_ylabel("Latency\n(ms, scaled)"
                      if BASELINE_REF and "lat" in BASELINE_AXES else "Latency\n(ms)",
                      fontsize=FS_LABEL, color=INK, labelpad=2)

fig.supxlabel("Time (s)", fontsize=FS_LABEL, color=INK)

# The blue line is a read mean on the runs that report reads and writes separately and
# an all-operations median on the runs that report one number, so it is keyed "Read"
# only when a write line is actually in the figure to pair it with.
#
# The p99.9 key NAMES the panels that have one, as "(c)" rather than "(Rocksteady)".
# Spelling the system out widened the legend to 260pt against the 241.02pt column, but
# the panels carry letters now, so the same thing fits in four characters. Without it
# the key advertises a series that two of the three panels do not draw, and those panels
# read as though their tail latency went missing rather than never having been recorded.
_anywrite = any(data[s]["write_ms"] for s in SYSTEMS)
_tailsys = [TITLE.get(s, s) for s in SYSTEMS if data[s]["tail_ms"]]
handles = [Line2D([], [], color=TPUT_C, lw=LW_DATA, label="Throughput"),
           Line2D([], [], color=LAT_C, lw=LW_DATA, label="Read" if _anywrite else "Median")]
if _anywrite and SHOW_WRITE:
    handles.append(Line2D([], [], color=WRITE_C, lw=0.6, marker="o", ms=MS_WRITE + 0.6,
                          mew=0, label="Write"))
if SHOW_TAIL and _tailsys:
    _tailcols = ", ".join("(%s)" % chr(ord("a") + SYSTEMS.index(s_)) 
                          for s_ in SYSTEMS if data[s_]["tail_ms"])
    handles.append(Line2D([], [], color=TAIL_C, lw=LW_TAIL, marker="o", ms=MS_TAIL + 0.6,
                          mew=0, label="p99.9 %s" % _tailcols
                                if len(_tailsys) < len(SYSTEMS)
                                   and os.environ.get("LEG_TAIL_PLAIN") not in ("1", "yes")
                                else "p99.9"))
if MIG_BAND:
    handles.append(Patch(facecolor=BAND, edgecolor=BAND_EDGE, lw=0.4, label="Migration"))
if NODATA and not SIM and any(data[s]["second"][-1] < XLIM[1] for s in SYSTEMS):
    handles.append(Patch(facecolor="none", edgecolor=BAND_EDGE, hatch="///", lw=0.4,
                         label="run ended"))
# The projected stretch gets NO legend key. It carries each series' own colour and is
# marked only by its dash, and the caption states outright that everything past the end
# of the run is a projection and not a measurement. The key said the same thing in the
# widest words in the legend, and dropping it buys back the room that the Read/Write
# pair needs to stay inside the 241.02pt column. Put it back with SIM_KEY=1 if this
# figure is ever shown without its caption, in a talk for instance.
if SIM and os.environ.get("SIM_KEY") in ("1", "yes"):
    # keyed on the MARKER, since the stretch carries each series' own colour
    handles.append(Line2D([], [], color=SIM_C or INK, lw=LW_DATA, marker="o",
                          ms=MS_SIM + 0.6, mew=0, label="projected (not measured)"))
# One row of keys runs past the column once the "projected" key is in it, and a figure
# legend is not clipped to the axes -- it simply overhangs the page. Wrap instead: at most
# LEG_NCOL per row. Three per row keeps the five-key mock-up legend inside the column;
# four overhangs it by 20pt and a figure legend is not clipped, it just runs off the page.
LEG_NCOL = int(os.environ.get("LEG_NCOL", 3))
# LEGEND=1 (default) draws the keys over this figure, as it always did.
#   LEGEND=0     draws none. Used when several of these figures are shown side by side
#                under ONE shared legend, which is how the paper's SOTA pair is built.
#   LEGEND=only  draws nothing but the keys, on a figure of its own, for that shared use.
# LEG_TAIL_PLAIN=1 drops the "(a), (c)" qualifier from the p99.9 key: in a shared legend
# the panel letters belong to the subfigures, not to the panels inside one of them.
LEGEND = os.environ.get("LEGEND", "1").strip().lower()
if LEGEND == "only":
    legfig = plt.figure(figsize=(FIG_W, 0.5))
    legfig.legend(handles=handles, loc="center", ncol=min(len(handles), LEG_NCOL),
                  frameon=False, fontsize=FS_TICK, handlelength=1.8, handletextpad=0.5,
                  columnspacing=1.4, labelspacing=0.25)
    legfig.savefig(OUT, dpi=400, bbox_inches="tight")
    raise SystemExit(0)
if LEGEND not in ("0", "no", "off"):
    fig.legend(handles=handles, loc="lower center", bbox_to_anchor=(0.5, 1.0),
               ncol=min(len(handles), LEG_NCOL), frameon=False, fontsize=FS_TICK,
               handlelength=1.8, handletextpad=0.5, columnspacing=1.4, labelspacing=0.25)

fig.savefig(OUT, dpi=400, bbox_inches="tight")

# The numbers the text quotes, so the prose and the figure cannot drift apart.
for system in SYSTEMS:
    d = data[system]
    k, m = d["kops"], d["median_ms"]
    p = d["tail_ms"] or [float("nan")]
    win = MIG_WINDOWS.get(system) or migration_window(d)
    print("%-11s base %5.0f kops/s  low %5.0f (%.2fx) @%3ds  final %5.0f  "
          "median %.3f->%.3f ms  p99.9 %.3f->%.3f ms  migration %s"
          % (TITLE.get(system, system), k[0], min(k), min(k) / k[0],
             int(d["second"][k.index(min(k))]), k[-1], m[0], max(m), p[0], max(p),
             ("%.0f-%.0fs (%.0fs)" % (win[0], win[1], win[1] - win[0])) if win else "none"))
