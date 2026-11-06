"""Latency / shape matrix for Serverless Inference: model x reasoning effort x structured output. No secrets printed."""
from __future__ import annotations

import concurrent.futures as cf
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for p in (ROOT / "scripts", ROOT, ROOT / "sandbox" / "runner"):
    sys.path.insert(0, str(p))
from vultr_env import load_env  # noqa: E402

load_env()
import httpx  # noqa: E402

from brz.llm.planner import SANDBOX_CONTRACT, Plan  # noqa: E402
from brz.llm.structured import _schema_instruction, json_schema_response_format  # noqa: E402

BASE = "https://api.vultrinference.com/v1"
RF = json_schema_response_format(Plan, "plan")
TASK = {"task": "Total the amount column per region and write summary.json", "budget_usd": 0.25,
        "pre_approved_domains": [], "attached_files": ["sales.csv"], "vm_plan": "vhp-1c-1gb-amd"}
SYS = SANDBOX_CONTRACT.format(max_steps=6)


def one(model: str, effort: str | None, schema: bool, budget: int = 240) -> dict:
    msgs = [{"role": "system", "content": SYS if schema else SYS + "\n\n" + _schema_instruction(Plan)},
            {"role": "user", "content": "Produce the plan for this task:\n" + json.dumps(TASK)}]
    body = {"model": model, "messages": msgs, "temperature": 0, "max_tokens": 8000}
    if schema:
        body["response_format"] = RF
    if effort:
        body["reasoning_effort"] = effort
    t = time.time()
    row = {"model": model, "effort": effort, "schema": schema}
    try:
        with httpx.Client(timeout=budget, headers={"Authorization": "Bearer " + os.environ["INFERENCE_API_KEY"]}) as c:
            r = c.post(BASE + "/chat/completions", json=body)
        row.update(status=r.status_code, seconds=round(time.time() - t, 1))
        if r.status_code != 200:
            row["error"] = r.text[:300]
            return row
        d = r.json()
        ch = d["choices"][0]
        m = ch["message"]
        row.update(finish=ch.get("finish_reason"), usage=d.get("usage"), msg_keys=sorted(m.keys()),
                   content_len=len(m.get("content") or ""), reasoning_len=len(m.get("reasoning_content") or m.get("reasoning") or ""))
        try:
            Plan.model_validate_json(m.get("content") or "")
            row["valid_plan"] = True
        except Exception as e:  # noqa: BLE001
            row["valid_plan"] = False
            row["content_head"] = (m.get("content") or "")[:160]
            row["why"] = str(e)[:160]
    except Exception as e:  # noqa: BLE001
        row.update(seconds=round(time.time() - t, 1), error=repr(e)[:160])
    return row


if __name__ == "__main__":
    combos = [(m, e, s) for m in ("glm-5.3", "qwen3.8-27b", "glm-5.3-flash") for e in ("minimal", "low", None) for s in (True, False)]
    out = Path(sys.argv[1])
    rows = []
    with cf.ThreadPoolExecutor(6) as ex:
        for row in ex.map(lambda a: one(*a), combos):
            rows.append(row)
            print(json.dumps(row), flush=True)
    out.write_text(json.dumps(rows, indent=1) + "\n", encoding="utf-8", newline="\n")
