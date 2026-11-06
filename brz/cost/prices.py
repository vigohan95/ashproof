"""Price tables.

``LivePriceTable`` is what the control plane uses on Vultr. Both sources were checked on 2026-11-06:

* ``GET /v2/plans`` carries ``hourly_cost``, but on plans with ``invoice_type: monthly`` that is a rounded display
  value. Pending charges bill those plans at ``monthly_cost / 672`` (vhp-1c-1gb-amd: 0.008929, not 0.008), so that is
  what we use. Plans with ``invoice_type: hourly`` (VX1) do bill at ``hourly_cost``.
* ``GET /v1/models`` called with an inference key carries ``cost_usd`` per token, under
  ``input_modalities[].pricing[type=prompt]`` and ``output_modalities[].pricing[type=completion]``.

``StaticPriceTable`` holds the same numbers as of that date. It serves offline mode, and live mode
when a source is unreachable; the receipt names which one priced the task.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

HOURS_PER_MONTH = 672  # Vultr's monthly billing cap for standard plans


@dataclass(frozen=True)
class TokenPrice:
    input_per_1m: float
    output_per_1m: float


# model id -> ($/1M input, $/1M output); RESEARCH.md section 4.1 table
STATIC_TOKEN_PRICES: dict[str, TokenPrice] = {
    "glm-5.3": TokenPrice(0.75, 3.00),
    "glm-5.3-flash": TokenPrice(0.10, 0.35),
    "qwen3.8-27b": TokenPrice(0.15, 1.00),
    "deepseek-v4.1-flash-1017": TokenPrice(0.15, 0.60),
    "minimax-m3.1-flash": TokenPrice(0.20, 0.90),
    "nemotron-3-nano-omni-30b-a3b-reasoning": TokenPrice(0.10, 0.25),
    "nemotron-3.5-content-safety": TokenPrice(0.05, 0.0),
    # local / test models are free
    "gemma3:4b": TokenPrice(0.0, 0.0),
    "fake-llm": TokenPrice(0.0, 0.0),
}

# Vultr documented flat rate when a model is missing from the table ($0.55 in / $2.75 out)
FALLBACK_TOKEN_PRICE = TokenPrice(0.55, 2.75)

# plan id -> $/hour; RESEARCH.md section 4.2
STATIC_VM_HOURLY: dict[str, float] = {
    "vx1-g-2c-8g": 0.060,
    "vx1-g-4c-16g": 0.120,
    "vx1-g-4c-16g-240s": 0.120,
    "vx1-m-2c-16g": 0.080,
    "vc2-1c-1gb": round(5.0 / HOURS_PER_MONTH, 6),
    "vhf-1c-1gb": round(6.0 / HOURS_PER_MONTH, 6),
    "vhp-1c-1gb-amd": round(6.0 / HOURS_PER_MONTH, 6),
    "vhp-2c-2gb-amd": round(18.0 / HOURS_PER_MONTH, 6),
}
FALLBACK_VM_HOURLY = 0.060  # assume a VX1 2c/8g when unknown (conservative)


class PriceTable(Protocol):
    def vm_hourly(self, plan_id: str) -> float: ...

    def token_price(self, model: str) -> TokenPrice: ...

    @property
    def source(self) -> str: ...


class StaticPriceTable:
    source = "static (checked against Vultr 2026-11-06)"

    def __init__(
        self,
        vm_hourly: dict[str, float] | None = None,
        token_prices: dict[str, TokenPrice] | None = None,
    ):
        self._vm = dict(STATIC_VM_HOURLY if vm_hourly is None else vm_hourly)
        self._tok = dict(STATIC_TOKEN_PRICES if token_prices is None else token_prices)

    def vm_hourly(self, plan_id: str) -> float:
        return self._vm.get(plan_id, FALLBACK_VM_HOURLY)

    def token_price(self, model: str) -> TokenPrice:
        return self._tok.get(model, FALLBACK_TOKEN_PRICE)


class LivePriceTable(StaticPriceTable):
    """Built from live Vultr payloads; falls back to the static table for anything missing."""

    source = "live (/v2/plans + /v1/models)"

    @classmethod
    def from_payloads(cls, plans: list[dict], models: list[dict] | None = None) -> LivePriceTable:
        vm: dict[str, float] = dict(STATIC_VM_HOURLY)
        for p in plans:
            pid = p.get("id")
            if not pid:
                continue
            if p.get("hourly_cost") is not None and p.get("invoice_type") != "monthly":
                vm[pid] = float(p["hourly_cost"])
            elif p.get("monthly_cost") is not None:
                vm[pid] = round(float(p["monthly_cost"]) / HOURS_PER_MONTH, 6)
        tok: dict[str, TokenPrice] = dict(STATIC_TOKEN_PRICES)
        for m in models or []:
            mid = m.get("id")
            cin = _per_token(m.get("input_modalities"), "prompt")
            cout = _per_token(m.get("output_modalities"), "completion")
            if mid and (cin is not None or cout is not None):
                tok[mid] = TokenPrice(round((cin or 0.0) * 1_000_000, 6), round((cout or 0.0) * 1_000_000, 6))
        return cls(vm, tok)


def _per_token(modalities: list[dict] | None, kind: str) -> float | None:
    """cost_usd per token for the text modality of a /v1/models entry."""
    for mod in modalities or []:
        if mod.get("type") != "text":
            continue
        for price in mod.get("pricing") or []:
            if price.get("type") == kind and price.get("unit") == "token":
                return float(price["cost_usd"])
    return None
