"""End-to-end: CSV task -> plan -> mock Vultr VM -> steps in a local runner -> fresh-sandbox re-run ->
verifier -> secret scan -> VM destroyed (GET 404) -> self-verifying receipt."""

from __future__ import annotations

import base64
import json

import httpx
import pytest
from brz_runner.netlog import StaticEgressReader

from apps.control_plane.app import create_app
from apps.control_plane.deps import build_mock_deps
from brz.audit import Receipt
from brz.vultr.mock import MockVultrState

CSV = b"region,amount\nnorth,10\nsouth,20\nnorth,5\nwest,2.5\n"
DENY_LINE = (
    "2026-11-05T12:00:03+0000 brz kernel: BRZ-EGRESS-DENY IN= OUT=eth0 SRC=10.0.0.5 DST=93.184.216.34 "
    "PROTO=TCP SPT=40000 DPT=443"
)


@pytest.fixture
async def stack(tmp_path):
    state = MockVultrState(activate_after_polls=1)
    deps = build_mock_deps(mock_state=state)
    # primary sandbox "sees" one denied egress attempt (as the nftables log would show); verifier sandbox none
    deps.backend.egress_reader_factory = lambda role: StaticEgressReader([DENY_LINE] if role == "primary" else [])
    deps.backend.workroot = str(tmp_path)
    app = create_app(deps)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://cp") as client:
            yield client, app, state


async def test_csv_task_end_to_end(stack):
    client, app, vultr = stack
    health = (await client.get("/health")).json()
    assert health["ok"] and health["mode"] == "mock" and health["provider"] == "mock-vultr"

    r = await client.post(
        "/tasks",
        json={
            "task": "Total the amount column per region from sales.csv and write summary.json",
            "budget_usd": 0.25,
            "allowed_domains": [],
            "files": [{"name": "sales.csv", "content_b64": base64.b64encode(CSV).decode()}],
        },
    )
    assert r.status_code == 202, r.text
    task_id = r.json()["id"]

    state = await app.state.store.wait(task_id, timeout=120)
    tl = (await client.get(f"/tasks/{task_id}")).json()
    assert tl["status"] == "verified", json.dumps(tl, indent=1)[:3000]

    # --- two throwaway VMs were created through the (mock) Vultr API and both are gone
    created = vultr.calls_for("POST", "/instances")
    assert len(created) == 2
    assert created[0].body["tags"][:3] == ["brz-sandbox", f"task-{task_id}", "role-primary"]
    user_data = base64.b64decode(created[0].body["user_data"]).decode()
    assert user_data.startswith("#cloud-config") and "brz-egress-apply" in user_data
    assert len(vultr.calls_for("DELETE", "/instances/")) == 2
    assert vultr.live_instances() == []
    for sb in tl["sandboxes"]:
        assert sb["destroyed"] is True
        assert (await client.get(f"/tasks/{task_id}")).status_code == 200
    # the proof itself: the API now answers 404 for both ids
    for h in state.sandboxes:
        assert h.proof is not None and h.proof.http_status == 404
    last_gets = [c for c in vultr.calls_for("GET", "/instances/") if c.status == 404]
    assert len(last_gets) >= 2

    # --- steps, verification, scan, egress, cost
    assert [s["exit_code"] for s in tl["steps"]] == [0]
    assert tl["verdict"]["passed"] and tl["verdict"]["rerun_performed"] and tl["verdict"]["rerun_match"] is True
    assert tl["verdict"]["primary_hashes"] == tl["verdict"]["rerun_hashes"]
    assert set(tl["verdict"]["primary_hashes"]) == {"s1/stdout", "s1/file/report.md", "s1/file/summary.json"}
    assert tl["secret_scan"]["clean"] is True
    assert tl["egress"]["attempts"] == 1 and tl["egress"]["denied"] == 1 and len(tl["egress"]["list"]) == 1
    assert tl["cost"]["total_usd"] > 0 and tl["cost"]["vm_usd"] > 0 and not tl["cost"]["over_budget"]
    assert len([ln for ln in tl["cost"]["lines"] if ln["kind"] == "vm"]) == 2
    kinds = [e["kind"] for e in tl["events"]]
    for expected in (
        "task.received",
        "task.planning",
        "plan.created",
        "budget.preflight",
        "task.provisioning",
        "vm.created",
        "vm.runner_ready",
        "task.running",
        "egress.denied",
        "step.finished",
        "task.verifying",
        "verify.verdict",
        "task.scanning",
        "secret_scan.done",
        "task.destroying",
        "vm.destroyed",
        "task.verified",
    ):
        assert expected in kinds, expected
    assert kinds.index("vm.created") < kinds.index("step.finished") < kinds.index("vm.destroyed")
    assert kinds[-1] == "task.verified"

    # --- outputs are served, and are what the sandbox produced
    summary = (await client.get(f"/tasks/{task_id}/outputs/summary.json")).json()
    assert summary["totals_by_group"] == {"north": 15.0, "south": 20.0, "west": 2.5}
    assert (await client.get(f"/tasks/{task_id}/outputs/nope.txt")).status_code == 404

    # --- receipt: JSON validates and self-verifies; Markdown has the containment evidence
    rj = await client.get(f"/tasks/{task_id}/receipt")
    assert rj.status_code == 200
    receipt = Receipt.model_validate(rj.json())
    ok, problems = receipt.verify()
    assert ok, problems
    assert receipt.status == "verified" and receipt.all_vms_destroyed
    assert receipt.audit_chain.ok and receipt.audit_head_hash == tl["audit_head_hash"]
    assert receipt.input_files["sales.csv"] == __import__("hashlib").sha256(CSV).hexdigest()
    assert receipt.egress.denied_count == 1 and receipt.secret_scan.clean
    assert {s.role for s in receipt.sandboxes} == {"primary", "verifier"}
    md = (await client.get(f"/tasks/{task_id}/receipt.md")).text
    assert "GET /v2/instances/{id} -> 404" in md and "All VMs destroyed: **yes**" in md
    assert "DENIED tcp 93.184.216.34:443" in md and "**CLEAN**" in md and "**Verdict:** PASSED" in md
    assert "Receipt integrity:** OK" in md
    md2 = (await client.get(f"/tasks/{task_id}/receipt", params={"format": "md"})).text
    assert md2 == md

    # tampering with the downloaded receipt is detectable offline
    cooked = Receipt.model_validate(rj.json())
    cooked.cost.total_usd = 0.0
    assert cooked.verify()[0] is False
