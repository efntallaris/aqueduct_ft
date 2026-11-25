#!/usr/bin/env python3
"""Slide one series along the time axis, so panels can share a migration start.

Every row keeps its measured values and its distance from every other row: only the
`second` column moves. Nothing is resampled, interpolated or invented, and no value is
touched. The seconds the shift vacates at the start are simply absent -- the run has no
measurement there -- so a panel shifted right begins with empty axis.

Say in the caption that the axis is shifted. After this it is no longer seconds since
the client started.

usage: shift_series.py <in.csv> <out.csv> --by N | --mig-start N --mig-was N
"""
import argparse, csv

ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
ap.add_argument("src")
ap.add_argument("dst")
ap.add_argument("--by", type=int, help="shift every second by this many")
ap.add_argument("--mig-start", type=int, help="put the migration band here")
ap.add_argument("--mig-was", type=int, help="where the band starts now (derived or logged)")
a = ap.parse_args()

if a.by is None:
    if a.mig_start is None or a.mig_was is None:
        raise SystemExit("give --by, or both --mig-start and --mig-was")
    a.by = a.mig_start - a.mig_was

rows = list(csv.DictReader(open(a.src, newline="")))
fields = list(rows[0].keys())
with open(a.dst, "w", newline="") as fh:
    w = csv.DictWriter(fh, fieldnames=fields)
    w.writeheader()
    for r in rows:
        r = dict(r)
        r["second"] = int(float(r["second"])) + a.by
        w.writerow(r)
print("%s -> %s   shift %+ds, %d rows, t=%s..%s"
      % (a.src, a.dst, a.by, len(rows), rows[0]["second"], int(float(rows[-1]["second"])) + a.by))
