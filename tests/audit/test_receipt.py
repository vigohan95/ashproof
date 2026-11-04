from __future__ import annotations

import json
from datetime import datetime, timezone

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

NOW = datetime(2026, 11, 5, 12, 0, 0, tzinfo=timezone.utc)


def _receipt(status: str = "verified") -> Receipt:
    log = AuditLog(clock=lambda: NOW)
    log.append("task.received", {"task_id": "t1"})
    log.append("vm.created", {"instance_id": "vm-1"})
    log.append("vm.destroyed", {"instance_id": "vm-1", "http_status": 404})
    return build_receipt(
        task_id="t1",
        status=status,
        task_text="Sum the amount column per region",
        input_files={"sales.csv": "a" * 64},
        plan={"task_summary": "sum per region", "est_cost_usd": 0.01, "required_domains": []},
        planner_model="glm-5.3",
        steps=[
            StepReceipt(
                step_id="s1",
                title="aggregate",
                kind="python",
                code_sha256="b" * 64,
                exit_code=0,
                duration_s=0.42,
                stdout_sha256="c" * 64,
                stderr_sha256="d" * 64,
                output_files={"summary.json": "e" * 64},
                executor="subprocess",
            )
        ],
        verifier={
            "passed": True,
            "verifier_model": "qwen3.8-27b",
            "rerun_performed": True,
            "rerun_match": True,
            "checks": [{"name": "s1:exit_code", "passed": True, "detail": "exit_code=0"}],
            "model_review": {"satisfies_task": True, "confidence": 0.9, "reasons": ["ok"], "concerns": []},
        },
        sandboxes=[
            SandboxReceipt(
                role="primary",
                provider="mock-vultr",
                instance_id="vm-1",
                plan="vhp-1c-1gb-amd",
                region="ewr",
                created_at=NOW,
                destroyed_at=NOW,
                proof_of_destruction={
                    "method": "GET /v2/instances/{id}",
                    "http_status": 404,
                    "observed_at": NOW.isoformat(),
                },
                inner_isolation="gvisor runsc --platform=systrap",
                ttl_minutes=20,
            ),
            SandboxReceipt(
                role="verifier", provider="mock-vultr", instance_id="vm-2", proof_of_destruction={"http_status": 404}
            ),
        ],
        egress=EgressSummary(
            allowed_domains=[],
            attempts=[
                EgressAttempt(
                    ts="2026-11-05T12:00:03Z", dst_ip="93.184.216.34", dst_port=443, proto="tcp", verdict="denied"
                )
            ],
        ),
        secret_scan=SecretScanSummary(clean=True, files_scanned=12, env_vars_checked=30),
        cost=CostSummary(
            total_usd=0.0101,
            vm_usd=0.009,
            tokens_usd=0.0011,
            budget_usd=0.5,
            lines=[{"label": "VM vhp-1c-1gb-amd", "usd": 0.009}],
        ),
        audit=log,
        now=NOW,
    )


def test_receipt_is_self_verifying():
    r = _receipt()
    assert len(r.receipt_sha256) == 64
    ok, problems = r.verify()
    assert ok and problems == []
    assert r.audit_chain.ok and r.audit_head_hash == r.audit_events[-1].hash
    assert r.all_vms_destroyed
    assert r.egress.denied_count == 1 and r.egress.allowed_count == 0
    assert r.cost.within_budget


def test_receipt_tamper_detection():
    r = _receipt()
    cooked = Receipt.model_validate(json.loads(r.to_json()))
    cooked.cost.total_usd = 0.0
    ok, problems = cooked.verify()
    assert not ok and problems == ["receipt_sha256 mismatch (receipt modified)"]

    chained = Receipt.model_validate(json.loads(r.to_json()))
    chained.audit_events[1].data["instance_id"] = "someone-else"
    ok, problems = chained.verify()
    assert not ok and any("audit chain broken at seq 1" in p for p in problems)

    head = Receipt.model_validate(json.loads(r.to_json()))
    head.audit_head_hash = "f" * 64
    ok, problems = head.verify()
    assert not ok and "audit_head_hash does not match" in problems[-1]


def test_receipt_json_roundtrip_and_markdown():
    r = _receipt()
    back = Receipt.model_validate_json(r.to_json())
    assert back.receipt_sha256 == r.receipt_sha256 and back.verify()[0]

    md = r.to_markdown()
    assert md.startswith("# Ashproof receipt `t1`")
    assert "**Status:** VERIFIED" in md
    assert "Receipt integrity:** OK" in md
    assert "GET /v2/instances/{id} -> 404" in md
    assert "All VMs destroyed: **yes**" in md
    assert "gvisor runsc --platform=systrap" in md
    assert "| s1 aggregate | python | 0 |" in md
    assert "**Verdict:** PASSED" in md and "qwen3.8-27b" in md
    assert "DENIED tcp 93.184.216.34:443" in md
    assert "**CLEAN**" in md
    assert "**Total:** $0.0101" in md and "within" in md
    assert "3 events, head `" in md and "| 2 |" in md and "vm.destroyed" in md

    tampered = Receipt.model_validate_json(r.to_json())
    tampered.status = "verified!"
    assert "Receipt integrity:** BROKEN" in tampered.to_markdown()


def test_receipt_reports_undestroyed_vm():
    r = _receipt()
    r.sandboxes[1].proof_of_destruction = {"method": "GET /v2/instances/{id}", "http_status": 200}
    assert not r.all_vms_destroyed
    assert "All VMs destroyed: **NO**" in r.to_markdown()
