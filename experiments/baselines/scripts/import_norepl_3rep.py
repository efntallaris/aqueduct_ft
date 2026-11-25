#!/usr/bin/env python3
"""The two measured Aqueduct runs, each from its own per-second CSV, into this schema.

  <src dir>/ycsb_per_second_norepl.csv  NR_NOREPL     -> data/5050/aqueduct.csv
  <src dir>/ycsb_per_second_3rep.csv    R3_3REPLICAS  -> data/5050/aqueduct_ft.csv

Both are the real 90s runs. Nothing here is projected, scaled or redrawn: the only
change is the schema and a shift, --mig-start, that slides a run so its logged
migration window begins at that second (both log it at 19s, so -m 20 moves both by
+1s). Seconds 0-1 are warm-up and 89 is cool-down, dropped by --first/--last.

latency_99_9 is left empty: these clients ran with YCSB's timeseries measurement,
which reports a per-second mean and no percentile.

usage: import_norepl_3rep.py <src dir> [-m 20] [-d data/5050]
"""
import argparse, csv, os

PAIRS = [("ycsb_per_second_norepl.csv", "aqueduct.csv"),
         ("ycsb_per_second_3rep.csv", "aqueduct_ft.csv")]
FIELDS = ["second", "entry_id", "current_ops", "latency_median", "latency_99_9",
          "latency_write", "in_migration_window"]


def main(src_dir, out_dir, mig_start, first, last):
    os.makedirs(out_dir, exist_ok=True)
    for src_name, out_name in PAIRS:
        rows = [r for r in csv.DictReader(open(os.path.join(src_dir, src_name), newline=""))
                if first <= int(r["t_s"]) <= last]
        if not rows:
            raise SystemExit("no rows in " + src_name)
        shift = 0
        if mig_start is not None:
            w = [int(r["t_s"]) for r in rows if r["in_migration_window"] == "1"]
            if not w:
                raise SystemExit(src_name + ": no migration window to align")
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
        print("%-28s -> %-16s %d s, shift %+d, %.0f -> %.0f kops/s"
              % (src_name, out_name, len(rows), shift, k[0], k[-1]))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("src_dir")
    ap.add_argument("-m", "--mig-start", type=int, default=20)
    ap.add_argument("-d", "--out-dir", default="data/5050")
    ap.add_argument("--first", type=int, default=2)
    ap.add_argument("--last", type=int, default=88)
    a = ap.parse_args()
    main(a.src_dir, a.out_dir, a.mig_start, a.first, a.last)
