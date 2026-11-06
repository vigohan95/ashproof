"""Control plane API.

    POST /tasks                     create + start a task (JSON; files as base64)
    GET  /tasks                     list
    GET  /tasks/{id}                timeline (status, plan, sandboxes, events, cost so far)
    POST /tasks/{id}/approve        {"approved": true|false} - human approval gate for new egress domains
    POST /tasks/{id}/kill           kill switch: revoke tokens, destroy VMs, record it
    GET  /tasks/{id}/receipt        receipt JSON   (?format=md for Markdown, also /receipt.md)
    GET  /tasks/{id}/outputs/{name} an output file of the primary run
    GET  /health

The orchestrator and its backend are injected through ``create_app(deps)`` so the same app
is exercised end-to-end against mock Vultr + FakeLLM + local runner in tests.
"""

from __future__ import annotations

import asyncio
import base64
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request, Response
from fastapi.responses import JSONResponse, PlainTextResponse, RedirectResponse
from pydantic import BaseModel, Field

from brz import __version__
from brz.orchestrator import TaskRequest, TaskState

from . import archive
from .deps import Deps, build_deps_from_env
from .guard import DemoGuard, DemoPolicy

log = logging.getLogger("brz")
SWEEP_INTERVAL_S = 300.0


class FileIn(BaseModel):
    name: str = Field(min_length=1, max_length=120, pattern=r"^[A-Za-z0-9._-]+$")
    content_b64: str


class TaskCreate(BaseModel):
    task: str = Field(min_length=3, max_length=20_000)
    budget_usd: float = Field(default=0.25, gt=0, le=50)
    allowed_domains: list[str] = Field(default_factory=list)
    files: list[FileIn] = Field(default_factory=list)
    require_approval: bool = True


class ApproveIn(BaseModel):
    approved: bool = True


class KillIn(BaseModel):
    reason: str = "user"


class TaskStore:
    def __init__(self) -> None:
        self.tasks: dict[str, TaskState] = {}
        self.runs: dict[str, asyncio.Task] = {}

    def get(self, task_id: str) -> TaskState:
        state = self.tasks.get(task_id)
        if state is None:
            raise HTTPException(status_code=404, detail="task not found")
        return state

    async def wait(self, task_id: str, timeout: float = 120.0) -> TaskState:
        """Test helper: block until the orchestration task for ``task_id`` finishes."""
        run = self.runs.get(task_id)
        if run is not None:
            await asyncio.wait_for(asyncio.shield(run), timeout=timeout)
        return self.get(task_id)


async def sweep_loop(d: Deps, interval_s: float = SWEEP_INTERVAL_S) -> None:
    """Delete sandboxes that outlived their TTL: a crashed run must not leave a VM billing."""
    ttl_s = (d.backend.config.ttl_minutes + 5) * 60  # type: ignore[attr-defined]
    while True:
        await asyncio.sleep(interval_s)
        try:
            deleted = await d.backend.sweep_orphans(ttl_s)  # type: ignore[attr-defined]
            if deleted:
                log.warning("orphan sweep deleted %s", deleted)
        except Exception as exc:  # noqa: BLE001 - the next pass tries again
            log.warning("orphan sweep failed: %s", type(exc).__name__)


def create_app(deps: Deps | None = None, guard: DemoGuard | None = None, data_dir: Path | None = None) -> FastAPI:
    store = TaskStore()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.deps = deps or build_deps_from_env()
        app.state.store = store
        await app.state.deps.refresh_prices()
        env_dir = os.environ.get("BRZ_DATA_DIR")
        app.state.data_dir = data_dir or (Path(env_dir) if env_dir else None)
        d = app.state.data_dir
        app.state.guard = guard or DemoGuard(DemoPolicy.from_env(), d / "demo-state.json" if d else None)
        if d:
            d.mkdir(parents=True, exist_ok=True)
            for old in archive.load(d / "tasks"):
                store.tasks[old.id] = old
        sweeper = asyncio.create_task(sweep_loop(app.state.deps)) if app.state.deps.mode == "live" else None
        try:
            yield
        finally:
            if sweeper:
                sweeper.cancel()
            for run in list(store.runs.values()):
                if not run.done():
                    run.cancel()
            await app.state.deps.aclose()

    app = FastAPI(
        title="Ashproof control plane",
        version=__version__,
        description=(
            "Containment-first agent execution on Vultr: one throwaway VM per task, verified, receipted, destroyed."
        ),
        lifespan=lifespan,
    )

    def _deps() -> Deps:
        return app.state.deps

    async def _run(state: TaskState) -> None:
        try:
            await _deps().orchestrator.run(state)
        finally:
            app.state.guard.note_finished(state.cost.total_usd)
            if app.state.data_dir:
                archive.save(app.state.data_dir / "tasks", state)

    @app.get("/health")
    async def health() -> dict[str, Any]:
        d = _deps()
        running = sum(1 for r in store.runs.values() if not r.done())
        return {
            "ok": True,
            "version": __version__,
            "mode": d.mode,
            "provider": d.backend.provider,
            "inner_isolation": d.backend.inner_isolation,
            "tasks": len(store.tasks),
            "running": running,
            "demo": app.state.guard.status(),
            "price_source": d.orchestrator.prices.source,
        }

    @app.post("/tasks", status_code=202)
    async def create_task(body: TaskCreate, http: Request) -> dict[str, Any]:
        try:
            files = {f.name: base64.b64decode(f.content_b64, validate=True) for f in body.files}
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=f"bad base64 in files: {exc}") from exc
        guard: DemoGuard = app.state.guard
        # Caddy appends the real peer, so the last entry is the one a client cannot forge
        forwarded = http.headers.get("x-forwarded-for", "").split(",")[-1].strip()
        guard.admit(
            forwarded or (http.client.host if http.client else "unknown"),
            task=body.task,
            budget_usd=body.budget_usd,
            domains=body.allowed_domains,
            files=files,
            running=sum(1 for r in store.runs.values() if not r.done()),
        )
        request = TaskRequest(
            task=body.task,
            budget_usd=body.budget_usd,
            allowed_domains=body.allowed_domains,
            files=files,
            require_approval=body.require_approval or guard.policy.enabled,  # strangers cannot waive the gate
        )
        orch = _deps().orchestrator
        state = orch.new_task(request)
        store.tasks[state.id] = state
        store.runs[state.id] = asyncio.create_task(_run(state), name=f"brz-task-{state.id}")
        return {
            "id": state.id,
            "status": state.status,
            "links": {
                "timeline": f"/tasks/{state.id}",
                "receipt": f"/tasks/{state.id}/receipt",
                "kill": f"/tasks/{state.id}/kill",
            },
        }

    @app.get("/tasks")
    async def list_tasks() -> dict[str, Any]:
        return {
            "tasks": [
                {
                    "id": s.id,
                    "status": s.status,
                    "created_at": s.created_at.isoformat(),
                    "task": s.request.task[:120],
                    "total_usd": s.cost.total_usd,
                }
                for s in store.tasks.values()
            ]
        }

    @app.get("/tasks/{task_id}")
    async def get_task(task_id: str) -> dict[str, Any]:
        return store.get(task_id).timeline()

    @app.post("/tasks/{task_id}/approve")
    async def approve(task_id: str, body: ApproveIn) -> dict[str, Any]:
        state = store.get(task_id)
        if state.status != "awaiting_approval":
            raise HTTPException(status_code=409, detail=f"task is {state.status}, not awaiting_approval")
        if body.approved:
            app.state.guard.check_domains(state.pending_domains)
        _deps().orchestrator.approve(state, body.approved)
        return {"id": task_id, "approved": body.approved, "domains": state.pending_domains}

    @app.post("/tasks/{task_id}/kill")
    async def kill(task_id: str, body: KillIn | None = None) -> dict[str, Any]:
        state = store.get(task_id)
        reason = body.reason if body else "user"
        if state.finished_at is not None:
            return {"id": task_id, "status": state.status, "killed": False, "detail": "task already finished"}
        await _deps().orchestrator.kill(state, reason)
        return {
            "id": task_id,
            "status": state.status,
            "killed": True,
            "sandboxes": [
                {"instance_id": h.instance_id, "destroyed": bool(h.proof and h.proof.destroyed)}
                for h in state.sandboxes
            ],
        }

    @app.get("/tasks/{task_id}/receipt")
    async def receipt(task_id: str, format: str = Query(default="json", pattern="^(json|md)$")) -> Response:
        state = store.get(task_id)
        if state.receipt is None:
            raise HTTPException(status_code=409, detail=f"receipt not ready (task is {state.status})")
        if format == "md":
            return PlainTextResponse(state.receipt.to_markdown(), media_type="text/markdown; charset=utf-8")
        return JSONResponse(content=state.receipt.model_dump(mode="json"))

    @app.get("/tasks/{task_id}/receipt/verify")
    async def receipt_verify(task_id: str) -> dict[str, Any]:
        state = store.get(task_id)
        if state.receipt is None:
            raise HTTPException(status_code=409, detail=f"receipt not ready (task is {state.status})")
        ok, problems = state.receipt.verify()
        return {
            "id": task_id,
            "ok": ok,
            "problems": problems,
            "events": len(state.receipt.audit_events),
            "head_hash": state.receipt.audit_head_hash,
            "receipt_sha256": state.receipt.receipt_sha256,
        }

    @app.get("/tasks/{task_id}/receipt.md")
    async def receipt_md(task_id: str) -> Response:
        return await receipt(task_id, format="md")

    @app.get("/tasks/{task_id}/outputs/{name}")
    async def output_file(task_id: str, name: str) -> Response:
        state = store.get(task_id)
        data = state.outputs.get(name)
        if data is None:
            raise HTTPException(status_code=404, detail="no such output")
        media = "application/json" if name.endswith(".json") else "text/plain; charset=utf-8"
        return Response(content=data, media_type=media)

    from .ui import router as ui_router

    app.include_router(ui_router)

    @app.get("/", include_in_schema=False)
    async def root() -> Response:
        return RedirectResponse(url="/ui", status_code=307)

    return app


app = create_app()


def main() -> None:
    import os

    import uvicorn

    uvicorn.run(
        "apps.control_plane.app:app",
        host=os.environ.get("BRZ_HOST", "127.0.0.1"),
        port=int(os.environ.get("BRZ_PORT", "8000")),
        reload=False,
    )


if __name__ == "__main__":
    main()
