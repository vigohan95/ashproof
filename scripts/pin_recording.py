"""Copy finished tasks from the control plane into the package, so the demo's recordings ship with the code.

    python scripts/pin_recording.py <ssh host alias> <task id> [<task id> ...]

The files are the control plane's own archive, unchanged. Nothing is edited: a recording is a real task, with its
real events and its receipt. Refuses a file that holds a secret or the operator's address.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
from vultr_env import load_env  # noqa: E402

DEST = ROOT / "apps" / "control_plane" / "recordings"


def main() -> int:
    load_env()
    host, *ids = sys.argv[1:]
    ssh = ["ssh", "-F", str(Path(os.environ["BRZ_SSH_DIR"]) / "ssh_config"), host]
    forbidden = [os.environ.get(k, "") for k in ("VULTR_API_KEY", "INFERENCE_API_KEY", "BRZ_OPERATOR_IP")]
    for task_id in ids:
        if not task_id.isalnum():
            raise SystemExit(f"bad task id {task_id!r}")
        raw = subprocess.run(
            [*ssh, f"cat /var/lib/ashproof/tasks/{task_id}.json"], capture_output=True, check=True, timeout=60
        ).stdout
        text = raw.decode("utf-8")
        if any(s and s in text for s in forbidden):
            print("refused, holds a secret or the operator address:", task_id)
            return 1
        data = json.loads(text)
        DEST.mkdir(parents=True, exist_ok=True)
        (DEST / f"{task_id}.json").write_text(text, encoding="utf-8", newline="\n")
        print("pinned", task_id, data["status"], len(data["timeline"]["events"]), "events")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
