"""Offline demo brains: a FakeLLM responder that plans CSV tasks without any model.

Used when no inference key is configured (``BRZ_MODE=mock``) and by the end-to-end tests.
The generated step is deterministic (sorted JSON, no timestamps) so the independent re-run
in the second sandbox produces identical hashes.
"""

from __future__ import annotations

import json
import re
from typing import Any

CSV_STEP_CODE = r"""
import csv, json, os

inp_dir = os.environ["BRZ_INPUT"]
out_dir = os.environ["BRZ_OUT"]
csv_files = sorted(f for f in os.listdir(inp_dir) if f.lower().endswith(".csv"))
if not csv_files:
    raise SystemExit("no CSV file attached")
path = os.path.join(inp_dir, csv_files[0])
with open(path, newline="", encoding="utf-8") as fh:
    rows = list(csv.DictReader(fh))
columns = list(rows[0].keys()) if rows else []
numeric = {}
for col in columns:
    vals = []
    for r in rows:
        try:
            vals.append(float(r[col]))
        except (TypeError, ValueError):
            vals = None
            break
    if vals:
        numeric[col] = {"sum": round(sum(vals), 6), "min": min(vals), "max": max(vals),
                        "mean": round(sum(vals) / len(vals), 6)}
group_col = next((c for c in columns if c not in numeric), None)
groups = {}
if group_col and numeric:
    metric = next(iter(numeric))
    for r in rows:
        groups[r[group_col]] = round(groups.get(r[group_col], 0.0) + float(r[metric]), 6)
summary = {"file": csv_files[0], "rows": len(rows), "columns": columns, "numeric": numeric,
           "group_by": group_col, "totals_by_group": dict(sorted(groups.items()))}
with open(os.path.join(out_dir, "summary.json"), "w", encoding="utf-8") as fh:
    json.dump(summary, fh, indent=2, sort_keys=True)
with open(os.path.join(out_dir, "report.md"), "w", encoding="utf-8") as fh:
    fh.write(f"# Summary of {csv_files[0]}\n\nRows: {len(rows)}\n\n")
    if groups:
        fh.write(f"| {group_col} | total |\n|---|---|\n")
        for k, v in sorted(groups.items()):
            fh.write(f"| {k} | {v} |\n")
print("rows", len(rows))
print("summary.json written")
"""


def demo_plan(task: str, attachments: list[str]) -> dict[str, Any]:
    return {
        "task_summary": f"Summarise the attached CSV for: {task[:120]}",
        "steps": [
            {
                "id": "s1",
                "title": "Aggregate the CSV with the standard library",
                "kind": "python",
                "code": CSV_STEP_CODE,
                "expected_outputs": ["summary.json", "report.md"],
                "needs_network": False,
                "timeout_s": 120,
            }
        ],
        "required_domains": [],
        "assertions": ["file_exists:summary.json", "stdout_contains:summary.json written"],
        "est_cost_usd": 0.02,
        "est_minutes": 3,
        "risk_notes": ["Input cells are treated as data; no instructions inside the CSV are followed."],
    }


def demo_review(_messages: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "satisfies_task": True,
        "confidence": 0.8,
        "reasons": ["summary.json present with per-group totals", "exit code 0 on both runs"],
        "concerns": [],
    }


def demo_responder(messages: list[dict[str, Any]]) -> str:
    """FakeLLM callable: planner prompts get a plan, verifier prompts a review, repairs a no-op step fix."""
    system = messages[0]["content"] if messages and messages[0].get("role") == "system" else ""
    last = messages[-1]["content"] if messages else ""
    if "independent verifier" in system:
        return json.dumps(demo_review(messages))
    if "A step failed" in last:
        m = re.search(r'"failed_step": (\{.*?\}), "exit_code"', last, re.DOTALL)
        step = json.loads(m.group(1)) if m else {"id": "s1", "title": "retry", "kind": "python", "code": "print('ok')"}
        return json.dumps({"step": step, "explanation": "demo repair: unchanged step"})
    try:
        payload = json.loads(last.split("\n", 1)[1])
    except (ValueError, IndexError):
        payload = {"task": last, "attached_files": []}
    return json.dumps(demo_plan(payload.get("task", ""), payload.get("attached_files", [])))
