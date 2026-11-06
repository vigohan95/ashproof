# Ashproof receipt `79256a61c790`

- **Status:** VERIFIED
- **Created:** 2026-11-06T05:52:27.782809+00:00
- **Task:** Total the amount column per region in sales.csv and write summary.json
- **Task sha256:** `9ae05af7a8024f5c7c09a01ea5d8a39096df157dd0253e1ee028e093a5e7c297`
- **Receipt sha256:** `2fc6d40b800821885da86f179bfb0321619e26c9baee19c6678234834e46ff03`
- **Receipt integrity:** OK

## Blast radius

| Sandbox | Provider | Instance | Created | Destroyed | Proof | Inner layer | Egress |
|---|---|---|---|---|---|---|---|
| primary | vultr | `cb369b8f-7a62-4497-b2f4-10e7df9559dc` | 2026-11-06T05:50:44+00:00 | 2026-11-06T05:52:27+00:00 | GET /v2/instances/{id} -> 404 | gvisor runsc --platform=systrap | default-deny |
| verifier | vultr | `fef237d0-1efa-4743-bd55-a88d0e0fd65d` | 2026-11-06T05:50:44+00:00 | 2026-11-06T05:52:26+00:00 | GET /v2/instances/{id} -> 404 | gvisor runsc --platform=systrap | default-deny |

All VMs destroyed: **yes**

## Plan

Aggregate the amount column per region from /work/input/sales.csv and write a summary.json to /work/out/.  
Planner model: `glm-5.3`; est. cost $0.0100; required domains: none

## Steps

| Step | Kind | Exit | Duration | stdout sha256 | Output files | Executor |
|---|---|---|---|---|---|---|
| 1 Aggregate sales.csv per region and write summary.json | python | 0 | 0.12s | `b2afba68bc30` | summary.json `834fc0e2acc4` | gvisor-systrap |

## Verification

- **Verdict:** PASSED (model: `qwen3.8-27b`)
- **Independent re-run:** performed; hashes identical: True
  - [x] 1:exit_code exit_code=0
  - [x] 1:output:summary.json present
  - [x] assert:file_exists:summary.json
  - [x] assert:stdout_contains:{
  - [x] rerun:hashes_identical all outputs byte-identical across two clean sandboxes
- **Model review:** satisfies_task=True confidence=0.99
  - Expected totals: north=15, south=20, west=2.5
  - summary.json contains exactly {"north": 15.0, "south": 20.0, "west": 2.5}
  - All values match the recomputation from the input CSV

## Egress

Policy: default-deny. Allowed domains: none.  
Attempts: 0 (denied 0, allowed 0)

## Secret hygiene

- Result: **CLEAN** (20 files, 16 env vars, scanner `brz_runner.secretscan`)

## Cost

- **Total:** $0.0178 (VM $0.0160, tokens $0.0018); budget $0.25 -> within
  - planner: $0.00150
  - VM verifier vhp-1c-1gb-amd: $0.00800
  - verifier: $0.00029
  - VM primary vhp-1c-1gb-amd: $0.00800

## Audit chain

24 events, head `1a2771a323902609a5b285530dfd494e48b3347db34bea70682b5e434c059dc0`, verification: OK

| # | Time | Event | Hash |
|---|---|---|---|
| 0 | 2026-11-06T05:50:37.442802+00:00 | task.received | `a91d12de1b6954b7` |
| 1 | 2026-11-06T05:50:37.444415+00:00 | task.planning | `25a726a57052f251` |
| 2 | 2026-11-06T05:50:39.244303+00:00 | cost.tokens | `a25bacf3c54a5920` |
| 3 | 2026-11-06T05:50:39.244459+00:00 | plan.created | `83b57709a23b0d20` |
| 4 | 2026-11-06T05:50:39.244629+00:00 | budget.preflight | `1347f6c52a11007a` |
| 5 | 2026-11-06T05:50:39.244719+00:00 | task.provisioning | `a44352fe25e0116a` |
| 6 | 2026-11-06T05:50:39.250247+00:00 | task.provisioning | `d813e54e5e72218d` |
| 7 | 2026-11-06T05:51:17.152663+00:00 | vm.created | `597d861a1eac2892` |
| 8 | 2026-11-06T05:51:17.214818+00:00 | vm.created | `20111576077caf8b` |
| 9 | 2026-11-06T05:52:25.407884+00:00 | vm.runner_ready | `2be99797a49db5fa` |
| 10 | 2026-11-06T05:52:25.408017+00:00 | task.running | `71f7929978a741a7` |
| 11 | 2026-11-06T05:52:25.410501+00:00 | vm.runner_ready | `17d3de2931824720` |
| 12 | 2026-11-06T05:52:25.539085+00:00 | step.finished | `f1183c2a9198d298` |
| 13 | 2026-11-06T05:52:25.539281+00:00 | task.verifying | `f1b4ac29bc9a5ead` |
| 14 | 2026-11-06T05:52:25.671107+00:00 | step.finished | `689a04856850a79d` |
| 15 | 2026-11-06T05:52:25.671309+00:00 | task.destroying | `0ab8feab51d81854` |
| 16 | 2026-11-06T05:52:26.269150+00:00 | vm.destroyed | `4bb44bc360be5fd5` |
| 17 | 2026-11-06T05:52:27.071206+00:00 | cost.tokens | `768fec865ca2d6a8` |
| 18 | 2026-11-06T05:52:27.071333+00:00 | verify.verdict | `6b3804414da16a31` |
| 19 | 2026-11-06T05:52:27.071451+00:00 | task.scanning | `2d976f0412fe429e` |
| 20 | 2026-11-06T05:52:27.084651+00:00 | secret_scan.done | `7fb6b5b0039c8708` |
| 21 | 2026-11-06T05:52:27.084769+00:00 | task.destroying | `35e560ce5438209c` |
| 22 | 2026-11-06T05:52:27.780828+00:00 | vm.destroyed | `fe74fe497a67dd72` |
| 23 | 2026-11-06T05:52:27.782264+00:00 | task.verified | `1a2771a323902609` |
