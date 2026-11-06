# Ashproof receipt `7bd90bed1051`

- **Status:** VERIFIED
- **Created:** 2026-11-06T06:47:59.873068+00:00
- **Task:** Total the amount column per region in sales.csv and write summary.json
- **Task sha256:** `9ae05af7a8024f5c7c09a01ea5d8a39096df157dd0253e1ee028e093a5e7c297`
- **Receipt sha256:** `4887f3b66b1348e833c3a5a9bc34e053f62649b5f3740c069d756e9aeba5542c`
- **Receipt integrity:** OK

## Blast radius

| Sandbox | Provider | Instance | Created | Destroyed | Proof | Inner layer | Egress |
|---|---|---|---|---|---|---|---|
| verifier | vultr | `fc7318c8-d7e4-4a1a-be01-88f6cebd5552` | 2026-11-06T06:46:08+00:00 | 2026-11-06T06:47:58+00:00 | GET /v2/instances/{id} -> 404 | gvisor runsc --platform=systrap | default-deny |
| primary | vultr | `cfb36bbc-d555-4a4b-83a4-d5cbde2b9b67` | 2026-11-06T06:46:18+00:00 | 2026-11-06T06:47:59+00:00 | GET /v2/instances/{id} -> 404 | gvisor runsc --platform=systrap | default-deny |

All VMs destroyed: **yes**

## Plan

Aggregate the amount column per region from /work/input/sales.csv and write /work/out/summary.json  
Planner model: `glm-5.3`; est. cost $0.0100; required domains: none

## Steps

| Step | Kind | Exit | Duration | stdout sha256 | Output files | Executor |
|---|---|---|---|---|---|---|
| 1 Aggregate amounts per region and write summary.json | python | 0 | 0.12s | `b2afba68bc30` | summary.json `834fc0e2acc4` | gvisor-systrap |

## Verification

- **Verdict:** PASSED (model: `qwen3.8-27b`)
- **Independent re-run:** performed; hashes identical: True
  - [x] 1:exit_code exit_code=0
  - [x] 1:output:summary.json present
  - [x] assert:file_exists:summary.json
  - [x] assert:stdout_contains:{
  - [x] rerun:hashes_identical all outputs byte-identical across two clean sandboxes
- **Model review:** satisfies_task=True confidence=1.0
  - Input has north=10+5=15, south=20, west=2.5
  - Output summary.json contains exactly {"north": 15.0, "south": 20.0, "west": 2.5}
  - All region totals are correct

## Egress

Policy: default-deny. Allowed domains: none.  
Attempts: 0 (denied 0, allowed 0)

## Secret hygiene

- Result: **CLEAN** (20 files, 16 env vars, scanner `brz_runner.secretscan`)

## Cost

- **Total:** $0.0178 (VM $0.0160, tokens $0.0018); budget $0.25 -> within
  - planner: $0.00151
  - VM verifier vhp-1c-1gb-amd: $0.00800
  - verifier: $0.00028
  - VM primary vhp-1c-1gb-amd: $0.00800

## Audit chain

24 events, head `2b7178a3755e0d475b6ed57097be67ae7d2a3848a76498f3b1e76616c965b18b`, verification: OK

| # | Time | Event | Hash |
|---|---|---|---|
| 0 | 2026-11-06T06:46:04.886359+00:00 | task.received | `6310ffff5369827d` |
| 1 | 2026-11-06T06:46:04.888612+00:00 | task.planning | `d72b06678e3a2c6d` |
| 2 | 2026-11-06T06:46:07.787608+00:00 | cost.tokens | `65ef2b95cf2d4249` |
| 3 | 2026-11-06T06:46:07.787756+00:00 | plan.created | `20d5fc254a42ebf2` |
| 4 | 2026-11-06T06:46:07.787879+00:00 | budget.preflight | `7e9dc180486121c2` |
| 5 | 2026-11-06T06:46:07.787975+00:00 | task.provisioning | `82b74cfbd7c39058` |
| 6 | 2026-11-06T06:46:07.793005+00:00 | task.provisioning | `8569d5249fbfd298` |
| 7 | 2026-11-06T06:46:39.864817+00:00 | vm.created | `2f7a961b3e64c429` |
| 8 | 2026-11-06T06:46:49.888927+00:00 | vm.created | `eccdf9308df7b1ff` |
| 9 | 2026-11-06T06:47:48.289078+00:00 | vm.runner_ready | `25402c22ff1d9df0` |
| 10 | 2026-11-06T06:47:58.016063+00:00 | vm.runner_ready | `a7fd0112533969ef` |
| 11 | 2026-11-06T06:47:58.016212+00:00 | task.running | `1bbbd2c1e571bde1` |
| 12 | 2026-11-06T06:47:58.148790+00:00 | step.finished | `1a778d173de54252` |
| 13 | 2026-11-06T06:47:58.149076+00:00 | task.verifying | `488d070455f15c0a` |
| 14 | 2026-11-06T06:47:58.281910+00:00 | step.finished | `021c015d50353f62` |
| 15 | 2026-11-06T06:47:58.282192+00:00 | task.destroying | `64f44e8837d8e2b7` |
| 16 | 2026-11-06T06:47:58.628416+00:00 | vm.destroyed | `937ee43613879999` |
| 17 | 2026-11-06T06:47:59.412277+00:00 | cost.tokens | `63a76a13ca1cd5f4` |
| 18 | 2026-11-06T06:47:59.412457+00:00 | verify.verdict | `e5ee06f7436ba871` |
| 19 | 2026-11-06T06:47:59.412658+00:00 | task.scanning | `e341a49a3ba7694d` |
| 20 | 2026-11-06T06:47:59.429307+00:00 | secret_scan.done | `f28ffd4b861d7e7c` |
| 21 | 2026-11-06T06:47:59.429488+00:00 | task.destroying | `22c4953574c1b7be` |
| 22 | 2026-11-06T06:47:59.871144+00:00 | vm.destroyed | `fef9a84c6455ecdd` |
| 23 | 2026-11-06T06:47:59.872726+00:00 | task.verified | `2b7178a3755e0d47` |
