from __future__ import annotations

from pathlib import Path

from brz_runner.secretscan import redact, run_scan, scan_env, scan_text

# Planted FAKE credentials (formats only; none of these is real)
FAKE_AWS = "AKIAIOSFODNN7EXAMPLE"
FAKE_GH = "ghp_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8"
FAKE_OPENAI = "sk-proj-" + "x" * 40
FAKE_SLACK = "xoxb-123456789012-abcdefghijkl"
FAKE_GOOGLE = "AIza" + "A" * 35
FAKE_STRIPE = "sk_live_" + "Z" * 24
FAKE_JWT = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dBjftJeZ4CVPmB92K27uhbUJU1p1r_wW1gFWFOEjXk"
FAKE_PEM = "-----BEGIN RSA PRIVATE KEY-----\nMIIEow...\n-----END RSA PRIVATE KEY-----"


def test_scan_text_detects_each_planted_format():
    text = "\n".join(
        [
            f"aws_access_key_id = {FAKE_AWS}",
            f"export GITHUB_TOKEN={FAKE_GH}",
            f"OPENAI_API_KEY: {FAKE_OPENAI}",
            f"slack: {FAKE_SLACK}",
            f"maps={FAKE_GOOGLE}",
            f"stripe={FAKE_STRIPE}",
            f"bearer {FAKE_JWT}",
            FAKE_PEM,
            "VULTR_API_KEY=ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789",
            "password = correct-horse-battery-staple",
        ]
    )
    findings = scan_text(text, "file:/work/.env")
    kinds = {f.kind for f in findings}
    assert {
        "aws_access_key_id",
        "github_token",
        "openai_key",
        "slack_token",
        "google_api_key",
        "stripe_key",
        "jwt",
        "private_key_block",
        "vultr_api_key",
        "generic_assignment",
    } <= kinds
    # redaction: never the full secret
    for f in findings:
        assert FAKE_GH not in f.redacted and FAKE_AWS not in f.redacted
        assert "*" in f.redacted
    assert any(f.where == "file:/work/.env:1" for f in findings)


def test_scan_text_clean_on_ordinary_code():
    code = "import csv\nrows = list(csv.reader(open('x.csv')))\nprint(sum(float(r[1]) for r in rows[1:]))\n"
    assert scan_text(code, "file:main.py") == []
    assert scan_text("region,amount\nnorth,10\nsouth,20\n", "file:sales.csv") == []
    # a hex sha256 or a UUID should not trip the generic assignment pattern
    assert scan_text("sha256 = 9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08", "f") == []


def test_scan_env_flags_values_and_names():
    env = {
        "PATH": "/usr/bin",
        "HOME": "/work",
        "AWS_SECRET_ACCESS_KEY": "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY",
        "GITHUB_TOKEN": FAKE_GH,
        "SSH_AUTH_SOCK": "/tmp/agent.sock",  # allowlisted name
        "BRZ_WORK": "/work",
        "MY_PASSWORD": "short",  # < 8 chars -> ignored
    }
    findings, count = scan_env(env)
    assert count == 7
    by_where = {f.where: f.kind for f in findings}
    assert by_where == {"env:AWS_SECRET_ACCESS_KEY": "sensitive_env_name", "env:GITHUB_TOKEN": "github_token"}


def test_run_scan_on_planted_tree(tmp_path: Path):
    work = tmp_path / "work"
    (work / "out").mkdir(parents=True)
    (work / "out" / "summary.json").write_text('{"north": 10}')
    (work / ".env").write_text(f"OPENAI_API_KEY={FAKE_OPENAI}\n")
    (work / "id_rsa").write_text(FAKE_PEM)
    (work / "blob.bin").write_bytes(b"\x00\x01" + FAKE_GH.encode())  # binary -> skipped
    (work / "big.txt").write_text("x" * 2_000_000)  # too large -> skipped
    report = run_scan([str(work), str(tmp_path / "missing")], environ={"PATH": "/usr/bin"})
    assert not report.clean
    assert report.files_scanned == 3 and report.files_skipped == 2 and report.env_vars_checked == 1
    kinds = sorted(f.kind for f in report.findings)
    assert kinds == ["openai_key", "private_key_block"]
    d = report.to_dict()
    assert d["findings_count"] == 2 and d["scanner"] == "brz_runner.secretscan"
    assert FAKE_OPENAI not in str(d)


def test_run_scan_clean_tree(tmp_path: Path):
    (tmp_path / "out").mkdir()
    (tmp_path / "out" / "a.txt").write_text("hello")
    report = run_scan([str(tmp_path)], environ={"PATH": "/usr/bin", "BRZ_STEP_ID": "s1"})
    assert report.clean and report.findings == [] and report.files_scanned == 1


def test_redact():
    assert redact("short") == "*****"
    r = redact("ghp_abcdefghijklmnopqrstuvwxyz0123456789")
    assert r.startswith("ghp_") and r.endswith("89") and "abcdefghij" not in r
