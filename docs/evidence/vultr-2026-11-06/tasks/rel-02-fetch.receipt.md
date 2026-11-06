# Ashproof receipt `8939a9e2586a`

- **Status:** VERIFIED
- **Created:** 2026-11-06T07:03:50.402488+00:00
- **Task:** Fetch https://example.com and write the text of its title tag to title.txt
- **Task sha256:** `b55c2f72d0269a1a0811e890fc2e751883be984d5c6d12f2f9e73c5883149cd5`
- **Receipt sha256:** `4bb8bb82ec60962794ce696e0242097590bd235d64a7389ba5fe921c86d7c7fc`
- **Receipt integrity:** OK

## Blast radius

| Sandbox | Provider | Instance | Created | Destroyed | Proof | Inner layer | Egress |
|---|---|---|---|---|---|---|---|
| verifier | vultr | `d78a05d7-a7f1-42e7-8b86-59e569368433` | 2026-11-06T07:01:55+00:00 | 2026-11-06T07:03:49+00:00 | GET /v2/instances/{id} -> 404 | gvisor runsc --platform=systrap | default-deny |
| primary | vultr | `8c58fa5d-4288-41ac-b0f9-23d675f01d92` | 2026-11-06T07:02:07+00:00 | 2026-11-06T07:03:50+00:00 | GET /v2/instances/{id} -> 404 | gvisor runsc --platform=systrap | default-deny |

All VMs destroyed: **yes**

## Plan

Fetch https://example.com and extract the <title> text into title.txt  
Planner model: `glm-5.3`; est. cost $0.0200; required domains: example.com

## Steps

| Step | Kind | Exit | Duration | stdout sha256 | Output files | Executor |
|---|---|---|---|---|---|---|
| fetch_title Fetch example.com and extract title | python | 0 | 0.27s | `aa57cf1d596d` | title.txt `aa57cf1d596d` | gvisor-systrap |

## Verification

- **Verdict:** PASSED (model: `qwen3.8-27b`)
- **Independent re-run:** performed; hashes identical: True
  - [x] fetch_title:exit_code exit_code=0
  - [x] fetch_title:output:title.txt present
  - [x] assert:file_exists:title.txt
  - [x] assert:file_contains:title.txt:Example Domain
  - [x] rerun:hashes_identical all outputs byte-identical across two clean sandboxes
- **Model review:** satisfies_task=True confidence=0.95
  - The title of https://example.com is well-known to be 'Example Domain'
  - title.txt was created with the correct content 'Example Domain'
  - Exit code 0 with no stderr indicates successful execution
  - The output matches the expected <title> text from example.com

## Egress

Policy: default-deny. Allowed domains: example.com.  
Attempts: 2 (denied 0, allowed 2)
- 2026-11-06T07:03:47+00:00 ALLOWED tcp 104.20.23.154:443
- 2026-11-06T07:03:48+00:00 ALLOWED tcp 104.20.23.154:443

## Secret hygiene

- Result: **CLEAN** (20 files, 16 env vars, scanner `brz_runner.secretscan`)

## Cost

- **Total:** $0.0176 (VM $0.0160, tokens $0.0016); budget $0.25 -> within
  - planner: $0.00131
  - VM verifier vhp-1c-1gb-amd: $0.00800
  - verifier: $0.00032
  - VM primary vhp-1c-1gb-amd: $0.00800

## Audit chain

26 events, head `86c8d29b5a7e3be69a8186882314181ed3481d80d525976adafac67e968a7db6`, verification: OK

| # | Time | Event | Hash |
|---|---|---|---|
| 0 | 2026-11-06T07:01:50.741404+00:00 | task.received | `fec5009ec02447d3` |
| 1 | 2026-11-06T07:01:50.743711+00:00 | task.planning | `8a5c419766f27d0a` |
| 2 | 2026-11-06T07:01:54.353570+00:00 | cost.tokens | `7667b7d21a84b598` |
| 3 | 2026-11-06T07:01:54.353736+00:00 | plan.created | `0070e98ebd8d306a` |
| 4 | 2026-11-06T07:01:54.353899+00:00 | budget.preflight | `e8ffa4e0b3f907cf` |
| 5 | 2026-11-06T07:01:54.353987+00:00 | task.provisioning | `d846d07c0ad01f0b` |
| 6 | 2026-11-06T07:01:54.359109+00:00 | task.provisioning | `bc096395c5686240` |
| 7 | 2026-11-06T07:02:32.132167+00:00 | vm.created | `deebdec5e21145fa` |
| 8 | 2026-11-06T07:02:39.919502+00:00 | vm.created | `c0ce1d11f8b7ae85` |
| 9 | 2026-11-06T07:03:40.098000+00:00 | vm.runner_ready | `d388253d9d8ae576` |
| 10 | 2026-11-06T07:03:48.285945+00:00 | vm.runner_ready | `a69850ff631d0ff4` |
| 11 | 2026-11-06T07:03:48.286078+00:00 | task.running | `220af0977f1ff0f6` |
| 12 | 2026-11-06T07:03:48.564569+00:00 | egress.allowed | `ee2ff1a6d06ba9f9` |
| 13 | 2026-11-06T07:03:48.564737+00:00 | step.finished | `31f83e788ffe95a4` |
| 14 | 2026-11-06T07:03:48.564905+00:00 | task.verifying | `390848dc7822b558` |
| 15 | 2026-11-06T07:03:48.795055+00:00 | egress.allowed | `0b9408dc079f61f7` |
| 16 | 2026-11-06T07:03:48.795180+00:00 | step.finished | `ca855599ba2a9642` |
| 17 | 2026-11-06T07:03:48.795319+00:00 | task.destroying | `b019fe5f2b51312e` |
| 18 | 2026-11-06T07:03:49.265411+00:00 | vm.destroyed | `520fb63242f85210` |
| 19 | 2026-11-06T07:03:50.150318+00:00 | cost.tokens | `bb890269f63f84df` |
| 20 | 2026-11-06T07:03:50.150445+00:00 | verify.verdict | `b75ae4b1da4e0245` |
| 21 | 2026-11-06T07:03:50.150558+00:00 | task.scanning | `9e024df845fe3dd6` |
| 22 | 2026-11-06T07:03:50.162829+00:00 | secret_scan.done | `437d013ca579948a` |
| 23 | 2026-11-06T07:03:50.162945+00:00 | task.destroying | `6c84223d4b6d97cd` |
| 24 | 2026-11-06T07:03:50.401735+00:00 | vm.destroyed | `8696ca49de0785d3` |
| 25 | 2026-11-06T07:03:50.402205+00:00 | task.verified | `86c8d29b5a7e3be6` |
