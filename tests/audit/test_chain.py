from __future__ import annotations

from datetime import datetime, timedelta, timezone

from brz.audit import GENESIS_HASH, AuditEvent, AuditLog, canonical_json, verify_chain


def _clock():
    t = datetime(2026, 11, 5, 12, 0, 0, tzinfo=timezone.utc)

    def tick():
        nonlocal t
        t += timedelta(seconds=1)
        return t

    return tick


def _log(n: int = 4) -> AuditLog:
    log = AuditLog(clock=_clock())
    log.append("task.received", {"task_id": "t1", "text": "sum csv"})
    log.append("plan.created", {"steps": 1, "est_cost_usd": 0.02})
    log.append("vm.created", {"instance_id": "abc", "plan": "vhp-1c-1gb-amd"})
    log.append("vm.destroyed", {"instance_id": "abc", "http_status": 404})
    return log


def test_chain_links_and_verifies():
    log = _log()
    events = log.events
    assert events[0].prev_hash == GENESIS_HASH
    for a, b in zip(events, events[1:], strict=False):
        assert b.prev_hash == a.hash and b.seq == a.seq + 1
    v = log.verify()
    assert v.ok and v.length == 4 and v.head_hash == log.head_hash == events[-1].hash
    assert len(log.head_hash) == 64


def test_hash_is_deterministic_and_canonical():
    a = AuditLog(clock=_clock())
    b = AuditLog(clock=_clock())
    a.append("x", {"b": 1, "a": [1, 2], "when": datetime(2026, 1, 1, tzinfo=timezone.utc)})
    b.append("x", {"a": [1, 2], "when": datetime(2026, 1, 1, tzinfo=timezone.utc), "b": 1})  # different key order
    assert a.head_hash == b.head_hash
    assert canonical_json({"b": 1, "a": "é"}) == '{"a":"é","b":1}'


def test_tamper_detection_modified_content():
    log = _log()
    events = log.events
    events[1].data["est_cost_usd"] = 0.0001  # cook the books
    v = verify_chain(events)
    assert not v.ok and v.broken_at == 1 and "modified" in v.reason


def test_tamper_detection_dropped_event():
    events = _log().events
    del events[2]
    v = verify_chain(events)
    assert not v.ok and v.broken_at == 3 and "sequence gap" in v.reason


def test_tamper_detection_reordered_events():
    events = _log().events
    events[1], events[2] = events[2], events[1]
    v = verify_chain(events)
    assert not v.ok and v.broken_at == 2  # first event whose seq/prev_hash no longer lines up


def test_tamper_detection_rewritten_tail():
    """Attacker rewrites the last event AND its hash: the chain still verifies internally,
    which is exactly why the receipt pins the head hash separately."""
    log = _log()
    original_head = log.head_hash
    events = log.events
    last = events[-1]
    payload = last.hashable_payload()
    payload["data"] = {"instance_id": "abc", "http_status": 200}
    events[-1] = AuditEvent(**payload, hash=AuditEvent.compute_hash(last.prev_hash, payload))
    assert verify_chain(events).ok  # internally consistent...
    assert verify_chain(events).head_hash != original_head  # ...but the committed head no longer matches


def test_jsonl_roundtrip():
    log = _log()
    text = log.to_jsonl()
    assert text.count("\n") == 4
    again = AuditLog.from_jsonl(text)
    assert again.verify().ok and again.head_hash == log.head_hash
    again.append("extra", {})
    assert again.verify().ok and len(again) == 5
    assert again.of_kind("vm.created")[0].data["instance_id"] == "abc"


def test_empty_chain():
    log = AuditLog()
    assert log.head_hash == GENESIS_HASH
    assert log.verify().ok and log.verify().length == 0
