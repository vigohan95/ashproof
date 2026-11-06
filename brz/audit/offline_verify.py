"""Offline receipt verifier. Standard library only, one file, no network.

Anyone holding a receipt can check it without installing this project::

    python offline_verify.py receipt.json [--expect-head HASH] [--expect-receipt HASH] [--json]
                             [--pubkey HEX] [--require-signature] [--anchors anchors.jsonl] [--checkpoint old.jsonl]
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

5. the Ed25519 signature over the receipt head, against the published key (or ``--pubkey``). The check is pure
   Python below, so this file still needs nothing installed. A signature can be removed from a file, so an unsigned
   receipt is reported, and ``--require-signature`` turns that into a failure;
6. with ``--anchors``, that this receipt is in the public log, that every log line chains to the one before and
   carries a valid signature. With ``--checkpoint``, that an older copy of the log is still its exact beginning.

A hash chain has no key, so someone who rewrites an event and recomputes every later hash produces a
self-consistent file. Only a signature or a head hash kept somewhere else can expose that: ``--expect-head`` pins one.
The signing key lives on the control plane, so a compromised control plane could sign a forgery. A copy of the log made
before the forgery is what exposes that, and the tool says so rather than implying the file is proven genuine.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys

GENESIS_HASH = "0" * 64
# The demo's receipt signing key, public half. The private half never leaves the control plane.
PUBLISHED_PUBLIC_KEY = ""

# --- Ed25519 verification, RFC 8032 section 5.1.7. Verification only, so no secret is handled here.
_P = 2**255 - 19
_L = 2**252 + 27742317777372353535851937790883648493
_D = -121665 * pow(121666, _P - 2, _P) % _P
_I = pow(2, (_P - 1) // 4, _P)


def _recover_x(y: int, sign: int) -> int | None:
    if y >= _P:
        return None
    x2 = (y * y - 1) * pow(_D * y * y + 1, _P - 2, _P) % _P
    if x2 == 0:
        return None if sign else 0
    x = pow(x2, (_P + 3) // 8, _P)
    if (x * x - x2) % _P:
        x = x * _I % _P
    if (x * x - x2) % _P:
        return None
    return _P - x if (x & 1) != sign else x


def _add(a: tuple, b: tuple) -> tuple:
    x1, y1, z1, t1 = a
    x2, y2, z2, t2 = b
    e, f = (y1 - x1) * (y2 - x2) % _P, (y1 + x1) * (y2 + x2) % _P
    g, h = 2 * t1 * t2 * _D % _P, 2 * z1 * z2 % _P
    i, j, k, m = f - e, h - g, h + g, f + e
    return i * j % _P, k * m % _P, j * k % _P, i * m % _P


def _mul(s: int, point: tuple) -> tuple:
    acc = (0, 1, 1, 0)
    while s:
        if s & 1:
            acc = _add(acc, point)
        point = _add(point, point)
        s >>= 1
    return acc


def _encode(point: tuple) -> bytes:
    x, y, z, _ = point
    zi = pow(z, _P - 2, _P)
    x, y = x * zi % _P, y * zi % _P
    return (y | (x & 1) << 255).to_bytes(32, "little")


def _decode(data: bytes) -> tuple | None:
    value = int.from_bytes(data, "little")
    y, sign = value & ((1 << 255) - 1), value >> 255
    x = _recover_x(y, sign)
    return None if x is None else (x, y, 1, x * y % _P)


_BY = 4 * pow(5, _P - 2, _P) % _P
_BASE = (_recover_x(_BY, 0), _BY, 1, _recover_x(_BY, 0) * _BY % _P)


def ed25519_verify(public_key: bytes, message: bytes, signature: bytes) -> bool:
    if len(public_key) != 32 or len(signature) != 64:
        return False
    a = _decode(public_key)
    s = int.from_bytes(signature[32:], "little")
    if a is None or s >= _L or _decode(signature[:32]) is None:
        return False
    h = int.from_bytes(hashlib.sha512(signature[:32] + public_key + message).digest(), "little") % _L
    expected = _add(_decode(signature[:32]), _mul(h, a))
    return _encode(_mul(s, _BASE)) == _encode(expected)


def key_id(public_hex: str) -> str:
    return hashlib.sha256(bytes.fromhex(public_hex)).hexdigest()[:16]


def receipt_message(task_id: str, status: str, head: str, receipt_sha256: str, signed_at: str) -> bytes:
    """The exact bytes that are signed. The browser check on the receipt page builds the same text."""
    return f"ashproof-receipt-v1\n{task_id}\n{status}\n{head}\n{receipt_sha256}\n{signed_at}\n".encode()


def _hex_verify(public_hex: str, message: bytes, signature_hex: str) -> bool:
    try:
        return ed25519_verify(bytes.fromhex(public_hex), message, bytes.fromhex(signature_hex))
    except (TypeError, ValueError):
        return False


def check_signature(receipt: dict, public_key: str | None = None) -> tuple[str, list[str]]:
    """``absent``, ``valid`` or ``invalid``, with the reasons."""
    block = receipt.get("signature")
    if not block:
        return "absent", []
    trusted = public_key or PUBLISHED_PUBLIC_KEY
    if not isinstance(block, dict):
        return "invalid", ["signature block is not an object"]
    if block.get("alg") != "ed25519":
        return "invalid", [f"unknown signature algorithm {block.get('alg')!r}"]
    if not trusted:
        return "invalid", ["no public key to check against: pass --pubkey"]
    if block.get("public_key") != trusted:
        return "invalid", [f"signed by another key, not the published one ({block.get('key_id')})"]
    message = receipt_message(
        str(receipt.get("task_id")),
        str(receipt.get("status")),
        str(receipt.get("audit_head_hash")),
        str(receipt.get("receipt_sha256")),
        str(block.get("signed_at")),
    )
    if not _hex_verify(trusted, message, str(block.get("value"))):
        return "invalid", ["signature does not match the receipt head"]
    return "valid", []


def anchor_hash(entry: dict) -> str:
    payload = {k: v for k, v in entry.items() if k not in ("hash", "sig")}
    return _sha(str(entry.get("prev_hash")) + canonical_json(payload))


def verify_anchors(text: str, public_key: str | None = None) -> tuple[list[str], list[dict]]:
    """Every line of a public log: sequence, link, hash, signature."""
    trusted = public_key or PUBLISHED_PUBLIC_KEY
    prev = GENESIS_HASH
    entries: list[dict] = []
    for i, line in enumerate(text.splitlines()):
        try:
            entry = json.loads(line)
        except ValueError:
            return [f"log line {i} is not JSON"], entries
        if entry.get("seq") != i:
            return [f"log line {i}: sequence gap, found {entry.get('seq')}"], entries
        if entry.get("prev_hash") != prev:
            return [f"log line {i}: does not link to the line before"], entries
        if entry.get("hash") != anchor_hash(entry):
            return [f"log line {i}: content does not match its hash"], entries
        if not _hex_verify(trusted, str(entry.get("hash")).encode(), str(entry.get("sig"))):
            return [f"log line {i}: signature is not valid"], entries
        prev = entry["hash"]
        entries.append(entry)
    return [], entries


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


def verify_receipt(
    receipt: dict,
    *,
    expect_head: str | None = None,
    expect_receipt: str | None = None,
    public_key: str | None = None,
    require_signature: bool = False,
    anchors: str | None = None,
    checkpoint: str | None = None,
) -> dict:
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
    body = {k: v for k, v in receipt.items() if k not in ("receipt_sha256", "signature")}
    recomputed = _sha(canonical_json(body))
    if recomputed != receipt.get("receipt_sha256"):
        problems.append("receipt_sha256 does not match the file")
    if expect_head is not None and expect_head != receipt.get("audit_head_hash"):
        problems.append(f"head hash differs from the pinned value {expect_head}")
    if expect_receipt is not None and expect_receipt != receipt.get("receipt_sha256"):
        problems.append(f"receipt hash differs from the pinned value {expect_receipt}")
    signature, reasons = check_signature(receipt, public_key)
    problems += reasons
    if signature == "absent" and require_signature:
        problems.append("receipt is not signed")
    anchor_line = None
    if anchors is not None:
        log_problems, entries = verify_anchors(anchors, public_key)
        problems += log_problems
        found = [
            e
            for e in entries
            if e.get("task_id") == receipt.get("task_id")
            and e.get("audit_head_hash") == receipt.get("audit_head_hash")
            and e.get("receipt_sha256") == receipt.get("receipt_sha256")
        ]
        if found:
            anchor_line = found[0]["seq"]
        else:
            problems.append("receipt is not in the public log")
        if checkpoint is not None and not anchors.startswith(checkpoint):
            problems.append("the older copy of the log is not the beginning of this log: history was rewritten")
    return {
        "ok": not problems,
        "problems": problems,
        "events": len(events),
        "steps": len(receipt.get("steps") or []),
        "head_hash": head,
        "receipt_sha256": receipt.get("receipt_sha256"),
        "pinned": expect_head is not None or expect_receipt is not None,
        "signature": signature,
        "anchor_line": anchor_line,
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
    p.add_argument("--pubkey", help="public key as hex, instead of the published one")
    p.add_argument("--require-signature", action="store_true", help="fail if the receipt is not signed")
    p.add_argument("--anchors", help="a copy of anchors.jsonl: check the log and find this receipt in it")
    p.add_argument("--checkpoint", help="an older copy of anchors.jsonl that must be the beginning of --anchors")
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
        pins["public_key"] = args.pubkey
        pins["require_signature"] = args.require_signature
        try:
            for name, path in (("anchors", args.anchors), ("checkpoint", args.checkpoint)):
                if path:
                    with open(path, encoding="utf-8", newline="") as fh:
                        pins[name] = fh.read()
        except OSError as exc:
            print(f"cannot read {exc.filename}: {exc}", file=sys.stderr)
            return 2
    result = verify_bytes(raw, jsonl=jsonl, **pins)
    if args.json:
        print(json.dumps(result, indent=1))
    else:
        print(f"{'OK' if result['ok'] else 'TAMPERED'}: {result['events']} events, {result['steps']} steps")
        print(f"head {result['head_hash']}")
        for problem in result["problems"]:
            print(f"  - {problem}")
        signature = result.get("signature")
        if signature == "valid":
            print("signature: valid, made with the published key")
        elif signature == "absent":
            print("signature: none")
        if result.get("anchor_line") is not None:
            print(f"public log: found at line {result['anchor_line']}")
        if result["ok"] and not result["pinned"]:
            if signature == "valid":
                print(
                    "note: the key lives on the control plane, so this shows who signed, not that it was uncompromised."
                )
                print("      A copy of the public log made earlier is what catches a rewrite: use --checkpoint.")
            else:
                print("note: self-consistent only. Compare the head hash with a copy kept elsewhere.")
                print("      Or use --expect-head.")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
