# Ashproof receipt `f9e2190bd298`

- **Status:** VERIFIED
- **Created:** 2026-11-06T06:39:48.915740+00:00
- **Task:** Total the amount column per region in sales.csv and write summary.json
- **Task sha256:** `9ae05af7a8024f5c7c09a01ea5d8a39096df157dd0253e1ee028e093a5e7c297`
- **Receipt sha256:** `c6073560e2cfb18fa615293093ff4bad6a85c3745bf4ffb4e1a1c27d11b8d4db`
- **Receipt integrity:** OK

## Blast radius

| Sandbox | Provider | Instance | Created | Destroyed | Proof | Inner layer | Egress |
|---|---|---|---|---|---|---|---|
| primary | vultr | `722acde7-2825-44a7-8374-5700cba1c598` | 2026-11-06T06:38:06+00:00 | 2026-11-06T06:39:48+00:00 | GET /v2/instances/{id} -> 404 | gvisor runsc --platform=systrap | default-deny |
| verifier | vultr | `ff70a726-390d-4f22-8951-f0821fee6810` | 2026-11-06T06:38:07+00:00 | 2026-11-06T06:39:47+00:00 | GET /v2/instances/{id} -> 404 | gvisor runsc --platform=systrap | default-deny |

All VMs destroyed: **yes**

## Plan

Aggregate the amount column by region from /work/input/sales.csv and write summary.json to /work/out/.  
Planner model: `glm-5.3`; est. cost $0.0100; required domains: none

## Steps

| Step | Kind | Exit | Duration | stdout sha256 | Output files | Executor |
|---|---|---|---|---|---|---|
| 1 Sum amount per region and write summary.json | python | 0 | 0.12s | `b2afba68bc30` | summary.json `834fc0e2acc4` | gvisor-systrap |

## Verification

- **Verdict:** PASSED (model: `qwen3.8-27b`)
- **Independent re-run:** performed; hashes identical: True
  - [x] 1:exit_code exit_code=0
  - [x] 1:output:summary.json present
  - [x] assert:file_exists:summary.json
  - [x] rerun:hashes_identical all outputs byte-identical across two clean sandboxes
- **Model review:** satisfies_task=True confidence=0.97
  - Correct totals: north=15.0 (10+5), south=20.0, west=2.5
  - Output file summary.json written with proper JSON structure
  - All regions from input are accounted for

## Egress

Policy: default-deny. Allowed domains: none.  
Attempts: 4 (denied 4, allowed 0)
- 2026-11-06T06:39:19.130756+00:00 DENIED udp 108.61.10.10:53
- 2026-11-06T06:39:19.130763+00:00 DENIED udp 108.61.115.10:53
- 2026-11-06T06:39:19.130763+00:00 DENIED udp 108.61.10.10:53
- 2026-11-06T06:39:19.131747+00:00 DENIED udp 108.61.115.10:53

## Secret hygiene

- Result: **CLEAN** (20 files, 16 env vars, scanner `brz_runner.secretscan`)

## Cost

- **Total:** $0.0176 (VM $0.0160, tokens $0.0016); budget $0.25 -> within
  - planner: $0.00133
  - VM verifier vhp-1c-1gb-amd: $0.00800
  - verifier: $0.00026
  - VM primary vhp-1c-1gb-amd: $0.00800

## Audit chain

28 events, head `63e39d93dbe3dbbb3c025d50576a342893222e1b277549f93faf7bbc49d7d9cb`, verification: OK

| # | Time | Event | Hash |
|---|---|---|---|
| 0 | 2026-11-06T06:38:03.303219+00:00 | task.received | `f04e98870a6aad8d` |
| 1 | 2026-11-06T06:38:03.349115+00:00 | task.planning | `fb972bcf9ad85036` |
| 2 | 2026-11-06T06:38:05.652867+00:00 | cost.tokens | `5e7e380458922ea7` |
| 3 | 2026-11-06T06:38:05.653334+00:00 | plan.created | `5fc22e36ad42d04e` |
| 4 | 2026-11-06T06:38:05.654422+00:00 | budget.preflight | `7ab11bbd5e1751d6` |
| 5 | 2026-11-06T06:38:05.655165+00:00 | task.provisioning | `0997de2750a76455` |
| 6 | 2026-11-06T06:38:05.705894+00:00 | task.provisioning | `b7d287c019d03fb0` |
| 7 | 2026-11-06T06:38:37.292660+00:00 | vm.created | `8f78402f336cb313` |
| 8 | 2026-11-06T06:38:38.780264+00:00 | vm.created | `87bcf96017a7c6aa` |
| 9 | 2026-11-06T06:39:45.474261+00:00 | vm.runner_ready | `3b106388b8227dcf` |
| 10 | 2026-11-06T06:39:45.474399+00:00 | task.running | `fa29ea6af60c66b6` |
| 11 | 2026-11-06T06:39:45.612822+00:00 | egress.denied | `360ae0bac8726246` |
| 12 | 2026-11-06T06:39:45.612988+00:00 | egress.denied | `e326aa625b2faee6` |
| 13 | 2026-11-06T06:39:45.613058+00:00 | egress.denied | `1bdbf8519ff36560` |
| 14 | 2026-11-06T06:39:45.613111+00:00 | egress.denied | `77b19b888813b41b` |
| 15 | 2026-11-06T06:39:45.613174+00:00 | step.finished | `a13bff86a24a1beb` |
| 16 | 2026-11-06T06:39:45.615455+00:00 | task.verifying | `827b58b75bb750dd` |
| 17 | 2026-11-06T06:39:47.008910+00:00 | vm.runner_ready | `98f7f243c59d34d1` |
| 18 | 2026-11-06T06:39:47.140317+00:00 | step.finished | `25a5713a169ffcad` |
| 19 | 2026-11-06T06:39:47.142001+00:00 | task.destroying | `37465980b7882046` |
| 20 | 2026-11-06T06:39:47.712010+00:00 | vm.destroyed | `bf16bb421bdc53ce` |
| 21 | 2026-11-06T06:39:48.632538+00:00 | cost.tokens | `bef2729906426827` |
| 22 | 2026-11-06T06:39:48.632687+00:00 | verify.verdict | `ee2fd05576978449` |
| 23 | 2026-11-06T06:39:48.632833+00:00 | task.scanning | `22d3b4782cbc88c9` |
| 24 | 2026-11-06T06:39:48.646606+00:00 | secret_scan.done | `706f5e5a8eeb2f67` |
| 25 | 2026-11-06T06:39:48.646734+00:00 | task.destroying | `80a991e65ca3e05f` |
| 26 | 2026-11-06T06:39:48.909694+00:00 | vm.destroyed | `73d8637b8134845b` |
| 27 | 2026-11-06T06:39:48.913666+00:00 | task.verified | `63e39d93dbe3dbbb` |
