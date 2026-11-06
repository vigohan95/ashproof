# Slide outline (PDF, 10 slides, 16:9)

Rubric in brackets: [A] Application of Technology, [P] Presentation, [B] Business Value, [O] Originality. The lablab
rubric gives top marks in Presentation only with a competitive analysis, and in Business Value only with a market and a
revenue model, so slides 7 to 9 are required. Every number comes from the README status table.

1. **Title.** Ashproof. *One throwaway Vultr VM per agent task, checked on a second VM, with a signed receipt that outlives
   both.* Three numbers: 2 throwaway VMs per task, 0 keys inside, about 2 cents per task. Repo and demo URL. [P]

2. **The problem, for one person.** A security reviewer is asked to approve an AI agent that will work on finance data. The
   agent can leak a key, send the file out, or claim work it did not do. The usual setup gives the reviewer one long-lived
   VM, open outbound traffic, a key in a config file, and the model's word that it finished. OWASP's Agentic Top 10 (ASI05)
   lists sandboxing as a control. [B]

3. **What we built.** The architecture diagram from the README: planner, approval gate, two VMs, gVisor per step, nftables
   default deny, single-use tokens, three models, signed receipt, public log, kill switch. [A][O]

4. **Vultr, specifically.** Cloud Compute: control plane plus two throwaway VMs per task. Serverless Inference, three
   models: `glm-5.3` plans, `qwen3.8-27b` verifies, `nemotron-3.5-content-safety` reads inputs and step output. v2 API:
   instances, plans, firewalls. Live prices from `/v2/plans` and `/v1/models`. Screenshots of the task page: the two instances with their 404s, and the cost lines. [A]

5. **Demo: a task from start to receipt.** Four screenshots: plan, two VMs active, verdict with the recomputed totals,
   receipt summary. Measured: about 2 minutes, $0.02. Then: 8 of 8 tasks ended as they should on the final code. [A]

6. **The compromised agent.** A CSV carries an injected note. A scripted plan stands in for a hijacked agent, and the slide
   says so. On real VMs it finds no keys, and the kernel refuses all 20 packets to the metadata service, 1.1.1.1 and 8.8.8.8.
   The totals are right and the task still fails, because it tried to leave. Screenshot: "What was refused" on the receipt.
   Beside it: attack suite on a real VM and the kill switch time. [O][A]

7. **What real VMs found.** The strongest slide for credibility. A table with four rows: uid 1000 was a sudo and lxd user;
   memory limit above RAM; account cap on active instances; quiet steps blamed for boot traffic. Each row: how we found it, the
   fix. None of these showed up in local tests. [A][O]

8. **Competitive analysis.** The table from `docs/COMPETITORS.md`. Include the rows where others win: boot time
   (sub-second microVMs against our 80 seconds) and runtime breadth (OpenSandbox). Add the sentence about the 73 repositories
   from that page, without naming any entry. [P][O]

9. **Market, pricing, unit cost.** Buyer: the security reviewer who has to approve an AI agent before it works on finance
   data; the budget sits with their security or platform team. Our measured floor per task is about $0.02 on Vultr: $0.018
   for two started VM hours and about $0.001 to $0.002 for tokens across three models. VM time is billed by the started hour, so
   reusing an hour across tasks is the first margin lever. Proposed, not tested with customers: self-hosted free (MIT), hosted
   at $0.25 per task, private deployment on the customer's Vultr account for a yearly fee. No market size figure: we have no
   cited source for one. [B]

10. **Limits and next steps.** Limits, stated plainly: 2 minutes per task; egress rules work on IPv4, so an approved domain
    opens its whole IP; encrypted data passes the scanner (A24); the control link is not encrypted; the signing key and the
    public log sit on the control plane. Next: snapshot image and warm pool, browser tasks with a vision check, the log's head
    published somewhere the control plane cannot write. Ask: pilot reviewers. Links. [B][P]

## Appendix (only if asked)

- A1: threat model: attacker inside a step, attacker with a token, compromised control plane; what each layer stops.
- A2: what a signature and the public log prove, and what they do not without a copy kept elsewhere.
- A3: test suite and evidence folder listing.

## Design notes

- One idea per slide, screenshots over bullets, and the receipt is the main image.
- Export as `ashproof-slides.pdf` and check that every link opens.
