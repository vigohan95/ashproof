"""Per-task running cost meter.

Vultr bills compute per *started* hour (so a 10-minute throwaway VM costs one full hour),
tokens per million. The meter keeps one line per charge so the receipt can show exactly
where every cent went, and :meth:`over_budget` lets the orchestrator trip the circuit
breaker before the next VM hour or LLM call.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from .prices import PriceTable, StaticPriceTable


@dataclass
class CostLine:
    kind: str  # "vm" | "tokens"
    label: str
    usd: float
    detail: dict[str, Any] = field(default_factory=dict)


@dataclass
class CostMeter:
    prices: PriceTable = field(default_factory=StaticPriceTable)
    budget_usd: float | None = None
    bill_hourly_ceiling: bool = True  # Vultr: each started hour is billed
    lines: list[CostLine] = field(default_factory=list)

    # ------------------------------------------------------------------ add
    def add_vm(self, plan_id: str, seconds: float, *, label: str | None = None) -> CostLine:
        rate = self.prices.vm_hourly(plan_id)
        hours = max(seconds, 0) / 3600.0
        billed_hours = float(math.ceil(hours)) if self.bill_hourly_ceiling else hours
        if seconds > 0 and billed_hours == 0:
            billed_hours = 1.0
        line = CostLine(
            kind="vm",
            label=label or f"VM {plan_id}",
            usd=round(rate * billed_hours, 6),
            detail={"plan": plan_id, "seconds": round(seconds, 1), "billed_hours": billed_hours, "hourly_usd": rate},
        )
        self.lines.append(line)
        return line

    def add_tokens(
        self, model: str, prompt_tokens: int, completion_tokens: int, *, label: str | None = None
    ) -> CostLine:
        price = self.prices.token_price(model)
        usd = (prompt_tokens * price.input_per_1m + completion_tokens * price.output_per_1m) / 1_000_000
        line = CostLine(
            kind="tokens",
            label=label or f"LLM {model}",
            usd=round(usd, 8),
            detail={
                "model": model,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
                "input_per_1m": price.input_per_1m,
                "output_per_1m": price.output_per_1m,
            },
        )
        self.lines.append(line)
        return line

    # ---------------------------------------------------------------- query
    @property
    def vm_usd(self) -> float:
        return round(sum(line.usd for line in self.lines if line.kind == "vm"), 8)

    @property
    def tokens_usd(self) -> float:
        return round(sum(line.usd for line in self.lines if line.kind == "tokens"), 8)

    @property
    def total_usd(self) -> float:
        return round(self.vm_usd + self.tokens_usd, 8)

    def over_budget(self) -> bool:
        return self.budget_usd is not None and self.total_usd > self.budget_usd

    def projected_vm_cost(self, plan_id: str, seconds: float) -> float:
        """What one more VM of this plan running this long would add (for pre-flight budget checks)."""
        rate = self.prices.vm_hourly(plan_id)
        hours = math.ceil(seconds / 3600.0) if self.bill_hourly_ceiling else seconds / 3600.0
        return round(rate * max(hours, 1 if self.bill_hourly_ceiling else 0), 6)

    def breakdown(self) -> dict[str, Any]:
        return {
            "total_usd": self.total_usd,
            "vm_usd": self.vm_usd,
            "tokens_usd": self.tokens_usd,
            "budget_usd": self.budget_usd,
            "over_budget": self.over_budget(),
            "price_source": self.prices.source,
            "lines": [{"kind": ln.kind, "label": ln.label, "usd": ln.usd, **ln.detail} for ln in self.lines],
        }
