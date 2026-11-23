# Three replicas per group against five

The same no-fault 3 → 6 migration run twice, once with the recipient group `sg4` at three
replicas and once at five, drawn as one phase breakdown so that the extra hop shows up as
displacement rather than as a number.

**Only `sg4` is widened.** The D5 run's chain setup lists four followers for `sg1->sg4` and
two for `sg2->sg5` and `sg3->sg6`, so pairs B and C run at three replicas in BOTH runs and
serve as controls: they come out at 2.26 vs 2.27 s and 2.47 vs 2.39 s. The figure therefore
follows pair A, which is the only pair the change touches.

```
Makefile          data/ -> figures/replicas_3v5.pdf, timestamp-driven
scripts/          the three scripts that do it
data/D3_r1/       the three-replica run (not in git, see below)
data/D5_r1/       the five-replica run
derived/          the phase data the figure is drawn from (JSON + a readable table)
figures/          replicas_3v5.pdf, 3.33 x 4.48 in
```

Compiling the paper (`make` in the repository root, or any `latexmk` run) redraws the figure
if the logs or a script changed. `make -C experiments/replica_count force` rebuilds it from the logs
up.

## The argument

The phases are identical in both runs. What changes is where a round *commits*. A batch is
durable once a majority of the recipient group holds it, so three replicas stop at F1 and
five stop at F2 — and the F1→F2 relay, off the critical path at three, is on it at five.
Chain replication is store-and-forward, so that second hop costs a full transfer, while the
leader's hop to F1 overlaps the donor's send and is nearly free.

Measured here: **2.23 s** against **3.00 s** for pair A's four rounds, a **+0.78 s** penalty
for the extra replicas, on migrations that took 7.09 s and 7.82 s end to end.

Both runs are no-fault, so `recovery_breakdown.py` is invoked with the scenario name
`HEALTHY`: t = 0 is the migration start rather than a crash.

## The figure

`figures/replicas_3v5.pdf` is drawn at 3.33 × 4.48 in with 7–9 pt type that is 7–9 pt on
paper. Include it with `\includegraphics{...}` and no `width=`. Rescaling throws the type
sizes off.

`scripts/paper_3vs5_breakdown.py` differs from the bundle's copy in one place. The
group-durable rules are drawn behind the bars rather than over them, they stop below the
marker instead of running through it, and each marker carries the number of the group that
committed there (`g1`--`g4`).

The Makefile passes the knobs the paper's version uses — `ROW_H=0.26 FS=8 FS_SM=6.5
LEG_NCOL=3 SHOW_HANDOVER=0`, pair `A`, width `3.33`. The script's own defaults are sized for
a full-width figure. It also takes `BAR_H`, `MIN_TRACK`, `INSIDE_MIN_H`, `EXTRA_H`,
`BAR_LABELS`, `BAR_UNIT`, `TITLE_A`, `TITLE_B`, `PER_BLOCK_X` and `SHOW_OVERLAP`.

## The data

`data/` is **not in git** — it is ~150 MB of raw logs. It sits here so that `make` can redraw
the figure from scratch, and a clone without it still compiles the paper from the committed
PDF. The source bundle is `deep_artifact`. Each run has the same shape as a crash-suite run
(`lincheck/run.log`, the per-host redis logs, `exp/`), described in
`../crash_recovery/README.md`.

**Timestamps.** Redis log timestamps are the CloudLab hosts' local time (UTC−7) with no
offset, and `recovery_breakdown.py` parses them as *local* time, which is why the Makefile
exports `TZ=Etc/GMT+7`. In another timezone the figure is displaced by the difference, which
does not look like an error — it looks like a nearly empty figure spanning tens of thousands
of seconds.

## The type

The scripts render in Computer Modern when `CMU_DIR` is set. This paper is USENIX, which is
Times (`mathptmx`), so the Makefile unexports it and the scripts fall back to Times New
Roman / STIX, matching the body type.
