"""Render attack results: JSON for machines, Markdown for people. Pure functions, unit-tested on any OS."""

from __future__ import annotations

import json

# What the first run found and what changed. Keyed by scenario id; shown next to the baseline result.
FIXES = {
    "A02": "The step's root is no longer the host root. It is a skeleton with /usr read-only and a few /etc entries.",
    "A03": "Outputs are read with lstat and O_NOFOLLOW; only regular files return, the rest are listed as skipped. "
    "The first run returned the runner's HMAC key through /work/out/stolen.key.",
    "A04": "Same change. The first run read /dev/zero through a link until the memory guard killed the runner.",
    "A05": "Every /work directory is lstat-checked before a step, files are created fresh with O_NOFOLLOW, chown does "
    "not follow links. The first run wrote and chowned the decoy directory as root.",
    "A06": "Step ids must match a strict pattern, in the runner and in the plan model.",
    "A10": "memory.swap is now set. The first run held 5.3 GiB against a 1.4 GiB limit by spilling into host swap.",
    "A12": "A watchdog polls /work every 50 ms and kills the step at 2 GiB (exit 125). The first run wrote all 3 GiB.",
    "A13": "stdout and stderr are drained through capped readers. The first run grew the root runner past 2 GB.",
    "A20": "Port 53 is closed after boot. Names are resolved once and pinned in /etc/hosts for the step. The first run "
    "delivered the tunnelled query to the resolver.",
    "A22": "Streams are scanned and redacted in the runner before they leave it, and the findings reach /scan. A dirty "
    "scan now fails the task.",
    "A23": "The scanner decodes base64 and hex one level, reads binary files, and no longer skips directories by name.",
    "A27": "Exec tokens now carry the sha256 of the step body. The first run ran swapped code under a valid token.",
    "A28": "Replies carry an HMAC over the body and the request's token. The first run accepted a forged result.",
    "A29": "A repair may change code only. Turning on the network, raising the timeout or dropping expected outputs "
    "fails the task and is written to the chain. The first run executed the widened step, in two sandboxes.",
}


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


def render_markdown(
    meta: dict,
    results: list[dict],
    *,
    heading: str = "Attack suite report",
    baseline: dict[str, str] | None = None,
) -> str:
    s = summarise(results)
    baseline = baseline or {}
    lines = [f"# {heading}", ""]
    lines.append(
        f"**{s['passed']} of {s['total']} scenarios contained, {s['failed']} succeeded, "
        f"{s['errors']} harness errors.** "
        "PASS means the attack failed. FAIL means the attack worked."
    )
    if s["accepted_limitations"]:
        lines.append(f"Failures we do not claim to stop: {', '.join(s['accepted_limitations'])}.")
    lines += ["", "## Environment", ""]
    for k, v in meta.items():
        lines.append(f"- {k}: `{v}`")
    head = "| ID | Category | Attack | Result | Time |"
    rule = "|---|---|---|---|---|"
    if baseline:
        head = "| ID | Category | Attack | First run | Now | Time |"
        rule = "|---|---|---|---|---|---|"
    lines += ["", "## Results", "", head, rule]
    for r in results:
        before = f"{baseline.get(r['id'], '-')} | " if baseline else ""
        lines.append(
            f"| {r['id']} | {r['category']} | {_cell(r['title'])} | {before}**{r['result']}** | "
            f"{r['duration_s']:.1f} s |"
        )
    changed = [r for r in results if baseline.get(r["id"]) == "FAIL" and r["id"] in FIXES]
    if changed:
        lines += ["", "## What the first run found", ""]
        lines += [f"- **{r['id']} {r['title']}.** {FIXES[r['id']]}" for r in changed]
    lines += ["", "## Details", ""]
    for r in results:
        lines += [f"### {r['id']} {r['title']}: {r['result']}", ""]
        lines.append(f"- Attempted: {r['attempted']}")
        lines.append(f"- Expected: {r['expected']}")
        if r.get("accepted_limitation"):
            lines.append(f"- Accepted limitation: {r['accepted_limitation']}")
        lines += ["- Observed:", "", "```json", json.dumps(r["observed"], indent=1, default=str)[:3500], "```", ""]
    return "\n".join(lines) + "\n"
