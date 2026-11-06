"""Finished tasks on disk, so receipts outlive a restart of the control plane.

A receipt is the product: "the VM burns, the proof stays" cannot depend on one process staying up. Only finished tasks
are stored. :class:`ArchivedTask` offers the attributes the API and UI read from a live ``TaskState``.
"""

from __future__ import annotations

import base64
import json
import logging
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from brz.audit import Receipt
from brz.orchestrator import TaskState

log = logging.getLogger("brz")


def save(directory: Path, state: TaskState) -> Path:
    data = {
        "id": state.id,
        "status": state.status,
        "created_at": state.created_at.isoformat(),
        "finished_at": state.finished_at.isoformat() if state.finished_at else None,
        "task": state.request.task,
        "total_usd": state.cost.total_usd,
        "destroyed": [bool(h.proof and h.proof.destroyed) for h in state.sandboxes],
        "timeline": state.timeline(),
        "receipt": state.receipt.model_dump(mode="json") if state.receipt else None,
        "outputs": {n: base64.b64encode(b).decode("ascii") for n, b in state.outputs.items()},
    }
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{state.id}.json"
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, default=str), encoding="utf-8")
    tmp.replace(path)
    return path


class ArchivedTask:
    def __init__(self, data: dict[str, Any]):
        self.id: str = data["id"]
        self.status: str = data["status"]
        self.created_at = datetime.fromisoformat(data["created_at"])
        self.finished_at = datetime.fromisoformat(data["finished_at"]) if data["finished_at"] else self.created_at
        self.request = SimpleNamespace(task=data["task"], scripted_plan=data["timeline"].get("scripted") or None)
        self.cost = SimpleNamespace(total_usd=data["total_usd"])
        self.sandboxes = [SimpleNamespace(proof=SimpleNamespace(destroyed=d)) for d in data["destroyed"]]
        self.receipt = Receipt.model_validate(data["receipt"]) if data["receipt"] else None
        self.outputs = {n: base64.b64decode(b) for n, b in data["outputs"].items()}
        self._timeline = data["timeline"]

    def timeline(self) -> dict[str, Any]:
        return self._timeline


def load(directory: Path) -> list[ArchivedTask]:
    tasks: list[ArchivedTask] = []
    for path in sorted(directory.glob("*.json")) if directory.exists() else []:
        try:
            tasks.append(ArchivedTask(json.loads(path.read_text(encoding="utf-8"))))
        except (ValueError, KeyError, TypeError) as exc:
            log.warning("skipping unreadable archive %s: %s", path.name, type(exc).__name__)
    return tasks
