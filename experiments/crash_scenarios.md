# Crash scenarios for the evaluation

Each scenario targets one recovery path of the protocol (Section 3.6), so every
recovery rule in the paper is backed by at least one measured run.
Existing runs keep their names (S1-S5, S8). New ones are numbered C1-C16.

Workload for all runs: the same YCSB setup as the run without faults, with the crash
injected by `ansible/crash/crash_inject.sh` at the trigger below.

## 1. Core matrix: crash point x role

| ID | Existing | Crash | Trigger (when to kill) | Recovery path exercised | Expected outcome |
|----|----------|-------|------------------------|-------------------------|------------------|
| C1 | - | Donor leader | after `START(Gi)` commits, before `prepare` is sent | donor recovery, nothing at the recipient yet | `QUERY_STATE` returns `MISSING`, the donor transfers from `prepare` |
| C2 | S2 | Donor leader | during the RDMA writes of `Gi` | partial landing buffers, late RDMA writes | `MISSING` or `TRANSFERRED`. A new transfer uses new buffers and RKeys, and late writes fail |
| C3 | S5 | Donor leader | after `TRANSFER_DURABLE(Gi)` commits, before `DONE(Gi)` | `GI_DONE` from the recipient's log | the donor commits `DONE(Gi)` and no data is sent again |
| C4 | - | Recipient leader | after `prepare` arrives, before `TXN_START(Gi)` commits | prepare is retried | the donor's query times out, the new leader answers `MISSING`, prepare again |
| C5 | S1 | Recipient leader | data landed on the leader only, before any chain step | no replica holds the data | `MISSING`, the donor sends the data again |
| C6 | - | Recipient leader | data on at least one follower, but not on the new leader | fetch from a replica | the new leader fetches from a replica and answers `TRANSFERRED`, no retransfer from the donor |
| C7 | - | Recipient leader | after `TRANSFER_DURABLE(Gi)` commits, before `GI_DONE` is sent | `QUERY_STATE` alone completes the group | the donor learns `GI_DONE` from its query and commits `DONE(Gi)` |
| C8 | S4 | Recipient follower | in the middle of the replication chain | chain repair | the leader removes it from the chain, it catches up later, `TRANSFER_DURABLE` still commits |
| C9 | S3 | Donor follower | any time during the migration | none (control) | no visible effect |

## 2. Compound and adversarial crashes

| ID | Existing | Crash | Trigger | What it shows | Expected outcome |
|----|----------|-------|---------|---------------|------------------|
| C10 | S8 | Both leaders | at the same time, during the transfer | worst-case recovery time | both groups elect leaders, the migration completes |
| C11 | - | Recipient leader, twice | crash the new leader again during its own recovery | recovery only moves forward | no rollback, the migration completes after the second election |
| C12 | - | Recipient replicas holding `Gi`, one after another | each crash after the previous replica rejoined | rejoin rule (a replica catches up before it counts toward the majority) | no data loss, `TRANSFER_DURABLE` holds a live holder at all times |
| C13 | - | Recipient leader, crash and restart of the same node | during its own transfer | late RDMA writes into reused memory | late writes fail against the new RKeys, data is intact |

## 3. Failures that are not crashes

| ID | Failure | Trigger | What it shows | Expected outcome |
|----|---------|---------|---------------|------------------|
| C14 | Slow recipient follower (CPU throttled or delayed NIC) | during the chain | chain repair on a timeout | the slow node is removed from the chain and receives the data later. Report the cost of an early removal |
| C15 | Network partition between the two leaders | during the transfer, healed after a few seconds | queries are retried safely | no progress during the partition, completion after it heals, no errors |
| C16 | Very short timeouts | the whole run | timeouts affect only liveness | extra queries and transfers, no correctness violation |

## 4. Metrics for every run

| Metric | Source |
|--------|--------|
| Unavailability of the migrating slots (s) | YCSB per-request errors for keys of `Gi` |
| Migration time vs. the run without faults (s) | slot ownership polling (`poll_slot_ownership.py`) |
| p99 latency during the migration (ms) | YCSB |
| Bytes sent again by the donor | donor logs (transfers per group) |
| Recovery breakdown (election, plan, chain rebuild) | node logs, as in the S1 timeline |
| Correctness check passed (yes/no) | read-back of acknowledged writes, per-slot digest across replicas |

## 5. Priority if time is short

C2, C5, C6, C7, C8, C10 and C11. Together they exercise every recovery rule at least once.

## 6. Presentation in the paper

- One table with all scenarios as rows and the metrics of Section 4 as columns.
- The S1 (C5) timeline as the detailed example (`experiments/S1_recovery.pdf`).
