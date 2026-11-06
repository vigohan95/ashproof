"""Consecutive real tasks through the public API, on the deployed code. Every outcome is counted, none is dropped.

    python scripts/reliability.py <base url> <out dir> <count>

The mix is the compromised agent, normal work, a fetch and a wall test. A run counts as good when it ends the way that
kind of task should: the attack failed by the refused-packet check, the other three verified, all with both VMs gone,
identical hashes across the two VMs, and a receipt that is signed, in the public log and passes the offline verifier.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from apps.control_plane.presets import PRESETS  # noqa: E402

TASK = {p["key"]: p["task"] for p in PRESETS}
MIX = [
    ("compromised-agent", "failed", ["--scenario", "compromised-agent"]),
    ("csv", "verified", []),
    ("fetch", "verified", ["--domains", "example.com"]),
    ("walls", "verified", ["--expect-refusals"]),
]


def main() -> None:
    base, out, count = sys.argv[1], Path(sys.argv[2]), int(sys.argv[3])
    rows = []
    for i in range(count):
        kind, expected, extra = MIX[i % len(MIX)]
        name = f"rel-{i + 1:02d}-{kind}"
        args = [sys.executable, str(ROOT / "scripts" / "live_task.py"), base, str(out), name, TASK[kind], *extra]
        t0 = time.monotonic()
        p = subprocess.run([*args, "--timeout", "280"], capture_output=True, text=True, timeout=330, check=False)
        path = out / f"{name}.summary.json"
        row = {"name": name, "rc": p.returncode, "seconds": round(time.monotonic() - t0, 1)}
        if path.exists() and p.returncode == 0:
            s = json.loads(path.read_text(encoding="utf-8"))
            row |= {
                "task_id": s["task_id"],
                "status": s["status"],
                "offline_verify_rc": s["offline_verify_rc"],
                "cost": s["cost"],
                "rerun_match": s["verdict"]["rerun_match"],
                "denied": s["egress"]["denied"],
                "all_404": all(v.get("proof") and v["proof"]["http_status"] == 404 for v in s["sandboxes"]),
            }
            row["good"] = bool(
                s["status"] == expected and row["rerun_match"] and row["all_404"] and row["offline_verify_rc"] == 0
            )
        else:
            row["good"] = False
            row["stderr"] = p.stderr[-300:] + p.stdout[-300:]
        rows.append(row)
        print(json.dumps(row), flush=True)
        (out.parent / f"{out.name}.json").write_text(json.dumps(rows, indent=1) + "\n", encoding="utf-8", newline="\n")
    print("series-done", flush=True)


if __name__ == "__main__":
    main()
