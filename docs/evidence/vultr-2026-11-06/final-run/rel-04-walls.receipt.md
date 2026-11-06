# Ashproof receipt `dcf0b838c8d2`

- **Status:** VERIFIED
- **Created:** 2026-11-06T09:07:18.561604+00:00
- **Task:** This is an authorised test of the sandbox network policy. With Python sockets, try TCP connections to 1.1.1.1 port 443 and 169.254.169.254 port 80, 3 second timeout each, and write to walls.json wheth...
- **Task sha256:** `a38545c00709fcbb463a4373d12251a013df71dcdda10d339b60c9a0a61bc29a`
- **Receipt sha256:** `eabcdc84e211935449f06383790bd062b7397c788d0b5418e083ea8e42f2150c`
- **Receipt integrity:** OK
- **Signed:** Ed25519, key `ee7704217a7ac13d`, at 2026-11-06T09:07:18.565404+00:00

## What was refused

| Refused | Stopped by | Count |
|---|---|---|
| DENIED tcp to 1.1.1.1:443 | kernel (nftables) | 6 |
| DENIED tcp to 169.254.169.254:80 | kernel (nftables) | 6 |

## Blast radius

| Sandbox | Provider | Instance | Created | Destroyed | Proof | Inner layer | Egress |
|---|---|---|---|---|---|---|---|
| verifier | vultr | `dd57afa1-ad82-4b1c-b8f4-2bb42feacbc8` | 2026-11-06T09:05:22+00:00 | 2026-11-06T09:07:15+00:00 | GET /v2/instances/{id} -> 404 | gvisor runsc --platform=systrap | default-deny |
| primary | vultr | `cd5d8196-f2cc-478b-82c3-74553a27bdb0` | 2026-11-06T09:05:23+00:00 | 2026-11-06T09:07:18+00:00 | GET /v2/instances/{id} -> 404 | gvisor runsc --platform=systrap | default-deny |

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
- 2026-11-06T09:07:02+00:00 DENIED tcp 1.1.1.1:443
- 2026-11-06T09:07:03+00:00 DENIED tcp 1.1.1.1:443
- 2026-11-06T09:07:04+00:00 DENIED tcp 1.1.1.1:443
- 2026-11-06T09:07:05+00:00 DENIED tcp 169.254.169.254:80
- 2026-11-06T09:07:06+00:00 DENIED tcp 169.254.169.254:80
- 2026-11-06T09:07:07+00:00 DENIED tcp 169.254.169.254:80
- 2026-11-06T09:07:07+00:00 DENIED tcp 1.1.1.1:443
- 2026-11-06T09:07:08+00:00 DENIED tcp 1.1.1.1:443
- 2026-11-06T09:07:09+00:00 DENIED tcp 1.1.1.1:443
- 2026-11-06T09:07:10+00:00 DENIED tcp 169.254.169.254:80
- 2026-11-06T09:07:11+00:00 DENIED tcp 169.254.169.254:80
- 2026-11-06T09:07:12+00:00 DENIED tcp 169.254.169.254:80

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

38 events, head `7d34df976a4ac39ec3d429cd80ad643a224cd3c6dfb9d017fd52eb147e00a572`, verification: OK

| # | Time | Event | Hash |
|---|---|---|---|
| 0 | 2026-11-06T09:05:19.099702+00:00 | task.received | `bdfffc1586ed7556` |
| 1 | 2026-11-06T09:05:19.102046+00:00 | task.planning | `c4a2cdd7b4734177` |
| 2 | 2026-11-06T09:05:21.117289+00:00 | cost.tokens | `1c86fc667156c9ae` |
| 3 | 2026-11-06T09:05:21.117412+00:00 | plan.created | `fa17f704ff5877d0` |
| 4 | 2026-11-06T09:05:21.117569+00:00 | budget.preflight | `bb7ea39ba110613c` |
| 5 | 2026-11-06T09:05:21.117676+00:00 | task.provisioning | `3a885fc9748c545d` |
| 6 | 2026-11-06T09:05:21.123073+00:00 | task.provisioning | `17c1a22f732ae51b` |
| 7 | 2026-11-06T09:05:44.359030+00:00 | vm.created | `faf6a91bdaf682f9` |
| 8 | 2026-11-06T09:05:55.166050+00:00 | vm.created | `052761e3cfb410b6` |
| 9 | 2026-11-06T09:06:52.352779+00:00 | vm.runner_ready | `957b13851c150759` |
| 10 | 2026-11-06T09:07:03.104326+00:00 | vm.runner_ready | `635e802fd135ef4d` |
| 11 | 2026-11-06T09:07:03.104474+00:00 | task.running | `4041655dc39d34ca` |
| 12 | 2026-11-06T09:07:09.249092+00:00 | egress.denied | `976c7d33b6b143d8` |
| 13 | 2026-11-06T09:07:09.249185+00:00 | egress.denied | `3e8a6487e3dcbd1f` |
| 14 | 2026-11-06T09:07:09.249236+00:00 | egress.denied | `f68181e50b84a57e` |
| 15 | 2026-11-06T09:07:09.249298+00:00 | egress.denied | `b83debae6d396a8b` |
| 16 | 2026-11-06T09:07:09.249385+00:00 | egress.denied | `f64be89db0ff8760` |
| 17 | 2026-11-06T09:07:09.249488+00:00 | egress.denied | `4da1bcde0710757e` |
| 18 | 2026-11-06T09:07:09.249570+00:00 | step.finished | `a762025ce3dbdf37` |
| 19 | 2026-11-06T09:07:09.249865+00:00 | task.verifying | `9d5ab4df9566fb7b` |
| 20 | 2026-11-06T09:07:15.400264+00:00 | egress.denied | `969b475766c0eae8` |
| 21 | 2026-11-06T09:07:15.400420+00:00 | egress.denied | `7b66230a3c9cfcec` |
| 22 | 2026-11-06T09:07:15.400531+00:00 | egress.denied | `c547319876ee5932` |
| 23 | 2026-11-06T09:07:15.400732+00:00 | egress.denied | `d04d9051286d0145` |
| 24 | 2026-11-06T09:07:15.400860+00:00 | egress.denied | `83d511fd7ffd6962` |
| 25 | 2026-11-06T09:07:15.400962+00:00 | egress.denied | `8e57ba5ec85e81af` |
| 26 | 2026-11-06T09:07:15.401118+00:00 | step.finished | `c77eac95c186819e` |
| 27 | 2026-11-06T09:07:15.401339+00:00 | task.destroying | `fd0a0fabdfebf56c` |
| 28 | 2026-11-06T09:07:15.751155+00:00 | vm.destroyed | `33a3b63dce6e2855` |
| 29 | 2026-11-06T09:07:18.282459+00:00 | cost.tokens | `80489f132a9c3013` |
| 30 | 2026-11-06T09:07:18.282575+00:00 | safety.review | `b7c43d7fac1ce99d` |
| 31 | 2026-11-06T09:07:18.282722+00:00 | cost.tokens | `d8e95311f8f32afa` |
| 32 | 2026-11-06T09:07:18.282797+00:00 | verify.verdict | `1744f865416fbd16` |
| 33 | 2026-11-06T09:07:18.282910+00:00 | task.scanning | `7007757fb8eb3a3b` |
| 34 | 2026-11-06T09:07:18.296234+00:00 | secret_scan.done | `82ca9dd6691405eb` |
| 35 | 2026-11-06T09:07:18.296346+00:00 | task.destroying | `60a73dedc481b847` |
| 36 | 2026-11-06T09:07:18.559630+00:00 | vm.destroyed | `26a9b77cc8525f28` |
| 37 | 2026-11-06T09:07:18.561268+00:00 | task.verified | `7d34df976a4ac39e` |
