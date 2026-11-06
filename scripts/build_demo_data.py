"""Build apps/control_plane/data/evidence.json from docs/evidence, so the demo shows the same numbers as the files.

python scripts/build_demo_data.py
"""

from __future__ import annotations

import json
import re
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
EV = ROOT / "docs" / "evidence" / "vultr-2026-11-06"
OUT = ROOT / "apps" / "control_plane" / "data" / "evidence.json"


def build() -> dict:
    report = json.loads((EV / "attacks-vm" / "results.json").read_text(encoding="utf-8"))
    baseline = json.loads(
        (ROOT / "docs" / "evidence" / "attacks-2026-11-04" / "baseline" / "results.json").read_text(encoding="utf-8")
    )
    before = {r["id"]: r["result"] for r in baseline["results"]}
    attacks = [
        {
            "id": r["id"],
            "category": r["category"],
            "title": r["title"],
            "attempted": r["attempted"],
            "result": r["result"],
            "before_fixes": before.get(r["id"], ""),
            "accepted_limitation": r.get("accepted_limitation", ""),
        }
        for r in report["results"]
    ]
    kill = (EV / "kill-switch.md").read_text(encoding="utf-8")
    spans = re.findall(r"median ([\d.]+) s, min ([\d.]+) s, max ([\d.]+) s", kill)
    reliability = json.loads((EV / "reliability.json").read_text(encoding="utf-8"))
    secs = [r["seconds"] for r in reliability]
    return {
        "source": "docs/evidence/vultr-2026-11-06/",
        "attacks": attacks,
        "contained": sum(1 for a in attacks if a["id"].startswith("A") and a["result"] == "PASS"),
        "attack_total": sum(1 for a in attacks if a["id"].startswith("A")),
        "worked_before_fixes": sum(1 for a in attacks if a["id"].startswith("A") and a["before_fixes"] == "FAIL"),
        "kill_step": dict(zip(("median_s", "min_s", "max_s"), map(float, spans[0]), strict=True), runs=5),
        "kill_boot": dict(zip(("median_s", "min_s", "max_s"), map(float, spans[1]), strict=True), runs=3),
        "reliability": {
            "verified": sum(1 for r in reliability if r.get("status") == "verified"),
            "total": len(reliability),
            "median_s": round(statistics.median(secs), 1),
            "slowest_s": max(secs),
        },
    }


def main() -> None:
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(build(), indent=1) + "\n", encoding="utf-8", newline="\n")
    print(OUT)


if __name__ == "__main__":
    main()
