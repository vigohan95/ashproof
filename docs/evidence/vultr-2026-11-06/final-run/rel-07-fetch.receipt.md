# Ashproof receipt `ac8657fa89d4`

- **Status:** VERIFIED
- **Created:** 2026-11-06T09:13:17.216444+00:00
- **Task:** Fetch https://example.com and write the text of its title tag to title.txt
- **Task sha256:** `b55c2f72d0269a1a0811e890fc2e751883be984d5c6d12f2f9e73c5883149cd5`
- **Receipt sha256:** `72b52fdf8adac796fdeea8a2c70b8451d41313ab995523670e7b181de4be45f1`
- **Receipt integrity:** OK
- **Signed:** Ed25519, key `ee7704217a7ac13d`, at 2026-11-06T09:13:17.218451+00:00

## What was refused

Nothing was refused.

## Blast radius

| Sandbox | Provider | Instance | Created | Destroyed | Proof | Inner layer | Egress |
|---|---|---|---|---|---|---|---|
| primary | vultr | `6bd44a8e-1226-4459-86e9-7ab0da5ce5d2` | 2026-11-06T09:11:33+00:00 | 2026-11-06T09:13:17+00:00 | GET /v2/instances/{id} -> 404 | gvisor runsc --platform=systrap | default-deny |
| verifier | vultr | `5878829e-d566-4703-84a0-f8fdf338e689` | 2026-11-06T09:11:34+00:00 | 2026-11-06T09:13:15+00:00 | GET /v2/instances/{id} -> 404 | gvisor runsc --platform=systrap | default-deny |

All VMs destroyed: **yes**

## Plan

Fetch https://example.com and write its <title> text to /work/out/title.txt  
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
  - [x] safety:step_output nemotron-3.5-content-safety marked nothing unsafe
  - [x] egress:nothing_unexpected_refused no packet was refused
- **Model review:** satisfies_task=True confidence=0.95
  - The evidence shows a successful fetch (exit_code 0) with stdout 'Example Domain\n'
  - The file title.txt contains 'Example Domain\n' which matches the known <title> of https://example.com
  - The task required writing the title tag text to title.txt, which is exactly what was done
  - concern: The input_files contains an unrelated sales.csv which is a distractor and was correctly ignored
- **Content filter:** `nemotron-3.5-content-safety`
  - input sales.csv: safe
  - output fetch_title/stdout: safe
  - output fetch_title/title.txt: safe

## Egress

Policy: default-deny. Allowed domains: example.com.  
Attempts: 2 (denied 0, allowed 2)
- 2026-11-06T09:13:02+00:00 ALLOWED tcp 104.20.23.154:443
- 2026-11-06T09:13:13+00:00 ALLOWED tcp 104.20.23.154:443

## Secret hygiene

- Result: **CLEAN** (20 files, 16 env vars, scanner `brz_runner.secretscan`)

## Cost

- **Total:** $0.0196 (VM $0.0179, tokens $0.0018); budget $0.25 -> within
  - planner: $0.00137
  - VM verifier vhp-1c-1gb-amd: $0.00893
  - safety model: $0.00007
  - verifier: $0.00034
  - VM primary vhp-1c-1gb-amd: $0.00893

## Audit chain

28 events, head `f4cab0620315833eeeaa9b86d2c33329f0e5c3ee09f33c5bb44c7c4b5b6c04ed`, verification: OK

| # | Time | Event | Hash |
|---|---|---|---|
| 0 | 2026-11-06T09:11:25.234382+00:00 | task.received | `2321d5e8c21fc910` |
| 1 | 2026-11-06T09:11:25.236560+00:00 | task.planning | `fba691ff7ca35465` |
| 2 | 2026-11-06T09:11:32.288207+00:00 | cost.tokens | `4cf1c8871ae65c0c` |
| 3 | 2026-11-06T09:11:32.288355+00:00 | plan.created | `56e0b6c15318579b` |
| 4 | 2026-11-06T09:11:32.288507+00:00 | budget.preflight | `c39ee5ddb5672362` |
| 5 | 2026-11-06T09:11:32.288613+00:00 | task.provisioning | `114e4cbf10965dc8` |
| 6 | 2026-11-06T09:11:32.293610+00:00 | task.provisioning | `ac2ce99f79bf7139` |
| 7 | 2026-11-06T09:11:55.106778+00:00 | vm.created | `e3e5ed08469e2723` |
| 8 | 2026-11-06T09:12:06.025358+00:00 | vm.created | `e85cd568cae3dade` |
| 9 | 2026-11-06T09:13:03.552040+00:00 | vm.runner_ready | `2db1d4c8104b9c59` |
| 10 | 2026-11-06T09:13:03.552174+00:00 | task.running | `95652a4c1f320783` |
| 11 | 2026-11-06T09:13:03.783057+00:00 | egress.allowed | `c09acdfc0516de7b` |
| 12 | 2026-11-06T09:13:03.783165+00:00 | step.finished | `5f0e62daf967113c` |
| 13 | 2026-11-06T09:13:03.783295+00:00 | task.verifying | `a8517ae244f91c91` |
| 14 | 2026-11-06T09:13:14.581545+00:00 | vm.runner_ready | `787e87d3e525c5f0` |
| 15 | 2026-11-06T09:13:14.813287+00:00 | egress.allowed | `7c4402c20879d69a` |
| 16 | 2026-11-06T09:13:14.813442+00:00 | step.finished | `47aa4bf2a50cd106` |
| 17 | 2026-11-06T09:13:14.813693+00:00 | task.destroying | `83fedf3b729dfb4e` |
| 18 | 2026-11-06T09:13:15.114892+00:00 | vm.destroyed | `905a0bc99496bfde` |
| 19 | 2026-11-06T09:13:16.802268+00:00 | cost.tokens | `0d0f3a077c333e5b` |
| 20 | 2026-11-06T09:13:16.802407+00:00 | safety.review | `406461f5751e8496` |
| 21 | 2026-11-06T09:13:16.802490+00:00 | cost.tokens | `c96cbbf463d9d1c0` |
| 22 | 2026-11-06T09:13:16.802557+00:00 | verify.verdict | `fca0ce085b9ec288` |
| 23 | 2026-11-06T09:13:16.802728+00:00 | task.scanning | `70749744e9cf435b` |
| 24 | 2026-11-06T09:13:16.815613+00:00 | secret_scan.done | `d2fb3755be90e0a3` |
| 25 | 2026-11-06T09:13:16.815772+00:00 | task.destroying | `a591f69dfd1fa93b` |
| 26 | 2026-11-06T09:13:17.214287+00:00 | vm.destroyed | `938ea20c9ca4a031` |
| 27 | 2026-11-06T09:13:17.215989+00:00 | task.verified | `f4cab0620315833e` |
