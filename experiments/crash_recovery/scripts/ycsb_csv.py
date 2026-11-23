#!/usr/bin/env python3
"""The YCSB numbers behind the grid figure, as CSV.

Parses exactly what plot_scaleout_ycsb.py parses -- the per-client YCSB status lines, one per
second -- so the CSV and the figure cannot disagree. Three files are written:

  ycsb_per_second.csv   one row per scenario-second: summed throughput and the mean latencies
  ycsb_per_client.csv   the same seconds split by client, before the summing
  runs.csv              one row per scenario: migration window, crash time, totals

usage: ycsb_csv.py <data-dir> <out-dir> [scenario ...]
  <data-dir>  the artifact's data/, with <SC>/exp and <SC>/lincheck in it
"""
import sys, os, re, csv, datetime, glob, math

SCEN = ["HEALTHY", "S1", "S2", "S5", "S10", "S11", "S12"]
data, out = sys.argv[1], sys.argv[2]
if len(sys.argv) > 3:
    SCEN = sys.argv[3:]
os.makedirs(out, exist_ok=True)

FMT = "%Y-%m-%d %H:%M:%S"
pat = re.compile(r'^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d):\d+ \d+ sec: \d+ operations; ([\d.]+) current ops/sec')
lat_pat = {op: re.compile(r'\[%s AverageLatency\(us\)=([\d.]+)\]' % op)
           for op in ("READ", "UPDATE", "READ-FAILED")}


def load(run):
    """(t0, [(client, {t: ops/s}, {op: {t: [(ms, ops/s)]}})]) -- one entry per YCSB client."""
    per = []
    for f in sorted(glob.glob(os.path.join(run, "ycsb", "*", "tmp", "ycsb_output_ycsb*"))):
        if "load" in os.path.basename(f):
            continue
        d, lats = {}, {op: {} for op in lat_pat}
        for l in open(f, errors="ignore"):
            m = pat.match(l)
            if not m:
                continue
            t = datetime.datetime.strptime(m.group(1), FMT)
            d[t] = float(m.group(2))
            for op, p in lat_pat.items():
                lm = p.search(l)
                if lm:
                    lats[op].setdefault(t, []).append((float(lm.group(1)) / 1000, d[t]))
        # the client's name is the directory two levels up: .../ycsb/<client>/tmp/<file>
        per.append((os.path.basename(os.path.dirname(os.path.dirname(f))), d, lats))
    return per


def mean(v):
    """Mean latency across clients, weighted by each client's throughput that second."""
    w = sum(k for _, k in v)
    return (sum(a * k for a, k in v) / w) if w else None


def window(run):
    """(start, end, seconds) of the migration, from exp/migration_window.txt."""
    p = os.path.join(run, "migration_window.txt")
    if not os.path.exists(p):
        return None, None, None
    s = open(p, errors="ignore").read()
    m = re.search(r"FULL.*\[(\d\d:\d\d:\d\d)\.\d+ -> (\d\d:\d\d:\d\d)\.\d+\]", s)
    md = re.search(r"FULL[^\n]*?([\d.]+)s", s)
    return (m.group(1) if m else None), (m.group(2) if m else None), (float(md.group(1)) if md else None)


def near(t0, hms, off_h=0):
    """An HH:MM:SS on the run's day, as seconds from t0."""
    h, mi, se = map(int, hms.split(":"))
    t = t0.replace(hour=h, minute=mi, second=se) + datetime.timedelta(hours=off_h)
    while t < t0 - datetime.timedelta(hours=12):
        t += datetime.timedelta(days=1)
    while t > t0 + datetime.timedelta(hours=12):
        t -= datetime.timedelta(days=1)
    return (t - t0).total_seconds()


tz = round((datetime.datetime.utcnow() - datetime.datetime.now()).total_seconds() / 3600)
f_sec = csv.writer(open(os.path.join(out, "ycsb_per_second.csv"), "w", newline=""))
f_cli = csv.writer(open(os.path.join(out, "ycsb_per_client.csv"), "w", newline=""))
f_run = csv.writer(open(os.path.join(out, "runs.csv"), "w", newline=""))
f_sec.writerow(["scenario", "t_s", "wall_clock_utc", "throughput_kops_s", "clients_reporting",
                "read_mean_ms", "update_mean_ms", "read_failed_mean_ms", "in_migration_window"])
f_cli.writerow(["scenario", "t_s", "client", "throughput_ops_s",
                "read_mean_ms", "update_mean_ms", "read_failed_mean_ms"])
f_run.writerow(["scenario", "ycsb_clients", "t0_utc", "migration_start_s", "migration_end_s",
                "migration_duration_s", "crash_s", "seconds_logged", "peak_kops_s",
                "min_kops_s_after_crash"])

for sc in SCEN:
    run = os.path.join(data, sc, "exp")
    if not os.path.isdir(run):
        sys.stderr.write("skip %s: no %s\n" % (sc, run))
        continue
    per = load(run)
    if not per:
        sys.stderr.write("skip %s: no YCSB output\n" % sc)
        continue
    ts = sorted(set().union(*[set(d) for _, d, _ in per]))
    # the time origin of the figures: the first second any client completed an operation
    t0 = next(t for t in ts if any(d.get(t, 0) > 0 for _, d, _ in per))
    ts = [t for t in ts if t >= t0]

    w0h, w1h, wdur = window(run)
    w0 = near(t0, w0h, tz) if w0h else None      # redis logs are local time; YCSB is UTC
    w1 = near(t0, w1h, tz) if w1h else None
    crash = None
    rl = os.path.join(data, sc, "lincheck", "run.log")
    if os.path.exists(rl):
        k = re.findall(r"\[crash_inject (\d\d:\d\d:\d\d)\] KILLED", open(rl, errors="ignore").read())
        if k:
            crash = near(t0, k[0])               # the injector logs UTC, like YCSB

    tot = []
    for t in ts:
        rel = (t - t0).total_seconds()
        ops = sum(d.get(t, 0) for _, d, _ in per)
        tot.append(ops / 1000)
        n = sum(1 for _, d, _ in per if t in d)
        row = [sc, "%.0f" % rel, t.strftime("%Y-%m-%d %H:%M:%S"), "%.3f" % (ops / 1000), n]
        for op in ("READ", "UPDATE", "READ-FAILED"):
            v = [x for _, _, lats in per for x in lats[op].get(t, [])]
            m = mean(v)
            row.append("" if m is None else "%.3f" % m)
        row.append(1 if (w0 is not None and w0 <= rel <= w1) else 0)
        f_sec.writerow(row)
        for name, d, lats in per:
            if t not in d:
                continue
            r = [sc, "%.0f" % rel, name, "%.1f" % d[t]]
            for op in ("READ", "UPDATE", "READ-FAILED"):
                v = lats[op].get(t, [])
                r.append("%.3f" % v[0][0] if v else "")
            f_cli.writerow(r)

    after = [v for t, v in zip(ts, tot) if crash is not None and (t - t0).total_seconds() >= crash]
    f_run.writerow([sc, len(per), t0.strftime("%Y-%m-%d %H:%M:%S"),
                    "" if w0 is None else "%.2f" % w0, "" if w1 is None else "%.2f" % w1,
                    "" if wdur is None else "%.2f" % wdur,
                    "" if crash is None else "%.2f" % crash,
                    len(ts), "%.3f" % max(tot), "%.3f" % min(after) if after else ""])
    print("%-8s %d clients, %d seconds" % (sc, len(per), len(ts)))
print("wrote ycsb_per_second.csv, ycsb_per_client.csv, runs.csv in %s" % out)
