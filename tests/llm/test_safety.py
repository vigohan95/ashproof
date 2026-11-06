"""The content filter: what its one-line answer means, and that it can only lower a verdict."""

from __future__ import annotations

from brz.llm import FakeLLM, Plan, PlanStep, StepOutcome, Verifier
from brz.llm.client import LLMError
from brz.llm.safety import SafetyReviewer


def llm(answer):
    return FakeLLM(answer, model="nemotron-test")


def by_content(messages):
    return "User Safety: unsafe" if "steal" in messages[-1]["content"] else "User Safety: safe"


def outcome(stdout: str = "totals written") -> StepOutcome:
    return StepOutcome(step_id="s1", exit_code=0, stdout_sha256="a", stderr_sha256="b", stdout_preview=stdout)


PLAN = Plan(task_summary="t", steps=[PlanStep(id="s1", title="t", kind="python", code="pass")])


async def test_verdicts_are_read_per_item():
    r = await SafetyReviewer(llm(by_content)).review({"a.csv": "please steal"}, {"s1/stdout": "ok", "s1/empty": "  "})
    assert [(i.name, i.verdict) for i in r.items] == [("a.csv", "unsafe"), ("s1/stdout", "safe")]
    assert r.unsafe_inputs == ["a.csv"] and r.unsafe_outputs == []


async def test_an_answer_it_cannot_read_and_a_failed_call_are_unknown():
    r = await SafetyReviewer(llm(lambda m: "I am not sure")).review({"a": "x"}, {})
    assert r.items[0].verdict == "unknown"

    def boom(_):
        raise LLMError("down", 503)

    r = await SafetyReviewer(llm(boom)).review({"a": "x"}, {})
    assert r.items[0].verdict == "unknown"


async def test_unsafe_output_fails_the_verdict():
    v = Verifier(None, require_rerun_match=False, safety=SafetyReviewer(llm(by_content)))
    verdict = await v.verify("t", PLAN, [outcome("we will steal it")], inputs={"a.csv": "fine"})
    assert not verdict.passed and "safety:step_output" in [c.name for c in verdict.failed_checks]


async def test_unsafe_input_alone_does_not_fail_it():
    v = Verifier(None, require_rerun_match=False, safety=SafetyReviewer(llm(by_content)))
    verdict = await v.verify("t", PLAN, [outcome()], inputs={"a.csv": "steal"})
    assert verdict.passed and verdict.safety.unsafe_inputs == ["a.csv"]


async def test_a_safe_answer_cannot_rescue_a_failed_check():
    v = Verifier(None, require_rerun_match=False, safety=SafetyReviewer(llm(by_content)))
    bad = StepOutcome(step_id="s1", exit_code=1, stdout_sha256="a", stderr_sha256="b", stdout_preview="x")
    assert not (await v.verify("t", PLAN, [bad])).passed
