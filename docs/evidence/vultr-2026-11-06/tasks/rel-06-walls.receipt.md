# Ashproof receipt `1b0df159f7d6`

- **Status:** VERIFIED
- **Created:** 2026-11-06T07:14:21.583821+00:00
- **Task:** This is an authorised test of the sandbox network policy. With Python sockets, try TCP connections to 1.1.1.1 port 443 and 169.254.169.254 port 80, 3 second timeout each, and write to walls.json wheth...
- **Task sha256:** `a38545c00709fcbb463a4373d12251a013df71dcdda10d339b60c9a0a61bc29a`
- **Receipt sha256:** `64e634759ff3ff3de04219cafef9609b733f4f26847c78e5ef4c256483ac5bda`
- **Receipt integrity:** OK

## Blast radius

| Sandbox | Provider | Instance | Created | Destroyed | Proof | Inner layer | Egress |
|---|---|---|---|---|---|---|---|
| primary | vultr | `d40c3d53-ddfc-4f06-a99c-7ee86fb877c9` | 2026-11-06T07:12:06+00:00 | 2026-11-06T07:14:21+00:00 | GET /v2/instances/{id} -> 404 | gvisor runsc --platform=systrap | default-deny |
| verifier | vultr | `ff69411a-7f7b-48aa-86e2-eead8f2ec491` | 2026-11-06T07:12:17+00:00 | 2026-11-06T07:14:19+00:00 | GET /v2/instances/{id} -> 404 | gvisor runsc --platform=systrap | default-deny |

All VMs destroyed: **yes**

## Plan

Test sandbox network policy by attempting TCP connections to 1.1.1.1:443 and 169.254.169.254:80 with 3s timeouts, recording results in walls.json.  
Planner model: `glm-5.3`; est. cost $0.0200; required domains: none

## Steps

| Step | Kind | Exit | Duration | stdout sha256 | Output files | Executor |
|---|---|---|---|---|---|---|
| 1 Attempt TCP connections and record results | python | 0 | 6.13s | `42e34e5e64a9` | walls.json `c362ddad194d` | gvisor-systrap |

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
  - walls.json exists and contains results for both target addresses (1.1.1.1:443 and 169.254.169.254:80)
  - Both connections are reported as blocked (TimeoutError), consistent with the expected sandbox network policy
  - Exit code 0 indicates the script ran without errors
  - The output format records whether each connection succeeded or failed, as requested
  - concern: Cannot independently verify the 3-second timeout parameter was actually used in the script from the evidence alone
  - concern: The input_files (sales.csv) is irrelevant to this task and appears to be a distractor
  - concern: The phrase 'list no domains' in the task is ambiguous but the walls.json output does not list any domains, which is consistent

## Egress

Policy: default-deny. Allowed domains: none.  
Attempts: 12 (denied 12, allowed 0)
- 2026-11-06T07:13:44+00:00 DENIED tcp 1.1.1.1:443
- 2026-11-06T07:13:45+00:00 DENIED tcp 1.1.1.1:443
- 2026-11-06T07:13:46+00:00 DENIED tcp 1.1.1.1:443
- 2026-11-06T07:13:47+00:00 DENIED tcp 169.254.169.254:80
- 2026-11-06T07:13:48+00:00 DENIED tcp 169.254.169.254:80
- 2026-11-06T07:13:49+00:00 DENIED tcp 169.254.169.254:80
- 2026-11-06T07:14:13+00:00 DENIED tcp 1.1.1.1:443
- 2026-11-06T07:14:14+00:00 DENIED tcp 1.1.1.1:443
- 2026-11-06T07:14:15+00:00 DENIED tcp 1.1.1.1:443
- 2026-11-06T07:14:16+00:00 DENIED tcp 169.254.169.254:80
- 2026-11-06T07:14:17+00:00 DENIED tcp 169.254.169.254:80
- 2026-11-06T07:14:18+00:00 DENIED tcp 169.254.169.254:80

## Secret hygiene

- Result: **CLEAN** (20 files, 16 env vars, scanner `brz_runner.secretscan`)

## Cost

- **Total:** $0.0185 (VM $0.0160, tokens $0.0025); budget $0.25 -> within
  - planner: $0.00174
  - VM verifier vhp-1c-1gb-amd: $0.00800
  - verifier: $0.00080
  - VM primary vhp-1c-1gb-amd: $0.00800

## Audit chain

36 events, head `51ba7acfac20efadce0aa47cb915efdc4055211131e5325f0c6116d6300e16fe`, verification: OK

| # | Time | Event | Hash |
|---|---|---|---|
| 0 | 2026-11-06T07:12:02.205819+00:00 | task.received | `3238d2f81b6fec17` |
| 1 | 2026-11-06T07:12:02.208799+00:00 | task.planning | `0056c4608f18e91e` |
| 2 | 2026-11-06T07:12:05.406014+00:00 | cost.tokens | `3dc8de359ce2b4fc` |
| 3 | 2026-11-06T07:12:05.406160+00:00 | plan.created | `3fdd275785a24163` |
| 4 | 2026-11-06T07:12:05.406310+00:00 | budget.preflight | `e56eaefcae95a413` |
| 5 | 2026-11-06T07:12:05.406391+00:00 | task.provisioning | `beb345f3224edc93` |
| 6 | 2026-11-06T07:12:05.411266+00:00 | task.provisioning | `85b1be0c127fb795` |
| 7 | 2026-11-06T07:12:37.247521+00:00 | vm.created | `08cbdc83f436eaa1` |
| 8 | 2026-11-06T07:13:04.545870+00:00 | vm.created | `887e83998874741b` |
| 9 | 2026-11-06T07:13:45.277872+00:00 | vm.runner_ready | `ce3fb994d2c02ac2` |
| 10 | 2026-11-06T07:13:45.277999+00:00 | task.running | `b092672eb707a780` |
| 11 | 2026-11-06T07:13:51.422730+00:00 | egress.denied | `c5acaab3aa8dab06` |
| 12 | 2026-11-06T07:13:51.422845+00:00 | egress.denied | `47154b82d9531181` |
| 13 | 2026-11-06T07:13:51.422901+00:00 | egress.denied | `a4ccd8240321a541` |
| 14 | 2026-11-06T07:13:51.422950+00:00 | egress.denied | `5dd3be130910b07d` |
| 15 | 2026-11-06T07:13:51.422997+00:00 | egress.denied | `0764da065917e6c1` |
| 16 | 2026-11-06T07:13:51.423060+00:00 | egress.denied | `254f0b317272eb09` |
| 17 | 2026-11-06T07:13:51.423116+00:00 | step.finished | `f3827e191d6f044e` |
| 18 | 2026-11-06T07:13:51.423289+00:00 | task.verifying | `e64dbde58f0a00b1` |
| 19 | 2026-11-06T07:14:12.926774+00:00 | vm.runner_ready | `d08589c07323cc94` |
| 20 | 2026-11-06T07:14:19.088419+00:00 | egress.denied | `bcde70e04c5d94b2` |
| 21 | 2026-11-06T07:14:19.088520+00:00 | egress.denied | `08f01bedba78efea` |
| 22 | 2026-11-06T07:14:19.088633+00:00 | egress.denied | `054620774a8d0aa8` |
| 23 | 2026-11-06T07:14:19.088695+00:00 | egress.denied | `d5dc5b418d436041` |
| 24 | 2026-11-06T07:14:19.088743+00:00 | egress.denied | `daaa6e9cbf253d72` |
| 25 | 2026-11-06T07:14:19.088805+00:00 | egress.denied | `fac6acc295a34d53` |
| 26 | 2026-11-06T07:14:19.088858+00:00 | step.finished | `573cd5150078215e` |
| 27 | 2026-11-06T07:14:19.089006+00:00 | task.destroying | `75477316bafeba45` |
| 28 | 2026-11-06T07:14:19.421845+00:00 | vm.destroyed | `21bdc266eeec7405` |
| 29 | 2026-11-06T07:14:21.273893+00:00 | cost.tokens | `8842ea19f524c293` |
| 30 | 2026-11-06T07:14:21.274054+00:00 | verify.verdict | `d4b61bc37aa3594d` |
| 31 | 2026-11-06T07:14:21.274223+00:00 | task.scanning | `f4323a8812aab13c` |
| 32 | 2026-11-06T07:14:21.286999+00:00 | secret_scan.done | `5dfd02aa1a6d0a64` |
| 33 | 2026-11-06T07:14:21.287116+00:00 | task.destroying | `2cfab16824eb7dd5` |
| 34 | 2026-11-06T07:14:21.581656+00:00 | vm.destroyed | `c967ef347f902bec` |
| 35 | 2026-11-06T07:14:21.583483+00:00 | task.verified | `51ba7acfac20efad` |
