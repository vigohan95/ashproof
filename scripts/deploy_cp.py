"""Deploy HEAD to the control-plane VM. Keys travel over ssh stdin into a 0640 file; they never reach a command line.

    python scripts/deploy_cp.py <ssh host alias> <public ip> <sandbox firewall group id>

Extra KEY=VALUE arguments are added to the service environment (for example BRZ_DEMO_TASKS_PER_DAY=100).
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from vultr_env import load_env  # noqa: E402

load_env()
SSH = ["ssh", "-F", str(Path(os.environ["BRZ_SSH_DIR"]) / "ssh_config")]


def ssh(host: str, cmd: str, stdin: bytes | None = None, timeout: int = 420) -> None:
    subprocess.run([*SSH, host, cmd], input=stdin, check=True, timeout=timeout)


def main() -> None:
    host, ip, fw, *extra = sys.argv[1:]
    public = ip.replace(".", "-") + ".sslip.io"
    env = {
        "VULTR_API_KEY": os.environ["VULTR_API_KEY"],
        "INFERENCE_API_KEY": os.environ["INFERENCE_API_KEY"],
        "BRZ_MODE": "live",
        "VULTR_REGION": "ewr",
        "VULTR_PLAN": "vhp-1c-1gb-amd",
        "VULTR_OS_ID": "2284",
        "VULTR_FIREWALL_GROUP_ID": fw,
        "BRZ_CONTROL_PLANE_CIDR": f"{ip}/32",
        "BRZ_DATA_DIR": "/var/lib/ashproof",
        "BRZ_PUBLIC_DEMO": "1",
        "BRZ_DEMO_DOMAINS": "example.com",
        "BRZ_MAX_STEP_TIMEOUT_S": "120",
        "BRZ_APPROVAL_TIMEOUT_S": "180",
    }
    env.update(kv.split("=", 1) for kv in extra)
    archive = subprocess.run(
        ["git", "archive", "--format=tar", "HEAD"], cwd=ROOT, capture_output=True, check=True
    ).stdout
    ssh(
        host,
        "rm -rf /opt/ashproof/app && mkdir -p /opt/ashproof/app /etc/ashproof && tar -x -C /opt/ashproof/app",
        archive,
    )
    body = "".join(f"{k}={v}\n" for k, v in env.items()).encode()
    ssh(host, "umask 027 && cat > /etc/ashproof/env", body)
    ssh(host, f"bash /opt/ashproof/app/scripts/cp_provision.sh {public}")
    print(f"https://{public}/")


if __name__ == "__main__":
    main()
