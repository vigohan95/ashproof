# Slide deck outline (PDF, 10 slides, 16:9)

Judging rubric mapping in brackets: [A] Application of Technology, [P] Presentation, [B] Business Value,
[O] Originality. The lablab rubric gives Presentation 5/5 only with a competitive analysis and Business
Value 4-5 only with market + revenue model, so slides 7-9 are not optional.

1. **Title** - Blast Radius Zero. One line: *Every AI task in its own throwaway Vultr VM: executed,
   verified, receipted, destroyed.* Three numbers: 1 VM per task · 0 secrets inside · $0.0x per task.
   Repo + demo URL. [P]

2. **The problem** - Agents that run real code/browse real sites are the biggest new attack surface
   (prompt injection -> exfiltration, lateral movement, destroyed environments). OWASP Agentic Top 10
   ASI05 lists sandboxing as a required control. Today's default (one VM, open egress, keys in a config
   file, "the model says it's done") is what every tutorial ships. [B]

3. **What we built** - the 60-second architecture diagram from the README. Two blast-radius layers,
   default-deny egress, zero secrets, independent verifier, hash-chained receipt, kill switch, cost
   meter, approval gate. [A][O]

4. **Vultr, specifically** - table: Cloud Compute (control plane + throwaway instances), Serverless
   Inference (`glm-5.3` planner, `qwen3.8-27b` verifier, `json_schema`), API v2 (`instances`, `plans`,
   `firewalls`, `snapshots`), Object Storage (receipt export), Firewall (inbound-only). Screenshot of the
   console instance list mid-task. [A]

5. **Demo 1 - a CSV task, start to receipt** - four screenshots: plan with required domains ->
   instance active -> results -> receipt with `GET /v2/instances/{id} -> 404`. [A]

6. **Demo 2 - the containment moments** - injected file tries to call out: *EGRESS DENIED*; secret scan:
   *0 findings*; re-run hashes identical in a second VM; kill switch -> instance gone in 3 s. Each with
   the matching line from the audit chain. [O][A]

7. **Competitive analysis** - the table from `docs/COMPETITORS.md` (8 differentiators as rows; BRZ vs
   Vultr tutorial, microsandbox, OpenSandbox, E2B, OpenHands, k8s agent-sandbox, browser-use). Honest
   row: boot time (they win) and runtime breadth (OpenSandbox wins). [P][O]

8. **Market and buyer** - who pays: platform/security teams at companies rolling out coding and data
   agents; finance/ops teams that need evidence for auditors. Pain: cannot let agents touch production
   data without a containment story; need per-task cost. Size pointers: agent-platform spend + the
   compliance budget that already pays for audit trails. (Numbers to be filled with cited sources on D5;
   no invented TAM.) [B]

9. **Pricing and unit economics** - "trusted execution" priced per task: our cost meter already shows
   the floor (one `vhp-1c-1gb-amd` started hour ≈ $0.009 + ~$0.002 tokens per verified task on Vultr).
   Price tiers: free (self-hosted, MIT) / team ($ per verified task with hosted control plane) /
   enterprise (private Vultr account, SSO, retention). Gross margin illustration from the meter. [B]

10. **Roadmap and ask** - Next 90 days: snapshot image + warm pool (sub-minute start), DNS-aware egress
    sets, Pattern B (Playwright + vision verifier + human approval of irreversible actions), Object
    Storage retention policies, Web UI, Vultr Marketplace listing. Ask: pilot teams. Links. [B][P]

## Appendix slides (only if asked)

* A1 - Threat model table: attacker inside the step (prompt-injected code) vs. attacker with the runner
  token vs. compromised control plane; what each layer stops.
* A2 - Receipt anatomy with the hash-chain verification algorithm.
* A3 - Test and CI evidence: 90 offline tests, live smoke tests, CI badge.

## Design notes

* One idea per slide, screenshots over bullet lists, the receipt is the hero image.
* Use the exact rubric words in slide titles where natural ("Application", "Business value").
* Export PDF; file name `blast-radius-zero-deck.pdf`; check every link in the PDF opens.
