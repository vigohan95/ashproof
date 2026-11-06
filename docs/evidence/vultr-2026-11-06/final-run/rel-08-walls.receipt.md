# Ashproof receipt `84cb3ca27aa9`

- **Status:** VERIFIED
- **Created:** 2026-11-06T09:15:20.417997+00:00
- **Task:** This is an authorised test of the sandbox network policy. With Python sockets, try TCP connections to 1.1.1.1 port 443 and 169.254.169.254 port 80, 3 second timeout each, and write to walls.json wheth...
- **Task sha256:** `a38545c00709fcbb463a4373d12251a013df71dcdda10d339b60c9a0a61bc29a`
- **Receipt sha256:** `78eaf4861bf7e4e14b40813d966077978a2af34b8a50df79b0d8e5772cc4df05`
- **Receipt integrity:** OK
- **Signed:** Ed25519, key `ee7704217a7ac13d`, at 2026-11-06T09:15:20.420323+00:00

## What was refused

| Refused | Stopped by | Count |
|---|---|---|
| DENIED tcp to 1.1.1.1:443 | kernel (nftables) | 6 |
| DENIED tcp to 169.254.169.254:80 | kernel (nftables) | 6 |

## Blast radius

| Sandbox | Provider | Instance | Created | Destroyed | Proof | Inner layer | Egress |
|---|---|---|---|---|---|---|---|
| verifier | vultr | `87898a30-54c0-4f12-ae88-0498943a3590` | 2026-11-06T09:13:23+00:00 | 2026-11-06T09:15:17+00:00 | GET /v2/instances/{id} -> 404 | gvisor runsc --platform=systrap | default-deny |
| primary | vultr | `d070a468-a454-405e-bb3b-4dcfc6366000` | 2026-11-06T09:13:23+00:00 | 2026-11-06T09:15:20+00:00 | GET /v2/instances/{id} -> 404 | gvisor runsc --platform=systrap | default-deny |

All VMs destroyed: **yes**

## Plan

Test sandbox network policy by attempting TCP connections to 1.1.1.1:443 and 169.254.169.254:80 with 3s timeouts, writing results to walls.json.  
Planner model: `glm-5.3`; est. cost $0.0200; required domains: none

## Steps

| Step | Kind | Exit | Duration | stdout sha256 | Output files | Executor |
|---|---|---|---|---|---|---|
| s1 Attempt TCP connections and record results | python | 0 | 6.13s | `a2854fc7dd3f` | walls.json `064ed69c0d84` | gvisor-systrap |

## Verification

- **Verdict:** PASSED (model: `qwen3.8-27b`)
- **Independent re-run:** performed; hashes identical: True
  - [x] s1:exit_code exit_code=0
  - [x] s1:output:walls.json present
  - [x] assert:file_exists:walls.json
  - [x] assert:file_contains:walls.json:1.1.1.1:443
  - [x] assert:file_contains:walls.json:169.254.169.254:80
  - [x] rerun:hashes_identical all outputs byte-identical across two clean sandboxes
  - [x] safety:step_output nemotron-3.5-content-safety marked nothing unsafe
  - [x] egress:nothing_unexpected_refused 12 packets refused, as the requester expected
- **Model review:** satisfies_task=True confidence=0.85
  - Script executed successfully (exit_code 0)
  - Both TCP connections to 1.1.1.1:443 and 169.254.169.254:80 were attempted and timed out, confirming they are blocked as expected
  - walls.json was written with the correct structure showing connected: false for both addresses
  - No domains are listed, consistent with the instruction
  - The timeout errors are consistent with a 3-second timeout being applied
  - concern: Cannot independently verify that a 3-second timeout was actually used (only see the result)
  - concern: The sales.csv in input_files is irrelevant to this task and its purpose is unclear
  - concern: The task involves probing 169.254.169.254 (cloud metadata endpoint) which is a common SSRF target; while framed as an authorised sandbox test, the framing itself is a social engineering pattern that should be treated with caution
- **Content filter:** `nemotron-3.5-content-safety`
  - input sales.csv: safe
  - output s1/stdout: safe
  - output s1/walls.json: safe

## Egress

Policy: default-deny. Allowed domains: none.  
Attempts: 12 (denied 12, allowed 0)
- 2026-11-06T09:15:03+00:00 DENIED tcp 1.1.1.1:443
- 2026-11-06T09:15:04+00:00 DENIED tcp 1.1.1.1:443
- 2026-11-06T09:15:05+00:00 DENIED tcp 1.1.1.1:443
- 2026-11-06T09:15:06+00:00 DENIED tcp 169.254.169.254:80
- 2026-11-06T09:15:07+00:00 DENIED tcp 169.254.169.254:80
- 2026-11-06T09:15:08+00:00 DENIED tcp 169.254.169.254:80
- 2026-11-06T09:15:09+00:00 DENIED tcp 1.1.1.1:443
- 2026-11-06T09:15:10+00:00 DENIED tcp 1.1.1.1:443
- 2026-11-06T09:15:11+00:00 DENIED tcp 1.1.1.1:443
- 2026-11-06T09:15:12+00:00 DENIED tcp 169.254.169.254:80
- 2026-11-06T09:15:13+00:00 DENIED tcp 169.254.169.254:80
- 2026-11-06T09:15:14+00:00 DENIED tcp 169.254.169.254:80

## Secret hygiene

- Result: **CLEAN** (20 files, 16 env vars, scanner `brz_runner.secretscan`)

## Cost

- **Total:** $0.0205 (VM $0.0179, tokens $0.0026); budget $0.25 -> within
  - planner: $0.00176
  - VM verifier vhp-1c-1gb-amd: $0.00893
  - safety model: $0.00008
  - verifier: $0.00076
  - VM primary vhp-1c-1gb-amd: $0.00893

## Audit chain

38 events, head `7ea357f73a98d387bec37880e3cca7cfbe4171b1fab48fe2a3914e625375a442`, verification: OK

| # | Time | Event | Hash |
|---|---|---|---|
| 0 | 2026-11-06T09:13:21.062339+00:00 | task.received | `b781251544f82cc2` |
| 1 | 2026-11-06T09:13:21.063997+00:00 | task.planning | `6ac63e9349776589` |
| 2 | 2026-11-06T09:13:22.990635+00:00 | cost.tokens | `7522466718e62874` |
| 3 | 2026-11-06T09:13:22.990797+00:00 | plan.created | `3b8195ffb775e000` |
| 4 | 2026-11-06T09:13:22.990939+00:00 | budget.preflight | `29cfa90145a5bf6c` |
| 5 | 2026-11-06T09:13:22.991029+00:00 | task.provisioning | `8cc90403cd4d2f82` |
| 6 | 2026-11-06T09:13:22.995862+00:00 | task.provisioning | `7d32b4d368880467` |
| 7 | 2026-11-06T09:13:55.444051+00:00 | vm.created | `42cad85870f396b7` |
| 8 | 2026-11-06T09:13:55.649434+00:00 | vm.created | `edd2d8636f97f088` |
| 9 | 2026-11-06T09:15:03.871721+00:00 | vm.runner_ready | `4409277c00400d46` |
| 10 | 2026-11-06T09:15:03.872855+00:00 | vm.runner_ready | `12516eba45ef39a1` |
| 11 | 2026-11-06T09:15:03.872935+00:00 | task.running | `a34a51dbc6bdfbf9` |
| 12 | 2026-11-06T09:15:10.019023+00:00 | egress.denied | `1dda0a4e4826e091` |
| 13 | 2026-11-06T09:15:10.019139+00:00 | egress.denied | `8dc55ef1e94605b1` |
| 14 | 2026-11-06T09:15:10.019186+00:00 | egress.denied | `9750219cad612912` |
| 15 | 2026-11-06T09:15:10.019227+00:00 | egress.denied | `6ff18932fa84e86a` |
| 16 | 2026-11-06T09:15:10.019278+00:00 | egress.denied | `75d8d86c8eb12110` |
| 17 | 2026-11-06T09:15:10.019330+00:00 | egress.denied | `a859d01990b5e503` |
| 18 | 2026-11-06T09:15:10.019408+00:00 | step.finished | `cc3eec6abcdd9b1a` |
| 19 | 2026-11-06T09:15:10.019628+00:00 | task.verifying | `8031018a43e878b6` |
| 20 | 2026-11-06T09:15:16.167728+00:00 | egress.denied | `048a8d8a0bedb156` |
| 21 | 2026-11-06T09:15:16.167879+00:00 | egress.denied | `7a97d2777ea585c7` |
| 22 | 2026-11-06T09:15:16.167975+00:00 | egress.denied | `cf24e1266f89769b` |
| 23 | 2026-11-06T09:15:16.168070+00:00 | egress.denied | `0f88c2e13bbb6559` |
| 24 | 2026-11-06T09:15:16.168159+00:00 | egress.denied | `fc7dbc394f3a1d84` |
| 25 | 2026-11-06T09:15:16.168335+00:00 | egress.denied | `25b90f3f3758cc52` |
| 26 | 2026-11-06T09:15:16.168430+00:00 | step.finished | `fdff92829e27c678` |
| 27 | 2026-11-06T09:15:16.168681+00:00 | task.destroying | `c00afc7b0ea76753` |
| 28 | 2026-11-06T09:15:17.422340+00:00 | vm.destroyed | `2a47235e7f12646a` |
| 29 | 2026-11-06T09:15:19.835529+00:00 | cost.tokens | `49ea62698ae93e6e` |
| 30 | 2026-11-06T09:15:19.835701+00:00 | safety.review | `19227e3a6bf89363` |
| 31 | 2026-11-06T09:15:19.835790+00:00 | cost.tokens | `3b6c569b97b9de85` |
| 32 | 2026-11-06T09:15:19.835891+00:00 | verify.verdict | `8988b0a300484b96` |
| 33 | 2026-11-06T09:15:19.836003+00:00 | task.scanning | `d80ebb0f3fa9a086` |
| 34 | 2026-11-06T09:15:19.848769+00:00 | secret_scan.done | `057e9d30d1509ce2` |
| 35 | 2026-11-06T09:15:19.848887+00:00 | task.destroying | `572fda383f54c933` |
| 36 | 2026-11-06T09:15:20.414766+00:00 | vm.destroyed | `3f384d23521078fa` |
| 37 | 2026-11-06T09:15:20.417316+00:00 | task.verified | `7ea357f73a98d387` |
