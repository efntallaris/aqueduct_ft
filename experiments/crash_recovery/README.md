# Crash recovery during a 3 → 6 scale-out

Everything behind the crash-suite figures: the raw logs, the scripts that turn them into
figures, and the figures themselves. Self-contained — nothing here needs the network or
the cluster.

```
Makefile          data/ -> figures/, timestamp-driven
scripts/          the five scripts that do it
data/             the raw logs, one directory per scenario (not in git, see below)
derived/          the phase data the figures are drawn from (JSON + a readable table)
derived/ycsb/     the YCSB throughput and latency numbers, as CSV
figures/          the figures the paper includes
```

Compiling the paper (`make` in the repository root, or any `latexmk` run) redraws a figure
whose logs or script changed and leaves the rest alone. `make -C experiments/crash_recovery force`
rebuilds everything from the logs up.

## The experiment

Three shard groups split into six while YCSB keeps running, with the slot ranges moved over
RDMA. Migration is deep-pipelined: the donor dispatches pair-major with depth 3, so several
rounds are in flight at once. A fault is injected mid-migration and the run must still
finish, still pass the linearizability check, and still pass the postchecks. All seven runs
did — `data/summary.txt` records 200 keys linearizable, 0 violating, 0 lost writes, and
`migration/crashes/replicas/donors/bulk` all PASS for every scenario.

| | scenario |
|---|---|
| HEALTHY | no fault |
| S1 | recipient leader crash |
| S2 | donor leader crash |
| S5 | both leaders crash |
| S10 | no majority — recipient leader crashes, the round is only on it |
| S11 | majority — recipient leader crashes after `MGN_RECP_DURABLE` |
| S12 | majority — recipient leader crashes, the round is on F1 but not F2 |

Each run: 3 donor groups (`sg1`–`sg3`, hosts `redis0`–`redis2` and their replicas) handing
2 730 slots each to 3 recipient groups (`sg4`–`sg6`), 3 replicas per group, one 2 MiB block
per slot. The figures follow pair A (`sg1` → `sg4`), four rounds of 682 slots. Testbed:
CloudLab, 12 c6620 nodes (10 store, 2 YCSB), RDMA over 100 GbE (Intel E810-C).

## The figures

| file | |
|---|---|
| `figures/<SC>.pdf` | one per scenario, one column wide: the phase breakdown of pair A with its own lane names and axis titles. The paper uses it for the no-fault baseline |
| `figures/grid/<SC>.pdf` | a panel of the six-scenario figure, 2.21 in tall: no arrows and no axis titles, since the figure states those once |
| `figures/grid7.pdf` | 7.00 × 3.80 in: per-second YCSB throughput and latency for all seven, migration window shaded, crash marked |

Neither breakdown variant carries the YCSB throughput panel or the per-replica
`Replica index update` row (`SHOW_IDXREP=1` brings that row back). The paper shows throughput
once, in `grid7.pdf`, rather than once per scenario. `make SHOW_YCSB=1 force` brings it back.

The grid panels are built to sit three to a row across the 7.00 in text width. Only the
panels in `GRID_LEFT` carry the lane names, in a `GRID_LEFTIN` gutter, and they are rendered
wider by exactly that gutter, so every panel ends up with the same 1.93 in of plot area and
the same seconds per inch. `GRID_XMIN`/`GRID_XMAX` pin one time window on all of them —
without it each run picks its own from its own events, the panels end up on different scales,
and a bar the window clips loses the duration label that no longer fits inside it.

`paper_recovery.py` takes a few knobs beyond the bundle's: `XLABEL`, `YLABEL` and `ROW_LABELS`
drop the axis titles and the lane names, `LEFT_IN` sets the label gutter, `XMIN`/`XMAX` pin the
time window, and `CUT_MS`/`CUT_MEW` size the red cross that marks a cut phase. Every bar in
every lane carries the number of its round over its duration, which is what lets a round be
followed down the lanes now that the arrows are off.

Figures are drawn at their final size with 7–9 pt type that is 7–9 pt on paper. Include them
with `\includegraphics{...}` and no `width=`. Rescaling throws the type sizes off.

### Reading a phase figure

Time is seconds from the crash (from the migration start in HEALTHY) and the red dashed line
is the crash. One row per phase of a round, one grey per round, so a round can be followed
down the rows:

- **Donor** — the donor sending the round. **Recipient (L) transfer** — the recipient leader
  receiving it. The same RDMA writes, one row per side.
- **Index update** — the recipient leader indexing the round's keys.
- **Chain replication** — leader → F1, the hop that makes the round durable on a majority.
- **Async chain replication** — F1 → F2, the rest of the chain after the majority hop.
- **Recipient** — the recipient group without a leader, and the recovery decision.

A red ✗ is a phase the crash cut mid-flight. A phase that finished before the crash carries
its duration like any other.

**An empty async lane after the crash is not missing data.** The crash killed one replica of
the recipient group, so when the chain is re-established the dead node is dropped, the group
is down to one live follower, and the majority hop already reaches it (`CHAIN-WIRE: … pos=1/1
… tail=1` in the recipient leader's log). There is no second hop left to draw. This is why
S1, S5, S10, S11 and S12 have an empty lane after the crash and HEALTHY and S2 do not.

### The Gb/s numbers are measured

`BLOCK_MIB` is the real 2 MiB block, so the volumes and rates are measured rather than
rescaled: 2 730 slots x 3 groups x 2 MiB = 17.2 GB, moved in 7.09 s, which is 19.4 Gb/s on a
100 GbE link (19% of it). An earlier default of `9.700638` rescaled the volumes to relabel the
runs, and nothing in the paper uses that any more.

The avg-latency lines break at the crash second in S2, S5, S11 and S12 because YCSB completed
zero operations in that second, so there is no mean to plot. The faint grey dashed segment
bridges the gap — it marks that the series continues, it is not a measurement.

## The data

`data/` is **not in git** — it is ~520 MB of raw logs. It sits here so that `make` can redraw
every figure from scratch, and a clone without it still compiles the paper from the committed
PDFs. The source bundle is `deep_artifact`.

`data/<SCENARIO>/` per run:

| path | what it is | read by |
|---|---|---|
| `lincheck/run.log` | the harness log: kill times, client start | all |
| `lincheck/logs/redis*/*.log` | per-host redis logs, trimmed to the run | `recovery_breakdown.py` |
| `lincheck/history.jsonl` | every linearizability-client operation (invoke/return ns, status) | the p99 series |
| `lincheck/lincheck.txt`, `postcheck.txt` | the verdicts for this run | — |
| `exp/migration_window.txt` | first `TXN_START` → last `TXN_DONE` | the grid titles |
| `exp/ycsb/*/tmp/ycsb_output_ycsb*` | per-client YCSB status lines (1 s timeseries) | throughput, avg latency |
| `exp/logs/*/tmp/redis_logs/*_sg*.log` | the full redis logs | `add_recv_durable.py` |

`data/lincheck_runs/` holds the same `lincheck/` directories under the names
`<SC>_qyes_<YYYYmmdd>_<HHMMSS>`, which is how `plot_scaleout_ycsb.py` matches a lincheck run
to a YCSB run (by start time, within 15 minutes).

**Timestamps.** Names in `lincheck_runs/` and in `history.jsonl` are UTC. Redis log
timestamps are the hosts' local time (UTC−7) with no offset, and `recovery_breakdown.py`
parses them as *local* time — which is why the Makefile exports `TZ=Etc/GMT+7`. Run the
scripts in another timezone and the YCSB overlay, the recovery rows and the x axis are
displaced by the difference. It does not look like an error. It looks like a nearly empty
figure spanning tens of thousands of seconds.

### The phase data

`derived/F_<SC>.json` is what the figures are actually drawn from, one entry per round:

```
copy    [start, end]   the donor's transfer of the round
idx     [start, end]   the recipient leader's index update
repl    [start, end]   leader -> F1
async   [start, end]   F1 -> F2, or [null, null] if there was no second hop
ok      true if the round committed, false if the crash cut it
reship  true if this is the donor re-sending a round the crash lost
lo      the round's first slot, which gives its number
```

Times are seconds relative to the first kill. `derived/F_<SC>.table.txt` is the same run as a
readable table, and it is also where a failed extraction leaves its traceback.

### The YCSB numbers as CSV

`derived/ycsb/` holds the numbers behind the grid figure, parsed from the same YCSB status
lines by the same code, so the two cannot disagree. `ycsb_per_second.csv` is one row per
scenario-second, `ycsb_per_client.csv` the same seconds before the clients are summed, and
`runs.csv` one row per scenario. **A latency cell is empty when no operation of that type
completed in that second.** That is not a parsing failure, it is the outage.

The p99 curves in the grid figure come from a different source — the linearizability client's
per-operation history in `data/<SC>/lincheck/history.jsonl`, which carries an invoke and a
return timestamp (ns) for every operation.

## The type

The scripts render in Computer Modern when `CMU_DIR` points at a directory of Computer Modern
TTFs. This paper is USENIX, which is Times (`mathptmx`), so the Makefile unexports `CMU_DIR`
and the scripts fall back to Times New Roman / STIX. Label placement depends on font metrics
(a label is measured before the script decides whether it fits inside a bar), so the two
families do not produce pixel-identical layouts. Both were checked and neither collides.

## What is not here

The scripts that *ran* the experiments — the Ansible playbooks, the migration driver
(`scaleout_pairs.py`), the YCSB and linearizability harness — need the cluster and are not in
this directory. This is everything needed to go from the recorded logs to the figures.
