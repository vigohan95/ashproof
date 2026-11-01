from __future__ import annotations

import httpx
import pytest
from pydantic import BaseModel

from brz.llm import ChatClient, FakeLLM, StructuredOutputError, UnsupportedResponseFormat, extract_json, structured


class Answer(BaseModel):
    city: str
    population: int


def test_extract_json_variants():
    assert extract_json('{"a": 1}') == {"a": 1}
    assert extract_json('Sure! Here it is:\n```json\n{"a": 1}\n```\nhope that helps') == {"a": 1}
    assert extract_json('prefix text {"a": {"b": [1, 2]}, "s": "x } y"} trailing') == {"a": {"b": [1, 2]}, "s": "x } y"}
    assert extract_json("list: [1, 2, 3] done") == [1, 2, 3]
    assert extract_json('{"a": 1} {"b": 2}') == {"a": 1}
    with pytest.raises(ValueError):
        extract_json("no json here at all")
    with pytest.raises(ValueError):
        extract_json("{broken json")


async def test_json_schema_path_is_preferred():
    llm = FakeLLM([FakeLLM.json({"city": "Seattle", "population": 750000})])
    res = await structured(llm, [{"role": "user", "content": "Biggest city in WA?"}], Answer)
    assert res.value == Answer(city="Seattle", population=750000)
    assert res.used_json_schema is True and res.rounds == 1
    rf = llm.calls[0]["response_format"]
    assert rf["type"] == "json_schema" and rf["json_schema"]["name"] == "Answer"
    assert "city" in rf["json_schema"]["schema"]["properties"]
    assert res.usage.prompt_tokens == 120 and res.usage.completion_tokens == 40


async def test_fallback_when_server_rejects_response_format():
    """Ollama/gemma3 behaviour: 400 on response_format -> re-ask with JSON-only instruction, parse prose."""
    llm = FakeLLM(['Here you go:\n```json\n{"city": "Seattle", "population": 750000}\n```'], reject_json_schema=True)
    res = await structured(llm, [{"role": "user", "content": "Biggest city in WA?"}], Answer)
    assert res.value.city == "Seattle"
    assert res.used_json_schema is False
    assert len(llm.calls) == 2
    assert llm.calls[0]["response_format"] is not None
    assert llm.calls[1]["response_format"] is None
    assert "Respond with a single JSON object only" in llm.calls[1]["messages"][0]["content"]
    assert res.usage.prompt_tokens == 120  # the rejected call cost nothing (it never ran)


async def test_repair_round_fixes_validation_error():
    llm = FakeLLM(
        [
            FakeLLM.json({"city": "Seattle", "population": "lots"}),  # invalid int
            FakeLLM.json({"city": "Seattle", "population": 750000}),
        ]
    )
    res = await structured(llm, [{"role": "user", "content": "q"}], Answer)
    assert res.value.population == 750000 and res.rounds == 2
    repair_prompt = llm.calls[1]["messages"][-1]["content"]
    assert "That was not valid" in repair_prompt and "population" in repair_prompt
    assert res.usage.prompt_tokens == 240


async def test_gives_up_after_max_repairs():
    llm = FakeLLM(["nonsense", "still nonsense", "and again"])
    with pytest.raises(StructuredOutputError) as exc:
        await structured(llm, [{"role": "user", "content": "q"}], Answer, max_repairs=2)
    assert len(exc.value.attempts) == 3


async def test_prefer_schema_false_skips_json_schema():
    llm = FakeLLM([FakeLLM.json({"city": "X", "population": 1})])
    res = await structured(llm, [{"role": "user", "content": "q"}], Answer, prefer_schema=False)
    assert res.used_json_schema is False and llm.calls[0]["response_format"] is None


async def test_chat_client_against_fake_openai_server():
    """ChatClient wire format: Bearer auth, /chat/completions body, usage parsing, 400 on response_format."""
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        import json

        seen["auth"] = request.headers.get("authorization")
        seen["body"] = json.loads(request.content)
        if request.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "glm-5.3"}]})
        if "response_format" in seen["body"] and seen["body"]["model"] == "no-schema-model":
            return httpx.Response(400, json={"error": "response_format unsupported"})
        return httpx.Response(
            200,
            json={
                "id": "x",
                "model": seen["body"]["model"],
                "choices": [
                    {"index": 0, "message": {"role": "assistant", "content": '{"ok": true}'}, "finish_reason": "stop"}
                ],
                "usage": {"prompt_tokens": 11, "completion_tokens": 3, "total_tokens": 14},
            },
        )

    transport = httpx.MockTransport(handler)
    client = ChatClient("https://api.vultrinference.com/v1", "SECRET", "glm-5.3", transport=transport)
    res = await client.chat([{"role": "user", "content": "hi"}], response_format={"type": "json_object"})
    assert seen["auth"] == "Bearer SECRET"
    assert seen["body"]["messages"][0]["content"] == "hi" and seen["body"]["stream"] is False
    assert res.content == '{"ok": true}' and res.usage.prompt_tokens == 11 and res.usage.completion_tokens == 3
    await client.aclose()

    strict = ChatClient("http://localhost:11434/v1", "", "no-schema-model", transport=transport)
    with pytest.raises(UnsupportedResponseFormat):
        await strict.chat([{"role": "user", "content": "hi"}], response_format={"type": "json_object"})
    assert "authorization" not in {k.lower() for k in strict._http.headers}  # no key -> no header
    await strict.aclose()
