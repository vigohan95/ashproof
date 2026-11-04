"""Render attack results: JSON for machines, Markdown for people. Pure functions, unit-tested on any OS."""

from __future__ import annotations

import json


def summarise(results: list[dict]) -> dict:
    passed = [r for r in results if r["result"] == "PASS"]
    failed = [r for r in results if r["result"] == "FAIL"]
    errors = [r for r in results if r["result"] == "ERROR"]
    return {
        "total": len(results),
        "passed": len(passed),
        "failed": len(failed),
        "errors": len(errors),
        "failed_ids": [r["id"] for r in failed],
        "error_ids": [r["id"] for r in errors],
        "accepted_limitations": [r["id"] for r in failed if r.get("accepted_limitation")],
    }


def _cell(text: str) -> str:
    return str(text).replace("|", "\\|").replace("\n", " ")


def render_markdown(meta: dict, results: list[dict], *, heading: str = "Attack suite report") -> str:
    s = summarise(results)
    lines = [f"# {heading}", ""]
    lines.append(
        f"**{s['passed']} of {s['total']} attacks contained, {s['failed']} succeeded, {s['errors']} harness errors.** "
        "PASS means the attack failed. FAIL means the attack worked."
    )
    if s["accepted_limitations"]:
        lines.append(f"Failures we do not claim to stop: {', '.join(s['accepted_limitations'])}.")
    lines += ["", "## Environment", ""]
    for k, v in meta.items():
        lines.append(f"- {k}: `{v}`")
    lines += ["", "## Results", "", "| ID | Category | Attack | Result | Time |", "|---|---|---|---|---|"]
    for r in results:
        lines.append(
            f"| {r['id']} | {r['category']} | {_cell(r['title'])} | **{r['result']}** | {r['duration_s']:.1f} s |"
        )
    lines += ["", "## Details", ""]
    for r in results:
        lines += [f"### {r['id']} {r['title']}: {r['result']}", ""]
        lines.append(f"- Attempted: {r['attempted']}")
        lines.append(f"- Expected: {r['expected']}")
        if r.get("accepted_limitation"):
            lines.append(f"- Accepted limitation: {r['accepted_limitation']}")
        lines += ["- Observed:", "", "```json", json.dumps(r["observed"], indent=1, default=str)[:3500], "```", ""]
    return "\n".join(lines) + "\n"
