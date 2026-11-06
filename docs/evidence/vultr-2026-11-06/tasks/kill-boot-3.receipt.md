# Ashproof receipt `06c02213bdee`

- **Status:** KILLED
- **Created:** 2026-11-06T06:29:20.869086+00:00
- **Task:** Run one python step that prints a heartbeat line every second for 100 seconds, flushing each line, and then writes done.txt containing the word done.
- **Task sha256:** `15fb68e706e11a6c4e85e737c76f3e27415386e3ea4733df2f428434c9b9fb1e`
- **Receipt sha256:** `5c0488a75fefc2b9459a698881f9e9c13066715115ff23b11f7793fb4f81fc5d`
- **Receipt integrity:** OK

## Blast radius

| Sandbox | Provider | Instance | Created | Destroyed | Proof | Inner layer | Egress |
|---|---|---|---|---|---|---|---|
| verifier | vultr | `6fd7c84a-184b-46ef-890c-838372c20be1` | 2026-11-06T06:28:45+00:00 | 2026-11-06T06:29:19+00:00 | GET /v2/instances/{id} -> 404 | gvisor runsc --platform=systrap | default-deny |
| primary | vultr | `e058611f-3e5e-4cd2-bf1d-3ce391d430ce` | 2026-11-06T06:28:47+00:00 | 2026-11-06T06:29:20+00:00 | GET /v2/instances/{id} -> 404 | gvisor runsc --platform=systrap | default-deny |

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
  - VM verifier vhp-1c-1gb-amd: $0.00800
  - VM primary vhp-1c-1gb-amd: $0.00800

## Audit chain

13 events, head `575380084508aba1fae9b983dcabcdf5eea525b630857ec778091e2b1952403d`, verification: OK

| # | Time | Event | Hash |
|---|---|---|---|
| 0 | 2026-11-06T06:27:51.711428+00:00 | task.received | `ae6b59c95c8195aa` |
| 1 | 2026-11-06T06:27:51.713069+00:00 | task.planning | `0e8c37a7bd37195e` |
| 2 | 2026-11-06T06:27:53.351224+00:00 | cost.tokens | `751bc8e098a8c6f7` |
| 3 | 2026-11-06T06:27:53.351435+00:00 | plan.created | `7dce2e4d7784d756` |
| 4 | 2026-11-06T06:27:53.351702+00:00 | budget.preflight | `07b6d2490d7c980a` |
| 5 | 2026-11-06T06:27:53.351859+00:00 | task.provisioning | `fdc28461fc77488c` |
| 6 | 2026-11-06T06:27:53.357984+00:00 | task.provisioning | `7bebbb502c96faee` |
| 7 | 2026-11-06T06:28:03.745019+00:00 | kill.requested | `188cccecdfe335dd` |
| 8 | 2026-11-06T06:29:19.218346+00:00 | task.destroying | `5cb6d75df5e3a3db` |
| 9 | 2026-11-06T06:29:19.892017+00:00 | vm.destroyed | `faa80ac0591f598c` |
| 10 | 2026-11-06T06:29:19.892146+00:00 | task.destroying | `521cce87869f1906` |
| 11 | 2026-11-06T06:29:20.868741+00:00 | vm.destroyed | `3806efc39bb0f555` |
| 12 | 2026-11-06T06:29:20.868880+00:00 | task.killed | `575380084508aba1` |
