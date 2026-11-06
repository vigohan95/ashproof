# Other sandboxes and how Ashproof compares

Sources: research on 2026-10-30 (the Vultr tutorial and each project's README and docs). Ashproof's column was
rechecked on 2026-11-06 against real runs on Vultr; the other columns were not rechecked.

Legend: Y = present and documented, P = partial / possible with extra work, N = absent, ? = unverified.

| Capability | **Ashproof** | Vultr tutorial (microsandbox on VX1) | microsandbox | OpenSandbox (Alibaba) | E2B | Daytona | OpenHands Docker runtime | k8s agent-sandbox | browser-use |
|---|---|---|---|---|---|---|---|---|---|
| 1. Throwaway VM **per task**, deleted at the end (outer blast radius) | **Y** - `POST`/`DELETE /v2/instances`, 404 in receipt | N - one long-lived VX1 | N - sandboxes inside one host | N - containers/pods on shared nodes | P - microVM per sandbox, hosted; self-host AWS/GCP/Azure only | P - managed; archived | N - container per session, shared kernel | P - pod per sandbox | N - runs in agent process |
| 2. Second isolation layer **inside** the VM (gVisor / microVM per step) | **Y** - runsc systrap per step | Y - libkrun microVM (needs KVM) | Y - libkrun (needs KVM) | P - gVisor/Firecracker on K8s only | Y - Firecracker | ? | N | Y - gVisor/Kata runtimeClass | N |
| 3. Egress **default-deny** + domain allowlist declared by the planner and approved by a human | **Y** - nftables + approval gate | N - all egress open | P - host allowlist, no approval flow | P - per-sandbox egress policy | P - internet toggle | P - network limits | N | P - NetworkPolicy by hand | N |
| 4. **Zero secrets in the sandbox** + single-use scoped capability tokens + end-of-task secret scan in the receipt | **Y** | N - API key in opencode.json | N | P - Credential Vault (secrets *are* delivered) | N | N | N - env passthrough | N | P - placeholders for sensitive data |
| 5. **Independent verification**: deterministic checks + re-run in a second clean VM + different model family | **Y** | N | N | N | N | N | N | N | N |
| 6. **Hash-chained audit log + Ed25519-signed receipt** (JSON + Markdown, checked offline or in the browser) | **Y** | N | N | N | N | P - audit log, not chained | N | N | N |
| 7. **Kill switch** (revoke tokens + destroy VM + record) and TTL watchdog | **Y** | N | P - stop sandbox | P - delete sandbox | P - kill sandbox | P | P - stop container | P - delete pod | N |
| 8. **Live cost meter per task** (VM hours x plan price + tokens x model price) and budget breaker | **Y** | N | N | N | N | N | N | N | N |
| Product surface | web UI + API + receipts | tutorial | SDK/CLI/MCP | platform | SaaS + SDK | SaaS | IDE/agent | CRD | library |
| Maturity (stars at research time) | new | - | 8.9k | 16.3k | 14.6k | 71k (archived) | - | pre-production | 119.6k |

## Other projects at this event

We read 73 repositories from this event on 2026-11-06. In those 73, none creates and deletes a Vultr VM per task in its
running service. gVisor, receipts, human approval and sandboxes with no keys inside are common there, so we do not list
them as differences. Some entries run a microVM per task on a long-lived host, which gives each task its own kernel and
starts faster than a cloud VM. The difference that remains is a separate cloud VM against a microVM on a shared host.

## What others do better

* microsandbox, E2B and other Firecracker-based systems start in under a second. Our outer VM takes about 80 seconds from
  the API call to a ready runner (measured on Vultr, no snapshot). The inner gVisor layer starts in under a second.
* OpenSandbox has far more runtimes (desktop, browser, several languages). Ashproof covers Python and shell today.
* browser-use is the better browser agent. Ashproof could wrap it in the sandbox rather than replace it.
* One VM per task costs more than a container: about $0.018 of VM time per task, because Vultr bills the started hour.
