#!/usr/bin/env python3
"""Paper figure of one crash run of the 3 -> 6 scale-out: recovery timeline over one pair's
migration, with YCSB throughput below on the same time axis.

usage: paper_recovery.py <Sx_recovery.json> <out.pdf|out.png> [width_in] [pair]
  <Sx_recovery.json>  written by recovery_breakdown.py next to its figure
  width_in            3.33 (default) = one column of a two-column paper; >= 4 = full text width
  pair                A|B|C: the pair whose rounds are drawn (default: the pair with a lost or
                      re-shipped round, else the pair of the first crashed group, else A)

Rows are built from what the run contains, so every scenario works:
  one row per group that lost its leader (no leader; for a recipient, the index update of the
  durable data, after which it serves), a Recovery row with the recovery steps that happened
  (plan = probe peers + re-home / resume plan; chain rebuild; a stalled forward to a dead
  follower and its re-forward), then the pair's rounds: copy, replication to F1, index update.
Drawn at print size: the text sizes below are the sizes on paper. Grayscale; red marks the fault."""
import sys, json, re, math
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

src, out = sys.argv[1], sys.argv[2]
WIDTH = float(sys.argv[3]) if len(sys.argv) > 3 else 3.33
d = json.load(open(src))
rows, sc = d["rows"], d.get("scenario", "")
FIRST_KIND = (d.get("faults") or [{"kind": "kill"}])[0]["kind"]   # kill, or partition / freeze
GROUP_PAIR = {"sg1": "A", "sg4": "A", "sg2": "B", "sg5": "B", "sg3": "C", "sg6": "C"}
CRASH_LABEL = {"S1": "recipient leader crash", "S2": "donor leader crash", "S3": "donor follower crash",
               "S4": "recipient follower crash", "S5": "donor + recipient leader crash",
               "S6": "recipient host crash", "S7": "donor host crash",
               "S8": "donor leader crash (after registration)",
               "S9": "donor A + recipient B leader crash",
               "S10": "recipient leader crash (no majority)", "S11": "recipient leader crash (majority)",
               "S12": "recipient leader crash (data on F1)"}
CRASH_SHORT = {"S5": "two leader crashes", "S9": "two leader crashes", "S6": "host crash", "S7": "host crash",
               "S8": "donor leader crash", "S10": "no majority", "S11": "majority", "S12": "data on F1"}


def find(pat):
    """[(name, a, b)] of the phase rows matching pat, with both ends known."""
    return [(n, a, b) for n, a, b in rows if re.search(pat, n) and a is not None and b is not None]


# ---- what happened -------------------------------------------------------------------------------
kills = [t for h, t in d.get("kills", [])] or [0.0]
# A no-fault baseline (HEALTHY): the JSON carries no kills, t=0 is the migration start. Keep the
# 0.0 above as the time origin, but draw none of the crash furniture -- no red crash line, no
# outage arrow -- or the figure invents a fault that never happened.
NO_FAULT = not d.get("kills")
dead = []                                   # groups that lost their leader: (sg, no-leader start, leader at)
for n, a, b in find(r"failure detection"):
    g = n.split(":")[0]
    el = find(r"^%s: election \(" % g)
    dead.append((g, a, el[0][2] if el else b))
idx_dur = {n.split(" ")[0]: (a, b) for n, a, b in find(r"INDEX UPDATE of durable data")}
rec = []                                    # recovery steps: (start, end, long label, short label, fill)
plan = find(r"probe peers") + find(r"donor decides")
if plan:
    a, b = min(p[1] for p in plan), max(p[2] for p in plan)
    if b - a >= 0.03:                       # a donor's own resume plan takes ~1 ms: nothing to draw
        rec.append((a, b, "refetch group",
                    "refetch group", "ctrl"))
for n, a, b in find(r"rebuild replication chain"):
    if b - a >= 0.03:
        rec.append((a, b, "chain reconstruction", "chain reconstruction", "chain"))
for n, a, b in find(r"forward to the dead F1"):
    rec.append((a, b, "forward to dead follower (stalls)", "stalled forward", "chain"))
for n, a, b in find(r"re-forward the round"):
    rec.append((a, b, "re-forward to the other follower", "re-forward", "ctrl"))
served_rows = find(r"served again \(median key\)|first key served again")
served = max(b for n, a, b in served_rows) if served_rows else None   # every affected key class back

allr = d.get("rounds") or []
PAIR = sys.argv[4] if len(sys.argv) > 4 else (
    next((r["pair"] for r in allr if r["reship"] or not r["ok"]), None)
    or (GROUP_PAIR.get(dead[0][0]) if dead else None) or "A")
# PAIR=ALL draws all three donor--recipient pairs on one axis. They run back to back, so
# the figure then spans the whole migration rather than its first third, and a bar is named
# by its pair and its group ("B3") instead of by its group alone (AqRaft 2026-11-22).
ALL_PAIRS = str(PAIR).upper() == "ALL"
rounds = sorted(allr, key=lambda r: r["copy"][0]) if ALL_PAIRS else [r for r in allr if r["pair"] == PAIR]
# Round numbers. AqRaft 2026-11-20: number each bar by the SLOT RANGE it moves, so a round and
# its re-ship share a number because they move the same slots -- not because of where they fall in
# arrival order.
#
# The previous rule walked the rounds in order and had every re-ship reuse a single `lost_k`. Two
# ways that went wrong, both visible in the 2026-11-20 suite:
#   - `lost_k` is one scalar, so when a scenario re-ships twice BOTH re-ships took the first lost
#     round's number. S10 (rounds 1,2, re-ship of 1, round 3, round 4) came out as 1,2,1,1,3.
#   - "reship" only means the id is in the 8e17+ space, which the donor also uses for a round the
#     orchestrator's re-drive dispatched fresh. Such a round never was lost, so giving it a lost
#     round's number is wrong twice over: S12's round 3 was drawn as "1" and its round 4 as "3".
# S11 happened to come out right under the old rule, which is why this went unnoticed.
#
# `lo` is the round's first slot, written by recovery_breakdown.py. Rank the distinct values: the
# migration walks the pair's range in ascending chunks, so rank+1 IS the round number. Fall back to
# the old counter for a JSON written before `lo` existed.
_los = sorted({r["lo"] for r in rounds if r.get("lo") is not None})
if _los and all(r.get("lo") is not None for r in rounds):
    if ALL_PAIRS:   # rank inside the pair: each pair's own slot range walks 1..4
        _bypair = {}
        for _r in rounds:
            _bypair.setdefault(_r["pair"], set()).add(_r["lo"])
        _bypair = {k: sorted(v) for k, v in _bypair.items()}
        num = [_bypair[r["pair"]].index(r["lo"]) + 1 for r in rounds]
    else:
        num = [_los.index(r["lo"]) + 1 for r in rounds]
else:
    num, k, lost_k = [], 0, None
    for r in rounds:
        if r["reship"] and r["ok"]:
            if lost_k is None:   # the lost round never started copying (donor died before)
                k += 1; lost_k = k
            num.append(lost_k)
        else:
            k += 1; num.append(k)
            if not r["ok"]:
                lost_k = k
# what the refetch found: where the round the crash interrupted was afterwards (a note on the
# Recipient recovery row, so the reader sees whether the round came from a replica or the donor)
RF = (d.get("refetch") or {}).get(PAIR)
RF_NOTE = None
if RF:
    k0_ = kills[0]
    # AqRaft 2026-11-20: name the round the recovery actually re-shipped, not merely the
    # first one that failed to commit. A kill under deep leaves SEVERAL rounds uncommitted
    # -- in S1 both round 1 and round 2 -- and taking the first made the note read "no live
    # replica has round 1 -> donor resends" while the bar beneath it, the one actually
    # resent, was round 2. The re-ship entry carries the right number by construction.
    # AqRaft 2026-11-22: the re-ship rule above is right only for the kinds whose note is about
    # a group the DONOR sends again. For self/peer/durable the note is about the group the new
    # leader ALREADY HAS, and that is the group in flight at the kill, not the next one the
    # pipeline happens to ship under the recovery path. In S12 the held group is G1 (slots
    # 0-681, MGN_RECP_DURABLE deferred by the hook, TXN_DONE at +2.38s) while the first
    # re-shipped round is G3, so the note read "new leader has G3" for a group it never held.
    _held = next((n for r, n in zip(rounds, num)
                  if not r["reship"] and r["copy"][0] is not None and r["copy"][0] < k0_
                  and (r.get("done") is None or r["done"] > k0_)), None)
    rn = (_held if RF["kind"] in ("self", "peer", "durable") and _held else None) or next(
        (n for r, n in zip(rounds, num) if r["reship"] and r["ok"]), None) or next(
        (n for r, n in zip(rounds, num) if not r["ok"]), None) or next(
        (n for r, n in zip(rounds, num) if r["copy"][0] < k0_ and (r.get("done") or 1e9) > k0_), None) or 1
    ARW = r"$\rightarrow$"
    kind = RF["kind"]
    if kind == "none":
        RF_NOTE = ("no live replica has G%d %s donor resends" % (rn, ARW)) if RF.get("leader") else \
                  ("recipient lacks G%d %s donor resends" % (rn, ARW))
    elif kind == "self":
        RF_NOTE = "new leader (was F1) has G%d %s no resend" % (rn, ARW)
    elif kind == "peer":
        RF_NOTE = "a follower has G%d %s fetched from it, no resend" % (rn, ARW)
    elif kind == "durable":
        RF_NOTE = "G%d already committed %s no resend" % (rn, ARW)
    elif kind == "partial":
        RF_NOTE = "recipient has %d/%d slots of G%d %s donor resends the rest" % (
            RF.get("durable", 0), RF.get("durable", 0) + RF.get("missing", 0), rn, ARW)
RF_SHORT = None
if RF_NOTE:
    # The panels put the consequence in parentheses rather than behind an arrow: the arrow was
    # the only one in the figure and read as a transition between two states, which is not what
    # the second line is (AqRaft 2026-11-22).
    RF_SHORT = {"none": ("no replica has G%d" if RF.get("leader") else "recipient lacks G%d") % rn
                        + "\n(donor resends)",
                "self": "new leader has G%d\n(no resend)" % rn,
                "peer": "a follower has G%d\n(fetched from it)" % rn,
                "durable": "G%d committed\n(no resend)" % rn,
                "partial": "recipient has part of G%d\n(donor resends the rest)" % rn}.get(RF["kind"])
yc = d.get("ycsb_kops") or []
# The async relay of the last group ends after its DONE commits, so the window has to cover
# it or the final bar is clipped by the frame (AqRaft 2026-11-22).
_aends = [r["async"][1] for r in rounds if r.get("async") and r["async"][1] is not None]
pair_end = max([r["done"] for r in rounds if r.get("done") is not None] + _aends + [kills[-1] + 1.0])
pair_start = min([r["copy"][0] for r in rounds] + [kills[0]])

# ---- style ---------------------------------------------------------------------------------------
INK, MUTED, AXIS = "#111111", "#555555", "#8a8a8a"
RED = "#c0392b"    # the fault: the crash, the time without a leader, the lost round (the only color)
G = {"ctrl": "#d4d4d4", "chain": "#f2f2f2", "copy": "#3d3d3d", "repl": "#7f7f7f", "idx": "#bdbdbd",
     "fill": "#e2e2e2", "band": "#f7f7f5", "vgrid": "#e6e6e6"}
# Round shades (grayscale; red stays reserved for the fault): (fill, text color) for rounds
# 1, 2, 3, 4 -- dark to light, the same shade for a round's copy, replication and index update.
ROUND_COL = [("#2e2e2e", "white"), ("#646464", "white"), ("#a3a3a3", INK), ("#d6d6d6", INK)]
COMPACT = WIDTH < 4.0
# WRAP=1 keeps the narrow figure's two-line lane names, its 1.02 in gutter and its tight
# right margin on a figure that is no longer narrow. Widening a figure to fit more in the
# bars otherwise backfires: past 4 in the names unwrap and take the width the bars needed
# (AqRaft 2026-11-22).

# FS/FT are what the type measures ON PAPER, so they are the one thing not to shrink when
# the figure shrinks. FS_MIN is the floor of the label ladder: below it a label is left out
# rather than set at a size no reader can use (AqRaft 2026-11-20).
import os as _os                                                  # (also imported below)
_WR = _os.environ.get("WRAP")
NARROW = COMPACT if _WR in (None, "") else _WR not in ("0", "no")
FS = float(_os.environ.get("FS") or (6.5 if COMPACT else 6))      # annotations (pt)
FT = float(_os.environ.get("FT") or (7.5 if COMPACT else 7))      # row and axis labels (pt)
FS_MIN = float(_os.environ.get("FS_MIN") or 0)
plt.rcParams.update({"font.family": ["Times New Roman", "Times", "STIXGeneral"], "mathtext.fontset": "stix",
                     "font.size": FT, "axes.edgecolor": AXIS, "axes.linewidth": 0.45,
                     "xtick.direction": "out", "ytick.direction": "out", "xtick.color": AXIS,
                     "ytick.color": AXIS, "xtick.labelcolor": INK, "ytick.labelcolor": INK,
                     "xtick.labelsize": FT - 0.5, "ytick.labelsize": FT, "hatch.linewidth": 0.5,
                     "pdf.fonttype": 42, "ps.fonttype": 42})

import os as _os, glob as _glob, matplotlib.font_manager as _fm
if _os.environ.get("CMU_DIR"):     # Computer Modern (CMU Serif) for every label, LaTeX-style math
    for _f in _glob.glob(_os.environ["CMU_DIR"] + "/*.ttf"): _fm.fontManager.addfont(_f)
    plt.rcParams.update({"font.family": ["CMU Serif"], "mathtext.fontset": "cm"})
# FONT_DIR is a directory of serif .otf/.ttf to set the labels in, and FONT_FAMILY the family
# name inside those files. This matters more than it looks: a USENIX paper is Times through
# mathptmx, which is URW Nimbus Roman, while matplotlib's "Times New Roman" is Monotype's
# different drawing of Times. Side by side on the page the two do not match. TeX Gyre Termes
# is Nimbus Roman as OpenType, so pointing FONT_DIR at it puts the figures in the paper's own
# face. Math (the one arrow) stays with STIX, which is Times-metric (AqRaft 2026-11-20).
elif _os.environ.get("FONT_DIR"):
    for _f in (_glob.glob(_os.environ["FONT_DIR"] + "/*.otf") +
               _glob.glob(_os.environ["FONT_DIR"] + "/*.ttf")):
        _fm.fontManager.addfont(_f)
    plt.rcParams["font.family"] = [_os.environ.get("FONT_FAMILY", "TeX Gyre Termes")]
# ---- rows, top to bottom: (key, label, height in row units) ----------------------------------------
lanes = []                                  # recovery steps in non-overlapping lanes
for it in sorted(rec):
    for ln in lanes:
        if ln[-1][1] + 0.02 <= it[0]:
            ln.append(it); break
    else:
        lanes.append([it])
# The same rows, in the same order and height, in every figure (empty when the scenario has
# nothing for them), so figures of different scenarios line up side by side:
#   Recipient / Donor: groups without a leader (red), the new recipient leader's index update of
#     its durable data (tick), followers down (red: kill -> restart, or to the end), frozen, or
#     refilling after a restart (grey: restart -> back in sync with the leader), a partition
#   Recovery: plan, chain rebuild, stalled forward / re-forward (up to 2 lanes)
#   Copy / Replication / Index update: the pair's rounds
REC_H = 1.3
# Recipient replicas that logged an index update, ordered by when they FIRST finished one, so
# the leader sits on top and the chain order reads downward. Each gets its own sub-row in the
# "Replica index update" lane with its host name, because a bare tick does not say WHICH replica
# finished -- which is the whole question that lane answers.
IDXREP_HOSTS = []
for _r in rounds:
    for _z in sorted(_r.get("idx_done") or [], key=lambda q: q["t"]):
        if _z["host"] not in IDXREP_HOSTS:
            IDXREP_HOSTS.append(_z["host"])
# SHOW_IDXREP=0: drop the per-replica "Replica index update" row. Emptying the host list is
# enough -- the layout below leaves the lane out when it is empty, and both of the row's drawing
# blocks are already guarded by it (AqRaft 2026-11-20).
if _os.environ.get("SHOW_IDXREP", "1") in ("0", "no", ""):
    IDXREP_HOSTS = []
IDXREP_H = max(1.0, 0.40 * len(IDXREP_HOSTS)) if IDXREP_HOSTS else 0.0

layout = [("donor", "Donor", 1.0), ("recip", "Recipient", 1.0), ("rec", "Recipient\nrecovery" if NARROW else "Recipient recovery", REC_H),
          ("copy", "Recipient (L)\ntransfer" if NARROW else "Recipient (L) transfer", 1.0),
          ("idx", "Index\nupdate" if NARROW else "Index update", 1.0),
          ("repl", "Chain\nreplication" if NARROW else "Chain replication", 1.0),
          ("async", "Async chain\nreplication" if NARROW else "Async chain replication", 1.0),
          ("idxrep", "Replica index\nupdate" if NARROW else "Replica index update", IDXREP_H)]
if not IDXREP_HOSTS:
    layout = [t for t in layout if t[0] != "idxrep"]
# AqRaft 2026-11-20: SHOW_REC=0 drops the Recipient-recovery row. Its contents (the refetch
# and the chain rebuild) are short boxes whose meaning lives in the text beside them rather
# than in their length, so the row costs a lane's height to say what a sentence can.
if _os.environ.get("SHOW_REC", "1") in ("0", "no", ""):
    layout = [t for t in layout if t[0] != "rec"]
# DROP_LANES leaves lanes out by key. In a no-fault run the Recipient lane carries nothing
# (it is where the faults are drawn) and the Donor lane repeats Recipient (L) transfer
# exactly -- the same RDMA writes seen from each side -- so the baseline figure asks for
# "donor,recip" and keeps only the four lanes that differ (AqRaft 2026-11-20).
DROPPED = {k for k in (_os.environ.get("DROP_LANES") or "").replace(" ", "").split(",") if k}
if DROPPED:
    layout = [t for t in layout if t[0] not in DROPPED]

# The red cross that marks a phase the crash cut mid-flight. It has to read at a panel's
# final size, where a cut bar is a few hundredths of an inch wide and the cross is the only
# thing saying the phase did not finish, so it is drawn heavier than the bars around it.
# CUT_MS and CUT_MEW override the size and the stroke weight (AqRaft 2026-11-20).
# The cross that marks a phase the crash cut mid-flight. Drawn with the FILLED "X" glyph
# rather than two thin strokes: at a panel's final size a stroked cross either disappears or,
# once the stroke is heavy enough to see, closes up into a blob. The filled glyph keeps the
# X shape at any size, and a thin white edge holds it off the bar behind it.
# CUT_MS sizes it and CUT_MEW sets that edge (AqRaft 2026-11-20).
# UNIT is what follows a duration. The default is a thin space and "s"; a panel in a grid
# sets UNIT=s and gets the width of that space back, which is the difference between a
# label that fits inside its bar and one that is left out (AqRaft 2026-11-20).
UNIT = _os.environ.get("UNIT", " s")
DUR = _os.environ.get("DUR", "%.2f")
CUT_MARK = _os.environ.get("CUT_MARK", "X")
CUT_MS = float(_os.environ.get("CUT_MS", 0) or 0) or (8.0 if not COMPACT else 7.0)
CUT_MEW = float(_os.environ.get("CUT_MEW", 0) or 0) or 0.7
RECIP_HOSTS, DONOR_HOSTS = ("redis3", "redis4", "redis5"), ("redis0", "redis1", "redis2")
side_of = lambda h: "recip" if h in RECIP_HOSTS else "donor"
faults = d.get("faults", [])
side_items = {"recip": [], "donor": []}   # (start, end, kind, label)
for g, a, b in dead:
    side_items["recip" if g in ("sg4", "sg5", "sg6") else "donor"].append(
        (a, b, "noleader", ("" if g in ("sg4", "sg1") else g + " ") + ("no leader " + DUR + UNIT) % (b - a)))
for f in faults:
    if f["kind"] == "partition" and f.get("secs"):
        for sd in ("recip", "donor"):
            side_items[sd].append((f["t"], f["t"] + f["secs"], "fault", "partition %.1f s" % f["secs"]))
    elif f["kind"] == "freeze" and f.get("secs"):
        side_items[side_of(f["host"])].append((f["t"], f["t"] + f["secs"], "fault",
                                               "%s frozen %.1f s" % (f["host"], f["secs"])))
    elif f["kind"] == "kill":
        # a leader's kill is its group's no-leader box; a follower's is drawn down until its restart
        if any(abs(a - f["t"]) < 0.05 for g, a, b in dead):
            continue
        # the CURRENT leader killed again (C11: the leader elected after the first kill): another
        # no-leader interval, until the group's next election
        lead = None
        for g in sorted({x[0] for x in d.get("leaders", [])}):
            if f.get("sg") and g != f["sg"]:
                continue
            prev = [x for x in d["leaders"] if x[0] == g and x[2] <= f["t"]]
            if prev and max(prev, key=lambda x: x[2])[1] == f["host"]:
                lead = g
        if lead:
            nxt = [x[2] for x in d["leaders"] if x[0] == lead and x[2] > f["t"]]
            if nxt:
                b_ = min(nxt)
                side_items["recip" if lead in ("sg4", "sg5", "sg6") else "donor"].append(
                    (f["t"], b_, "noleader", ("no leader " + DUR + UNIT) % (b_ - f["t"])))
                continue
        rs = [x["t"] for x in faults if x["kind"] == "restart" and x["host"] == f["host"] and x["t"] > f["t"]]
        end = min(rs) if rs else None
        side_items[side_of(f["host"])].append((f["t"], end, "down", "%s down" % f["host"]))
for f in faults:
    if f["kind"] == "restart":
        ss = [x["t"] for x in faults if x["kind"] == "insync" and x["host"] == f["host"] and x["t"] > f["t"]]
        if ss:
            side_items[side_of(f["host"])].append((f["t"], min(ss), "refill",
                                                   "%s refill %.0f s" % (f["host"], min(ss) - f["t"])))
Y, edges, top = {}, [], 0.0
for key, lab, h in layout:                  # y grows downward in this loop, flipped below
    Y[key] = top + h / 2; edges.append((top, top + h)); top += h
TOTAL = top
Y = {k: TOTAL - v for k, v in Y.items()}
edges = [(TOTAL - b, TOTAL - a) for a, b in edges]
# GLEG=1 puts a band above the panel naming the migration-group shades, for a figure whose
# caption no longer explains them. Off by default: in a grid of panels one caption serves
# all of them and the band would cost 0.20 in on each (AqRaft 2026-11-22).
GLEG = _os.environ.get("GLEG", "0") not in ("0", "no", "")
LEG_IN = 0.20 if GLEG else 0.0   # legend band above the top panel (in)
# SHOW_YCSB=0: the phase timeline alone, with no YCSB throughput panel under it. The panel's
# height is given back to the figure rather than left blank, and the time axis moves up to the
# phase panel (AqRaft 2026-11-20).
SHOW_YCSB = _os.environ.get("SHOW_YCSB", "1") not in ("0", "no", "")
# XLABEL=0: drop the "Time after the crash (s)" axis title, for a grid of panels where one
# title under the bottom row serves all of them. The tick numbers stay.
XLABEL_ON = _os.environ.get("XLABEL", "1") not in ("0", "no", "")
_XL_H = 0.0 if XLABEL_ON else 0.17
_YC_H = 0.8 if COMPACT else 0.75
# LANE_H is the height of one lane in inches. The default 0.33 is what the figures were
# drawn at; the paper runs them a little shorter so the floats stop taking a page each.
# Dropping it too far costs the two-line "G1 / 0.51s" labels, which then fall back to the
# duration alone (AqRaft 2026-11-20).
LANE_H = float(_os.environ.get("LANE_H") or 0.33)
HEIGHT = (0.95 if COMPACT else 0.9) + LANE_H * TOTAL + (0.25 if COMPACT else 0.2) + LEG_IN - _XL_H
if not SHOW_YCSB:
    HEIGHT -= _YC_H
# BAR_H is a bar's height as a fraction of its lane. At 0.56 the two-line label inside a
# bar had its top line's ink 0.38 pt ABOVE the bar's edge, measured on the output: the
# text fitted the lane but not the rectangle it sat in (AqRaft 2026-11-21).
H = float(_os.environ.get("BAR_H") or 0.56)

if SHOW_YCSB:
    fig, (ax, ay) = plt.subplots(2, 1, figsize=(WIDTH, HEIGHT), sharex=True,
                                 gridspec_kw={"height_ratios": [LANE_H * TOTAL + 0.15, _YC_H]})
else:
    fig, ax = plt.subplots(1, 1, figsize=(WIDTH, HEIGHT))
    ay = None
PANELS_ = (ax, ay) if SHOW_YCSB else (ax,)
# XPAD_L/XPAD_R: the empty time before the first bar and after the last. The defaults leave
# room for a crash annotation before t=0; a no-fault figure has none, and that margin is
# width the bars need to carry their durations (AqRaft 2026-11-22).
_XPL = _os.environ.get("XPAD_L")
_XPR = _os.environ.get("XPAD_R")
x0 = (pair_start - float(_XPL)) if _XPL else min(-0.8 if NARROW else -1.0, pair_start - 0.1)
x1 = (pair_end + float(_XPR)) if _XPR else max(pair_end + (0.25 if NARROW else 0.7), max(kills) + 4.0,   # >= 4 s after the crash: comparable figures
         max([b + 0.5 for it in side_items.values() for a, b, k, lab in it if b is not None] or [0]))
# XMIN/XMAX pin the time window. Without them each run picks its own from its own events,
# which is right for a figure on its own and wrong for a grid of panels read side by side:
# the panels end up on different scales, and a bar the window clips loses the label that no
# longer fits inside it (AqRaft 2026-11-20).
x0 = float(_os.environ["XMIN"]) if _os.environ.get("XMIN") else x0
x1 = float(_os.environ["XMAX"]) if _os.environ.get("XMAX") else x1


ROW_LABELS = _os.environ.get("ROW_LABELS", "1") not in ("0", "no", "")
# LEFT_IN overrides the label gutter. The default leaves room for the widest lane name at
# the default type size; a grid of panels can set it to what the names actually measure and
# give the difference back to the plot area (AqRaft 2026-11-20).
L_IN = float(_os.environ.get("LEFT_IN", "0") or 0) or ((1.02 if NARROW else 1.45) if ROW_LABELS else 0.10)
R_IN = 0.05                                                   # left/right margins (in)
IN_PER_S = (WIDTH - L_IN - R_IN) / (x1 - x0)                    # inches per second on the time axis
# margins now (not at the end): the bars below are sized in inches from the axes geometry
fig.subplots_adjust(left=L_IN / WIDTH, right=1 - R_IN / WIDTH, top=1 - (0.03 + LEG_IN) / HEIGHT,
                    bottom=(float(_os.environ.get("BOTTOM_IN") or (0.36 if COMPACT else 0.31))
                            - _XL_H) / HEIGHT, hspace=0.12)
# XOFF shifts what the time axis READS, not where anything is drawn: the bars keep their own
# zero at the migration start, and the labels become the run clock of the client panel beside
# it, so one time can be followed across both panels (AqRaft 2026-11-22).
XOFF = float(_os.environ.get("XOFF") or 0)
if XOFF:
    from matplotlib.ticker import FuncFormatter, MultipleLocator
    _step = float(_os.environ.get("XSTEP") or 1)
    ax.xaxis.set_major_locator(MultipleLocator(_step, offset=(-XOFF) % _step))
    ax.xaxis.set_major_formatter(FuncFormatter(lambda v, _p: "%g" % round(v + XOFF, 6)))
ax.set_xlim(x0, x1); ax.set_ylim(0, TOTAL)
_pos = ax.get_position()
ASPECT = (TOTAL / (_pos.height * HEIGHT)) * IN_PER_S   # row units per inch / seconds per inch
# the white gap between touching boxes, in inches of page. At 0.012 in two consecutive
# groups read as one block with their labels jammed together, which is why the pair
# before a crash looked cramped next to the isolated bars after it (AqRaft 2026-11-21).
GAP_X = float(_os.environ.get("GAP_IN") or 0.012) / IN_PER_S
RND_X = 0.016 / IN_PER_S                                # corner rounding (same in every figure)


_TW_CACHE = {}


def text_w(txt, fs):
    """Printed width (in) of the widest line of txt at fs pt, MEASURED in the font actually in
    use. This was an estimate of 0.40 em per character, which ran 5-35% short -- worst on the
    short strings, where "G1" came out at two thirds of its real width -- so a label was
    accepted into a bar it then overflowed. Measuring costs one throwaway Text per distinct
    (string, size), which is why the results are cached (AqRaft 2026-11-20)."""
    key = (txt, round(fs, 2))
    if key not in _TW_CACHE:
        _t = fig.text(0, 0, txt, fontsize=fs)
        try:
            _TW_CACHE[key] = _t.get_window_extent(renderer=fig.canvas.get_renderer()).width / fig.dpi
        except Exception:        # no renderer yet: fall back to the old estimate
            _TW_CACHE[key] = max(len(t) for t in txt.split("\n")) * fs * 0.40 / 72
        finally:
            _t.remove()
    return _TW_CACHE[key]


def fits(txt, fs, a, b, pad=0.04, h=None):
    """txt fits inside a box from a to b (s), with pad (in) to spare; and in height h (row units)."""
    # A box the time window cuts is drawn shorter than it is, so a duration written inside it
    # would be a number over a bar of the wrong length. Leave it out and let the bar run off
    # the edge unlabelled (AqRaft 2026-11-20).
    if a < x0 - 1e-9 or b > x1 + 1e-9:
        return False
    if text_w(txt, fs) + pad > (b - a) * IN_PER_S:
        return False
    return h is None or (txt.count("\n") + 1) * fs * 1.05 / 72 <= h * IN_PER_S / ASPECT + 0.01


_CUR_PAIR = [None]


def gname(n):
    """What a bar calls its migration group. With one pair in the figure the pair is implicit
    and the group's number is enough ("G3"). With all three on one axis the pair is what tells
    two bars of the same shade apart, so it leads the name ("B3")."""
    return ("%s%d" % (_CUR_PAIR[0], n)) if (ALL_PAIRS and _CUR_PAIR[0]) else ("G%d" % n)


def group_lab(n, a, b, h=None):
    """What a bar says: its migration group over its duration, then the duration alone, then
    the group alone, each tried at three sizes. One ladder for every lane, so the same bar
    does not read "G2" in one row and "0.51s" in the row below (AqRaft 2026-11-20)."""
    for cand in ((gname(n) + "\n" + DUR + UNIT) % (b - a), (DUR + UNIT) % (b - a), gname(n)):
        for f in [x for x in (FS - 1.0, FS - 1.8, FS - 2.4) if x >= FS_MIN]:
            if fits(cand, f, a, b, pad=0.015, h=(h if "\n" in cand else None)):
                return cand, f
    return "", None


def held_lab(n, a, b, h=None):
    """A bar that was still being held when the crash hit says so, but it is a bar of a
    group like any other, so it carries that group's name first: "G1" over "held", then
    "held" alone, then "G1" alone. Without the name the only bar of G1 in these two lanes
    read "held" while every other bar of G1 read "G1", so the group did not line up with
    itself across the figure (AqRaft 2026-11-20)."""
    for cand in (gname(n) + "\nheld", "held", gname(n)):
        for f in [x for x in (FS - 1.0, FS - 1.8, FS - 2.4) if x >= FS_MIN]:
            if fits(cand, f, a, b, pad=0.10, h=(h if "\n" in cand else None)):
                return cand, f
    return "", None


def lane_y(*names):
    """The y of the first lane that exists, falling back to the topmost drawn lane."""
    for n in names:
        if n in Y:
            return Y[n]
    return max(Y.values()) if Y else 0.0


def short_of(lab):
    """The short form of a label: its duration ("... 0.59 s" -> "0.59 s"), else its last word."""
    m = re.search(r"([\d.]+ s)$", lab)
    return m.group(1) if m else lab.split()[-1]


# Flow arrows (FLOW_ARROWS=0 turns them off): every bar drawn while _CUR_ROUND is set is
# recorded, so one round can be followed down the lanes it passes through after the fact,
# without threading positions through the round loop's many branches.
_BARS = []
_CUR_ROUND = [None]


# Every two-line in-bar label passes ls=1.35. The bars of a round the crash interrupted used to
# take the 0.85 default, so in S10 the pre-crash G1 had its two lines 5.2pt apart while the
# re-sent G1 one lane over had them 7.4pt apart -- the same bar, the same size, reading as
# misaligned (AqRaft 2026-11-22).
def bar(y, a, b, fill, txt="", txtcol=INK, h=H, hatch=None, edge=None, lw=0.0, z=2, fs=None, ls=0.85,
        ha="center"):
    """A box from a to b (s) on row y: slightly rounded corners, and a hair of white on each side
    so boxes that touch stay apart."""
    g = GAP_X if (b - a) > 3 * GAP_X else 0.0
    w = max(b - a - g, 1e-6)
    r = min(RND_X, w / 2, (h / 2) / ASPECT)
    if _CUR_ROUND[0] is not None:
        _BARS.append((_CUR_ROUND[0], y, a, b, fill))
    ax.add_patch(FancyBboxPatch((a + g / 2, y - h / 2), w, h,
                                boxstyle="round,pad=0,rounding_size=%.6g" % r, mutation_aspect=ASPECT,
                                facecolor=fill, hatch=hatch, zorder=z,
                                edgecolor=edge if edge else (MUTED if hatch else fill),
                                linewidth=lw if (edge or hatch) else 0))
    if txt:
        # ha="left" pins the label to the bar's START instead of its middle. A bar another round
        # is drawn over (the held forward in S10) has a centred label landing where that round's
        # own label sits; at one-column width the two collide (AqRaft 2026-11-20).
        _tx = (a + b) / 2 if ha == "center" else a + 0.035 / IN_PER_S
        ax.text(_tx, y, txt, ha=ha, va="center", fontsize=fs or FS, color=txtcol, zorder=z + 1,
                linespacing=ls)


# grid: light alternating row bands, vertical lines at every second through both panels
for i, (lo, hi) in enumerate(edges):
    if i % 2 == 0:
        ax.axhspan(lo, hi, color=G["band"], lw=0, zorder=0)

# the new recipient leader's index update of its durable data, then serves: a tick, and a note that
# shortens itself to the free space before the next item of the row
idx_notes = []   # (tick x, note, note end x)
for g, a, b in dead:
    if g in idx_dur:
        ia, ib = idx_dur[g]
        ms = max(1, (ib - ia) * 1e3)
        nxt = min([it[0] for it in side_items["recip"] if it[0] > ia + 0.01] + [x1])
        note = next((t for t in (("index update (%.0f ms), then serve" if COMPACT else
                                  "index update of durable data (%.0f ms), then serve clients") % ms,
                                 "index update %.0f ms" % ms, "%.0f ms" % ms)
                     if text_w(t, FS) / IN_PER_S + 0.12 <= nxt - ia), "")
        idx_notes.append((ia, note, ia + 0.08 + text_w(note, FS) / IN_PER_S if note else ia))
# The index update of the durable data takes ~1 ms right at the end of the time without a leader:
# not drawn (the faulty phase ends where the new leader serves).
idx_notes = []
# Recipient / Donor rows: items in up to two lanes when they overlap in time
for sd, items in side_items.items():
    items = sorted((a, (b if b is not None else x1), k, lab) for a, b, k, lab in items)
    rows_ = []
    for it in items:
        for ln in rows_:
            if ln[-1][1] + 0.02 <= it[0]:
                ln.append(it); break
        else:
            rows_.append([it])
    nl = max(1, len(rows_))
    lh = 1.0 / nl
    for li, ln in enumerate(rows_):
        if sd not in Y:
            continue
        y = Y[sd] + 0.5 - lh * (li + 0.5)
        h = min(H, lh * 0.82)
        for a, b, kind, lab in ln:
            if kind == "refill":
                bar(y, a, b, G["fill"], h=h, edge=MUTED, lw=0.4)
                col = INK
            else:   # no leader, down, frozen, partition: the fault, red
                bar(y, a, b, "white", hatch="/////", edge=RED, lw=0.6, h=h)
                col = INK   # label text black (red text on the red hatching was hard to read)
            # the label inside the box if it fits there (full, on two lines, or short), else the
            # short form next to the box where the lane is free -- never across the box's edge
            f0 = FS if nl == 1 else FS - 0.8
            P = 0.06                      # default clearance (in) a label leaves inside its bar
            sh = short_of(lab)
            # break before the duration -- "no leader" over "1.51s" -- rather than two words
            # from the end, which used to give "no" over "leader 1.51s"
            two = (lab[:lab.rfind(" ")] + "\n" + lab[lab.rfind(" ") + 1:]) if " " in lab else None
            # In a panel the two-line form is tried FIRST. One box in six happens to be wide
            # enough for the single line, and a figure where one box reads "no leader 1.74s"
            # and its neighbour reads "1.07s" looks like two different marks (AqRaft 2026-11-20).
            cands = ([(two, f0, P), (lab, f0, P), (two, f0 - 1.0, P)] if (COMPACT and two) else
                     [(lab, f0, P)] + ([(two, f0, P)] if two else []))
            # A bar near 1.1s is 0.37in wide and the two-line form needs 0.31in at one size
            # down, so the 0.06in pad alone is what pushes it out and the box falls back to a
            # bare "1.1s" -- a red hatched bar with no word in it. Retry the two-line form on a
            # tighter pad before giving up the name (AqRaft 2026-11-22).
            if two:
                cands += [(two, f0 - 1.0, 0.03)]
            cands += [(sh, f0, P), (sh, f0 - 1.0, P)]
            pick = next(((t, f) for t, f, pd in cands if fits(t, f, a, b, pad=pd, h=h)), None)
            if pick:
                ax.text((a + b) / 2, y, pick[0], fontsize=pick[1], ha="center", va="center", color=col,
                        zorder=4, linespacing=0.85,
                        bbox=dict(boxstyle="square,pad=0.05", fc="white", ec="none") if kind != "refill" else None)
            else:
                wsh = text_w(sh, f0 - 1.0) / IN_PER_S + 0.08
                nxt = min([c for c, _, _, _ in ln if c > a] + [x1] +
                          ([n0 for n0, _, _ in idx_notes if n0 >= b - 0.01] if sd == "recip" else []))
                prv = max([d_ for _, d_, _, _ in ln if d_ < a] + [x0])
                if nxt - b > wsh:
                    ax.text(b + 0.04, y, sh, fontsize=f0 - 1.0, ha="left", va="center", color=col, zorder=4)
                elif a - prv > wsh:
                    ax.text(a - 0.04, y, sh, fontsize=f0 - 1.0, ha="right", va="center", color=col, zorder=4)
            if kind == "refill":
                ax.plot([b] * 2, [y - h / 2, y + h / 2], color=INK, lw=1.2, zorder=4)   # in sync
for ia, note, _ in idx_notes:
    y = lane_y("recip", "copy", "donor")
    ax.plot([ia] * 2, [y - H / 2, y + H / 2], color=INK, lw=1.6, zorder=4)
    if note:
        ax.text(ia + 0.08, y, note, fontsize=FS, color=INK, va="center")
# recovery steps, one lane each, labels inside and durations to the right
RF_DONE = False
# re-pack the recovery steps now that label widths are known: a step's label sits to the right of
# its bar, so the next step on the same line must start after that label, not just after the bar
def _step_end(it):
    a, b, long_lab, short_lab, fill = it
    lab = short_lab if COMPACT else long_lab
    if fits(lab, FS - 0.3, a, b):
        return b + 0.06 + text_w("0.00 s", FS - 0.3) / IN_PER_S
    return b + 0.06 + text_w(lab + " 0.00 s", FS - 0.3) / IN_PER_S
lanes = []
for it in sorted(rec):
    for ln in lanes:
        if _step_end(ln[-1]) + 0.04 <= it[0]:
            ln.append(it); break
    else:
        lanes.append([it])
if lanes and "rec" in Y:
    n_l, rh = len(lanes), REC_H
    lane_h = rh / max(2, n_l)
    for li, ln in enumerate(lanes):
        y = Y["rec"] + rh / 2 - lane_h * (li + 0.5)
        for a, b, long_lab, short_lab, fill in ln:
            lab = short_lab if COMPACT else long_lab
            inside = fits(lab, FS - 0.3, a, b)
            bar(y, a, b, G[fill], lab if inside else "", h=min(0.5, lane_h * 0.78), edge=MUTED, lw=0.4,
                fs=FS - 0.3)
            txt = ((DUR + UNIT) if inside else lab + (" " + DUR + UNIT)) % (b - a)
            if RF_NOTE and long_lab == "refetch group" and not COMPACT:
                txt += ": " + RF_NOTE
                RF_DONE = True
            ax.text(b + 0.06, y, txt, fontsize=FS - 0.3, color=INK, va="center")
if RF_SHORT and COMPACT:      # column figure: no room beside the refetch bar -- two lines on the
    # Recipient row, right of the no-leader interval
    # right of the recipient group's no-leader bar (and of its label when it sits outside the bar)
    nx = RF["t"] + 0.08
    for g, a, b in dead:
        if g in ("sg4", "sg5", "sg6") and GROUP_PAIR.get(g) == PAIR:
            dl = (DUR + UNIT) % (b - a)
            e = b + text_w(dl, FS) / IN_PER_S + 0.16      # past the bar and a label beside it
            nx = max(nx, e)
    # keep it inside the frame: at one-column width this note runs past the right edge
    # (AqRaft 2026-11-20)
    _rw = max(text_w(_l, FS - 1.0) for _l in RF_SHORT.split("\n")) / IN_PER_S
    nx = max(x0 + 0.02 / IN_PER_S, min(nx, x1 - _rw - 0.04 / IN_PER_S))
    ax.text(nx, lane_y("recip", "copy", "donor"), RF_SHORT, fontsize=FS - 1.0, color=INK, va="center", linespacing=1.1)
elif RF_NOTE and not RF_DONE and "rec" in Y:   # no refetch bar (donor asked the recipient, ~1 ms): note alone
    li = len(lanes) if len(lanes) < 2 else 0
    lane_h = REC_H / 2
    y = Y["rec"] + REC_H / 2 - lane_h * (li + 0.5)
    ax.text(RF["t"], y, "refetch: " + RF_NOTE, fontsize=FS - 0.3, color=INK, va="center")
# the pair's rounds: copy, replication to F1, index update
AGONE = []        # rounds with no F1 -> F2 hop left to draw: the group has one follower
AEND = []         # where the async bars that ARE drawn end: the note must clear them
for r, n in zip(rounds, num):
    _CUR_ROUND[0] = n
    _CUR_PAIR[0] = r["pair"]
    ca, cb = r["copy"]
    if cb is None:           # its donor died mid-copy: the copy ends at that kill
        cb = next((kt for kt in sorted(kills) if kt > ca), ca + 0.05)
    if r.get("async_gone"):
        AGONE.append((ca, cb))
    if not r["ok"]:          # a round its crash cut short: its own round color up to the crash,
        # and a red x where each of its bars meets the crash line (transfer, index update, chain
        # replication alike)
        kt = next((t for t in sorted(kills) if t >= ca - 1e-6), cb)
        rc, rt = ROUND_COL[(n - 1) % len(ROUND_COL)]
        # drawn at its true length (a round cut right after it started is a sliver); its number
        # only when it fits
        ce = min(cb, kt)
        # the donor sending it, the recipient leader receiving it (a round cut in its setup moved
        # no byte yet: the donor row only)
        rws = tuple(w for w in (("donor",) if r.get("setup") else ("donor", "copy")) if w in Y)
        # AqRaft 2026-11-20: a copy that finished before the crash carries its duration like any
        # other round. Only a copy the crash cut mid-flight has no duration to state, and then the
        # round number alone is the label.
        _done = ce < kt - 0.02
        _cl = ((gname(n) + "\n" + DUR + UNIT) % (ce - ca)) if _done else gname(n)
        _cf = next((f for f in [x for x in (FS - 1.0, FS - 1.8, FS - 2.4) if x >= FS_MIN]
                    if fits(_cl, f, ca, ce, pad=0.015, h=(H if _done else None))), None)
        if _cf is None and _done:                      # the duration does not fit: the number does
            _cl, _cf = gname(n), (FS - 1.0 if fits(gname(n), FS - 1.0, ca, ce, pad=0.01) else None)
        for row in rws:
            bar(Y[row], ca, ce, rc, _cl if _cf else "", txtcol=rt, fs=_cf or (FS - 1.0), ls=1.35)
        # an x only where a bar meets the crash line: a copy that had finished gets none
        cut = [Y[w] for w in rws] if ce >= kt - 0.02 else []
        held = r.get("held")
        for key in ("idx", "repl"):
            a0 = r[key][0]
            if a0 is None and held:   # landed, waiting to be forwarded to F1 when the leader died
                a0 = held[0]
                lab, _hf = held_lab(n, a0, kt, H)
                bar(Y[key], a0, kt, rc, lab, txtcol=rt, fs=_hf or (FS - 1.0), ha="left", ls=1.35)
                cut.append(Y[key])
            elif a0 is not None and a0 < kt:
                # AqRaft 2026-11-20: draw to the phase's OWN end, not to the kill line.
                # This branch covers every round in a "not ok" group, but under deep a kill
                # leaves rounds in two very different states: some were genuinely cut
                # mid-phase, others had finished every phase and were only missing their
                # commit. Drawing both to kt and crossing them claimed the second kind was
                # destroyed -- in S1, round 1's index update and chain replication both ended
                # at -0.15 s, 150 ms before the crash, and were drawn running into it.
                a1 = r[key][1]
                end = kt if (a1 is None or a1 > kt) else a1
                # a phase that ran to its own end carries its duration, as in a clean round; one
                # the crash cut has no duration to state and stays bare
                # a phase that ran to its own end carries the group and its duration, as in a
                # clean group; one the crash cut has no duration to state and stays bare
                _pd, _pf = (group_lab(n, a0, end, H) if (a1 is not None and a1 <= kt - 0.02)
                            else ("", None))
                bar(Y[key], a0, end, rc, _pd if _pf else "", txtcol=rt, fs=_pf or (FS - 1.0), ls=1.35)
                if a1 is None or a1 > kt - 0.02:
                    cut.append(Y[key])
        for yy in cut:
            ax.plot([kt], [yy], marker=CUT_MARK, color=RED, ms=CUT_MS, mew=CUT_MEW, mec="#ffffff", zorder=6, clip_on=False)
        continue
    # each bar carries its duration (copy: round number above it), when it fits the bar
    # the duration at one size, or one step smaller, before it is left out
    DFS = FS - 1.0
    lab = (gname(n) + "\n" + DUR + UNIT) % (cb - ca)
    if not fits(lab, DFS, ca, cb, pad=0.015, h=H):
        DFS = FS - 1.8
        if not fits(lab, DFS, ca, cb, pad=0.015, h=H):
            lab, DFS = gname(n), FS - 1.0
    # one color per round, the same for its copy, replication and index update
    rc, rt = ROUND_COL[(n - 1) % len(ROUND_COL)]
    # the transfer of the round: the donor sending it (Donor row) and the recipient leader
    # receiving it (Recipient (L) transfer row) -- the same RDMA writes, seen from each side
    for row in (w for w in ("donor", "copy") if w in Y):
        if r["reship"]:
            # the retransfer: the color of the round it sends again (the one the crash cut), no outline
            bar(Y[row], ca, cb, rc, lab, txtcol=rt, z=3, fs=DFS, ls=1.35)
        else:
            bar(Y[row], ca, cb, rc, lab, txtcol=rt, fs=DFS, ls=1.35)
    ad = r.get("adopted")
    for key, (a, b), col, tc in (("repl", r["repl"], rc, rt), ("idx", r["idx"], rc, rt)):
        if a is not None and b is None and ad:
            # the old leader died before finishing this step for the round (S12: its index update):
            # cut at the crash, like a lost round
            kt = next((t for t in sorted(kills) if t >= a - 1e-6), None)
            if kt is not None and kt > a:
                bar(Y[key], a, kt, col)
                ax.plot([kt], [Y[key]], marker=CUT_MARK, color=RED, ms=CUT_MS, mew=CUT_MEW, mec="#ffffff",
                        zorder=6, clip_on=False)
            continue
        if a is None or b is None:
            continue
        d, f_ = group_lab(n, a, b, H)
        bar(Y[key], a, b, col, d, txtcol=tc, fs=f_ or DFS, ls=1.35)
    # the rest of the chain after the majority hop (F1 -> F2), when the round had one; if F1 held
    # the round for a while before sending it, that wait as a thin line with its length
    aa, ab = (r.get("async") or [None, None])
    # F1 holding the round for F2 when the leader died (S12: the test hook held F1's forward
    # across the crash): the hold up to the crash, cut there, like S10's held forward
    aw = r.get("async_wait")
    if aw and aw[0] is not None:
        kw = next((t for t in sorted(kills) if aw[0] < t < aw[1]), None)
        if kw is not None:
            # "held" on every lane (reverted 2026-11-11): the bar is the forward F1 was holding
            # when the leader died, and the x marker already says the crash stopped it.
            _al, _af = held_lab(n, aw[0], kw, H)
            bar(Y["async"], aw[0], kw, rc, _al, txtcol=rt, fs=_af or (FS - 1.0), ha="left", ls=1.35)
            ax.plot([kw], [Y["async"]], marker=CUT_MARK, color=RED, ms=CUT_MS, mew=CUT_MEW, mec="#ffffff",
                    zorder=6, clip_on=False)
    if aa is not None and ab is not None and ab > aa:
        AEND.append(ab)
        # (fits() already refuses a bar the window cuts, so a label here is one that is
        # written over the whole bar the reader can see)
        d, f_ = group_lab(n, aa, ab, H)
        bar(Y["async"], aa, ab, rc, d, txtcol=rt, fs=f_ or DFS, ls=1.35)
    if ad:
        # finished from a follower's copy after the crash: F1's forward to the new leader (chain
        # replication) and the new leader's index update -- no transfer from the donor
        # labelled with who did it: before the crash the round went leader -> F1 and the old leader
        # indexed it; these are the rest of the chain for the same round (F1 -> F2, and F1 and F2
        # indexing it), which would otherwise read as the same step running twice
        for key, who in (("repl", "F1\u2192F2"), ("idx", "F1, F2")):
            if key not in ad:
                continue
            a, b = ad[key]
            if a is None or b is None or b <= a:
                continue
            lab2 = ("%s\n" + DUR + UNIT) % (who, b - a)
            f_ = next((f for f in [x for x in (FS - 1.0, FS - 1.8, FS - 2.4) if x >= FS_MIN] if fits(lab2, f, a, b, pad=0.015, h=H)), None)
            if f_ is None:
                lab2 = who
                f_ = next((f for f in [x for x in (FS - 1.0, FS - 1.8, FS - 2.4) if x >= FS_MIN] if fits(lab2, f, a, b, pad=0.01)), None)
            bar(Y[key], a, b, rc, lab2 if f_ else "", txtcol=rt, fs=f_ or DFS, ls=1.35)
    # Per-replica index update: one tick per recipient replica, at the moment IT finished
    # indexing this round, joined by a thin line from the first to the last. The leader
    # finishing says nothing about the followers, so the SPREAD is the point -- in S12 the
    # leader indexes round 1 before the crash and the last replica only ~2 s later, after a new
    # leader has taken over. Labelled with the spread when it is big enough to matter.
    _idone = r.get("idx_done") or []
    if _idone and IDXREP_HOSTS:
        # one sub-row per replica, named; a thin line joins THIS round's ticks across the rows so
        # the round they belong to is obvious, and the spread is labelled when it is big enough
        # to matter (in normal operation every replica lands within ~10 ms of the leader).
        _lh = IDXREP_H / len(IDXREP_HOSTS)
        _pts = []
        for _z in sorted(_idone, key=lambda q: q["t"]):
            _ri = IDXREP_HOSTS.index(_z["host"])
            _yy = Y["idxrep"] + IDXREP_H / 2 - _lh * (_ri + 0.5)
            _pts.append((_z["t"], _yy))
            ax.plot([_z["t"]], [_yy], marker="|", color=rc,
                    ms=(6.2 if not COMPACT else 5.4) * min(1.0, _lh / 0.40), mew=1.6,
                    zorder=3, clip_on=False)
        if len(_pts) > 1:
            ax.plot([q[0] for q in _pts], [q[1] for q in _pts], color=rc, lw=0.65, zorder=2)
_CUR_ROUND[0] = None
# An empty async lane after the crash is not missing data: the dead node was dropped when the
# chain was re-established, the group is down to one live follower, and the majority hop already
# reaches it, so there is no F1 -> F2 hop to draw for those rounds. Say so on the lane, or the
# blank reads as a figure that lost its bars (AqRaft 2026-11-20).
if AGONE and "async" in Y and _os.environ.get("ASYNC_NOTE") == "1":   # off by default
    _a0, _a1 = min(z[0] for z in AGONE), max(z[1] for z in AGONE)
    if AEND:                      # clear of the last async bar, which can run under these rounds
        _a0 = max(_a0, max(AEND) + 0.06)
    _a1 = min(_a1, x1)
    for _t in ([] if _a1 - _a0 < 0.12 else
               ("no F1\u2192F2 hop: one follower left", "no F1\u2192F2 hop", "one follower")):
        _f = next((f for f in [x for x in (FS - 1.0, FS - 1.8, FS - 2.4) if x >= FS_MIN] if fits(_t, f, _a0, _a1, pad=0.02)), None)
        if _f is not None:
            ax.text((_a0 + _a1) / 2, Y["async"], _t, ha="center", va="center",
                    fontsize=_f, color=MUTED, zorder=4)
            break
# One round's path down the figure: donor -> recipient (L) transfer -> index update ->
# chain replication -> async chain replication, in the order the lanes are DRAWN, so an
# arrow never crosses a lane it skips. Each arrow leaves the bottom edge of a round's bar
# and lands on the top edge of that same round's next bar, both at the bar's START -- which
# is what makes the pipelining legible: round 2's copy begins while round 1 is still
# replicating, and the arrows show that overlap instead of hiding it.
if _os.environ.get("FLOW_ARROWS", "1") != "0":
    _order = [k for k in ("donor", "copy", "idx", "repl", "async") if k in Y]
    _by_round = {}
    for _rn, _by, _a, _b, _fill in _BARS:
        if _a is None:
            continue
        for _k in _order:
            if abs(_by - Y[_k]) < 1e-6:
                _by_round.setdefault(_rn, {}).setdefault(_k, []).append((_a, _fill))
                break
    for _rn in sorted(_by_round):
        _lanes = {k: sorted(v) for k, v in _by_round[_rn].items()}
        # A round can appear more than once per lane: a round the crash cut is SENT AGAIN, so
        # its donor/copy/idx/repl bars each occur twice. Chain the i-th bar of each lane to the
        # i-th of the next -- one arrow path per episode -- or the resend is left unconnected
        # while the arrows all hang off the episode that died.
        for _ep in range(max(len(v) for v in _lanes.values())):
            _seq = [(k, _lanes[k][_ep][0], _lanes[k][_ep][1]) for k in _order
                    if k in _lanes and _ep < len(_lanes[k])]
            for (_k1, _x1, _c1), (_k2, _x2, _c2) in zip(_seq, _seq[1:]):
                ax.annotate("", xy=(_x2, Y[_k2] + H / 2), xytext=(_x1, Y[_k1] - H / 2), zorder=1.2,
                            arrowprops=dict(arrowstyle="-|>", color=_c1, lw=0.7,
                                            shrinkA=0.5, shrinkB=0.5, mutation_scale=5.5,
                                            connectionstyle="arc3,rad=0.0"))
for kt in (() if NO_FAULT else kills):
    for a_ in PANELS_:
        # behind the boxes and their labels in the top panel; over the throughput frame below
        a_.axvline(kt, color=RED, ls=(0, (3, 2)), lw=0.8, zorder=1.5 if a_ is ax else 2.5)
if IDXREP_HOSTS:
    _lh = IDXREP_H / len(IDXREP_HOSTS)
    for _ri, _h in enumerate(IDXREP_HOSTS):
        _yy = Y["idxrep"] + IDXREP_H / 2 - _lh * (_ri + 0.5)
        ax.text(x0 + 0.02 * (x1 - x0), _yy, _h, fontsize=FS - 2.4, color=MUTED,
                ha="left", va="center", zorder=4)
ax.set_yticks([Y[k] for k, _, _ in layout])
ax.set_yticklabels([lab for _, lab, _ in layout] if ROW_LABELS else [""] * len(layout),
                   linespacing=0.85, fontsize=FT)
ax.set_ylim(0, TOTAL)   # no labels above the rows
ax.tick_params(axis="y", length=0, pad=2)
# XLAB overrides the axis title. The long form costs more height under the plot than a
# short one, which puts this figure's frame out of line with a shorter-titled figure beside
# it; the caption can carry the origin instead (AqRaft 2026-11-20).
XLAB = _os.environ.get("XLAB") or ("Time after the %s (s)" % ("migration start" if NO_FAULT else
                                   "crash" if FIRST_KIND == "kill" else "fault"))
# with a throughput panel below, the ticks here carry no numbers (it has them); without one,
# this panel takes the numbers and the axis title
ax.tick_params(axis="x", length=2.5, width=0.45, color="#000000", labelbottom=not SHOW_YCSB,
               pad=1.5, labelsize=FT - 0.5)
if not SHOW_YCSB and XLABEL_ON:
    ax.set_xlabel(XLAB, fontsize=FT, color=INK, labelpad=1)
# YLABEL=0 drops the "Phase" axis title. The lane names say what the axis is, and in a
# grid of panels the title costs gutter width that the plot area can use instead.
if ROW_LABELS and _os.environ.get("YLABEL", "1") not in ("0", "no", ""):
    ax.set_ylabel("Phase", fontsize=FT, color=INK, labelpad=2)
# No legend band (2026-11-11). The marks are explained in the caption instead, and the band
# cost ~0.22 in of height on every figure. LEG_IN above is the band's size: keep it 0 to
# reclaim the space rather than leave it blank. `git log -S "fig.legend"` has the handles.
if GLEG:
    from matplotlib.patches import Patch
    _h = [Patch(facecolor=ROUND_COL[i][0], edgecolor="none", label="$G_%d$" % (i + 1))
          for i in range(len(ROUND_COL))]
    _bb = ax.get_position()
    fig.legend(handles=_h, loc="lower center", ncol=len(_h), frameon=False, fontsize=FS,
               handlelength=0.9, handleheight=0.9, handletextpad=0.35, columnspacing=0.9,
               borderpad=0.0, borderaxespad=0.0,
               bbox_to_anchor=((_bb.x0 + _bb.x1) / 2, 1 - LEG_IN / HEIGHT + 0.012,
                               0, 0), bbox_transform=fig.transFigure)

FRAME = dict(color="#000000", lw=0.6)    # borders: each panel in a thin black box, flush with the data
# FRAME=0 keeps the bottom axis only, as the 3-vs-5 figure does: the lanes are banded and
# the bars sit on the time axis, so three of the four sides are ink with no job
# (AqRaft 2026-11-21).
_BOXED = _os.environ.get("FRAME", "1") not in ("0", "no", "")
for _n, s_ in ax.spines.items():
    if _BOXED or _n == "bottom":
        s_.set_edgecolor(FRAME["color"]); s_.set_linewidth(FRAME["lw"])
    else:
        s_.set_visible(False)

if SHOW_YCSB:
    # throughput: black line (no fill); the client outage as a dimension line
    pts = [(t, v) for t, v in yc if x0 - 1 <= t <= x1 + 1]
    tx, vy = [t for t, v in pts], [v for t, v in pts]
    ay.plot(tx, vy, color=INK, lw=0.9, marker="o", ms=2.6, mfc="white", mec=INK, mew=0.7, zorder=3)
    if served is not None:
        ay.annotate("", xy=(kills[0], 385), xytext=(served, 385), zorder=4,
                    arrowprops=dict(arrowstyle="<->", lw=0.6, color=INK, shrinkA=0, shrinkB=0))
        ay.plot([served, served], [0, 400], color=INK, lw=0.5, zorder=2)
        # the outage as its duration only, centred under the arrow (2026-11-06)
        ay.text((kills[0] + served) / 2, 368, (DUR + UNIT) % (served - kills[0]), fontsize=FS, color=INK,
                va="top", ha="center")
    ay.set_xlim(x0, x1); ay.set_ylim(0, 440); ay.set_yticks([0, 150, 300])
    ay.set_ylabel("YCSB\nKops/s", fontsize=FT, color=INK, linespacing=0.9, labelpad=2)
    ay.set_xlabel(XLAB, fontsize=FT, color=INK, labelpad=1)
    ay.tick_params(axis="both", length=2.5, width=0.45, pad=1.5, labelsize=FT - 0.5)
    for s_ in ay.spines.values():
        s_.set_edgecolor(FRAME["color"]); s_.set_linewidth(FRAME["lw"])
    ay.tick_params(axis="both", color=FRAME["color"])
# tight_layout does not handle the shared-x grid: explicit margins (inches)
fig.subplots_adjust(left=L_IN / WIDTH, right=1 - R_IN / WIDTH, top=1 - (0.03 + LEG_IN) / HEIGHT,
                    bottom=(float(_os.environ.get("BOTTOM_IN") or (0.36 if COMPACT else 0.31))
                            - _XL_H) / HEIGHT, hspace=0.12)   # the two frames divide the panels
# Both axis titles at the same x, inside the left margin (the longest row label, "Recipient (L)
# transfer", used to push them past the figure edge).
_axw = WIDTH - L_IN - R_IN
for a_ in PANELS_:
    a_.yaxis.set_label_coords(-(L_IN - 0.24) / _axw, 0.5)   # 0.24 in: room for a 2-line title
fig.savefig(out, dpi=400)
if out.endswith(".pdf"):
    fig.savefig(out[:-4] + ".png", dpi=400)
print("wrote %s (%s, pair %s, %.2f x %.2f in)" % (out, sc, PAIR, WIDTH, HEIGHT))
