"""Serial latency check, one call at a time, so queueing from our own parallel calls is not blamed on the model."""

from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from llm_probe import one  # noqa: E402

rows = []
for model, effort in (
    ("glm-5.3", "low"),
    ("glm-5.3", "low"),
    ("glm-5.3", "low"),
    ("glm-5.3-flash", "low"),
    ("qwen3.8-27b", "low"),
):
    row = one(model, effort, True, budget=200)
    rows.append(
        {k: row.get(k) for k in ("model", "effort", "status", "seconds", "finish", "valid_plan", "error")}
        | {"completion_tokens": (row.get("usage") or {}).get("completion_tokens")}
    )
    print(json.dumps(rows[-1]), flush=True)
Path(sys.argv[1]).write_text(json.dumps(rows, indent=1) + "\n", encoding="utf-8", newline="\n")
