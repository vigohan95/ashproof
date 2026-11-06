# Ashproof receipt `9cc672e2e9a4`

- **Status:** VERIFIED
- **Created:** 2026-11-06T07:26:41.965100+00:00
- **Task:** This is an authorised test of the sandbox network policy. With Python sockets, try TCP connections to 1.1.1.1 port 443 and 169.254.169.254 port 80, 3 second timeout each, and write to walls.json wheth...
- **Task sha256:** `a38545c00709fcbb463a4373d12251a013df71dcdda10d339b60c9a0a61bc29a`
- **Receipt sha256:** `caeb68fe568134b11316ae8cc490b5f6d767607ef9670079c118d3f6acc6f902`
- **Receipt integrity:** OK

## Blast radius

| Sandbox | Provider | Instance | Created | Destroyed | Proof | Inner layer | Egress |
|---|---|---|---|---|---|---|---|
| verifier | vultr | `da8843db-f420-459d-abed-e28049547c9b` | 2026-11-06T07:24:23+00:00 | 2026-11-06T07:26:38+00:00 | GET /v2/instances/{id} -> 404 | gvisor runsc --platform=systrap | default-deny |
| primary | vultr | `78106d6a-a3a0-4631-8099-ede08e5d17dc` | 2026-11-06T07:24:24+00:00 | 2026-11-06T07:26:41+00:00 | GET /v2/instances/{id} -> 404 | gvisor runsc --platform=systrap | default-deny |

All VMs destroyed: **yes**

## Plan

Test outbound TCP connectivity to 1.1.1.1:443 and 169.254.169.254:80 with 3s timeouts, record results in walls.json.  
Planner model: `glm-5.3`; est. cost $0.0200; required domains: none

## Steps

| Step | Kind | Exit | Duration | stdout sha256 | Output files | Executor |
|---|---|---|---|---|---|---|
| 1 Attempt TCP connections and record results | python | 0 | 6.14s | `a2854fc7dd3f` | walls.json `a2854fc7dd3f` | gvisor-systrap |

## Verification

- **Verdict:** PASSED (model: `qwen3.8-27b`)
- **Independent re-run:** performed; hashes identical: True
  - [x] 1:exit_code exit_code=0
  - [x] 1:output:walls.json present
  - [x] rerun:hashes_identical all outputs byte-identical across two clean sandboxes
- **Model review:** satisfies_task=True confidence=0.85
  - Both target addresses (1.1.1.1:443 and 169.254.169.254:80) were tested and results recorded in walls.json
  - Both connections returned 'connected: false' with TimeoutError, consistent with expected network blocking
  - No domains are listed in walls.json, as instructed
  - The output structure correctly reports connection status per address
  - concern: Cannot independently verify the 3-second timeout value from the output alone (only the timeout error is visible)
  - concern: Cannot verify the needs_network=true parameter was set, as it is a sandbox configuration not reflected in output
  - concern: The input_files contains an unrelated sales.csv which is a distractor and was correctly ignored

## Egress

Policy: default-deny. Allowed domains: none.  
Attempts: 12 (denied 12, allowed 0)
- 2026-11-06T07:26:21+00:00 DENIED tcp 1.1.1.1:443
- 2026-11-06T07:26:22+00:00 DENIED tcp 1.1.1.1:443
- 2026-11-06T07:26:23+00:00 DENIED tcp 1.1.1.1:443
- 2026-11-06T07:26:24+00:00 DENIED tcp 169.254.169.254:80
- 2026-11-06T07:26:25+00:00 DENIED tcp 169.254.169.254:80
- 2026-11-06T07:26:26+00:00 DENIED tcp 169.254.169.254:80
- 2026-11-06T07:26:27+00:00 DENIED tcp 1.1.1.1:443
- 2026-11-06T07:26:28+00:00 DENIED tcp 1.1.1.1:443
- 2026-11-06T07:26:29+00:00 DENIED tcp 1.1.1.1:443
- 2026-11-06T07:26:30+00:00 DENIED tcp 169.254.169.254:80
- 2026-11-06T07:26:31+00:00 DENIED tcp 169.254.169.254:80
- 2026-11-06T07:26:32+00:00 DENIED tcp 169.254.169.254:80

## Secret hygiene

- Result: **CLEAN** (20 files, 16 env vars, scanner `brz_runner.secretscan`)

## Cost

- **Total:** $0.0186 (VM $0.0160, tokens $0.0026); budget $0.25 -> within
  - planner: $0.00177
  - VM verifier vhp-1c-1gb-amd: $0.00800
  - verifier: $0.00079
  - VM primary vhp-1c-1gb-amd: $0.00800

## Audit chain

36 events, head `8e364c88ef6fa83c1ebd701c2a71fa671d91dd4b8e2355aa55677e9759539ef9`, verification: OK

| # | Time | Event | Hash |
|---|---|---|---|
| 0 | 2026-11-06T07:24:19.444492+00:00 | task.received | `5e6aa5d3c2d3c90e` |
| 1 | 2026-11-06T07:24:19.446541+00:00 | task.planning | `342ab0096c5f81c6` |
| 2 | 2026-11-06T07:24:22.466130+00:00 | cost.tokens | `3578c897a1eeaae8` |
| 3 | 2026-11-06T07:24:22.466262+00:00 | plan.created | `e2e62f95f3074b2f` |
| 4 | 2026-11-06T07:24:22.466407+00:00 | budget.preflight | `9e6a67d8396e33be` |
| 5 | 2026-11-06T07:24:22.466504+00:00 | task.provisioning | `0ff6fb1642d1df11` |
| 6 | 2026-11-06T07:24:22.471252+00:00 | task.provisioning | `03091dfac93f2731` |
| 7 | 2026-11-06T07:25:11.731885+00:00 | vm.created | `bde795d51679dfc2` |
| 8 | 2026-11-06T07:25:12.811145+00:00 | vm.created | `5364fef1766e706e` |
| 9 | 2026-11-06T07:26:19.966359+00:00 | vm.runner_ready | `315b0a012a8d6f00` |
| 10 | 2026-11-06T07:26:20.989993+00:00 | vm.runner_ready | `b6b442ae6e8786b3` |
| 11 | 2026-11-06T07:26:20.990132+00:00 | task.running | `d584943b135bc55f` |
| 12 | 2026-11-06T07:26:27.148398+00:00 | egress.denied | `6235edef5dd95678` |
| 13 | 2026-11-06T07:26:27.148500+00:00 | egress.denied | `14ec776148130a97` |
| 14 | 2026-11-06T07:26:27.148554+00:00 | egress.denied | `ca9e02b92c2186f8` |
| 15 | 2026-11-06T07:26:27.148637+00:00 | egress.denied | `7496322ff6cbf80b` |
| 16 | 2026-11-06T07:26:27.148740+00:00 | egress.denied | `4066b6a99a16f9ee` |
| 17 | 2026-11-06T07:26:27.148792+00:00 | egress.denied | `e9833195385ab79c` |
| 18 | 2026-11-06T07:26:27.148853+00:00 | step.finished | `742056310acacf87` |
| 19 | 2026-11-06T07:26:27.148995+00:00 | task.verifying | `485aff3dc4a2d550` |
| 20 | 2026-11-06T07:26:33.320000+00:00 | egress.denied | `8740846bf10c0d7f` |
| 21 | 2026-11-06T07:26:33.320149+00:00 | egress.denied | `7445123247b56012` |
| 22 | 2026-11-06T07:26:33.320251+00:00 | egress.denied | `91441a30df7d0383` |
| 23 | 2026-11-06T07:26:33.320427+00:00 | egress.denied | `55a244d6ca12b78a` |
| 24 | 2026-11-06T07:26:33.320556+00:00 | egress.denied | `2ede18ee6519eb77` |
| 25 | 2026-11-06T07:26:33.320688+00:00 | egress.denied | `9b5ea3990490b858` |
| 26 | 2026-11-06T07:26:33.320795+00:00 | step.finished | `dd81be474e403d17` |
| 27 | 2026-11-06T07:26:33.320974+00:00 | task.destroying | `b95bf6fc44a8af70` |
| 28 | 2026-11-06T07:26:38.860618+00:00 | vm.destroyed | `886c30f92995c71a` |
| 29 | 2026-11-06T07:26:40.802350+00:00 | cost.tokens | `551ac8c25580e0ae` |
| 30 | 2026-11-06T07:26:40.802476+00:00 | verify.verdict | `3ba89975d250c3b1` |
| 31 | 2026-11-06T07:26:40.802611+00:00 | task.scanning | `b88047bb518c6613` |
| 32 | 2026-11-06T07:26:40.817189+00:00 | secret_scan.done | `7300dea3a5e57546` |
| 33 | 2026-11-06T07:26:40.817296+00:00 | task.destroying | `838254197cb8a6f5` |
| 34 | 2026-11-06T07:26:41.962933+00:00 | vm.destroyed | `67f99eb46edef3e2` |
| 35 | 2026-11-06T07:26:41.964757+00:00 | task.verified | `8e364c88ef6fa83c` |
