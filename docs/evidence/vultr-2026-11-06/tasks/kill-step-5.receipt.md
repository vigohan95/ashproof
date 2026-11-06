# Ashproof receipt `32d757f86235`

- **Status:** KILLED
- **Created:** 2026-11-06T06:26:31.151251+00:00
- **Task:** Run one python step that prints a heartbeat line every second for 100 seconds, flushing each line, and then writes done.txt containing the word done.
- **Task sha256:** `15fb68e706e11a6c4e85e737c76f3e27415386e3ea4733df2f428434c9b9fb1e`
- **Receipt sha256:** `99a674a12a5485bec681266cfc064236047b96db1b2811a3a5ea0d81a7f586a8`
- **Receipt integrity:** OK

## Blast radius

| Sandbox | Provider | Instance | Created | Destroyed | Proof | Inner layer | Egress |
|---|---|---|---|---|---|---|---|
| verifier | vultr | `b21e4349-04a0-4b1c-aef7-9f1eb1d30e4e` | 2026-11-06T06:24:43+00:00 | 2026-11-06T06:26:31+00:00 | GET /v2/instances/{id} -> 404 | gvisor runsc --platform=systrap | default-deny |
| primary | vultr | `3b6c3cfe-da35-477a-9b9a-7b790db607ee` | 2026-11-06T06:24:43+00:00 | 2026-11-06T06:26:31+00:00 | GET /v2/instances/{id} -> 404 | gvisor runsc --platform=systrap | default-deny |

All VMs destroyed: **yes**

## Plan

Single Python step printing a flushed heartbeat line each second for 100 seconds, then writing done.txt.  
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
  - planner: $0.00119
  - VM verifier vhp-1c-1gb-amd: $0.00800
  - VM primary vhp-1c-1gb-amd: $0.00800

## Audit chain

20 events, head `d55c9aab55905da7a91675975c9c770ac13ccacdd349152a872824e1c7051be5`, verification: OK

| # | Time | Event | Hash |
|---|---|---|---|
| 0 | 2026-11-06T06:24:40.841548+00:00 | task.received | `4db5ba6bc1e58418` |
| 1 | 2026-11-06T06:24:40.842979+00:00 | task.planning | `4f008fb5205f181e` |
| 2 | 2026-11-06T06:24:42.642552+00:00 | cost.tokens | `2d4eb2b7bd867d68` |
| 3 | 2026-11-06T06:24:42.642754+00:00 | plan.created | `121b9c06af475ed6` |
| 4 | 2026-11-06T06:24:42.642939+00:00 | budget.preflight | `87e48d8954a76510` |
| 5 | 2026-11-06T06:24:42.643042+00:00 | task.provisioning | `d0441edacbe6e0e2` |
| 6 | 2026-11-06T06:24:42.648171+00:00 | task.provisioning | `faa1c46cf50ccc97` |
| 7 | 2026-11-06T06:25:15.235278+00:00 | vm.created | `22d49c5e7703fd94` |
| 8 | 2026-11-06T06:25:15.353843+00:00 | vm.created | `c6f52cc4c71a5f49` |
| 9 | 2026-11-06T06:26:23.169226+00:00 | vm.runner_ready | `41c8ba9761bb6e5b` |
| 10 | 2026-11-06T06:26:23.679758+00:00 | vm.runner_ready | `a8e1baae498026b5` |
| 11 | 2026-11-06T06:26:23.679915+00:00 | task.running | `3f508a5eed6ada77` |
| 12 | 2026-11-06T06:26:30.692930+00:00 | kill.requested | `b362f4a850309128` |
| 13 | 2026-11-06T06:26:30.704043+00:00 | kill.tokens_revoked | `bad71b765f6f22cb` |
| 14 | 2026-11-06T06:26:30.704218+00:00 | task.destroying | `0b7825d36d58b245` |
| 15 | 2026-11-06T06:26:30.707008+00:00 | kill.tokens_revoked | `e5473b95d6199833` |
| 16 | 2026-11-06T06:26:30.707127+00:00 | task.destroying | `16580109476f3bb6` |
| 17 | 2026-11-06T06:26:31.002474+00:00 | vm.destroyed | `7d3fec2e8369f7e3` |
| 18 | 2026-11-06T06:26:31.150518+00:00 | vm.destroyed | `b388ba29dfbe2b43` |
| 19 | 2026-11-06T06:26:31.151027+00:00 | task.killed | `d55c9aab55905da7` |
