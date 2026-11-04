"""Offline receipt verifier. Standard library only, one file, no network.

Anyone holding a receipt can check it without installing this project::

    python offline_verify.py receipt.json [--expect-head HASH] [--expect-receipt HASH] [--json]
    python offline_verify.py audit.jsonl                        # a bare audit log: chain checks only

Exit code 0 means every check passed, 1 means the file was tampered with or is inconsistent, and 2 means
it could not be read. What is checked:

1. every audit event: sequence, link to the previous hash, and its own hash;
2. ``audit_head_hash`` and the stored ``audit_chain`` block against the recomputed chain;
3. ``receipt_sha256`` over everything else in the file (added fields count, because nothing is parsed
   into a model first);
4. the human-readable fields against the chain: the step table, the verdict, the final status and the
   task text cannot disagree with the signed-off events, so editing them and recomputing
   ``receipt_sha256`` is caught as well.

A hash chain has no key, so someone who rewrites an event and recomputes every later hash produces a
self-consistent file. Only a head hash kept somewhere else can expose that: pass it with ``--expect-head``.
Without a pin the tool says so rather than implying the file is proven genuine.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys

GENESIS_HASH = "0" * 64


def canonical_json(obj) -> str:
    """Must match :func:`brz.audit.chain.canonical_json` for JSON-parsed data."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def event_hash(event: dict) -> str:
    payload = {k: event.get(k) for k in ("seq", "ts", "kind", "data", "prev_hash")}
    return _sha(str(event.get("prev_hash")) + canonical_json(payload))


def verify_events(events: list) -> tuple[list[str], str]:
    """Problems in the chain, and the head hash reached before the first problem."""
    prev = GENESIS_HASH
    for i, ev in enumerate(events):
        if not isinstance(ev, dict):
            return [f"event {i} is not an object"], prev
        if ev.get("seq") != i:
            return [f"event {i}: sequence gap, found seq {ev.get('seq')}"], prev
        if ev.get("prev_hash") != prev:
            return [f"event {i} ({ev.get('kind')}): prev_hash does not match the previous event"], prev
        if ev.get("hash") != event_hash(ev):
            return [f"event {i} ({ev.get('kind')}): content does not match its hash"], prev
        prev = ev["hash"]
    return [], prev


def _cross_check(receipt: dict, events: list[dict]) -> list[str]:
    problems: list[str] = []
    finished: dict[str, dict] = {}
    for ev in events:
        if ev.get("kind") == "step.finished" and ev.get("data", {}).get("role") == "primary":
            finished.pop(ev["data"].get("step_id"), None)  # a repaired step keeps its last attempt, in that place
            finished[ev["data"].get("step_id")] = ev["data"]
    steps = receipt.get("steps")
    steps = steps if isinstance(steps, list) else []
    listed = [s.get("step_id") for s in steps if isinstance(s, dict)]
    if listed != list(finished):
        problems.append(f"steps table {listed} does not match the chain {list(finished)}")
    for s in steps:
        data = finished.get(s.get("step_id")) if isinstance(s, dict) else None
        if data is None:
            continue
        for field, chained in (
            ("exit_code", data.get("exit_code")),
            ("stdout_sha256", data.get("stdout_sha256")),
            ("output_files", data.get("files")),
        ):
            if s.get(field) != chained:
                problems.append(f"step {s.get('step_id')}: {field} does not match the chain")
    verdicts = [ev for ev in events if ev.get("kind") == "verify.verdict"]
    verifier = receipt.get("verifier") or {}
    if verdicts:
        chained = verdicts[-1].get("data", {})
        for field in ("passed", "rerun_match"):
            if verifier.get(field) != chained.get(field):
                problems.append(f"verifier.{field} does not match the chain")
    elif verifier.get("passed"):
        problems.append("verifier.passed is true but the chain has no verdict")
    if events and events[-1].get("kind") != f"task.{receipt.get('status')}":
        problems.append(f"status {receipt.get('status')!r} does not match the last event {events[-1].get('kind')!r}")
    if _sha(str(receipt.get("task_text"))) != receipt.get("task_text_sha256"):
        problems.append("task_text does not match task_text_sha256")
    received = next((ev for ev in events if ev.get("kind") == "task.received"), None)
    if received and received.get("data", {}).get("task_sha256") != receipt.get("task_text_sha256"):
        problems.append("task_text_sha256 does not match the chain")
    return problems


def verify_receipt(receipt: dict, *, expect_head: str | None = None, expect_receipt: str | None = None) -> dict:
    events = receipt.get("audit_events")
    events = events if isinstance(events, list) else []
    problems, head = verify_events(events)
    chain_ok = not problems
    if chain_ok:
        if not events:
            problems.append("receipt has no audit events")
        if receipt.get("audit_head_hash") != head:
            problems.append("audit_head_hash does not match the events")
        stored = receipt.get("audit_chain") or {}
        if stored.get("ok") is not True or stored.get("length") != len(events) or stored.get("head_hash") != head:
            problems.append("audit_chain block does not match the events")
        problems += _cross_check(receipt, events)
    body = {k: v for k, v in receipt.items() if k != "receipt_sha256"}
    recomputed = _sha(canonical_json(body))
    if recomputed != receipt.get("receipt_sha256"):
        problems.append("receipt_sha256 does not match the file")
    if expect_head is not None and expect_head != receipt.get("audit_head_hash"):
        problems.append(f"head hash differs from the pinned value {expect_head}")
    if expect_receipt is not None and expect_receipt != receipt.get("receipt_sha256"):
        problems.append(f"receipt hash differs from the pinned value {expect_receipt}")
    return {
        "ok": not problems,
        "problems": problems,
        "events": len(events),
        "steps": len(receipt.get("steps") or []),
        "head_hash": head,
        "receipt_sha256": receipt.get("receipt_sha256"),
        "pinned": expect_head is not None or expect_receipt is not None,
    }


def verify_jsonl(text: str, *, expect_head: str | None = None) -> dict:
    events = [json.loads(line) for line in text.splitlines() if line.strip()]
    problems, head = verify_events(events)
    if expect_head is not None and expect_head != head:
        problems.append(f"head hash differs from the pinned value {expect_head}")
    return {
        "ok": not problems,
        "problems": problems,
        "events": len(events),
        "steps": 0,
        "head_hash": head,
        "receipt_sha256": None,
        "pinned": expect_head is not None,
    }


def verify_bytes(raw: bytes, *, jsonl: bool = False, **pins) -> dict:
    """Verify file content. Anything that does not parse counts as tampered, not as a crash."""
    try:
        text = raw.decode("utf-8")
        if jsonl:
            return verify_jsonl(text, expect_head=pins.get("expect_head"))
        data = json.loads(text)
        if not isinstance(data, dict):
            raise ValueError("top level is not an object")
        return verify_receipt(data, **pins)
    except (ValueError, UnicodeDecodeError, TypeError, KeyError, AttributeError) as exc:
        message = f"not a valid receipt: {type(exc).__name__}: {exc}"
        return {"ok": False, "problems": [message], "events": 0, "steps": 0, "head_hash": "", "pinned": False}


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Verify a receipt offline. Needs nothing but Python.")
    p.add_argument("path", help="receipt.json, or an audit log ending in .jsonl")
    p.add_argument("--expect-head", help="audit head hash kept outside this file")
    p.add_argument("--expect-receipt", help="receipt_sha256 kept outside this file")
    p.add_argument("--json", action="store_true", help="print the result as JSON")
    args = p.parse_args(argv)
    try:
        with open(args.path, "rb") as fh:
            raw = fh.read()
    except OSError as exc:
        print(f"cannot read {args.path}: {exc}", file=sys.stderr)
        return 2
    pins = {"expect_head": args.expect_head}
    jsonl = args.path.endswith(".jsonl")
    if not jsonl:
        pins["expect_receipt"] = args.expect_receipt
    result = verify_bytes(raw, jsonl=jsonl, **pins)
    if args.json:
        print(json.dumps(result, indent=1))
    else:
        print(f"{'OK' if result['ok'] else 'TAMPERED'}: {result['events']} events, {result['steps']} steps")
        print(f"head {result['head_hash']}")
        for problem in result["problems"]:
            print(f"  - {problem}")
        if result["ok"] and not result["pinned"]:
            print("note: self-consistent only. Compare the head hash with a copy kept elsewhere, or use --expect-head.")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
