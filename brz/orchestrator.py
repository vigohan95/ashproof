"""Orchestrator: plan -> approve -> throwaway VM -> steps -> independent re-run -> verify -> scan -> destroy -> receipt.

Everything is dependency-injected (planner, verifier, sandbox backend, price table, clock) so
the identical code path runs against mock Vultr + FakeLLM + local runner in tests and against
the live Vultr API + Serverless Inference in production.

State machine (``TaskState.status``):

    queued -> planning -> [awaiting_approval] -> provisioning -> running -> verifying
           -> scanning -> destroying -> verified | failed | killed | error

Every transition, every LLM call, every step, every egress attempt and the VM 404 are
appended to the task's hash-chained audit log, which ends up inside the receipt.
"""

from __future__ import annotations

import asyncio
import hashlib
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

from brz.audit import (
    AuditLog,
    CostSummary,
    EgressAttempt,
    EgressSummary,
    Receipt,
    SandboxReceipt,
    SecretScanSummary,
    StepReceipt,
    build_receipt,
)
from brz.cost import CostMeter, PriceTable, StaticPriceTable
from brz.llm import Plan, Planner, PlanStep, StepOutcome, Verifier, VerifierVerdict
from brz.llm.client import Usage
from brz.sandbox.backends import SandboxBackend, SandboxHandle
from brz.sandbox.runner_client import RunnerClient, RunnerError, RunnerStepResult


class TaskRequest(BaseModel):
    task: str = Field(min_length=3, max_length=20_000)
    budget_usd: float = Field(default=0.25, gt=0, le=50)
    allowed_domains: list[str] = Field(default_factory=list)
    files: dict[str, bytes] = Field(default_factory=dict)  # name -> content
    require_approval: bool = True  # park on new egress domains until a human approves (UI toggle)


@dataclass
class OrchestratorConfig:
    verify_in_fresh_sandbox: bool = True
    max_repairs: int = 1
    require_approval_for_new_domains: bool = True
    approval_timeout_s: float = 900.0
    runner_ready_timeout_s: float = 240.0
    runner_ready_interval_s: float = 3.0
    preview_bytes: int = 4000
    planner_model_label: str = ""
    verifier_model_label: str = ""
    parallel_verifier_boot: bool = False  # boot the second VM while the first works; saves one boot per task
    max_step_timeout_s: int = 1800


def repair_violations(original: PlanStep, fixed: PlanStep) -> list[str]:
    """How a repaired step widens what was planned. Step output reaches the repair prompt, so a repair may
    change code but nothing that was approved or that the verifier checks: only the human gate can widen those."""
    problems: list[str] = []
    if fixed.needs_network and not original.needs_network:
        problems.append("needs_network turned on")
    if fixed.timeout_s > original.timeout_s:
        problems.append(f"timeout raised from {original.timeout_s}s to {fixed.timeout_s}s")
    dropped = sorted(set(original.expected_outputs) - set(fixed.expected_outputs))
    if dropped:
        problems.append(f"expected outputs removed: {dropped}")
    return problems


class TaskKilled(Exception):
    pass


class TaskFailed(Exception):
    pass


@dataclass
class TaskState:
    request: TaskRequest
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    status: str = "queued"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: datetime | None = None
    plan: Plan | None = None
    planner_model: str = ""
    pending_domains: list[str] = field(default_factory=list)
    approved_domains: list[str] = field(default_factory=list)
    approval: asyncio.Event = field(default_factory=asyncio.Event)
    approval_decision: bool | None = None
    kill_requested: bool = False
    kill_reason: str = ""
    audit: AuditLog = field(default_factory=AuditLog)
    cost: CostMeter = field(default_factory=CostMeter)
    sandboxes: list[SandboxHandle] = field(default_factory=list)
    step_receipts: list[StepReceipt] = field(default_factory=list)
    primary_outcomes: list[StepOutcome] = field(default_factory=list)
    rerun_outcomes: list[StepOutcome] | None = None
    verdict: VerifierVerdict | None = None
    egress_attempts: list[EgressAttempt] = field(default_factory=list)
    secret_scan: SecretScanSummary | None = None
    receipt: Receipt | None = None
    error: str = ""
    outputs: dict[str, bytes] = field(default_factory=dict)  # final output files (primary run)
    _clients: dict[str, RunnerClient] = field(default_factory=dict)
    _destroy_locks: dict[str, asyncio.Lock] = field(default_factory=dict)

    def set_status(self, status: str, **data: Any) -> None:
        self.status = status
        self.audit.append(f"task.{status}", {"task_id": self.id, **data})

    def timeline(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "finished_at": self.finished_at.isoformat() if self.finished_at else None,
            "task": self.request.task,
            "budget_usd": self.request.budget_usd,
            "allowed_domains": sorted({*self.request.allowed_domains, *self.approved_domains}),
            "pending_domains": self.pending_domains,
            "require_approval": self.request.require_approval,
            "kill_requested": self.kill_requested,
            "plan": self.plan.model_dump() if self.plan else None,
            "planner_model": self.planner_model,
            "sandboxes": [
                {
                    "role": h.role,
                    "instance_id": h.instance_id,
                    "plan": h.plan,
                    "region": h.region,
                    "created_at": h.created_at.isoformat() if h.created_at else None,
                    "active_at": h.active_at.isoformat() if h.active_at else None,
                    "destroyed_at": h.destroyed_at.isoformat() if h.destroyed_at else None,
                    "destroyed": bool(h.proof and h.proof.destroyed),
                    "proof": (
                        {
                            "method": h.proof.method,
                            "http_status": h.proof.http_status,
                            "observed_at": h.proof.observed_at.isoformat(),
                            "attempts": h.proof.attempts,
                        }
                        if h.proof
                        else None
                    ),
                    "runner_url": h.runner_url,
                }
                for h in self.sandboxes
            ],
            "steps": [s.model_dump() for s in self.step_receipts],
            "verdict": self.verdict.model_dump() if self.verdict else None,
            "egress": {
                "attempts": len(self.egress_attempts),
                "denied": sum(1 for a in self.egress_attempts if a.verdict == "denied"),
                "list": [a.model_dump() for a in self.egress_attempts[:200]],
            },
            "secret_scan": self.secret_scan.model_dump() if self.secret_scan else None,
            "cost": self.cost.breakdown(),
            "error": self.error,
            "events": [e.model_dump() for e in self.audit.events],
            "audit_head_hash": self.audit.head_hash,
            "receipt_ready": self.receipt is not None,
        }


class Orchestrator:
    def __init__(
        self,
        *,
        planner: Planner,
        verifier: Verifier,
        backend: SandboxBackend,
        prices: PriceTable | None = None,
        config: OrchestratorConfig | None = None,
    ):
        self.planner = planner
        self.verifier = verifier
        self.backend = backend
        self.prices = prices or StaticPriceTable()
        self.config = config or OrchestratorConfig()

    def new_task(self, request: TaskRequest) -> TaskState:
        state = TaskState(request=request)
        state.cost = CostMeter(prices=self.prices, budget_usd=request.budget_usd)
        state.audit.append(
            "task.received",
            {
                "task_id": state.id,
                "task_sha256": hashlib.sha256(request.task.encode()).hexdigest(),
                "budget_usd": request.budget_usd,
                "allowed_domains": request.allowed_domains,
                "files": {n: hashlib.sha256(b).hexdigest() for n, b in request.files.items()},
            },
        )
        return state

    # ------------------------------------------------------------------ run
    async def run(self, state: TaskState) -> Receipt:
        final_status = "error"
        verifier_boot: asyncio.Task | None = None
        try:
            await self._plan(state)
            await self._approval_gate(state)
            self._budget_preflight(state)
            if self.config.verify_in_fresh_sandbox and self.config.parallel_verifier_boot:
                verifier_boot = asyncio.create_task(self._provision(state, "verifier", background=True))
            primary = await self._provision(state, "primary")
            await self._execute_steps(state, primary, record=True)
            if self.config.verify_in_fresh_sandbox:
                state.set_status("verifying", mode="fresh-sandbox re-run")
                verifier_vm = await (verifier_boot or self._provision(state, "verifier"))
                state.rerun_outcomes = await self._execute_steps(state, verifier_vm, record=False)
                await self._destroy(state, verifier_vm)
            else:
                state.set_status("verifying", mode="deterministic-only")
            await self._verify(state)
            await self._scan_and_egress(state, primary)
            await self._destroy(state, primary)
            scan_clean = state.secret_scan is None or state.secret_scan.clean
            if not scan_clean:
                state.error = "secret scan is not clean"
            final_status = "verified" if state.verdict and state.verdict.passed and scan_clean else "failed"
        except TaskKilled:
            final_status = "killed"
        except TaskFailed as exc:
            state.error = str(exc)
            final_status = "failed"
        except Exception as exc:  # noqa: BLE001 - anything else is recorded, VMs still destroyed
            if state.kill_requested:  # a VM deleted under a waiting call is the kill working, not a fault
                final_status = "killed"
            else:
                state.error = f"{type(exc).__name__}: {exc}"
                state.audit.append("task.error", {"error": state.error})
                final_status = "error"
        finally:
            if verifier_boot is not None:
                if not verifier_boot.done():
                    verifier_boot.cancel()
                await asyncio.gather(verifier_boot, return_exceptions=True)
            await self._destroy_all(state)
            await self._close_clients(state)
            state.finished_at = datetime.now(timezone.utc)
            state.set_status(final_status, error=state.error or None, total_usd=state.cost.total_usd)
            state.receipt = self._build_receipt(state, final_status)
        return state.receipt

    # ---------------------------------------------------------------- stages
    async def _plan(self, state: TaskState) -> None:
        state.set_status("planning")
        req = state.request
        res = await self.planner.plan(
            req.task,
            budget_usd=req.budget_usd,
            allowed_domains=req.allowed_domains,
            attachments=sorted(req.files),
            vm_plan=getattr(getattr(self.backend, "config", None), "plan", "vhp-1c-1gb-amd"),
        )
        for step in res.plan.steps:
            step.timeout_s = min(step.timeout_s, self.config.max_step_timeout_s)
        state.plan = res.plan
        state.planner_model = res.model or self.config.planner_model_label
        self._charge_tokens(state, state.planner_model, res.usage, "planner")
        state.audit.append(
            "plan.created",
            {
                "model": state.planner_model,
                "json_schema": res.used_json_schema,
                "steps": [s.model_dump(exclude={"code"}) | {"code_sha256": _sha(s.code)} for s in res.plan.steps],
                "required_domains": res.plan.required_domains,
                "unapproved_domains": res.unapproved_domains,
                "est_cost_usd": res.plan.est_cost_usd,
                "risk_notes": res.plan.risk_notes,
                "usage": res.usage.model_dump(),
            },
        )
        state.pending_domains = res.unapproved_domains
        self._check_kill(state)

    async def _approval_gate(self, state: TaskState) -> None:
        if not state.pending_domains:
            return
        if not self.config.require_approval_for_new_domains or not state.request.require_approval:
            state.approved_domains = list(state.pending_domains)
            state.pending_domains = []
            state.audit.append("approval.auto", {"domains": state.approved_domains})
            return
        state.set_status("awaiting_approval", domains=state.pending_domains)
        try:
            await asyncio.wait_for(state.approval.wait(), timeout=self.config.approval_timeout_s)
        except TimeoutError:
            state.audit.append("approval.timeout", {"domains": state.pending_domains})
            raise TaskFailed("approval timed out") from None
        self._check_kill(state)
        if not state.approval_decision:
            state.audit.append("approval.rejected", {"domains": state.pending_domains})
            raise TaskFailed(f"domains rejected by user: {state.pending_domains}")
        state.approved_domains = list(state.pending_domains)
        state.pending_domains = []
        state.audit.append("approval.granted", {"domains": state.approved_domains})

    def approve(self, state: TaskState, approved: bool) -> None:
        state.approval_decision = approved
        state.approval.set()

    def _budget_preflight(self, state: TaskState) -> None:
        assert state.plan is not None
        vm_plan = getattr(getattr(self.backend, "config", None), "plan", "vhp-1c-1gb-amd")
        vms = 2 if self.config.verify_in_fresh_sandbox else 1
        projected = state.cost.total_usd + vms * state.cost.projected_vm_cost(vm_plan, 60)
        state.audit.append(
            "budget.preflight",
            {
                "spent_usd": state.cost.total_usd,
                "projected_usd": projected,
                "plan_estimate_usd": state.plan.est_cost_usd,
                "budget_usd": state.request.budget_usd,
            },
        )
        if projected > state.request.budget_usd:
            raise TaskFailed(f"projected cost ${projected:.4f} exceeds budget ${state.request.budget_usd:.4f}")

    async def _provision(self, state: TaskState, role: str, *, background: bool = False) -> SandboxHandle:
        self._check_kill(state)
        if background:
            state.audit.append("task.provisioning", {"task_id": state.id, "role": role, "background": True})
        else:
            state.set_status("provisioning", role=role)
        domains = sorted({*state.request.allowed_domains, *state.approved_domains})
        handle = await self.backend.provision(state.id, role, domains, on_created=state.sandboxes.append)
        self._check_kill(state)
        state.audit.append(
            "vm.created",
            {
                "role": role,
                "instance_id": handle.instance_id,
                "plan": handle.plan,
                "region": handle.region,
                "provider": self.backend.provider,
                "allowed_domains": domains,
                "egress_policy": "default-deny",
                "inner_isolation": self.backend.inner_isolation,
                "label": handle.meta.get("label"),
                "admin_access": bool(handle.meta.get("admin_access")),
            },
        )
        client = RunnerClient(handle.runner_url, task_id=state.id, token_key=handle.token_key)
        state._clients[handle.instance_id] = client
        health = await client.wait_ready(
            timeout=self.config.runner_ready_timeout_s,
            interval=self.config.runner_ready_interval_s,
            should_stop=lambda: state.kill_requested,
        )
        state.audit.append(
            "vm.runner_ready",
            {
                "role": role,
                "instance_id": handle.instance_id,
                "executor": health.get("executor"),
                "main_ip": handle.meta.get("main_ip"),
            },
        )
        self._check_kill(state)
        return handle

    async def _execute_steps(self, state: TaskState, handle: SandboxHandle, *, record: bool) -> list[StepOutcome]:
        assert state.plan is not None
        client = state._clients[handle.instance_id]
        if record:
            state.set_status("running", instance_id=handle.instance_id)
        outcomes: list[StepOutcome] = []
        for idx, step in enumerate(list(state.plan.steps)):
            self._check_kill(state)
            if state.cost.over_budget():
                raise TaskFailed(f"budget exceeded mid-task (${state.cost.total_usd:.4f})")
            files = state.request.files if idx == 0 else {}
            current = step
            attempts = 0
            repaired = False
            while True:
                attempts += 1
                try:
                    result = await client.run_step(current, files=files)
                except RunnerError as exc:
                    if state.kill_requested or exc.status in (403, 410):
                        raise TaskKilled() from exc
                    raise
                self._record_step(state, handle, current, result, attempts, repaired, record)
                ok = result.exit_code == 0 and not result.missing_expected_outputs
                if ok or not record or attempts > self.config.max_repairs:
                    break
                fixed, usage = await self.planner.repair(
                    state.request.task,
                    state.plan,
                    current,
                    exit_code=result.exit_code,
                    stdout=result.stdout,
                    stderr=result.stderr,
                )
                self._charge_tokens(state, state.planner_model, usage, "planner.repair")
                violations = repair_violations(current, fixed.step)
                if violations:
                    state.audit.append(
                        "step.repair_rejected",
                        {
                            "step_id": current.id,
                            "violations": violations,
                            "explanation": fixed.explanation,
                            "rejected_code_sha256": _sha(fixed.step.code),
                        },
                    )
                    raise TaskFailed(f"repair of step {current.id} rejected: {'; '.join(violations)}")
                state.audit.append(
                    "step.repaired",
                    {"step_id": current.id, "explanation": fixed.explanation, "new_code_sha256": _sha(fixed.step.code)},
                )
                state.plan.steps[idx] = fixed.step
                current = fixed.step
                repaired = True
            outcomes.append(self._outcome(current, result))
            if record:
                for name, f in result.files.items():
                    if f.content is not None:
                        state.outputs[name] = f.content
            if not ok and record:
                raise TaskFailed(f"step {current.id} failed with exit code {result.exit_code}")
        if record:
            state.primary_outcomes = outcomes
        return outcomes

    def _record_step(
        self,
        state: TaskState,
        handle: SandboxHandle,
        step: PlanStep,
        result: RunnerStepResult,
        attempts: int,
        repaired: bool,
        record: bool,
    ) -> None:
        role = handle.role
        for a in result.egress_attempts:
            attempt = EgressAttempt(
                ts=str(a.get("ts", "")),
                dst_ip=str(a.get("dst_ip", "")),
                dst_port=a.get("dst_port"),
                proto=str(a.get("proto", "")),
                verdict=str(a.get("verdict", "denied")),
                raw=str(a.get("raw", "")),
            )
            state.egress_attempts.append(attempt)
            state.audit.append(
                f"egress.{attempt.verdict}",
                {
                    "role": role,
                    "step_id": step.id,
                    "dst_ip": attempt.dst_ip,
                    "dst_port": attempt.dst_port,
                    "proto": attempt.proto,
                },
            )
        state.audit.append(
            "step.finished",
            {
                "role": role,
                "step_id": step.id,
                "attempt": attempts,
                "exit_code": result.exit_code,
                "duration_s": round(result.duration_s, 3),
                "stdout_sha256": result.stdout_sha256,
                "files": result.file_hashes,
                "executor": result.executor,
                "timed_out": result.timed_out,
                "missing_expected_outputs": result.missing_expected_outputs,
                "skipped_outputs": result.skipped_outputs,
                "secret_findings": result.secret_findings,
            },
        )
        if record:
            state.step_receipts = [s for s in state.step_receipts if s.step_id != step.id]
            state.step_receipts.append(
                StepReceipt(
                    step_id=step.id,
                    title=step.title,
                    kind=step.kind,
                    code_sha256=_sha(step.code),
                    exit_code=result.exit_code,
                    duration_s=result.duration_s,
                    stdout_sha256=result.stdout_sha256,
                    stderr_sha256=result.stderr_sha256,
                    output_files=result.file_hashes,
                    attempts=attempts,
                    repaired=repaired,
                    executor=result.executor,
                )
            )

    def _outcome(self, step: PlanStep, result: RunnerStepResult) -> StepOutcome:
        n = self.config.preview_bytes
        return StepOutcome(
            step_id=step.id,
            exit_code=result.exit_code,
            duration_s=result.duration_s,
            stdout_sha256=result.stdout_sha256,
            stderr_sha256=result.stderr_sha256,
            files=result.file_hashes,
            stdout_preview=result.stdout[:n],
            stderr_preview=result.stderr[:n],
            file_previews={name: result.file_text(name, n) for name in result.files},
        )

    async def _verify(self, state: TaskState) -> None:
        assert state.plan is not None
        self._check_kill(state)
        verdict = await self.verifier.verify(
            state.request.task,
            state.plan,
            state.primary_outcomes,
            state.rerun_outcomes,
            inputs={
                n: b[: self.config.preview_bytes].decode("utf-8", "replace")
                for n, b in state.request.files.items()
            },
        )
        state.verdict = verdict
        self._charge_tokens(state, verdict.verifier_model, verdict.usage, "verifier")
        state.audit.append(
            "verify.verdict",
            {
                "passed": verdict.passed,
                "verifier_model": verdict.verifier_model,
                "rerun_performed": verdict.rerun_performed,
                "rerun_match": verdict.rerun_match,
                "failed_checks": [c.model_dump() for c in verdict.failed_checks],
                "primary_hashes": verdict.primary_hashes,
                "rerun_hashes": verdict.rerun_hashes,
                "model_review": verdict.model_review.model_dump() if verdict.model_review else None,
            },
        )

    async def _scan_and_egress(self, state: TaskState, handle: SandboxHandle) -> None:
        self._check_kill(state)
        state.set_status("scanning", instance_id=handle.instance_id)
        client = state._clients[handle.instance_id]
        report = await client.scan()
        state.secret_scan = SecretScanSummary(
            clean=bool(report.get("clean")),
            findings_count=int(report.get("findings_count", 0)),
            findings=list(report.get("findings") or []),
            files_scanned=int(report.get("files_scanned", 0)),
            env_vars_checked=int(report.get("env_vars_checked", 0)),
            scanner=str(report.get("scanner", "")),
        )
        state.audit.append("secret_scan.done", state.secret_scan.model_dump())

    async def _destroy(self, state: TaskState, handle: SandboxHandle, *, revoke: bool = True) -> None:
        async with state._destroy_locks.setdefault(handle.instance_id, asyncio.Lock()):
            await self._destroy_locked(state, handle, revoke)

    async def _destroy_locked(self, state: TaskState, handle: SandboxHandle, revoke: bool) -> None:
        if handle.proof is not None:
            return
        state.set_status("destroying", instance_id=handle.instance_id, role=handle.role)
        client = state._clients.get(handle.instance_id)
        if client is not None and revoke:
            try:
                await client.revoke()
            except RunnerError:
                pass
        proof = await self.backend.destroy(handle)
        state.cost.add_vm(handle.plan or "unknown", handle.lifetime_seconds(), label=f"VM {handle.role} {handle.plan}")
        state.audit.append(
            "vm.destroyed",
            {
                "role": handle.role,
                "instance_id": handle.instance_id,
                "method": proof.method,
                "http_status": proof.http_status,
                "observed_at": proof.observed_at.isoformat(),
                "attempts": proof.attempts,
                "lifetime_s": round(handle.lifetime_seconds(), 1),
            },
        )

    async def _destroy_all(self, state: TaskState) -> None:
        for handle in state.sandboxes:
            if handle.proof is None:
                try:
                    await self._destroy(state, handle)
                except Exception as exc:  # noqa: BLE001
                    state.audit.append("vm.destroy_failed", {"instance_id": handle.instance_id, "error": repr(exc)})

    async def _close_clients(self, state: TaskState) -> None:
        for client in state._clients.values():
            await client.aclose()
        state._clients.clear()

    # ------------------------------------------------------------ kill switch
    async def kill(self, state: TaskState, reason: str = "user") -> None:
        """Revoke every runner token, destroy every VM, record it. Safe to call at any stage."""
        if state.kill_requested:
            return
        state.kill_requested = True
        state.kill_reason = reason
        state.audit.append("kill.requested", {"reason": reason, "status_at_kill": state.status})
        state.approval.set()  # unblock an approval wait
        await asyncio.gather(*(self._kill_one(state, h) for h in list(state.sandboxes)))

    async def _kill_one(self, state: TaskState, handle: SandboxHandle) -> None:
        client = state._clients.get(handle.instance_id)
        if client is not None:
            try:
                rev = await client.revoke()
                state.audit.append(
                    "kill.tokens_revoked",
                    {"instance_id": handle.instance_id, "killed_running_step": rev.get("killed_running_step")},
                )
            except RunnerError as exc:
                state.audit.append("kill.revoke_failed", {"instance_id": handle.instance_id, "error": str(exc)})
        try:
            await self._destroy(state, handle, revoke=False)
        except Exception as exc:  # noqa: BLE001
            state.audit.append("vm.destroy_failed", {"instance_id": handle.instance_id, "error": repr(exc)})

    def _check_kill(self, state: TaskState) -> None:
        if state.kill_requested:
            raise TaskKilled()

    # ---------------------------------------------------------------- helpers
    def _charge_tokens(self, state: TaskState, model: str, usage: Usage, label: str) -> None:
        if usage.total_tokens == 0:
            return
        line = state.cost.add_tokens(model or "unknown", usage.prompt_tokens, usage.completion_tokens, label=label)
        state.audit.append("cost.tokens", {"label": label, "model": model, **usage.model_dump(), "usd": line.usd})

    def _build_receipt(self, state: TaskState, status: str) -> Receipt:
        sandboxes = [
            SandboxReceipt(
                role=h.role,
                provider=self.backend.provider,
                instance_id=h.instance_id,
                plan=h.plan,
                region=h.region,
                created_at=h.created_at,
                active_at=h.active_at,
                destroyed_at=h.destroyed_at,
                proof_of_destruction=(
                    {
                        "method": h.proof.method,
                        "http_status": h.proof.http_status,
                        "observed_at": h.proof.observed_at.isoformat(),
                        "attempts": h.proof.attempts,
                    }
                    if h.proof
                    else None
                ),
                inner_isolation=self.backend.inner_isolation,
                ttl_minutes=getattr(getattr(self.backend, "config", None), "ttl_minutes", None),
            )
            for h in state.sandboxes
        ]
        verifier = (
            state.verdict.model_dump()
            if state.verdict
            else {"passed": False, "verifier_model": "", "checks": [], "rerun_performed": False, "rerun_match": None}
        )
        bd = state.cost.breakdown()
        return build_receipt(
            task_id=state.id,
            status=status,
            task_text=state.request.task,
            input_files={n: _sha_bytes(b) for n, b in state.request.files.items()},
            plan=state.plan.model_dump() if state.plan else {},
            planner_model=state.planner_model,
            steps=state.step_receipts,
            verifier=verifier,
            sandboxes=sandboxes,
            egress=EgressSummary(
                allowed_domains=sorted({*state.request.allowed_domains, *state.approved_domains}),
                attempts=state.egress_attempts,
            ),
            secret_scan=state.secret_scan,
            cost=CostSummary(
                total_usd=bd["total_usd"],
                vm_usd=bd["vm_usd"],
                tokens_usd=bd["tokens_usd"],
                lines=bd["lines"],
                budget_usd=state.request.budget_usd,
            ),
            audit=state.audit,
        )


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _sha_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()
