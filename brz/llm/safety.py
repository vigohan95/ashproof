"""Third model: ``nemotron-3.5-content-safety`` reads inputs and step output before the verifier model does.

It answers one line, ``User Safety: safe`` or ``User Safety: unsafe``, with no reason and no category. Measured on Vultr
on 2026-11-06: it marked our injected CSV and the attack's log unsafe, and normal CSVs, fetched titles and wall test
output safe. See docs/evidence/vultr-2026-11-06/safety-probe.json. That is a small sample, and it is a content filter,
not an injection detector: the kernel is what stops an attack.

Like the verifier model, it can only lower a verdict. An unsafe step output fails a check. An unsafe input is recorded
and told to the verifier model, because a file can be dirty without the work being wrong. A failed call is recorded as
``unknown`` and changes nothing.
"""

from __future__ import annotations

import asyncio
import re
from typing import Literal

from pydantic import BaseModel, Field

from .client import LLM, LLMError, Usage

_VERDICT = re.compile(r"safety:\s*(safe|unsafe)", re.IGNORECASE)
MAX_CHARS = 4000
MAX_ITEMS = 12


class SafetyItem(BaseModel):
    source: Literal["input", "output"]
    name: str
    verdict: Literal["safe", "unsafe", "unknown"]


class SafetyReview(BaseModel):
    model: str
    items: list[SafetyItem] = Field(default_factory=list)
    usage: Usage = Field(default_factory=Usage)

    @property
    def unsafe_outputs(self) -> list[str]:
        return [i.name for i in self.items if i.source == "output" and i.verdict == "unsafe"]

    @property
    def unsafe_inputs(self) -> list[str]:
        return [i.name for i in self.items if i.source == "input" and i.verdict == "unsafe"]


class SafetyReviewer:
    def __init__(self, llm: LLM):
        self.llm = llm

    async def _one(self, source: str, name: str, text: str) -> tuple[SafetyItem, Usage]:
        try:
            res = await self.llm.chat([{"role": "user", "content": text[:MAX_CHARS]}], max_tokens=20)
        except LLMError:
            return SafetyItem(source=source, name=name, verdict="unknown"), Usage()
        m = _VERDICT.search(res.content)
        verdict = m.group(1).lower() if m else "unknown"
        return SafetyItem(source=source, name=name, verdict=verdict), res.usage

    async def review(self, inputs: dict[str, str], outputs: dict[str, str]) -> SafetyReview:
        texts = [("input", n, t) for n, t in inputs.items()] + [("output", n, t) for n, t in outputs.items()]
        texts = [(s, n, t) for s, n, t in texts if t.strip()][:MAX_ITEMS]
        results = await asyncio.gather(*(self._one(*t) for t in texts))
        usage = Usage(
            prompt_tokens=sum(u.prompt_tokens for _, u in results),
            completion_tokens=sum(u.completion_tokens for _, u in results),
        )
        return SafetyReview(model=getattr(self.llm, "model", ""), items=[i for i, _ in results], usage=usage)
