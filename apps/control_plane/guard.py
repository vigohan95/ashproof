"""Limits for a control plane that anyone can reach.

On a public URL the "human" behind the approval gate is a stranger, so the gate alone cannot stop someone opening our
VMs as a relay, and POST /tasks alone would let anyone spend the account. With ``BRZ_PUBLIC_DEMO=1``:

* the domains a task can reach come from a fixed list, whoever clicks approve;
* tasks are capped per day, per client address and in total dollars;
* task size, file size, budget and step timeout are capped.

Client addresses are kept in memory only. The daily count and total spend go to ``demo-state.json`` so a restart
cannot reset them.
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException


def _int(name: str, default: int) -> int:
    return int(os.environ.get(name) or default)


@dataclass
class DemoPolicy:
    enabled: bool = False
    allowed_domains: list[str] = field(default_factory=lambda: ["example.com"])
    max_running: int = 2
    tasks_per_day: int = 24
    tasks_per_client_hour: int = 4
    total_usd: float = 10.0
    max_task_chars: int = 2000
    max_file_bytes: int = 256 * 1024
    max_budget_usd: float = 0.25
    max_step_timeout_s: int = 120
    approval_timeout_s: float = 180.0

    @classmethod
    def from_env(cls) -> DemoPolicy:
        enabled = os.environ.get("BRZ_PUBLIC_DEMO", "").strip().lower() in ("1", "true", "yes", "on")
        domains = [d.strip().lower() for d in os.environ.get("BRZ_DEMO_DOMAINS", "example.com").split(",") if d.strip()]
        return cls(
            enabled=enabled,
            allowed_domains=domains,
            max_running=_int("BRZ_DEMO_MAX_RUNNING", 2),
            tasks_per_day=_int("BRZ_DEMO_TASKS_PER_DAY", 24),
            tasks_per_client_hour=_int("BRZ_DEMO_TASKS_PER_CLIENT_HOUR", 4),
            total_usd=float(os.environ.get("BRZ_DEMO_TOTAL_USD") or 10.0),
        )


class DemoGuard:
    def __init__(self, policy: DemoPolicy, state_path: Path | None = None, clock=time.time):
        self.policy = policy
        self.state_path = state_path
        self._clock = clock
        self._clients: dict[str, list[float]] = {}
        self.day = ""
        self.day_count = 0
        self.total_usd = 0.0
        self._load()

    # ------------------------------------------------------------ persistence
    def _load(self) -> None:
        if self.state_path and self.state_path.exists():
            data = json.loads(self.state_path.read_text(encoding="utf-8"))
            self.day = data.get("day", "")
            self.day_count = int(data.get("day_count", 0))
            self.total_usd = float(data.get("total_usd", 0.0))

    def _save(self) -> None:
        if self.state_path:
            tmp = self.state_path.with_suffix(".tmp")
            tmp.write_text(
                json.dumps({"day": self.day, "day_count": self.day_count, "total_usd": self.total_usd}),
                encoding="utf-8",
            )
            tmp.replace(self.state_path)

    def _today(self) -> str:
        return datetime.fromtimestamp(self._clock(), timezone.utc).strftime("%Y-%m-%d")

    def _roll(self) -> None:
        today = self._today()
        if today != self.day:
            self.day = today
            self.day_count = 0

    # ----------------------------------------------------------------- checks
    def admit(
        self,
        client: str,
        *,
        task: str,
        budget_usd: float,
        domains: list[str],
        files: dict[str, bytes],
        running: int,
    ) -> None:
        """Raise HTTPException if this task may not start; otherwise count it."""
        p = self.policy
        if not p.enabled:
            return
        self._roll()
        if len(task) > p.max_task_chars:
            raise HTTPException(413, f"public demo: task text is limited to {p.max_task_chars} characters")
        if sum(len(b) for b in files.values()) > p.max_file_bytes:
            raise HTTPException(413, f"public demo: files are limited to {p.max_file_bytes // 1024} KiB in total")
        if budget_usd > p.max_budget_usd:
            raise HTTPException(403, f"public demo: budget is limited to ${p.max_budget_usd:.2f}")
        self.check_domains(domains)
        if self.total_usd >= p.total_usd:
            raise HTTPException(429, "public demo: the total spending limit is reached; receipts stay readable")
        if self.day_count >= p.tasks_per_day:
            raise HTTPException(429, f"public demo: the limit of {p.tasks_per_day} tasks per day is reached")
        if running >= p.max_running:
            raise HTTPException(429, "public demo: tasks are running, try again in a few minutes")
        now = self._clock()
        recent = [t for t in self._clients.get(client, []) if now - t < 3600]
        if len(recent) >= p.tasks_per_client_hour:
            raise HTTPException(429, f"public demo: limited to {p.tasks_per_client_hour} tasks per hour per address")
        self._clients[client] = [*recent, now]
        self.day_count += 1
        self._save()

    def check_domains(self, domains: list[str]) -> None:
        if not self.policy.enabled:
            return
        outside = sorted({d.strip().lower() for d in domains} - set(self.policy.allowed_domains))
        if outside:
            raise HTTPException(
                403, f"public demo: {outside} cannot be opened here; only {self.policy.allowed_domains} can"
            )

    def note_finished(self, total_usd: float) -> None:
        if self.policy.enabled:
            self.total_usd = round(self.total_usd + total_usd, 6)
            self._save()

    def status(self) -> dict[str, Any]:
        p = self.policy
        if not p.enabled:
            return {"enabled": False}
        self._roll()
        return {
            "enabled": True,
            "allowed_domains": p.allowed_domains,
            "tasks_today": self.day_count,
            "tasks_per_day": p.tasks_per_day,
            "total_usd": self.total_usd,
            "total_usd_limit": p.total_usd,
            "max_budget_usd": p.max_budget_usd,
        }
