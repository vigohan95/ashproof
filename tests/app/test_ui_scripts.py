"""Every page's inline JavaScript must parse. A syntax error kills the whole page while the server still answers 200."""

from __future__ import annotations

import re
import shutil
import subprocess

import httpx
import pytest

from apps.control_plane.app import create_app
from apps.control_plane.deps import build_mock_deps

NODE = shutil.which("node")
TASK = {"task": "Total the amount column per region and write summary.json", "budget_usd": 0.25, "files": []}


@pytest.mark.skipif(NODE is None, reason="node is not installed")
async def test_inline_scripts_parse(tmp_path):
    app = create_app(build_mock_deps())
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as c:
            tid = (await c.post("/tasks", json=TASK)).json()["id"]
            await app.state.store.wait(tid)
            pages = [
                (await c.get(p)).text
                for p in ("/", "/ui/tasks", "/ui/evidence", "/ui/new", f"/ui/tasks/{tid}", f"/ui/tasks/{tid}/receipt")
            ]
    scripts = [s for page in pages for s in re.findall(r"<script>([\s\S]*?)</script>", page)]
    assert scripts
    for i, source in enumerate(scripts):
        path = tmp_path / f"s{i}.js"
        path.write_text(source, encoding="utf-8")
        result = subprocess.run([NODE, "--check", str(path)], capture_output=True, text=True, timeout=30, check=False)
        assert result.returncode == 0, result.stderr[:600]
