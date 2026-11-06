# Ashproof receipt `18eb27122cea`

- **Status:** VERIFIED
- **Created:** 2026-11-06T07:10:03.783943+00:00
- **Task:** Total the amount column per region in sales.csv and write summary.json
- **Task sha256:** `9ae05af7a8024f5c7c09a01ea5d8a39096df157dd0253e1ee028e093a5e7c297`
- **Receipt sha256:** `cdfd1319efbbc671fb0e123f67910c111b522fa92a26c9afc7696d664579e900`
- **Receipt integrity:** OK

## Blast radius

| Sandbox | Provider | Instance | Created | Destroyed | Proof | Inner layer | Egress |
|---|---|---|---|---|---|---|---|
| primary | vultr | `64db5330-73ea-4d1a-a4c3-5899aeb9662e` | 2026-11-06T07:06:12+00:00 | 2026-11-06T07:10:03+00:00 | GET /v2/instances/{id} -> 404 | gvisor runsc --platform=systrap | default-deny |
| verifier | vultr | `ce3b14c8-b8e2-4cef-a491-983dd7019ad4` | 2026-11-06T07:06:13+00:00 | 2026-11-06T07:10:02+00:00 | GET /v2/instances/{id} -> 404 | gvisor runsc --platform=systrap | default-deny |

All VMs destroyed: **yes**

## Plan

Aggregate the amount column per region from /work/input/sales.csv and write summary.json to /work/out/  
Planner model: `glm-5.3`; est. cost $0.0200; required domains: none

## Steps

| Step | Kind | Exit | Duration | stdout sha256 | Output files | Executor |
|---|---|---|---|---|---|---|
| step-1 Aggregate amounts per region and write summary.json (repaired) | python | 0 | 0.22s | `131df3a3a25b` | summary.json `d3a13064a1cb` | gvisor-systrap |

## Verification

- **Verdict:** PASSED (model: `qwen3.8-27b`)
- **Independent re-run:** performed; hashes identical: True
  - [x] step-1:exit_code exit_code=0
  - [x] step-1:output:summary.json present
  - [x] assert:file_exists:summary.json
  - [x] assert:file_contains:summary.json:regions
  - [x] assert:file_contains:summary.json:grand_total
  - [x] rerun:hashes_identical all outputs byte-identical across two clean sandboxes
- **Model review:** satisfies_task=True confidence=0.99
  - Recomputed from input: north=10+5=15, south=20, west=2.5, grand_total=37.5
  - Output summary.json matches expected values exactly
  - File was written to the expected location with correct structure

## Egress

Policy: default-deny. Allowed domains: none.  
Attempts: 0 (denied 0, allowed 0)

## Secret hygiene

- Result: **CLEAN** (20 files, 16 env vars, scanner `brz_runner.secretscan`)

## Cost

- **Total:** $0.0197 (VM $0.0160, tokens $0.0037); budget $0.25 -> within
  - planner: $0.00173
  - planner.repair: $0.00163
  - VM verifier vhp-1c-1gb-amd: $0.00800
  - verifier: $0.00030
  - VM primary vhp-1c-1gb-amd: $0.00800

## Audit chain

27 events, head `259f50376c2980178e065903b12801a27bbd665d6bd2f8030e83dfc3965e0209`, verification: OK

| # | Time | Event | Hash |
|---|---|---|---|
| 0 | 2026-11-06T07:06:08.837308+00:00 | task.received | `d1b431fc51a71bdb` |
| 1 | 2026-11-06T07:06:08.839209+00:00 | task.planning | `d4342f3b5b92dc83` |
| 2 | 2026-11-06T07:06:11.707504+00:00 | cost.tokens | `632d0265181c0c8e` |
| 3 | 2026-11-06T07:06:11.707665+00:00 | plan.created | `bd05a95523083c1c` |
| 4 | 2026-11-06T07:06:11.707793+00:00 | budget.preflight | `08c2302fce48d319` |
| 5 | 2026-11-06T07:06:11.707898+00:00 | task.provisioning | `cba8528f67d5abb9` |
| 6 | 2026-11-06T07:06:11.712716+00:00 | task.provisioning | `16123ed6987e2233` |
| 7 | 2026-11-06T07:07:26.262564+00:00 | vm.created | `5895525da30873ef` |
| 8 | 2026-11-06T07:07:35.550654+00:00 | vm.created | `d72f9f502ecab562` |
| 9 | 2026-11-06T07:09:52.186774+00:00 | vm.runner_ready | `f789c3e98c6ca3b4` |
| 10 | 2026-11-06T07:09:58.330709+00:00 | vm.runner_ready | `e94af83b7a9ca18c` |
| 11 | 2026-11-06T07:09:58.330909+00:00 | task.running | `a60babb154bba26c` |
| 12 | 2026-11-06T07:09:58.516690+00:00 | step.finished | `418776f085e59737` |
| 13 | 2026-11-06T07:10:01.154793+00:00 | cost.tokens | `15e70af859343545` |
| 14 | 2026-11-06T07:10:01.155028+00:00 | step.repaired | `a7c5a7e92bd90722` |
| 15 | 2026-11-06T07:10:01.394742+00:00 | step.finished | `09083ccb5e4c9671` |
| 16 | 2026-11-06T07:10:01.395050+00:00 | task.verifying | `3c337322442b6806` |
| 17 | 2026-11-06T07:10:01.855335+00:00 | step.finished | `50ea50eba5a8e488` |
| 18 | 2026-11-06T07:10:01.855644+00:00 | task.destroying | `ac44321566ca7079` |
| 19 | 2026-11-06T07:10:02.231695+00:00 | vm.destroyed | `5e9288424f11dd44` |
| 20 | 2026-11-06T07:10:03.075969+00:00 | cost.tokens | `82227f2b61f65873` |
| 21 | 2026-11-06T07:10:03.076180+00:00 | verify.verdict | `d3a2faf5d038bc13` |
| 22 | 2026-11-06T07:10:03.076459+00:00 | task.scanning | `b75767087254b6ee` |
| 23 | 2026-11-06T07:10:03.111544+00:00 | secret_scan.done | `2ec6a3c7dc04d72a` |
| 24 | 2026-11-06T07:10:03.111818+00:00 | task.destroying | `8dbb23b71977e234` |
| 25 | 2026-11-06T07:10:03.781753+00:00 | vm.destroyed | `f4a3c67bc29f2cf4` |
| 26 | 2026-11-06T07:10:03.783622+00:00 | task.verified | `259f50376c298017` |
