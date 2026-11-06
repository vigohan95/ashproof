"""Behaviour observed against the real Serverless Inference API on 2026-11-06, pinned so it cannot regress."""

from __future__ import annotations

import httpx
import pytest

from brz.cost.prices import LivePriceTable
from brz.llm import ChatClient
from brz.llm.client import LLMError, parse_chat_response
from brz.llm.planner import Plan
from brz.llm.structured import StructuredOutputError, structured

MODEL_ENTRY = {
    "id": "glm-5.3",
    "input_modalities": [
        {"type": "text", "pricing": [{"type": "prompt", "unit": "token", "cost_usd": "0.00000075"}]},
        {"type": "image", "supported_inputs": {}},
    ],
    "output_modalities": [
        {"type": "text", "pricing": [{"type": "completion", "unit": "token", "cost_usd": "0.000003"}]},
    ],
}


def completion(content: str, finish: str = "stop", reasoning: str = "") -> dict:
    msg = {"role": "assistant", "content": content}
    if reasoning:
        msg["reasoning_content"] = reasoning
    return {
        "model": "m",
        "choices": [{"message": msg, "finish_reason": finish}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 20},
    }


def test_live_prices_read_the_real_model_shape():
    table = LivePriceTable.from_payloads([{"id": "vc2-1c-1gb", "hourly_cost": 0.007}], [MODEL_ENTRY])
    price = table.token_price("glm-5.3")
    assert price.input_per_1m == pytest.approx(0.75)
    assert price.output_per_1m == pytest.approx(3.0)
    assert table.vm_hourly("vc2-1c-1gb") == pytest.approx(0.007)


def test_reasoning_is_kept_apart_from_the_answer():
    res = parse_chat_response(completion("answer", reasoning="thinking"))
    assert res.content == "answer"
    assert res.reasoning == "thinking"


async def test_reasoning_effort_is_sent_and_429_is_retried():
    seen: list[dict] = []
    replies = iter([httpx.Response(429, json={}), httpx.Response(200, json=completion("ok"))])

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        seen.append(json.loads(request.content))
        return next(replies)

    client = ChatClient(
        "http://x/v1", "k", "m", transport=httpx.MockTransport(handler), reasoning_effort="low", backoff_base=0
    )
    res = await client.chat([{"role": "user", "content": "hi"}])
    await client.aclose()
    assert res.content == "ok"
    assert len(seen) == 2
    assert seen[0]["reasoning_effort"] == "low"


async def test_retries_stop_and_the_error_surfaces():
    client = ChatClient(
        "http://x/v1",
        "k",
        "m",
        transport=httpx.MockTransport(lambda r: httpx.Response(503, text="busy")),
        max_retries=1,
        backoff_base=0,
    )
    with pytest.raises(LLMError):
        await client.chat([{"role": "user", "content": "hi"}])
    await client.aclose()


async def test_budget_spent_on_reasoning_is_reported_not_crashed():
    """qwen3.8-27b at default effort: finish_reason=length, no content."""
    client = ChatClient(
        "http://x/v1",
        "k",
        "m",
        transport=httpx.MockTransport(lambda r: httpx.Response(200, json=completion("", "length", "thinking"))),
    )
    with pytest.raises(StructuredOutputError) as err:
        await structured(client, [{"role": "user", "content": "plan"}], Plan)
    await client.aclose()
    assert "length" in str(err.value)
