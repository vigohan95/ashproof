"""Hash-chained audit log.

Every event is ``sha256(prev_hash + canonical_json(event_without_hash))``. The head hash
commits to the entire history, so a receipt that carries the head hash + the events can be
re-verified offline by anyone: change one byte, drop one event, reorder two events, and
:func:`verify_chain` points at the first broken link.

Canonical JSON = sorted keys, no whitespace, UTF-8, no NaN. Timestamps are part of the
hashed payload (they are evidence too).
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, Field

GENESIS_HASH = "0" * 64


def canonical_json(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False, default=_default)


def _default(o: Any) -> Any:
    if isinstance(o, datetime):
        return o.isoformat()
    if isinstance(o, BaseModel):
        return o.model_dump(mode="json")
    if isinstance(o, bytes):
        return o.hex()
    if isinstance(o, set | frozenset):
        return sorted(o)
    raise TypeError(f"not JSON serialisable: {type(o).__name__}")


def sha256_hex(data: str) -> str:
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


class AuditEvent(BaseModel):
    seq: int
    ts: str  # ISO-8601 UTC
    kind: str  # e.g. "task.received", "vm.created", "step.finished", "egress.denied"
    data: dict[str, Any] = Field(default_factory=dict)
    prev_hash: str
    hash: str

    def hashable_payload(self) -> dict[str, Any]:
        return {"seq": self.seq, "ts": self.ts, "kind": self.kind, "data": self.data, "prev_hash": self.prev_hash}

    @staticmethod
    def compute_hash(prev_hash: str, payload: dict[str, Any]) -> str:
        return sha256_hex(prev_hash + canonical_json(payload))


class ChainVerification(BaseModel):
    ok: bool
    length: int
    head_hash: str
    broken_at: int | None = None  # seq of the first bad event
    reason: str = ""


class AuditLog:
    """Append-only in-memory chain. Persist with :meth:`to_jsonl`; reload with :meth:`from_jsonl`."""

    def __init__(self, events: Iterable[AuditEvent] | None = None, *, clock=None):
        self._events: list[AuditEvent] = list(events or [])
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    # --- write
    def append(self, kind: str, data: dict[str, Any] | None = None) -> AuditEvent:
        prev = self.head_hash
        payload = {
            "seq": len(self._events),
            "ts": self._clock().isoformat(),
            "kind": kind,
            "data": json.loads(canonical_json(data or {})),  # normalise (datetimes -> str, etc.)
            "prev_hash": prev,
        }
        ev = AuditEvent(**payload, hash=AuditEvent.compute_hash(prev, payload))
        self._events.append(ev)
        return ev

    # --- read
    @property
    def events(self) -> list[AuditEvent]:
        return list(self._events)

    @property
    def head_hash(self) -> str:
        return self._events[-1].hash if self._events else GENESIS_HASH

    def __len__(self) -> int:
        return len(self._events)

    def of_kind(self, kind: str) -> list[AuditEvent]:
        return [e for e in self._events if e.kind == kind]

    def verify(self) -> ChainVerification:
        return verify_chain(self._events)

    # --- persistence
    def to_jsonl(self) -> str:
        return "".join(canonical_json(e.model_dump()) + "\n" for e in self._events)

    @classmethod
    def from_jsonl(cls, text: str) -> AuditLog:
        events = [AuditEvent.model_validate(json.loads(line)) for line in text.splitlines() if line.strip()]
        return cls(events)


def verify_chain(events: list[AuditEvent]) -> ChainVerification:
    prev = GENESIS_HASH
    for i, ev in enumerate(events):
        if ev.seq != i:
            return ChainVerification(
                ok=False,
                length=len(events),
                head_hash=prev,
                broken_at=ev.seq,
                reason=f"sequence gap: expected seq {i}, got {ev.seq}",
            )
        if ev.prev_hash != prev:
            return ChainVerification(
                ok=False,
                length=len(events),
                head_hash=prev,
                broken_at=ev.seq,
                reason="prev_hash does not match previous event",
            )
        expected = AuditEvent.compute_hash(prev, ev.hashable_payload())
        if ev.hash != expected:
            return ChainVerification(
                ok=False,
                length=len(events),
                head_hash=prev,
                broken_at=ev.seq,
                reason="event hash mismatch (content modified)",
            )
        prev = ev.hash
    return ChainVerification(ok=True, length=len(events), head_hash=prev)
