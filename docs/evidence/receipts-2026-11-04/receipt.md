# Blast Radius Zero receipt `6c06db8c1d13`

- **Status:** VERIFIED
- **Created:** 2026-11-04T12:33:45.086441+00:00
- **Task:** Total the amount column per region in sales.csv and write report.md
- **Task sha256:** `ea2ccd6559796cbaa3b815e6f6af70cc2da5a1a692ae3413d5ff991f22afc88d`
- **Receipt sha256:** `7598e85934f6198e196b39f88049dc5dd2897dcc10714351e3fbc89d344ccd5b`
- **Receipt integrity:** OK

## Blast radius

| Sandbox | Provider | Instance | Created | Destroyed | Proof | Inner layer | Egress |
|---|---|---|---|---|---|---|---|
| primary | local | `local-primary` | 2026-11-04T12:33:43+00:00 | 2026-11-04T12:33:45+00:00 | local runner stopped -> 0 | gvisor runsc --platform=systrap (WSL, no VM) | default-deny |
| verifier | local | `local-verifier` | 2026-11-04T12:33:44+00:00 | 2026-11-04T12:33:45+00:00 | local runner stopped -> 0 | gvisor runsc --platform=systrap (WSL, no VM) | default-deny |

All VMs destroyed: **yes**

## Plan

Total sales per region and write a short report  
Planner model: `scripted-model`; est. cost $0.0100; required domains: none

## Steps

| Step | Kind | Exit | Duration | stdout sha256 | Output files | Executor |
|---|---|---|---|---|---|---|
| s1 totals | python | 0 | 0.17s | `f7efd1c6b44a` | summary.json `31aaa7700251` | gvisor-systrap |
| s2 report | python | 0 | 0.17s | `7689195b7742` | report.md `baf33e6912a2`, summary.json `31aaa7700251` | gvisor-systrap |

## Verification

- **Verdict:** PASSED (model: `scripted-model`)
- **Independent re-run:** performed; hashes identical: True
  - [x] s1:exit_code exit_code=0
  - [x] s1:output:summary.json present
  - [x] s2:exit_code exit_code=0
  - [x] s2:output:report.md present
  - [x] assert:file_contains:report.md:north 15.0
  - [x] rerun:hashes_identical all outputs byte-identical across two clean sandboxes
- **Model review:** satisfies_task=True confidence=0.9
  - totals match

## Egress

Policy: default-deny. Allowed domains: none.  
Attempts: 0 (denied 0, allowed 0)

## Secret hygiene

- Result: **CLEAN** (5 files, 4 env vars, scanner `brz_runner.secretscan`)

## Cost

- **Total:** $0.0182 (VM $0.0179, tokens $0.0004); budget $5.00 -> within
  - planner: $0.00018
  - VM verifier vhp-1c-1gb-amd: $0.00893
  - verifier: $0.00018
  - VM primary vhp-1c-1gb-amd: $0.00893

## Audit chain

26 events, head `4009b3fa1f87c30e8b07fe98db696225e3a7d27b045e6d86943a4039b211ce3c`, verification: OK

| # | Time | Event | Hash |
|---|---|---|---|
| 0 | 2026-11-04T12:33:43.479074+00:00 | task.received | `de95037fa557890e` |
| 1 | 2026-11-04T12:33:43.479183+00:00 | task.planning | `f05336d988366abb` |
| 2 | 2026-11-04T12:33:43.486387+00:00 | cost.tokens | `2d3d9a3a26230fb0` |
| 3 | 2026-11-04T12:33:43.486540+00:00 | plan.created | `9a90ce4b20ab4565` |
| 4 | 2026-11-04T12:33:43.486657+00:00 | budget.preflight | `61abe6daf99780da` |
| 5 | 2026-11-04T12:33:43.486705+00:00 | task.provisioning | `8593f9893fe8e7d2` |
| 6 | 2026-11-04T12:33:43.821868+00:00 | vm.created | `1a0dc30e4f13a3d6` |
| 7 | 2026-11-04T12:33:43.931704+00:00 | vm.runner_ready | `de0a870f88b966c6` |
| 8 | 2026-11-04T12:33:43.932089+00:00 | task.running | `abf540508ffc592b` |
| 9 | 2026-11-04T12:33:44.119383+00:00 | step.finished | `c19ab0eda1fc505d` |
| 10 | 2026-11-04T12:33:44.302878+00:00 | step.finished | `c32ae11e344acb3b` |
| 11 | 2026-11-04T12:33:44.302992+00:00 | task.verifying | `b48a2671396052b4` |
| 12 | 2026-11-04T12:33:44.303018+00:00 | task.provisioning | `968267eee44a534d` |
| 13 | 2026-11-04T12:33:44.610431+00:00 | vm.created | `f67cdf5bb070f99c` |
| 14 | 2026-11-04T12:33:44.639150+00:00 | vm.runner_ready | `e862e0834b8e620b` |
| 15 | 2026-11-04T12:33:44.827480+00:00 | step.finished | `05dbcd3d250a18e8` |
| 16 | 2026-11-04T12:33:45.014516+00:00 | step.finished | `a6813daf11ec02f3` |
| 17 | 2026-11-04T12:33:45.014684+00:00 | task.destroying | `77bd4faff68b2b0a` |
| 18 | 2026-11-04T12:33:45.038806+00:00 | vm.destroyed | `01975cb0caf3059b` |
| 19 | 2026-11-04T12:33:45.040983+00:00 | cost.tokens | `575972765937ffb5` |
| 20 | 2026-11-04T12:33:45.041103+00:00 | verify.verdict | `ad66f1e9015ff9f0` |
| 21 | 2026-11-04T12:33:45.041204+00:00 | task.scanning | `da81ea297665eb2c` |
| 22 | 2026-11-04T12:33:45.058528+00:00 | secret_scan.done | `b0cfa5a7a24f1c26` |
| 23 | 2026-11-04T12:33:45.058629+00:00 | task.destroying | `7591e2e2a8f60fda` |
| 24 | 2026-11-04T12:33:45.083029+00:00 | vm.destroyed | `a5b45b5a5013dd92` |
| 25 | 2026-11-04T12:33:45.086224+00:00 | task.verified | `4009b3fa1f87c30e` |
