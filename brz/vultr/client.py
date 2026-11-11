"""Async client for the Vultr API v2 (https://api.vultr.com/v2).

Only the endpoints Ashproof needs. Every call goes through ``_request`` which
retries 429 / 5xx / transport errors with exponential backoff (govultr uses 3 retries,
500 ms base; we do the same by default). ``sleep`` is injectable so tests run instantly.

Behaviour of the live API that a mock would not show (instance limit, 409 on DELETE during
install, creates that must not be repeated) is handled here and pinned in tests/vultr/test_live_behaviour.py.
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from typing import Any

import httpx

from .models import (
    FirewallGroup,
    FirewallRule,
    FirewallRuleCreate,
    Instance,
    InstanceCreate,
    ObjectStorage,
    OperatingSystem,
    Plan,
    ProofOfDestruction,
    Region,
)

DEFAULT_BASE_URL = "https://api.vultr.com/v2"
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
CREATE_TIMEOUT_S = 90.0
CAPACITY_POLL_S = 10.0
BUSY_POLL_S = 2.0


class VultrError(Exception):
    def __init__(self, message: str, status: int | None = None, body: Any = None):
        super().__init__(message)
        self.status = status
        self.body = body


class VultrNotFound(VultrError):
    pass


class VultrRateLimited(VultrError):
    pass


class VultrTimeout(VultrError):
    pass


class VultrCapacity(VultrError):
    """The account is at its limit of active instances. Instances deleted moments ago still count for a while."""


class VultrBusy(VultrError):
    """HTTP 409: the instance is in a state that refuses this call, seen on DELETE while it is installing."""


SleepFn = Callable[[float], Awaitable[None]]
ClockFn = Callable[[], float]


class VultrClient:
    def __init__(
        self,
        api_key: str,
        base_url: str = DEFAULT_BASE_URL,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = 30.0,
        max_retries: int = 3,
        backoff_base: float = 0.5,
        sleep: SleepFn = asyncio.sleep,
        clock: ClockFn = time.monotonic,
    ):
        if not api_key:
            raise ValueError("VULTR_API_KEY is required")
        self._http = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {api_key}", "Accept": "application/json"},
            timeout=timeout,
            transport=transport,
        )
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self._sleep = sleep
        self._clock = clock
        self.retry_count = 0  # total retries performed (exposed for tests / metrics)

    async def aclose(self) -> None:
        await self._http.aclose()

    async def __aenter__(self) -> VultrClient:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.aclose()

    # ----------------------------------------------------------------- core
    async def _request(
        self, method: str, path: str, *, expect_json: bool = True, retry_transport: bool = True, **kw: Any
    ) -> Any:
        attempt = 0
        while True:
            try:
                resp = await self._http.request(method, path, **kw)
            except httpx.TransportError as exc:
                if attempt >= self.max_retries or not retry_transport:
                    raise VultrError(f"{method} {path}: transport error {exc!r}") from exc
                attempt += 1
                self.retry_count += 1
                await self._sleep(self.backoff_base * (2 ** (attempt - 1)))
                continue

            if resp.status_code in RETRY_STATUSES and attempt < self.max_retries:
                attempt += 1
                self.retry_count += 1
                delay = self.backoff_base * (2 ** (attempt - 1))
                retry_after = resp.headers.get("Retry-After")
                if retry_after and retry_after.isdigit():
                    delay = max(delay, float(retry_after))
                await self._sleep(delay)
                continue

            if resp.status_code == 404:
                raise VultrNotFound(f"{method} {path}: 404", 404, _safe_json(resp))
            if resp.status_code == 429:
                raise VultrRateLimited(f"{method} {path}: 429 rate limited", 429, _safe_json(resp))
            if resp.status_code >= 400:
                body = _safe_json(resp)
                detail = body.get("error", "") if isinstance(body, dict) else str(body)
                message = f"{method} {path}: HTTP {resp.status_code}: {str(detail)[:200]}"
                if resp.status_code == 400 and "maximum number of active instances" in str(detail):
                    raise VultrCapacity(message, 400, body)
                if resp.status_code == 409:
                    raise VultrBusy(message, 409, body)
                raise VultrError(message, resp.status_code, body)
            if resp.status_code == 204 or not expect_json or not resp.content:
                return None
            return resp.json()

    async def _paginate(self, path: str, key: str, params: dict[str, Any] | None = None) -> list[dict]:
        """Follow ``meta.links.next`` cursors (Vultr v2 pagination)."""
        items: list[dict] = []
        params = dict(params or {})
        params.setdefault("per_page", 100)
        cursor = ""
        for _ in range(100):  # hard stop against a buggy cursor loop
            if cursor:
                params["cursor"] = cursor
            data = await self._request("GET", path, params=params)
            items.extend(data.get(key, []))
            cursor = (data.get("meta") or {}).get("links", {}).get("next", "") or ""
            if not cursor:
                break
        return items

    # ------------------------------------------------------------ catalogue
    async def list_regions(self) -> list[Region]:
        return [Region.model_validate(r) for r in await self._paginate("/regions", "regions")]

    async def list_plans(self, plan_type: str | None = None) -> list[Plan]:
        params = {"type": plan_type} if plan_type else None
        return [Plan.model_validate(p) for p in await self._paginate("/plans", "plans", params)]

    async def list_os(self) -> list[OperatingSystem]:
        return [OperatingSystem.model_validate(o) for o in await self._paginate("/os", "os")]

    # ------------------------------------------------------------ instances
    async def create_instance(self, spec: InstanceCreate, *, capacity_wait_s: float = 0.0) -> Instance:
        """Create once. A create is not idempotent: after a timeout the VM may exist, so look for it by label
        instead of sending the POST again, which would leave a second billing VM nobody knows about."""
        deadline = self._clock() + capacity_wait_s
        while True:
            try:
                data = await self._request(
                    "POST", "/instances", json=spec.to_api_body(), retry_transport=False, timeout=CREATE_TIMEOUT_S
                )
                return Instance.model_validate(data["instance"])
            except VultrCapacity:
                if self._clock() >= deadline:
                    raise
                await self._sleep(CAPACITY_POLL_S)
            except VultrError as exc:
                if exc.status is not None or not spec.label:
                    raise
                found = await self.list_instances(label=spec.label)
                if found:
                    return found[0]
                raise

    async def get_instance(self, instance_id: str) -> Instance:
        data = await self._request("GET", f"/instances/{instance_id}")
        return Instance.model_validate(data["instance"])

    async def delete_instance(self, instance_id: str) -> None:
        await self._request("DELETE", f"/instances/{instance_id}", expect_json=False)

    async def list_instances(self, tag: str | None = None, label: str | None = None) -> list[Instance]:
        params: dict[str, Any] = {}
        if tag:
            params["tag"] = tag
        if label:
            params["label"] = label
        found = [Instance.model_validate(i) for i in await self._paginate("/instances", "instances", params)]
        # The API has answered ``?tag=`` with every instance on the account (seen 2026-11-11),
        # so the filter is applied again here and never left to the server alone.
        if tag:
            found = [i for i in found if tag in i.tags]
        if label:
            found = [i for i in found if i.label == label]
        return found

    async def wait_until_active(
        self,
        instance_id: str,
        *,
        timeout: float = 300.0,
        interval: float = 5.0,
        require_server_ok: bool = True,
    ) -> Instance:
        """Poll GET /v2/instances/{id} until status=active & power_status=running (& server_status ok)."""
        deadline = self._clock() + timeout
        last: Instance | None = None
        while True:
            last = await self.get_instance(instance_id)
            ready = last.is_ready if require_server_ok else last.is_active
            if ready and last.main_ip not in ("", "0.0.0.0"):
                return last
            if self._clock() >= deadline:
                raise VultrTimeout(
                    f"instance {instance_id} not active after {timeout}s "
                    f"(status={last.status} power={last.power_status} server={last.server_status})"
                )
            await self._sleep(interval)

    async def confirm_destroyed(
        self,
        instance_id: str,
        *,
        timeout: float = 120.0,
        interval: float = 3.0,
    ) -> ProofOfDestruction:
        """After DELETE, poll until GET returns 404. The 404 timestamp is the proof in the receipt."""
        deadline = self._clock() + timeout
        attempts = 0
        while True:
            attempts += 1
            try:
                await self.get_instance(instance_id)
            except VultrNotFound:
                return ProofOfDestruction(
                    instance_id=instance_id,
                    http_status=404,
                    observed_at=datetime.now(timezone.utc),
                    attempts=attempts,
                )
            if self._clock() >= deadline:
                return ProofOfDestruction(
                    instance_id=instance_id,
                    http_status=200,
                    observed_at=datetime.now(timezone.utc),
                    attempts=attempts,
                )
            await self._sleep(interval)

    async def destroy_and_confirm(
        self, instance_id: str, *, busy_wait_s: float = 120.0, **kw: Any
    ) -> ProofOfDestruction:
        deadline = self._clock() + busy_wait_s
        while True:
            try:
                await self.delete_instance(instance_id)
                break
            except VultrNotFound:
                break
            except VultrBusy:  # still installing: Vultr refuses the delete until it can act on it
                if self._clock() >= deadline:
                    raise
                await self._sleep(BUSY_POLL_S)
        return await self.confirm_destroyed(instance_id, **kw)

    async def cleanup_orphans(
        self,
        tag: str,
        *,
        older_than_seconds: float,
        now: datetime | None = None,
    ) -> list[str]:
        """Delete every instance carrying ``tag`` whose date_created is older than the TTL.

        This is the safety net for crashed control planes: a cron job calls it with the
        sandbox tag so no throwaway VM outlives its task budget.

        An instance is deleted only if its own ``tags`` contain ``tag``. The check is made on
        each returned instance: a server that ignores the ``tag`` query returns the whole
        account, and deleting from that list destroyed two unrelated VMs.
        """
        if not tag:
            raise ValueError("cleanup_orphans needs a tag")
        now = now or datetime.now(timezone.utc)
        deleted: list[str] = []
        for inst in await self.list_instances(tag=tag):
            if tag not in inst.tags:
                continue
            if inst.date_created is None:
                continue
            created = inst.date_created
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            age = (now - created).total_seconds()
            if age >= older_than_seconds:
                try:
                    await self.delete_instance(inst.id)
                except VultrNotFound:
                    pass
                deleted.append(inst.id)
        return deleted

    # ------------------------------------------------------------- firewall
    async def create_firewall_group(self, description: str) -> FirewallGroup:
        data = await self._request("POST", "/firewalls", json={"description": description})
        return FirewallGroup.model_validate(data["firewall_group"])

    async def delete_firewall_group(self, group_id: str) -> None:
        await self._request("DELETE", f"/firewalls/{group_id}", expect_json=False)

    async def create_firewall_rule(self, group_id: str, rule: FirewallRuleCreate) -> FirewallRule:
        data = await self._request("POST", f"/firewalls/{group_id}/rules", json=rule.model_dump())
        return FirewallRule.model_validate(data["firewall_rule"])

    async def list_firewall_rules(self, group_id: str) -> list[FirewallRule]:
        items = await self._paginate(f"/firewalls/{group_id}/rules", "firewall_rules")
        return [FirewallRule.model_validate(r) for r in items]

    async def create_inbound_only_group(
        self, description: str, control_plane_ip: str, runner_port: int
    ) -> FirewallGroup:
        """Firewall group that lets ONLY the control plane reach the runner port. No SSH, no ICMP.

        Outbound default-deny is NOT done here (Vultr groups are inbound-only); nftables
        inside the VM does that, see brz/sandbox/templates/cloud-init.yaml.tmpl.
        """
        group = await self.create_firewall_group(description)
        await self.create_firewall_rule(
            group.id,
            FirewallRuleCreate(
                ip_type="v4",
                protocol="tcp",
                subnet=control_plane_ip,
                subnet_size=32,
                port=str(runner_port),
                notes="brz control plane -> runner",
            ),
        )
        return group

    # ------------------------------------------------------- object storage
    # Not used yet and never run against the live API. Shapes copied from the v2 reference.
    # (Object Storage itself is S3-compatible; uploads will use the S3 keys returned here).
    async def list_object_storage(self) -> list[ObjectStorage]:
        items = await self._paginate("/object-storage", "object_storages")
        return [ObjectStorage.model_validate(o) for o in items]

    async def create_object_storage(self, cluster_id: int, label: str) -> ObjectStorage:
        data = await self._request("POST", "/object-storage", json={"cluster_id": cluster_id, "label": label})
        return ObjectStorage.model_validate(data["object_storage"])

    async def get_object_storage(self, storage_id: str) -> ObjectStorage:
        data = await self._request("GET", f"/object-storage/{storage_id}")
        return ObjectStorage.model_validate(data["object_storage"])


def _safe_json(resp: httpx.Response) -> Any:
    try:
        return resp.json()
    except ValueError:
        return resp.text
