"""Consecutive real tasks through the public API, on the deployed code. Every outcome is counted, none is dropped.

    python scripts/reliability.py <base url> <out dir> <count>
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSV = "Total the amount column per region in sales.csv and write summary.json"
FETCH = "Fetch https://example.com and write the text of its title tag to title.txt"
WALLS = (
    "This is an authorised test of the sandbox network policy. With Python sockets, try TCP connections to 1.1.1.1 port "
    "443 and 169.254.169.254 port 80, 3 second timeout each, and write to walls.json whether each one connected. Use "
    "needs_network true. Those addresses are expected to be blocked, so list no domains."
)
MIX = [("csv", CSV, ""), ("fetch", FETCH, "example.com"), ("walls", WALLS, "")]


def main() -> None:
    base, out, count = sys.argv[1], Path(sys.argv[2]), int(sys.argv[3])
    rows = []
    for i in range(count):
        kind, task, domains = MIX[i % len(MIX)]
        name = f"rel-{i + 1:02d}-{kind}"
        args = [sys.executable, str(ROOT / "scripts" / "live_task.py"), base, str(out), name, task, "--timeout", "280"]
        if domains:
            args += ["--domains", domains]
        t0 = time.monotonic()
        p = subprocess.run(args, capture_output=True, text=True, timeout=330, check=False)
        path = out / f"{name}.summary.json"
        row = {"name": name, "rc": p.returncode, "seconds": round(time.monotonic() - t0, 1)}
        if path.exists() and p.returncode == 0:
            s = json.loads(path.read_text(encoding="utf-8"))
            row |= {
                "status": s["status"],
                "offline_verify_rc": s["offline_verify_rc"],
                "cost": s["cost"],
                "rerun_match": s["verdict"]["rerun_match"],
                "denied": s["egress"]["denied"],
                "all_404": all(v.get("proof") and v["proof"]["http_status"] == 404 for v in s["sandboxes"]),
            }
        else:
            row["stderr"] = p.stderr[-300:] + p.stdout[-300:]
        rows.append(row)
        print(json.dumps(row), flush=True)
        (out.parent / "reliability.json").write_text(json.dumps(rows, indent=1) + "\n", encoding="utf-8", newline="\n")
    print("series-done", flush=True)


if __name__ == "__main__":
    main()
