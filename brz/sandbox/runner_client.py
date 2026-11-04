"""Control-plane side client for the in-VM runner.

Signs one single-use capability token per request (``brz_runner.tokens``), talks plain HTTP
to the runner port (the VM's nftables + Vultr firewall group restrict who can reach it), and
converts replies into typed results. The same client is used against a real VM and against
the in-process :class:`brz_runner.server.BackgroundRunner` in tests.

Plain HTTP is safe to the extent that both directions are authenticated: exec tokens pin the
step body, and every successful reply must carry a MAC over the body and the request's token.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import hmac
import time
from typing import Any

import httpx
from brz_runner.tokens import reply_mac, sign_step_token, sign_token
from pydantic import BaseModel, Field

from brz.llm.planner import PlanStep


class RunnerFile(BaseModel):
    sha256: str
    size: int
    content: bytes | None = None


class RunnerStepResult(BaseModel):
    step_id: str
    exit_code: int
    stdout: str
    stderr: str
    stdout_sha256: str
    stderr_sha256: str
    duration_s: float
    timed_out: bool = False
    executor: str = ""
    error: str = ""
    files: dict[str, RunnerFile] = Field(default_factory=dict)
    egress_attempts: list[dict[str, Any]] = Field(default_factory=list)
    missing_expected_outputs: list[str] = Field(default_factory=list)
    skipped_outputs: list[dict[str, Any]] = Field(default_factory=list)
    secret_findings: list[dict[str, Any]] = Field(default_factory=list)
    stdout_truncated: bool = False
    stderr_truncated: bool = False

    @property
    def file_hashes(self) -> dict[str, str]:
        return {n: f.sha256 for n, f in sorted(self.files.items())}

    def file_text(self, name: str, limit: int = 4000) -> str:
        f = self.files.get(name)
        if f is None or f.content is None:
            return ""
        return f.content[:limit].decode("utf-8", "replace")


class RunnerError(Exception):
    def __init__(self, message: str, status: int | None = None, body: Any = None):
        super().__init__(message)
        self.status = status
        self.body = body


class RunnerClient:
    def __init__(
        self,
        base_url: str,
        *,
        task_id: str,
        token_key: bytes,
        token_ttl_s: int = 60,
        timeout: float = 600.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.task_id = task_id
        self._key = token_key
        self.token_ttl_s = token_ttl_s
        self._http = httpx.AsyncClient(base_url=self.base_url, timeout=timeout, transport=transport)
        self.tokens_issued = 0

    async def aclose(self) -> None:
        await self._http.aclose()

    def _token(self, action: str, step_id: str = "*") -> str:
        self.tokens_issued += 1
        return sign_token(self._key, task_id=self.task_id, scope=[action], step_id=step_id, ttl_s=self.token_ttl_s)

    async def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        try:
            resp = await self._http.post(path, json=body)
        except httpx.TransportError as exc:
            raise RunnerError(f"runner unreachable: {exc!r}") from exc
        data: Any
        try:
            data = resp.json()
        except ValueError:
            data = resp.text
        if resp.status_code >= 400:
            raise RunnerError(f"runner {path} -> {resp.status_code}: {data}", resp.status_code, data)
        expected = reply_mac(self._key, body["token"], resp.content)
        if not hmac.compare_digest(resp.headers.get("x-brz-reply-mac", ""), expected):
            raise RunnerError(f"runner {path}: reply failed authentication (MAC mismatch)", resp.status_code)
        return data

    # ---- API
    async def health(self) -> dict[str, Any]:
        resp = await self._http.get("/health")
        resp.raise_for_status()
        return resp.json()

    async def wait_ready(
        self, *, timeout: float = 240.0, interval: float = 3.0, sleep=asyncio.sleep, clock=time.monotonic
    ) -> dict[str, Any]:
        deadline = clock() + timeout
        last_err = ""
        while True:
            try:
                h = await self.health()
                if h.get("task_id") == self.task_id and h.get("ok"):
                    return h
                last_err = f"unexpected health: {h}"
            except (httpx.HTTPError, ValueError) as exc:
                last_err = repr(exc)
            if clock() >= deadline:
                raise RunnerError(f"runner not ready after {timeout}s: {last_err}")
            await sleep(interval)

    async def run_step(self, step: PlanStep, files: dict[str, bytes] | None = None) -> RunnerStepResult:
        payload = {
            "step_id": step.id,
            "kind": step.kind,
            "code": step.code,
            "files": {n: base64.b64encode(b).decode("ascii") for n, b in (files or {}).items()},
            "timeout_s": step.timeout_s,
            "expected_outputs": step.expected_outputs,
            "needs_network": step.needs_network,
        }
        self.tokens_issued += 1
        token = sign_step_token(self._key, task_id=self.task_id, step=payload, ttl_s=self.token_ttl_s)
        data = await self._post("/steps", {"token": token, "step": payload})
        files_out: dict[str, RunnerFile] = {}
        for name, meta in (data.get("files") or {}).items():
            content = base64.b64decode(meta["content_b64"]) if meta.get("content_b64") else None
            if content is not None and hashlib.sha256(content).hexdigest() != meta["sha256"]:
                raise RunnerError(f"runner file {name} hash mismatch in transit")
            files_out[name] = RunnerFile(sha256=meta["sha256"], size=meta["size"], content=content)
        return RunnerStepResult(**{k: v for k, v in data.items() if k != "files"}, files=files_out)

    async def scan(self, paths: list[str] | None = None) -> dict[str, Any]:
        body: dict[str, Any] = {"token": self._token("scan")}
        if paths:
            body["paths"] = paths
        return await self._post("/scan", body)

    async def egress(self) -> list[dict[str, Any]]:
        data = await self._post("/egress", {"token": self._token("egress")})
        return list(data.get("attempts") or [])

    async def revoke(self, *, poweroff: bool = False) -> dict[str, Any]:
        return await self._post("/revoke", {"token": self._token("revoke"), "poweroff": poweroff})
