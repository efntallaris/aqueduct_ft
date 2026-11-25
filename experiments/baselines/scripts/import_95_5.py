#!/usr/bin/env python3
"""The two measured 95/5 Aqueduct runs, from one combined export, into this schema.

  <src>/ycsb_per_second.csv   NR_95_5  (no replication) -> data/955/aqueduct.csv
                              R3_95_5  (3 replicas)     -> data/955/aqueduct_ft.csv

Both are REAL 90s runs of this paper's store at 95% read / 5% update, measured on the
same testbed in one sitting (2026-11-25 01:18 and 01:24 UTC, per the export's runs.csv).
They are the 95/5 counterpart of the even-split pair that scripts/import_norepl_3rep.py
brings in, and they are what finally lets the 95/5 half of the paper's figure show this
paper's system rather than only the FAST submission's baselines.

Nothing here is projected, scaled or redrawn. The only changes are:

  schema   one row per second per scenario, split into one file per scenario, with the
           columns plot_baselines.py reads. Throughput goes from kops/s to ops/s and the
           latencies from ms to MICROSECONDS, because that is this directory's unit --
           plot_baselines.py divides every latency column by 1000 (see its load()), so
           the FAST CSVs' 29.98 is 0.03 ms of RAMCloud and 4976.0 is 4.98 ms of Redis.

  shift    --mig-start slides a run so its logged migration window begins at that second.
           Both runs log it at 18s, so -m 20 moves both by +2s, which puts them on the
           same migration second as the even-split pair (that one logs 19s and is moved
           +1s). Every value and every row-to-row distance is untouched. SAY IN THE
           CAPTION THAT THE AXIS IS SHIFTED: after this it is not seconds since the
           client started.

  trim     --first/--last drop the partial seconds at each end, which are measurement
           artifacts rather than anything the store did. t_s=0 is a fraction of a second
           of logging (NR reports 3.8 kops/s against a 218 kops/s steady state) and
           t_s=88 is the same at the other end (NR 187.0, R3 77.0 against ~405 and ~360).
           --first 2 also clears NR's one-second ramp at t_s=1. This is the same rule
           import_norepl_3rep.py applies to the even-split pair.

latency_99_9 is left EMPTY, as it is for the even-split pair: these clients ran with
YCSB's timeseries measurement, which reports a per-second mean and no percentile. The
export does carry percentiles in percentiles_phases_95_5.csv, but those are per-PHASE
aggregates (whole / before / during / after), not a per-second series, so they cannot
become a line on these panels. Quote them in the text instead.

usage: import_95_5.py <src dir> [-m 20] [-d data/955] [--first 2] [--last 87]
"""
import argparse, csv, os

# export scenario -> this directory's file stem
PAIRS = [("NR_95_5", "aqueduct.csv"), ("R3_95_5", "aqueduct_ft.csv")]
FIELDS = ["second", "entry_id", "current_ops", "latency_median", "latency_99_9",
          "latency_write", "in_migration_window"]


def main(src_dir, out_dir, mig_start, first, last):
    os.makedirs(out_dir, exist_ok=True)
    src = os.path.join(src_dir, "ycsb_per_second.csv")
    allrows = list(csv.DictReader(open(src, newline="")))
    for scenario, out_name in PAIRS:
        rows = [r for r in allrows
                if r["scenario"] == scenario and first <= int(r["t_s"]) <= last]
        if not rows:
            raise SystemExit("no rows for %s in %s" % (scenario, src))
        shift = 0
        if mig_start is not None:
            w = [int(r["t_s"]) for r in allrows
                 if r["scenario"] == scenario and r["in_migration_window"] == "1"]
            if not w:
                raise SystemExit(scenario + ": no migration window to align")
            shift = mig_start - min(w)
        out = os.path.join(out_dir, out_name)
        with open(out, "w", newline="") as fh:
            w_ = csv.DictWriter(fh, fieldnames=FIELDS)
            w_.writeheader()
            for r in rows:
                us = lambda k: ("%.3f" % (float(r[k]) * 1000.0)) if r[k] else ""
                w_.writerow({"second": int(r["t_s"]) + shift, "entry_id": 0,
                             "current_ops": "%.3f" % (float(r["throughput_kops_s"]) * 1000.0),
                             "latency_median": us("read_mean_ms"), "latency_99_9": "",
                             "latency_write": us("update_mean_ms"),
                             "in_migration_window": r["in_migration_window"]})
        k = [float(r["throughput_kops_s"]) for r in rows]
        mig = [int(r["t_s"]) + shift for r in rows if r["in_migration_window"] == "1"]
        print("%-10s -> %-18s %d s, t=%d..%d, shift %+d, mig %d..%d, %.0f -> %.0f kops/s"
              % (scenario, out_name, len(rows), int(rows[0]["t_s"]) + shift,
                 int(rows[-1]["t_s"]) + shift, shift, min(mig), max(mig), k[0], k[-1]))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("src_dir")
    ap.add_argument("-m", "--mig-start", type=int, default=20)
    ap.add_argument("-d", "--out-dir", default="data/955")
    ap.add_argument("--first", type=int, default=2)
    ap.add_argument("--last", type=int, default=87)
    a = ap.parse_args()
    main(a.src_dir, a.out_dir, a.mig_start, a.first, a.last)
