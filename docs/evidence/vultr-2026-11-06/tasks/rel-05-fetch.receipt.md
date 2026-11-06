# Ashproof receipt `0fdf515c80d3`

- **Status:** VERIFIED
- **Created:** 2026-11-06T07:11:58.478642+00:00
- **Task:** Fetch https://example.com and write the text of its title tag to title.txt
- **Task sha256:** `b55c2f72d0269a1a0811e890fc2e751883be984d5c6d12f2f9e73c5883149cd5`
- **Receipt sha256:** `0736a8cab272679086b0dc3f88220ee699d64171e2fdf226646cea2ec55f7a09`
- **Receipt integrity:** OK

## Blast radius

| Sandbox | Provider | Instance | Created | Destroyed | Proof | Inner layer | Egress |
|---|---|---|---|---|---|---|---|
| primary | vultr | `d7d4b7d9-9e7d-4aa9-a3bc-5014b4fef76d` | 2026-11-06T07:10:14+00:00 | 2026-11-06T07:11:58+00:00 | GET /v2/instances/{id} -> 404 | gvisor runsc --platform=systrap | default-deny |
| verifier | vultr | `dc5a7346-1a7b-42cb-b155-981c08e3cc86` | 2026-11-06T07:10:15+00:00 | 2026-11-06T07:11:56+00:00 | GET /v2/instances/{id} -> 404 | gvisor runsc --platform=systrap | default-deny |

All VMs destroyed: **yes**

## Plan

Fetch https://example.com and write the content of its <title> tag to /work/out/title.txt.  
Planner model: `glm-5.3`; est. cost $0.0200; required domains: example.com

## Steps

| Step | Kind | Exit | Duration | stdout sha256 | Output files | Executor |
|---|---|---|---|---|---|---|
| fetch_title Fetch example.com and extract title | python | 0 | 0.22s | `aa57cf1d596d` | title.txt `aa57cf1d596d` | gvisor-systrap |

## Verification

- **Verdict:** PASSED (model: `qwen3.8-27b`)
- **Independent re-run:** performed; hashes identical: True
  - [x] fetch_title:exit_code exit_code=0
  - [x] fetch_title:output:title.txt present
  - [x] assert:file_exists:title.txt
  - [x] assert:file_contains:title.txt:Example Domain
  - [x] rerun:hashes_identical all outputs byte-identical across two clean sandboxes
- **Model review:** satisfies_task=True confidence=0.95
  - The file title.txt was created with content 'Example Domain\n'
  - This is the correct and well-known title of https://example.com
  - Exit code 0 indicates the fetch and write operation succeeded
  - The task requirement to write the title tag text to title.txt is met
  - concern: The plan mentioned path /work/out/title.txt but the evidence only shows 'title.txt' — however the task itself only specifies 'title.txt' so this is acceptable

## Egress

Policy: default-deny. Allowed domains: example.com.  
Attempts: 2 (denied 0, allowed 2)
- 2026-11-06T07:11:53+00:00 ALLOWED tcp 104.20.23.154:443
- 2026-11-06T07:11:55+00:00 ALLOWED tcp 104.20.23.154:443

## Secret hygiene

- Result: **CLEAN** (20 files, 16 env vars, scanner `brz_runner.secretscan`)

## Cost

- **Total:** $0.0178 (VM $0.0160, tokens $0.0018); budget $0.25 -> within
  - planner: $0.00138
  - VM verifier vhp-1c-1gb-amd: $0.00800
  - verifier: $0.00042
  - VM primary vhp-1c-1gb-amd: $0.00800

## Audit chain

26 events, head `bcb0e4cd16eaf25fed190e6073c2e96ee39c1831dfc420dcc2f9dfe336ce65a7`, verification: OK

| # | Time | Event | Hash |
|---|---|---|---|
| 0 | 2026-11-06T07:10:09.315637+00:00 | task.received | `3b4cd28f5d7032ed` |
| 1 | 2026-11-06T07:10:09.317015+00:00 | task.planning | `9ffd4b842cb28351` |
| 2 | 2026-11-06T07:10:13.386675+00:00 | cost.tokens | `d06c2f9fd71ae9b1` |
| 3 | 2026-11-06T07:10:13.386813+00:00 | plan.created | `8a0e66c27c0c2328` |
| 4 | 2026-11-06T07:10:13.386949+00:00 | budget.preflight | `821ea4d0b463d9ac` |
| 5 | 2026-11-06T07:10:13.387038+00:00 | task.provisioning | `f8ebb91c68da380a` |
| 6 | 2026-11-06T07:10:13.392280+00:00 | task.provisioning | `8216ae61f760130c` |
| 7 | 2026-11-06T07:10:46.088877+00:00 | vm.created | `03bf79c34e3d7bcf` |
| 8 | 2026-11-06T07:10:47.807011+00:00 | vm.created | `96580a1ad0e44862` |
| 9 | 2026-11-06T07:11:54.177152+00:00 | vm.runner_ready | `90f560674a316435` |
| 10 | 2026-11-06T07:11:54.177283+00:00 | task.running | `d729d8df4a44de3b` |
| 11 | 2026-11-06T07:11:54.407868+00:00 | egress.allowed | `f5fcd8942fa979cf` |
| 12 | 2026-11-06T07:11:54.407970+00:00 | step.finished | `17a3532788820f70` |
| 13 | 2026-11-06T07:11:54.408104+00:00 | task.verifying | `07d60c224dfcab48` |
| 14 | 2026-11-06T07:11:56.223330+00:00 | vm.runner_ready | `3c2d14a6a06aa028` |
| 15 | 2026-11-06T07:11:56.454044+00:00 | egress.allowed | `49bbf26d6204302b` |
| 16 | 2026-11-06T07:11:56.454148+00:00 | step.finished | `04672938d97d4f21` |
| 17 | 2026-11-06T07:11:56.454266+00:00 | task.destroying | `5c403f5e017635ea` |
| 18 | 2026-11-06T07:11:56.789685+00:00 | vm.destroyed | `50ba9ee911b71fff` |
| 19 | 2026-11-06T07:11:57.955667+00:00 | cost.tokens | `ae19c1d4d2d94cf3` |
| 20 | 2026-11-06T07:11:57.955789+00:00 | verify.verdict | `441773a6d88de041` |
| 21 | 2026-11-06T07:11:57.955914+00:00 | task.scanning | `d054b5fdcad5c046` |
| 22 | 2026-11-06T07:11:57.969087+00:00 | secret_scan.done | `acfcadf6a96e3229` |
| 23 | 2026-11-06T07:11:57.969196+00:00 | task.destroying | `95053d9f9758f70b` |
| 24 | 2026-11-06T07:11:58.476697+00:00 | vm.destroyed | `69b0746b1c2fcaab` |
| 25 | 2026-11-06T07:11:58.478283+00:00 | task.verified | `bcb0e4cd16eaf25f` |
