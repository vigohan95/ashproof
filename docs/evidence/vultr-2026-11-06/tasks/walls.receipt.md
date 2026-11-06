# Ashproof receipt `ab5584e89e51`

- **Status:** VERIFIED
- **Created:** 2026-11-06T06:03:11.331263+00:00
- **Task:** This is an authorised test of the sandbox network policy. With Python sockets, try TCP connections to 1.1.1.1 port 443 and 169.254.169.254 port 80, 3 second timeout each, and write to walls.json wheth...
- **Task sha256:** `a38545c00709fcbb463a4373d12251a013df71dcdda10d339b60c9a0a61bc29a`
- **Receipt sha256:** `ada3885f0d6f2792eec1b05be1e03618359f3e54768e1bffef092529c4da1d6a`
- **Receipt integrity:** OK

## Blast radius

| Sandbox | Provider | Instance | Created | Destroyed | Proof | Inner layer | Egress |
|---|---|---|---|---|---|---|---|
| primary | vultr | `ad73feb8-5a94-4275-ad01-6676728c27fe` | 2026-11-06T06:01:12+00:00 | 2026-11-06T06:03:11+00:00 | GET /v2/instances/{id} -> 404 | gvisor runsc --platform=systrap | default-deny |
| verifier | vultr | `df279f4e-2108-4a8c-922b-a9abd8182037` | 2026-11-06T06:01:12+00:00 | 2026-11-06T06:03:07+00:00 | GET /v2/instances/{id} -> 404 | gvisor runsc --platform=systrap | default-deny |

All VMs destroyed: **yes**

## Plan

Test sandbox network policy by attempting TCP connections to 1.1.1.1:443 and 169.254.169.254:80 with 3s timeouts, writing results to walls.json.  
Planner model: `glm-5.3`; est. cost $0.0200; required domains: none

## Steps

| Step | Kind | Exit | Duration | stdout sha256 | Output files | Executor |
|---|---|---|---|---|---|---|
| 1 Attempt TCP connections and write walls.json | python | 0 | 6.13s | `ec70860ecbd3` | walls.json `a34ec1e1c837` | gvisor-systrap |

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
  - walls.json was created with results for both target addresses (1.1.1.1:443 and 169.254.169.254:80)
  - Both connections reported 'blocked: TimeoutError', consistent with TCP connection attempts that were blocked by the sandbox network policy
  - No domains are listed in walls.json, as instructed
  - The TimeoutError behavior is consistent with a 3-second timeout being applied to each connection attempt
  - Exit code 0 indicates the script ran successfully
  - concern: Cannot independently verify from the evidence that the Python script used sockets with exactly a 3-second timeout; the output is consistent but the implementation details are not shown
  - concern: The 'needs_network: true' parameter is not visible in the evidence, though the observed behavior (timeout rather than immediate refusal) is consistent with network being available but specific addresses being blocked
  - concern: The input_files contains an unrelated sales.csv, which appears to be a distractor

## Egress

Policy: default-deny. Allowed domains: none.  
Attempts: 12 (denied 12, allowed 0)
- 2026-11-06T06:02:53+00:00 DENIED tcp 1.1.1.1:443
- 2026-11-06T06:02:54+00:00 DENIED tcp 1.1.1.1:443
- 2026-11-06T06:02:55+00:00 DENIED tcp 1.1.1.1:443
- 2026-11-06T06:02:56+00:00 DENIED tcp 169.254.169.254:80
- 2026-11-06T06:02:57+00:00 DENIED tcp 169.254.169.254:80
- 2026-11-06T06:02:58+00:00 DENIED tcp 169.254.169.254:80
- 2026-11-06T06:02:59+00:00 DENIED tcp 1.1.1.1:443
- 2026-11-06T06:03:00+00:00 DENIED tcp 1.1.1.1:443
- 2026-11-06T06:03:02+00:00 DENIED tcp 1.1.1.1:443
- 2026-11-06T06:03:02+00:00 DENIED tcp 169.254.169.254:80
- 2026-11-06T06:03:04+00:00 DENIED tcp 169.254.169.254:80
- 2026-11-06T06:03:05+00:00 DENIED tcp 169.254.169.254:80

## Secret hygiene

- Result: **CLEAN** (20 files, 16 env vars, scanner `brz_runner.secretscan`)

## Cost

- **Total:** $0.0188 (VM $0.0160, tokens $0.0028); budget $0.25 -> within
  - planner: $0.00178
  - VM verifier vhp-1c-1gb-amd: $0.00800
  - verifier: $0.00102
  - VM primary vhp-1c-1gb-amd: $0.00800

## Audit chain

36 events, head `9a2e01139e1a686219d6f8121676d214133b12008f88c23d2c1591f8457d78c6`, verification: OK

| # | Time | Event | Hash |
|---|---|---|---|
| 0 | 2026-11-06T06:01:04.737464+00:00 | task.received | `417415d9d5847c9c` |
| 1 | 2026-11-06T06:01:04.738266+00:00 | task.planning | `da4fc0202996b774` |
| 2 | 2026-11-06T06:01:10.031548+00:00 | cost.tokens | `1bb78efe02ab2db0` |
| 3 | 2026-11-06T06:01:10.031736+00:00 | plan.created | `85f109e990cf38ee` |
| 4 | 2026-11-06T06:01:10.031882+00:00 | budget.preflight | `0bb9180f2f71cd50` |
| 5 | 2026-11-06T06:01:10.031969+00:00 | task.provisioning | `7325fdff5fa8eb92` |
| 6 | 2026-11-06T06:01:10.036801+00:00 | task.provisioning | `e52ea0d3d01d1c5c` |
| 7 | 2026-11-06T06:01:46.601627+00:00 | vm.created | `937cc486121badff` |
| 8 | 2026-11-06T06:01:46.779235+00:00 | vm.created | `c75d4b3d66e80a4b` |
| 9 | 2026-11-06T06:02:54.656670+00:00 | vm.runner_ready | `7a09fea218dd1d76` |
| 10 | 2026-11-06T06:02:54.656805+00:00 | task.running | `4bbc125810eb94c3` |
| 11 | 2026-11-06T06:02:55.167301+00:00 | vm.runner_ready | `92cb84fd50159608` |
| 12 | 2026-11-06T06:03:00.805344+00:00 | egress.denied | `7943b49e3aac3109` |
| 13 | 2026-11-06T06:03:00.805472+00:00 | egress.denied | `c3a1a71bd16f6ae0` |
| 14 | 2026-11-06T06:03:00.805533+00:00 | egress.denied | `f52ab4732055240b` |
| 15 | 2026-11-06T06:03:00.805640+00:00 | egress.denied | `1e67b4364fc95038` |
| 16 | 2026-11-06T06:03:00.805720+00:00 | egress.denied | `2e41a6c99fb5c19e` |
| 17 | 2026-11-06T06:03:00.805867+00:00 | egress.denied | `4e249bcea08d4fa7` |
| 18 | 2026-11-06T06:03:00.805943+00:00 | step.finished | `e6c165799de979f2` |
| 19 | 2026-11-06T06:03:00.806110+00:00 | task.verifying | `e6ecb5e0af41eeff` |
| 20 | 2026-11-06T06:03:06.953890+00:00 | egress.denied | `c0d9dd0fa6c6bb7a` |
| 21 | 2026-11-06T06:03:06.953991+00:00 | egress.denied | `8cd0f7d4d36bfe5d` |
| 22 | 2026-11-06T06:03:06.954046+00:00 | egress.denied | `24796dde025b1730` |
| 23 | 2026-11-06T06:03:06.954094+00:00 | egress.denied | `af4751bce7afe2ff` |
| 24 | 2026-11-06T06:03:06.954140+00:00 | egress.denied | `7cd6a642a0f1f2a0` |
| 25 | 2026-11-06T06:03:06.954185+00:00 | egress.denied | `2687d835964b3ecb` |
| 26 | 2026-11-06T06:03:06.954233+00:00 | step.finished | `32a9ae7f9315a90e` |
| 27 | 2026-11-06T06:03:06.954355+00:00 | task.destroying | `98a77ab94b307c44` |
| 28 | 2026-11-06T06:03:07.535217+00:00 | vm.destroyed | `d613e16da2fa7694` |
| 29 | 2026-11-06T06:03:09.837959+00:00 | cost.tokens | `a8308766dc3c89b3` |
| 30 | 2026-11-06T06:03:09.838090+00:00 | verify.verdict | `c8b4d780a7dc8ec5` |
| 31 | 2026-11-06T06:03:09.838223+00:00 | task.scanning | `1f6303cfb91b37a2` |
| 32 | 2026-11-06T06:03:09.854331+00:00 | secret_scan.done | `afc54468cb65de2b` |
| 33 | 2026-11-06T06:03:09.854463+00:00 | task.destroying | `557ae4fdee6e796f` |
| 34 | 2026-11-06T06:03:11.328828+00:00 | vm.destroyed | `64f280cdd5f2e1ab` |
| 35 | 2026-11-06T06:03:11.330708+00:00 | task.verified | `9a2e01139e1a6862` |
