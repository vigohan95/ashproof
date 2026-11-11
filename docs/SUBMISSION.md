# lablab submission text

Every number below comes from a run on Vultr and is linked in the README status table.

## Title (50 characters at most)

Ashproof: one throwaway Vultr VM per agent task

## Short description (255 characters at most)

For the security reviewer who has to approve an AI agent. Each task runs in a throwaway Vultr VM with outbound traffic
denied and no keys inside. A second VM repeats it. Both are deleted, and a signed receipt shows what ran and what was
refused.

## Long description

**Who it is for.** The security reviewer who has to approve an AI agent before it works on finance data. The receipt is the
review evidence: what ran, what was refused, and proof that the VM is gone.

**The problem.** An agent that runs code can leak a key, send data out, or say it finished when it did not. The usual setup
is one long-lived VM with open outbound traffic and an API key in a config file. If something goes wrong, the reviewer has
little evidence of what happened.

**What it does.** You give Ashproof a task and a file. `glm-5.3` on Vultr Serverless Inference writes a plan. The control
plane creates two new Vultr VMs through the API. Each step runs in gVisor on the first VM. The same plan then runs on the
second VM, and every output must match byte for byte. `nemotron-3.5-content-safety` reads the inputs and step output, and
`qwen3.8-27b`, a different model family, recomputes what it can from the input and judges the result. Both VMs are deleted,
and `GET /v2/instances/{id}` returning 404 is written into the receipt.

**Containment.** Outbound traffic is denied by nftables unless a domain was approved, and DNS is closed after boot. The
sandbox holds no cloud or model keys. The control plane sends one signed, single-use token per step. A kill switch revokes
the tokens and deletes both VMs. Denied packets are read from the kernel log into the receipt, and a task that tries to
leave fails even when its output is right.

**The compromised agent.** One click on the demo runs a CSV with an injected note and a plan that stands in for a hijacked
agent. The plan is a fixed script, labelled as one, because our planner never sees file content. Everything after the plan is
real: on two Vultr VMs it finds no keys, and the kernel refuses all 20 packets to the metadata service, 1.1.1.1 and 8.8.8.8.
The receipt lists what was refused, and the task ends failed.

**Evidence.** The receipt is hash-chained and signed with Ed25519. A Python script with no dependencies checks it offline, and
the receipt page repeats the check in the browser, with a button that changes one byte. Each signed head goes into a public
append-only log. The signing key and the log are on the control plane, so a compromised control plane could sign a forgery;
an earlier copy of the log is what exposes that, and the repository holds one. We ran 31 attacks against the sandbox, first
in WSL and then on a real Vultr VM, and report the one that still works. The first boot on Vultr found problems our local
tests could not: the image's uid 1000 belongs to a user in the sudo and lxd groups, the memory limit was higher than the VM's
RAM, and the account has a cap on active instances. Each is fixed and written up in the repository. On the final code, 8 of 8 tasks through the public URL ended as they should: 2 compromised agent, 6 normal (CSV, fetch, wall test), with identical hashes across each pair of VMs and a signed receipt each time.

**Vultr services.** Cloud Compute for the control plane and for every throwaway VM, Serverless Inference for three models,
the v2 API for instances, plans, firewalls and live prices, and firewall groups so that only the control plane can reach a
sandbox.

**Limits.** A task takes about two minutes, nearly all of it VM boot. Allowed domains are pinned by IPv4 at boot, so other
sites on the same address are reachable; we measured this on a Cloudflare address. The secret scanner does not stop encrypted
data (attack A24), which is why the guarantee rests on there being no secret to take and no route out.

**Cost and price.** Each task reports its own cost, about two cents on the current plan, checked against Vultr's pending
charges. Proposed price, not yet tested with customers: self-hosted free under MIT, hosted at $0.25 per task.

## Technology and category tags

Vultr, Vultr Cloud Compute, Vultr Serverless Inference, gVisor, nftables, Ed25519, Python, FastAPI, AI agents, sandboxing, security

## Links

- Demo: https://45-76-6-117.sslip.io/
- GitHub: https://github.com/vigohan95/ashproof
- Video: https://youtu.be/2jKjxSnxIjE
- Slides: `ashproof-slides.pdf`, built from `docs/SLIDES-OUTLINE.md`
- Cover image: `ashproof-cover.png`, 1280x720

## Build note

The core library was started on 2026-11-01, before the 2026-11-03 kickoff, and tested locally. All Vultr integration, real runs, signing and the landing page came after kickoff. Commit dates are public. Built with AI coding assistance.
