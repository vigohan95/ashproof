"""Sandbox backends: how the orchestrator gets (and destroys) a throwaway VM.

* :class:`VultrSandboxBackend` - the real thing: ``POST /v2/instances`` with the rendered
  cloud-init, wait until active, runner at ``http://<main_ip>:<port>``, ``DELETE`` + GET-404
  proof at the end. Works against the live API and against :mod:`brz.vultr.mock` alike.
* :class:`LocalRunnerVultrBackend` - test/offline-demo variant: same Vultr lifecycle (through
  the mock API) but the runner is an in-process :class:`brz_runner.server.BackgroundRunner`
  executing steps as local subprocesses, since no VM exists to receive the cloud-init.
"""

from __future__ import annotations

import os
import sys
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Protocol

from brz_runner.executor import SubprocessExecutor
from brz_runner.netlog import EgressReader, NullEgressReader
from brz_runner.server import BackgroundRunner, RunnerConfig
from brz_runner.tokens import new_key

from brz.vultr import InstanceCreate, ProofOfDestruction, VultrClient

from .cloudinit import SandboxSpec, render_cloud_init

SANDBOX_TAG = "brz-sandbox"


@dataclass
class SandboxHandle:
    role: str  # "primary" | "verifier"
    task_id: str
    instance_id: str
    runner_url: str
    token_key: bytes
    plan: str = ""
    region: str = ""
    created_at: datetime | None = None
    active_at: datetime | None = None
    destroyed_at: datetime | None = None
    proof: ProofOfDestruction | None = None
    meta: dict[str, Any] = field(default_factory=dict)

    def lifetime_seconds(self, now: datetime | None = None) -> float:
        if self.created_at is None:
            return 0.0
        end = self.destroyed_at or now or datetime.now(timezone.utc)
        return max((end - self.created_at).total_seconds(), 0.0)


@dataclass
class VultrSandboxConfig:
    region: str = "ewr"
    plan: str = "vhp-1c-1gb-amd"
    os_id: int | None = 2284  # Ubuntu 24.04 LTS x64 (confirm id via GET /v2/os on event day)
    snapshot_id: str | None = None  # pre-baked image: packages + runsc preinstalled
    firewall_group_id: str | None = None
    control_plane_cidr: str = "0.0.0.0/0"
    runner_port: int = 8700
    ttl_minutes: int = 20
    dns_server: str = "1.1.1.1"
    inner_isolation: str = "gvisor"
    vm_active_timeout_s: float = 300.0
    vm_poll_interval_s: float = 5.0
    destroy_confirm_timeout_s: float = 120.0
    extra_tags: list[str] = field(default_factory=list)
    # Debug door, off by default: SSH into the sandbox from one address. Recorded on every VM it applies to.
    sshkey_ids: list[str] = field(default_factory=list)
    admin_cidr: str | None = None


class SandboxBackend(Protocol):
    provider: str
    inner_isolation: str

    async def provision(self, task_id: str, role: str, allowed_domains: list[str]) -> SandboxHandle: ...

    async def destroy(self, handle: SandboxHandle) -> ProofOfDestruction: ...

    async def aclose(self) -> None: ...


class VultrSandboxBackend:
    provider = "vultr"

    def __init__(self, client: VultrClient, config: VultrSandboxConfig | None = None):
        self.client = client
        self.config = config or VultrSandboxConfig()
        self.inner_isolation = (
            "gvisor runsc --platform=systrap" if self.config.inner_isolation == "gvisor" else "none (subprocess)"
        )
        self.user_data_cache: dict[str, str] = {}  # instance id -> rendered cloud-init (for the audit)

    def _spec(self, task_id: str, allowed_domains: list[str], token_key: bytes) -> SandboxSpec:
        c = self.config
        return SandboxSpec(
            task_id=task_id,
            token_key=token_key,
            allowed_domains=allowed_domains,
            control_plane_cidr=c.control_plane_cidr,
            runner_port=c.runner_port,
            ttl_minutes=c.ttl_minutes,
            dns_server=c.dns_server,
            inner_isolation=c.inner_isolation,
            admin_cidr=c.admin_cidr,
        )

    def _instance_spec(self, task_id: str, role: str, user_data: str) -> InstanceCreate:
        c = self.config
        return InstanceCreate(
            region=c.region,
            plan=c.plan,
            os_id=None if c.snapshot_id else c.os_id,
            snapshot_id=c.snapshot_id,
            label=f"brz-{task_id[:24]}-{role}",
            hostname=f"brz-{task_id.lower()[:40]}",
            tags=[SANDBOX_TAG, f"task-{task_id}", f"role-{role}", *c.extra_tags],
            user_data=user_data,
            firewall_group_id=c.firewall_group_id,
            sshkey_id=list(c.sshkey_ids),
        )

    async def provision(self, task_id: str, role: str, allowed_domains: list[str]) -> SandboxHandle:
        key = new_key()
        user_data = render_cloud_init(self._spec(task_id, allowed_domains, key))
        inst = await self.client.create_instance(self._instance_spec(task_id, role, user_data))
        handle = SandboxHandle(
            role=role,
            task_id=task_id,
            instance_id=inst.id,
            runner_url="",
            token_key=key,
            plan=inst.plan,
            region=inst.region,
            created_at=datetime.now(timezone.utc),
            meta={
                "label": inst.label,
                "tags": inst.tags,
                "user_data_bytes": len(user_data),
                "admin_access": bool(self.config.admin_cidr or self.config.sshkey_ids),
            },
        )
        self.user_data_cache[inst.id] = user_data
        active = await self.client.wait_until_active(
            inst.id, timeout=self.config.vm_active_timeout_s, interval=self.config.vm_poll_interval_s
        )
        handle.active_at = datetime.now(timezone.utc)
        handle.runner_url = f"http://{active.main_ip}:{self.config.runner_port}"
        handle.meta["main_ip"] = active.main_ip
        return handle

    async def destroy(self, handle: SandboxHandle) -> ProofOfDestruction:
        proof = await self.client.destroy_and_confirm(handle.instance_id, timeout=self.config.destroy_confirm_timeout_s)
        handle.destroyed_at = proof.observed_at
        handle.proof = proof
        return proof

    async def sweep_orphans(self, older_than_seconds: float) -> list[str]:
        return await self.client.cleanup_orphans(SANDBOX_TAG, older_than_seconds=older_than_seconds)

    async def aclose(self) -> None:
        await self.client.aclose()


class LocalRunnerVultrBackend(VultrSandboxBackend):
    """Mock-Vultr lifecycle + an in-process runner per 'VM' (tests, offline demo)."""

    provider = "mock-vultr"

    def __init__(
        self,
        client: VultrClient,
        config: VultrSandboxConfig | None = None,
        *,
        workroot: str | None = None,
        egress_reader_factory=None,
        python_bin: str = sys.executable,
    ):
        super().__init__(client, config)
        self.inner_isolation = "none (local subprocess; mock backend)"
        self.workroot = workroot or tempfile.mkdtemp(prefix="brz-local-")
        self.egress_reader_factory = egress_reader_factory or (lambda role: NullEgressReader())
        self.python_bin = python_bin
        self.runners: dict[str, BackgroundRunner] = {}

    async def provision(self, task_id: str, role: str, allowed_domains: list[str]) -> SandboxHandle:
        handle = await super().provision(task_id, role, allowed_domains)
        work = os.path.join(self.workroot, task_id, role)
        os.makedirs(work, exist_ok=True)
        egress: EgressReader = self.egress_reader_factory(role)
        cfg = RunnerConfig(
            task_id=task_id,
            token_key=handle.token_key,
            executor=SubprocessExecutor(work, python_bin=self.python_bin),
            egress=egress,
            scan_paths=[work],
            scan_environ={"PATH": "/usr/bin", "HOME": work, "BRZ_WORK": work},
            host="127.0.0.1",
            port=0,
        )
        runner = BackgroundRunner(cfg).start()
        self.runners[handle.instance_id] = runner
        handle.runner_url = runner.url
        handle.meta["local_workroot"] = work
        return handle

    async def destroy(self, handle: SandboxHandle) -> ProofOfDestruction:
        runner = self.runners.pop(handle.instance_id, None)
        if runner is not None:
            runner.stop()
        return await super().destroy(handle)

    async def aclose(self) -> None:
        for runner in self.runners.values():
            runner.stop()
        self.runners.clear()
        await super().aclose()
