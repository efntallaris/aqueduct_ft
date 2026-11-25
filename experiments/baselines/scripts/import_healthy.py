#!/usr/bin/env python3
"""Convert the crash suite's HEALTHY run into this directory's CSV schema.

    python3 scripts/import_healthy.py \\
        ../crash_recovery/derived/ycsb/ycsb_per_second.csv data/955/aqueduct_ft.csv

HEALTHY is the no-fault migration of the fault-tolerant store -- the run behind the
no-fault figure of experiments/crash_recovery. It is the only run in the paper that
exercises the fault-tolerant protocol with no fault injected, which is what makes it the
right panel to set beside the FAST submission's runs.

Two things it does NOT share with them, both of which belong in the caption:

  Testbed. The FAST runs are their own cluster and dataset. This one is 12 CloudLab c6620
  nodes. Absolute heights are therefore not comparable across the row -- the shape of each
  curve against its own flat start is.

  Latency. The FAST runs report a per-second median and a 99.9th percentile. This run
  reports per-second MEANS for reads and updates and NO PERCENTILE AT ALL. The read mean
  therefore goes into the median column, the update mean into latency_write, and the
  percentile column is left empty, which the plotting script reads as "this panel has no
  tail line". There is no percentile to be recovered here by importing differently: the
  source columns are read_mean_ms, update_mean_ms and read_failed_mean_ms, and that is
  all the run records.

The warm-up and the cool-down are dropped: the YCSB clients are starting (3 and 33.9
kops/s against a 158 kops/s steady state on the 90 s run) and stopping, and neither is a
measurement of the store. They are FOUND IN THE DATA rather than hard-coded, so a longer
re-run of the same scenario needs no edit here -- a second is kept once the throughput
first reaches WARM of the run's median, and dropped again at the tail once it falls back
below it. in_migration_window is carried through, so this panel's grey band is the logged
window (19-26 s on the 90 s run) rather than one derived from the throughput trace.
"""

import csv
import os
import sys

SRC, DST = sys.argv[1], sys.argv[2]
SCENARIO = sys.argv[3] if len(sys.argv) > 3 else "HEALTHY"
# a second counts as part of the run once its throughput is within this fraction of the
# run's median. 0.5 is far below any real dip (the deepest in the crash suite is 0.29 of
# the steady state, and this is the no-fault run) and far above a client starting or
# stopping (0.02 and 0.21 of the median on the 90 s run).
WARM = float(os.environ.get("WARM", 0.5))

with open(SRC) as fh:
    rows = [r for r in csv.DictReader(fh)
            if r["scenario"] == SCENARIO and r["read_mean_ms"]]

kops = sorted(float(r["throughput_kops_s"]) for r in rows)
floor = WARM * kops[len(kops) // 2]
first = next(i for i, r in enumerate(rows) if float(r["throughput_kops_s"]) >= floor)
last = len(rows) - 1 - next(i for i, r in enumerate(reversed(rows))
                            if float(r["throughput_kops_s"]) >= floor)
rows = rows[first:last + 1]

with open(DST, "w", newline="") as fh:
    w = csv.writer(fh)
    w.writerow(["second", "entry_id", "current_ops", "latency_median", "latency_99_9",
                "latency_write", "in_migration_window"])
    for r in rows:
        w.writerow([r["t_s"], 0,
                    "%.3f" % (float(r["throughput_kops_s"]) * 1000),   # ops/s
                    "%.3f" % (float(r["read_mean_ms"]) * 1000),        # us, as in the FAST schema
                    "",                                                # no percentile in this run
                    # the update mean, carried as its own series rather than dropped: it
                    # is measured, it is the write side of the same seconds, and the
                    # no-fault figure of experiments/crash_recovery already plots the
                    # read and the write of this run as a pair.
                    "%.3f" % (float(r["update_mean_ms"]) * 1000) if r["update_mean_ms"] else "",
                    r["in_migration_window"]])

win = [int(r["t_s"]) for r in rows if r["in_migration_window"] == "1"]
print("%s: %d seconds (t=%s..%s) -> %s%s"
      % (SCENARIO, len(rows), rows[0]["t_s"], rows[-1]["t_s"], DST,
         (", logged migration %d-%ds" % (min(win), max(win))) if win else ""))
