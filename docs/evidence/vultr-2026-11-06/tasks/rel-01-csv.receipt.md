# Ashproof receipt `99565e472c1e`

- **Status:** VERIFIED
- **Created:** 2026-11-06T07:01:47.190141+00:00
- **Task:** Total the amount column per region in sales.csv and write summary.json
- **Task sha256:** `9ae05af7a8024f5c7c09a01ea5d8a39096df157dd0253e1ee028e093a5e7c297`
- **Receipt sha256:** `231d64289a05a997991ef50426a073cf86fd51b139cc168048b504c83f832767`
- **Receipt integrity:** OK

## Blast radius

| Sandbox | Provider | Instance | Created | Destroyed | Proof | Inner layer | Egress |
|---|---|---|---|---|---|---|---|
| verifier | vultr | `f463f1b8-420a-4eb0-b5b6-adfd66d12112` | 2026-11-06T07:00:00+00:00 | 2026-11-06T07:01:45+00:00 | GET /v2/instances/{id} -> 404 | gvisor runsc --platform=systrap | default-deny |
| primary | vultr | `cdbaf150-5968-4171-86af-df4ecc568eff` | 2026-11-06T07:00:01+00:00 | 2026-11-06T07:01:47+00:00 | GET /v2/instances/{id} -> 404 | gvisor runsc --platform=systrap | default-deny |

All VMs destroyed: **yes**

## Plan

Aggregate the amount column per region from sales.csv and write summary.json  
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
  - [x] rerun:hashes_identical all outputs byte-identical across two clean sandboxes
- **Model review:** satisfies_task=True confidence=0.99
  - Expected totals: north=15, south=20, west=2.5
  - summary.json contains exactly {"north": 15.0, "south": 20.0, "west": 2.5}
  - All values match the recomputation from the input CSV

## Egress

Policy: default-deny. Allowed domains: none.  
Attempts: 0 (denied 0, allowed 0)

## Secret hygiene

- Result: **CLEAN** (20 files, 16 env vars, scanner `brz_runner.secretscan`)

## Cost

- **Total:** $0.0177 (VM $0.0160, tokens $0.0017); budget $0.25 -> within
  - planner: $0.00138
  - VM verifier vhp-1c-1gb-amd: $0.00800
  - verifier: $0.00029
  - VM primary vhp-1c-1gb-amd: $0.00800

## Audit chain

24 events, head `626c20731dd310594cb775ed00de8da4f2740240b310fcba40045450bd402d6e`, verification: OK

| # | Time | Event | Hash |
|---|---|---|---|
| 0 | 2026-11-06T06:59:56.987921+00:00 | task.received | `fe8e0f0b2a57498b` |
| 1 | 2026-11-06T06:59:56.989180+00:00 | task.planning | `4087d03deefc8ad2` |
| 2 | 2026-11-06T06:59:59.898166+00:00 | cost.tokens | `10508ad7d3d9add2` |
| 3 | 2026-11-06T06:59:59.898316+00:00 | plan.created | `1ee822489d7a93ce` |
| 4 | 2026-11-06T06:59:59.898494+00:00 | budget.preflight | `6dc296128dc02ef1` |
| 5 | 2026-11-06T06:59:59.898611+00:00 | task.provisioning | `1a45271bc7cb0167` |
| 6 | 2026-11-06T06:59:59.905027+00:00 | task.provisioning | `97f6905bccce1c79` |
| 7 | 2026-11-06T07:00:31.157670+00:00 | vm.created | `c8d5eb388051300b` |
| 8 | 2026-11-06T07:00:36.900128+00:00 | vm.created | `262c6f366a52d611` |
| 9 | 2026-11-06T07:01:39.263880+00:00 | vm.runner_ready | `f6583874c7157a53` |
| 10 | 2026-11-06T07:01:44.896842+00:00 | vm.runner_ready | `c6c6406d0dd878e4` |
| 11 | 2026-11-06T07:01:44.896991+00:00 | task.running | `472ba42ecdd8972b` |
| 12 | 2026-11-06T07:01:45.028415+00:00 | step.finished | `65fab07e6b2a759b` |
| 13 | 2026-11-06T07:01:45.028673+00:00 | task.verifying | `c2525ea0221d2e3d` |
| 14 | 2026-11-06T07:01:45.158264+00:00 | step.finished | `5306f921d1e611ab` |
| 15 | 2026-11-06T07:01:45.158456+00:00 | task.destroying | `d97c0833e942b573` |
| 16 | 2026-11-06T07:01:45.701052+00:00 | vm.destroyed | `9a7850febca9a4e7` |
| 17 | 2026-11-06T07:01:46.598223+00:00 | cost.tokens | `7a5332237c5d348d` |
| 18 | 2026-11-06T07:01:46.598356+00:00 | verify.verdict | `12911928db8fc2c1` |
| 19 | 2026-11-06T07:01:46.598500+00:00 | task.scanning | `fccaec70d5e5f164` |
| 20 | 2026-11-06T07:01:46.611255+00:00 | secret_scan.done | `9e9a05264d06b345` |
| 21 | 2026-11-06T07:01:46.611392+00:00 | task.destroying | `e368fa0842c8d765` |
| 22 | 2026-11-06T07:01:47.189290+00:00 | vm.destroyed | `287393797b3be435` |
| 23 | 2026-11-06T07:01:47.189833+00:00 | task.verified | `626c20731dd31059` |
