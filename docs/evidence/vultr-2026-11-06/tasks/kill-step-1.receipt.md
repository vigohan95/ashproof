# Ashproof receipt `40303d78f489`

- **Status:** KILLED
- **Created:** 2026-11-06T06:18:43.124369+00:00
- **Task:** Run one python step that prints a heartbeat line every second for 100 seconds, flushing each line, and then writes done.txt containing the word done.
- **Task sha256:** `15fb68e706e11a6c4e85e737c76f3e27415386e3ea4733df2f428434c9b9fb1e`
- **Receipt sha256:** `2ced0dcad323d7bd278fdd8e7d86b5fcdfb8e00ab62ee8f89ab6924a46018bef`
- **Receipt integrity:** OK

## Blast radius

| Sandbox | Provider | Instance | Created | Destroyed | Proof | Inner layer | Egress |
|---|---|---|---|---|---|---|---|
| primary | vultr | `fc1927c9-37df-4a88-a126-a5be271010bb` | 2026-11-06T06:16:55+00:00 | 2026-11-06T06:18:43+00:00 | GET /v2/instances/{id} -> 404 | gvisor runsc --platform=systrap | default-deny |
| verifier | vultr | `2a15d9af-28b8-4b8a-8d83-bc3e1af6deee` | 2026-11-06T06:16:56+00:00 | 2026-11-06T06:18:43+00:00 | GET /v2/instances/{id} -> 404 | gvisor runsc --platform=systrap | default-deny |

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

20 events, head `5d11b992aa19dbb3f214153ad719cd1d9085817802b3f31e61df6bf8d95b3546`, verification: OK

| # | Time | Event | Hash |
|---|---|---|---|
| 0 | 2026-11-06T06:16:50.105300+00:00 | task.received | `aacd9317d9aacb36` |
| 1 | 2026-11-06T06:16:50.105988+00:00 | task.planning | `fa72733fbce824ca` |
| 2 | 2026-11-06T06:16:51.766510+00:00 | cost.tokens | `b1ea68907570efd0` |
| 3 | 2026-11-06T06:16:51.766689+00:00 | plan.created | `5c65fd1cb79ff897` |
| 4 | 2026-11-06T06:16:51.766825+00:00 | budget.preflight | `bc2286149aa7d609` |
| 5 | 2026-11-06T06:16:51.766913+00:00 | task.provisioning | `41c959b128d14362` |
| 6 | 2026-11-06T06:16:51.772048+00:00 | task.provisioning | `cf3febd5a354d565` |
| 7 | 2026-11-06T06:17:27.201799+00:00 | vm.created | `76727068f1ed677e` |
| 8 | 2026-11-06T06:17:27.475203+00:00 | vm.created | `7f93332ffccf6f94` |
| 9 | 2026-11-06T06:18:35.200894+00:00 | vm.runner_ready | `b0d8a48293d4da40` |
| 10 | 2026-11-06T06:18:35.201042+00:00 | task.running | `06081fbda5585f6a` |
| 11 | 2026-11-06T06:18:35.713053+00:00 | vm.runner_ready | `ef7725b3d637e3e9` |
| 12 | 2026-11-06T06:18:42.606410+00:00 | kill.requested | `ec2694c09ffdaf74` |
| 13 | 2026-11-06T06:18:42.615023+00:00 | kill.tokens_revoked | `8fc10b34b6f9e35c` |
| 14 | 2026-11-06T06:18:42.615164+00:00 | task.destroying | `d89ffbcee219d9af` |
| 15 | 2026-11-06T06:18:42.617924+00:00 | kill.tokens_revoked | `0c61ff6daf86b804` |
| 16 | 2026-11-06T06:18:42.618022+00:00 | task.destroying | `819e745be9345a28` |
| 17 | 2026-11-06T06:18:43.116228+00:00 | vm.destroyed | `1192c207fef880ee` |
| 18 | 2026-11-06T06:18:43.123717+00:00 | vm.destroyed | `89effd2c86493b8a` |
| 19 | 2026-11-06T06:18:43.124142+00:00 | task.killed | `5d11b992aa19dbb3` |
