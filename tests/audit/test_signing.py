"""Receipt signatures and the public log: the pure Python verifier, tampering, key handling, the HTTP surface."""

from __future__ import annotations

import base64
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

import httpx
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from apps.control_plane.app import create_app
from apps.control_plane.deps import build_mock_deps
from brz.audit import AuditLog, CostSummary, EgressSummary, build_receipt
from brz.audit import offline_verify as ov
from brz.audit.signing import AnchorLog, ReceiptSigner, keygen

ROOT = Path(__file__).resolve().parents[2]
VERIFIER = ROOT / "brz" / "audit" / "offline_verify.py"
NOW = datetime(2026, 11, 6, tzinfo=timezone.utc)

# RFC 8032 section 7.1, tests 1 to 3: public key, message, signature.
RFC8032 = [
    (
        "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a",
        "",
        "e5564300c360ac729086e2cc806e828a84877f1eb8e5d974d873e065224901555fb8821590a33bacc61e39701cf9b46bd25bf5f0595bbe24655141438e7a100b",
    ),
    (
        "3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c",
        "72",
        "92a009a9f0d4cab8720e820b5f642540a2b27b5416503f8fb3762223ebdb69da085ac1e43e15996e458f3613d0f11d8c387b2eaeb4302aeeb00d291612bb0c00",
    ),
    (
        "fc51cd8e6218a1a38da47ed00230f0580816ed13ba3303ac5deb911548908025",
        "af82",
        "6291d657deec24024827e69c3abe01a30ce548a284743a445e3680d7db5ac3ac18ff9b538d16f290ae67f760984dc6594a7c15e9716ed28dc027beceea1ec40a",
    ),
]


def make_receipt(task_id: str = "t1"):
    audit = AuditLog()
    audit.append("task.received", {"task_id": task_id, "task_sha256": ov._sha("x")})
    audit.append("task.failed", {"task_id": task_id, "total_usd": 1.0})
    return build_receipt(
        task_id=task_id,
        status="failed",
        task_text="x",
        input_files={},
        plan={},
        planner_model="",
        steps=[],
        verifier={"passed": False, "rerun_match": None},
        sandboxes=[],
        egress=EgressSummary(),
        secret_scan=None,
        cost=CostSummary(total_usd=1.0),
        audit=audit,
        now=NOW,
    )


@pytest.fixture
def signer():
    return ReceiptSigner(Ed25519PrivateKey.generate())


def as_dict(receipt) -> dict:
    return json.loads(json.dumps(receipt.model_dump(mode="json")))


@pytest.mark.parametrize("public,message,signature", RFC8032)
def test_pure_python_verifier_on_rfc8032_vectors(public, message, signature):
    pub, msg, sig = bytes.fromhex(public), bytes.fromhex(message), bytes.fromhex(signature)
    assert ov.ed25519_verify(pub, msg, sig)
    assert not ov.ed25519_verify(pub, msg + b"x", sig)
    assert not ov.ed25519_verify(pub, msg, sig[:-1] + bytes([sig[-1] ^ 1]))


def test_pure_python_verifier_agrees_with_cryptography():
    for i in range(5):
        key = Ed25519PrivateKey.generate()
        pub = bytes.fromhex(ReceiptSigner(key).public_hex)
        msg = f"message {i}".encode()
        assert ov.ed25519_verify(pub, msg, key.sign(msg))


def test_signature_rejects_a_high_s_value():
    pub, _, signature = RFC8032[0]
    sig = bytes.fromhex(signature)
    s = int.from_bytes(sig[32:], "little") + ov._L  # the same point, malleated
    assert not ov.ed25519_verify(bytes.fromhex(pub), b"", sig[:32] + s.to_bytes(32, "little"))


def test_signed_receipt_verifies_and_stays_hash_stable(signer):
    r = make_receipt()
    before = r.receipt_sha256
    signer.sign(r, NOW)
    assert r.receipt_sha256 == before and r.verify()[0]
    result = ov.verify_receipt(as_dict(r), public_key=signer.public_hex, require_signature=True)
    assert result["ok"], result["problems"]
    assert result["signature"] == "valid"


def test_unsigned_receipt_is_reported_and_can_be_required(signer):
    d = as_dict(make_receipt())
    assert ov.verify_receipt(d, public_key=signer.public_hex)["signature"] == "absent"
    assert not ov.verify_receipt(d, public_key=signer.public_hex, require_signature=True)["ok"]


def test_old_receipt_without_the_field_still_verifies(signer):
    d = as_dict(make_receipt())
    del d["signature"]
    assert ov.verify_receipt(d, public_key=signer.public_hex)["ok"]


@pytest.mark.parametrize("field", ["status", "task_id", "audit_head_hash", "receipt_sha256"])
def test_changing_a_signed_field_breaks_the_signature(signer, field):
    d = as_dict(signer.sign(make_receipt(), NOW))
    d[field] = "killed" if field == "status" else "0" * 64
    status, reasons = ov.check_signature(d, signer.public_hex)
    assert status == "invalid" and reasons


def test_a_forger_with_another_key_is_caught(signer):
    other = ReceiptSigner(Ed25519PrivateKey.generate())
    d = as_dict(other.sign(make_receipt(), NOW))
    result = ov.verify_receipt(d, public_key=signer.public_hex)
    assert not result["ok"] and "another key" in result["problems"][0]


def test_full_rewrite_is_caught_by_the_signature(signer):
    """A chain alone passes a full rewrite. A rewrite that keeps the old signature does not pass."""
    good = signer.sign(make_receipt("real"), NOW)
    forged = make_receipt("real")
    forged.task_text = "something else"
    forged.task_text_sha256 = ov._sha("something else")
    forged.finalize()
    forged.signature = good.signature
    assert ov.check_signature(as_dict(forged), signer.public_hex)[0] == "invalid"


def test_anchor_log_chains_and_catches_edits(tmp_path, signer):
    log = AnchorLog(tmp_path / "anchors.jsonl", signer)
    first, second = signer.sign(make_receipt("a"), NOW), signer.sign(make_receipt("b"), NOW)
    log.append(first, NOW)
    copy = log.path.read_text(encoding="utf-8")
    log.append(second, NOW)
    text = log.path.read_text(encoding="utf-8")

    result = ov.verify_receipt(as_dict(second), public_key=signer.public_hex, anchors=text, checkpoint=copy)
    assert result["ok"] and result["anchor_line"] == 1

    reopened = AnchorLog(tmp_path / "anchors.jsonl", signer)
    assert reopened.seq == 2 and reopened.head == json.loads(text.splitlines()[-1])["hash"]

    problems, _ = ov.verify_anchors(text.replace('"status":"failed"', '"status":"verified"', 1), signer.public_hex)
    assert problems and "does not match its hash" in problems[0]

    dropped = "".join(text.splitlines(keepends=True)[1:])
    assert ov.verify_anchors(dropped, signer.public_hex)[0]
    assert not ov.verify_receipt(as_dict(first), public_key=signer.public_hex, anchors="", checkpoint="")["ok"]


def test_rewritten_log_does_not_match_an_older_copy(tmp_path, signer):
    """A holder of the key can rebuild a valid log. An older copy shows that history changed."""
    log = AnchorLog(tmp_path / "a.jsonl", signer)
    log.append(signer.sign(make_receipt("a"), NOW), NOW)
    copy = log.path.read_text(encoding="utf-8")
    rebuilt = AnchorLog(tmp_path / "b.jsonl", signer)
    forged = signer.sign(make_receipt("c"), NOW)
    rebuilt.append(forged, NOW)
    text = rebuilt.path.read_text(encoding="utf-8")
    assert ov.verify_anchors(text, signer.public_hex)[0] == []
    result = ov.verify_receipt(as_dict(forged), public_key=signer.public_hex, anchors=text, checkpoint=copy)
    assert not result["ok"] and "rewritten" in result["problems"][0]


def test_keygen_never_overwrites_and_prints_only_the_public_half(tmp_path):
    path = tmp_path / "signing.key"
    public = keygen(str(path))
    seed = path.read_text(encoding="ascii").strip()
    assert public != seed and len(seed) == 64
    assert ReceiptSigner.from_file(path).public_hex == public
    assert seed not in repr(ReceiptSigner.from_file(path))
    with pytest.raises(FileExistsError):
        keygen(str(path))


def test_cli_stays_stdlib_only_and_reports(tmp_path, signer):
    path = tmp_path / "receipt.json"
    r = signer.sign(make_receipt(), NOW)
    path.write_text(r.to_json(), encoding="utf-8")
    run = [sys.executable, "-I", "-S", str(VERIFIER), str(path), "--pubkey", signer.public_hex, "--require-signature"]
    p = subprocess.run(run, capture_output=True, text=True, timeout=60, check=False)
    assert p.returncode == 0, p.stdout + p.stderr
    assert "signature: valid" in p.stdout

    d = json.loads(path.read_text(encoding="utf-8"))
    d["signature"]["value"] = "00" * 64
    path.write_text(json.dumps(d), encoding="utf-8")
    p = subprocess.run(run, capture_output=True, text=True, timeout=60, check=False)
    assert p.returncode == 1 and "signature does not match" in p.stdout


async def test_the_app_signs_logs_and_serves_the_key_but_never_the_private_half(tmp_path):
    key = Ed25519PrivateKey.generate()
    signer = ReceiptSigner(key)
    seed = keygen_seed_hex(key)
    deps = build_mock_deps()
    deps.backend.workroot = str(tmp_path / "work")
    app = create_app(deps, data_dir=tmp_path / "data", signer=signer)
    body = {
        "task": "Summarise sales.csv per region",
        "budget_usd": 0.25,
        "files": [{"name": "sales.csv", "content_b64": base64.b64encode(b"region,amount\nnorth,1\n").decode()}],
    }
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://cp") as c:
            task_id = (await c.post("/tasks", json=body)).json()["id"]
            await app.state.store.wait(task_id)
            pub = (await c.get("/pubkey")).json()
            receipt = (await c.get(f"/tasks/{task_id}/receipt")).json()
            anchors = (await c.get("/anchors.jsonl")).text
            check = (await c.get(f"/tasks/{task_id}/receipt/verify")).json()
            page = (await c.get(f"/ui/tasks/{task_id}/receipt")).text
            timeline = (await c.get(f"/tasks/{task_id}")).text
    assert pub["public_key"] == signer.public_hex and check["signature"] == "valid" and check["ok"]
    assert "Change one byte" in page
    result = ov.verify_receipt(receipt, public_key=signer.public_hex, require_signature=True, anchors=anchors)
    assert result["ok"], result["problems"]
    everything = [json.dumps(receipt), anchors, page, timeline, json.dumps(pub)]
    everything += [p.read_text(encoding="utf-8") for p in (tmp_path / "data").rglob("*") if p.is_file()]
    assert not any(seed in text for text in everything)


def keygen_seed_hex(key: Ed25519PrivateKey) -> str:
    from cryptography.hazmat.primitives import serialization

    return key.private_bytes(
        serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption()
    ).hex()


async def test_a_deployment_without_a_key_says_so(tmp_path):
    deps = build_mock_deps()
    deps.backend.workroot = str(tmp_path)
    app = create_app(deps)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://cp") as c:
            assert (await c.get("/pubkey")).status_code == 404
            assert (await c.get("/anchors.jsonl")).text == ""
