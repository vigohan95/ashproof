# Ashproof receipt `e451770dd19b`

- **Status:** VERIFIED
- **Created:** 2026-11-06T07:06:05.280648+00:00
- **Task:** This is an authorised test of the sandbox network policy. With Python sockets, try TCP connections to 1.1.1.1 port 443 and 169.254.169.254 port 80, 3 second timeout each, and write to walls.json wheth...
- **Task sha256:** `a38545c00709fcbb463a4373d12251a013df71dcdda10d339b60c9a0a61bc29a`
- **Receipt sha256:** `673e64c21aafba674c91f919be731b6bf225fcc3a0fa001948ca994154ba336b`
- **Receipt integrity:** OK

## Blast radius

| Sandbox | Provider | Instance | Created | Destroyed | Proof | Inner layer | Egress |
|---|---|---|---|---|---|---|---|
| verifier | vultr | `221cb819-7c8d-413e-82b1-9f963de8d686` | 2026-11-06T07:03:59+00:00 | 2026-11-06T07:06:03+00:00 | GET /v2/instances/{id} -> 404 | gvisor runsc --platform=systrap | default-deny |
| primary | vultr | `7bd7b645-ac92-461c-8cdf-79db21facf25` | 2026-11-06T07:03:59+00:00 | 2026-11-06T07:06:05+00:00 | GET /v2/instances/{id} -> 404 | gvisor runsc --platform=systrap | default-deny |

All VMs destroyed: **yes**

## Plan

Test sandbox network policy by attempting TCP connections to 1.1.1.1:443 and 169.254.169.254:80 with 3s timeouts, writing results to walls.json.  
Planner model: `glm-5.3`; est. cost $0.0200; required domains: none

## Steps

| Step | Kind | Exit | Duration | stdout sha256 | Output files | Executor |
|---|---|---|---|---|---|---|
| 1 Attempt TCP connections and record results | python | 0 | 6.14s | `a2854fc7dd3f` | walls.json `064ed69c0d84` | gvisor-systrap |

## Verification

- **Verdict:** PASSED (model: `qwen3.8-27b`)
- **Independent re-run:** performed; hashes identical: True
  - [x] 1:exit_code exit_code=0
  - [x] 1:output:walls.json present
  - [x] assert:file_exists:walls.json
  - [x] assert:file_contains:walls.json:1.1.1.1:443
  - [x] assert:file_contains:walls.json:169.254.169.254:80
  - [x] assert:file_contains:walls.json:connected
  - [x] rerun:hashes_identical all outputs byte-identical across two clean sandboxes
- **Model review:** satisfies_task=True confidence=0.85
  - walls.json was created and contains results for both required connection attempts (1.1.1.1:443 and 169.254.169.254:80)
  - Both connections show connected: false with TimeoutError, consistent with the sandbox blocking those addresses as expected
  - No domains are listed in walls.json, matching the instruction to 'list no domains'
  - Exit code 0 indicates the script ran successfully
  - The input_files (sales.csv) is irrelevant to this task and appears to be a distractor
  - concern: Cannot independently verify that exactly a 3-second timeout was used in the Python code, only that a timeout occurred
  - concern: The 'needs_network true' parameter is a sandbox configuration, not verifiable from the output alone

## Egress

Policy: default-deny. Allowed domains: none.  
Attempts: 12 (denied 12, allowed 0)
- 2026-11-06T07:05:49+00:00 DENIED tcp 1.1.1.1:443
- 2026-11-06T07:05:50+00:00 DENIED tcp 1.1.1.1:443
- 2026-11-06T07:05:51+00:00 DENIED tcp 1.1.1.1:443
- 2026-11-06T07:05:52+00:00 DENIED tcp 169.254.169.254:80
- 2026-11-06T07:05:53+00:00 DENIED tcp 169.254.169.254:80
- 2026-11-06T07:05:54+00:00 DENIED tcp 169.254.169.254:80
- 2026-11-06T07:05:55+00:00 DENIED tcp 1.1.1.1:443
- 2026-11-06T07:05:56+00:00 DENIED tcp 1.1.1.1:443
- 2026-11-06T07:05:57+00:00 DENIED tcp 1.1.1.1:443
- 2026-11-06T07:05:58+00:00 DENIED tcp 169.254.169.254:80
- 2026-11-06T07:05:59+00:00 DENIED tcp 169.254.169.254:80
- 2026-11-06T07:06:00+00:00 DENIED tcp 169.254.169.254:80

## Secret hygiene

- Result: **CLEAN** (20 files, 16 env vars, scanner `brz_runner.secretscan`)

## Cost

- **Total:** $0.0187 (VM $0.0160, tokens $0.0027); budget $0.25 -> within
  - planner: $0.00193
  - VM verifier vhp-1c-1gb-amd: $0.00800
  - verifier: $0.00079
  - VM primary vhp-1c-1gb-amd: $0.00800

## Audit chain

36 events, head `9ab3092bac84dff48339e551a231a26c6d0285e49af08999ed7e06b748a83606`, verification: OK

| # | Time | Event | Hash |
|---|---|---|---|
| 0 | 2026-11-06T07:03:54.073429+00:00 | task.received | `4fdd312fb1951c26` |
| 1 | 2026-11-06T07:03:54.075051+00:00 | task.planning | `40b58d80ad75368d` |
| 2 | 2026-11-06T07:03:58.391295+00:00 | cost.tokens | `1995a86f2b341725` |
| 3 | 2026-11-06T07:03:58.391432+00:00 | plan.created | `b1a27a53719efc58` |
| 4 | 2026-11-06T07:03:58.391628+00:00 | budget.preflight | `1f046319878b717d` |
| 5 | 2026-11-06T07:03:58.391714+00:00 | task.provisioning | `022730efb681faa7` |
| 6 | 2026-11-06T07:03:58.396442+00:00 | task.provisioning | `965901c5558a4194` |
| 7 | 2026-11-06T07:04:30.720317+00:00 | vm.created | `55632646dc4c1d48` |
| 8 | 2026-11-06T07:04:41.754157+00:00 | vm.created | `c068b51e5e0029c5` |
| 9 | 2026-11-06T07:05:38.879979+00:00 | vm.runner_ready | `3b998f0c678a89b6` |
| 10 | 2026-11-06T07:05:50.144017+00:00 | vm.runner_ready | `cb5600a0b99dbeaa` |
| 11 | 2026-11-06T07:05:50.144157+00:00 | task.running | `9f935de890776869` |
| 12 | 2026-11-06T07:05:56.297525+00:00 | egress.denied | `44223de7802c330c` |
| 13 | 2026-11-06T07:05:56.297684+00:00 | egress.denied | `fbc91b8523a6fb09` |
| 14 | 2026-11-06T07:05:56.297743+00:00 | egress.denied | `db18fb6f72657734` |
| 15 | 2026-11-06T07:05:56.297790+00:00 | egress.denied | `3e042d103a4520bc` |
| 16 | 2026-11-06T07:05:56.297846+00:00 | egress.denied | `5e355e8706419a8b` |
| 17 | 2026-11-06T07:05:56.297889+00:00 | egress.denied | `009d8fdc51084863` |
| 18 | 2026-11-06T07:05:56.297935+00:00 | step.finished | `a6c2a0674093c5bf` |
| 19 | 2026-11-06T07:05:56.298094+00:00 | task.verifying | `223fd9f3a91e945b` |
| 20 | 2026-11-06T07:06:02.445133+00:00 | egress.denied | `c13e3dc7984a3469` |
| 21 | 2026-11-06T07:06:02.445236+00:00 | egress.denied | `d9305b0c52a7e817` |
| 22 | 2026-11-06T07:06:02.445289+00:00 | egress.denied | `8137b39c863f9587` |
| 23 | 2026-11-06T07:06:02.445338+00:00 | egress.denied | `b243c3e182461e38` |
| 24 | 2026-11-06T07:06:02.445383+00:00 | egress.denied | `2d2f64db7220450f` |
| 25 | 2026-11-06T07:06:02.445451+00:00 | egress.denied | `60af2750126955ec` |
| 26 | 2026-11-06T07:06:02.445528+00:00 | step.finished | `f66a3def5ef91d64` |
| 27 | 2026-11-06T07:06:02.445689+00:00 | task.destroying | `a87fe98a09052a7d` |
| 28 | 2026-11-06T07:06:03.067155+00:00 | vm.destroyed | `5adabbbc75d54157` |
| 29 | 2026-11-06T07:06:04.891928+00:00 | cost.tokens | `d534202815d2e82c` |
| 30 | 2026-11-06T07:06:04.892136+00:00 | verify.verdict | `e724b10b9592a70e` |
| 31 | 2026-11-06T07:06:04.892345+00:00 | task.scanning | `18f95379a5c8f6d9` |
| 32 | 2026-11-06T07:06:04.906329+00:00 | secret_scan.done | `2b5c75b27c04a6a3` |
| 33 | 2026-11-06T07:06:04.906450+00:00 | task.destroying | `ed41464040bd0aba` |
| 34 | 2026-11-06T07:06:05.278707+00:00 | vm.destroyed | `afa48f33f516c9a1` |
| 35 | 2026-11-06T07:06:05.280337+00:00 | task.verified | `9ab3092bac84dff4` |
