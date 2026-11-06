# lablab submission text

Every number below comes from a run on Vultr and is linked in the README status table. Fill the two blanks after the
repository and the video exist.

## Title (50 characters at most)

Ashproof: one throwaway Vultr VM per agent task

## Short description (255 characters at most)

An agent runs real code in a throwaway Vultr VM with outbound traffic denied and no keys inside. A second clean VM
repeats the work. The VMs are deleted, and a receipt anyone can check offline records what happened.

## Long description

**The problem.** An agent that runs code can leak a key, send data out, or say it finished when it did not. The usual
setup is one long-lived VM with open outbound traffic and an API key in a config file. If something goes wrong, there is
little evidence of what happened.

**What it does.** You give Ashproof a task and a file. `glm-5.3` on Vultr Serverless Inference writes a plan. The control
plane creates two new Vultr VMs through the API. Each step runs in gVisor on the first VM. The same plan then runs on the
second VM, and every output must match byte for byte. `qwen3.8-27b`, a different model family, recomputes what it can from
the input and judges the result. Both VMs are deleted, and `GET /v2/instances/{id}` returning 404 is written into the
receipt.

**Containment.** Outbound traffic is denied by nftables unless a domain was approved, and DNS is closed after boot. The
sandbox holds no cloud or model keys. The control plane sends one signed, single-use token per step. A kill switch revokes
the tokens and deletes both VMs. Denied packets are read from the kernel log into the receipt.

**Evidence.** The receipt is hash-chained, and a Python script with no dependencies checks it offline. We ran 31 attacks
against the sandbox, first in WSL and then on a real Vultr VM, and report the ones that got through. The first boot on
Vultr found problems our local tests could not: the image's uid 1000 belongs to a user in the sudo and lxd groups, the
memory limit was higher than the VM's RAM, and the account has a cap on active instances. Each is fixed and written up in
the repository.

**Vultr services.** Cloud Compute for the control plane and for every throwaway VM, Serverless Inference for both models
with `response_format: json_schema`, the v2 API for instances, plans, firewalls and live prices, and firewall groups so
that only the control plane can reach a sandbox.

**Limits.** A task takes about two minutes, nearly all of it VM boot. Allowed domains are pinned by IPv4 at boot, so other
sites on the same address are reachable. The secret scanner does not stop encrypted data, which is why the guarantee rests
on there being no secret to take and no route out.

**Who it is for.** Teams that want agents to work on real data and need evidence for security or audit reviews. Each task
reports its own cost, about two cents on the current plan.

## Technology and category tags

Vultr, Vultr Cloud Compute, Vultr Serverless Inference, gVisor, nftables, Python, FastAPI, AI agents, sandboxing, security

## Links

- Demo: https://66-135-3-140.sslip.io/
- GitHub: TO FILL once the repository is public
- Video: TO FILL (YouTube unlisted, 5 minutes at most)
- Slides: `ashproof-deck.pdf`, built from `docs/SLIDES-OUTLINE.md`
