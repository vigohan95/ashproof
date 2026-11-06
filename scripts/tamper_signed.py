"""Flip one bit in every byte of a signed receipt and count what the offline verifier misses.

    python scripts/tamper_signed.py <receipt.json> <out.json>

Each copy is checked with the signature required, against the published key. Any undetected flip is kept in the output
with what it changed, so it can be read.
"""

from __future__ import annotations

import json
import sys
from multiprocessing import Pool
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "brz" / "audit"))
import offline_verify as ov  # noqa: E402

RAW = b""


def init(raw: bytes) -> None:
    global RAW
    RAW = raw


def check(i: int) -> dict | None:
    copy = bytearray(RAW)
    copy[i] ^= 1
    result = ov.verify_bytes(bytes(copy), require_signature=True, expect_head=None, expect_receipt=None)
    if result["ok"]:
        window = bytes(RAW[max(0, i - 24) : i + 24]).decode("utf-8", "replace")
        return {"offset": i, "was": chr(RAW[i]), "now": chr(copy[i]), "context": window}
    return None


def main() -> None:
    raw = Path(sys.argv[1]).read_bytes()
    baseline = ov.verify_bytes(raw, require_signature=True)
    assert baseline["ok"], baseline
    with Pool(initializer=init, initargs=(raw,)) as pool:
        missed = [r for r in pool.imap(check, range(len(raw)), chunksize=256) if r]
    out = {
        "receipt": Path(sys.argv[1]).name,
        "bytes": len(raw),
        "flips": len(raw),
        "undetected": len(missed),
        "undetected_flips": missed,
        "signature": baseline["signature"],
    }
    Path(sys.argv[2]).write_text(json.dumps(out, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps({k: v for k, v in out.items() if k != "undetected_flips"}))
    for m in missed[:10]:
        print(m)


if __name__ == "__main__":
    main()
