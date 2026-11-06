"""Optional live smoke test against a local OpenAI-compatible server (Ollama by default).

Skipped unless the server answers ``GET /models`` within one second, or when
``BRZ_SKIP_LIVE=1`` (CI). Override with ``BRZ_LIVE_BASE_URL`` / ``BRZ_LIVE_MODEL`` to point it
at Vultr Serverless Inference (``BRZ_LIVE_API_KEY`` for the bearer token).

gemma3:4b on CPU takes ~1 minute per call, so this is one planner call only.
"""

from __future__ import annotations

import os

import httpx
import pytest

from brz.llm import ChatClient, Planner

BASE_URL = os.environ.get("BRZ_LIVE_BASE_URL", "http://localhost:11434/v1")
MODEL = os.environ.get("BRZ_LIVE_MODEL", "gemma3:4b")
API_KEY = os.environ.get("BRZ_LIVE_API_KEY", "")


def _reachable() -> bool:
    if os.environ.get("BRZ_SKIP_LIVE") == "1":
        return False
    try:
        r = httpx.get(
            f"{BASE_URL}/models", timeout=1.0, headers={"Authorization": f"Bearer {API_KEY}"} if API_KEY else {}
        )
        return r.status_code == 200
    except Exception:
        return False


pytestmark = pytest.mark.live


@pytest.mark.skipif(not _reachable(), reason=f"no OpenAI-compatible server at {BASE_URL}")
async def test_live_planner_produces_valid_plan():
    client = ChatClient(BASE_URL, API_KEY, MODEL, timeout=600)
    try:
        planner = Planner(client, max_steps=3)
        res = await planner.plan(
            "Read /work/input/sales.csv (columns: region,amount) and write the total amount per region "
            "to /work/out/summary.json as a JSON object. Print 'done' at the end.",
            budget_usd=0.10,
            allowed_domains=[],
            attachments=["sales.csv"],
        )
    finally:
        await client.aclose()
    plan = res.plan
    assert 1 <= len(plan.steps) <= 3
    assert any(s.kind == "python" for s in plan.steps)
    assert res.usage.total_tokens > 0
    print(
        f"\n[live] model={MODEL} json_schema={res.used_json_schema} steps={len(plan.steps)} "
        f"domains={plan.required_domains} tokens={res.usage.total_tokens}"
    )
