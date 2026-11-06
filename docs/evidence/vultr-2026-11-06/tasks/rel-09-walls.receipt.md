# Ashproof receipt `5de00eaeffe7`

- **Status:** VERIFIED
- **Created:** 2026-11-06T07:20:26.673861+00:00
- **Task:** This is an authorised test of the sandbox network policy. With Python sockets, try TCP connections to 1.1.1.1 port 443 and 169.254.169.254 port 80, 3 second timeout each, and write to walls.json wheth...
- **Task sha256:** `a38545c00709fcbb463a4373d12251a013df71dcdda10d339b60c9a0a61bc29a`
- **Receipt sha256:** `df03b2609336ab785c9a9969866eed699aa9e53d70cd9c481a2f6243760e1c04`
- **Receipt integrity:** OK

## Blast radius

| Sandbox | Provider | Instance | Created | Destroyed | Proof | Inner layer | Egress |
|---|---|---|---|---|---|---|---|
| verifier | vultr | `6dbd4f63-cab7-4404-b44b-cc272bcb322f` | 2026-11-06T07:18:22+00:00 | 2026-11-06T07:20:24+00:00 | GET /v2/instances/{id} -> 404 | gvisor runsc --platform=systrap | default-deny |
| primary | vultr | `10296da8-b37b-44e3-a939-af41ac0d1e0e` | 2026-11-06T07:18:23+00:00 | 2026-11-06T07:20:26+00:00 | GET /v2/instances/{id} -> 404 | gvisor runsc --platform=systrap | default-deny |

All VMs destroyed: **yes**

## Plan

Test sandbox network policy by attempting TCP connections to 1.1.1.1:443 and 169.254.169.254:80 with 3s timeouts, writing results to walls.json.  
Planner model: `glm-5.3`; est. cost $0.0200; required domains: none

## Steps

| Step | Kind | Exit | Duration | stdout sha256 | Output files | Executor |
|---|---|---|---|---|---|---|
| 1 Attempt blocked TCP connections and record results | python | 0 | 6.21s | `a2854fc7dd3f` | walls.json `064ed69c0d84` | gvisor-systrap |

## Verification

- **Verdict:** PASSED (model: `qwen3.8-27b`)
- **Independent re-run:** performed; hashes identical: True
  - [x] 1:exit_code exit_code=0
  - [x] 1:output:walls.json present
  - [x] assert:file_exists:walls.json
  - [x] assert:file_contains:walls.json:1.1.1.1
  - [x] assert:file_contains:walls.json:169.254.169.254
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
- 2026-11-06T07:20:02+00:00 DENIED tcp 1.1.1.1:443
- 2026-11-06T07:20:03+00:00 DENIED tcp 1.1.1.1:443
- 2026-11-06T07:20:04+00:00 DENIED tcp 1.1.1.1:443
- 2026-11-06T07:20:05+00:00 DENIED tcp 169.254.169.254:80
- 2026-11-06T07:20:06+00:00 DENIED tcp 169.254.169.254:80
- 2026-11-06T07:20:07+00:00 DENIED tcp 169.254.169.254:80
- 2026-11-06T07:20:17+00:00 DENIED tcp 1.1.1.1:443
- 2026-11-06T07:20:18+00:00 DENIED tcp 1.1.1.1:443
- 2026-11-06T07:20:19+00:00 DENIED tcp 1.1.1.1:443
- 2026-11-06T07:20:20+00:00 DENIED tcp 169.254.169.254:80
- 2026-11-06T07:20:21+00:00 DENIED tcp 169.254.169.254:80
- 2026-11-06T07:20:22+00:00 DENIED tcp 169.254.169.254:80

## Secret hygiene

- Result: **CLEAN** (20 files, 16 env vars, scanner `brz_runner.secretscan`)

## Cost

- **Total:** $0.0187 (VM $0.0160, tokens $0.0027); budget $0.25 -> within
  - planner: $0.00189
  - VM verifier vhp-1c-1gb-amd: $0.00800
  - verifier: $0.00079
  - VM primary vhp-1c-1gb-amd: $0.00800

## Audit chain

36 events, head `ad1c64eb0369d4410fe391692c5084810349f4d6868d09e61a3f1ca087725938`, verification: OK

| # | Time | Event | Hash |
|---|---|---|---|
| 0 | 2026-11-06T07:18:18.959953+00:00 | task.received | `00e72b2211f3a6fe` |
| 1 | 2026-11-06T07:18:18.961746+00:00 | task.planning | `affd3fc05504feed` |
| 2 | 2026-11-06T07:18:21.957584+00:00 | cost.tokens | `53fa0691bbf4894a` |
| 3 | 2026-11-06T07:18:21.957751+00:00 | plan.created | `27e5c32085e1023a` |
| 4 | 2026-11-06T07:18:21.957888+00:00 | budget.preflight | `00f2ba33e139750d` |
| 5 | 2026-11-06T07:18:21.958042+00:00 | task.provisioning | `8155c7a33a5918a2` |
| 6 | 2026-11-06T07:18:21.963629+00:00 | task.provisioning | `3f77731e4ece9885` |
| 7 | 2026-11-06T07:18:53.919279+00:00 | vm.created | `0efd88d82aa3ebf3` |
| 8 | 2026-11-06T07:19:09.261786+00:00 | vm.created | `a4fdf3c7399e8b69` |
| 9 | 2026-11-06T07:20:02.113180+00:00 | vm.runner_ready | `b08246acaa1ce256` |
| 10 | 2026-11-06T07:20:02.113381+00:00 | task.running | `fc5d9f48ab8b7572` |
| 11 | 2026-11-06T07:20:08.326013+00:00 | egress.denied | `71e120c5fc8b5251` |
| 12 | 2026-11-06T07:20:08.326118+00:00 | egress.denied | `970bd490aed73dfb` |
| 13 | 2026-11-06T07:20:08.326199+00:00 | egress.denied | `1ed40ceea4e61915` |
| 14 | 2026-11-06T07:20:08.326251+00:00 | egress.denied | `68e0b3a9d1893d9c` |
| 15 | 2026-11-06T07:20:08.326296+00:00 | egress.denied | `1051fa6d225150cd` |
| 16 | 2026-11-06T07:20:08.326339+00:00 | egress.denied | `191d6fa02ae9f676` |
| 17 | 2026-11-06T07:20:08.326387+00:00 | step.finished | `030142142e968b90` |
| 18 | 2026-11-06T07:20:08.326519+00:00 | task.verifying | `4b09e939da9c2536` |
| 19 | 2026-11-06T07:20:17.470452+00:00 | vm.runner_ready | `ab2f2a985016b0c7` |
| 20 | 2026-11-06T07:20:23.640871+00:00 | egress.denied | `9c81c95b2f5e6af2` |
| 21 | 2026-11-06T07:20:23.640976+00:00 | egress.denied | `5c0c7b1fa03cf12a` |
| 22 | 2026-11-06T07:20:23.641032+00:00 | egress.denied | `937ecf05400527f9` |
| 23 | 2026-11-06T07:20:23.641081+00:00 | egress.denied | `126e619e057f5dc0` |
| 24 | 2026-11-06T07:20:23.641128+00:00 | egress.denied | `00640a35a73b4de7` |
| 25 | 2026-11-06T07:20:23.641191+00:00 | egress.denied | `e8eca89bc34ac078` |
| 26 | 2026-11-06T07:20:23.641252+00:00 | step.finished | `7351bbdaa1a6aa3a` |
| 27 | 2026-11-06T07:20:23.641368+00:00 | task.destroying | `4395a124ad1120ef` |
| 28 | 2026-11-06T07:20:24.492427+00:00 | vm.destroyed | `bce35c8b2911cad7` |
| 29 | 2026-11-06T07:20:26.156755+00:00 | cost.tokens | `1f3ede3b456216a8` |
| 30 | 2026-11-06T07:20:26.156930+00:00 | verify.verdict | `f8e339bc994370b1` |
| 31 | 2026-11-06T07:20:26.157054+00:00 | task.scanning | `66126f1bfd8102fd` |
| 32 | 2026-11-06T07:20:26.171029+00:00 | secret_scan.done | `72f695ca91afaad3` |
| 33 | 2026-11-06T07:20:26.171139+00:00 | task.destroying | `53372896572288ac` |
| 34 | 2026-11-06T07:20:26.671661+00:00 | vm.destroyed | `d7ec09e961fe9e96` |
| 35 | 2026-11-06T07:20:26.673489+00:00 | task.verified | `ad1c64eb0369d441` |
