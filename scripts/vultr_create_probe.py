"""How does POST /v2/instances behave when several creates overlap? Logs status, body and timing, deletes everything.

python scripts/vultr_create_probe.py <out.json> <concurrency>
"""

from __future__ import annotations

import asyncio
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

from brz.sandbox.cloudinit import SandboxSpec, render_cloud_init  # noqa: E402
from brz.vultr import InstanceCreate  # noqa: E402

API = "https://api.vultr.com/v2"
HEADERS = {"Authorization": "Bearer " + os.environ["VULTR_API_KEY"]}


async def create(c: httpx.AsyncClient, i: int, t0: float) -> dict:
    ud = render_cloud_init(
        SandboxSpec(task_id=f"probe{i}", token_key=os.urandom(32), control_plane_cidr="192.0.2.1/32")
    )
    body = InstanceCreate(
        region="ewr",
        plan="vhp-1c-1gb-amd",
        os_id=2284,
        label=f"brz-probe-{i}",
        hostname=f"brz-probe-{i}",
        tags=["brz-sandbox", "probe"],
        user_data=ud,
    ).to_api_body()
    s = time.monotonic()
    r = await c.post(API + "/instances", json=body, headers=HEADERS)
    row = {
        "i": i,
        "started_s": round(s - t0, 2),
        "seconds": round(time.monotonic() - s, 2),
        "status": r.status_code,
        "headers": {
            k: v
            for k, v in r.headers.items()
            if k.lower() in ("retry-after", "x-ratelimit-limit", "x-ratelimit-remaining")
        },
    }
    if r.status_code < 300:
        row["instance_id"] = r.json()["instance"]["id"]
    else:
        row["body"] = r.text[:400]
    print(json.dumps(row), flush=True)
    return row


async def delete(c: httpx.AsyncClient, iid: str) -> dict:
    t0 = time.monotonic()
    codes = []
    while time.monotonic() - t0 < 150:
        r = await c.delete(f"{API}/instances/{iid}", headers=HEADERS)
        codes.append(r.status_code)
        if r.status_code in (204, 404):
            break
        if len(codes) == 1:
            print("delete", iid[:8], r.status_code, r.text[:200], flush=True)
        await asyncio.sleep(3)
    return {"instance_id": iid, "codes": codes, "seconds_until_delete_accepted": round(time.monotonic() - t0, 1)}


async def main() -> None:
    out, n = Path(sys.argv[1]), int(sys.argv[2])
    async with httpx.AsyncClient(timeout=120) as c:
        t0 = time.monotonic()
        rows = await asyncio.gather(*(create(c, i, t0) for i in range(n)))
        ids = [r["instance_id"] for r in rows if "instance_id" in r]
        deletes = await asyncio.gather(*(delete(c, i) for i in ids))
    print(json.dumps(deletes), flush=True)
    out.write_text(json.dumps({"creates": rows, "deletes": deletes}, indent=1) + "\n", encoding="utf-8", newline="\n")


asyncio.run(main())
