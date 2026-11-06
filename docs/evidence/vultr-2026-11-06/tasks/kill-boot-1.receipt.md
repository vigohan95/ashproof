# Ashproof receipt `199ed2ac2a34`

- **Status:** KILLED
- **Created:** 2026-11-06T06:27:09.671031+00:00
- **Task:** Run one python step that prints a heartbeat line every second for 100 seconds, flushing each line, and then writes done.txt containing the word done.
- **Task sha256:** `15fb68e706e11a6c4e85e737c76f3e27415386e3ea4733df2f428434c9b9fb1e`
- **Receipt sha256:** `9f6a0d50c3dd29b9e3fd500f888dfb46dc9275923c4f2e0c77d106f965004fd3`
- **Receipt integrity:** OK

## Blast radius

| Sandbox | Provider | Instance | Created | Destroyed | Proof | Inner layer | Egress |
|---|---|---|---|---|---|---|---|
| primary | vultr | `5ee75724-92d2-4b1d-92ec-5960fd6f35f2` | 2026-11-06T06:26:37+00:00 | 2026-11-06T06:27:09+00:00 | GET /v2/instances/{id} -> 404 | gvisor runsc --platform=systrap | default-deny |
| verifier | vultr | `e60360b5-e739-42a4-90b9-9dfda24d686e` | 2026-11-06T06:26:38+00:00 | 2026-11-06T06:27:09+00:00 | GET /v2/instances/{id} -> 404 | gvisor runsc --platform=systrap | default-deny |

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

- **Total:** $0.0172 (VM $0.0160, tokens $0.0012); budget $0.25 -> within
  - planner: $0.00125
  - VM primary vhp-1c-1gb-amd: $0.00800
  - VM verifier vhp-1c-1gb-amd: $0.00800

## Audit chain

13 events, head `b45fc46518bc99b88e2f1afb05ac2242cd68aaa17d595294d1ad9e0eeefc9f22`, verification: OK

| # | Time | Event | Hash |
|---|---|---|---|
| 0 | 2026-11-06T06:26:34.871528+00:00 | task.received | `7f0c712de5e09bc7` |
| 1 | 2026-11-06T06:26:34.873349+00:00 | task.planning | `492812e522cbe5fb` |
| 2 | 2026-11-06T06:26:36.948453+00:00 | cost.tokens | `639a2ec788191301` |
| 3 | 2026-11-06T06:26:36.948653+00:00 | plan.created | `26cadcf97f07b331` |
| 4 | 2026-11-06T06:26:36.948842+00:00 | budget.preflight | `48014803cf6b59e5` |
| 5 | 2026-11-06T06:26:36.948964+00:00 | task.provisioning | `da329b886dd66317` |
| 6 | 2026-11-06T06:26:36.955283+00:00 | task.provisioning | `b1a5696a3dcde185` |
| 7 | 2026-11-06T06:26:47.885049+00:00 | kill.requested | `d53e671e2125ed7d` |
| 8 | 2026-11-06T06:26:47.885243+00:00 | task.destroying | `7ea2870b2bb26fee` |
| 9 | 2026-11-06T06:26:47.886146+00:00 | task.destroying | `2fc9d16a0c012c36` |
| 10 | 2026-11-06T06:27:09.565192+00:00 | vm.destroyed | `862b767156d199db` |
| 11 | 2026-11-06T06:27:09.670438+00:00 | vm.destroyed | `e51c6f56bedb0072` |
| 12 | 2026-11-06T06:27:09.670710+00:00 | task.killed | `b45fc46518bc99b8` |
