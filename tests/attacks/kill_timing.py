"""Kill switch timing under gVisor: ``python -m tests.attacks.kill_timing --out DIR --runs 30``.

Each run starts a fresh runner and a hostile step: 5 processes that ignore SIGTERM, four spinning and one
writing a heartbeat. Once the heartbeat exists, the harness records every host process of the sandbox,
takes T0, calls ``POST /revoke`` with a signed token, and polls /proc until each of those processes has exited.

Measured from T0: the HTTP reply, the last host process gone, and the last heartbeat written. This covers the
in-VM half of the kill switch. The control-plane half (``DELETE /v2/instances/{id}`` until GET returns 404)
needs Vultr and is not in these numbers.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import platform
import statistics
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

from . import harness as H

HOSTILE = """
import os, signal, time
for s in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
    signal.signal(s, signal.SIG_IGN)
worker = False
for _ in range(4):
    if os.fork() == 0:
        worker = True
        break
if worker:
    while True:
        pass
fd = os.open('/work/out/heartbeat', os.O_CREAT | os.O_WRONLY, 0o644)
while True:
    os.pwrite(fd, b'%20.6f' % time.time(), 0)
    time.sleep(0.002)
"""


def one_run(index: int) -> dict:
    with H.RunnerHarness(f"kill-{index}") as r:
        box: dict = {}

        def run_step() -> None:
            box["status"], box["res"] = r.step(HOSTILE, timeout_s=60)

        thread = threading.Thread(target=run_step)
        thread.start()
        heartbeat = f"{r.workroot}/out/heartbeat"
        deadline = time.monotonic() + 20
        while time.monotonic() < deadline and not (os.path.exists(heartbeat) and os.path.getsize(heartbeat) >= 20):
            time.sleep(0.005)
        time.sleep(0.2)  # let all five processes reach their loops
        pids = H.descendants(r.pid)
        token = r.token("revoke")

        wall0 = time.time()
        t0 = time.perf_counter()
        status, reply = r.post("/revoke", {"token": token})
        ack_ms = (time.perf_counter() - t0) * 1000
        while any(H.is_alive(p) for p in pids) and time.perf_counter() - t0 < 15:
            time.sleep(0.0002)
        gone_ms = (time.perf_counter() - t0) * 1000

        thread.join(timeout=20)
        with open(heartbeat, "rb") as fh:
            last_beat = float(fh.read(20))
        left = H.sandbox_leftovers()
        containers = H.runsc_list()
    return {
        "run": index,
        "host_processes_at_kill": len(pids),
        "revoke_http_status": status,
        "killed_running_step": reply.get("killed_running_step"),
        "kill_to_http_reply_ms": round(ack_ms, 2),
        "kill_to_all_processes_gone_ms": round(gone_ms, 2),
        "last_heartbeat_relative_to_kill_ms": round((last_beat - wall0) * 1000, 2),
        "running_step_http_status": box.get("status"),
        "processes_left_after": left,
        "runsc_containers_left": containers,
    }


def percentile(values: list[float], pct: float) -> float:
    """Nearest rank."""
    ordered = sorted(values)
    return ordered[max(math.ceil(pct / 100 * len(ordered)) - 1, 0)]


def stats(values: list[float]) -> dict:
    return {
        "n": len(values),
        "min": round(min(values), 2),
        "p50": round(percentile(values, 50), 2),
        "p95": round(percentile(values, 95), 2),
        "max": round(max(values), 2),
        "mean": round(statistics.fmean(values), 2),
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", required=True)
    p.add_argument("--runs", type=int, default=30)
    args = p.parse_args()
    canaries = H.Canaries()
    canaries.install()
    runs = []
    try:
        for i in range(args.runs):
            runs.append(one_run(i))
            print(json.dumps(runs[-1]), flush=True)
    finally:
        canaries.remove()
    valid = [
        r
        for r in runs
        if r["killed_running_step"] is True
        and r["revoke_http_status"] == 200
        and r["running_step_http_status"] == 410
        and r["host_processes_at_kill"] >= 3
    ]
    clean = [r for r in valid if not r["processes_left_after"] and not r["runsc_containers_left"]]
    gone = stats([r["kill_to_all_processes_gone_ms"] for r in runs])
    reply = stats([r["kill_to_http_reply_ms"] for r in runs])
    beat = stats([r["last_heartbeat_relative_to_kill_ms"] for r in runs])
    summary = {
        "date_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "kernel_host": platform.release(),
        "runsc": H.subprocess.run([H.RUNSC, "--version"], capture_output=True, text=True).stdout.splitlines()[0],
        "runs": len(runs),
        "runs_where_the_kill_hit_a_running_step": len(valid),
        "runs_with_nothing_left_afterwards": len(clean),
        "kill_to_all_processes_gone_ms": gone,
        "kill_to_http_reply_ms": reply,
        "last_heartbeat_relative_to_kill_ms": beat,
    }
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "results.json").write_text(json.dumps({"summary": summary, "runs": runs}, indent=1), encoding="utf-8")
    lines = [
        "# Kill switch timing under gVisor",
        "",
        f"{summary['runs']} runs on {summary['runsc']}, platform systrap, WSL2 kernel {summary['kernel_host']}, "
        f"{summary['date_utc']}. Hostile step: 5 processes ignoring SIGTERM, four of them spinning on the CPU.",
        "",
        "T0 is immediately before `POST /revoke` is sent with a signed token. All figures in milliseconds.",
        "",
        "| Measure | min | p50 | p95 | max | mean |",
        "|---|---|---|---|---|---|",
    ]
    for name, row in (
        ("Kill to every host process of the sandbox gone", gone),
        ("Kill to HTTP reply", reply),
        ("Last heartbeat written, relative to kill", beat),
    ):
        lines.append(f"| {name} | {row['min']} | {row['p50']} | {row['p95']} | {row['max']} | {row['mean']} |")
    lines += [
        "",
        f"The kill reached a running step in {len(valid)} of {len(runs)} runs: HTTP 200, and the step's own call ended "
        "410. "
        f"Nothing was left afterwards in {len(clean)} of {len(runs)} runs: no runsc or gVisor process, "
        "`runsc list` empty.",
        "",
        "A negative heartbeat figure means the last beat was written before T0. The harness polls /proc with a 0.2 ms "
        "sleep between checks. The figures come from one workstation, not from a Vultr VM.",
        "",
        "Not in these numbers: the control-plane half of the kill switch, `DELETE /v2/instances/{id}` until GET returns "
        "404. That needs Vultr.",
        "",
        "Reproduce: `scripts/wsl-evidence.sh kill_timing --out <dir> --runs 30`",
        "",
    ]
    (out / "report.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(summary, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
