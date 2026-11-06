# Ashproof receipt `c6d10387afa8`

- **Status:** VERIFIED
- **Created:** 2026-11-06T07:22:19.494810+00:00
- **Task:** Total the amount column per region in sales.csv and write summary.json
- **Task sha256:** `9ae05af7a8024f5c7c09a01ea5d8a39096df157dd0253e1ee028e093a5e7c297`
- **Receipt sha256:** `335bc51c6f55152e8e6972cd1291104e515523b7d1e518b54377eecda38da77e`
- **Receipt integrity:** OK

## Blast radius

| Sandbox | Provider | Instance | Created | Destroyed | Proof | Inner layer | Egress |
|---|---|---|---|---|---|---|---|
| verifier | vultr | `d88d380c-a698-49db-b5d3-1ca5c7251c72` | 2026-11-06T07:20:36+00:00 | 2026-11-06T07:22:18+00:00 | GET /v2/instances/{id} -> 404 | gvisor runsc --platform=systrap | default-deny |
| primary | vultr | `a7590626-c5fe-4243-bc0f-366f5aa7df49` | 2026-11-06T07:20:37+00:00 | 2026-11-06T07:22:19+00:00 | GET /v2/instances/{id} -> 404 | gvisor runsc --platform=systrap | default-deny |

All VMs destroyed: **yes**

## Plan

Aggregate the amount column per region from sales.csv and write summary.json  
Planner model: `glm-5.3`; est. cost $0.0100; required domains: none

## Steps

| Step | Kind | Exit | Duration | stdout sha256 | Output files | Executor |
|---|---|---|---|---|---|---|
| s1 Aggregate amounts per region | python | 0 | 0.12s | `b234ecaddb89` | summary.json `834fc0e2acc4` | gvisor-systrap |

## Verification

- **Verdict:** PASSED (model: `qwen3.8-27b`)
- **Independent re-run:** performed; hashes identical: True
  - [x] s1:exit_code exit_code=0
  - [x] s1:output:summary.json present
  - [x] assert:file_exists:summary.json
  - [x] assert:stdout_contains:regions:
  - [x] rerun:hashes_identical all outputs byte-identical across two clean sandboxes
- **Model review:** satisfies_task=True confidence=0.99
  - Recomputed from input: north=10+5=15, south=20, west=2.5 — matches summary.json exactly
  - All three regions present with correct totals
  - Output is valid JSON with numeric values

## Egress

Policy: default-deny. Allowed domains: none.  
Attempts: 0 (denied 0, allowed 0)

## Secret hygiene

- Result: **CLEAN** (20 files, 16 env vars, scanner `brz_runner.secretscan`)

## Cost

- **Total:** $0.0176 (VM $0.0160, tokens $0.0016); budget $0.25 -> within
  - planner: $0.00133
  - VM verifier vhp-1c-1gb-amd: $0.00800
  - verifier: $0.00025
  - VM primary vhp-1c-1gb-amd: $0.00800

## Audit chain

24 events, head `4066740f4a917d7f86989553e8a015566adde03f04ea377b7b54047b2b685343`, verification: OK

| # | Time | Event | Hash |
|---|---|---|---|
| 0 | 2026-11-06T07:20:30.508525+00:00 | task.received | `80703bc0d23120e3` |
| 1 | 2026-11-06T07:20:30.509998+00:00 | task.planning | `2256f98cc5520ba7` |
| 2 | 2026-11-06T07:20:32.644948+00:00 | cost.tokens | `52249baf2b56692b` |
| 3 | 2026-11-06T07:20:32.645082+00:00 | plan.created | `8953d6f4f8c3d6e3` |
| 4 | 2026-11-06T07:20:32.645274+00:00 | budget.preflight | `703165ed13a41855` |
| 5 | 2026-11-06T07:20:32.645422+00:00 | task.provisioning | `de9cbb07ae97496c` |
| 6 | 2026-11-06T07:20:32.650146+00:00 | task.provisioning | `27c27d52fc21e895` |
| 7 | 2026-11-06T07:21:08.507834+00:00 | vm.created | `c466f8325bb9ee76` |
| 8 | 2026-11-06T07:21:09.836311+00:00 | vm.created | `eed1d7fe5e092db2` |
| 9 | 2026-11-06T07:22:16.770564+00:00 | vm.runner_ready | `bbaea667ce199a0e` |
| 10 | 2026-11-06T07:22:17.792907+00:00 | vm.runner_ready | `71d74a47f0584ec4` |
| 11 | 2026-11-06T07:22:17.793054+00:00 | task.running | `ed8bef5971bada25` |
| 12 | 2026-11-06T07:22:17.922926+00:00 | step.finished | `7648978d118a189b` |
| 13 | 2026-11-06T07:22:17.923183+00:00 | task.verifying | `8f3ae33981137b1e` |
| 14 | 2026-11-06T07:22:18.051986+00:00 | step.finished | `726325e1fdeef109` |
| 15 | 2026-11-06T07:22:18.052185+00:00 | task.destroying | `29ed2def62012ade` |
| 16 | 2026-11-06T07:22:18.362397+00:00 | vm.destroyed | `3a578d31e13a3594` |
| 17 | 2026-11-06T07:22:19.229293+00:00 | cost.tokens | `eaef8954a2c6da8f` |
| 18 | 2026-11-06T07:22:19.229412+00:00 | verify.verdict | `3e65c3ee9a9afa65` |
| 19 | 2026-11-06T07:22:19.229530+00:00 | task.scanning | `9e68659935ac62a5` |
| 20 | 2026-11-06T07:22:19.242420+00:00 | secret_scan.done | `601890c37f77ae80` |
| 21 | 2026-11-06T07:22:19.242517+00:00 | task.destroying | `6e1836b5b1154188` |
| 22 | 2026-11-06T07:22:19.491726+00:00 | vm.destroyed | `561cf34c95388528` |
| 23 | 2026-11-06T07:22:19.494278+00:00 | task.verified | `4066740f4a917d7f` |
