"""Structured output: ``response_format: json_schema`` first, plain-JSON prompting as fallback.

Vultr Serverless Inference models advertise ``response_format: json_schema``; Ollama with
gemma3:4b does not (and has no tool calling), so every structured call in Ashproof goes through
:func:`structured` which:

1. tries ``response_format={"type": "json_schema", ...}``,
2. on ``UnsupportedResponseFormat`` (or when ``prefer_schema=False``) re-asks with an
   explicit "respond with JSON only" instruction,
3. extracts the first JSON object from the reply (code fences, prose around it, trailing
   commentary are all tolerated),
4. validates with the pydantic model; on failure sends the validation error back once
   and retries ("repair" round).

Every call returns the parsed model plus the usage of ALL rounds so the cost meter sees
the real token spend.
"""

from __future__ import annotations

import json
import re
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ValidationError

from .client import LLM, ChatResult, UnsupportedResponseFormat, Usage

T = TypeVar("T", bound=BaseModel)

_FENCE_RE = re.compile(r"```(?:json|JSON)?\s*(.*?)```", re.DOTALL)


class StructuredOutputError(Exception):
    def __init__(self, message: str, attempts: list[ChatResult]):
        super().__init__(message)
        self.attempts = attempts


class StructuredResult(BaseModel, Generic[T]):
    value: T
    usage: Usage
    rounds: int
    used_json_schema: bool
    raw_text: str


def extract_json(text: str) -> Any:
    """Pull the first JSON value out of free-form model text. Raises ValueError if none."""
    text = text.strip()
    # 1. whole thing is JSON
    try:
        return json.loads(text)
    except ValueError:
        pass
    # 2. fenced block(s)
    for m in _FENCE_RE.finditer(text):
        try:
            return json.loads(m.group(1).strip())
        except ValueError:
            continue
    # 3. first balanced {...} or [...] in the text
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        while start != -1:
            depth = 0
            in_str = False
            esc = False
            for i in range(start, len(text)):
                ch = text[i]
                if in_str:
                    if esc:
                        esc = False
                    elif ch == "\\":
                        esc = True
                    elif ch == '"':
                        in_str = False
                    continue
                if ch == '"':
                    in_str = True
                elif ch == opener:
                    depth += 1
                elif ch == closer:
                    depth -= 1
                    if depth == 0:
                        candidate = text[start : i + 1]
                        try:
                            return json.loads(candidate)
                        except ValueError:
                            break
            start = text.find(opener, start + 1)
    raise ValueError("no JSON value found in model output")


def json_schema_response_format(model: type[BaseModel], name: str | None = None, strict: bool = True) -> dict:
    schema = model.model_json_schema()
    return {
        "type": "json_schema",
        "json_schema": {"name": name or model.__name__, "schema": schema, "strict": strict},
    }


def _schema_instruction(model: type[BaseModel]) -> str:
    return (
        "Respond with a single JSON object only - no prose, no markdown fences. "
        "It must validate against this JSON Schema:\n" + json.dumps(model.model_json_schema(), ensure_ascii=False)
    )


async def structured(
    llm: LLM,
    messages: list[dict[str, Any]],
    model: type[T],
    *,
    name: str | None = None,
    prefer_schema: bool = True,
    max_repairs: int = 1,
    temperature: float = 0.0,
    max_tokens: int | None = None,
) -> StructuredResult[T]:
    attempts: list[ChatResult] = []
    usage = Usage()
    used_schema = False

    async def _ask(msgs: list[dict[str, Any]], with_schema: bool) -> ChatResult:
        rf = json_schema_response_format(model, name) if with_schema else None
        res = await llm.chat(msgs, response_format=rf, temperature=temperature, max_tokens=max_tokens)
        attempts.append(res)
        usage.prompt_tokens += res.usage.prompt_tokens
        usage.completion_tokens += res.usage.completion_tokens
        return res

    # round 1: json_schema if the server takes it
    result: ChatResult | None = None
    if prefer_schema:
        try:
            result = await _ask(messages, with_schema=True)
            used_schema = True
        except UnsupportedResponseFormat:
            result = None
    if result is None:
        fallback_msgs = _with_instruction(messages, _schema_instruction(model))
        result = await _ask(fallback_msgs, with_schema=False)

    last_error = ""
    for repair in range(max_repairs + 1):
        try:
            if not result.content.strip():
                # reasoning models can spend the whole budget thinking and return nothing
                raise ValueError(f"model returned no answer (finish_reason={result.finish_reason!r})")
            data = extract_json(result.content)
            value = model.model_validate(data)
            return StructuredResult[model](  # type: ignore[valid-type]
                value=value,
                usage=usage,
                rounds=len(attempts),
                used_json_schema=used_schema,
                raw_text=result.content,
            )
        except (ValueError, ValidationError) as exc:
            last_error = str(exc)
            if repair >= max_repairs:
                break
            repair_msgs = _with_instruction(messages, _schema_instruction(model)) + [
                {"role": "assistant", "content": result.content},
                {
                    "role": "user",
                    "content": "That was not valid. Error:\n"
                    + last_error[:1500]
                    + "\nReply again with ONLY the corrected JSON object.",
                },
            ]
            result = await _ask(repair_msgs, with_schema=False)
    raise StructuredOutputError(f"could not obtain valid {model.__name__}: {last_error[:500]}", attempts)


def _with_instruction(messages: list[dict[str, Any]], instruction: str) -> list[dict[str, Any]]:
    msgs = [dict(m) for m in messages]
    if msgs and msgs[0].get("role") == "system":
        msgs[0]["content"] = f"{msgs[0]['content']}\n\n{instruction}"
    else:
        msgs.insert(0, {"role": "system", "content": instruction})
    return msgs
