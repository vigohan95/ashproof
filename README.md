# Ashproof

**The VM burns. The proof stays.** Containment-first agent execution on Vultr. Every task gets its own throwaway Vultr VM, runs with
outbound network denied by default and zero secrets inside, is re-run by an independent verifier in a
second clean VM, leaves a hash-chained, Ed25519-signed receipt - and then the VM is deleted.
`GET /v2/instances/{id}` -> `404` is part of the receipt.

**Who it is for:** the security reviewer who has to approve an AI agent before it works on finance data. The receipt
is the review evidence: what ran, what was refused, and proof that the VM is gone.

> Built for the Vultr "Agent Rush" hackathon (lablab.ai), Challenge 1 *Blast Radius Zero*: a system that
> **plans, dispatches and verifies real executed work** inside a sandbox. MIT licensed.

**Code:** https://github.com/vigohan95/ashproof
**Live demo:** https://66-135-3-140.sslip.io/ (real Vultr VMs and real models; one task at a time, limits on the page).
**A real receipt:** [`rel-01-compromised-agent.receipt.md`](docs/evidence/vultr-2026-11-06/final-run/rel-01-compromised-agent.receipt.md), from the compromised agent.

## Judge in 60 seconds

1. Open the [demo](https://66-135-3-140.sslip.io/). A real recorded task prints on the right in about 15 seconds. It is
   labelled as a recording, and its plan is labelled as a script.
2. Click **Open the receipt**. It opens with what was refused, and your browser checks the chain, the hash, the signature
   and the public log. Click **Change one byte and check again**.
3. Click **Run the compromised agent live** on the home page. Two real VMs, about 2 minutes, one task at a time. If a task
   is already running, the page links to it.
4. [Evidence](https://66-135-3-140.sslip.io/ui/evidence) lists all 31 attacks and the kill switch numbers.

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
|  Sandbox broker: POST /v2/instances (cloud-init) -> wait active -> runner ready, both VMs booting at once     |
|  Dispatcher: one single-use HMAC capability token per step  ------------------------------+                   |
|  Verifier qwen3.8-27b (different model family) + deterministic checks + fresh-VM re-run   |                   |
|  Content filter nemotron-3.5-content-safety reads inputs and step output                  |                   |
|  Audit: every event sha256-chained -> receipt, signed with Ed25519, head in anchors.jsonl |                   |
|  Cost meter: VM hours x /v2/plans price + tokens x /v1/models price, live per task        |                   |
|  Kill switch: revoke tokens + DELETE /v2/instances/{id} + confirm 404                     |                   |
+-------------------------------------------------------------------------------------------|-------------------+
                                                                                            v
+---------------- throwaway VM #1 (primary) ----------------+   +---------------- throwaway VM #2 (verifier) ---+
| tags: brz-sandbox, task-<id>   TTL watchdog: poweroff @20m |   | same image, same steps, nothing shared        |
| nftables: OUTPUT policy drop; allowlist resolved at boot   |   |                                               |
| runner (stdlib) : /steps /scan /egress /revoke             |   |  -> output hashes must be byte-identical      |
|   each step in gVisor runsc --platform=systrap, uid 10001  |   |                                               |
| secrets present: 0 (scanned and receipted)                 |   |                                               |
+------------------------------------------------------------+   +-----------------------------------------------+
            ... task ends -> DELETE -> GET returns 404 (in the receipt) ...
```

Outer blast radius = one VM, N minutes, a fraction of a cent. Inner blast radius = one gVisor sandbox per
step. Both go to zero when the task ends.

## Vultr services used

| Service | Role |
|---|---|
| **Cloud Compute** | the control plane (`vc2-1c-1gb`, about $0.18 a day) and two *throwaway* instances per task (`vhp-1c-1gb-amd`), created and deleted through the API |
| **Serverless Inference** (`https://api.vultrinference.com/v1`) | three models: planner `glm-5.3` and independent verifier `qwen3.8-27b` (a different model family), both through `chat/completions` with `response_format: json_schema` and `reasoning_effort: low`, and content filter `nemotron-3.5-content-safety` on inputs and step output |
| **Vultr API v2** | `POST/GET/DELETE /v2/instances`, `GET /v2/plans` for live VM prices. With an inference key, `GET /v1/models` gives live token prices |
| **Firewall groups** | only the control plane can reach a sandbox's runner port. Vultr groups are inbound only, so outbound default-deny is nftables inside the VM |

## 5-minute quickstart

```bash
git clone https://github.com/vigohan95/ashproof && cd ashproof
python -m venv .venv && . .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
python -m pytest -q                                   # 221 tests, no credentials, no cloud

# Offline demo (mock Vultr + local runner + demo planner): zero credentials
BRZ_MODE=mock uvicorn apps.control_plane.app:app --port 8000
# open http://localhost:8000/  -> new task -> live timeline (approval gate, kill switch, VM 404 proof) -> receipt
# The compromised agent preset is refused here: its attack code only runs on real VMs.
# To sign receipts: python -m brz.audit.signing keygen signing.key, then BRZ_SIGNING_KEY_FILE=signing.key
curl -s localhost:8000/health
curl -s -X POST localhost:8000/tasks -H 'content-type: application/json' -d '{
  "task": "Total the amount column per region and write summary.json",
  "budget_usd": 0.25,
  "files": [{"name": "sales.csv", "content_b64": "cmVnaW9uLGFtb3VudApub3J0aCwxMApzb3V0aCwyMApub3J0aCw1Cg=="}]
}'
curl -s localhost:8000/tasks/<id>            # timeline: plan, VMs, steps, verdict, egress, cost, audit chain
curl -s localhost:8000/tasks/<id>/receipt.md # the receipt, including the GET 404 proof of destruction

# Live on Vultr: run this on a Vultr VM, because the runner port accepts the control plane's address only
export VULTR_API_KEY=...  INFERENCE_API_KEY=...
export VULTR_REGION=ewr VULTR_PLAN=vhp-1c-1gb-amd BRZ_CONTROL_PLANE_CIDR=<control plane ip>/32
export VULTR_FIREWALL_GROUP_ID=<group that allows tcp 8700 from the control plane only>
uvicorn apps.control_plane.app:app --host 127.0.0.1 --port 8000
```

Environment variables are listed in `apps/control_plane/deps.py` and `apps/control_plane/guard.py`.
`scripts/deploy_cp.py` deploys to a VM: systemd service as an unprivileged user, Caddy for HTTPS on `<ip>.sslip.io`, keys
sent over ssh stdin into a 0640 file. The receipt signing key is made on the VM and stays there, outside git. The Vultr API
key's access control list must include the control plane's address.

## Security model

| Control | What it means here | Where |
|---|---|---|
| **Two blast-radius layers** | outer: one throwaway Vultr VM per task, tagged, TTL watchdog, deleted at the end; inner: each step in gVisor `runsc --platform=systrap` (user-space kernel, no KVM needed), uid 10001 with no groups, no capabilities, root filesystem is a skeleton with `/usr` read-only (the rest of the machine is not visible), `/work` and a 256 MiB `/tmp` the only writable paths, memory capped at 60 percent of the VM's RAM with no swap, 256 pids, 2 GiB polled quota on `/work` | `brz/sandbox/backends.py`, `sandbox/runner/brz_runner/executor.py`, cloud-init template |
| **Egress default-deny** | steps without `needs_network` have no interface at all. Others go through nftables `OUTPUT policy drop`: only the approved domains' IPv4s (resolved once at boot) on 80/443. Port 53 is closed after boot, because a resolver is a tunnel; approved names are pinned in the step's `/etc/hosts`. Denied packets are logged (`BRZ-EGRESS-DENY`) for the receipt | `brz_runner/egress.py`, `brz_runner/netlog.py` |
| **Zero secrets in the sandbox** | the VM never receives a cloud or inference key; the only secret is a per-task HMAC key that authenticates the control plane to that one runner. Capability tokens are single-use, scoped (`exec`/`scan`/`egress`/`revoke`), expire in 60 s and pin the exact step body; replies carry an HMAC, so the plain-HTTP control link is authenticated both ways. Step env is allow-listed. stdout and stderr are scanned and redacted in the runner before they reach any model prompt; a final scan covers env and the work tree. A dirty scan fails the task | `brz_runner/tokens.py`, `brz_runner/secretscan.py`, `brz_runner/server.py` |
| **Independent verifier** | deterministic checks (exit codes, expected outputs, plan assertions) + the whole plan re-run in a **second clean VM** with byte-identical output hashes required + a review by a *different model family*, which sees input previews and recomputes what it can; the model can only lower a verdict, never rescue a failed check. A step with a network that had packets refused fails the task, whatever its output, unless the requester (never the plan) said this is a wall test. `nemotron-3.5-content-safety` reads inputs and step output first: unsafe output fails a check, an unsafe input is recorded and told to the verifier model. A repair may change a step's code, never widen it: turning on the network, raising the timeout or dropping expected outputs fails the task | `brz/llm/verifier.py`, `brz/llm/safety.py`, `brz/orchestrator.py` |
| **Hash-chained receipts** | every event is `sha256(prev_hash + canonical_json(event))`; the receipt pins the head hash and its own `receipt_sha256`; anyone can re-verify with `python brz/audit/offline_verify.py receipt.json`, which needs nothing but Python. Modified, dropped or reordered events are pinpointed, and the readable fields are checked against the chain | `brz/audit/` |
| **Signed receipts** | the control plane signs the head and receipt hash with Ed25519. Public key: [`docs/keys/receipt-signing.pub`](docs/keys/receipt-signing.pub), `/pubkey` and inside `offline_verify.py`, which verifies in pure Python so it still needs nothing installed. The receipt page repeats chain, hash, signature and log checks in the browser, and [`/ui/verify`](https://66-135-3-140.sslip.io/ui/verify) checks any receipt file. The private key is a 0640 file on the control plane, outside git, read only by the control plane service; it appears in no receipt, log or response. A signature can be removed from a file, so an unsigned receipt is reported and `--require-signature` fails it | `brz/audit/signing.py`, `brz/audit/offline_verify.py` |
| **Public log** | every signed head is appended to [`/anchors.jsonl`](https://66-135-3-140.sslip.io/anchors.jsonl): each line chains to the one before and is signed. The repository holds an earlier copy, [`anchors-checkpoint.jsonl`](docs/evidence/vultr-2026-11-06/anchors-checkpoint.jsonl); `offline_verify.py --anchors live.jsonl --checkpoint old.jsonl` fails if the live log no longer starts with it | `brz/audit/signing.py` |
| **Compromised agent** | a fixed server-side scenario: a CSV with an injected note and a scripted plan standing in for a hijacked agent. A caller can name the scenario but cannot supply a plan. It passes the same gates as a model's plan, and it is refused outside live mode. Every page, the chain and the receipt mark the plan as a script | `apps/control_plane/scenarios.py` |
| **Kill switch** | `POST /tasks/{id}/kill`: revoke all runner tokens (kills the running step), `DELETE` every VM at once, confirm 404, write it all into the chain; works in any state, including during boot and "awaiting approval" | `Orchestrator.kill` |
| **Cost meter** | per-started-hour VM cost x plan price + tokens x per-model price, per task, from live Vultr prices; budget preflight refuses before the first VM; mid-task breaker | `brz/cost/` |
| **Approval gate** | the planner declares the domains it needs; anything outside the pre-approved list parks the task in `awaiting_approval` until a human approves or rejects - no VM exists until then. A task the planner refuses never gets a VM and is never `verified` | `Orchestrator._approval_gate` |
| **Public demo limits** | on a public URL the human at the gate is a stranger, so domains come from a fixed list, the gate cannot be waived, and tasks are capped per day, per address and in total dollars. Finished tasks survive a restart. An orphan sweep runs every 5 minutes | `apps/control_plane/guard.py`, `archive.py`, `app.py` |

Known limitations:

- **An approved domain opens its whole IP.** Egress is allow-listed by IPv4 resolved once at boot, so other sites on that
  address are reachable. Measured: with only `example.com` approved, a step reached `www.cloudflare.com` on the same
  Cloudflare address and got HTTP 200. A CDN domain is a wide opening. A CDN that retires an address can also break an
  approved domain, and a wildcard only pins its apex.
- **Kill during boot is slow.** Mid-step the kill takes about half a second, but Vultr refuses `DELETE` while a VM installs,
  so during boot it took 20 to 77 seconds.
- **Tasks are slow next to a microVM.** A task usually takes about 2 minutes, nearly all of it VM boot. The slowest verified
  task took 240 seconds. Vultr VMs can also get stuck: one of about 80 stayed `installingbooting` for good. It is deleted
  after 150 seconds and replaced.
- **One task at a time on the demo.** The account limits active instances, and deleted ones seem to count for a short time.
- **The secret scan is a tripwire, not data-loss prevention.** Encrypted data passes it (attack A24, the one attack that still
  succeeds). The guarantee is that the sandbox holds no secret and has no route out, which with an approved domain means
  no route other than that IP.
- **The signing key is on the control plane.** A signature shows which machine issued a receipt, not that the machine was
  uncompromised: a compromised control plane could sign a forgery.
- **The public log is not an outside witness by itself.** The same machine serves it and holds its key, so whoever controls
  that machine can rebuild it from the start. It only catches a rewrite against a copy kept elsewhere, and only for lines
  written before that copy. The copy in this repository proves nothing about timing until the repository is public,
  because until then its history can be changed as well. Nothing in the log says when an entry was really written.
- **Our planner never sees file content, so an injected file cannot hijack it.** That is why the compromised agent's plan is
  a script. It shows what the sandbox does after a hijack, not that a hijack is likely. The injected note does reach the
  verifier model and the content filter, which are real.
- **The content filter is a filter.** `nemotron-3.5-content-safety` answers `safe` or `unsafe`, with no reason. It was right
  on the 12 samples in `safety-probe.json`, which is a small set. The kernel is what stops an attack.
- **Refused packets are counted per step window.** A host process sending during a step with a network would fail the task.
  It has not happened in a real run. Steps without a network are never blamed.
- **The first 4000 bytes of each input go to the verifier model**, so that it can recompute results. The planner sees only
  file names.
- **Boot has an open window.** Packages and gVisor are fetched before lock-down. No step exists yet, and the runner has not
  started. A snapshot image would remove it; that is not built.
- The `/work` quota is polled every 50 ms, so it overshoots: the last run stopped at 2053 MiB against 2048.
- A fork bomb ends the whole step: the sandbox dies at about 75 to 100 forks, not with a clean `EAGAIN`.
- The control link is authenticated but not encrypted, so step code and output are readable on the wire. The Vultr firewall
  group limits who is on that path; no secret crosses it.

## Status: what ran on Vultr

All of this ran on real Vultr VMs in `ewr` on 2026-11-06, with real models. The final run used commit `fd2caaf`; only
evidence, recordings, docs and the evidence page's wording changed after it. Evidence is in
[`docs/evidence/vultr-2026-11-06/`](docs/evidence/vultr-2026-11-06/).

| What ran | Result | Evidence |
|---|---|---|
| Task from the public HTTPS API to receipt | two VMs, step in gVisor, hashes identical across both, verifier recomputed the totals, both VMs 404, offline verifier OK. 114 s, $0.0196 | [`tasks/`](docs/evidence/vultr-2026-11-06/tasks/) |
| Reliability on the final code | **8 of 8 tasks ended as they should**, in a row, through the public URL: 2 compromised agent, 6 normal (CSV, fetch, wall test). Median 123 s, slowest 141 s. Hashes identical across all VM pairs, every VM 404, every receipt signed, in the public log and passed the offline verifier with `--require-signature` | [`final-run.json`](docs/evidence/vultr-2026-11-06/final-run.json) |
| Compromised agent, 2 runs in that series | status `failed`, 20 packets refused by the kernel each time (metadata service, 1.1.1.1:443, 8.8.8.8:53 tcp and udp), 0 allowed. No key found. `nemotron` marked the CSV and the output unsafe. `qwen3.8-27b` was given only the cover story and still reported the injection in its concerns, while saying the totals were right | [`final-run/`](docs/evidence/vultr-2026-11-06/final-run/) |
| Kill switch and planner refusal on the final code | killed mid-step: both VMs 404 in 0.74 s. Theft request: refused in 2.6 s, no VM | `final-run/kill-step.*`, `final-run/refused.*` |
| Signed receipt tamper check | one bit flipped in each of the 35,252 bytes of a real signed receipt, signature required: 0 undetected | [`final-run-tamper.json`](docs/evidence/vultr-2026-11-06/final-run-tamper.json) |
| Browser check | on the live receipt page in a real browser: chain, hash, Ed25519 by WebCrypto and public log all pass, and one changed byte names the broken event. A test runs the same script on real receipts in Node | `tests/app/test_browser_check.py` |
| Content filter | `nemotron-3.5-content-safety` through the inference API: about 0.7 s a call. Injected CSV, attack log, attack code and 2 plain unsafe texts marked unsafe; 7 normal samples marked safe | [`safety-probe.json`](docs/evidence/vultr-2026-11-06/safety-probe.json) |
| An earlier reliability run, before signing and the refused-packet check | 12 of 12 verified: 4 CSV, 4 fetch, 4 walls. Median 122 s, slowest 239 s | [`reliability.json`](docs/evidence/vultr-2026-11-06/reliability.json) |
| A reliability run before that one | stopped at task 5 of 12: one stuck VM and false egress attribution, both fixed. Kept as found | [`reliability-run1/`](docs/evidence/vultr-2026-11-06/reliability-run1/) |
| Boot, API call to ready runner | 77 to 82 s in three direct measurements (37 to 40 s to `active`). 109 KB of `user_data` (145 KB as base64) accepted, no limit reached | `first-vm-*.json` |
| gVisor step | `4.19.0-gvisor`, uid 10001, only `lo` without `needs_network`, root is a skeleton, env has no secrets. runsc release-20261102.0, systrap. `/dev/kvm` absent on `vc2` and `vhp`, which systrap does not need | `first-vm-*.json` |
| Egress in the kernel log | not on the list: no DNS. 1.1.1.1:443, the metadata service and an allowed IP on 8080: `BRZ-EGRESS-DENY`. Allowed name: 200 and `BRZ-EGRESS-ALLOW`. Lines reach the receipt | `first-vm-*.json`, `tasks/walls.*` |
| Attack suite on a real VM | same plan and cloud-init as production: **30 of 31 attacks contained, the negative control passes**. A24 is the accepted limitation | [`attacks-vm/report.md`](docs/evidence/vultr-2026-11-06/attacks-vm/report.md) |
| Memory bomb before and after the fix | before: `global_oom`, host `systemd` and the harness killed. After: `CONSTRAINT_MEMCG`, step stopped at 512 MiB, runner up | `attacks-memory-baseline/run.json`, `attacks-vm/run.json` |
| Kill switch, mid-step, 5 runs | button to both VMs 404: median 0.52 s, max 1.11 s. Tokens revoked in 10 to 14 ms. The running step was killed each time | [`kill-switch.md`](docs/evidence/vultr-2026-11-06/kill-switch.md) |
| Kill switch, during boot, 3 runs | 20 to 77 s, because of Vultr's 409. All VMs 404 | [`kill-switch.md`](docs/evidence/vultr-2026-11-06/kill-switch.md) |
| Task the planner refuses | data theft request: refused in 3.2 s, $0.0011, no VM, status `failed` | `tasks/exfil-refused.*` |
| Serverless Inference | `json_schema` accepted by the planner and the verifier. Alone, `glm-5.3` takes about 4 s and `qwen3.8-27b` about 3 s. Verifier passed good work and rejected wrong numbers, empty output and an injection | `llm-*.json` |
| Orphan sweep | a script of ours was killed before its cleanup and left a tagged VM running. The control plane found it by tag at 25 minutes and deleted it on its own; `GET` returned 404. The control plane VM has a different tag and is not swept | `orphan-sweep.txt` |
| Prices | live from `/v2/plans` and `/v1/models`; each receipt names its price source. The VM rate matches the pending charges (0.008929 per started hour). Receipts before the last commit were metered about 10 percent low | `tasks/final-csv.*` |

Measured earlier on a workstation (WSL2, gVisor release-20261026.0), and not repeated on Vultr:

| What ran | Result | Evidence |
|---|---|---|
| Receipt tamper detection | flip, delete and reorder all detected by the offline verifier run as `python -I -S`; of 23,632 single-byte flips, one went undetected, and it changes no parsed value. A full rewrite passes without a pinned head and fails with one | [`tamper report`](docs/evidence/receipts-2026-11-04/tamper-report.md) |
| Kill switch, in-VM half | 5 processes ignoring SIGTERM, 30 runs: all gone in p50 9.5 ms, max 10.6 ms | [`kill timing`](docs/evidence/kill-timing-2026-11-04/report.md) |
| First attack run, before any fixes | 15 of 31 attacks worked | [`first run`](docs/evidence/attacks-2026-11-04/baseline/report.md) |

Not built: Object Storage export, snapshot image and warm pool, browser tasks, a host-name egress proxy.

## What real VMs found

The workstation runs passed before any of this was seen.

| What happened | How it surfaced | Fix |
|---|---|---|
| Steps ran as uid 1000, which on Vultr's image is `linuxuser`, in `sudo` and `lxd`. A gVisor escape would have landed on a privileged account | `cloud-init status: error` on the first boot, although the task had worked | uid 10001 with no groups; `linuxuser` removed at boot |
| The 1.5 GB memory limit was above the VM's 955 MB of RAM. A memory bomb ran the whole VM out of memory and killed host `systemd` | Attack A10 on a real VM | limit is 60 percent of RAM |
| The account limits active instances. `POST /v2/instances` returned 400 and a task failed | two tasks at once, then a direct test of five parallel creates | client waits for capacity; demo runs one task at a time |
| `DELETE` returns 409 while a VM installs, so a kill during boot lost its first attempt | pressing the kill switch during boot | retried until accepted; VMs are registered the moment they exist |
| A timed-out create was retried, which could make a second billing VM. No duplicate happened; found while reviewing a 71 s create | code review after a real slow call | a create is sent once; after a timeout the VM is looked up by label |
| Quiet steps were charged with host DNS packets from boot, because `journalctl` exits 1 on "no entries" and the reader fell back to the whole log | a CSV task with no network showing 4 denied packets | exit 1 means nothing happened; the fallback keeps the step's time window |
| A VM stayed `installingbooting` for good and the task waited 300 s | reliability run | gives up at 150 s, deletes it, retries once |
| gVisor `latest` had moved since our tests | `runsc --version` on the first boot | pinned to release 20261102.0 |
| The planner refused a data theft task, ran something harmless, and the receipt said `verified` | running that task with real models | a refusal is a field on the plan: no VM, status `failed` |
| The verifier never saw the input files, so it could not catch wrong totals | noticing that our first live test had pasted the data into the task text | it gets input previews and recomputes |
| At default reasoning effort `qwen3.8-27b` spent all 8,000 tokens thinking and returned no JSON | a matrix across three models | `reasoning_effort` is `low` |
| The cost meter read about 10 percent low: `hourly_cost` in `/v2/plans` is rounded on monthly-invoiced plans | comparing the meter with Vultr's pending charges | those plans use `monthly_cost / 672`, which matches the bill |
| The verifier model read the words "scripted attack" in the plan summary, so its concerns proved nothing | reading its review of the first compromised agent run | the plan summary is now the cover story a hijacked agent would give; the label stays on the pages, the chain and the receipt |
| A syntax error from our own edit left the task page dead while the server answered 200 | running the page's script against a real timeline | a test parses every page's inline script |

## Repository layout

```
brz/              library: vultr/ (API client + mock) · llm/ (client, structured output, planner, verifier)
                  audit/ (hash chain, receipt) · cost/ (meter, prices) · sandbox/ (cloud-init, runner client, backends)
                  orchestrator.py
sandbox/runner/   brz_runner: the stdlib-only program that runs inside the throwaway VM
apps/control_plane/  FastAPI app + server-rendered UI, wiring (mock | live), public demo limits, task archive,
                  fixed scenarios, recordings shown on the home page
tests/            221 tests; tests/attacks/ is the attack suite
scripts/          deploy, live runs and evidence: deploy_cp.py, first_vm.py, live_task.py, attack_vm.py, reliability.py
docs/             SUBMISSION · VIDEO-SCRIPT · SLIDES-OUTLINE · COMPETITORS · keys/ · evidence/ · video/
```

## Reproduce the evidence

Workstation, as root in Linux or WSL with `runsc` in `/usr/local/bin`:

```bash
scripts/wsl-attacks.sh  docs/evidence/attacks-<date> --baseline docs/evidence/attacks-2026-11-04/baseline/results.json
scripts/wsl-evidence.sh receipt_evidence --out docs/evidence/receipts-<date>
scripts/wsl-evidence.sh kill_timing --out docs/evidence/kill-timing-<date> --runs 30
```

On Vultr, with `VULTR_API_KEY`, `INFERENCE_API_KEY` and `BRZ_OPERATOR_IP` in `.env`:

```bash
python scripts/first_vm.py <out dir> <firewall group id>            # one VM: boot, step, egress, 404
python scripts/live_task.py <base url> <out dir> <name> "<task>"    # one task through the public API, verified offline
python scripts/attack_vm.py <out dir> <firewall id> <ssh key id> <control plane ssh alias>
python scripts/reliability.py <base url> <out dir> 8                # mixed tasks, including the compromised agent
python scripts/live_task.py <base url> <out dir> attack x --scenario compromised-agent
python scripts/safety_probe.py <out.json>                           # the content filter, with controls
python scripts/tamper_signed.py <receipt.json> <out.json>           # flip one bit in every byte
```

Check a receipt against the live log and the copy in this repository:

```bash
curl -s https://66-135-3-140.sslip.io/anchors.jsonl -o live.jsonl
python brz/audit/offline_verify.py receipt.json --require-signature --anchors live.jsonl \
    --checkpoint docs/evidence/vultr-2026-11-06/anchors-checkpoint.jsonl
```

## Docs

- [`docs/COMPETITORS.md`](docs/COMPETITORS.md) - what existing sandboxes do and do not do, feature by feature
- [`docs/VIDEO-SCRIPT.md`](docs/VIDEO-SCRIPT.md) - the demo video, shot by shot; [`docs/video/`](docs/video/) records and builds it
- [`docs/SLIDES-OUTLINE.md`](docs/SLIDES-OUTLINE.md) - the deck: problem, demo, findings, market, pricing, limits
- [`docs/SUBMISSION.md`](docs/SUBMISSION.md) - lablab form text

## License

MIT.

## How this was built

Honest timeline, and the commit dates in this repository show it. The core library (Vultr client and mock, planner and verifier, receipts, cost table, cloud-init, runner, gVisor executor, UI) was started on 2026-11-01, before the 2026-11-03 kickoff, and tested locally without Vultr. Everything on real Vultr came after the kickoff: first real VM, Serverless Inference, public control plane, attack runs on real VMs, signing, the landing page. Those runs found real defects, listed above.

Written with AI coding assistance (Claude Code). All numbers here come from runs stored under `docs/evidence/`.
