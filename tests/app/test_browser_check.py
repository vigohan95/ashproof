"""Run the receipt page's real check script in Node, on real receipts: it must agree with the Python verifier."""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from brz.audit import Receipt
from brz.audit.signing import AnchorLog, ReceiptSigner

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "apps" / "control_plane" / "templates" / "_check_script.html"
RECORDINGS = ROOT / "apps" / "control_plane" / "recordings"
NODE = shutil.which("node")

HARNESS = """
globalThis.window = { isSecureContext: true };
const fs = require("fs");
const cases = JSON.parse(fs.readFileSync(process.argv[2], "utf8"));
(async () => {
  const out = [];
  for (const c of cases) {
    const clean = await checkReceipt(c.text, c.key, c.anchors);
    const tampered = await checkReceipt(tamperOneByte(c.text).text, c.key, c.anchors);
    out.push({ clean, tampered });
  }
  console.log(JSON.stringify(out));
})();
"""

pytestmark = pytest.mark.skipif(NODE is None, reason="node is not installed")


def run_check(tmp_path: Path, cases: list[dict]) -> list[dict]:
    source = SCRIPT.read_text(encoding="utf-8").replace("<script>", "").replace("</script>", "")
    js = tmp_path / "check.js"
    js.write_text(source + HARNESS, encoding="utf-8")
    data = tmp_path / "cases.json"
    data.write_text(json.dumps(cases), encoding="utf-8")
    p = subprocess.run([NODE, str(js), str(data)], capture_output=True, text=True, timeout=120, check=False)
    assert p.returncode == 0, p.stderr[:800]
    return json.loads(p.stdout)


def states(rows: list[dict]) -> list[str]:
    return [r["state"] for r in rows]


def wire(receipt: Receipt) -> str:
    """The text the API sends: what FastAPI's JSONResponse renders."""
    return json.dumps(receipt.model_dump(mode="json"), ensure_ascii=False, separators=(",", ":"))


def recordings() -> list[Receipt]:
    out = []
    for path in sorted(RECORDINGS.glob("*.json")):
        out.append(Receipt.model_validate(json.loads(path.read_text(encoding="utf-8"))["receipt"]))
    return out


def test_signed_real_receipts_pass_and_one_changed_byte_fails(tmp_path):
    signer = ReceiptSigner(Ed25519PrivateKey.generate())
    log = AnchorLog(tmp_path / "anchors.jsonl", signer)
    receipts = recordings()
    assert receipts
    for r in receipts:
        signer.sign(r)
        log.append(r)
    anchors = log.path.read_text(encoding="utf-8")
    cases = [{"text": wire(r), "key": signer.public_hex, "anchors": anchors} for r in receipts]
    for result in run_check(tmp_path, cases):
        assert states(result["clean"]) == ["ok", "ok", "ok", "ok"], result["clean"]
        assert "bad" in states(result["tampered"]), result["tampered"]


def test_a_receipt_with_another_key_or_no_signature_is_not_passed(tmp_path):
    signer = ReceiptSigner(Ed25519PrivateKey.generate())
    other = ReceiptSigner(Ed25519PrivateKey.generate())
    unsigned = recordings()[0]
    unsigned.signature = None
    forged = recordings()[0]
    other.sign(forged)
    cases = [
        {"text": wire(unsigned), "key": signer.public_hex, "anchors": ""},
        {"text": wire(forged), "key": signer.public_hex, "anchors": ""},
    ]
    plain, wrong_key = run_check(tmp_path, cases)
    assert states(plain["clean"]) == ["ok", "ok", "none", "none"], plain["clean"]
    assert "bad" in states(wrong_key["clean"]) and "another key" in json.dumps(wrong_key["clean"])
