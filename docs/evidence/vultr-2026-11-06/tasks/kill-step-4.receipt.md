# Ashproof receipt `15054bccb8d2`

- **Status:** KILLED
- **Created:** 2026-11-06T06:24:37.211292+00:00
- **Task:** Run one python step that prints a heartbeat line every second for 100 seconds, flushing each line, and then writes done.txt containing the word done.
- **Task sha256:** `15fb68e706e11a6c4e85e737c76f3e27415386e3ea4733df2f428434c9b9fb1e`
- **Receipt sha256:** `6a03d4b8c19190f9f8a5edf14a66e65b98a74b6c0c6b976d1d8a2b3f3f39f598`
- **Receipt integrity:** OK

## Blast radius

| Sandbox | Provider | Instance | Created | Destroyed | Proof | Inner layer | Egress |
|---|---|---|---|---|---|---|---|
| verifier | vultr | `3b1ce76d-226a-4064-bfbd-718a2cb67315` | 2026-11-06T06:22:44+00:00 | 2026-11-06T06:24:37+00:00 | GET /v2/instances/{id} -> 404 | gvisor runsc --platform=systrap | default-deny |
| primary | vultr | `436fe62b-011c-4ad0-ad24-be2eca094df1` | 2026-11-06T06:22:45+00:00 | 2026-11-06T06:24:37+00:00 | GET /v2/instances/{id} -> 404 | gvisor runsc --platform=systrap | default-deny |

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

20 events, head `566f3867c44b37462620867f2c174a6daf80e5be365e2b6965b761a5cd557e34`, verification: OK

| # | Time | Event | Hash |
|---|---|---|---|
| 0 | 2026-11-06T06:22:39.919519+00:00 | task.received | `77efee8f23114dff` |
| 1 | 2026-11-06T06:22:39.921104+00:00 | task.planning | `168d6ac49e237ff0` |
| 2 | 2026-11-06T06:22:41.608032+00:00 | cost.tokens | `c507bf0b83fd1c58` |
| 3 | 2026-11-06T06:22:41.608193+00:00 | plan.created | `a4d1b810166a464b` |
| 4 | 2026-11-06T06:22:41.608327+00:00 | budget.preflight | `2257a8b3a4d05438` |
| 5 | 2026-11-06T06:22:41.608413+00:00 | task.provisioning | `85995253c6ff8da9` |
| 6 | 2026-11-06T06:22:41.613002+00:00 | task.provisioning | `c80a5369c45ceaca` |
| 7 | 2026-11-06T06:23:20.665814+00:00 | vm.created | `bc7177aa0f028d57` |
| 8 | 2026-11-06T06:23:21.445450+00:00 | vm.created | `c286dcb62f6082a2` |
| 9 | 2026-11-06T06:24:28.992785+00:00 | vm.runner_ready | `da7332281535a941` |
| 10 | 2026-11-06T06:24:29.504196+00:00 | vm.runner_ready | `f1e4b0867fe99e2b` |
| 11 | 2026-11-06T06:24:29.504322+00:00 | task.running | `c19fab89358c84dc` |
| 12 | 2026-11-06T06:24:36.859810+00:00 | kill.requested | `6ca5385f3bf6b2d9` |
| 13 | 2026-11-06T06:24:36.868833+00:00 | kill.tokens_revoked | `bcc3debdac84246f` |
| 14 | 2026-11-06T06:24:36.868987+00:00 | task.destroying | `1221c0b10f2b015f` |
| 15 | 2026-11-06T06:24:36.871266+00:00 | kill.tokens_revoked | `83a1ca6b8f8ee439` |
| 16 | 2026-11-06T06:24:36.871528+00:00 | task.destroying | `05eb49a1831abc5b` |
| 17 | 2026-11-06T06:24:37.139299+00:00 | vm.destroyed | `ecaf03650b8bc8b2` |
| 18 | 2026-11-06T06:24:37.210238+00:00 | vm.destroyed | `b8bf8cb9300fabef` |
| 19 | 2026-11-06T06:24:37.210987+00:00 | task.killed | `566f3867c44b3746` |
