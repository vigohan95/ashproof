# Ashproof receipt `b04aaf87094f`

- **Status:** KILLED
- **Created:** 2026-11-06T09:17:37.010493+00:00
- **Task:** Run one python step that prints a heartbeat line every second for 100 seconds, flushing each line, and then writes done.txt containing the word done.
- **Task sha256:** `15fb68e706e11a6c4e85e737c76f3e27415386e3ea4733df2f428434c9b9fb1e`
- **Receipt sha256:** `e871adbc9269d6976fed794697e59a02e64d12047d7885ce06fa953d185c7fca`
- **Receipt integrity:** OK
- **Signed:** Ed25519, key `ee7704217a7ac13d`, at 2026-11-06T09:17:37.012162+00:00

## What was refused

Nothing was refused.

## Blast radius

| Sandbox | Provider | Instance | Created | Destroyed | Proof | Inner layer | Egress |
|---|---|---|---|---|---|---|---|
| primary | vultr | `cff8141d-e372-4199-b62b-9ff9b39b28ee` | 2026-11-06T09:15:45+00:00 | 2026-11-06T09:17:37+00:00 | GET /v2/instances/{id} -> 404 | gvisor runsc --platform=systrap | default-deny |
| verifier | vultr | `d7072342-2e3c-41ce-b78c-cb2ce2282313` | 2026-11-06T09:15:46+00:00 | 2026-11-06T09:17:36+00:00 | GET /v2/instances/{id} -> 404 | gvisor runsc --platform=systrap | default-deny |

All VMs destroyed: **yes**

## Plan

Single Python step printing a flushed heartbeat line every second for 100 seconds, then writing done.txt.  
Planner model: `glm-5.3`; est. cost $0.0200; required domains: none

## Steps

| Step | Kind | Exit | Duration | stdout sha256 | Output files | Executor |
|---|---|---|---|---|---|---|
| 1 Heartbeat loop and done.txt | python | 1 | 0.12s | `f352438c0258` | - | gvisor-systrap |

## Verification

- **Verdict:** FAILED (model: ``)
- **Independent re-run:** not performed; hashes identical: None

## Egress

Policy: default-deny. Allowed domains: none.  
Attempts: 0 (denied 0, allowed 0)

## Secret hygiene

Scan not performed.

## Cost

- **Total:** $0.0199 (VM $0.0179, tokens $0.0020); budget $0.25 -> within
  - planner: $0.00109
  - planner.repair: $0.00096
  - VM verifier vhp-1c-1gb-amd: $0.00893
  - VM primary vhp-1c-1gb-amd: $0.00893

## Audit chain

23 events, head `989c93cde4907d1da7bbc2b8de275b347919b0ff587bd11b510253c4b85a8d04`, verification: OK

| # | Time | Event | Hash |
|---|---|---|---|
| 0 | 2026-11-06T09:15:43.823743+00:00 | task.received | `e2b37af528a1bd47` |
| 1 | 2026-11-06T09:15:43.825223+00:00 | task.planning | `8fa96366c51c415b` |
| 2 | 2026-11-06T09:15:45.316566+00:00 | cost.tokens | `18534d1bd1e54390` |
| 3 | 2026-11-06T09:15:45.316712+00:00 | plan.created | `a8c3c10d9c9cbdf4` |
| 4 | 2026-11-06T09:15:45.316836+00:00 | budget.preflight | `bd03f2b23a6ea09e` |
| 5 | 2026-11-06T09:15:45.316918+00:00 | task.provisioning | `becb49230ab24195` |
| 6 | 2026-11-06T09:15:45.321557+00:00 | task.provisioning | `0b6e5079bf77b571` |
| 7 | 2026-11-06T09:16:06.858402+00:00 | vm.created | `76d7919cffa0d4db` |
| 8 | 2026-11-06T09:16:17.445263+00:00 | vm.created | `c41b69d2a77915a1` |
| 9 | 2026-11-06T09:17:14.943801+00:00 | vm.runner_ready | `471f5db15c156a4f` |
| 10 | 2026-11-06T09:17:25.695793+00:00 | vm.runner_ready | `fb040cbf362c9696` |
| 11 | 2026-11-06T09:17:25.695920+00:00 | task.running | `7deb7ce4118c92ea` |
| 12 | 2026-11-06T09:17:25.824227+00:00 | step.finished | `a8926f53c569dcbc` |
| 13 | 2026-11-06T09:17:26.802785+00:00 | cost.tokens | `221bb7c05175042a` |
| 14 | 2026-11-06T09:17:26.802904+00:00 | step.repaired | `f8c0ad0c9778b811` |
| 15 | 2026-11-06T09:17:36.267162+00:00 | kill.requested | `1159d88b2b3df155` |
| 16 | 2026-11-06T09:17:36.275299+00:00 | kill.tokens_revoked | `7449454def13a515` |
| 17 | 2026-11-06T09:17:36.275422+00:00 | task.destroying | `642d330e78cbf06a` |
| 18 | 2026-11-06T09:17:36.277547+00:00 | kill.tokens_revoked | `f42b4c48857f726d` |
| 19 | 2026-11-06T09:17:36.277690+00:00 | task.destroying | `3973c9163712a108` |
| 20 | 2026-11-06T09:17:36.882393+00:00 | vm.destroyed | `d6dc50c2cc102cee` |
| 21 | 2026-11-06T09:17:37.009788+00:00 | vm.destroyed | `35b98a7fe917cc41` |
| 22 | 2026-11-06T09:17:37.010220+00:00 | task.killed | `989c93cde4907d1d` |
