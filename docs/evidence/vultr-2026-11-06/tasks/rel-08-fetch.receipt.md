# Ashproof receipt `8f82054b04a7`

- **Status:** VERIFIED
- **Created:** 2026-11-06T07:18:15.520294+00:00
- **Task:** Fetch https://example.com and write the text of its title tag to title.txt
- **Task sha256:** `b55c2f72d0269a1a0811e890fc2e751883be984d5c6d12f2f9e73c5883149cd5`
- **Receipt sha256:** `e580c0e7265c6e1773fab9df7fb7a1844e63013e1d9b84e512f2fba1e02ad9ce`
- **Receipt integrity:** OK

## Blast radius

| Sandbox | Provider | Instance | Created | Destroyed | Proof | Inner layer | Egress |
|---|---|---|---|---|---|---|---|
| verifier | vultr | `e0b44128-7d59-4c16-a24d-85cbd9e2d488` | 2026-11-06T07:16:29+00:00 | 2026-11-06T07:18:14+00:00 | GET /v2/instances/{id} -> 404 | gvisor runsc --platform=systrap | default-deny |
| primary | vultr | `cdf38e70-92ec-4447-b016-cd8b43be8bca` | 2026-11-06T07:16:34+00:00 | 2026-11-06T07:18:15+00:00 | GET /v2/instances/{id} -> 404 | gvisor runsc --platform=systrap | default-deny |

All VMs destroyed: **yes**

## Plan

Fetch https://example.com and write its <title> text to /work/out/title.txt.  
Planner model: `glm-5.3`; est. cost $0.0100; required domains: example.com

## Steps

| Step | Kind | Exit | Duration | stdout sha256 | Output files | Executor |
|---|---|---|---|---|---|---|
| fetch_title Fetch example.com and extract title | shell | 0 | 0.17s | `e3b0c44298fc` | title.txt `aa57cf1d596d` | gvisor-systrap |

## Verification

- **Verdict:** PASSED (model: `qwen3.8-27b`)
- **Independent re-run:** performed; hashes identical: True
  - [x] fetch_title:exit_code exit_code=0
  - [x] fetch_title:output:title.txt present
  - [x] assert:file_exists:title.txt
  - [x] assert:file_contains:title.txt:Example Domain
  - [x] rerun:hashes_identical all outputs byte-identical across two clean sandboxes
- **Model review:** satisfies_task=True confidence=0.95
  - The file title.txt contains 'Example Domain\n', which is the correct <title> text of https://example.com.
  - Exit code 0 indicates the fetch/write step succeeded.
  - The input_files (sales.csv) are irrelevant to this task and do not affect the outcome.

## Egress

Policy: default-deny. Allowed domains: example.com.  
Attempts: 2 (denied 0, allowed 2)
- 2026-11-06T07:18:13+00:00 ALLOWED tcp 104.20.23.154:443
- 2026-11-06T07:18:12+00:00 ALLOWED tcp 104.20.23.154:443

## Secret hygiene

- Result: **CLEAN** (20 files, 16 env vars, scanner `brz_runner.secretscan`)

## Cost

- **Total:** $0.0175 (VM $0.0160, tokens $0.0015); budget $0.25 -> within
  - planner: $0.00118
  - VM verifier vhp-1c-1gb-amd: $0.00800
  - verifier: $0.00036
  - VM primary vhp-1c-1gb-amd: $0.00800

## Audit chain

26 events, head `f5c668b6bddf59d6a41a0c6f1ffb50411e8e7279ba1cfa1b95aadae1858cd931`, verification: OK

| # | Time | Event | Hash |
|---|---|---|---|
| 0 | 2026-11-06T07:16:26.383012+00:00 | task.received | `f08ba5a4c6553e37` |
| 1 | 2026-11-06T07:16:26.384686+00:00 | task.planning | `231c00a8bbf06067` |
| 2 | 2026-11-06T07:16:28.301179+00:00 | cost.tokens | `25ac1c951cc64100` |
| 3 | 2026-11-06T07:16:28.301356+00:00 | plan.created | `7a79c8680ec3b1e6` |
| 4 | 2026-11-06T07:16:28.301539+00:00 | budget.preflight | `ce88ea1fad0e862d` |
| 5 | 2026-11-06T07:16:28.301648+00:00 | task.provisioning | `179136388a52d41d` |
| 6 | 2026-11-06T07:16:28.306383+00:00 | task.provisioning | `73688e3f727c97e4` |
| 7 | 2026-11-06T07:17:01.202839+00:00 | vm.created | `1b688939be227133` |
| 8 | 2026-11-06T07:17:05.295191+00:00 | vm.created | `e48cb2d4eddaf647` |
| 9 | 2026-11-06T07:18:09.472047+00:00 | vm.runner_ready | `95dfed1db3016400` |
| 10 | 2026-11-06T07:18:13.565975+00:00 | vm.runner_ready | `f1c5fd06b046dad4` |
| 11 | 2026-11-06T07:18:13.566115+00:00 | task.running | `0b6408b69b83b48a` |
| 12 | 2026-11-06T07:18:13.743714+00:00 | egress.allowed | `d111d571790e7221` |
| 13 | 2026-11-06T07:18:13.743840+00:00 | step.finished | `c1bc9c31676c72d7` |
| 14 | 2026-11-06T07:18:13.744034+00:00 | task.verifying | `4a24edf6d40cf774` |
| 15 | 2026-11-06T07:18:13.924953+00:00 | egress.allowed | `20f1d360a693294e` |
| 16 | 2026-11-06T07:18:13.925057+00:00 | step.finished | `5f8b00f94791a6c3` |
| 17 | 2026-11-06T07:18:13.925177+00:00 | task.destroying | `057b140ace39d4c4` |
| 18 | 2026-11-06T07:18:14.297496+00:00 | vm.destroyed | `2e51f374d906826d` |
| 19 | 2026-11-06T07:18:15.224359+00:00 | cost.tokens | `685fe9582f3ba0a7` |
| 20 | 2026-11-06T07:18:15.224478+00:00 | verify.verdict | `c362530cb7a05495` |
| 21 | 2026-11-06T07:18:15.224602+00:00 | task.scanning | `ad34c4e66c353cfa` |
| 22 | 2026-11-06T07:18:15.237769+00:00 | secret_scan.done | `6ec55bbaf60cc68a` |
| 23 | 2026-11-06T07:18:15.237895+00:00 | task.destroying | `beb3dee34c04e81f` |
| 24 | 2026-11-06T07:18:15.518009+00:00 | vm.destroyed | `e273e5992a141738` |
| 25 | 2026-11-06T07:18:15.519909+00:00 | task.verified | `f5c668b6bddf59d6` |
