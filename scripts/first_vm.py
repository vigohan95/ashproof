"""First real throwaway VM through our own code: VultrSandboxBackend -> cloud-init -> runner -> gVisor step ->
egress deny and allow -> scan -> revoke -> DELETE -> GET 404. Writes evidence; destroys the VM whatever happens.

    python scripts/first_vm.py <out dir> <sandbox firewall id> [debug ssh key id]

Run from the operator PC: EXIT_IP stands in for the control plane until it runs on Vultr.
"""

from __future__ import annotations

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

from brz.llm.planner import PlanStep  # noqa: E402
from brz.sandbox.backends import VultrSandboxBackend, VultrSandboxConfig  # noqa: E402
from brz.sandbox.runner_client import RunnerClient  # noqa: E402
from brz.vultr import VultrClient  # noqa: E402

EXIT_IP = os.environ["BRZ_OPERATOR_IP"]
SSH_DIR = Path(os.environ.get("BRZ_SSH_DIR", "ssh"))

PROBE = """
import json, os, platform, socket
out = {"uid": os.getuid(), "kernel": platform.release(), "cwd": os.getcwd(),
       "interfaces": [n for _, n in socket.if_nameindex()],
       "env_keys": sorted(os.environ), "dev": sorted(os.listdir("/dev")),
       "root": sorted(os.listdir("/"))}
print(json.dumps(out, sort_keys=True))
open("/work/out/probe.json", "w").write(json.dumps(out, sort_keys=True))
"""

CURL = 'curl -sS -m {t} -o /dev/null -w "%{{http_code}}\\n" {url}; echo "exit=$?"'
EGRESS = "\n".join(
    [
        "echo '== name not on the allowlist (no DNS in the sandbox)'",
        CURL.format(t=6, url="https://wikipedia.org"),
        "echo '== IP not on the allowlist'",
        CURL.format(t=6, url="https://1.1.1.1"),
        "echo '== metadata service'",
        CURL.format(t=4, url="http://169.254.169.254/v1.json"),
        "echo '== allowlisted name, wrong port'",
        CURL.format(t=4, url="http://example.com:8080/"),
        "echo '== allowlisted name'",
        CURL.format(t=10, url="https://example.com"),
    ]
)

BOOT_DEBUG = (
    "cloud-init status --long; tail -n 60 /var/log/cloud-init-output.log; "
    "systemctl status brz-runner --no-pager | tail -n 20; nft list ruleset | head -40; ufw status"
)
VM_DEBUG = (
    "cloud-init status --long; systemd-analyze 2>&1 | head -3; tail -n 4 /var/log/cloud-init-output.log; "
    "cat /etc/brz/resolved_domains.txt; cat /etc/brz/hosts; ls -l /dev/kvm 2>&1; "
    "getent passwd 1000; id runner; grep -c -E 'svm|vmx' /proc/cpuinfo; lscpu | grep 'Model name'; free -m | head -2; ufw status | head -2; "
    "nft list ruleset; journalctl -k --no-pager -o short-iso --grep BRZ-EGRESS- | tail -n 20; "
    "/usr/local/bin/runsc --version; df -h / | tail -1"
)


def ssh(ip: str, cmd: str, timeout: int = 60) -> str:
    args = ["ssh", "-F", str(SSH_DIR / "ssh_config"), "-o", "UserKnownHostsFile=/dev/null", "-o", "LogLevel=ERROR"]
    args += [f"root@{ip}", cmd]
    try:
        p = subprocess.run(args, capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace")
        return p.stdout + p.stderr
    except subprocess.TimeoutExpired:
        return "ssh timeout"


async def main() -> int:
    load_env()
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    fw = sys.argv[2]
    sshkey = sys.argv[3] if len(sys.argv) > 3 else ""
    cfg = VultrSandboxConfig(
        firewall_group_id=fw,
        control_plane_cidr=f"{EXIT_IP}/32",
        ttl_minutes=30,
        sshkey_ids=[sshkey] if sshkey else [],
        admin_cidr=f"{EXIT_IP}/32" if sshkey else None,
    )
    backend = VultrSandboxBackend(VultrClient(os.environ["VULTR_API_KEY"]), cfg)
    task_id = "first-vm-" + datetime.now(timezone.utc).strftime("%H%M%S")
    log: dict = {
        "task_id": task_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "plan": cfg.plan,
        "region": cfg.region,
        "os_id": cfg.os_id,
        "debug_ssh": bool(sshkey),
    }
    handle = None
    client = None
    t0 = time.monotonic()
    rc = 1
    try:
        handle = await backend.provision(task_id, "primary", ["example.com"])
        log.update(
            instance_id=handle.instance_id,
            user_data_bytes=handle.meta["user_data_bytes"],
            seconds_to_active=round(time.monotonic() - t0, 1),
        )
        print("active", log["seconds_to_active"], "s", handle.instance_id, flush=True)
        client = RunnerClient(handle.runner_url, task_id=task_id, token_key=handle.token_key)
        try:
            log["health"] = await client.wait_ready(timeout=420, interval=4)
            log["seconds_to_runner_ready"] = round(time.monotonic() - t0, 1)
            print("runner ready", log["seconds_to_runner_ready"], "s", log["health"], flush=True)
        except Exception as exc:  # noqa: BLE001
            log["runner_error"] = str(exc)[:400]
            print("runner NOT ready", log["runner_error"], flush=True)
            if sshkey:
                log["boot_debug"] = ssh(handle.meta["main_ip"], BOOT_DEBUG, 90)
                print(log["boot_debug"], flush=True)
            raise
        r1 = await client.run_step(
            PlanStep(id="probe", title="probe", kind="python", code=PROBE, expected_outputs=["probe.json"], timeout_s=60)
        )
        log["step_probe"] = r1.model_dump(exclude={"files"}) | {"files": r1.file_hashes}
        print("probe", r1.exit_code, r1.executor, r1.stdout[:600], r1.stderr[:300], flush=True)
        r2 = await client.run_step(
            PlanStep(id="egress", title="egress", kind="shell", code=EGRESS, needs_network=True, timeout_s=60)
        )
        log["step_egress"] = r2.model_dump(exclude={"files"})
        print("egress", r2.exit_code, r2.stdout, r2.stderr[:800], json.dumps(r2.egress_attempts)[:1500], flush=True)
        await asyncio.sleep(2)
        log["egress_all"] = await client.egress()
        print("egress_all", len(log["egress_all"]), flush=True)
        log["scan"] = await client.scan()
        print("scan", {k: v for k, v in log["scan"].items() if k != "findings"}, log["scan"].get("findings"), flush=True)
        if sshkey:
            log["vm_debug"] = ssh(handle.meta["main_ip"], VM_DEBUG, 60)
            print(log["vm_debug"], flush=True)
        log["revoke"] = await client.revoke()
        rc = 0
    except Exception as exc:  # noqa: BLE001
        log["error"] = repr(exc)[:600]
        print("ERROR", log["error"], flush=True)
    finally:
        if client:
            await client.aclose()
        if handle:
            t1 = time.monotonic()
            proof = await backend.destroy(handle)
            log["destroy"] = {
                "http_status": proof.http_status,
                "attempts": proof.attempts,
                "observed_at": proof.observed_at.isoformat(),
                "seconds_delete_to_404": round(time.monotonic() - t1, 2),
            }
            print("destroyed", log["destroy"], flush=True)
        await backend.aclose()
        log["finished_at"] = datetime.now(timezone.utc).isoformat()
        path = out / f"{task_id}.json"
        path.write_text(json.dumps(log, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    return rc


raise SystemExit(asyncio.run(main()))
