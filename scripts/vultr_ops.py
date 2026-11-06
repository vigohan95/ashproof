"""Operator commands against the live Vultr account. Run from Windows Python (system proxy). Prints no secrets.

    python scripts/vultr_ops.py status              balance, pending charges, every instance
    python scripts/vultr_ops.py sweep [--all]       delete brz-sandbox VMs (older than TTL, or all with --all)
    python scripts/vultr_ops.py ensure-sshkey PUB   register a public key, print its id
    python scripts/vultr_ops.py ensure-firewall DESC CIDR PORTS   firewall group with tcp rules, print its id
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "sandbox" / "runner"))
from vultr_env import load_env  # noqa: E402

from brz.sandbox.backends import SANDBOX_TAG  # noqa: E402
from brz.vultr import VultrClient  # noqa: E402


async def status(c: VultrClient) -> dict:
    acct = (await c._request("GET", "/account"))["account"]
    inst = await c.list_instances()
    out = {
        "balance": acct.get("balance"),
        "pending_charges": acct.get("pending_charges"),
        "instances": [
            {"id": i.id, "label": i.label, "plan": i.plan, "region": i.region, "ip": i.main_ip, "status": i.status,
             "power": i.power_status, "server": i.server_status, "created": str(i.date_created), "tags": i.tags}
            for i in inst
        ],
    }
    return out


async def main() -> int:
    load_env()
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    s = sub.add_parser("sweep")
    s.add_argument("--all", action="store_true")
    k = sub.add_parser("ensure-sshkey")
    k.add_argument("pub")
    f = sub.add_parser("ensure-firewall")
    f.add_argument("desc")
    f.add_argument("cidr")
    f.add_argument("ports", help="comma list, e.g. 22,8700")
    args = ap.parse_args()
    async with VultrClient(os.environ["VULTR_API_KEY"]) as c:
        if args.cmd == "status":
            print(json.dumps(await status(c), indent=1))
        elif args.cmd == "sweep":
            deleted = await c.cleanup_orphans(SANDBOX_TAG, older_than_seconds=0 if args.all else 25 * 60)
            print(json.dumps({"deleted": deleted}))
        elif args.cmd == "ensure-sshkey":
            pub = Path(args.pub).read_text(encoding="utf-8").strip()
            data = await c._request("GET", "/ssh-keys")
            for key in data.get("ssh_keys", []):
                if key["ssh_key"].split()[:2] == pub.split()[:2]:
                    print(key["id"])
                    return 0
            made = await c._request("POST", "/ssh-keys", json={"name": "ashproof-operator", "ssh_key": pub})
            print(made["ssh_key"]["id"])
        elif args.cmd == "ensure-firewall":
            data = await c._request("GET", "/firewalls")
            for g in data.get("firewall_groups", []):
                if g["description"] == args.desc:
                    print(g["id"])
                    return 0
            from brz.vultr.models import FirewallRuleCreate

            g = await c.create_firewall_group(args.desc)
            ip, _, size = args.cidr.partition("/")
            for port in args.ports.split(","):
                await c.create_firewall_rule(
                    g.id, FirewallRuleCreate(subnet=ip, subnet_size=int(size or 32), port=port, notes=args.desc[:30])
                )
            print(g.id)
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
