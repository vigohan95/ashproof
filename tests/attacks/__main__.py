"""Run the attack suite: ``python -m tests.attacks --out docs/evidence/attacks-<date> [--only A03,A05]``.

Needs root and runsc (see scripts/wsl-attacks.sh). Writes report.md and results.json into --out.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

from . import harness as H
from .report import render_markdown, summarise
from .scenarios import SCENARIOS, Ctx


def _cmd(args: list[str]) -> str:
    try:
        out = subprocess.run(args, capture_output=True, text=True, timeout=15, check=False)
        return (out.stdout or out.stderr).strip().splitlines()[0]
    except (OSError, IndexError, subprocess.TimeoutExpired) as exc:
        return f"unavailable: {exc}"


def environment() -> dict:
    head = os.environ.get("BRZ_GIT_HEAD") or _cmd(
        ["git", "-c", "safe.directory=*", "-C", str(H.REPO), "rev-parse", "--short", "HEAD"]
    )
    dirty = subprocess.run(
        ["git", "-c", "safe.directory=*", "-C", str(H.REPO), "status", "--porcelain", "--", "sandbox", "brz"],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    ).stdout.strip()
    return {
        "date_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "kernel_host": platform.release(),
        "runsc": _cmd([H.RUNSC, "--version"]),
        "platform": "systrap",
        "python": platform.python_version(),
        "git_head": head,
        "uncommitted_changes_in_sandbox_or_brz": bool(dirty),
    }


def run(only: set[str] | None) -> list[dict]:
    canaries = H.Canaries()
    canaries.install()
    results: list[dict] = []
    try:
        for sc in SCENARIOS:
            if only and sc.id not in only:
                continue
            ctx = Ctx(canaries)
            t = time.perf_counter()
            try:
                contained, observed = sc.fn(ctx)
                result = "PASS" if contained else "FAIL"
            except Exception:  # noqa: BLE001 - a broken scenario must not look like a contained attack
                contained, result = False, "ERROR"
                observed = {"harness_error": traceback.format_exc()[-1500:]}
            for r in ctx.runners:
                r.stop()
            H.clean_containers()
            results.append(
                {
                    "id": sc.id,
                    "category": sc.category,
                    "title": sc.title,
                    "attempted": sc.attempted,
                    "expected": sc.expected,
                    "accepted_limitation": sc.accepted_limitation,
                    "result": result,
                    "duration_s": round(time.perf_counter() - t, 2),
                    "observed": observed,
                    "steps": ctx.step_log(),
                }
            )
            print(f"{sc.id} {result:5} {results[-1]['duration_s']:7.1f}s  {sc.title}", flush=True)
    finally:
        canaries.remove()
    return results


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", required=True)
    p.add_argument("--only", default="", help="comma-separated scenario ids")
    p.add_argument("--heading", default="Attack suite report")
    p.add_argument("--baseline", default="", help="results.json of an earlier run, shown side by side")
    args = p.parse_args()
    if os.geteuid() != 0 or not os.path.exists(H.RUNSC):
        print("needs root and /usr/local/bin/runsc", file=sys.stderr)
        return 2
    only = {x.strip() for x in args.only.split(",") if x.strip()} or None
    meta = environment()
    results = run(only)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(
        json.dumps({"environment": meta, "summary": summarise(results), "results": results}, indent=1, default=str),
        encoding="utf-8",
    )
    baseline = {}
    if args.baseline:
        earlier = json.loads(Path(args.baseline).read_text(encoding="utf-8"))
        baseline = {r["id"]: r["result"] for r in earlier["results"]}
    report = render_markdown(meta, results, heading=args.heading, baseline=baseline)
    (out / "report.md").write_text(report, encoding="utf-8")
    s = summarise(results)
    print(f"{s['passed']}/{s['total']} contained; failed: {s['failed_ids']}; errors: {s['error_ids']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
