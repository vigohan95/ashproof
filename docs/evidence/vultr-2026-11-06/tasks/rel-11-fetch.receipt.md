# Ashproof receipt `b703b535fcb9`

- **Status:** VERIFIED
- **Created:** 2026-11-06T07:24:15.720617+00:00
- **Task:** Fetch https://example.com and write the text of its title tag to title.txt
- **Task sha256:** `b55c2f72d0269a1a0811e890fc2e751883be984d5c6d12f2f9e73c5883149cd5`
- **Receipt sha256:** `2a3b7d2728086c4e53b427fbedc70db524f5a6c48690e00b222b76a808272dbb`
- **Receipt integrity:** OK

## Blast radius

| Sandbox | Provider | Instance | Created | Destroyed | Proof | Inner layer | Egress |
|---|---|---|---|---|---|---|---|
| primary | vultr | `4abc6bfa-bb94-442f-a32f-c4b7ad3a4bdb` | 2026-11-06T07:22:26+00:00 | 2026-11-06T07:24:15+00:00 | GET /v2/instances/{id} -> 404 | gvisor runsc --platform=systrap | default-deny |
| verifier | vultr | `89346bd6-cfe3-4f90-8d6d-68c8cd264d08` | 2026-11-06T07:22:28+00:00 | 2026-11-06T07:24:12+00:00 | GET /v2/instances/{id} -> 404 | gvisor runsc --platform=systrap | default-deny |

All VMs destroyed: **yes**

## Plan

Fetch https://example.com and write the contents of its <title> tag to /work/out/title.txt.  
Planner model: `glm-5.3`; est. cost $0.0200; required domains: example.com

## Steps

| Step | Kind | Exit | Duration | stdout sha256 | Output files | Executor |
|---|---|---|---|---|---|---|
| fetch_title Fetch example.com and extract the title tag | python | 0 | 0.22s | `3a96d6195ad4` | title.txt `aa57cf1d596d` | gvisor-systrap |

## Verification

- **Verdict:** PASSED (model: `qwen3.8-27b`)
- **Independent re-run:** performed; hashes identical: True
  - [x] fetch_title:exit_code exit_code=0
  - [x] fetch_title:output:title.txt present
  - [x] assert:file_exists:title.txt
  - [x] assert:file_contains:title.txt:Example Domain
  - [x] rerun:hashes_identical all outputs byte-identical across two clean sandboxes
- **Model review:** satisfies_task=True confidence=0.95
  - The step completed with exit_code 0
  - The extracted title 'Example Domain' is the correct and well-known title of https://example.com
  - The file title.txt was written with the content 'Example Domain\n', which matches the title tag text
  - The irrelevant input file (sales.csv) does not affect this task
  - concern: The evidence does not show the actual HTTP fetch command or its raw output, so we rely on the correctness of the known title for example.com
  - concern: The plan mentions writing to /work/out/title.txt but the evidence shows the file as 'title.txt' (relative path) — minor path discrepancy but the file content is correct

## Egress

Policy: default-deny. Allowed domains: example.com.  
Attempts: 2 (denied 0, allowed 2)
- 2026-11-06T07:24:10+00:00 ALLOWED tcp 104.20.23.154:443
- 2026-11-06T07:24:11+00:00 ALLOWED tcp 104.20.23.154:443

## Secret hygiene

- Result: **CLEAN** (20 files, 16 env vars, scanner `brz_runner.secretscan`)

## Cost

- **Total:** $0.0181 (VM $0.0160, tokens $0.0021); budget $0.25 -> within
  - planner: $0.00152
  - VM verifier vhp-1c-1gb-amd: $0.00800
  - verifier: $0.00054
  - VM primary vhp-1c-1gb-amd: $0.00800

## Audit chain

26 events, head `503dc98c529dca2a573735cfecfa958b2be9cc01ce9c5b93e71bb1501271983b`, verification: OK

| # | Time | Event | Hash |
|---|---|---|---|
| 0 | 2026-11-06T07:22:23.118869+00:00 | task.received | `09f70399c174fd78` |
| 1 | 2026-11-06T07:22:23.120503+00:00 | task.planning | `96a5a3239eab5efb` |
| 2 | 2026-11-06T07:22:25.817375+00:00 | cost.tokens | `9dcdc840dd5bb207` |
| 3 | 2026-11-06T07:22:25.817559+00:00 | plan.created | `8450cfd5b66eb3ee` |
| 4 | 2026-11-06T07:22:25.817735+00:00 | budget.preflight | `fca0d2c0b1462e73` |
| 5 | 2026-11-06T07:22:25.817834+00:00 | task.provisioning | `57a60b72fafa9920` |
| 6 | 2026-11-06T07:22:25.823296+00:00 | task.provisioning | `d2f8fff91063d270` |
| 7 | 2026-11-06T07:22:59.254555+00:00 | vm.created | `7756d3f7a916e5dc` |
| 8 | 2026-11-06T07:23:03.271076+00:00 | vm.created | `1cf6aef8930c14ad` |
| 9 | 2026-11-06T07:24:07.358105+00:00 | vm.runner_ready | `40420aca4b2d8ec7` |
| 10 | 2026-11-06T07:24:11.455821+00:00 | vm.runner_ready | `30b2e2bc0d95faad` |
| 11 | 2026-11-06T07:24:11.455952+00:00 | task.running | `cd1f3c803cbf9840` |
| 12 | 2026-11-06T07:24:11.685704+00:00 | egress.allowed | `e8746b7bb6370be8` |
| 13 | 2026-11-06T07:24:11.685870+00:00 | step.finished | `aa53e6f3ae7bab35` |
| 14 | 2026-11-06T07:24:11.686126+00:00 | task.verifying | `0b470f35ada0a310` |
| 15 | 2026-11-06T07:24:11.966399+00:00 | egress.allowed | `430c1014ead183de` |
| 16 | 2026-11-06T07:24:11.966514+00:00 | step.finished | `d57904e51b2aa071` |
| 17 | 2026-11-06T07:24:11.966688+00:00 | task.destroying | `b256f6d47ae3955d` |
| 18 | 2026-11-06T07:24:12.924526+00:00 | vm.destroyed | `fa99ebfc70c2bbeb` |
| 19 | 2026-11-06T07:24:14.970623+00:00 | cost.tokens | `b806a35092698296` |
| 20 | 2026-11-06T07:24:14.970763+00:00 | verify.verdict | `484180c3c3046ba4` |
| 21 | 2026-11-06T07:24:14.970897+00:00 | task.scanning | `7b6c0a0130f49d9f` |
| 22 | 2026-11-06T07:24:14.986811+00:00 | secret_scan.done | `401dedf0249da1b8` |
| 23 | 2026-11-06T07:24:14.986973+00:00 | task.destroying | `9a6d2d64272306dc` |
| 24 | 2026-11-06T07:24:15.718704+00:00 | vm.destroyed | `7466e5f433d5003e` |
| 25 | 2026-11-06T07:24:15.720309+00:00 | task.verified | `503dc98c529dca2a` |
