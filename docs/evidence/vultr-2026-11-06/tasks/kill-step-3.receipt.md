# Ashproof receipt `4183c5cfec05`

- **Status:** KILLED
- **Created:** 2026-11-06T06:22:36.056443+00:00
- **Task:** Run one python step that prints a heartbeat line every second for 100 seconds, flushing each line, and then writes done.txt containing the word done.
- **Task sha256:** `15fb68e706e11a6c4e85e737c76f3e27415386e3ea4733df2f428434c9b9fb1e`
- **Receipt sha256:** `a037049cb705e863a525dda581294b847b697942285a6b1a0fdb26e01a912100`
- **Receipt integrity:** OK

## Blast radius

| Sandbox | Provider | Instance | Created | Destroyed | Proof | Inner layer | Egress |
|---|---|---|---|---|---|---|---|
| verifier | vultr | `2ab2957c-9962-4dcf-a298-031845a48162` | 2026-11-06T06:20:45+00:00 | 2026-11-06T06:22:36+00:00 | GET /v2/instances/{id} -> 404 | gvisor runsc --platform=systrap | default-deny |
| primary | vultr | `c87dccde-47ab-4ca0-b6f5-efac146a8a04` | 2026-11-06T06:20:46+00:00 | 2026-11-06T06:22:36+00:00 | GET /v2/instances/{id} -> 404 | gvisor runsc --platform=systrap | default-deny |

All VMs destroyed: **yes**

## Plan

Single Python step printing a flushed heartbeat line every second for 100 seconds, then writing done.txt containing 'done'.  
Planner model: `glm-5.3`; est. cost $0.0200; required domains: none

## Steps

| Step | Kind | Exit | Duration | stdout sha256 | Output files | Executor |
|---|---|---|---|---|---|---|

## Verification

- **Verdict:** FAILED (model: ``)
- **Independent re-run:** not performed; hashes identical: None

## Egress

Policy: default-deny. Allowed domains: none.  
Attempts: 0 (denied 0, allowed 0)

## Secret hygiene

Scan not performed.

## Cost

- **Total:** $0.0173 (VM $0.0160, tokens $0.0013); budget $0.25 -> within
  - planner: $0.00129
  - VM primary vhp-1c-1gb-amd: $0.00800
  - VM verifier vhp-1c-1gb-amd: $0.00800

## Audit chain

20 events, head `f743df061c493cdfee29f7fda6030772ea2c5917a4d8baeda5e2f451f9baa5da`, verification: OK

| # | Time | Event | Hash |
|---|---|---|---|
| 0 | 2026-11-06T06:20:42.648712+00:00 | task.received | `7631de94b49bb5e5` |
| 1 | 2026-11-06T06:20:42.650005+00:00 | task.planning | `126d18ebccb32971` |
| 2 | 2026-11-06T06:20:45.123930+00:00 | cost.tokens | `e44e8990ec7a02c9` |
| 3 | 2026-11-06T06:20:45.124064+00:00 | plan.created | `073fe6b4e2518f9a` |
| 4 | 2026-11-06T06:20:45.124198+00:00 | budget.preflight | `8fb321d59f9ba3b8` |
| 5 | 2026-11-06T06:20:45.124304+00:00 | task.provisioning | `622c8a73371bdda7` |
| 6 | 2026-11-06T06:20:45.128911+00:00 | task.provisioning | `862c994e6c4d0868` |
| 7 | 2026-11-06T06:21:07.602254+00:00 | vm.created | `3f950a357966901d` |
| 8 | 2026-11-06T06:21:19.810173+00:00 | vm.created | `fb43a121df7492dd` |
| 9 | 2026-11-06T06:22:15.873459+00:00 | vm.runner_ready | `c6b567a47211223c` |
| 10 | 2026-11-06T06:22:28.157950+00:00 | vm.runner_ready | `3f77f88d6bc1c4d0` |
| 11 | 2026-11-06T06:22:28.158077+00:00 | task.running | `6aeaeb6cbad661ab` |
| 12 | 2026-11-06T06:22:35.491342+00:00 | kill.requested | `ea23c9123706e160` |
| 13 | 2026-11-06T06:22:35.499012+00:00 | kill.tokens_revoked | `b341cf853ceb9cdc` |
| 14 | 2026-11-06T06:22:35.499148+00:00 | task.destroying | `37401cc7a31ce3b9` |
| 15 | 2026-11-06T06:22:35.501158+00:00 | kill.tokens_revoked | `c30a763161a09a8f` |
| 16 | 2026-11-06T06:22:35.501233+00:00 | task.destroying | `0ac43be87c47637d` |
| 17 | 2026-11-06T06:22:36.037172+00:00 | vm.destroyed | `6dbc6dfd996b7cb8` |
| 18 | 2026-11-06T06:22:36.054188+00:00 | vm.destroyed | `e09fb267c9d77133` |
| 19 | 2026-11-06T06:22:36.056020+00:00 | task.killed | `f743df061c493cdf` |
