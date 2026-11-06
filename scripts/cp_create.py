"""Create the long-lived control-plane VM (idempotent by label). Prints id and IP. Tag differs from sandboxes on purpose:
the orphan sweep deletes only ``brz-sandbox`` instances."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
for p in (ROOT / "scripts", ROOT, ROOT / "sandbox" / "runner"):
    sys.path.insert(0, str(p))
from vultr_env import load_env  # noqa: E402

load_env()

from brz.vultr import InstanceCreate, VultrClient  # noqa: E402
from brz.vultr.models import FirewallRuleCreate  # noqa: E402

LABEL = "ashproof-control-plane"
PLAN = sys.argv[2] if len(sys.argv) > 2 else "vc2-1c-1gb"
ADMIN_IP = os.environ["BRZ_OPERATOR_IP"]


async def ensure_fw(c: VultrClient) -> str:
    data = await c._request("GET", "/firewalls")
    for g in data.get("firewall_groups", []):
        if g["description"] == LABEL:
            return g["id"]
    g = await c.create_firewall_group(LABEL)
    await c.create_firewall_rule(g.id, FirewallRuleCreate(subnet=ADMIN_IP, subnet_size=32, port="22", notes="operator ssh"))
    for port in ("80", "443"):
        await c.create_firewall_rule(g.id, FirewallRuleCreate(subnet="0.0.0.0", subnet_size=0, port=port, notes="public demo"))
    return g.id


async def main() -> None:
    load_env()
    sshkey = sys.argv[1]
    async with VultrClient(os.environ["VULTR_API_KEY"]) as c:
        fw = await ensure_fw(c)
        found = await c.list_instances(label=LABEL)
        inst = found[0] if found else await c.create_instance(InstanceCreate(
            region="ewr", plan=PLAN, os_id=2284, label=LABEL, hostname=LABEL, tags=["ashproof-control-plane"],
            sshkey_id=[sshkey], firewall_group_id=fw))
        inst = await c.wait_until_active(inst.id, timeout=300)
        print(json.dumps({"id": inst.id, "ip": inst.main_ip, "plan": inst.plan, "region": inst.region,
                          "firewall": fw, "status": inst.status, "server": inst.server_status}))


asyncio.run(main())
