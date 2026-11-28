#!/usr/bin/env python3
"""Does any machine transmit (or receive) two migration transfers at once?

usage: tx_overlap.py <tag> <topology.yml>      e.g. tx_overlap.py S5_r3 topology_spread5.yml

check_disjoint.py answers this from the SCHEDULE MODEL, and only for --mode pairwise; its
own header says deep holds up to --depth rounds of one pair in flight, a wider window than
it models. This answers it from the MEASURED timings instead, so it covers deep too.

Every transfer is store-and-forward, so each hop occupies a real interval:
    donor copy      TX donor leader     [copy[0], copy[1]]
    hop 1           TX recipient leader [repl[0], recv[F1]]
    hop k >= 2      TX F_{k-1}          [recv[F_{k-1}], recv[F_k]]
Intervals are gathered per host over ALL pairs and rounds, then checked pairwise. Full
duplex, so send and receive at once on one NIC is fine and TX/RX are checked separately.
"""
import sys, os, json, yaml, itertools, collections

tag, topo = sys.argv[1], sys.argv[2]
HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
T = yaml.safe_load(open("/users/entall/rd/ansible/experiments/custom_scaleout_3to6/" + topo))
G = {g["id"]: g for g in T["redisraft_shardgroups"]}
PAIR = {"sg4": "A", "sg5": "B", "sg6": "C"}
DONOR = {"sg4": "sg1", "sg5": "sg2", "sg6": "sg3"}

tx = collections.defaultdict(list)     # host -> [(a, b, what)]
rx = collections.defaultdict(list)
for grp, pair in PAIR.items():
    path = os.path.join(HERE, "bd", "%s_%s.json" % (tag, grp))
    if not os.path.exists(path):
        print("  (no %s)" % path); continue
    d = json.load(open(path))
    rs = [r for r in d["rounds"] if r["pair"] == pair]
    chain = [n["host"] for n in sorted(G[grp]["nodes"], key=lambda n: n["raft_id"])]
    donor = [n["host"] for n in G[DONOR[grp]]["nodes"] if n["raft_id"] == 1][0]
    recv = d.get("recv", {})
    for k, r in enumerate(rs):
        if r["copy"]:
            tx[donor].append((r["copy"][0], r["copy"][1], "%s r%d donor->L" % (grp, k + 1)))
            rx[chain[0]].append((r["copy"][0], r["copy"][1], "%s r%d donor->L" % (grp, k + 1)))
        prev_t = r["repl"][0] if r["repl"] else None
        for i in range(1, len(chain)):
            h, src = chain[i], chain[i - 1]
            if h not in recv or k >= len(recv[h]) or prev_t is None:
                break
            t = recv[h][k]
            tx[src].append((prev_t, t, "%s r%d hop%d %s->%s" % (grp, k + 1, i, src, h)))
            rx[h].append((prev_t, t, "%s r%d hop%d %s->%s" % (grp, k + 1, i, src, h)))
            prev_t = t

bad = 0
for name, book in (("TX", tx), ("RX", rx)):
    for h in sorted(book, key=lambda x: int(x[5:])):
        iv = sorted(book[h])
        for (a1, b1, w1), (a2, b2, w2) in itertools.combinations(iv, 2):
            ov = min(b1, b2) - max(a1, a2)
            if ov > 0.02:                       # 20 ms of slack for log timestamp jitter
                bad += 1
                print("  %s CLASH on %-7s %.3f s overlap:  %-28s [%.2f,%.2f]  vs  %-28s [%.2f,%.2f]"
                      % (name, h, ov, w1, a1, b1, w2, a2, b2))
print("  %s: %d overlapping transfer pair(s) on one host" % (tag, bad))
