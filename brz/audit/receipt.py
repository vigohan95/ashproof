"""Receipt: the forensic artefact a task leaves behind after its VM is gone.

Everything a compliance reviewer needs in one document: what was asked, what was planned,
what ran (hashes), what an independent verifier concluded, which VM it ran in and the
HTTP 404 that proves the VM no longer exists, every egress attempt, the secret-hygiene
scan, the cost, and the full hash chain of audit events with its verification result.

``receipt_sha256`` is the hash of the canonical JSON of everything else, so the receipt
itself is tamper-evident; the audit chain inside it is verified again at render time.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from .chain import AuditEvent, AuditLog, ChainVerification, canonical_json, sha256_hex, verify_chain


class StepReceipt(BaseModel):
    step_id: str
    title: str
    kind: str
    code_sha256: str
    exit_code: int
    duration_s: float
    stdout_sha256: str
    stderr_sha256: str
    output_files: dict[str, str] = Field(default_factory=dict)  # name -> sha256
    attempts: int = 1
    repaired: bool = False
    executor: str = ""  # "gvisor-systrap" | "subprocess" ...


class SandboxReceipt(BaseModel):
    role: str  # "primary" | "verifier"
    provider: str  # "vultr" | "mock-vultr" | "local"
    instance_id: str
    plan: str = ""
    region: str = ""
    created_at: datetime | None = None
    active_at: datetime | None = None
    destroyed_at: datetime | None = None
    proof_of_destruction: dict[str, Any] | None = None  # {method, http_status, observed_at, attempts}
    inner_isolation: str = ""  # "gvisor runsc --platform=systrap" | "none (local test)"
    egress_policy: str = "default-deny"
    ttl_minutes: int | None = None

    @property
    def destroyed(self) -> bool:
        return bool(self.proof_of_destruction and self.proof_of_destruction.get("http_status") == 404)


class EgressAttempt(BaseModel):
    ts: str
    dst_ip: str
    dst_port: int | None = None
    proto: str = ""
    verdict: str  # "denied" | "allowed"
    domain: str | None = None
    raw: str = ""


class EgressSummary(BaseModel):
    allowed_domains: list[str] = Field(default_factory=list)
    attempts: list[EgressAttempt] = Field(default_factory=list)

    @property
    def denied_count(self) -> int:
        return sum(1 for a in self.attempts if a.verdict == "denied")

    @property
    def allowed_count(self) -> int:
        return sum(1 for a in self.attempts if a.verdict == "allowed")


class SecretScanSummary(BaseModel):
    clean: bool
    findings_count: int = 0
    findings: list[dict[str, Any]] = Field(default_factory=list)  # redacted
    files_scanned: int = 0
    env_vars_checked: int = 0
    scanner: str = "brz_runner.secretscan"


class CostSummary(BaseModel):
    total_usd: float
    vm_usd: float = 0.0
    tokens_usd: float = 0.0
    lines: list[dict[str, Any]] = Field(default_factory=list)
    budget_usd: float | None = None

    @property
    def within_budget(self) -> bool:
        return self.budget_usd is None or self.total_usd <= self.budget_usd


class Receipt(BaseModel):
    receipt_version: str = "1"
    task_id: str
    created_at: datetime
    status: str  # "verified" | "failed" | "killed" | "unverified"
    task_text_sha256: str
    task_text: str
    input_files: dict[str, str] = Field(default_factory=dict)  # name -> sha256
    plan: dict[str, Any]
    planner_model: str = ""
    steps: list[StepReceipt]
    verifier: dict[str, Any]
    sandboxes: list[SandboxReceipt]
    egress: EgressSummary
    secret_scan: SecretScanSummary | None
    cost: CostSummary
    audit_events: list[AuditEvent]
    audit_head_hash: str
    audit_chain: ChainVerification
    receipt_sha256: str = ""
    signature: dict[str, Any] | None = None  # Ed25519 over the head; outside receipt_sha256, which it covers

    # ----------------------------------------------------------------- build
    def finalize(self) -> Receipt:
        body = self.model_dump(mode="json", exclude={"receipt_sha256", "signature"})
        self.receipt_sha256 = sha256_hex(canonical_json(body))
        return self

    def verify(self) -> tuple[bool, list[str]]:
        """Recompute everything verifiable offline: receipt hash + audit chain + head hash."""
        problems: list[str] = []
        body = self.model_dump(mode="json", exclude={"receipt_sha256", "signature"})
        if sha256_hex(canonical_json(body)) != self.receipt_sha256:
            problems.append("receipt_sha256 mismatch (receipt modified)")
        chain = verify_chain(self.audit_events)
        if not chain.ok:
            problems.append(f"audit chain broken at seq {chain.broken_at}: {chain.reason}")
        elif chain.head_hash != self.audit_head_hash:
            problems.append("audit_head_hash does not match the events")
        return (not problems), problems

    def refusals(self) -> list[dict[str, Any]]:
        """What was stopped, read from the chain and the kernel's lines. One row per kind of thing."""
        rows: list[dict[str, Any]] = []
        for e in self.audit_events:
            if e.kind == "plan.refused":
                rows.append({"what": e.data.get("reason", ""), "by": "planner, no VM created", "count": 1})
            elif e.kind == "approval.rejected":
                rows.append(
                    {"what": f"egress to {e.data.get('domains')}", "by": "human at the approval gate", "count": 1}
                )
            elif e.kind == "step.repair_rejected":
                rows.append({"what": f"repair of {e.data.get('step_id')}", "by": "repair rules", "count": 1})
        seen: dict[tuple, dict[str, Any]] = {}
        for a in self.egress.attempts:
            if a.verdict != "denied":
                continue
            key = (a.proto, a.dst_ip, a.dst_port)
            row = seen.setdefault(
                key, {"what": f"{a.proto} to {a.dst_ip}:{a.dst_port or ''}", "by": "kernel (nftables)", "count": 0}
            )
            row["count"] += 1
        return rows + list(seen.values())

    @property
    def all_vms_destroyed(self) -> bool:
        return all(s.destroyed for s in self.sandboxes if s.provider != "local")

    # ---------------------------------------------------------------- render
    def to_json(self) -> str:
        return self.model_dump_json(indent=2)

    def to_markdown(self) -> str:
        ok, problems = self.verify()
        lines: list[str] = []
        lines.append(f"# Ashproof receipt `{self.task_id}`")
        lines.append("")
        lines.append(f"- **Status:** {self.status.upper()}")
        lines.append(f"- **Created:** {self.created_at.isoformat()}")
        lines.append(f"- **Task:** {self.task_text[:200]}{'...' if len(self.task_text) > 200 else ''}")
        lines.append(f"- **Task sha256:** `{self.task_text_sha256}`")
        lines.append(f"- **Receipt sha256:** `{self.receipt_sha256}`")
        lines.append(f"- **Receipt integrity:** {'OK' if ok else 'BROKEN: ' + '; '.join(problems)}")
        if self.signature:
            sig = self.signature
            lines.append(f"- **Signed:** Ed25519, key `{sig.get('key_id')}`, at {sig.get('signed_at')}")
        else:
            lines.append("- **Signed:** no")
        if str(self.plan.get("task_summary", "")).startswith("SCRIPTED ATTACK"):
            lines.append(
                "- **Plan source:** a fixed attack script standing in for a hijacked agent. No model wrote it. "
                "The VMs, the kernel log lines and this receipt are real."
            )
        lines.append("")
        lines.append("## What was refused")
        lines.append("")
        refused = self.refusals()
        if refused:
            lines.append("| Refused | Stopped by | Count |")
            lines.append("|---|---|---|")
            for row in refused:
                lines.append(f"| DENIED {row['what']} | {row['by']} | {row['count']} |")
        else:
            lines.append("Nothing was refused.")
        lines.append("")
        lines.append("## Blast radius")
        lines.append("")
        lines.append("| Sandbox | Provider | Instance | Created | Destroyed | Proof | Inner layer | Egress |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for s in self.sandboxes:
            proof = "-"
            if s.proof_of_destruction:
                proof = f"{s.proof_of_destruction.get('method')} -> {s.proof_of_destruction.get('http_status')}"
            lines.append(
                f"| {s.role} | {s.provider} | `{s.instance_id}` | {_fmt(s.created_at)} | {_fmt(s.destroyed_at)} | "
                f"{proof} | {s.inner_isolation or '-'} | {s.egress_policy} |"
            )
        lines.append("")
        lines.append(f"All VMs destroyed: **{'yes' if self.all_vms_destroyed else 'NO'}**")
        lines.append("")
        lines.append("## Plan")
        lines.append("")
        lines.append(f"{self.plan.get('task_summary', '')}  ")
        lines.append(
            f"Planner model: `{self.planner_model or '-'}`; est. cost ${self.plan.get('est_cost_usd', 0):.4f}; "
            f"required domains: {', '.join(self.plan.get('required_domains') or []) or 'none'}"
        )
        lines.append("")
        lines.append("## Steps")
        lines.append("")
        lines.append("| Step | Kind | Exit | Duration | stdout sha256 | Output files | Executor |")
        lines.append("|---|---|---|---|---|---|---|")
        for st in self.steps:
            files = ", ".join(f"{n} `{h[:12]}`" for n, h in st.output_files.items()) or "-"
            rep = " (repaired)" if st.repaired else ""
            lines.append(
                f"| {st.step_id} {st.title}{rep} | {st.kind} | {st.exit_code} | {st.duration_s:.2f}s | "
                f"`{st.stdout_sha256[:12]}` | {files} | {st.executor or '-'} |"
            )
        lines.append("")
        lines.append("## Verification")
        lines.append("")
        v = self.verifier
        lines.append(
            f"- **Verdict:** {'PASSED' if v.get('passed') else 'FAILED'} (model: `{v.get('verifier_model', '-')}`)"
        )
        lines.append(
            f"- **Independent re-run:** {'performed' if v.get('rerun_performed') else 'not performed'}; "
            f"hashes identical: {v.get('rerun_match')}"
        )
        for c in v.get("checks", []):
            lines.append(f"  - [{'x' if c.get('passed') else ' '}] {c.get('name')} {c.get('detail', '')}".rstrip())
        mr = v.get("model_review")
        if mr:
            lines.append(
                f"- **Model review:** satisfies_task={mr.get('satisfies_task')} confidence={mr.get('confidence')}"
            )
            for r in mr.get("reasons", []):
                lines.append(f"  - {r}")
            for cnc in mr.get("concerns", []):
                lines.append(f"  - concern: {cnc}")
        lines.append("")
        lines.append("## Egress")
        lines.append("")
        lines.append(f"Policy: default-deny. Allowed domains: {', '.join(self.egress.allowed_domains) or 'none'}.  ")
        eg = self.egress
        lines.append(f"Attempts: {len(eg.attempts)} (denied {eg.denied_count}, allowed {eg.allowed_count})")
        for a in self.egress.attempts[:50]:
            lines.append(
                f"- {a.ts} {a.verdict.upper()} {a.proto} {a.dst_ip}:{a.dst_port or ''} {a.domain or ''}".rstrip()
            )
        lines.append("")
        lines.append("## Secret hygiene")
        lines.append("")
        if self.secret_scan is None:
            lines.append("Scan not performed.")
        else:
            ss = self.secret_scan
            lines.append(
                f"- Result: **{'CLEAN' if ss.clean else str(ss.findings_count) + ' FINDING(S)'}** "
                f"({ss.files_scanned} files, {ss.env_vars_checked} env vars, scanner `{ss.scanner}`)"
            )
            for f in ss.findings[:20]:
                lines.append(f"  - {f.get('kind')} at {f.get('where')}: `{f.get('redacted')}`")
        lines.append("")
        lines.append("## Cost")
        lines.append("")
        lines.append(
            f"- **Total:** ${self.cost.total_usd:.4f} (VM ${self.cost.vm_usd:.4f}, tokens ${self.cost.tokens_usd:.4f})"
            + (
                f"; budget ${self.cost.budget_usd:.2f} -> {'within' if self.cost.within_budget else 'EXCEEDED'}"
                if self.cost.budget_usd is not None
                else ""
            )
        )
        for ln in self.cost.lines:
            lines.append(f"  - {ln.get('label')}: ${ln.get('usd', 0):.5f}")
        lines.append("")
        lines.append("## Audit chain")
        lines.append("")
        lines.append(
            f"{len(self.audit_events)} events, head `{self.audit_head_hash}`, "
            f"verification: {'OK' if self.audit_chain.ok else 'BROKEN'}"
        )
        lines.append("")
        lines.append("| # | Time | Event | Hash |")
        lines.append("|---|---|---|---|")
        for e in self.audit_events:
            lines.append(f"| {e.seq} | {e.ts} | {e.kind} | `{e.hash[:16]}` |")
        lines.append("")
        return "\n".join(lines)


def _fmt(dt: datetime | None) -> str:
    return dt.isoformat(timespec="seconds") if dt else "-"


def build_receipt(
    *,
    task_id: str,
    status: str,
    task_text: str,
    input_files: dict[str, str],
    plan: dict[str, Any],
    planner_model: str,
    steps: list[StepReceipt],
    verifier: dict[str, Any],
    sandboxes: list[SandboxReceipt],
    egress: EgressSummary,
    secret_scan: SecretScanSummary | None,
    cost: CostSummary,
    audit: AuditLog,
    now: datetime | None = None,
) -> Receipt:
    receipt = Receipt(
        task_id=task_id,
        created_at=now or datetime.now(timezone.utc),
        status=status,
        task_text_sha256=sha256_hex(task_text),
        task_text=task_text,
        input_files=input_files,
        plan=plan,
        planner_model=planner_model,
        steps=steps,
        verifier=verifier,
        sandboxes=sandboxes,
        egress=egress,
        secret_scan=secret_scan,
        cost=cost,
        audit_events=audit.events,
        audit_head_hash=audit.head_hash,
        audit_chain=audit.verify(),
    )
    return receipt.finalize()
