"""Ed25519 signatures on receipts, and a public append-only log of what was signed.

A hash chain has no key: whoever can rewrite a receipt can recompute every hash. A signature binds the receipt head to a
key, so a rewrite needs the private key too. The key lives on the control plane, in a file outside git, and is read
only here. It is never written to a receipt, a log line or a response.

What this does not prove: a control plane that is itself compromised holds the key and can sign anything. The log
narrows that. Each line chains to the one before and is signed, so once anyone has copied a line, lines before it
cannot be changed without the copy showing it. The log is served by the same machine, so it is not an outside witness
until someone keeps such a copy. The repository holds one.

    python -m brz.audit.signing keygen /etc/ashproof/signing.key     writes the key, prints only the public half
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from .chain import GENESIS_HASH, canonical_json
from .offline_verify import anchor_hash, key_id, receipt_message
from .receipt import Receipt


class ReceiptSigner:
    def __init__(self, private_key: Ed25519PrivateKey):
        self._key = private_key
        raw = private_key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
        self.public_hex = raw.hex()
        self.key_id = key_id(self.public_hex)

    @classmethod
    def from_file(cls, path: str | Path) -> ReceiptSigner:
        seed = bytes.fromhex(Path(path).read_text(encoding="ascii").strip())
        return cls(Ed25519PrivateKey.from_private_bytes(seed))

    def __repr__(self) -> str:  # a stray log line must not be able to show the key
        return f"ReceiptSigner(key_id={self.key_id})"

    def sign_bytes(self, message: bytes) -> str:
        return self._key.sign(message).hex()

    def sign(self, receipt: Receipt, now: datetime | None = None) -> Receipt:
        signed_at = (now or datetime.now(timezone.utc)).isoformat()
        message = receipt_message(
            receipt.task_id, receipt.status, receipt.audit_head_hash, receipt.receipt_sha256, signed_at
        )
        receipt.signature = {
            "alg": "ed25519",
            "key_id": self.key_id,
            "public_key": self.public_hex,
            "signed_at": signed_at,
            "value": self.sign_bytes(message),
        }
        return receipt


class AnchorLog:
    """``anchors.jsonl``: one signed, chained line per signed receipt. Only ever appended to."""

    def __init__(self, path: Path, signer: ReceiptSigner):
        self.path = path
        self.signer = signer
        self.seq = 0
        self.head = GENESIS_HASH
        if path.exists():
            lines = path.read_text(encoding="utf-8").splitlines()
            if lines:
                last = json.loads(lines[-1])
                self.seq = last["seq"] + 1
                self.head = last["hash"]

    def append(self, receipt: Receipt, now: datetime | None = None) -> dict[str, Any]:
        entry: dict[str, Any] = {
            "seq": self.seq,
            "ts": (now or datetime.now(timezone.utc)).isoformat(),
            "task_id": receipt.task_id,
            "status": receipt.status,
            "audit_head_hash": receipt.audit_head_hash,
            "receipt_sha256": receipt.receipt_sha256,
            "prev_hash": self.head,
        }
        entry["hash"] = anchor_hash(entry)
        entry["sig"] = self.signer.sign_bytes(entry["hash"].encode("ascii"))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, "a", encoding="utf-8", newline="\n") as fh:
            fh.write(canonical_json(entry) + "\n")
            fh.flush()
            os.fsync(fh.fileno())
        self.seq += 1
        self.head = entry["hash"]
        return entry


def keygen(path: str) -> str:
    """Write a new key to ``path`` (never over an existing one) and return the public half."""
    key = Ed25519PrivateKey.generate()
    seed = key.private_bytes(serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o640)
    with os.fdopen(fd, "w", encoding="ascii") as fh:
        fh.write(seed.hex() + "\n")
    return ReceiptSigner(key).public_hex


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 2 or args[0] != "keygen":
        print("usage: python -m brz.audit.signing keygen PATH", file=sys.stderr)
        return 2
    print(keygen(args[1]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
