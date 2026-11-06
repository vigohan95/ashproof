# Ashproof receipt `d78825fab7d3`

- **Status:** VERIFIED
- **Created:** 2026-11-06T09:05:15.069329+00:00
- **Task:** Fetch https://example.com and write the text of its title tag to title.txt
- **Task sha256:** `b55c2f72d0269a1a0811e890fc2e751883be984d5c6d12f2f9e73c5883149cd5`
- **Receipt sha256:** `b126641991daeac96d6c9223d92c88cdbd3e8011b5cdd0df188969f75da7aa62`
- **Receipt integrity:** OK
- **Signed:** Ed25519, key `ee7704217a7ac13d`, at 2026-11-06T09:05:15.071193+00:00

## What was refused

Nothing was refused.

## Blast radius

| Sandbox | Provider | Instance | Created | Destroyed | Proof | Inner layer | Egress |
|---|---|---|---|---|---|---|---|
| verifier | vultr | `3b32ce5d-dca3-4725-af23-725a7fbd4421` | 2026-11-06T09:03:16+00:00 | 2026-11-06T09:05:12+00:00 | GET /v2/instances/{id} -> 404 | gvisor runsc --platform=systrap | default-deny |
| primary | vultr | `ff6e91c3-2906-4360-890d-d35570616b98` | 2026-11-06T09:03:16+00:00 | 2026-11-06T09:05:15+00:00 | GET /v2/instances/{id} -> 404 | gvisor runsc --platform=systrap | default-deny |

All VMs destroyed: **yes**

## Plan

Fetch https://example.com and write its <title> text to /work/out/title.txt  
Planner model: `glm-5.3`; est. cost $0.0200; required domains: example.com

## Steps

| Step | Kind | Exit | Duration | stdout sha256 | Output files | Executor |
|---|---|---|---|---|---|---|
| fetch_title Fetch example.com and extract title | python | 0 | 0.27s | `aa57cf1d596d` | title.txt `162b81548a8d` | gvisor-systrap |

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
  - The title of https://example.com is well-known to be 'Example Domain'
  - The evidence shows title.txt contains 'Example Domain' which matches the expected title tag text
  - Exit code 0 with no stderr indicates the fetch and write operation succeeded
  - The input file sales.csv is irrelevant to this task and was not needed
- **Content filter:** `nemotron-3.5-content-safety`
  - input sales.csv: safe
  - output fetch_title/stdout: safe
  - output fetch_title/title.txt: safe

## Egress

Policy: default-deny. Allowed domains: example.com.  
Attempts: 2 (denied 0, allowed 2)
- 2026-11-06T09:04:56+00:00 ALLOWED tcp 104.20.23.154:443
- 2026-11-06T09:05:12+00:00 ALLOWED tcp 104.20.23.154:443

## Secret hygiene

- Result: **CLEAN** (20 files, 16 env vars, scanner `brz_runner.secretscan`)

## Cost

- **Total:** $0.0197 (VM $0.0179, tokens $0.0018); budget $0.25 -> within
  - planner: $0.00132
  - VM verifier vhp-1c-1gb-amd: $0.00893
  - safety model: $0.00007
  - verifier: $0.00041
  - VM primary vhp-1c-1gb-amd: $0.00893

## Audit chain

28 events, head `b653e0e83f9ba2015a37a2f3a7eadf6fc5c987096922618e5a1e1c48ae1d9cf3`, verification: OK

| # | Time | Event | Hash |
|---|---|---|---|
| 0 | 2026-11-06T09:03:12.584644+00:00 | task.received | `3a83c70c35fc565d` |
| 1 | 2026-11-06T09:03:12.586273+00:00 | task.planning | `3025f9a7c779f033` |
| 2 | 2026-11-06T09:03:15.125337+00:00 | cost.tokens | `c7c2ba62c5a01f0f` |
| 3 | 2026-11-06T09:03:15.125470+00:00 | plan.created | `fc5d28a25225ee34` |
| 4 | 2026-11-06T09:03:15.125617+00:00 | budget.preflight | `c2127a6f3fb758e5` |
| 5 | 2026-11-06T09:03:15.125705+00:00 | task.provisioning | `04b8a56f634890f4` |
| 6 | 2026-11-06T09:03:15.130934+00:00 | task.provisioning | `11c26147a56517d6` |
| 7 | 2026-11-06T09:03:48.250118+00:00 | vm.created | `970b837f804ff558` |
| 8 | 2026-11-06T09:04:03.774248+00:00 | vm.created | `1beb287479280a18` |
| 9 | 2026-11-06T09:04:56.638325+00:00 | vm.runner_ready | `0c9eb3c317e81a78` |
| 10 | 2026-11-06T09:04:56.638492+00:00 | task.running | `b4393d790d50ad83` |
| 11 | 2026-11-06T09:04:56.918941+00:00 | egress.allowed | `b448f01a05dcb7cd` |
| 12 | 2026-11-06T09:04:56.919074+00:00 | step.finished | `da40ffd653beb88b` |
| 13 | 2026-11-06T09:04:56.919223+00:00 | task.verifying | `9fa5831cdda3ffde` |
| 14 | 2026-11-06T09:05:12.069950+00:00 | vm.runner_ready | `0c0a22bd55f37d5e` |
| 15 | 2026-11-06T09:05:12.444843+00:00 | egress.allowed | `58e4d3b3cd6fca70` |
| 16 | 2026-11-06T09:05:12.444961+00:00 | step.finished | `8dafd0e63a7d75bc` |
| 17 | 2026-11-06T09:05:12.445162+00:00 | task.destroying | `12b6446e761cd2b3` |
| 18 | 2026-11-06T09:05:12.880846+00:00 | vm.destroyed | `71d7bab078561a58` |
| 19 | 2026-11-06T09:05:14.632358+00:00 | cost.tokens | `799d34e5dd9b1d3d` |
| 20 | 2026-11-06T09:05:14.632494+00:00 | safety.review | `0aac55dde94760f2` |
| 21 | 2026-11-06T09:05:14.632600+00:00 | cost.tokens | `8669bbbda7ca7f77` |
| 22 | 2026-11-06T09:05:14.632674+00:00 | verify.verdict | `95a1e99b5e7b5ace` |
| 23 | 2026-11-06T09:05:14.632775+00:00 | task.scanning | `b8c964f2f48ef55d` |
| 24 | 2026-11-06T09:05:14.644652+00:00 | secret_scan.done | `afa57ac135f682a9` |
| 25 | 2026-11-06T09:05:14.644762+00:00 | task.destroying | `560bf6e4542f3f84` |
| 26 | 2026-11-06T09:05:15.066782+00:00 | vm.destroyed | `32c61305eaa613be` |
| 27 | 2026-11-06T09:05:15.068795+00:00 | task.verified | `b653e0e83f9ba201` |
