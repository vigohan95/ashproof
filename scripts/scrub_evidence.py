"""Remove operator specifics from evidence before it is committed; refuse if a secret value is present.

    python scripts/scrub_evidence.py docs/evidence/vultr-2026-11-06

The operator's IP becomes <operator-ip>. The VMs' own addresses stay: they are deleted and show the run was real.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from vultr_env import load_env  # noqa: E402


def main() -> int:
    load_env()
    op = os.environ.get("BRZ_OPERATOR_IP", "")
    secrets = [os.environ.get(k, "") for k in ("VULTR_API_KEY", "INFERENCE_API_KEY")]
    bad = 0
    for path in sorted(Path(sys.argv[1]).rglob("*")):
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        if any(s and s in text for s in secrets):
            print("SECRET FOUND, not safe to commit:", path)
            bad += 1
        if op and op in text:
            path.write_text(text.replace(op, "<operator-ip>"), encoding="utf-8", newline="\n")
            print("scrubbed", path)
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
