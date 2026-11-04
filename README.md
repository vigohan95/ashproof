# Ashproof

**The VM burns. The proof stays.** Containment-first agent execution on Vultr. Every task gets its own
throwaway Vultr VM, runs with
outbound network denied by default and zero secrets inside, is re-run by an independent verifier in a
second clean VM, leaves a hash-chained receipt - and then the VM is deleted. `GET /v2/instances/{id}` -> `404`
is part of the receipt.

> Built for the Vultr "Agent Rush" hackathon (lablab.ai), Challenge 1 *Blast Radius Zero*: a system that
> **plans, dispatches and verifies real executed work** inside a sandbox. MIT licensed.

## The problem

Letting an AI agent run real code or browse real sites is the fastest way to get work done and the
fastest way to leak a key, exfiltrate a dataset or wreck an environment. The usual answer is one
long-lived VM with a container inside, all egress open, API keys in a config file, and "the model said
it worked". That is the baseline every sandboxing tutorial ships (including Vultr's own), and it is what
OWASP's Agentic Top 10 (ASI05) says is not enough.

## 60-second architecture

```
 browser / API client
        |  POST /tasks {task, files, budget, allowed_domains}
        v
+-------------------------------- control plane (FastAPI, Vultr Cloud Compute) --------------------------------+
|  holds the ONLY copies of VULTR_API_KEY and INFERENCE_API_KEY                                                |
|                                                                                                              |
|  Planner  glm-5.3 (Vultr Serverless Inference, json_schema)  -> Plan{steps, required_domains, est_cost}      |
|  Approval gate: new egress domains need a human click                                                        |
|  Budget breaker: projected $ > budget -> refuse before any VM                                                 |
|  Sandbox broker: POST /v2/instances (cloud-init) -> wait active -> runner ready                               |
|  Dispatcher: one single-use HMAC capability token per step  ------------------------------+                   |
|  Verifier qwen3.8-27b (different model family) + deterministic checks + fresh-VM re-run   |                   |
|  Audit: every event sha256-chained  -> receipt (JSON + Markdown) -> Object Storage        |                   |
|  Cost meter: VM hours x /v2/plans price + tokens x /v1/models price, live per task        |                   |
|  Kill switch: revoke tokens + DELETE /v2/instances/{id} + confirm 404                     |                   |
+-------------------------------------------------------------------------------------------|-------------------+
                                                                                            v
+---------------- throwaway VM #1 (primary) ----------------+   +---------------- throwaway VM #2 (verifier) ---+
| tags: brz-sandbox, task-<id>   TTL watchdog: poweroff @20m |   | same image, same steps, nothing shared        |
| nftables: OUTPUT policy drop; allowlist resolved at boot   |   |                                               |
| runner (stdlib) : /steps /scan /egress /revoke             |   |  -> output hashes must be byte-identical      |
|   each step in gVisor runsc --platform=systrap, uid 1000   |   |                                               |
| secrets present: 0 (scanned and receipted)                 |   |                                               |
+------------------------------------------------------------+   +-----------------------------------------------+
            ... task ends -> DELETE -> GET returns 404 (in the receipt) ...
```

Outer blast radius = one VM, N minutes, a fraction of a cent. Inner blast radius = one gVisor sandbox per
step. Both go to zero when the task ends.

## Vultr services used

| Service | Role |
|---|---|
| **Cloud Compute** | the control plane VM, and one *throwaway* instance per task (plus one per verification), created and deleted through the API |
| **Serverless Inference** (`https://api.vultrinference.com/v1`) | planner `glm-5.3`, independent verifier `qwen3.8-27b` (different model family), both via OpenAI-compatible `chat/completions` with `response_format: json_schema` |
| **Vultr API v2** | `POST/GET/DELETE /v2/instances`, `GET /v2/plans` (live prices), `/v2/firewalls` (inbound-only group for the runner port), `/v2/snapshots` (pre-baked sandbox image) |
| **Object Storage** (S3-compatible) | receipt + audit bundle export with pre-signed links *(event-day wiring)* |
| **Firewall** | inbound: only the control plane reaches the runner port; outbound default-deny is nftables inside the VM |

## 5-minute quickstart

```bash
git clone <repo> ashproof && cd ashproof
python -m venv .venv && . .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
python -m pytest -q                                   # 148 tests, no credentials, no cloud

# Offline demo (mock Vultr + local runner + demo planner): zero credentials
BRZ_MODE=mock uvicorn apps.control_plane.app:app --port 8000
# open http://localhost:8000/ui  -> new task -> live timeline (approval gate, kill switch, VM 404 proof) -> receipt
curl -s localhost:8000/health
curl -s -X POST localhost:8000/tasks -H 'content-type: application/json' -d '{
  "task": "Total the amount column per region and write summary.json",
  "budget_usd": 0.25,
  "files": [{"name": "sales.csv", "content_b64": "cmVnaW9uLGFtb3VudApub3J0aCwxMApzb3V0aCwyMApub3J0aCw1Cg=="}]
}'
curl -s localhost:8000/tasks/<id>            # timeline: plan, VMs, steps, verdict, egress, cost, audit chain
curl -s localhost:8000/tasks/<id>/receipt.md # the receipt, including the GET 404 proof of destruction

# Live on Vultr
export VULTR_API_KEY=...  INFERENCE_API_KEY=...
export VULTR_REGION=ewr VULTR_PLAN=vhp-1c-1gb-amd BRZ_CONTROL_PLANE_CIDR=<control plane ip>/32
uvicorn apps.control_plane.app:app --host 0.0.0.0 --port 8000
```

Environment variables are listed in `apps/control_plane/deps.py`.

## Security model

| Control | What it means here | Where |
|---|---|---|
| **Two blast-radius layers** | outer: one throwaway Vultr VM per task, tagged, TTL watchdog, deleted at the end; inner: each step in gVisor `runsc --platform=systrap` (user-space kernel, no KVM needed), uid 1000, no capabilities, root filesystem is a skeleton with `/usr` read-only (the rest of the machine is not visible), `/work` and a 256 MiB `/tmp` the only writable paths, memory capped without swap, 256 pids, 2 GiB polled quota on `/work` | `brz/sandbox/backends.py`, `sandbox/runner/brz_runner/executor.py`, cloud-init template |
| **Egress default-deny** | steps without `needs_network` have no interface at all. Others go through nftables `OUTPUT policy drop`: only the approved domains' IPv4s (resolved once at boot) on 80/443. Port 53 is closed after boot, because a resolver is a tunnel; approved names are pinned in the step's `/etc/hosts`. Denied packets are logged (`BRZ-EGRESS-DENY`) for the receipt | `brz_runner/egress.py`, `brz_runner/netlog.py` |
| **Zero secrets in the sandbox** | the VM never receives a cloud or inference key; the only secret is a per-task HMAC key that authenticates the control plane to that one runner. Capability tokens are single-use, scoped (`exec`/`scan`/`egress`/`revoke`), expire in 60 s and pin the exact step body; replies carry an HMAC, so the plain-HTTP control link is authenticated both ways. Step env is allow-listed. stdout and stderr are scanned and redacted in the runner before they reach any model prompt; a final scan covers env and the work tree. A dirty scan fails the task | `brz_runner/tokens.py`, `brz_runner/secretscan.py`, `brz_runner/server.py` |
| **Independent verifier** | deterministic checks (exit codes, expected outputs, plan assertions) + the whole plan re-run in a **second clean VM** with byte-identical output hashes required + a review by a *different model family*; the model can only lower a verdict, never rescue a failed check. A repair may change a step's code, never widen it: turning on the network, raising the timeout or dropping expected outputs fails the task | `brz/llm/verifier.py`, `brz/orchestrator.py` |
| **Hash-chained receipts** | every event is `sha256(prev_hash + canonical_json(event))`; the receipt pins the head hash and its own `receipt_sha256`; anyone can re-verify with `python brz/audit/offline_verify.py receipt.json`, which needs nothing but Python. Modified, dropped or reordered events are pinpointed, and the readable fields are checked against the chain. A chain has no key: a forger who recomputes every hash is only caught by a head hash kept elsewhere (`--expect-head`), and the tool says so | `brz/audit/` |
| **Kill switch** | `POST /tasks/{id}/kill`: revoke all runner tokens (kills the running step), `DELETE` every VM, confirm 404, write it all into the chain; works in any state including "awaiting approval" | `Orchestrator.kill` |
| **Cost meter** | per-started-hour VM cost x plan price + tokens x per-model price, per task, live; budget preflight refuses before the first VM; mid-task breaker | `brz/cost/` |
| **Approval gate** | the planner declares the domains it needs; anything outside the pre-approved list parks the task in `awaiting_approval` until a human approves or rejects - no VM exists until then | `Orchestrator._approval_gate` |

Known limitations:

- Egress allow-listing is by IPv4 resolved **once at boot**. A CDN that retires an address mid-task can break
  an approved domain, a wildcard only pins its apex, and other hostnames sharing an approved IP are reachable.
- The secret scan is a tripwire, not data-loss prevention. Encrypted data passes it (attack A24, the one attack
  that still succeeds). The guarantee is that the sandbox holds no secret and has no route out.
- The `/work` quota is polled every 50 ms, so it overshoots: the last run stopped at 2201 MiB against 2048.
- A fork bomb ends the whole step: the sandbox dies with exit 2 at about 100 forks, not with a clean `EAGAIN`.
- The control link is authenticated but not encrypted, so step code and output are readable on the wire. The
  Vultr firewall group limits who is on that path; no secret crosses it.

## Status: what was measured, and what still needs Vultr

Everything below ran on one workstation: WSL2 Ubuntu 24.04, kernel 6.18, runsc release-20261026.0, platform
systrap, 2026-11-04. **Nothing here has run on a Vultr VM yet.** No Vultr API call, no Serverless Inference
call and no VM boot has happened.

| Measured | Result | Evidence |
|---|---|---|
| Attack suite, real runner, real gVisor, real HTTP and tokens | 31 attacks plus a negative control. **First run: 15 attacks worked** (among them reading the runner's HMAC key through a symlink in `/work/out`, writing outside `/work` as root, a 5.3 GiB memory bomb against a 1.4 GiB limit, swapped code under a valid token, a DNS tunnel). **After fixes: 30 of 31 contained, the control passes**; A24 (encrypted data past the scanner) still works and is an accepted limitation | [`report`](docs/evidence/attacks-2026-11-04/report.md), [`first run`](docs/evidence/attacks-2026-11-04/baseline/report.md) |
| Egress ruleset against real packets | the repo's generated nftables ruleset in a network namespace, step in `runsc --network=host`: allowlisted IP on 443 connects, same IP on 8080, another IP, 169.254.169.254 and a tunnelled DNS query all fail and the listeners receive nothing; the runner port answers only the control-plane address | A19, A20 in the report |
| Receipt tamper detection | flip, delete and reorder all detected on a real receipt by the offline verifier run as `python -I -S`; of 23,632 single-byte flips, one went undetected, and it changes no parsed value (last digit of a long float). A full rewrite passes without a pin and fails with one | [`tamper report`](docs/evidence/receipts-2026-11-04/tamper-report.md) |
| Kill switch, in-VM half | `POST /revoke` against 5 processes ignoring SIGTERM, 30 runs: all host processes gone in **p50 9.5 ms, max 10.6 ms**. An earlier batch of 30 gave p50 13.2 ms, max 21.6 ms. Nothing left in any run | [`kill timing`](docs/evidence/kill-timing-2026-11-04/report.md) |
| Task through the real orchestrator | two steps, both sandboxes in gVisor, output hashes identical across the two, status `verified`. Scripted models; sandboxes were runner processes, not VMs | [`receipt`](docs/evidence/receipts-2026-11-04/receipt.md) |
| Prompt injection in step output | a scripted model that obeys everything it reads could not widen a step or pass bad work. This is the worst case by construction; no real model was tested | A29, A30 in the report |
| cloud-init | `cloud-init schema` valid (26.1), ~106 KB rendered. Never booted | re-run 2026-11-04 |
| LLM client | live smoke test against local Ollama `gemma3:4b` on 2026-11-01 (json_schema accepted, valid plan) | `tests/llm/test_live_ollama.py` |
| Test suite | `python -m pytest -q`: 148 tests. On Windows 144 pass, 4 skip (symlinks, root + runsc); in WSL as root 147 pass, 1 skip (no local model server) | CI runs ruff + pytest |

| Tested only against a mock, or not started | State |
|---|---|
| Vultr API v2 client | tested against an in-process mock (shapes from govultr), first live call pending |
| Web UI, control plane API | real code, exercised in mock mode with FakeLLM |
| Cost meter | static price table; live prices need the Vultr pricing source |

| Still needs Vultr | Why it matters |
|---|---|
| A real throwaway VM: create, cloud-init boot, runner ready, `DELETE`, `GET` -> 404 | the outer blast radius and the proof of destruction are not demonstrated yet |
| Serverless Inference with `glm-5.3` and `qwen3.8-27b` | no real planner or verifier run yet; `json_schema` support unconfirmed |
| `BRZ-EGRESS-*` log lines read into a receipt | the ruleset's verdicts are proven by listeners, but its log lines were not observed: netfilter does not log from a non-init namespace by default, and we left that system setting alone |
| Control-plane half of the kill switch | time from button to `GET` 404 |
| Two real VMs producing identical hashes, 20 consecutive tasks, public demo | none of this exists yet |
| Object Storage export, snapshot image, pre-warm pool, Pattern B | not started; see `docs/EVENT-DAY-TODO.md` |

## Repository layout

```
brz/              library: vultr/ (API client + mock) · llm/ (client, structured output, planner, verifier)
                  audit/ (hash chain, receipt) · cost/ (meter, prices) · sandbox/ (cloud-init, runner client, backends)
                  orchestrator.py
sandbox/runner/   brz_runner: the stdlib-only program that runs inside the throwaway VM
apps/control_plane/  FastAPI app + server-rendered UI (ui.py, templates/), dependency wiring (mock | live), demo planner
tests/            148 tests; tests/attacks/ is the attack suite, tests/llm/test_live_ollama.py the optional live smoke test
scripts/          wsl-attacks.sh and wsl-evidence.sh reproduce everything in docs/evidence/
docs/             EVENT-DAY-TODO · VIDEO-SCRIPT · SLIDES-OUTLINE · COMPETITORS · evidence/
```

## Reproduce the evidence

Needs Linux (or WSL) as root, with `runsc` in `/usr/local/bin`.

```bash
scripts/wsl-attacks.sh  docs/evidence/attacks-<date> --baseline docs/evidence/attacks-2026-11-04/baseline/results.json
scripts/wsl-evidence.sh receipt_evidence --out docs/evidence/receipts-<date>
scripts/wsl-evidence.sh kill_timing --out docs/evidence/kill-timing-<date> --runs 30
```

## Docs

- [`docs/COMPETITORS.md`](docs/COMPETITORS.md) - what existing sandboxes do and do not do, feature by feature
- [`docs/VIDEO-SCRIPT.md`](docs/VIDEO-SCRIPT.md) - 3-minute storyboard with the containment moments
- [`docs/SLIDES-OUTLINE.md`](docs/SLIDES-OUTLINE.md) - deck outline: problem, solution, demo, market, pricing, roadmap
- [`docs/EVENT-DAY-TODO.md`](docs/EVENT-DAY-TODO.md) - exactly what happens once real Vultr credentials exist

## License

MIT.
