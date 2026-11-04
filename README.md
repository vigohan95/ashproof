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
python -m pytest -q                                   # 94 offline tests, no credentials, no network

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
| **Two blast-radius layers** | outer: one throwaway Vultr VM per task, tagged, TTL watchdog, deleted at the end; inner: each step in gVisor `runsc --platform=systrap` (user-space kernel, no KVM needed), uid 1000, host root read-only, `/work` the only writable path | `brz/sandbox/backends.py`, `sandbox/runner/brz_runner/executor.py`, cloud-init template |
| **Egress default-deny** | nftables `OUTPUT policy drop`; only one fixed DNS resolver and the approved domains' IPv4s (resolved at boot) on 80/443; every denied packet is logged (`BRZ-EGRESS-DENY`) and lands in the receipt | `brz_runner/egress.py`, `brz_runner/netlog.py` |
| **Zero secrets in the sandbox** | the VM never receives a cloud or inference key; the only secret is a per-task HMAC key that authenticates the control plane to that one runner. Capability tokens are single-use, scoped (`exec`/`scan`/`egress`/`revoke`), step-bound and expire in 60 s. Step env is allow-listed. A secret scan (key-format regexes + env names) runs at the end and its result is in the receipt | `brz_runner/tokens.py`, `brz_runner/secretscan.py`, `brz_runner/server.py` |
| **Independent verifier** | deterministic checks (exit codes, expected outputs, plan assertions) + the whole plan re-run in a **second clean VM** with byte-identical output hashes required + a review by a *different model family*; the model can only lower a verdict, never rescue a failed check | `brz/llm/verifier.py`, `brz/orchestrator.py` |
| **Hash-chained receipts** | every event is `sha256(prev_hash + canonical_json(event))`; the receipt pins the head hash and its own `receipt_sha256`; anyone can re-verify offline, and modified / dropped / reordered events are pinpointed | `brz/audit/` |
| **Kill switch** | `POST /tasks/{id}/kill`: revoke all runner tokens (kills the running step), `DELETE` every VM, confirm 404, write it all into the chain; works in any state including "awaiting approval" | `Orchestrator.kill` |
| **Cost meter** | per-started-hour VM cost x plan price + tokens x per-model price, per task, live; budget preflight refuses before the first VM; mid-task breaker | `brz/cost/` |
| **Approval gate** | the planner declares the domains it needs; anything outside the pre-approved list parks the task in `awaiting_approval` until a human approves or rejects - no VM exists until then | `Orchestrator._approval_gate` |

Known limitation (by design, documented): egress allow-listing is by IPv4 resolved **once at boot**
through the fixed resolver. A CDN that rotates addresses mid-task can break an approved domain, and other
hostnames sharing an approved IP are reachable. The roadmap item is DNS-aware dynamic sets.

## Status: what is real today vs. what is mocked

| Component | Status | Evidence |
|---|---|---|
| Vultr API v2 client (instances, plans, regions, os, firewall, tags, cloud-init, retries, 404 proof, orphan sweep) | **real code, tested against an in-process mock of the API** (shapes from govultr); first live call on event day | `tests/vultr` (12 tests) |
| Mock Vultr API | real (FastAPI), lifecycle `pending -> active -> 404`, fault injection, call log | `brz/vultr/mock.py` |
| OpenAI-compatible LLM client + `json_schema` structured output with plain-JSON fallback and repair round | **real**; live smoke test passed against local Ollama `gemma3:4b` (json_schema accepted, valid plan, 802 tokens, 48.6 s) | `tests/llm` (16 tests + 1 live) |
| Planner / Verifier logic | real; prompts will be tuned on event day against `glm-5.3` / `qwen3.8-27b` | `tests/llm/test_planner_verifier.py` |
| Hash-chained audit log + self-verifying receipt (JSON + Markdown) | **real**, tamper tests | `tests/audit` (12 tests) |
| Cost meter | real; prices from a static table (RESEARCH 2026-10-30); `LivePriceTable.from_payloads` ready for `/v2/plans` + `/v1/models` | `tests/cost` (6 tests) |
| In-VM runner (HTTP, tokens, executor, secret scan, egress log) | **real**, exercised over real HTTP in tests with a subprocess executor | `tests/sandbox/test_runner.py` |
| gVisor executor (`runsc --platform=systrap`, OCI bundle) | **real, exercised in WSL2 Ubuntu 24.04 (2026-11-01)**: runsc release-20261026.0 ran the repo-generated bundle; Python step as uid 1000 inside kernel `4.19.0-gvisor` in 0.12 s, outputs collected, root read-only, two re-runs byte-identical, timeout -> 124, `needs_network` step reached https://example.com (HTTP 200) while no-network steps have no interface. Not yet run on a Vultr VM | `tests/sandbox/test_runner.py`, `docs/EVENT-DAY-TODO.md` (WSL log) |
| cloud-init template (nftables default-deny, fixed DNS, TTL timer, runner service, embedded runner) | renders valid YAML; **`cloud-init schema --config-file` valid (cloud-init 26.1), yamllint clean, `nft -c -f` accepts the generated ruleset (nftables 1.0.9)** - all in WSL; **not yet booted on a real VM** - event day D1 | `tests/sandbox/test_cloudinit.py`, `tests/sandbox/test_netlog_egress.py` |
| In-VM runner under gVisor, driven by signed tokens | **real in WSL**: `/health`, `/steps` (gVisor), replay rejected, `/scan` clean, `/revoke`; `journalctl -k` egress reader untested until a VM exists | WSL log in `docs/EVENT-DAY-TODO.md` |
| Orchestrator + control plane API (plan, approval gate, budget breaker, steps + repair, fresh-VM re-run, verify, scan, destroy, receipt, kill switch) | **real**, full flow end-to-end against mock Vultr + local runner + FakeLLM | `tests/app` (14 tests) |
| Web UI (`/ui`: task list, new-task form, live timeline with approval gate / kill switch / VM lifecycle with 404 proof / egress / scan / cost, receipt page with chain verification) | **real**, server-rendered (Jinja2 + vanilla JS, no build step); works in mock mode without credentials | `tests/app/test_ui.py` |
| Object Storage export, snapshot base image, pre-warm pool, Pattern B (Playwright + vision verify) | not started; see `docs/EVENT-DAY-TODO.md` | - |

Test suite: `python -m pytest -q` -> **94 passed, 1 skipped** (the live LLM smoke test skips when no local
OpenAI-compatible server answers). CI runs ruff + pytest on every push (`.github/workflows/ci.yml`).

## Repository layout

```
brz/              library: vultr/ (API client + mock) · llm/ (client, structured output, planner, verifier)
                  audit/ (hash chain, receipt) · cost/ (meter, prices) · sandbox/ (cloud-init, runner client, backends)
                  orchestrator.py
sandbox/runner/   brz_runner: the stdlib-only program that runs inside the throwaway VM
apps/control_plane/  FastAPI app + server-rendered UI (ui.py, templates/), dependency wiring (mock | live), demo planner
tests/            94 offline tests; tests/llm/test_live_ollama.py is the optional live smoke test
docs/             EVENT-DAY-TODO · VIDEO-SCRIPT · SLIDES-OUTLINE · COMPETITORS
```

## Docs

- [`docs/COMPETITORS.md`](docs/COMPETITORS.md) - what existing sandboxes do and do not do, feature by feature
- [`docs/VIDEO-SCRIPT.md`](docs/VIDEO-SCRIPT.md) - 3-minute storyboard with the containment moments
- [`docs/SLIDES-OUTLINE.md`](docs/SLIDES-OUTLINE.md) - deck outline: problem, solution, demo, market, pricing, roadmap
- [`docs/EVENT-DAY-TODO.md`](docs/EVENT-DAY-TODO.md) - exactly what happens once real Vultr credentials exist

## License

MIT.
