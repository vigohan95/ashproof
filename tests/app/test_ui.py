"""UI tests: pages render in mock mode, approval flow through the UI-visible API, kill flow, receipt page."""

from __future__ import annotations

import asyncio
import base64
import json

import httpx
import pytest

from apps.control_plane.app import create_app
from apps.control_plane.demo import demo_plan, demo_responder
from apps.control_plane.deps import build_mock_deps
from apps.control_plane.ui import markdown_to_html
from brz.llm import FakeLLM, Planner
from brz.vultr.mock import MockVultrState

CSV_B64 = base64.b64encode(b"region,amount\nnorth,1\nsouth,2\n").decode()


@pytest.fixture
async def ui(tmp_path):
    state = MockVultrState(activate_after_polls=1)
    deps = build_mock_deps(mock_state=state)
    deps.backend.workroot = str(tmp_path)
    app = create_app(deps)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://cp") as client:
            yield client, app, deps


async def _submit(client, **kw) -> str:
    body = {
        "task": "Summarise sales.csv per region",
        "budget_usd": 0.25,
        "files": [{"name": "sales.csv", "content_b64": CSV_B64}],
    }
    body.update(kw)
    r = await client.post("/tasks", json=body)
    assert r.status_code == 202, r.text
    return r.json()["id"]


async def _wait(client, task_id, *statuses, timeout=30.0):
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while True:
        tl = (await client.get(f"/tasks/{task_id}")).json()
        if tl["status"] in statuses:
            return tl
        assert loop.time() < deadline, f"stuck in {tl['status']}"
        await asyncio.sleep(0.05)


async def test_pages_render_and_receipt_page(ui):
    client, app, deps = ui
    r = await client.get("/", follow_redirects=False)
    assert r.status_code == 307 and r.headers["location"] == "/ui"
    r = await client.get("/ui")
    assert r.status_code == 200 and "No tasks yet" in r.text and "mode <strong>mock</strong>" in r.text
    r = await client.get("/ui/new")
    assert r.status_code == 200 and 'id="require_approval"' in r.text and "Budget (USD)" in r.text
    assert (await client.get("/ui/tasks/nope")).status_code == 404

    task_id = await _submit(client)
    r = await client.get(f"/ui/tasks/{task_id}")
    assert r.status_code == 200
    assert "KILL SWITCH" in r.text and f'const TASK_ID = "{task_id}"' in r.text and "Approve these domains" in r.text
    # receipt not ready yet -> 409 on both API and page
    tl = await _wait(client, task_id, "verified")
    assert tl["sandboxes"][0]["proof"]["http_status"] == 404 and tl["sandboxes"][0]["proof"]["observed_at"]
    assert "list" in tl["egress"]

    r = await client.get("/ui")
    assert task_id in r.text and "badge verified" in r.text and '<span class="ok">yes</span>' in r.text
    r = await client.get(f"/ui/tasks/{task_id}/receipt")
    assert r.status_code == 200
    assert "CHAIN VERIFIED" in r.text and "VMs DESTROYED" in r.text and "NO SECRETS" in r.text
    assert "GET /v2/instances/{id} -&gt; 404" in r.text or "GET /v2/instances/{id} -> 404" in r.text
    assert "<table>" in r.text and "Ashproof receipt" in r.text
    assert f'download="receipt-{task_id}.json"' in r.text
    v = (await client.get(f"/tasks/{task_id}/receipt/verify")).json()
    assert v["ok"] is True and v["problems"] == [] and v["events"] > 10


async def test_ui_approval_flow(ui):
    client, app, deps = ui
    plan = demo_plan("demo", ["sales.csv"]) | {"required_domains": ["pypi.org"]}

    def responder(messages):
        last = messages[-1]["content"]
        return json.dumps(plan) if last.startswith("Produce the plan") else demo_responder(messages)

    deps.orchestrator.planner = Planner(FakeLLM(responder, model="demo-fake-llm"))
    task_id = await _submit(client)
    tl = await _wait(client, task_id, "awaiting_approval")
    assert tl["pending_domains"] == ["pypi.org"] and tl["require_approval"] is True
    page = (await client.get(f"/ui/tasks/{task_id}")).text
    assert 'class="badge awaiting_approval"' in page
    r = await client.post(f"/tasks/{task_id}/approve", json={"approved": True})
    assert r.status_code == 200
    tl = await _wait(client, task_id, "verified", "failed", timeout=60)
    assert tl["status"] == "verified" and tl["allowed_domains"] == ["pypi.org"]

    # the UI toggle: require_approval=false skips the gate entirely
    task2 = await _submit(client, require_approval=False)
    tl2 = await _wait(client, task2, "verified", "failed", timeout=60)
    kinds = [e["kind"] for e in tl2["events"]]
    assert "approval.auto" in kinds and "task.awaiting_approval" not in kinds and tl2["status"] == "verified"


async def test_ui_kill_flow(ui):
    client, app, deps = ui
    plan = demo_plan("demo", ["sales.csv"])
    plan["steps"][0]["code"] = "import time\nprint('start', flush=True)\ntime.sleep(30)\n"
    plan["steps"][0]["expected_outputs"] = []
    plan["assertions"] = []

    def responder(messages):
        last = messages[-1]["content"]
        return json.dumps(plan) if last.startswith("Produce the plan") else demo_responder(messages)

    deps.orchestrator.planner = Planner(FakeLLM(responder, model="demo-fake-llm"))
    task_id = await _submit(client)
    await _wait(client, task_id, "running")
    await asyncio.sleep(0.4)
    r = await client.post(f"/tasks/{task_id}/kill", json={"reason": "kill switch pressed in UI"})
    assert r.status_code == 200 and r.json()["killed"] is True
    tl = await _wait(client, task_id, "killed")
    assert tl["kill_requested"] is True and all(s["destroyed"] for s in tl["sandboxes"])
    page = (await client.get(f"/ui/tasks/{task_id}/receipt")).text
    assert "badge killed" in page and "CHAIN VERIFIED" in page and "VMs DESTROYED" in page
    listing = (await client.get("/ui")).text
    assert "badge killed" in listing


def test_markdown_subset_renderer():
    md = (
        "# Title\n\n- **Bold** item `code`\n  - [x] nested ok\n  - [ ] nested bad\n\n"
        "| a | b |\n|---|---|\n| 1 | DENIED |\n\nplain <script>\n"
    )
    html = markdown_to_html(md)
    assert "<h1>Title</h1>" in html
    assert "<strong>Bold</strong>" in html and "<code>code</code>" in html
    assert '<span class="ok">' in html and '<span class="bad">' in html
    assert '<tr class="deny">' in html and "<th>a</th>" in html
    assert "&lt;script&gt;" in html and "<script>" not in html
