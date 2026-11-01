"""Control-plane behaviours beyond the happy path: kill switch, approval gate, budget breaker,
verification failure, error paths. All against mock Vultr + FakeLLM + local runner."""

from __future__ import annotations

import asyncio
import base64
import json

import httpx
import pytest

from apps.control_plane.app import create_app
from apps.control_plane.demo import demo_plan, demo_responder
from apps.control_plane.deps import build_mock_deps
from brz.llm import FakeLLM, Planner, Verifier
from brz.vultr.mock import MockVultrState

CSV_B64 = base64.b64encode(b"region,amount\nnorth,1\n").decode()


def _plan_with(**overrides):
    plan = demo_plan("demo", ["sales.csv"])
    plan.update(overrides)
    return plan


def _responder_with_plan(plan: dict):
    def responder(messages):
        last = messages[-1]["content"]
        if last.startswith("Produce the plan"):
            return json.dumps(plan)
        return demo_responder(messages)

    return responder


@pytest.fixture
async def make_stack(tmp_path):
    """Factory: build an app whose planner answers with ``plan`` (demo plan by default); torn down after the test."""
    stacks: list[tuple] = []

    async def _make(plan: dict | None = None, *, verify_fresh: bool = True, verifier_llm=None):
        state = MockVultrState(activate_after_polls=1)
        deps = build_mock_deps(mock_state=state, verify_fresh=verify_fresh)
        deps.backend.workroot = str(tmp_path)
        if plan is not None:
            deps.orchestrator.planner = Planner(FakeLLM(_responder_with_plan(plan), model="demo-fake-llm"))
        if verifier_llm is not None:
            deps.orchestrator.verifier = Verifier(verifier_llm)
        app = create_app(deps)
        cm = app.router.lifespan_context(app)
        await cm.__aenter__()
        client = httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://cp")
        stacks.append((cm, client))
        return client, app, state

    yield _make

    for cm, client in stacks:
        await client.aclose()
        await cm.__aexit__(None, None, None)


async def _submit(client: httpx.AsyncClient, **kw) -> str:
    body = {
        "task": "Summarise sales.csv",
        "budget_usd": 0.25,
        "allowed_domains": [],
        "files": [{"name": "sales.csv", "content_b64": CSV_B64}],
    }
    body.update(kw)
    r = await client.post("/tasks", json=body)
    assert r.status_code == 202, r.text
    return r.json()["id"]


async def _wait_status(client: httpx.AsyncClient, task_id: str, *statuses: str, timeout: float = 30.0) -> dict:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        tl = (await client.get(f"/tasks/{task_id}")).json()
        if tl["status"] in statuses:
            return tl
        if asyncio.get_running_loop().time() > deadline:
            raise AssertionError(
                f"task stuck in {tl['status']}, wanted {statuses}; events={[e['kind'] for e in tl['events']]}"
            )
        await asyncio.sleep(0.05)


async def test_unknown_task_and_not_ready_receipt(make_stack):
    client, app, _ = await make_stack()
    assert (await client.get("/tasks/nope")).status_code == 404
    assert (await client.post("/tasks/nope/kill")).status_code == 404
    assert (await client.get("/tasks/nope/receipt")).status_code == 404
    r = await client.post("/tasks", json={"task": "x"})  # too short
    assert r.status_code == 422
    r = await client.post("/tasks", json={"task": "valid task", "files": [{"name": "a.csv", "content_b64": "!!!"}]})
    assert r.status_code == 400
    assert (await client.get("/tasks")).json()["tasks"] == []


async def test_kill_switch_mid_step_destroys_vm_and_receipts_it(make_stack):
    slow = _plan_with(
        steps=[
            {
                "id": "s1",
                "title": "slow",
                "kind": "python",
                "code": "import time\nprint('start', flush=True)\ntime.sleep(30)\n",
                "expected_outputs": [],
                "needs_network": False,
                "timeout_s": 120,
            }
        ],
        assertions=[],
    )
    client, app, vultr = await make_stack(slow)
    task_id = await _submit(client)
    tl = await _wait_status(client, task_id, "running")
    primary = tl["sandboxes"][0]["instance_id"]
    # give the step a moment to actually start inside the runner
    await asyncio.sleep(0.5)

    r = await client.post(f"/tasks/{task_id}/kill", json={"reason": "operator pressed the button"})
    assert r.status_code == 200 and r.json()["killed"] is True
    assert r.json()["sandboxes"] == [{"instance_id": primary, "destroyed": True}]

    tl = await _wait_status(client, task_id, "killed")
    kinds = [e["kind"] for e in tl["events"]]
    assert "kill.requested" in kinds and "kill.tokens_revoked" in kinds and "vm.destroyed" in kinds
    assert kinds[-1] == "task.killed"
    assert vultr.live_instances() == []
    assert tl["verdict"] is None and tl["cost"]["vm_usd"] > 0
    receipt = (await client.get(f"/tasks/{task_id}/receipt")).json()
    assert receipt["status"] == "killed" and receipt["sandboxes"][0]["proof_of_destruction"]["http_status"] == 404
    md = (await client.get(f"/tasks/{task_id}/receipt.md")).text
    assert "**Status:** KILLED" in md and "All VMs destroyed: **yes**" in md
    # a second kill is a no-op
    r = await client.post(f"/tasks/{task_id}/kill")
    assert r.json()["killed"] is False


async def test_approval_gate_grants_then_runs(make_stack):
    plan = _plan_with(required_domains=["pypi.org"])
    client, app, vultr = await make_stack(plan)
    task_id = await _submit(client)
    tl = await _wait_status(client, task_id, "awaiting_approval")
    assert tl["pending_domains"] == ["pypi.org"] and vultr.calls_for("POST", "/instances") == []  # no VM yet

    r = await client.post(f"/tasks/{task_id}/approve", json={"approved": True})
    assert r.status_code == 200 and r.json()["domains"] == ["pypi.org"]
    tl = await _wait_status(client, task_id, "verified", "failed", "error", timeout=60)
    assert tl["status"] == "verified", tl["error"]
    assert tl["allowed_domains"] == ["pypi.org"]
    created = vultr.calls_for("POST", "/instances")[0]
    user_data = base64.b64decode(created.body["user_data"]).decode()
    assert "\n      pypi.org\n" in user_data  # approved domain reached the sandbox allowlist
    kinds = [e["kind"] for e in tl["events"]]
    assert "task.awaiting_approval" in kinds and "approval.granted" in kinds
    assert (await client.post(f"/tasks/{task_id}/approve", json={"approved": True})).status_code == 409


async def test_approval_gate_rejects(make_stack):
    plan = _plan_with(required_domains=["evil.example"])
    client, app, vultr = await make_stack(plan)
    task_id = await _submit(client)
    await _wait_status(client, task_id, "awaiting_approval")
    await client.post(f"/tasks/{task_id}/approve", json={"approved": False})
    tl = await _wait_status(client, task_id, "failed")
    assert "rejected" in tl["error"] and vultr.calls_for("POST", "/instances") == []
    receipt = (await client.get(f"/tasks/{task_id}/receipt")).json()
    assert receipt["status"] == "failed" and receipt["sandboxes"] == []


async def test_kill_while_awaiting_approval(make_stack):
    plan = _plan_with(required_domains=["pypi.org"])
    client, app, vultr = await make_stack(plan)
    task_id = await _submit(client)
    await _wait_status(client, task_id, "awaiting_approval")
    await client.post(f"/tasks/{task_id}/kill")
    tl = await _wait_status(client, task_id, "killed")
    assert vultr.calls_for("POST", "/instances") == [] and tl["status"] == "killed"


async def test_budget_breaker_refuses_before_any_vm(make_stack):
    client, app, vultr = await make_stack()
    task_id = await _submit(client, budget_usd=0.001)  # cheaper than one started VM hour
    tl = await _wait_status(client, task_id, "failed")
    assert "exceeds budget" in tl["error"]
    assert vultr.calls_for("POST", "/instances") == []
    kinds = [e["kind"] for e in tl["events"]]
    assert "budget.preflight" in kinds and "vm.created" not in kinds


async def test_verification_fails_when_reruns_differ(make_stack):
    nondeterministic = _plan_with(
        steps=[
            {
                "id": "s1",
                "title": "random",
                "kind": "python",
                "code": (
                    "import os, random\n"
                    "open(os.path.join(os.environ['BRZ_OUT'], 'r.txt'), 'w').write(str(random.random()))\n"
                    "print('ok')\n"
                ),
                "expected_outputs": ["r.txt"],
                "needs_network": False,
                "timeout_s": 60,
            }
        ],
        assertions=["file_exists:r.txt"],
    )
    client, app, vultr = await make_stack(nondeterministic)
    task_id = await _submit(client)
    tl = await _wait_status(client, task_id, "failed", "verified", timeout=60)
    assert tl["status"] == "failed"
    assert tl["verdict"]["passed"] is False and tl["verdict"]["rerun_match"] is False
    failed = [c["name"] for c in tl["verdict"]["checks"] if not c["passed"]]
    assert failed == ["rerun:hashes_identical"]
    assert vultr.live_instances() == [] and len(vultr.calls_for("POST", "/instances")) == 2
    md = (await client.get(f"/tasks/{task_id}/receipt.md")).text
    assert "**Verdict:** FAILED" in md and "s1/file/r.txt" in md


async def test_step_failure_is_repaired_once_then_fails(make_stack):
    broken = _plan_with(
        steps=[
            {
                "id": "s1",
                "title": "broken",
                "kind": "python",
                "code": "raise SystemExit(7)\n",
                "expected_outputs": [],
                "needs_network": False,
                "timeout_s": 60,
            }
        ],
        assertions=[],
    )
    client, app, vultr = await make_stack(broken, verify_fresh=False)
    task_id = await _submit(client)
    tl = await _wait_status(client, task_id, "failed")
    assert "exit code 7" in tl["error"]
    kinds = [e["kind"] for e in tl["events"]]
    assert kinds.count("step.finished") == 2 and "step.repaired" in kinds  # one repair attempt, same failure
    assert tl["steps"][0]["attempts"] == 2 and tl["steps"][0]["repaired"] is True
    assert vultr.live_instances() == []


async def test_deterministic_only_mode_requires_no_second_vm(make_stack):
    client, app, vultr = await make_stack(verify_fresh=False, verifier_llm=None)
    deps = app.state.deps
    deps.orchestrator.verifier = Verifier(None, require_rerun_match=False)
    task_id = await _submit(client)
    tl = await _wait_status(client, task_id, "verified", "failed", timeout=60)
    assert tl["status"] == "verified" and len(vultr.calls_for("POST", "/instances")) == 1
    assert tl["verdict"]["rerun_performed"] is False and tl["verdict"]["verifier_model"] == "deterministic-only"
