"""In-process mock of the Vultr API v2 for tests and offline demos.

It is a FastAPI app, so the real :class:`brz.vultr.client.VultrClient` talks to it through
``httpx.ASGITransport`` with zero network. It reproduces:

* instance lifecycle ``pending`` -> ``active`` (after N polls) -> DELETE -> ``GET`` returns 404
* ``?tag=`` filtering and ``meta.links.next`` pagination shape
* plan / region / os catalogues with the prices from RESEARCH.md section 4
* firewall groups + rules, object storage (minimal)
* fault injection (``fail_next``: 429 / 5xx for the next N matching requests)
* a full call log (``calls``) for assertions

Shapes are taken from govultr (instance.go, plan.go, firewall_rule.go). Where the real
API differs, fix it HERE and in the client, never in the orchestrator.
"""

from __future__ import annotations

import base64
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import FastAPI, Header, Request
from fastapi.responses import JSONResponse, Response

MOCK_API_KEY = "MOCKKEY000000000000000000000000000000"

DEFAULT_PLANS: list[dict[str, Any]] = [
    # VX1 (dedicated AMD EPYC vCPU); hourly, no 672h cap. Prices: third-party snapshot 2026-03.
    {
        "id": "vx1-g-2c-8g",
        "vcpu_count": 2,
        "ram": 8192,
        "disk": 80,
        "bandwidth": 4096,
        "monthly_cost": 43.8,
        "hourly_cost": 0.060,
        "type": "vx1",
        "locations": ["ewr", "atl"],
    },
    {
        "id": "vx1-g-4c-16g",
        "vcpu_count": 4,
        "ram": 16384,
        "disk": 160,
        "bandwidth": 5120,
        "monthly_cost": 87.6,
        "hourly_cost": 0.120,
        "type": "vx1",
        "locations": ["ewr", "atl"],
    },
    {
        "id": "vx1-m-2c-16g",
        "vcpu_count": 2,
        "ram": 16384,
        "disk": 80,
        "bandwidth": 4096,
        "monthly_cost": 58.4,
        "hourly_cost": 0.080,
        "type": "vx1",
        "locations": ["ewr", "atl"],
    },
    # Regular / High Frequency / High Performance cloud compute ($5 / $6 / $6 per month, 672h cap)
    {
        "id": "vc2-1c-1gb",
        "vcpu_count": 1,
        "ram": 1024,
        "disk": 25,
        "bandwidth": 1024,
        "monthly_cost": 5.0,
        "hourly_cost": 0.007,
        "type": "vc2",
        "locations": ["ewr", "atl", "sea", "lax"],
    },
    {
        "id": "vhf-1c-1gb",
        "vcpu_count": 1,
        "ram": 1024,
        "disk": 32,
        "bandwidth": 1024,
        "monthly_cost": 6.0,
        "hourly_cost": 0.009,
        "type": "vhf",
        "locations": ["ewr", "atl", "sea", "lax"],
    },
    {
        "id": "vhp-1c-1gb-amd",
        "vcpu_count": 1,
        "ram": 1024,
        "disk": 25,
        "bandwidth": 2048,
        "monthly_cost": 6.0,
        "hourly_cost": 0.009,
        "type": "vhp",
        "locations": ["ewr", "atl", "sea", "lax"],
    },
    {
        "id": "vhp-2c-2gb-amd",
        "vcpu_count": 2,
        "ram": 2048,
        "disk": 60,
        "bandwidth": 3072,
        "monthly_cost": 18.0,
        "hourly_cost": 0.027,
        "type": "vhp",
        "locations": ["ewr", "atl", "sea", "lax"],
    },
]

DEFAULT_REGIONS: list[dict[str, Any]] = [
    {
        "id": "ewr",
        "city": "New Jersey",
        "country": "US",
        "continent": "North America",
        "options": ["ddos_protection", "block_storage_high_perf", "kubernetes"],
    },
    {
        "id": "atl",
        "city": "Atlanta",
        "country": "US",
        "continent": "North America",
        "options": ["ddos_protection", "block_storage_high_perf", "kubernetes"],
    },
    {
        "id": "sea",
        "city": "Seattle",
        "country": "US",
        "continent": "North America",
        "options": ["ddos_protection", "block_storage_high_perf", "kubernetes"],
    },
    {
        "id": "lax",
        "city": "Los Angeles",
        "country": "US",
        "continent": "North America",
        "options": ["ddos_protection", "block_storage_high_perf", "kubernetes"],
    },
]

DEFAULT_OS: list[dict[str, Any]] = [
    {"id": 2284, "name": "Ubuntu 24.04 LTS x64", "arch": "x64", "family": "ubuntu"},
    {"id": 2136, "name": "Debian 12 x64 (bookworm)", "arch": "x64", "family": "debian"},
    {"id": 164, "name": "Snapshot", "arch": "x64", "family": "snapshot"},
]


@dataclass
class CallRecord:
    method: str
    path: str
    query: dict[str, str]
    body: Any
    status: int


@dataclass
class MockInstance:
    id: str
    label: str
    plan: str
    region: str
    os_id: int
    tags: list[str]
    hostname: str
    user_data_b64: str | None
    firewall_group_id: str | None
    date_created: datetime
    polls: int = 0
    deleted: bool = False
    snapshot_id: str | None = None

    def to_api(self, active: bool) -> dict[str, Any]:
        return {
            "id": self.id,
            "os": "Ubuntu 24.04 LTS x64",
            "ram": 8192,
            "disk": 80,
            "main_ip": "203.0.113.42" if active else "0.0.0.0",
            "vcpu_count": 2,
            "region": self.region,
            "plan": self.plan,
            "date_created": self.date_created.isoformat().replace("+00:00", "Z"),
            "status": "active" if active else "pending",
            "allowed_bandwidth": 4096,
            "netmask_v4": "255.255.254.0",
            "gateway_v4": "203.0.113.1",
            "power_status": "running" if active else "stopped",
            "server_status": "ok" if active else "installingbooting",
            "v6_network": "",
            "v6_main_ip": "",
            "v6_network_size": 0,
            "label": self.label,
            "internal_ip": "",
            "kvm": "",
            "hostname": self.hostname,
            "tag": self.tags[0] if self.tags else "",
            "tags": list(self.tags),
            "os_id": self.os_id,
            "app_id": 0,
            "image_id": "",
            "firewall_group_id": self.firewall_group_id or "",
            "features": [],
            "user_scheme": "root",
        }


@dataclass
class MockVultrState:
    api_key: str = MOCK_API_KEY
    activate_after_polls: int = 2  # GET /instances/{id} calls before status flips to active
    instances: dict[str, MockInstance] = field(default_factory=dict)
    firewall_groups: dict[str, dict[str, Any]] = field(default_factory=dict)
    firewall_rules: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    object_storages: dict[str, dict[str, Any]] = field(default_factory=dict)
    plans: list[dict[str, Any]] = field(default_factory=lambda: [dict(p) for p in DEFAULT_PLANS])
    regions: list[dict[str, Any]] = field(default_factory=lambda: [dict(r) for r in DEFAULT_REGIONS])
    os_list: list[dict[str, Any]] = field(default_factory=lambda: [dict(o) for o in DEFAULT_OS])
    calls: list[CallRecord] = field(default_factory=list)
    _faults: list[dict[str, Any]] = field(default_factory=list)
    _rule_seq: int = 0
    now: datetime | None = None  # override "current time" for date_created (orphan tests)

    # ---- helpers for tests
    def fail_next(self, status: int, times: int = 1, method: str | None = None, path_prefix: str = "") -> None:
        self._faults.append({"status": status, "times": times, "method": method, "path_prefix": path_prefix})

    def _pop_fault(self, method: str, path: str) -> int | None:
        for f in self._faults:
            if f["times"] <= 0:
                continue
            if f["method"] and f["method"] != method:
                continue
            if not path.startswith(f["path_prefix"]):
                continue
            f["times"] -= 1
            return int(f["status"])
        return None

    def calls_for(self, method: str, path_prefix: str = "") -> list[CallRecord]:
        return [c for c in self.calls if c.method == method and c.path.startswith(path_prefix)]

    def live_instances(self) -> list[MockInstance]:
        return [i for i in self.instances.values() if not i.deleted]

    def activate_all(self) -> None:
        for i in self.instances.values():
            i.polls = max(i.polls, self.activate_after_polls)

    def _is_active(self, inst: MockInstance) -> bool:
        return inst.polls >= self.activate_after_polls

    def _now(self) -> datetime:
        return self.now or datetime.now(timezone.utc)


def create_mock_app(state: MockVultrState | None = None) -> FastAPI:
    state = state or MockVultrState()
    app = FastAPI(title="mock-vultr-v2")
    app.state.vultr = state

    @app.middleware("http")
    async def _record_and_fault(request: Request, call_next):  # type: ignore[no-untyped-def]
        path = request.url.path
        if path.startswith("/v2"):
            path = path[3:]
        body: Any = None
        raw = await request.body()
        if raw:
            try:
                import json

                body = json.loads(raw)
            except ValueError:
                body = raw.decode("utf-8", "replace")
        auth = request.headers.get("authorization", "")
        if auth != f"Bearer {state.api_key}":
            state.calls.append(CallRecord(request.method, path, dict(request.query_params), body, 401))
            return JSONResponse({"error": "Invalid API token.", "status": 401}, status_code=401)
        fault = state._pop_fault(request.method, path)
        if fault is not None:
            state.calls.append(CallRecord(request.method, path, dict(request.query_params), body, fault))
            headers = {"Retry-After": "1"} if fault == 429 else {}
            return JSONResponse({"error": f"injected {fault}", "status": fault}, status_code=fault, headers=headers)
        response = await call_next(request)
        state.calls.append(CallRecord(request.method, path, dict(request.query_params), body, response.status_code))
        return response

    def _meta(n: int) -> dict[str, Any]:
        return {"total": n, "links": {"next": "", "prev": ""}}

    # ---- catalogue
    @app.get("/v2/regions")
    async def regions() -> dict[str, Any]:
        return {"regions": state.regions, "meta": _meta(len(state.regions))}

    @app.get("/v2/plans")
    async def plans(type: str | None = None) -> dict[str, Any]:
        items = [p for p in state.plans if not type or p["type"] == type]
        return {"plans": items, "meta": _meta(len(items))}

    @app.get("/v2/os")
    async def os_list() -> dict[str, Any]:
        return {"os": state.os_list, "meta": _meta(len(state.os_list))}

    # ---- instances
    @app.post("/v2/instances", status_code=202)
    async def create_instance(body: dict[str, Any]) -> dict[str, Any]:
        for key in ("region", "plan"):
            if key not in body:
                return JSONResponse({"error": f"{key} is required", "status": 400}, status_code=400)  # type: ignore[return-value]
        if "os_id" not in body and "snapshot_id" not in body and "image_id" not in body:
            return JSONResponse(
                {"error": "os_id, snapshot_id or image_id is required", "status": 400},  # type: ignore[return-value]
                status_code=400,
            )
        if not any(r["id"] == body["region"] for r in state.regions):
            return JSONResponse({"error": "Invalid region", "status": 400}, status_code=400)  # type: ignore[return-value]
        if not any(p["id"] == body["plan"] for p in state.plans):
            return JSONResponse({"error": "Invalid plan", "status": 400}, status_code=400)  # type: ignore[return-value]
        ud = body.get("user_data")
        if ud is not None:
            try:
                base64.b64decode(ud, validate=True)
            except Exception:
                return JSONResponse({"error": "user_data must be base64", "status": 400}, status_code=400)  # type: ignore[return-value]
        inst = MockInstance(
            id=str(uuid.uuid4()),
            label=body.get("label", ""),
            plan=body["plan"],
            region=body["region"],
            os_id=int(body.get("os_id") or 164),
            tags=list(body.get("tags") or []),
            hostname=body.get("hostname", ""),
            user_data_b64=ud,
            firewall_group_id=body.get("firewall_group_id"),
            date_created=state._now(),
            snapshot_id=body.get("snapshot_id"),
        )
        state.instances[inst.id] = inst
        return {"instance": inst.to_api(active=False) | {"default_password": "mock-password"}}

    @app.get("/v2/instances")
    async def list_instances(tag: str | None = None, label: str | None = None) -> dict[str, Any]:
        items = []
        for inst in state.live_instances():
            if tag and tag not in inst.tags:
                continue
            if label and label != inst.label:
                continue
            items.append(inst.to_api(state._is_active(inst)))
        return {"instances": items, "meta": _meta(len(items))}

    @app.get("/v2/instances/{instance_id}")
    async def get_instance(instance_id: str) -> Any:
        inst = state.instances.get(instance_id)
        if inst is None or inst.deleted:
            return JSONResponse({"error": "Invalid server.", "status": 404}, status_code=404)
        inst.polls += 1
        return {"instance": inst.to_api(state._is_active(inst))}

    @app.delete("/v2/instances/{instance_id}", status_code=204, response_model=None)
    async def delete_instance(instance_id: str) -> Any:
        inst = state.instances.get(instance_id)
        if inst is None or inst.deleted:
            return JSONResponse({"error": "Invalid server.", "status": 404}, status_code=404)
        inst.deleted = True
        return Response(status_code=204)

    # ---- firewall
    @app.post("/v2/firewalls", status_code=201)
    async def create_firewall(body: dict[str, Any]) -> dict[str, Any]:
        gid = str(uuid.uuid4())
        group = {
            "id": gid,
            "description": body.get("description", ""),
            "date_created": state._now().isoformat(),
            "date_modified": state._now().isoformat(),
            "instance_count": 0,
            "rule_count": 0,
            "max_rule_count": 50,
        }
        state.firewall_groups[gid] = group
        state.firewall_rules[gid] = []
        return {"firewall_group": group}

    @app.delete("/v2/firewalls/{gid}", status_code=204, response_model=None)
    async def delete_firewall(gid: str) -> Any:
        if gid not in state.firewall_groups:
            return JSONResponse({"error": "not found", "status": 404}, status_code=404)
        del state.firewall_groups[gid]
        state.firewall_rules.pop(gid, None)
        return Response(status_code=204)

    @app.post("/v2/firewalls/{gid}/rules", status_code=201)
    async def create_rule(gid: str, body: dict[str, Any]) -> Any:
        if gid not in state.firewall_groups:
            return JSONResponse({"error": "not found", "status": 404}, status_code=404)
        state._rule_seq += 1
        rule = {
            "id": state._rule_seq,
            "ip_type": body.get("ip_type", "v4"),
            "action": "accept",
            "protocol": body.get("protocol", "tcp"),
            "port": body.get("port", ""),
            "subnet": body.get("subnet", ""),
            "subnet_size": body.get("subnet_size", 0),
            "source": body.get("source", ""),
            "notes": body.get("notes", ""),
        }
        state.firewall_rules[gid].append(rule)
        state.firewall_groups[gid]["rule_count"] += 1
        return {"firewall_rule": rule}

    @app.get("/v2/firewalls/{gid}/rules")
    async def list_rules(gid: str) -> Any:
        if gid not in state.firewall_groups:
            return JSONResponse({"error": "not found", "status": 404}, status_code=404)
        rules = state.firewall_rules[gid]
        return {"firewall_rules": rules, "meta": _meta(len(rules))}

    # ---- object storage (minimal)
    @app.get("/v2/object-storage")
    async def list_object_storage() -> dict[str, Any]:
        items = list(state.object_storages.values())
        return {"object_storages": items, "meta": _meta(len(items))}

    @app.post("/v2/object-storage", status_code=202)
    async def create_object_storage(body: dict[str, Any]) -> dict[str, Any]:
        sid = str(uuid.uuid4())
        obj = {
            "id": sid,
            "date_created": state._now().isoformat(),
            "cluster_id": int(body.get("cluster_id", 2)),
            "region": "ewr",
            "label": body.get("label", ""),
            "status": "active",
            "s3_hostname": "ewr1.vultrobjects.com",
            "s3_access_key": "MOCKACCESSKEY",
            "s3_secret_key": "MOCKSECRETKEY",
        }
        state.object_storages[sid] = obj
        return {"object_storage": obj}

    @app.get("/v2/object-storage/{sid}")
    async def get_object_storage(sid: str) -> Any:
        obj = state.object_storages.get(sid)
        if obj is None:
            return JSONResponse({"error": "not found", "status": 404}, status_code=404)
        return {"object_storage": obj}

    @app.get("/v2/account")
    async def account(authorization: str = Header(default="")) -> dict[str, Any]:
        return {
            "account": {
                "name": "mock",
                "email": "mock@example.com",
                "balance": -200.0,
                "pending_charges": 0.0,
                "acls": ["manage_users", "subscriptions"],
            }
        }

    return app


def age_instances(state: MockVultrState, by: timedelta) -> None:
    """Shift every instance's date_created into the past (orphan-cleanup tests)."""
    for inst in state.instances.values():
        inst.date_created = inst.date_created - by
