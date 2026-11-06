# Ashproof receipt `6a276c6baef8`

- **Status:** VERIFIED
- **Created:** 2026-11-06T06:46:00.794582+00:00
- **Task:** This is an authorised test of the sandbox network policy. With Python sockets, try TCP connections to 1.1.1.1 port 443 and 169.254.169.254 port 80, 3 second timeout each, and write to walls.json wheth...
- **Task sha256:** `a38545c00709fcbb463a4373d12251a013df71dcdda10d339b60c9a0a61bc29a`
- **Receipt sha256:** `c3581be519314dd39be79e41578846ad312bac076bf9191d62ab8669d428b2f3`
- **Receipt integrity:** OK

## Blast radius

| Sandbox | Provider | Instance | Created | Destroyed | Proof | Inner layer | Egress |
|---|---|---|---|---|---|---|---|
| primary | vultr | `af91e7b4-0932-4ac8-83d2-c54ad48e38d2` | 2026-11-06T06:42:07+00:00 | 2026-11-06T06:46:00+00:00 | GET /v2/instances/{id} -> 404 | gvisor runsc --platform=systrap | default-deny |
| verifier | vultr | `cdb2fb3f-b28f-4b3c-b14a-61c889281f0e` | 2026-11-06T06:42:09+00:00 | 2026-11-06T06:45:58+00:00 | GET /v2/instances/{id} -> 404 | gvisor runsc --platform=systrap | default-deny |

All VMs destroyed: **yes**

## Plan

Attempt TCP connections to 1.1.1.1:443 and 169.254.169.254:80 with 3s timeouts, record results in walls.json.  
Planner model: `glm-5.3`; est. cost $0.0200; required domains: none

## Steps

| Step | Kind | Exit | Duration | stdout sha256 | Output files | Executor |
|---|---|---|---|---|---|---|
| 1 Test outbound TCP connectivity and record results | python | 0 | 6.25s | `a2854fc7dd3f` | walls.json `064ed69c0d84` | gvisor-systrap |

## Verification

- **Verdict:** PASSED (model: `qwen3.8-27b`)
- **Independent re-run:** performed; hashes identical: True
  - [x] 1:exit_code exit_code=0
  - [x] 1:output:walls.json present
  - [x] assert:file_exists:walls.json
  - [x] assert:file_contains:walls.json:1.1.1.1:443
  - [x] assert:file_contains:walls.json:169.254.169.254:80
  - [x] rerun:hashes_identical all outputs byte-identical across two clean sandboxes
- **Model review:** satisfies_task=True confidence=0.85
  - Both target addresses (1.1.1.1:443 and 169.254.169.254:80) were attempted and recorded in walls.json
  - Both connections timed out, consistent with the expected blocking behavior
  - walls.json contains only the two IP:port entries with no domains listed, as required
  - Exit code 0 indicates the script ran successfully
  - The timeout errors are consistent with a 3-second timeout being applied (though the exact value cannot be independently confirmed from output alone)
  - The input_files (sales.csv) is irrelevant to this task and appears to be a distractor

## Egress

Policy: default-deny. Allowed domains: none.  
Attempts: 12 (denied 12, allowed 0)
- 2026-11-06T06:45:45+00:00 DENIED tcp 1.1.1.1:443
- 2026-11-06T06:45:46+00:00 DENIED tcp 1.1.1.1:443
- 2026-11-06T06:45:47+00:00 DENIED tcp 1.1.1.1:443
- 2026-11-06T06:45:48+00:00 DENIED tcp 169.254.169.254:80
- 2026-11-06T06:45:49+00:00 DENIED tcp 169.254.169.254:80
- 2026-11-06T06:45:50+00:00 DENIED tcp 169.254.169.254:80
- 2026-11-06T06:45:51+00:00 DENIED tcp 1.1.1.1:443
- 2026-11-06T06:45:52+00:00 DENIED tcp 1.1.1.1:443
- 2026-11-06T06:45:53+00:00 DENIED tcp 1.1.1.1:443
- 2026-11-06T06:45:54+00:00 DENIED tcp 169.254.169.254:80
- 2026-11-06T06:45:55+00:00 DENIED tcp 169.254.169.254:80
- 2026-11-06T06:45:56+00:00 DENIED tcp 169.254.169.254:80

## Secret hygiene

- Result: **CLEAN** (20 files, 16 env vars, scanner `brz_runner.secretscan`)

## Cost

- **Total:** $0.0185 (VM $0.0160, tokens $0.0025); budget $0.25 -> within
  - planner: $0.00179
  - VM verifier vhp-1c-1gb-amd: $0.00800
  - verifier: $0.00075
  - VM primary vhp-1c-1gb-amd: $0.00800

## Audit chain

36 events, head `385ed7b9acae686fae5e7873db45b22327404152b62cdfe80c669b3766ac0a6b`, verification: OK

| # | Time | Event | Hash |
|---|---|---|---|
| 0 | 2026-11-06T06:42:04.461482+00:00 | task.received | `3439c8f232a67e5a` |
| 1 | 2026-11-06T06:42:04.463316+00:00 | task.planning | `a7408e0050f599e3` |
| 2 | 2026-11-06T06:42:07.242465+00:00 | cost.tokens | `ae56668db39daa13` |
| 3 | 2026-11-06T06:42:07.242636+00:00 | plan.created | `a820c5c16f712391` |
| 4 | 2026-11-06T06:42:07.242778+00:00 | budget.preflight | `0f8cd40109f1eca6` |
| 5 | 2026-11-06T06:42:07.242892+00:00 | task.provisioning | `5e0887701e9afdbd` |
| 6 | 2026-11-06T06:42:07.247853+00:00 | task.provisioning | `92298f4ef259199c` |
| 7 | 2026-11-06T06:43:20.636554+00:00 | vm.created | `376d01d97c9fd96a` |
| 8 | 2026-11-06T06:43:21.947919+00:00 | vm.created | `05810ae329a08651` |
| 9 | 2026-11-06T06:45:43.231148+00:00 | vm.runner_ready | `4f43e2acdc6b5461` |
| 10 | 2026-11-06T06:45:45.275969+00:00 | vm.runner_ready | `be48b815e7c95172` |
| 11 | 2026-11-06T06:45:45.276097+00:00 | task.running | `f94b17373d531b3b` |
| 12 | 2026-11-06T06:45:51.556744+00:00 | egress.denied | `c55c07c7a477df12` |
| 13 | 2026-11-06T06:45:51.556862+00:00 | egress.denied | `3d5cc09273ffd6c1` |
| 14 | 2026-11-06T06:45:51.557037+00:00 | egress.denied | `da5cbded23835892` |
| 15 | 2026-11-06T06:45:51.557126+00:00 | egress.denied | `1a8fea1b5cfe67d5` |
| 16 | 2026-11-06T06:45:51.557181+00:00 | egress.denied | `a13d9fc2cc043190` |
| 17 | 2026-11-06T06:45:51.557233+00:00 | egress.denied | `85144560d9d9c274` |
| 18 | 2026-11-06T06:45:51.557340+00:00 | step.finished | `8a5eb0546d2b9310` |
| 19 | 2026-11-06T06:45:51.557480+00:00 | task.verifying | `11fb19afce002a8a` |
| 20 | 2026-11-06T06:45:57.849819+00:00 | egress.denied | `64e65d5ddb60184d` |
| 21 | 2026-11-06T06:45:57.850001+00:00 | egress.denied | `92845dfa60bdd2fc` |
| 22 | 2026-11-06T06:45:57.850107+00:00 | egress.denied | `67617c14e07ee0aa` |
| 23 | 2026-11-06T06:45:57.850202+00:00 | egress.denied | `4a5ee37e8cf4f666` |
| 24 | 2026-11-06T06:45:57.850367+00:00 | egress.denied | `6f3cc59442ea8091` |
| 25 | 2026-11-06T06:45:57.850433+00:00 | egress.denied | `127c92c3cea1f9f9` |
| 26 | 2026-11-06T06:45:57.850538+00:00 | step.finished | `c7184b86f58769a1` |
| 27 | 2026-11-06T06:45:57.850772+00:00 | task.destroying | `efac197a499cec3a` |
| 28 | 2026-11-06T06:45:58.427492+00:00 | vm.destroyed | `8c8266fa982b54c1` |
| 29 | 2026-11-06T06:46:00.420278+00:00 | cost.tokens | `c2765bae88319b80` |
| 30 | 2026-11-06T06:46:00.420423+00:00 | verify.verdict | `076cfde97e0334a0` |
| 31 | 2026-11-06T06:46:00.420534+00:00 | task.scanning | `79f3a0a28066dabc` |
| 32 | 2026-11-06T06:46:00.442377+00:00 | secret_scan.done | `e5985ec86ccc5259` |
| 33 | 2026-11-06T06:46:00.442541+00:00 | task.destroying | `d527677f5be16958` |
| 34 | 2026-11-06T06:46:00.792747+00:00 | vm.destroyed | `82be8a35f991ebff` |
| 35 | 2026-11-06T06:46:00.794082+00:00 | task.verified | `385ed7b9acae686f` |
