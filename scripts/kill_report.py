"""Kill switch timing from the audit events of real runs: kill.requested -> last vm.destroyed (GET returned 404).

    python scripts/kill_report.py <tasks dir> <out.md> <prefix> [<prefix> ...]

Times come from the control plane's own hash-chained events, so the operator's network is not part of them.
"""

from __future__ import annotations

import json
import statistics
import sys
from datetime import datetime
from pathlib import Path


def ts(event: dict) -> datetime:
    return datetime.fromisoformat(event["ts"])


def one(path: Path) -> dict:
    d = json.loads(path.read_text(encoding="utf-8"))
    ev = d["events"]
    kill = next((e for e in ev if e["kind"] == "kill.requested"), None)
    if kill is None:
        return {}
    gone = [e for e in ev if e["kind"] == "vm.destroyed"]
    revoked = [e for e in ev if e["kind"] == "kill.tokens_revoked"]
    return {
        "task": d["id"],
        "final": d["status"],
        "status_at_kill": kill["data"].get("status_at_kill"),
        "vms": len(d["sandboxes"]),
        "all_404": all(s.get("proof") and s["proof"]["http_status"] == 404 for s in d["sandboxes"]),
        "killed_running_step": any(r["data"].get("killed_running_step") for r in revoked),
        "seconds_to_tokens_revoked": round((ts(revoked[-1]) - ts(kill)).total_seconds(), 3) if revoked else None,
        "seconds_to_last_404": round((max(ts(e) for e in gone) - ts(kill)).total_seconds(), 3),
    }


def main() -> None:
    src, out, *prefixes = sys.argv[1:]
    groups = {}
    for prefix in prefixes:
        groups[prefix] = [r for r in map(one, sorted(Path(src).glob(f"{prefix}*.timeline.json"))) if r]
    lines = ["# Kill switch on real Vultr VMs", ""]
    lines += ["Measured from the control plane's audit events: `kill.requested` to the last `vm.destroyed`, which is", ""]
    lines += ["written after `GET /v2/instances/{id}` returned 404. Each task had two VMs. Vultr plan vhp-1c-1gb-amd, ewr.", ""]
    for prefix, rows in groups.items():
        t = [r["seconds_to_last_404"] for r in rows]
        lines += [f"## {prefix}: {len(rows)} runs", ""]
        lines += [f"Button to both VMs 404: median {statistics.median(t):.2f} s, min {min(t):.2f} s, max {max(t):.2f} s.", ""]
        lines += ["| task | state at kill | final | step killed | tokens revoked (s) | both 404 (s) | VMs | all 404 |"]
        lines += ["|---|---|---|---|---|---|---|---|"]
        for r in rows:
            lines.append(
                f"| {r['task']} | {r['status_at_kill']} | {r['final']} | {r['killed_running_step']} | "
                f"{r['seconds_to_tokens_revoked']} | {r['seconds_to_last_404']} | {r['vms']} | {r['all_404']} |"
            )
        lines.append("")
    Path(out).write_text("\n".join(lines), encoding="utf-8", newline="\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
