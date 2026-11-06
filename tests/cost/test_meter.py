from __future__ import annotations

import pytest

from brz.cost import (
    FALLBACK_TOKEN_PRICE,
    FALLBACK_VM_HOURLY,
    CostMeter,
    LivePriceTable,
    StaticPriceTable,
    TokenPrice,
)


def test_vm_billed_per_started_hour():
    m = CostMeter()
    line = m.add_vm("vhp-1c-1gb-amd", seconds=10 * 60)  # 10 minutes -> 1 billed hour
    assert line.detail["billed_hours"] == 1.0
    assert line.usd == pytest.approx(0.008, rel=1e-3)  # under one cent
    m.add_vm("vx1-g-2c-8g", seconds=3601)  # just over an hour -> 2 hours
    assert m.lines[-1].detail["billed_hours"] == 2.0 and m.lines[-1].usd == pytest.approx(0.12)
    assert m.vm_usd == pytest.approx(0.008 + 0.12, rel=1e-3)


def test_vm_exact_billing_option_and_zero_seconds():
    m = CostMeter(bill_hourly_ceiling=False)
    assert m.add_vm("vx1-g-2c-8g", seconds=1800).usd == pytest.approx(0.03)
    assert CostMeter().add_vm("vx1-g-2c-8g", seconds=0).usd == 0.0


def test_token_pricing_from_research_table():
    m = CostMeter()
    planner = m.add_tokens("glm-5.3", prompt_tokens=8_000, completion_tokens=1_000)
    assert planner.usd == pytest.approx(8_000 * 0.75 / 1e6 + 1_000 * 3.0 / 1e6)
    verifier = m.add_tokens("qwen3.8-27b", prompt_tokens=8_000, completion_tokens=1_000)
    assert verifier.usd == pytest.approx(8_000 * 0.15 / 1e6 + 1_000 * 1.0 / 1e6)
    assert m.tokens_usd == pytest.approx(planner.usd + verifier.usd)
    # RESEARCH 4.1: 1000 rounds of (8K in + 1K out) on both models stays under $15
    assert (planner.usd + verifier.usd) * 1000 < 15
    assert m.add_tokens("gemma3:4b", 10_000, 10_000).usd == 0.0


def test_unknown_prices_fall_back_conservatively():
    t = StaticPriceTable()
    assert t.vm_hourly("vx1-g-64c-256g") == FALLBACK_VM_HOURLY
    assert t.token_price("some-new-model") == FALLBACK_TOKEN_PRICE
    assert t.source.startswith("static")


def test_budget_and_breakdown():
    m = CostMeter(budget_usd=0.05)
    m.add_vm("vhp-1c-1gb-amd", 600)
    m.add_tokens("glm-5.3", 20_000, 5_000)
    assert not m.over_budget()
    assert m.projected_vm_cost("vx1-g-2c-8g", 60) == pytest.approx(0.06)
    m.add_vm("vx1-g-2c-8g", 60)
    assert m.over_budget()
    b = m.breakdown()
    assert b["over_budget"] is True and b["budget_usd"] == 0.05
    assert b["total_usd"] == pytest.approx(m.vm_usd + m.tokens_usd)
    assert {ln["kind"] for ln in b["lines"]} == {"vm", "tokens"}
    assert b["lines"][1]["model"] == "glm-5.3" and b["lines"][1]["prompt_tokens"] == 20_000


def test_live_price_table_from_payloads():
    plans = [
        {"id": "vx1-g-2c-8g", "monthly_cost": 50.0, "hourly_cost": 0.07},  # hourly wins
        {"id": "vc2-1c-1gb", "monthly_cost": 5.0},  # monthly / 672
        {"id": "weird", "monthly_cost": None},
    ]
    models = [{"id": "glm-5.3", "pricing": {"input": 0.8, "output": 3.2}}, {"id": "no-pricing"}]
    live = LivePriceTable.from_payloads(plans, models)
    assert live.vm_hourly("vx1-g-2c-8g") == 0.07
    assert live.vm_hourly("vc2-1c-1gb") == pytest.approx(5.0 / 672, rel=1e-3)
    assert live.vm_hourly("vhp-1c-1gb-amd") == StaticPriceTable().vm_hourly("vhp-1c-1gb-amd")  # kept from static
    assert live.token_price("glm-5.3") == TokenPrice(0.8, 3.2)
    assert live.token_price("qwen3.8-27b") == StaticPriceTable().token_price("qwen3.8-27b")
    assert live.source.startswith("live")
    assert CostMeter(prices=live).add_vm("vx1-g-2c-8g", 60).usd == pytest.approx(0.07)
