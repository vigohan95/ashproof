"""Run the attack suite on a real Vultr sandbox VM: same plan, same cloud-init, egress locked down as in production.

    python scripts/attack_vm.py <out dir> <firewall id> <ssh key id> <control plane ssh alias> [--only A03,A05] [--heading H]

pip cannot run on the VM, which is the point of the VM, so Python dependencies are copied from the control plane
over ssh. The only differences from a production sandbox: the debug SSH door is open, and brz-runner is stopped so the
suite can start its own runners. The VM is destroyed whatever happens.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for p in (ROOT / "scripts", ROOT, ROOT / "sandbox" / "runner"):
    sys.path.insert(0, str(p))
from vultr_env import load_env  # noqa: E402

load_env()
from brz.sandbox.backends import VultrSandboxBackend, VultrSandboxConfig  # noqa: E402
from brz.sandbox.runner_client import RunnerClient  # noqa: E402
from brz.vultr import VultrClient  # noqa: E402

OP = os.environ["BRZ_OPERATOR_IP"]
SSH_CFG = str(Path(os.environ["BRZ_SSH_DIR"]) / "ssh_config")
SSH = ["ssh", "-F", SSH_CFG, "-o", "UserKnownHostsFile=/dev/null", "-o", "LogLevel=ERROR"]
SUITE_LIMIT_S = 1500


def ssh(target: str, cmd: str, *, stdin: bytes | None = None, timeout: int = 120) -> subprocess.CompletedProcess:
    return subprocess.run([*SSH, target, cmd], input=stdin, capture_output=True, timeout=timeout, check=False)


def text(p: subprocess.CompletedProcess) -> str:
    return (p.stdout + p.stderr).decode("utf-8", "replace")


async def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("out")
    ap.add_argument("firewall")
    ap.add_argument("sshkey")
    ap.add_argument("cp")
    ap.add_argument("--only", default="")
    ap.add_argument("--heading", default="Attack suite on a real Vultr VM")
    a = ap.parse_args()
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    cfg = VultrSandboxConfig(
        firewall_group_id=a.firewall,
        control_plane_cidr=f"{OP}/32",
        ttl_minutes=60,
        sshkey_ids=[a.sshkey],
        admin_cidr=f"{OP}/32",
    )
    backend = VultrSandboxBackend(VultrClient(os.environ["VULTR_API_KEY"]), cfg)
    task_id = "attacks-" + datetime.now(timezone.utc).strftime("%H%M%S")
    handle = None
    log: dict = {"task_id": task_id, "plan": cfg.plan, "region": cfg.region, "only": a.only}
    rc = 1
    try:
        handle = await backend.provision(task_id, "primary", [])
        ip = handle.meta["main_ip"]
        target = f"root@{ip}"
        client = RunnerClient(handle.runner_url, task_id=task_id, token_key=handle.token_key)
        log["health"] = await client.wait_ready(timeout=300, interval=4)
        await client.aclose()
        print("vm ready", ip, flush=True)

        deps = ssh(a.cp, "tar -C /opt/ashproof/venv/lib/python3.12 -czf - site-packages", timeout=200)
        print("deps bytes", len(deps.stdout), flush=True)
        print(text(ssh(target, "mkdir -p /opt/brz-deps && tar -xz -C /opt/brz-deps && echo deps-ok", stdin=deps.stdout, timeout=300))[-200:], flush=True)
        repo = subprocess.run(["git", "archive", "--format=tar", "HEAD"], cwd=ROOT, capture_output=True, check=True).stdout
        head = subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
        log["git_head"] = head
        print(text(ssh(target, "mkdir -p /root/ashproof && tar -x -C /root/ashproof && echo repo-ok", stdin=repo, timeout=120))[-200:], flush=True)

        only = f"--only {a.only}" if a.only else ""
        run = (
            "systemctl stop brz-runner; mkdir -p /srv/brz-attacks /var/lib/brz/bundles; cd /root/ashproof; "
            "PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=/root/ashproof:/root/ashproof/sandbox/runner:/opt/brz-deps/site-packages "
            f"nohup timeout -k 10 {SUITE_LIMIT_S} python3 -m tests.attacks --out /root/out {only} "
            f"--heading '{a.heading}' > /root/suite.log 2>&1; echo finished $? > /root/suite.done"
        )
        subprocess.Popen([*SSH, "-f", target, f"nohup sh -c \"{run}\" >/dev/null 2>&1 &"], stdin=subprocess.DEVNULL)
        t0 = time.monotonic()
        last = ""
        while time.monotonic() - t0 < SUITE_LIMIT_S + 60:
            await asyncio.sleep(20)
            try:
                p = ssh(target, "cat /root/suite.done 2>/dev/null; tail -n 1 /root/suite.log", timeout=40)
            except subprocess.TimeoutExpired:
                print("ssh timeout: the VM may be struggling", flush=True)
                continue
            now = text(p).strip()[-160:]
            if now != last:
                print(f"{time.monotonic() - t0:6.0f}s {now}", flush=True)
                last = now
            if "finished" in now:
                break
        log["seconds"] = round(time.monotonic() - t0)
        log["suite_log_tail"] = text(ssh(target, "tail -n 40 /root/suite.log", timeout=40))
        log["oom_lines"] = text(ssh(target, "dmesg | grep -i -E 'out of memory|oom-kill|Killed process' | tail -n 20", timeout=40))
        log["vm_memory"] = text(ssh(target, "free -m; uptime; df -h / | tail -1", timeout=40))
        tar = ssh(target, "tar -C /root/out -czf - .", timeout=120)
        (out / "out.tgz").write_bytes(tar.stdout)
        subprocess.run(["tar", "-xzf", "out.tgz"], cwd=out, check=False)
        (out / "out.tgz").unlink()
        rc = 0
    except Exception as exc:  # noqa: BLE001
        log["error"] = repr(exc)[:600]
        print("ERROR", log["error"], flush=True)
    finally:
        if handle:
            proof = await backend.destroy(handle)
            log["destroy"] = {"http_status": proof.http_status, "observed_at": proof.observed_at.isoformat()}
            print("destroyed", log["destroy"], flush=True)
        await backend.aclose()
        (out / "run.json").write_text(json.dumps(log, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    return rc


raise SystemExit(asyncio.run(main()))
