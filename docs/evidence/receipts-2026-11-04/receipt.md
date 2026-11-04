# Ashproof receipt `bb00802abf72`

- **Status:** VERIFIED
- **Created:** 2026-11-04T12:39:20.975620+00:00
- **Task:** Total the amount column per region in sales.csv and write report.md
- **Task sha256:** `ea2ccd6559796cbaa3b815e6f6af70cc2da5a1a692ae3413d5ff991f22afc88d`
- **Receipt sha256:** `171c3f0d76f27a6ee2b50a68fc76ca2e0def4717ed4ba2548ea961ba1f00c704`
- **Receipt integrity:** OK

## Blast radius

| Sandbox | Provider | Instance | Created | Destroyed | Proof | Inner layer | Egress |
|---|---|---|---|---|---|---|---|
| primary | local | `local-primary` | 2026-11-04T12:39:20+00:00 | 2026-11-04T12:39:20+00:00 | local runner stopped -> 0 | gvisor runsc --platform=systrap (WSL, no VM) | default-deny |
| verifier | local | `local-verifier` | 2026-11-04T12:39:20+00:00 | 2026-11-04T12:39:20+00:00 | local runner stopped -> 0 | gvisor runsc --platform=systrap (WSL, no VM) | default-deny |

All VMs destroyed: **yes**

## Plan

Total sales per region and write a short report  
Planner model: `scripted-model`; est. cost $0.0100; required domains: none

## Steps

| Step | Kind | Exit | Duration | stdout sha256 | Output files | Executor |
|---|---|---|---|---|---|---|
| s1 totals | python | 0 | 0.12s | `f7efd1c6b44a` | summary.json `31aaa7700251` | gvisor-systrap |
| s2 report | python | 0 | 0.12s | `7689195b7742` | report.md `baf33e6912a2`, summary.json `31aaa7700251` | gvisor-systrap |

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

26 events, head `9004bc932e2aa0748d60cbf26843eafcecfda82d511919facf72881c4dba9185`, verification: OK

| # | Time | Event | Hash |
|---|---|---|---|
| 0 | 2026-11-04T12:39:19.740029+00:00 | task.received | `63c0a98efdfcec8e` |
| 1 | 2026-11-04T12:39:19.740103+00:00 | task.planning | `b2a60140c5899339` |
| 2 | 2026-11-04T12:39:19.742928+00:00 | cost.tokens | `360e41f7a1370342` |
| 3 | 2026-11-04T12:39:19.742998+00:00 | plan.created | `27a6b65d6348353b` |
| 4 | 2026-11-04T12:39:19.743064+00:00 | budget.preflight | `6199daab086ad155` |
| 5 | 2026-11-04T12:39:19.743095+00:00 | task.provisioning | `16b9028a9025a985` |
| 6 | 2026-11-04T12:39:20.014487+00:00 | vm.created | `9f1b97b956a635a3` |
| 7 | 2026-11-04T12:39:20.086873+00:00 | vm.runner_ready | `0326955eee7a1f62` |
| 8 | 2026-11-04T12:39:20.086949+00:00 | task.running | `268ac0ae732d795a` |
| 9 | 2026-11-04T12:39:20.215139+00:00 | step.finished | `c2931f6c15e987f2` |
| 10 | 2026-11-04T12:39:20.342877+00:00 | step.finished | `2cbd2b070c827f86` |
| 11 | 2026-11-04T12:39:20.342972+00:00 | task.verifying | `e45d2561adfe194f` |
| 12 | 2026-11-04T12:39:20.342998+00:00 | task.provisioning | `e3ac6dcaa2698d33` |
| 13 | 2026-11-04T12:39:20.598032+00:00 | vm.created | `dbdbcc081e4b9ac4` |
| 14 | 2026-11-04T12:39:20.621596+00:00 | vm.runner_ready | `6506b8940aa3e33d` |
| 15 | 2026-11-04T12:39:20.749338+00:00 | step.finished | `43bd03e581d03217` |
| 16 | 2026-11-04T12:39:20.926653+00:00 | step.finished | `2cc63a38fefd0851` |
| 17 | 2026-11-04T12:39:20.926742+00:00 | task.destroying | `b00638c4d27d0c49` |
| 18 | 2026-11-04T12:39:20.944035+00:00 | vm.destroyed | `f2bc643ee20abd67` |
| 19 | 2026-11-04T12:39:20.945227+00:00 | cost.tokens | `70f3d4dccddb2cd0` |
| 20 | 2026-11-04T12:39:20.945277+00:00 | verify.verdict | `cd4c893dc059c87d` |
| 21 | 2026-11-04T12:39:20.945330+00:00 | task.scanning | `9011c18d4b39cf1c` |
| 22 | 2026-11-04T12:39:20.956114+00:00 | secret_scan.done | `a9200cbfd304341d` |
| 23 | 2026-11-04T12:39:20.956183+00:00 | task.destroying | `019864400bff5d9a` |
| 24 | 2026-11-04T12:39:20.972270+00:00 | vm.destroyed | `d9ffbba3024c9b41` |
| 25 | 2026-11-04T12:39:20.975393+00:00 | task.verified | `9004bc932e2aa074` |
