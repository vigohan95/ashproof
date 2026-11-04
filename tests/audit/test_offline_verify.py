"""The offline verifier must catch every edit, and be honest about the one it cannot catch without a pin."""

from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

from brz.audit import (
    AuditLog,
    CostSummary,
    EgressSummary,
    Receipt,
    SecretScanSummary,
    StepReceipt,
    build_receipt,
    canonical_json,
)
from brz.audit import offline_verify as ov

NOW = datetime(2026, 11, 5, 12, 0, 0, tzinfo=timezone.utc)
TOOL = str(Path(ov.__file__))
TASK = "Sum the amount column per region"


def _step(sid: str, n: int) -> StepReceipt:
    return StepReceipt(
        step_id=sid,
        title=f"step {n}",
        kind="python",
        code_sha256=f"{n}" * 64,
        exit_code=0,
        duration_s=0.5,
        stdout_sha256=f"{n + 1}" * 64,
        stderr_sha256="e" * 64,
        output_files={f"out{n}.json": f"{n + 2}" * 64},
    )


def _receipt() -> Receipt:
    log = AuditLog(clock=lambda: NOW)
    log.append("task.received", {"task_sha256": hashlib.sha256(TASK.encode()).hexdigest()})
    steps = [_step("s1", 1), _step("s2", 4)]
    for s in steps:
        for role in ("primary", "verifier"):
            log.append(
                "step.finished",
                {
                    "role": role,
                    "step_id": s.step_id,
                    "exit_code": 0,
                    "stdout_sha256": s.stdout_sha256,
                    "files": s.output_files,
                },
            )
    log.append("verify.verdict", {"passed": True, "rerun_match": True})
    log.append("vm.destroyed", {"http_status": 404})
    log.append("task.verified", {})
    return build_receipt(
        task_id="t1",
        status="verified",
        task_text=TASK,
        input_files={},
        plan={"task_summary": "sum"},
        planner_model="m",
        steps=steps,
        verifier={"passed": True, "rerun_match": True, "checks": []},
        sandboxes=[],
        egress=EgressSummary(),
        secret_scan=SecretScanSummary(clean=True),
        cost=CostSummary(total_usd=0.01),
        audit=log,
        now=NOW,
    )


@pytest.fixture
def raw() -> bytes:
    return _receipt().to_json().encode("utf-8")


def _edit(raw: bytes, fn) -> bytes:
    data = json.loads(raw)
    fn(data)
    return json.dumps(data).encode("utf-8")


def _reseal_receipt(data: dict) -> None:
    body = {k: v for k, v in data.items() if k != "receipt_sha256"}
    data["receipt_sha256"] = hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest()


def _rewrite_chain(data: dict) -> None:
    """Forge properly: recompute every event hash, the head, the chain block and the receipt hash."""
    prev = ov.GENESIS_HASH
    for ev in data["audit_events"]:
        ev["prev_hash"] = prev
        ev["hash"] = ov.event_hash(ev)
        prev = ev["hash"]
    data["audit_head_hash"] = prev
    data["audit_chain"]["head_hash"] = prev
    data["audit_chain"]["length"] = len(data["audit_events"])
    _reseal_receipt(data)


def test_honest_receipt_passes_and_matches_the_pydantic_verifier(raw: bytes):
    res = ov.verify_bytes(raw)
    assert res["ok"], res
    assert res["events"] == 8 and res["steps"] == 2 and res["pinned"] is False
    assert Receipt.model_validate_json(raw).verify() == (True, [])


def test_one_flipped_byte_anywhere_is_detected(raw: bytes):
    positions = range(0, len(raw), 53)
    for pos in positions:
        flipped = bytearray(raw)
        flipped[pos] ^= 0x01
        assert not ov.verify_bytes(bytes(flipped))["ok"], f"flip at byte {pos} went unnoticed"


def test_flip_inside_an_event_names_the_event(raw: bytes):
    def tamper(d):
        d["audit_events"][1]["data"]["exit_code"] = 1

    res = ov.verify_bytes(_edit(raw, tamper))
    assert not res["ok"] and "event 1 (step.finished): content does not match its hash" in res["problems"]


@pytest.mark.parametrize("where", ["chain", "table", "table_resealed"])
def test_a_deleted_step_is_detected(raw: bytes, where: str):
    def tamper(d):
        if where == "chain":
            del d["audit_events"][3]  # s2 primary
        else:
            del d["steps"][1]
        if where == "table_resealed":
            _reseal_receipt(d)

    res = ov.verify_bytes(_edit(raw, tamper))
    assert not res["ok"]
    if where == "chain":
        assert "sequence gap" in res["problems"][0]
    if where == "table_resealed":
        assert res["problems"] == ["steps table ['s1'] does not match the chain ['s1', 's2']"]


@pytest.mark.parametrize("where", ["chain", "table_resealed"])
def test_reordered_steps_are_detected(raw: bytes, where: str):
    def tamper(d):
        if where == "chain":
            ev = d["audit_events"]
            ev[1], ev[3] = ev[3], ev[1]
        else:
            d["steps"].reverse()
            _reseal_receipt(d)

    res = ov.verify_bytes(_edit(raw, tamper))
    assert not res["ok"]
    if where == "chain":
        assert "sequence gap" in res["problems"][0]
    else:
        assert "does not match the chain" in res["problems"][0]


@pytest.mark.parametrize(
    ("edit", "expected"),
    [
        (lambda d: d["steps"][0].update(exit_code=1), "step s1: exit_code"),
        (lambda d: d["steps"][0].update(stdout_sha256="0" * 64), "step s1: stdout_sha256"),
        (lambda d: d["steps"][1]["output_files"].update({"extra": "1" * 64}), "step s2: output_files"),
        (lambda d: d["verifier"].update(passed=False), "verifier.passed"),
        (lambda d: d.update(status="failed"), "status 'failed'"),
        (lambda d: d.update(task_text="something else"), "task_text does not match"),
    ],
)
def test_editing_the_readable_fields_is_caught_even_with_a_resealed_receipt_hash(raw: bytes, edit, expected: str):
    def tamper(d):
        edit(d)
        _reseal_receipt(d)

    res = ov.verify_bytes(_edit(raw, tamper))
    assert not res["ok"] and any(expected in p for p in res["problems"]), res["problems"]


def test_added_field_is_caught(raw: bytes):
    res = ov.verify_bytes(_edit(raw, lambda d: d.update(note="added later")))
    assert res["problems"] == ["receipt_sha256 does not match the file"]


def test_a_full_rewrite_needs_a_pinned_head_and_the_tool_says_so(raw: bytes):
    honest_head = json.loads(raw)["audit_head_hash"]

    def tamper(d):
        d["audit_events"][1]["data"]["stdout_sha256"] = "0" * 64
        d["steps"][0]["stdout_sha256"] = "0" * 64
        _rewrite_chain(d)

    forged = _edit(raw, tamper)
    unpinned = ov.verify_bytes(forged)
    assert unpinned["ok"] and unpinned["pinned"] is False  # a chain has no key: this forgery is self-consistent
    pinned = ov.verify_bytes(forged, expect_head=honest_head)
    assert not pinned["ok"] and "pinned value" in pinned["problems"][0]


def test_jsonl_audit_log(raw: bytes):
    events = json.loads(raw)["audit_events"]
    good = "".join(canonical_json(e) + "\n" for e in events).encode()
    assert ov.verify_bytes(good, jsonl=True)["ok"]
    assert not ov.verify_bytes(good.replace(b"step.finished", b"step.finishee", 1), jsonl=True)["ok"]
    assert not ov.verify_bytes(good, jsonl=True, expect_head="0" * 64)["ok"]
    assert not ov.verify_bytes(b"not json\n", jsonl=True)["ok"]


@pytest.mark.parametrize("junk", [b"", b"[]", b"{}", b"\xff\xfe", b'{"audit_events": [1]}'])
def test_junk_is_rejected_without_a_crash(junk: bytes):
    assert ov.verify_bytes(junk)["ok"] is False


def test_cli_runs_with_python_alone(tmp_path: Path, raw: bytes):
    """-I -S: no site-packages, no project on the path. The auditor needs nothing but Python."""
    path = tmp_path / "receipt.json"
    path.write_bytes(raw)
    head = json.loads(raw)["audit_head_hash"]

    def run(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(
            [sys.executable, "-I", "-S", TOOL, *args], capture_output=True, text=True, timeout=30, check=False
        )

    ok = run(str(path))
    assert ok.returncode == 0 and ok.stdout.startswith("OK: 8 events, 2 steps") and "self-consistent only" in ok.stdout
    pinned = run(str(path), "--expect-head", head, "--expect-receipt", json.loads(raw)["receipt_sha256"])
    assert pinned.returncode == 0 and "self-consistent" not in pinned.stdout
    data = copy.deepcopy(json.loads(raw))
    data["audit_events"][2]["ts"] = "2026-11-05T12:00:01+00:00"
    path.write_text(json.dumps(data))
    bad = run(str(path), "--json")
    assert bad.returncode == 1 and json.loads(bad.stdout)["ok"] is False
    assert run(str(tmp_path / "missing.json")).returncode == 2
