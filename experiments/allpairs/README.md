# All-pairs migration breakdown — figure, data, and how to rebuild it

`pairwise_all5.{png,pdf,csv}` and `deep_all5.{png,pdf,csv}`: every round of every pair of a
3 -> 6 scale-out on one time axis, 3-node chains in the upper panel and 5-node chains in the
lower one.

## The CSV

One row per rectangle the figure draws, written by the same pass that draws it, so the table
and the picture cannot disagree. 121 rows each = 96 spans (2 panels x 3 pairs x 4 rounds x
4 lanes) + 24 round-durable instants + header.

| column | |
|---|---|
| `panel` | which of the two panels (the figure's own title) |
| `run_tag` | the run it came from: `S3_r2`, `A5_r1`, `D3_r2`, `E5_r1` |
| `pair` | A = sg1->sg4, B = sg2->sg5, C = sg3->sg6 |
| `group` | the recipient group |
| `group_nodes` | its width, 3 or 5 |
| `round` | 1..4 (ROUNDS=4, ~682 slots each) |
| `lane` | Donor to recipient transfer / Index update on leader / Chain replication / Async chain replication, or `round durable` |
| `start_s`, `end_s` | seconds from the COLD-EXCLUDED migration start |
| `duration_s` | `end_s - start_s`; blank on a `round durable` row, where only `start_s` is meaningful |

`Chain replication` is the leader's hop up to the MAJORITY replica and `Async chain
replication` is majority -> tail. Both are rebuilt from the per-replica receipts rather than
taken from the json's own `repl`/`async` fields, which assume majority = leader + F1 and so
are only right at n=3. A 2f+1 group commits once f followers hold the batch.

## Rebuilding

    ./scripts/build_breakdown_all.sh                 # run data -> bd/<tag>_<group>.json
    CMU_DIR=<path to the cmu ttfs> \
    TITLE_A="3 replicas" \
    TITLE_B="5 replicas" \
      python3 -I scripts/fig_allpairs.py figs/allpairs/pairwise_all5.png S3_r2 A5_r1 6.9

`fig_allpairs.py <out> <tagA> <tagB> [width_in]` writes `.pdf`, `.svg`, `.png` and `.csv`.
`TITLE_A`/`TITLE_B` set the panel titles; omit `CMU_DIR` for DejaVu instead of Computer
Modern. It reads `bd/<tag>_<group>.json` for all three groups.

The json chain, which `build_breakdown_all.sh` drives:

    recovery_breakdown.py  HEALTHY <run>/lincheck <run>/exp out.png   -> bd/<tag>.json
    add_recv_durable.py    <run> <group> bd/<tag>_<group>.json        -> adds recv/durable

`recovery_breakdown.py` does not write `recv`/`durable`; `add_recv_durable.py` parses them
out of the node logs (`RDMA CHAIN-FORWARDED` receipts and `MGN_RECP_DURABLE`). One json per
group is needed because those two fields are per group.

Why a separate generator at all: `paper_3vs5_breakdown.py` takes the pair as argv[4] and
filters to it, so it can only ever draw 4 of the 12 rounds.

## tx_overlap.py

    python3 -I scripts/tx_overlap.py <tag> <topology.yml>

Checks whether any machine transmits (or receives) two migration transfers at once, from
the measured intervals rather than from the schedule model — which matters because
`check_disjoint.py` only models the pairwise schedule. Result on these runs: 0 overlaps in
every pairwise run, 8-16 in the deep ones, and every one of those is the same pair's next
round entering a hop the previous round has not drained. Zero are two different pairs
colliding, i.e. none is a placement fault.
