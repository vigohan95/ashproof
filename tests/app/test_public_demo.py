"""The limits a public URL needs, the archive that keeps receipts across restarts, and kill during boot."""

from __future__ import annotations

import asyncio
import base64
import json

import httpx
import pytest
from fastapi import HTTPException

from apps.control_plane import archive
from apps.control_plane.app import create_app
from apps.control_plane.deps import build_mock_deps
from apps.control_plane.guard import DemoGuard, DemoPolicy
from brz.audit import Receipt

CSV = base64.b64encode(b"region,amount\nnorth,10\nsouth,20\nnorth,5\n").decode()
TASK = {
    "task": "Total the amount column per region and write summary.json",
    "budget_usd": 0.25,
    "files": [{"name": "sales.csv", "content_b64": CSV}],
}


def guard(**kw) -> DemoGuard:
    return DemoGuard(DemoPolicy(enabled=True, **kw))


def admit(g: DemoGuard, client="a", **kw):
    args = {"task": "x", "budget_usd": 0.1, "domains": [], "files": {}, "running": 0} | kw
    g.admit(client, **args)


@pytest.mark.parametrize(
    ("kw", "status"),
    [
        ({"task": "x" * 2001}, 413),
        ({"files": {"a": b"x" * (256 * 1024 + 1)}}, 413),
        ({"budget_usd": 0.26}, 403),
        ({"domains": ["evil.example"]}, 403),
        ({"running": 2}, 429),
    ],
)
def test_refusals(kw, status):
    with pytest.raises(HTTPException) as err:
        admit(guard(), **kw)
    assert err.value.status_code == status


def test_disabled_guard_refuses_nothing():
    DemoGuard(DemoPolicy(enabled=False)).admit("a", task="x" * 9999, budget_usd=9, domains=["e.x"], files={}, running=9)


def test_per_client_limit_does_not_block_others():
    g = guard(tasks_per_client_hour=2)
    admit(g, "a")
    admit(g, "a")
    with pytest.raises(HTTPException):
        admit(g, "a")
    admit(g, "b")


def test_daily_limit_resets_next_day():
    now = [1_800_000_000.0]
    g = DemoGuard(DemoPolicy(enabled=True, tasks_per_day=1), clock=lambda: now[0])
    admit(g)
    with pytest.raises(HTTPException):
        admit(g, "b")
    now[0] += 86400
    admit(g, "b")


def test_counters_survive_a_restart_and_addresses_are_not_stored(tmp_path):
    path = tmp_path / "demo-state.json"
    g = DemoGuard(DemoPolicy(enabled=True, total_usd=0.05), path)
    admit(g, "203.0.113.9")
    g.note_finished(0.05)
    assert "203.0.113.9" not in path.read_text()
    again = DemoGuard(DemoPolicy(enabled=True, total_usd=0.05), path)
    with pytest.raises(HTTPException) as err:
        admit(again, "c")
    assert err.value.status_code == 429


async def run_app(app, fn):
    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
            return await fn(c, app)


async def test_a_stranger_cannot_approve_a_domain_off_the_list():
    from brz.orchestrator import TaskRequest

    g = guard(allowed_domains=["example.com"])
    app = create_app(build_mock_deps(), guard=g)

    async def go(c, app):
        orch = app.state.deps.orchestrator
        state = orch.new_task(TaskRequest(task="fetch it"))
        state.status = "awaiting_approval"
        state.pending_domains = ["evil.example"]
        app.state.store.tasks[state.id] = state
        denied = await c.post(f"/tasks/{state.id}/approve", json={"approved": True})
        rejected = await c.post(f"/tasks/{state.id}/approve", json={"approved": False})
        return denied.status_code, rejected.status_code, state.approval_decision

    assert await run_app(app, go) == (403, 200, False)


async def test_public_mode_keeps_the_approval_gate_on():
    app = create_app(build_mock_deps(), guard=guard())

    async def go(c, app):
        r = await c.post("/tasks", json=TASK | {"require_approval": False})
        tid = r.json()["id"]
        state = await app.state.store.wait(tid)
        return state.request.require_approval

    assert await run_app(app, go) is True


async def test_receipt_survives_a_restart(tmp_path):
    first = create_app(build_mock_deps(), guard=guard(), data_dir=tmp_path)

    async def run_task(c, app):
        tid = (await c.post("/tasks", json=TASK)).json()["id"]
        await app.state.store.wait(tid)
        return tid, (await c.get(f"/tasks/{tid}/receipt")).json()

    tid, receipt = await run_app(first, run_task)
    assert json.loads((tmp_path / "tasks" / f"{tid}.json").read_text())["status"] == "verified"

    second = create_app(build_mock_deps(), guard=guard(), data_dir=tmp_path)

    async def read(c, app):
        return (
            (await c.get(f"/tasks/{tid}/receipt")).json(),
            (await c.get(f"/tasks/{tid}/receipt/verify")).json(),
            (await c.get("/ui")).status_code,
            (await c.get(f"/ui/tasks/{tid}")).status_code,
            (await c.get(f"/ui/tasks/{tid}/receipt")).status_code,
            (await c.get(f"/tasks/{tid}/outputs/summary.json")).status_code,
            (await c.post(f"/tasks/{tid}/kill")).json()["killed"],
        )

    after, verify, ui, page, rpage, out, killed = await run_app(second, read)
    assert after == receipt
    assert verify["ok"] is True
    assert (ui, page, rpage, out) == (200, 200, 200, 200)
    assert killed is False


def test_a_corrupt_archive_file_is_skipped(tmp_path):
    (tmp_path / "bad.json").write_text("{not json")
    assert archive.load(tmp_path) == []
    assert Receipt  # imported for the archive round trip above


async def test_kill_during_boot_reaches_the_vm_and_ends_killed():
    """The VM exists before it is active. A kill in that window must delete it and report killed, not error."""
    from brz.orchestrator import TaskRequest
    from brz.vultr.mock import MockVultrState

    deps = build_mock_deps(mock_state=MockVultrState(activate_after_polls=10_000))
    deps.backend.config.vm_poll_interval_s = 0.01
    deps.orchestrator.config.parallel_verifier_boot = True
    orch = deps.orchestrator
    files = {"sales.csv": b"region,amount\na,1\n"}
    state = orch.new_task(TaskRequest(task="Total the amount column per region", files=files))
    run = asyncio.create_task(orch.run(state))
    for _ in range(500):
        await asyncio.sleep(0.01)
        if len(state.sandboxes) == 2:
            break
    assert len(state.sandboxes) == 2, "both VMs are registered while they boot"
    await orch.kill(state, "test")
    receipt = await asyncio.wait_for(run, timeout=20)
    await deps.aclose()
    assert receipt.status == "killed"
    assert all(h.proof and h.proof.destroyed for h in state.sandboxes)


async def test_a_vm_stuck_installing_is_deleted_and_retried():
    """One real VM stayed installingbooting for good while the task waited on it."""
    from brz.orchestrator import TaskRequest
    from brz.vultr.client import VultrTimeout

    deps = build_mock_deps()
    orch = deps.orchestrator
    backend = deps.backend
    real = backend.client.wait_until_active
    calls = []

    async def first_one_sticks(instance_id, **kw):
        calls.append(instance_id)
        if len(calls) == 1:
            raise VultrTimeout("stuck installing")
        return await real(instance_id, **kw)

    backend.client.wait_until_active = first_one_sticks
    orch.config.verify_in_fresh_sandbox = False
    orch.verifier.require_rerun_match = False
    state = orch.new_task(TaskRequest(task="Total the amount column per region", files={"sales.csv": b"region,amount"}))
    await orch.run(state)
    await deps.aclose()
    primaries = [h for h in state.sandboxes if h.role == "primary"]
    assert len(primaries) == 2, "a replacement was created"
    assert all(h.proof and h.proof.destroyed for h in primaries), "the stuck VM is gone too"
    assert "vm.boot_failed" in [e.kind for e in state.audit.events]
