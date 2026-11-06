"""Dependency wiring for the control plane.

``BRZ_MODE=live`` (default when ``VULTR_API_KEY`` is set): real Vultr API + Vultr Serverless
Inference (planner ``glm-5.3``, verifier ``qwen3.8-27b``, content filter ``nemotron-3.5-content-safety``).
``BRZ_MODE=mock`` (default otherwise): in-process mock Vultr + local runner + demo FakeLLM, so
the whole product runs on a laptop with zero credentials.

Environment variables (live mode):
    VULTR_API_KEY, VULTR_REGION, VULTR_PLAN, VULTR_OS_ID, VULTR_SNAPSHOT_ID, VULTR_FIREWALL_GROUP_ID,
    BRZ_CONTROL_PLANE_CIDR, BRZ_RUNNER_PORT, BRZ_SANDBOX_TTL_MINUTES, BRZ_INNER_ISOLATION (gvisor|none),
    INFERENCE_API_KEY, INFERENCE_BASE_URL, BRZ_PLANNER_MODEL, BRZ_VERIFIER_MODEL, BRZ_SAFETY_MODEL,
    BRZ_VERIFY_FRESH_SANDBOX (1|0),
    BRZ_REASONING_EFFORT (default low; the default of the models themselves is too slow and can return nothing),
    BRZ_PARALLEL_VERIFIER_BOOT (1|0), BRZ_MAX_STEP_TIMEOUT_S, BRZ_APPROVAL_TIMEOUT_S
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass

import httpx

from brz.cost import LivePriceTable, StaticPriceTable
from brz.llm import VULTR_INFERENCE_BASE_URL, ChatClient, FakeLLM, Planner, Verifier
from brz.llm.client import DEFAULT_REASONING_EFFORT
from brz.llm.safety import SafetyReviewer
from brz.orchestrator import Orchestrator, OrchestratorConfig
from brz.sandbox.backends import LocalRunnerVultrBackend, SandboxBackend, VultrSandboxBackend, VultrSandboxConfig
from brz.vultr import VultrClient
from brz.vultr.mock import MOCK_API_KEY, MockVultrState, create_mock_app

from .demo import demo_responder


@dataclass
class Deps:
    orchestrator: Orchestrator
    backend: SandboxBackend
    mode: str
    mock_state: MockVultrState | None = None
    llm_clients: list[ChatClient] | None = None

    async def refresh_prices(self) -> str:
        """Live mode: load real prices. On failure keep the static table, and the receipt will say so."""
        if self.mode != "live":
            return self.orchestrator.prices.source
        try:
            plans = await self.backend.client.list_plans()  # type: ignore[attr-defined]
            async with httpx.AsyncClient(timeout=30) as http:
                base = os.environ.get("INFERENCE_BASE_URL", VULTR_INFERENCE_BASE_URL).rstrip("/")
                key = os.environ.get("INFERENCE_API_KEY", "")
                resp = await http.get(f"{base}/models", headers={"Authorization": f"Bearer {key}"})
                resp.raise_for_status()
            self.orchestrator.prices = LivePriceTable.from_payloads(
                [p.model_dump() for p in plans], resp.json().get("data", [])
            )
        except Exception as exc:  # noqa: BLE001 - never block start-up on a price feed
            logging.getLogger("brz").warning("live prices unavailable: %s", type(exc).__name__)
        return self.orchestrator.prices.source

    async def aclose(self) -> None:
        await self.backend.aclose()
        for c in self.llm_clients or []:
            await c.aclose()


def _env_bool(name: str, default: bool) -> bool:
    v = os.environ.get(name)
    return default if v is None else v.strip().lower() in ("1", "true", "yes", "on")


def sandbox_config_from_env() -> VultrSandboxConfig:
    return VultrSandboxConfig(
        region=os.environ.get("VULTR_REGION", "ewr"),
        plan=os.environ.get("VULTR_PLAN", "vhp-1c-1gb-amd"),
        os_id=int(os.environ["VULTR_OS_ID"]) if os.environ.get("VULTR_OS_ID") else 2284,
        snapshot_id=os.environ.get("VULTR_SNAPSHOT_ID") or None,
        firewall_group_id=os.environ.get("VULTR_FIREWALL_GROUP_ID") or None,
        control_plane_cidr=os.environ.get("BRZ_CONTROL_PLANE_CIDR", "0.0.0.0/0"),
        runner_port=int(os.environ.get("BRZ_RUNNER_PORT", "8700")),
        ttl_minutes=int(os.environ.get("BRZ_SANDBOX_TTL_MINUTES", "20")),
        inner_isolation=os.environ.get("BRZ_INNER_ISOLATION", "gvisor"),
        sshkey_ids=[k for k in os.environ.get("BRZ_DEBUG_SSHKEY_ID", "").split(",") if k],
        admin_cidr=os.environ.get("BRZ_ADMIN_CIDR") or None,
    )


def build_mock_deps(*, verify_fresh: bool = True, mock_state: MockVultrState | None = None) -> Deps:
    state = mock_state or MockVultrState(activate_after_polls=1)
    app = create_mock_app(state)
    client = VultrClient(MOCK_API_KEY, base_url="http://mock-vultr/v2", transport=httpx.ASGITransport(app=app))
    cfg = sandbox_config_from_env()
    cfg.inner_isolation = "none"
    cfg.vm_poll_interval_s = 0.01
    backend = LocalRunnerVultrBackend(client, cfg)
    llm = FakeLLM(demo_responder, model="demo-fake-llm")
    orch = Orchestrator(
        planner=Planner(llm),
        verifier=Verifier(FakeLLM(demo_responder, model="demo-fake-verifier")),
        backend=backend,
        prices=StaticPriceTable(),
        config=OrchestratorConfig(verify_in_fresh_sandbox=verify_fresh, runner_ready_interval_s=0.05),
    )
    return Deps(orchestrator=orch, backend=backend, mode="mock", mock_state=state)


def build_live_deps() -> Deps:
    api_key = os.environ["VULTR_API_KEY"]
    inference_key = os.environ.get("INFERENCE_API_KEY", "")
    base_url = os.environ.get("INFERENCE_BASE_URL", VULTR_INFERENCE_BASE_URL)
    planner_model = os.environ.get("BRZ_PLANNER_MODEL", "glm-5.3")
    verifier_model = os.environ.get("BRZ_VERIFIER_MODEL", "qwen3.8-27b")
    effort = os.environ.get("BRZ_REASONING_EFFORT", DEFAULT_REASONING_EFFORT) or None
    planner_llm = ChatClient(base_url, inference_key, planner_model, reasoning_effort=effort)
    verifier_llm = ChatClient(base_url, inference_key, verifier_model, reasoning_effort=effort)
    safety_model = os.environ.get("BRZ_SAFETY_MODEL", "nemotron-3.5-content-safety")  # empty turns it off
    safety_llm = ChatClient(base_url, inference_key, safety_model, timeout=30.0) if safety_model else None
    backend = VultrSandboxBackend(VultrClient(api_key), sandbox_config_from_env())
    orch = Orchestrator(
        planner=Planner(planner_llm),
        verifier=Verifier(verifier_llm, safety=SafetyReviewer(safety_llm) if safety_llm else None),
        backend=backend,
        prices=StaticPriceTable(),  # replaced by Deps.refresh_prices() when the app starts
        config=OrchestratorConfig(
            verify_in_fresh_sandbox=_env_bool("BRZ_VERIFY_FRESH_SANDBOX", True),
            planner_model_label=planner_model,
            verifier_model_label=verifier_model,
            parallel_verifier_boot=_env_bool("BRZ_PARALLEL_VERIFIER_BOOT", True),
            max_step_timeout_s=int(os.environ.get("BRZ_MAX_STEP_TIMEOUT_S", "1800")),
            approval_timeout_s=float(os.environ.get("BRZ_APPROVAL_TIMEOUT_S", "900")),
        ),
    )
    clients = [c for c in (planner_llm, verifier_llm, safety_llm) if c]
    return Deps(orchestrator=orch, backend=backend, mode="live", llm_clients=clients)


def build_deps_from_env() -> Deps:
    mode = os.environ.get("BRZ_MODE") or ("live" if os.environ.get("VULTR_API_KEY") else "mock")
    if mode == "live":
        return build_live_deps()
    return build_mock_deps()
