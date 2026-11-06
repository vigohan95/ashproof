# Ashproof receipt `0b41ab02c93f`

- **Status:** VERIFIED
- **Created:** 2026-11-06T07:16:23.034770+00:00
- **Task:** Total the amount column per region in sales.csv and write summary.json
- **Task sha256:** `9ae05af7a8024f5c7c09a01ea5d8a39096df157dd0253e1ee028e093a5e7c297`
- **Receipt sha256:** `2c2ac25b79c206df3cbaaa23a1ac9603f0018a7b16596bbb7c1070ccf0a87066`
- **Receipt integrity:** OK

## Blast radius

| Sandbox | Provider | Instance | Created | Destroyed | Proof | Inner layer | Egress |
|---|---|---|---|---|---|---|---|
| primary | vultr | `82a6d914-614d-42b6-a504-4ff24f1e4949` | 2026-11-06T07:14:29+00:00 | 2026-11-06T07:16:23+00:00 | GET /v2/instances/{id} -> 404 | gvisor runsc --platform=systrap | default-deny |
| verifier | vultr | `e999f11e-3ea4-4356-8490-f5fb34fc6e75` | 2026-11-06T07:14:30+00:00 | 2026-11-06T07:16:21+00:00 | GET /v2/instances/{id} -> 404 | gvisor runsc --platform=systrap | default-deny |

All VMs destroyed: **yes**

## Plan

Aggregate the amount column per region from /work/input/sales.csv and write /work/out/summary.json  
Planner model: `glm-5.3`; est. cost $0.0100; required domains: none

## Steps

| Step | Kind | Exit | Duration | stdout sha256 | Output files | Executor |
|---|---|---|---|---|---|---|
| summarize Sum amounts per region into summary.json | python | 0 | 0.12s | `b2afba68bc30` | summary.json `834fc0e2acc4` | gvisor-systrap |

## Verification

- **Verdict:** PASSED (model: `qwen3.8-27b`)
- **Independent re-run:** performed; hashes identical: True
  - [x] summarize:exit_code exit_code=0
  - [x] summarize:output:summary.json present
  - [x] assert:file_exists:summary.json
  - [x] assert:stdout_contains:{
  - [x] rerun:hashes_identical all outputs byte-identical across two clean sandboxes
- **Model review:** satisfies_task=True confidence=1.0
  - Expected totals: north=15, south=20, west=2.5
  - Output summary.json contains exactly {"north": 15.0, "south": 20.0, "west": 2.5}
  - All values match the recomputation from the input CSV

## Egress

Policy: default-deny. Allowed domains: none.  
Attempts: 0 (denied 0, allowed 0)

## Secret hygiene

- Result: **CLEAN** (20 files, 16 env vars, scanner `brz_runner.secretscan`)

## Cost

- **Total:** $0.0176 (VM $0.0160, tokens $0.0016); budget $0.25 -> within
  - planner: $0.00136
  - VM verifier vhp-1c-1gb-amd: $0.00800
  - verifier: $0.00028
  - VM primary vhp-1c-1gb-amd: $0.00800

## Audit chain

24 events, head `7fe65175e45a47fb6fdeaae255df0a067ea9e5d350bfbf6441facf065d7155f1`, verification: OK

| # | Time | Event | Hash |
|---|---|---|---|
| 0 | 2026-11-06T07:14:25.936565+00:00 | task.received | `c9d5339481dcf8b6` |
| 1 | 2026-11-06T07:14:25.938325+00:00 | task.planning | `e2ff236686811b62` |
| 2 | 2026-11-06T07:14:28.409390+00:00 | cost.tokens | `9297fa93937b0069` |
| 3 | 2026-11-06T07:14:28.409518+00:00 | plan.created | `059311cc4d72c97f` |
| 4 | 2026-11-06T07:14:28.409659+00:00 | budget.preflight | `3ac3997d8ae2ecf6` |
| 5 | 2026-11-06T07:14:28.409737+00:00 | task.provisioning | `962069056160457a` |
| 6 | 2026-11-06T07:14:28.414428+00:00 | task.provisioning | `562ba5608984b163` |
| 7 | 2026-11-06T07:15:00.811856+00:00 | vm.created | `14af5662ad6dbed5` |
| 8 | 2026-11-06T07:15:13.301818+00:00 | vm.created | `ffcfc548429f3bf7` |
| 9 | 2026-11-06T07:16:09.152560+00:00 | vm.runner_ready | `fb3631e87714dcb2` |
| 10 | 2026-11-06T07:16:09.152726+00:00 | task.running | `4f50986abc1f3716` |
| 11 | 2026-11-06T07:16:09.282766+00:00 | step.finished | `2a749824f1e0c1b3` |
| 12 | 2026-11-06T07:16:09.282974+00:00 | task.verifying | `114eb453f9d072f2` |
| 13 | 2026-11-06T07:16:21.439288+00:00 | vm.runner_ready | `963b2be8bbbf62a5` |
| 14 | 2026-11-06T07:16:21.573304+00:00 | step.finished | `0e217341678019e6` |
| 15 | 2026-11-06T07:16:21.573461+00:00 | task.destroying | `965ebead6aff36df` |
| 16 | 2026-11-06T07:16:21.894650+00:00 | vm.destroyed | `2a22a4387b721f7c` |
| 17 | 2026-11-06T07:16:22.692768+00:00 | cost.tokens | `35d56a8dd09065b7` |
| 18 | 2026-11-06T07:16:22.692894+00:00 | verify.verdict | `7887352d36c4d637` |
| 19 | 2026-11-06T07:16:22.693018+00:00 | task.scanning | `39f7b0eed3dae968` |
| 20 | 2026-11-06T07:16:22.706277+00:00 | secret_scan.done | `55187ff83aa58b99` |
| 21 | 2026-11-06T07:16:22.706406+00:00 | task.destroying | `a25f1717ac594f7a` |
| 22 | 2026-11-06T07:16:23.031979+00:00 | vm.destroyed | `fbf94b9f9b6b50e7` |
| 23 | 2026-11-06T07:16:23.034105+00:00 | task.verified | `7fe65175e45a47fb` |
