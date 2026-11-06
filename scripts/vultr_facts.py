"""D1 facts: what the live Vultr catalogue really says. Writes docs/evidence/vultr-<date>/facts.json. No secrets."""
from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "sandbox" / "runner"))
from vultr_env import ROOT, load_env  # noqa: E402

from brz.vultr import VultrClient  # noqa: E402

WANT = ("vx1-g-2c-8g", "vhp-1c-1gb-amd", "vhp-1c-1gb", "vc2-1c-1gb", "vhf-1c-1gb", "vc2-1c-0.5gb")


async def main(out: Path) -> None:
    load_env()
    async with VultrClient(os.environ["VULTR_API_KEY"]) as c:
        regions = await c.list_regions()
        plans = await c.list_plans()
        oses = await c.list_os()
    ubuntu = [o.model_dump() for o in oses if "ubuntu" in o.name.lower()]
    picked = [p.model_dump() for p in plans if p.id in WANT or p.id.startswith("vx1-g-2c")]
    cheapest = sorted(
        [p for p in plans if "ewr" in p.locations],
        key=lambda p: p.effective_hourly_cost(),
    )[:8]
    facts = {
        "regions_total": len(regions),
        "regions_us": [r.id for r in regions if r.country == "US"],
        "ewr": next((r.model_dump() for r in regions if r.id == "ewr"), None),
        "plans_total": len(plans),
        "plan_keys": sorted(plans[0].model_dump().keys()) if plans else [],
        "picked_plans": [{**p, "locations_has_ewr": "ewr" in p["locations"], "locations": len(p["locations"])} for p in picked],
        "cheapest_ewr": [
            {"id": p.id, "vcpu": p.vcpu_count, "ram": p.ram, "disk": p.disk, "monthly": p.monthly_cost,
             "hourly_field": p.hourly_cost, "type": p.type}
            for p in cheapest
        ],
        "os_ubuntu": ubuntu,
    }
    out.mkdir(parents=True, exist_ok=True)
    (out / "facts.json").write_text(json.dumps(facts, indent=1, default=str) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(facts, indent=1, default=str)[:7000])


if __name__ == "__main__":
    asyncio.run(main(ROOT / "docs" / "evidence" / "vultr-2026-11-06"))
