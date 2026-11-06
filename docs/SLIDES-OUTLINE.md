# Slide outline (PDF, 10 slides, 16:9)

Rubric in brackets: [A] Application of Technology, [P] Presentation, [B] Business Value, [O] Originality. The lablab
rubric gives top marks in Presentation only with a competitive analysis, and in Business Value only with a market and a
revenue model, so slides 7 to 9 are required. Every number comes from the README status table.

1. **Title.** Ashproof. *One throwaway Vultr VM per agent task, checked on a second VM, with a receipt that outlives both.*
   Three numbers: 1 VM per task, 0 keys inside, about 2 cents per task. Repo and demo URL. [P]

2. **The problem.** An agent that runs code can leak a key, send data out, or claim work it did not do. The common setup is
   one long-lived VM, open outbound traffic, a key in a config file, and the model's word that it finished. OWASP's Agentic
   Top 10 (ASI05) lists sandboxing as a control. [B]

3. **What we built.** The architecture diagram from the README: planner, approval gate, two VMs, gVisor per step, nftables
   default deny, single-use tokens, verifier, receipt, kill switch. [A][O]

4. **Vultr, specifically.** Cloud Compute: control plane plus two throwaway VMs per task. Serverless Inference: `glm-5.3`
   plans, `qwen3.8-27b` verifies, both with `json_schema`. v2 API: instances, plans, firewalls. Live prices from `/v2/plans`
   and `/v1/models`. Screenshot of the console during a task. [A]

5. **Demo: a task from start to receipt.** Four screenshots: plan, two VMs active, verdict with the recomputed totals,
   receipt with 404. Measured: 110 seconds, $0.018. [A]

6. **Containment on real VMs.** Denied packets to 1.1.1.1 and to the metadata service, from the kernel log. Output hashes
   identical across two VMs. Kill switch time from `kill-switch.md`. Attack suite result on a real VM. [O][A]

7. **What real VMs found.** The strongest slide for credibility. A table with four rows: uid 1000 was a sudo and lxd user;
   memory limit above RAM; account cap on active instances; DELETE refused during install. Each row: how we found it, the
   fix. None of these showed up in local tests. [A][O]

8. **Competitive analysis.** The table from `docs/COMPETITORS.md`. Include the rows where others win: boot time
   (sub-second microVMs against our 80 seconds) and runtime breadth (OpenSandbox). [P][O]

9. **Market, pricing, unit cost.** Buyer: platform and security teams rolling out agents, who need evidence for audits. Our
   measured floor per verified task is $0.018 on Vultr: $0.016 for two VM hours and $0.002 for tokens. VM time is billed by
   the started hour, so reusing an hour across tasks is the first margin lever. Tiers: self-hosted (MIT), hosted per
   verified task, private deployment. Market size only with cited sources; no invented figures. [B]

10. **Limits and next steps.** Limits, stated plainly: 2 minutes per task, IPv4 pinning at boot, encrypted data passes the
    scanner, control link not encrypted. Next: snapshot image and warm pool, browser tasks with a vision check, receipts in
    Object Storage, signed receipts. Ask: pilot teams. Links. [B][P]

## Appendix (only if asked)

- A1: threat model: attacker inside a step, attacker with a token, compromised control plane; what each layer stops.
- A2: how the hash chain works and what it does not prove without a pinned head hash.
- A3: test suite and evidence folder listing.

## Design notes

- One idea per slide, screenshots over bullets, and the receipt is the main image.
- Export as `ashproof-deck.pdf` and check that every link opens.
