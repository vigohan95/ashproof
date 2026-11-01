"""FakeLLM: deterministic stand-in for tests and the offline demo.

Responses can be a list of strings (consumed in order), a callable that receives the
message list and returns a string, or a dict keyed by a substring found in the last
user message. ``reject_json_schema=True`` makes it behave like Ollama/gemma3 (HTTP 400
on ``response_format``), which exercises the plain-JSON fallback path.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from .client import ChatResult, UnsupportedResponseFormat, Usage

Responder = list[str] | Callable[[list[dict[str, Any]]], str] | dict[str, str]


class FakeLLM:
    def __init__(
        self,
        responses: Responder | None = None,
        *,
        model: str = "fake-llm",
        reject_json_schema: bool = False,
        prompt_tokens: int = 120,
        completion_tokens: int = 40,
        delay: float = 0.0,
    ):
        self.model = model
        self.reject_json_schema = reject_json_schema
        self.calls: list[dict[str, Any]] = []
        self._responses = responses if responses is not None else ["{}"]
        self._index = 0
        self._usage = (prompt_tokens, completion_tokens)
        self.delay = delay

    @staticmethod
    def json(obj: Any) -> str:
        return json.dumps(obj, ensure_ascii=False)

    def _next(self, messages: list[dict[str, Any]]) -> str:
        r = self._responses
        if callable(r):
            return r(messages)
        if isinstance(r, dict):
            last_user = next((m["content"] for m in reversed(messages) if m.get("role") == "user"), "")
            for key, val in r.items():
                if key in str(last_user):
                    return val
            raise AssertionError(f"FakeLLM has no response for: {str(last_user)[:200]}")
        if self._index >= len(r):
            raise AssertionError(f"FakeLLM ran out of responses after {self._index} calls")
        out = r[self._index]
        self._index += 1
        return out

    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        response_format: dict[str, Any] | None = None,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> ChatResult:
        if self.delay:
            import asyncio

            await asyncio.sleep(self.delay)
        self.calls.append({"messages": messages, "response_format": response_format, "tools": tools})
        if response_format is not None and self.reject_json_schema:
            raise UnsupportedResponseFormat("fake server: response_format not supported", 400)
        content = self._next(messages)
        return ChatResult(
            content=content,
            model=self.model,
            usage=Usage(prompt_tokens=self._usage[0], completion_tokens=self._usage[1]),
            finish_reason="stop",
        )
