# Ashproof receipt `def42ffeb355`

- **Status:** KILLED
- **Created:** 2026-11-06T06:20:38.924851+00:00
- **Task:** Run one python step that prints a heartbeat line every second for 100 seconds, flushing each line, and then writes done.txt containing the word done.
- **Task sha256:** `15fb68e706e11a6c4e85e737c76f3e27415386e3ea4733df2f428434c9b9fb1e`
- **Receipt sha256:** `24ca9a94c6512a81dc3295d1c1d51eb159c00b4b7069b7aed10824dc00661839`
- **Receipt integrity:** OK

## Blast radius

| Sandbox | Provider | Instance | Created | Destroyed | Proof | Inner layer | Egress |
|---|---|---|---|---|---|---|---|
| verifier | vultr | `b9d10404-a8e4-4685-93f5-016bd9f4c655` | 2026-11-06T06:18:51+00:00 | 2026-11-06T06:20:38+00:00 | GET /v2/instances/{id} -> 404 | gvisor runsc --platform=systrap | default-deny |
| primary | vultr | `d30976b6-5d0d-4097-ab33-e154d134d555` | 2026-11-06T06:18:51+00:00 | 2026-11-06T06:20:38+00:00 | GET /v2/instances/{id} -> 404 | gvisor runsc --platform=systrap | default-deny |

All VMs destroyed: **yes**

## Plan

Single Python step printing a flushed heartbeat line every second for 100 seconds, then writing done.txt.  
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

- **Total:** $0.0170 (VM $0.0160, tokens $0.0010); budget $0.25 -> within
  - planner: $0.00103
  - VM primary vhp-1c-1gb-amd: $0.00800
  - VM verifier vhp-1c-1gb-amd: $0.00800

## Audit chain

20 events, head `67264d9435d0bc545235f31cae9629b14c41579c2198a71ed5d2aceee8800a66`, verification: OK

| # | Time | Event | Hash |
|---|---|---|---|
| 0 | 2026-11-06T06:18:46.808104+00:00 | task.received | `c949e0fc619522af` |
| 1 | 2026-11-06T06:18:46.810382+00:00 | task.planning | `70bea6c6cf6b5e42` |
| 2 | 2026-11-06T06:18:48.589166+00:00 | cost.tokens | `0543a5fd123c2bbc` |
| 3 | 2026-11-06T06:18:48.589307+00:00 | plan.created | `c8d0244edfacc8e5` |
| 4 | 2026-11-06T06:18:48.589441+00:00 | budget.preflight | `5c4869c16074c0a7` |
| 5 | 2026-11-06T06:18:48.589531+00:00 | task.provisioning | `a5d3f3f0c90b4a8a` |
| 6 | 2026-11-06T06:18:48.594282+00:00 | task.provisioning | `de03987118f29f1f` |
| 7 | 2026-11-06T06:19:22.425152+00:00 | vm.created | `3ec2725bda58cc21` |
| 8 | 2026-11-06T06:19:22.787362+00:00 | vm.created | `04f4302cb40eb3a0` |
| 9 | 2026-11-06T06:20:30.399737+00:00 | vm.runner_ready | `b3e23dd9f3b07610` |
| 10 | 2026-11-06T06:20:30.911503+00:00 | vm.runner_ready | `037ed6dc28334857` |
| 11 | 2026-11-06T06:20:30.911664+00:00 | task.running | `a9f7a25616b51cac` |
| 12 | 2026-11-06T06:20:37.815444+00:00 | kill.requested | `b83c3a741ad4b46f` |
| 13 | 2026-11-06T06:20:37.825060+00:00 | kill.tokens_revoked | `d524fe935ab27b7c` |
| 14 | 2026-11-06T06:20:37.825176+00:00 | task.destroying | `2659e9d5bb724343` |
| 15 | 2026-11-06T06:20:37.826204+00:00 | kill.tokens_revoked | `e0ab6ee45f5a784f` |
| 16 | 2026-11-06T06:20:37.826293+00:00 | task.destroying | `65c01d492d8d78b5` |
| 17 | 2026-11-06T06:20:38.921867+00:00 | vm.destroyed | `4542aa84ba44443f` |
| 18 | 2026-11-06T06:20:38.923071+00:00 | vm.destroyed | `59d3f9e677890597` |
| 19 | 2026-11-06T06:20:38.924375+00:00 | task.killed | `67264d9435d0bc54` |
