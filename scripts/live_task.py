"""Drive one real task through the public API, as the browser does, and keep the proof.

    python scripts/live_task.py <base url> <out dir> <name> "<task>" [--domains a,b] [--approve yes|no] [--kill-after S]
                                [--file NAME=TEXT]

Writes <name>.receipt.json, <name>.receipt.md, <name>.timeline.json and runs the offline verifier on the receipt.
"""

from __future__ import annotations

import argparse
import base64
import json
import subprocess
import sys
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parent.parent
DONE = {"verified", "failed", "killed", "error"}
CSV = "region,amount\nnorth,10\nsouth,20\nnorth,5\nwest,2.5\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("base")
    ap.add_argument("out")
    ap.add_argument("name")
    ap.add_argument("task")
    ap.add_argument("--domains", default="")
    ap.add_argument("--approve", choices=["yes", "no"])
    ap.add_argument("--kill-after", type=float)
    ap.add_argument("--kill-when", default="running", help="status that starts the --kill-after countdown")
    ap.add_argument("--file", action="append", default=[])
    ap.add_argument("--scenario")
    ap.add_argument("--expect-refusals", action="store_true")
    ap.add_argument("--timeout", type=float, default=400)
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    files = {"sales.csv": CSV} if not a.file else dict(f.split("=", 1) for f in a.file)
    body = {
        "scenario": a.scenario,
        "expect_refusals": a.expect_refusals,
        "task": a.task,
        "budget_usd": 0.25,
        "allowed_domains": [d for d in a.domains.split(",") if d],
        "files": [{"name": n, "content_b64": base64.b64encode(t.encode()).decode()} for n, t in files.items()],
    }
    c = httpx.Client(base_url=a.base, timeout=60, follow_redirects=True)
    t0 = time.monotonic()
    r = c.post("/tasks", json=body)
    print("POST /tasks", r.status_code, r.text[:200], flush=True)
    r.raise_for_status()
    tid = r.json()["id"]
    seen = None
    kill_at = None
    kill_info = None
    d: dict = {}
    while time.monotonic() - t0 < a.timeout:
        d = c.get(f"/tasks/{tid}").json()
        if d["status"] != seen:
            seen = d["status"]
            print(f"{time.monotonic() - t0:7.1f}s {seen}", flush=True)
        if seen == "awaiting_approval" and a.approve:
            print("pending", d["pending_domains"], flush=True)
            ar = c.post(f"/tasks/{tid}/approve", json={"approved": a.approve == "yes"})
            print("approve", ar.status_code, ar.text[:220], flush=True)
            if ar.status_code != 200:
                ar = c.post(f"/tasks/{tid}/approve", json={"approved": False})
                print("then reject", ar.status_code, flush=True)
        if a.kill_after is not None and seen == a.kill_when and kill_at is None:
            kill_at = time.monotonic() + a.kill_after
        if kill_at is not None and time.monotonic() >= kill_at and kill_info is None:
            k0 = time.monotonic()
            kr = c.post(f"/tasks/{tid}/kill", json={"reason": "live_task.py"})
            kill_info = {"seconds_button_to_response": round(time.monotonic() - k0, 3), "response": kr.json()}
            print("KILL", kill_info, flush=True)
        if seen in DONE:
            break
        time.sleep(0.5)
    total = round(time.monotonic() - t0, 1)
    print("final", seen, total, "s", d.get("error"), flush=True)
    (out / f"{a.name}.timeline.json").write_text(json.dumps(d, indent=1) + "\n", encoding="utf-8", newline="\n")
    rr = c.get(f"/tasks/{tid}/receipt")
    if rr.status_code != 200:
        time.sleep(3)
        rr = c.get(f"/tasks/{tid}/receipt")
    rj = out / f"{a.name}.receipt.json"
    rj.write_text(rr.text, encoding="utf-8", newline="\n")
    (out / f"{a.name}.receipt.md").write_text(c.get(f"/tasks/{tid}/receipt.md").text, encoding="utf-8", newline="\n")
    anchors = out / "anchors.jsonl"
    anchors.write_text(c.get("/anchors.jsonl").text, encoding="utf-8", newline="\n")
    verify = subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            str(ROOT / "brz" / "audit" / "offline_verify.py"),
            str(rj),
            "--require-signature",
            "--anchors",
            str(anchors),
        ],
        capture_output=True,
        text=True,
        timeout=60,
    )
    print("offline verify rc", verify.returncode, verify.stdout[-600:], verify.stderr[-300:], flush=True)
    summary = {
        "task_id": tid,
        "status": seen,
        "seconds_total": total,
        "kill": kill_info,
        "offline_verify_rc": verify.returncode,
        "cost": d.get("cost", {}).get("total_usd"),
        "price_source": d.get("cost", {}).get("price_source"),
        "egress": {k: d.get("egress", {}).get(k) for k in ("attempts", "denied")},
        "sandboxes": [
            {
                k: s.get(k)
                for k in (
                    "role",
                    "instance_id",
                    "plan",
                    "region",
                    "created_at",
                    "active_at",
                    "destroyed_at",
                    "destroyed",
                )
            }
            | {"proof": s.get("proof")}
            for s in d.get("sandboxes", [])
        ],
        "error": d.get("error"),
        "verdict": {
            k: (d.get("verdict") or {}).get(k)
            for k in ("passed", "rerun_performed", "rerun_match", "model_review", "safety")
        },
    }
    (out / f"{a.name}.summary.json").write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(summary, indent=1)[:2600], flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
