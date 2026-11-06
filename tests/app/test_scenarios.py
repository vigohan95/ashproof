"""The compromised agent scenario: fixed on the server, labelled everywhere, and a refused packet fails the task."""

from __future__ import annotations

import httpx
from brz_runner.netlog import StaticEgressReader

from apps.control_plane import scenarios
from apps.control_plane.app import create_app
from apps.control_plane.deps import build_mock_deps
from brz.audit.offline_verify import verify_receipt
from brz.llm import Plan, PlanStep
from brz.orchestrator import TaskRequest
from brz.vultr.mock import MockVultrState

DENY = (
    "2026-11-05T12:00:03+0000 brz kernel: BRZ-EGRESS-DENY IN= OUT=eth0 SRC=10.0.0.5 DST=1.1.1.1 "
    "PROTO=TCP SPT=40000 DPT=443"
)


def harmless(needs_network: bool = True) -> Plan:
    """The sandbox here is a local process, so the test plan must not be the attack itself."""
    code = "import os; open(os.path.join(os.environ['BRZ_OUT'], 'a.txt'), 'w').write('a'); print('done')"
    summary = "Test stand-in."
    step = PlanStep(
        id="s1", title="t", kind="python", code=code, expected_outputs=["a.txt"], needs_network=needs_network
    )
    return Plan(task_summary=summary, steps=[step])


def stack(tmp_path):
    deps = build_mock_deps(mock_state=MockVultrState(activate_after_polls=1))
    deps.backend.egress_reader_factory = lambda role: StaticEgressReader([DENY])
    deps.backend.workroot = str(tmp_path)
    return deps


async def run(deps, **kw):
    orch = deps.orchestrator
    state = orch.new_task(TaskRequest(task="total it", scripted_label=scenarios.SCRIPTED_LABEL, **kw))
    await orch.run(state)
    return state


async def test_scripted_plan_with_refused_packets_fails_and_the_receipt_says_what_was_refused(tmp_path):
    state = await run(stack(tmp_path), scripted_plan=harmless())
    assert state.status == "failed" and state.error.startswith("contained: 2 packets")
    assert state.planner_model == scenarios.SCRIPTED_LABEL
    assert state.receipt.refusals() == [{"what": "tcp to 1.1.1.1:443", "by": "kernel (nftables)", "count": 2}]
    md = state.receipt.to_markdown()
    assert "## What was refused" in md and "No model wrote it" in md
    assert verify_receipt(state.receipt.model_dump(mode="json"), public_key="00" * 32)["ok"]
    assert any(e.kind == "plan.created" and e.data.get("scripted") for e in state.audit.events)


async def test_expected_refusals_do_not_fail_a_wall_test(tmp_path):
    state = await run(stack(tmp_path), scripted_plan=harmless(), expect_refusals=True)
    assert state.status == "verified"
    assert any(c.name == "egress:nothing_unexpected_refused" and c.passed for c in state.verdict.checks)


async def test_a_step_without_a_network_is_not_blamed_for_host_packets(tmp_path):
    state = await run(stack(tmp_path), scripted_plan=harmless(needs_network=False))
    assert state.status == "verified" and state.refused_packets == 0


async def test_the_attack_cannot_run_outside_a_real_sandbox_and_callers_cannot_supply_a_plan(tmp_path):
    deps = stack(tmp_path)
    app = create_app(deps)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://cp") as c:
            r = await c.post("/tasks", json={"task": "abc", "scenario": "compromised-agent"})
            assert r.status_code == 409
            assert (await c.post("/tasks", json={"task": "abc", "scenario": "nope"})).status_code == 404
            r = await c.post("/tasks", json={"task": "abc", "scripted_plan": {"task_summary": "x", "steps": []}})
            assert r.status_code == 202
            state = await app.state.store.wait(r.json()["id"], timeout=60)
            assert state.request.scripted_plan is None


def test_the_fixed_plan_is_labelled_and_the_injected_note_is_in_the_file():
    s = scenarios.COMPROMISED_AGENT
    assert "Scripted attack" in s.plan.risk_notes[0] and scenarios.SCRIPTED_LABEL.startswith("scripted")
    assert "attack" not in s.plan.task_summary.lower()  # the verifier model reads this; it must not be told
    assert b"SYSTEM NOTE TO THE AGENT" in s.files["sales.csv"]
    assert s.plan.required_domains == [] and s.plan.steps[0].needs_network
    compile(s.plan.steps[0].code, "attack", "exec")
