"""Minimal OpenAI-compatible chat client.

Works against Vultr Serverless Inference (``https://api.vultrinference.com/v1``), a local
Ollama (``http://localhost:11434/v1``) or anything else that speaks ``/chat/completions``.
Only what we use: non-streaming chat, optional ``response_format``, optional ``tools``,
usage accounting. No SDK dependency; httpx only.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

import httpx
from pydantic import BaseModel, Field

VULTR_INFERENCE_BASE_URL = "https://api.vultrinference.com/v1"


class Usage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens


class ChatResult(BaseModel):
    content: str
    model: str = ""
    usage: Usage = Field(default_factory=Usage)
    finish_reason: str = ""
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    raw: dict[str, Any] = Field(default_factory=dict)


class LLMError(Exception):
    def __init__(self, message: str, status: int | None = None, body: Any = None):
        super().__init__(message)
        self.status = status
        self.body = body


class UnsupportedResponseFormat(LLMError):
    """The server rejected ``response_format`` (HTTP 400/422) - caller should fall back."""


@runtime_checkable
class LLM(Protocol):
    """What Planner / Verifier / structured() depend on. ChatClient and FakeLLM both satisfy it."""

    model: str

    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        response_format: dict[str, Any] | None = None,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> ChatResult: ...


class ChatClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        *,
        timeout: float = 120.0,
        transport: httpx.AsyncBaseTransport | None = None,
        extra_headers: dict[str, str] | None = None,
    ):
        self.model = model
        self.base_url = base_url.rstrip("/")
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        if extra_headers:
            headers.update(extra_headers)
        self._http = httpx.AsyncClient(base_url=self.base_url, headers=headers, timeout=timeout, transport=transport)

    async def aclose(self) -> None:
        await self._http.aclose()

    async def list_models(self) -> list[str]:
        resp = await self._http.get("/models")
        resp.raise_for_status()
        return [m.get("id", "") for m in resp.json().get("data", [])]

    async def chat(
        self,
        messages: list[dict[str, Any]],
        *,
        response_format: dict[str, Any] | None = None,
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> ChatResult:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }
        if response_format is not None:
            body["response_format"] = response_format
        if tools:
            body["tools"] = tools
        if max_tokens is not None:
            body["max_tokens"] = max_tokens
        try:
            resp = await self._http.post("/chat/completions", json=body)
        except httpx.TransportError as exc:
            raise LLMError(f"chat transport error: {exc!r}") from exc
        if resp.status_code in (400, 422) and response_format is not None:
            raise UnsupportedResponseFormat(f"server rejected response_format: {resp.text[:300]}", resp.status_code)
        if resp.status_code >= 400:
            raise LLMError(f"chat HTTP {resp.status_code}: {resp.text[:300]}", resp.status_code, resp.text)
        data = resp.json()
        return parse_chat_response(data, default_model=self.model)


def parse_chat_response(data: dict[str, Any], default_model: str = "") -> ChatResult:
    choices = data.get("choices") or []
    if not choices:
        raise LLMError("chat response had no choices", body=data)
    msg = choices[0].get("message") or {}
    content = msg.get("content") or ""
    if isinstance(content, list):  # some servers return content parts
        content = "".join(part.get("text", "") for part in content if isinstance(part, dict))
    usage = data.get("usage") or {}
    return ChatResult(
        content=content,
        model=data.get("model") or default_model,
        usage=Usage(
            prompt_tokens=int(usage.get("prompt_tokens") or 0),
            completion_tokens=int(usage.get("completion_tokens") or 0),
        ),
        finish_reason=choices[0].get("finish_reason") or "",
        tool_calls=list(msg.get("tool_calls") or []),
        raw=data,
    )
