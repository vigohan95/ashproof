# Ashproof receipt `17c481766fdb`

- **Status:** FAILED
- **Created:** 2026-11-06T06:02:59.173619+00:00
- **Task:** Fetch https://example.com and write the text of its h1 heading to title.txt
- **Task sha256:** `b7f459239a5c73fd57defbbdaa6cbc703adbd6844880a0f3f3575d86d398dcac`
- **Receipt sha256:** `cfb25c1c919d3d38df2e3e5c4fe7500b79bf7a3a117d5c986c138acacf161a25`
- **Receipt integrity:** OK

## Blast radius

| Sandbox | Provider | Instance | Created | Destroyed | Proof | Inner layer | Egress |
|---|---|---|---|---|---|---|---|
| verifier | vultr | `590319cb-5cb1-4c96-afe8-3ab81e885318` | 2026-11-06T06:01:08+00:00 | 2026-11-06T06:02:58+00:00 | GET /v2/instances/{id} -> 404 | gvisor runsc --platform=systrap | default-deny |
| primary | vultr | `9fa8e500-f3f7-4869-bf52-3d06b2f496d0` | 2026-11-06T06:01:09+00:00 | 2026-11-06T06:02:59+00:00 | GET /v2/instances/{id} -> 404 | gvisor runsc --platform=systrap | default-deny |

All VMs destroyed: **yes**

## Plan

Fetch https://example.com and extract the h1 heading text into title.txt  
Planner model: `glm-5.3`; est. cost $0.0200; required domains: example.com

## Steps

| Step | Kind | Exit | Duration | stdout sha256 | Output files | Executor |
|---|---|---|---|---|---|---|
| fetch_and_extract Fetch example.com and extract h1 text (repaired) | python | 1 | 0.22s | `e3b0c44298fc` | - | gvisor-systrap |

## Verification

- **Verdict:** FAILED (model: ``)
- **Independent re-run:** not performed; hashes identical: None

## Egress

Policy: default-deny. Allowed domains: example.com.  
Attempts: 2 (denied 0, allowed 2)
- 2026-11-06T06:02:51+00:00 ALLOWED tcp 104.20.23.154:443
- 2026-11-06T06:02:55+00:00 ALLOWED tcp 104.20.23.154:443

## Secret hygiene

Scan not performed.

## Cost

- **Total:** $0.0195 (VM $0.0160, tokens $0.0035); budget $0.25 -> within
  - planner: $0.00149
  - planner.repair: $0.00199
  - VM verifier vhp-1c-1gb-amd: $0.00800
  - VM primary vhp-1c-1gb-amd: $0.00800

## Audit chain

23 events, head `9d24dc90d2e2a7b3bd03736be6c5d2090bb295f71d5f60d09422154a21e01195`, verification: OK

| # | Time | Event | Hash |
|---|---|---|---|
| 0 | 2026-11-06T06:01:04.756745+00:00 | task.received | `53e6410c37d7e347` |
| 1 | 2026-11-06T06:01:04.757784+00:00 | task.planning | `055a17369314546d` |
| 2 | 2026-11-06T06:01:06.982332+00:00 | cost.tokens | `59ba7e328448609b` |
| 3 | 2026-11-06T06:01:06.982492+00:00 | plan.created | `5c866db643609e03` |
| 4 | 2026-11-06T06:01:06.982659+00:00 | budget.preflight | `d94ad35853686ffa` |
| 5 | 2026-11-06T06:01:06.982751+00:00 | task.provisioning | `5eb021e5f3e1ecc3` |
| 6 | 2026-11-06T06:01:06.988615+00:00 | task.provisioning | `a81c8d8d7162a720` |
| 7 | 2026-11-06T06:01:43.295374+00:00 | vm.created | `f0191469de695987` |
| 8 | 2026-11-06T06:01:43.996269+00:00 | vm.created | `ac579ce1651dd270` |
| 9 | 2026-11-06T06:02:51.585069+00:00 | vm.runner_ready | `506a59cf648e012d` |
| 10 | 2026-11-06T06:02:52.095892+00:00 | vm.runner_ready | `c93ce725495151ab` |
| 11 | 2026-11-06T06:02:52.096046+00:00 | task.running | `0ba6ecfa603a084d` |
| 12 | 2026-11-06T06:02:52.327811+00:00 | egress.allowed | `e0796a1ac975e73c` |
| 13 | 2026-11-06T06:02:52.327925+00:00 | step.finished | `ba41fbbf8942d2e4` |
| 14 | 2026-11-06T06:02:56.678201+00:00 | cost.tokens | `6e68ae77c7cd1bdd` |
| 15 | 2026-11-06T06:02:56.678333+00:00 | step.repaired | `0f2e48da877c1713` |
| 16 | 2026-11-06T06:02:56.908663+00:00 | egress.allowed | `659551b3e281a08b` |
| 17 | 2026-11-06T06:02:56.908781+00:00 | step.finished | `801c25c28fec65ec` |
| 18 | 2026-11-06T06:02:56.908996+00:00 | task.destroying | `819e5e08f129eaf3` |
| 19 | 2026-11-06T06:02:58.555492+00:00 | vm.destroyed | `dab12e891b34fbdc` |
| 20 | 2026-11-06T06:02:58.555669+00:00 | task.destroying | `4fce3ca4e8952173` |
| 21 | 2026-11-06T06:02:59.172884+00:00 | vm.destroyed | `4a2357e5e0378fb6` |
| 22 | 2026-11-06T06:02:59.173350+00:00 | task.failed | `9d24dc90d2e2a7b3` |
