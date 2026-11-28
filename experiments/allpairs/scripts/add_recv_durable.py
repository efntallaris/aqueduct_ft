#!/usr/bin/env python3
"""Add the `recv` and `durable` fields that paper_3vs5_breakdown.py needs and
recovery_breakdown.py does not write.

REPRODUCE.md says the snippet lives in experiments/2026-11-18_deep_pipeline/ -- it does not;
that folder has only run.sh, run_ib.sh, validate.sh and two plotting scripts, none of which
mention these fields. This reconstructs it from the committed bd/*.json, whose format is:

    recv     {host: [t per round]}   chain FOLLOWERS only; the leader receives from the
                                     donor, not over the chain, so it has no CHAIN-FORWARDED
    durable  [t per round]           per-group MGN_RECP_DURABLE on the recipient

Times are seconds from the migration-window start (the COLD-EXCLUDED left edge), which is
what reproduces the committed numbers: against P3_r1 this parser gives redis4 0.632 vs the
stored 0.633 and redis5 1.174 vs 1.175.

Receipt line (count ONE per round, the one carrying n_slots):
    RDMA CHAIN-FORWARDED: sess=<id> length=<n> n_slots=<n> tail=<0|1>
there is also a bare "sess=<id> tail ack_enqueued=1" line on the tail replica -- not a
receipt, and counting it doubles the tail's round count.

Commit line, on the recipient (NOT the donor's DONE; REPRODUCE.md section 2 explains they
differ by up to 0.40 s when rounds pipeline):
    <raft> MGN_RECP_DURABLE applied: payload="sess=<n> slots=<lo>-<hi> ..."

Usage: add_recv_durable.py <run_dir> <group> <json>   e.g. data/S3_r1 sg4 bd/S3_r1.json
       add_recv_durable.py <run_dir> <group> --print   parse only, write nothing
"""
import sys, os, re, json, glob, datetime

RECV_RE = re.compile(r"RDMA CHAIN-FORWARDED: sess=(\d+) length=\d+ n_slots=\d+ tail=([01])")
DUR_RE  = re.compile(r'MGN_RECP_DURABLE applied: payload="sess=\d+ slots=(\d+)-(\d+)')
TS_RE   = re.compile(r"(\d{2}) (\w{3}) (\d{4}) (\d{2}):(\d{2}):(\d{2})\.(\d{3})")
MONTHS  = {m: i + 1 for i, m in enumerate(
    "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split())}


def stamp(line):
    m = TS_RE.search(line)
    if not m:
        return None
    d, mon, y, H, M, S, ms = m.groups()
    return datetime.datetime(int(y), MONTHS[mon], int(d), int(H), int(M), int(S),
                             int(ms) * 1000)


def window_start(run):
    """Left edge of the COLD-EXCLUDED migration window, as a datetime."""
    f = os.path.join(run, "exp", "migration_window.txt")
    for line in open(f, errors="replace"):
        if "COLD-EXCLUDED" in line:
            m = re.search(r"\[(\d{2}):(\d{2}):(\d{2})\.(\d{3})", line)
            if m:
                return [int(x) for x in m.groups()]        # h, m, s, ms
    raise SystemExit("no COLD-EXCLUDED line in %s" % f)


def logs_for(run, group):
    """{host: logfile} for every replica of `group` in this run."""
    out = {}
    for f in glob.glob(os.path.join(run, "exp", "logs", "*", "tmp", "redis_logs", "*_%s.log" % group)):
        out[os.path.basename(f).split("_")[0]] = f
    return out


def main():
    run, group, dest = sys.argv[1], sys.argv[2], sys.argv[3]
    h, m, s, ms = window_start(run)
    files = logs_for(run, group)
    if not files:
        raise SystemExit("no %s logs under %s" % (group, run))

    # t0 on the same date as the first log line we can stamp
    any_ts = next((stamp(l) for f in files.values() for l in open(f, errors="replace")
                   if stamp(l)), None)
    t0 = any_ts.replace(hour=h, minute=m, second=s, microsecond=ms * 1000)
    rel = lambda t: round((t - t0).total_seconds(), 3)

    # AqRaft 2026-11-20 FIX: ignore lines left over from EARLIER runs.
    #
    # logs_for() globs *_<group>.log across every host, and a host keeps that file
    # between runs. topology_spread5.yml puts sg4's F3/F4 on redis8/redis9, so after
    # any 5-replica run those two hosts hold a redis8_sg4.log / redis9_sg4.log that a
    # later 3-REPLICA run still matches -- where they are not in sg4's chain at all.
    # Their stale CHAIN-FORWARDED lines then land in `recv` at huge negative offsets
    # (measured 2026-11-20: redis8 at -24053 s and -4922 s against a real range of
    # 0.6..3.2 s), and the renderer folds them into the x-extent: paper_3vs5_breakdown
    # asked matplotlib for a 20,677,791-pixel-wide canvas and died. Keep only what
    # falls inside this run's own window.
    WINDOW = (-300.0, 3600.0)
    in_window = lambda x: WINDOW[0] <= x <= WINDOW[1]

    recv, durable_by_host = {}, {}
    dropped = {}
    for host, f in sorted(files.items()):
        ts, dur, drop = [], [], 0
        for line in open(f, errors="replace"):
            if RECV_RE.search(line):
                t = stamp(line)
                if t:
                    v = rel(t)
                    ts.append(v) if in_window(v) else None
                    drop += 0 if in_window(v) else 1
            elif DUR_RE.search(line):
                t = stamp(line)
                if t:
                    v = rel(t)
                    dur.append(v) if in_window(v) else None
                    drop += 0 if in_window(v) else 1
        if drop:
            dropped[host] = drop
        if ts:
            recv[host] = ts
        if dur:
            durable_by_host[host] = dur
    if dropped:
        sys.stderr.write("add_recv_durable: ignored out-of-window lines from a previous run: %s\n"
                         % ", ".join("%s=%d" % kv for kv in sorted(dropped.items())))

    # The group's commit times: every replica applies the entry, so take the earliest
    # per round across replicas -- that is when the group committed, not when a given
    # follower got round to applying it.
    durable = []
    if durable_by_host:
        n = min(len(v) for v in durable_by_host.values())
        durable = [round(min(v[i] for v in durable_by_host.values()), 3) for i in range(n)]

    print("%s %s  t0=%02d:%02d:%02d.%03d" % (run, group, h, m, s, ms))
    for host in sorted(recv):
        print("   recv %-8s %s" % (host, recv[host]))
    print("   durable  %s" % durable)

    if dest == "--print":
        return
    with open(dest) as fh:
        d = json.load(fh)
    d["recv"], d["durable"] = recv, durable
    with open(dest, "w") as fh:
        json.dump(d, fh)
    print("   -> wrote recv/durable into %s" % dest)


if __name__ == "__main__":
    main()
