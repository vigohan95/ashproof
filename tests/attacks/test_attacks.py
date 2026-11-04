"""The attack suite itself needs root + runsc; on other machines only its bookkeeping is tested here."""

from __future__ import annotations

import os
import shutil

import pytest

from .report import render_markdown, summarise
from .scenarios import SCENARIOS

RESULTS = [
    {
        "id": "A01",
        "category": "fs",
        "title": "first | attack",
        "attempted": "a",
        "expected": "b",
        "accepted_limitation": "",
        "result": "PASS",
        "duration_s": 1.0,
        "observed": {"x": 1},
    },
    {
        "id": "A02",
        "category": "net",
        "title": "second",
        "attempted": "a",
        "expected": "b",
        "accepted_limitation": "cannot be stopped",
        "result": "FAIL",
        "duration_s": 2.0,
        "observed": {},
    },
    {
        "id": "A03",
        "category": "net",
        "title": "third",
        "attempted": "a",
        "expected": "b",
        "accepted_limitation": "",
        "result": "ERROR",
        "duration_s": 0.1,
        "observed": {"harness_error": "boom"},
    },
]


def test_scenario_ids_are_unique_and_described():
    ids = [s.id for s in SCENARIOS]
    assert len(ids) == len(set(ids)) >= 12
    assert all(s.title and s.attempted and s.expected and s.category for s in SCENARIOS)


def test_summary_never_counts_an_error_as_contained():
    s = summarise(RESULTS)
    assert (s["total"], s["passed"], s["failed"], s["errors"]) == (3, 1, 1, 1)
    assert s["failed_ids"] == ["A02"] and s["error_ids"] == ["A03"] and s["accepted_limitations"] == ["A02"]


def test_report_shows_failures_and_escapes_table_cells():
    md = render_markdown({"runsc": "x"}, RESULTS)
    assert "**1 of 3 scenarios contained, 1 succeeded, 1 harness errors.**" in md
    assert "| A02 | net | second | **FAIL** |" in md
    assert "first \\| attack" in md
    assert "Failures we do not claim to stop: A02." in md


def test_report_compares_with_the_first_run():
    md = render_markdown({}, RESULTS, baseline={"A01": "FAIL", "A02": "FAIL"})
    assert "| A01 | fs | first \\| attack | FAIL | **PASS** |" in md


@pytest.mark.skipif(
    not (shutil.which("runsc") and hasattr(os, "geteuid") and os.geteuid() == 0),
    reason="needs root and runsc; run scripts/wsl-attacks.sh",
)
def test_one_real_attack_is_contained():
    from . import harness as H
    from .scenarios import Ctx, a01

    canaries = H.Canaries()
    canaries.install()
    ctx = Ctx(canaries)
    try:
        contained, observed = a01(ctx)
    finally:
        canaries.remove()
    assert contained, observed
