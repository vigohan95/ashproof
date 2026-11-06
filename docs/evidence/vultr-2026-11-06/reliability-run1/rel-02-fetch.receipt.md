# Ashproof receipt `44589de687c5`

- **Status:** VERIFIED
- **Created:** 2026-11-06T06:42:00.688842+00:00
- **Task:** Fetch https://example.com and write the text of its title tag to title.txt
- **Task sha256:** `b55c2f72d0269a1a0811e890fc2e751883be984d5c6d12f2f9e73c5883149cd5`
- **Receipt sha256:** `a76419dfe38b0007429ae13bebcad2259b4b26b929ac2dfa2828b037881ec667`
- **Receipt integrity:** OK

## Blast radius

| Sandbox | Provider | Instance | Created | Destroyed | Proof | Inner layer | Egress |
|---|---|---|---|---|---|---|---|
| primary | vultr | `779dc81f-78e8-4cdf-b4f4-8e6c62e15892` | 2026-11-06T06:39:56+00:00 | 2026-11-06T06:42:00+00:00 | GET /v2/instances/{id} -> 404 | gvisor runsc --platform=systrap | default-deny |
| verifier | vultr | `15dad487-b719-4176-b2c8-b2b0f7572f1f` | 2026-11-06T06:40:17+00:00 | 2026-11-06T06:41:59+00:00 | GET /v2/instances/{id} -> 404 | gvisor runsc --platform=systrap | default-deny |

All VMs destroyed: **yes**

## Plan

Fetch https://example.com and write the content of its <title> tag to /work/out/title.txt.  
Planner model: `glm-5.3`; est. cost $0.0100; required domains: example.com

## Steps

| Step | Kind | Exit | Duration | stdout sha256 | Output files | Executor |
|---|---|---|---|---|---|---|
| fetch_title Fetch example.com and extract title | python | 0 | 0.22s | `aa57cf1d596d` | title.txt `162b81548a8d` | gvisor-systrap |

## Verification

- **Verdict:** PASSED (model: `qwen3.8-27b`)
- **Independent re-run:** performed; hashes identical: True
  - [x] fetch_title:exit_code exit_code=0
  - [x] fetch_title:output:title.txt present
  - [x] assert:file_exists:title.txt
  - [x] assert:file_contains:title.txt:Example Domain
  - [x] rerun:hashes_identical all outputs byte-identical across two clean sandboxes
- **Model review:** satisfies_task=True confidence=0.95
  - The file title.txt contains 'Example Domain', which is the correct and well-known title of https://example.com.
  - Exit code 0 indicates the fetch and write operation succeeded.
  - The output file name matches the task requirement (title.txt).
  - concern: The plan referenced /work/out/title.txt but the evidence shows title.txt (path may differ but filename is correct).
  - concern: The input_files (sales.csv) are irrelevant to this task and appear to be a distractor.

## Egress

Policy: default-deny. Allowed domains: example.com.  
Attempts: 2 (denied 0, allowed 2)
- 2026-11-06T06:41:35+00:00 ALLOWED tcp 104.20.23.154:443
- 2026-11-06T06:41:58+00:00 ALLOWED tcp 104.20.23.154:443

## Secret hygiene

- Result: **CLEAN** (20 files, 16 env vars, scanner `brz_runner.secretscan`)

## Cost

- **Total:** $0.0178 (VM $0.0160, tokens $0.0018); budget $0.25 -> within
  - planner: $0.00130
  - VM verifier vhp-1c-1gb-amd: $0.00800
  - verifier: $0.00047
  - VM primary vhp-1c-1gb-amd: $0.00800

## Audit chain

26 events, head `0a04241ad87cae58e594d984f92a7cc253a93593cf17b27cb391b6c8f11264dd`, verification: OK

| # | Time | Event | Hash |
|---|---|---|---|
| 0 | 2026-11-06T06:39:53.284697+00:00 | task.received | `b3059a99193913a6` |
| 1 | 2026-11-06T06:39:53.288530+00:00 | task.planning | `2f204059882388ab` |
| 2 | 2026-11-06T06:39:55.421882+00:00 | cost.tokens | `6abcd42e518a47ee` |
| 3 | 2026-11-06T06:39:55.422082+00:00 | plan.created | `3f184d811f0d82b6` |
| 4 | 2026-11-06T06:39:55.422251+00:00 | budget.preflight | `2ab2353c865f7d14` |
| 5 | 2026-11-06T06:39:55.422376+00:00 | task.provisioning | `188111bd4bfb7dff` |
| 6 | 2026-11-06T06:39:55.427832+00:00 | task.provisioning | `2e0ac970106a6bab` |
| 7 | 2026-11-06T06:40:28.132067+00:00 | vm.created | `2fd9ebabc17ac9f7` |
| 8 | 2026-11-06T06:40:50.167118+00:00 | vm.created | `2075758bc14757d0` |
| 9 | 2026-11-06T06:41:36.064724+00:00 | vm.runner_ready | `c58ab3366e26a0ad` |
| 10 | 2026-11-06T06:41:36.064870+00:00 | task.running | `a19aa254db311e5a` |
| 11 | 2026-11-06T06:41:36.296619+00:00 | egress.allowed | `7a7af21eb705dea0` |
| 12 | 2026-11-06T06:41:36.296714+00:00 | step.finished | `29b735443cfb3641` |
| 13 | 2026-11-06T06:41:36.296889+00:00 | task.verifying | `d84ab7498275fa3d` |
| 14 | 2026-11-06T06:41:58.595041+00:00 | vm.runner_ready | `e9abaa12308d3c47` |
| 15 | 2026-11-06T06:41:58.875490+00:00 | egress.allowed | `aaaeed116837959d` |
| 16 | 2026-11-06T06:41:58.875741+00:00 | step.finished | `0227f9a04f274f92` |
| 17 | 2026-11-06T06:41:58.875950+00:00 | task.destroying | `77889d462a940d0c` |
| 18 | 2026-11-06T06:41:59.213070+00:00 | vm.destroyed | `a8dd958f2d4438ed` |
| 19 | 2026-11-06T06:42:00.355558+00:00 | cost.tokens | `72a51b7a4dee8a02` |
| 20 | 2026-11-06T06:42:00.355768+00:00 | verify.verdict | `764263c22cf414ce` |
| 21 | 2026-11-06T06:42:00.355958+00:00 | task.scanning | `f1e1c71c0b012cee` |
| 22 | 2026-11-06T06:42:00.372448+00:00 | secret_scan.done | `5edfd6d9d81dec61` |
| 23 | 2026-11-06T06:42:00.372766+00:00 | task.destroying | `6f0ed9ae98adbb38` |
| 24 | 2026-11-06T06:42:00.685876+00:00 | vm.destroyed | `32ea83ad4c3f932c` |
| 25 | 2026-11-06T06:42:00.688368+00:00 | task.verified | `0a04241ad87cae58` |
