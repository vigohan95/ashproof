# Ashproof receipt `706fa63d1e02`

- **Status:** KILLED
- **Created:** 2026-11-06T06:27:48.480285+00:00
- **Task:** Run one python step that prints a heartbeat line every second for 100 seconds, flushing each line, and then writes done.txt containing the word done.
- **Task sha256:** `15fb68e706e11a6c4e85e737c76f3e27415386e3ea4733df2f428434c9b9fb1e`
- **Receipt sha256:** `52ec2ff2f9a6e374d2631a7ed97d89318f2de589ba579844d41127637a3d1539`
- **Receipt integrity:** OK

## Blast radius

| Sandbox | Provider | Instance | Created | Destroyed | Proof | Inner layer | Egress |
|---|---|---|---|---|---|---|---|
| verifier | vultr | `c3e48b59-26f3-49d5-b59a-1c0e5ed14a44` | 2026-11-06T06:27:17+00:00 | 2026-11-06T06:27:36+00:00 | GET /v2/instances/{id} -> 404 | gvisor runsc --platform=systrap | default-deny |
| primary | vultr | `24810128-5879-4c41-938b-25e78ef55a23` | 2026-11-06T06:27:17+00:00 | 2026-11-06T06:27:47+00:00 | GET /v2/instances/{id} -> 404 | gvisor runsc --platform=systrap | default-deny |

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
  - planner: $0.00130
  - VM verifier vhp-1c-1gb-amd: $0.00800
  - VM primary vhp-1c-1gb-amd: $0.00800

## Audit chain

13 events, head `4291d725691f109abe2bdcca4142da105da2dd2cc48e9169e4e8cb49efff2baf`, verification: OK

| # | Time | Event | Hash |
|---|---|---|---|
| 0 | 2026-11-06T06:27:13.471878+00:00 | task.received | `3480b52e90f80c59` |
| 1 | 2026-11-06T06:27:13.473482+00:00 | task.planning | `92c78f05c05d1e76` |
| 2 | 2026-11-06T06:27:16.837427+00:00 | cost.tokens | `ef18fe6548f1c8c3` |
| 3 | 2026-11-06T06:27:16.837635+00:00 | plan.created | `89b8eda6a71d103e` |
| 4 | 2026-11-06T06:27:16.837815+00:00 | budget.preflight | `55895246f2887925` |
| 5 | 2026-11-06T06:27:16.837915+00:00 | task.provisioning | `511304cf1dcfc4b5` |
| 6 | 2026-11-06T06:27:16.843096+00:00 | task.provisioning | `ce1b28936277de69` |
| 7 | 2026-11-06T06:27:27.830972+00:00 | kill.requested | `bc6d5c41e7a7e65b` |
| 8 | 2026-11-06T06:27:27.831193+00:00 | task.destroying | `f9907819b4cb4502` |
| 9 | 2026-11-06T06:27:27.832215+00:00 | task.destroying | `ea4f8caab7c3a0c4` |
| 10 | 2026-11-06T06:27:36.733303+00:00 | vm.destroyed | `94d09a2ce1e31863` |
| 11 | 2026-11-06T06:27:47.869251+00:00 | vm.destroyed | `0380506f7d838bb1` |
| 12 | 2026-11-06T06:27:48.479988+00:00 | task.killed | `4291d725691f109a` |
