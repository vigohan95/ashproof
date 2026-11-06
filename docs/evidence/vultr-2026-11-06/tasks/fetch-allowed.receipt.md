# Ashproof receipt `8a5565115fbf`

- **Status:** FAILED
- **Created:** 2026-11-06T05:54:50.629485+00:00
- **Task:** Fetch https://example.com and write the text of its h1 heading to title.txt
- **Task sha256:** `b7f459239a5c73fd57defbbdaa6cbc703adbd6844880a0f3f3575d86d398dcac`
- **Receipt sha256:** `6a5b18e3d4b4ae1d77baa86eea0339e938c276ddbb8b9a29ab3a5acb154656c1`
- **Receipt integrity:** OK

## Blast radius

| Sandbox | Provider | Instance | Created | Destroyed | Proof | Inner layer | Egress |
|---|---|---|---|---|---|---|---|
| primary | vultr | `bea0126a-f5b1-457c-99a6-3a00bb7ee7c9` | 2026-11-06T05:53:03+00:00 | 2026-11-06T05:54:50+00:00 | GET /v2/instances/{id} -> 404 | gvisor runsc --platform=systrap | default-deny |
| verifier | vultr | `5099c84b-e6c4-44b5-a08e-4617096660c3` | 2026-11-06T05:53:05+00:00 | 2026-11-06T05:54:50+00:00 | GET /v2/instances/{id} -> 404 | gvisor runsc --platform=systrap | default-deny |

All VMs destroyed: **yes**

## Plan

Fetch https://example.com and extract the h1 heading text into title.txt  
Planner model: `glm-5.3`; est. cost $0.0100; required domains: example.com

## Steps

| Step | Kind | Exit | Duration | stdout sha256 | Output files | Executor |
|---|---|---|---|---|---|---|
| fetch_and_extract Fetch example.com and extract h1 text (repaired) | python | 1 | 0.21s | `e3b0c44298fc` | - | gvisor-systrap |

## Verification

- **Verdict:** FAILED (model: ``)
- **Independent re-run:** not performed; hashes identical: None

## Egress

Policy: default-deny. Allowed domains: example.com.  
Attempts: 2 (denied 0, allowed 2)
- 2026-11-06T05:54:44+00:00 ALLOWED tcp 104.20.23.154:443
- 2026-11-06T05:54:48+00:00 ALLOWED tcp 104.20.23.154:443

## Secret hygiene

Scan not performed.

## Cost

- **Total:** $0.0196 (VM $0.0160, tokens $0.0036); budget $0.25 -> within
  - planner: $0.00134
  - planner.repair: $0.00225
  - VM primary vhp-1c-1gb-amd: $0.00800
  - VM verifier vhp-1c-1gb-amd: $0.00800

## Audit chain

23 events, head `12f1d2242d5fe24d428f5beb0498e60e82cf35080b97212e49d1978627b64d6d`, verification: OK

| # | Time | Event | Hash |
|---|---|---|---|
| 0 | 2026-11-06T05:52:59.853743+00:00 | task.received | `68c3dbe0fc848b98` |
| 1 | 2026-11-06T05:52:59.855603+00:00 | task.planning | `56ac496b0f2a4d5b` |
| 2 | 2026-11-06T05:53:03.327774+00:00 | cost.tokens | `f2e2420182329ee3` |
| 3 | 2026-11-06T05:53:03.327931+00:00 | plan.created | `00a4d48fc9fbdc50` |
| 4 | 2026-11-06T05:53:03.328087+00:00 | budget.preflight | `c56ee6eb7311e987` |
| 5 | 2026-11-06T05:53:03.328186+00:00 | task.provisioning | `bf64086208ac6de9` |
| 6 | 2026-11-06T05:53:03.333397+00:00 | task.provisioning | `3aec4913fb6ee643` |
| 7 | 2026-11-06T05:53:37.074469+00:00 | vm.created | `2f11421f00886d0d` |
| 8 | 2026-11-06T05:53:38.212900+00:00 | vm.created | `f84bbd590527ad2d` |
| 9 | 2026-11-06T05:54:45.184672+00:00 | vm.runner_ready | `3a9494a0b16534bc` |
| 10 | 2026-11-06T05:54:45.184816+00:00 | task.running | `74f4722d72c105e2` |
| 11 | 2026-11-06T05:54:45.416202+00:00 | egress.allowed | `3a9559c700af7594` |
| 12 | 2026-11-06T05:54:45.416293+00:00 | step.finished | `85c185e9d033541f` |
| 13 | 2026-11-06T05:54:46.207347+00:00 | vm.runner_ready | `9d961aef6fe063c4` |
| 14 | 2026-11-06T05:54:49.671237+00:00 | cost.tokens | `1b45ff8b4b55d95f` |
| 15 | 2026-11-06T05:54:49.671348+00:00 | step.repaired | `8a3623512fb8624e` |
| 16 | 2026-11-06T05:54:49.902365+00:00 | egress.allowed | `a0b266bb68ed38ac` |
| 17 | 2026-11-06T05:54:49.902475+00:00 | step.finished | `31feac67e5607d4d` |
| 18 | 2026-11-06T05:54:49.902737+00:00 | task.destroying | `3bc4654c2e4d6241` |
| 19 | 2026-11-06T05:54:50.301876+00:00 | vm.destroyed | `9adc3709beb50700` |
| 20 | 2026-11-06T05:54:50.302028+00:00 | task.destroying | `ee51def641bb98c9` |
| 21 | 2026-11-06T05:54:50.628865+00:00 | vm.destroyed | `838343b17a9e9e9d` |
| 22 | 2026-11-06T05:54:50.629277+00:00 | task.failed | `12f1d2242d5fe24d` |
