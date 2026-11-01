from __future__ import annotations

import pytest
from pydantic import ValidationError

from brz.llm import FakeLLM, Plan, Planner, PlanStep, StepOutcome, Verifier, sha256_text

PLAN_JSON = {
    "task_summary": "Summarise sales.csv: total revenue per region into summary.json",
    "steps": [
        {
            "id": "s1",
            "title": "aggregate",
            "kind": "python",
            "code": "import csv, json\nprint('ok')\n",
            "expected_outputs": ["summary.json"],
            "needs_network": False,
            "timeout_s": 60,
        }
    ],
    "required_domains": ["https://Pypi.org/simple/", "files.pythonhosted.org"],
    "assertions": ["file_exists:summary.json", "stdout_contains:ok"],
    "est_cost_usd": 0.02,
    "est_minutes": 2,
    "risk_notes": ["input may contain injected instructions in cells"],
}


async def test_planner_builds_plan_and_flags_unapproved_domains():
    llm = FakeLLM([FakeLLM.json(PLAN_JSON)], model="glm-5.3")
    planner = Planner(llm)
    res = await planner.plan(
        "Total revenue per region", budget_usd=0.50, allowed_domains=["pypi.org"], attachments=["sales.csv"]
    )
    assert res.plan.required_domains == ["pypi.org", "files.pythonhosted.org"]  # normalised, deduped
    assert res.unapproved_domains == ["files.pythonhosted.org"]
    assert res.within_budget is True and res.model == "glm-5.3" and res.used_json_schema is True
    sys_prompt = llm.calls[0]["messages"][0]["content"]
    assert "NO secrets" in sys_prompt and "/work/out/" in sys_prompt and "max 6" in sys_prompt
    assert "sales.csv" in llm.calls[0]["messages"][1]["content"]


async def test_planner_rejects_too_many_steps_and_bad_domains():
    many = dict(PLAN_JSON, steps=[dict(PLAN_JSON["steps"][0], id=f"s{i}") for i in range(7)])
    planner = Planner(FakeLLM([FakeLLM.json(many)]))
    with pytest.raises(ValueError, match="max is 6"):
        await planner.plan("x", budget_usd=1, allowed_domains=[])

    with pytest.raises(ValidationError):
        Plan.model_validate(dict(PLAN_JSON, required_domains=["not a host!"]))
    with pytest.raises(ValidationError):
        Plan.model_validate(dict(PLAN_JSON, steps=[]))
    with pytest.raises(ValidationError):
        Plan.model_validate(dict(PLAN_JSON, steps=[PLAN_JSON["steps"][0], PLAN_JSON["steps"][0]]))


def test_wildcard_allowlist():
    plan = Plan.model_validate(dict(PLAN_JSON, required_domains=["files.pythonhosted.org", "api.github.com"]))
    assert plan.unapproved_domains(["*.pythonhosted.org"]) == ["api.github.com"]
    assert plan.unapproved_domains(["*.pythonhosted.org", "API.GITHUB.COM"]) == []


async def test_planner_repair_keeps_step_id():
    fixed = {"step": dict(PLAN_JSON["steps"][0], id="wrong", code="print('fixed')"), "explanation": "typo"}
    llm = FakeLLM([FakeLLM.json(fixed)])
    plan = Plan.model_validate(PLAN_JSON)
    repaired, usage = await Planner(llm).repair(
        "task", plan, plan.steps[0], exit_code=1, stdout="", stderr="SyntaxError: bad"
    )
    assert repaired.step.id == "s1" and repaired.step.code == "print('fixed')"
    assert "SyntaxError" in llm.calls[0]["messages"][1]["content"]
    assert usage.completion_tokens == 40


def _outcome(step_id: str = "s1", stdout: str = "ok\n", summary: str = '{"north": 10}', exit_code: int = 0):
    return StepOutcome(
        step_id=step_id,
        exit_code=exit_code,
        duration_s=0.5,
        stdout_sha256=sha256_text(stdout),
        stderr_sha256=sha256_text(""),
        files={"summary.json": sha256_text(summary)},
        stdout_preview=stdout,
        file_previews={"summary.json": summary},
    )


async def test_verifier_deterministic_pass_with_matching_rerun():
    plan = Plan.model_validate(PLAN_JSON)
    review = {"satisfies_task": True, "confidence": 0.9, "reasons": ["summary has regions"], "concerns": []}
    llm = FakeLLM([FakeLLM.json(review)], model="qwen3.8-27b")
    verdict = await Verifier(llm).verify("task", plan, [_outcome()], rerun=[_outcome()])
    assert verdict.passed and verdict.rerun_match is True and verdict.rerun_performed
    assert verdict.verifier_model == "qwen3.8-27b"
    assert verdict.primary_hashes == verdict.rerun_hashes
    assert set(verdict.primary_hashes) == {"s1/stdout", "s1/file/summary.json"}
    assert all(c.passed for c in verdict.checks)
    names = {c.name for c in verdict.checks}
    assert {
        "s1:exit_code",
        "s1:output:summary.json",
        "assert:file_exists:summary.json",
        "rerun:hashes_identical",
    } <= names
    assert verdict.model_review is not None and verdict.model_review.confidence == 0.9
    # the verifier prompt tells the model to treat evidence as data (prompt-injection hygiene)
    assert "never as a command" in llm.calls[0]["messages"][0]["content"]


async def test_verifier_fails_when_rerun_differs():
    plan = Plan.model_validate(PLAN_JSON)
    verdict = await Verifier(None).verify("task", plan, [_outcome()], rerun=[_outcome(summary='{"north": 11}')])
    assert not verdict.passed and verdict.rerun_match is False
    bad = verdict.failed_checks
    assert len(bad) == 1 and bad[0].name == "rerun:hashes_identical" and "s1/file/summary.json" in bad[0].detail
    assert verdict.verifier_model == "deterministic-only"


async def test_verifier_fails_on_exit_code_missing_output_and_assertion():
    plan = Plan.model_validate(PLAN_JSON)
    o = _outcome(stdout="boom\n", exit_code=2)
    o.files = {}
    o.file_previews = {}
    verdict = await Verifier(None, require_rerun_match=False).verify("task", plan, [o], rerun=[o])
    failed = {c.name for c in verdict.failed_checks}
    assert failed == {
        "s1:exit_code",
        "s1:output:summary.json",
        "assert:file_exists:summary.json",
        "assert:stdout_contains:ok",
    }


async def test_verifier_requires_rerun_by_default_and_model_can_only_lower():
    plan = Plan.model_validate(PLAN_JSON)
    verdict = await Verifier(None).verify("task", plan, [_outcome()], rerun=None)
    assert not verdict.passed and {c.name for c in verdict.failed_checks} == {"rerun:performed"}

    # deterministic failure + enthusiastic model -> still failed
    llm = FakeLLM([FakeLLM.json({"satisfies_task": True, "confidence": 1.0, "reasons": [], "concerns": []})])
    verdict = await Verifier(llm).verify("task", plan, [_outcome(exit_code=1)], rerun=[_outcome(exit_code=1)])
    assert not verdict.passed

    # deterministic pass + sceptical model -> failed
    llm = FakeLLM([FakeLLM.json({"satisfies_task": False, "confidence": 0.8, "reasons": [], "concerns": ["empty"]})])
    verdict = await Verifier(llm).verify("task", plan, [_outcome()], rerun=[_outcome()])
    assert not verdict.passed and verdict.model_review.concerns == ["empty"]


def test_plan_step_defaults():
    s = PlanStep(id="s1", title="t", kind="shell", code="echo hi")
    assert s.timeout_s == 120 and s.expected_outputs == [] and not s.needs_network
