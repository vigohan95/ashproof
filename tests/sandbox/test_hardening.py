"""Regression tests for what the attack suite found (docs/evidence/attacks-2026-11-04). These run anywhere; the
same attacks against real gVisor are in tests/attacks."""

from __future__ import annotations

import base64
import hashlib
import json
import os
import sys
from pathlib import Path

import httpx
import pytest
from brz_runner.egress import build_ruleset, hosts_lines
from brz_runner.executor import GvisorExecutor, StepRequest, SubprocessExecutor
from brz_runner.secretscan import scan_and_redact, scan_text
from brz_runner.server import BackgroundRunner, RunnerConfig
from brz_runner.tokens import (
    TokenError,
    TokenRegistry,
    reply_mac,
    sign_step_token,
    sign_token,
    step_digest,
    verify_token,
)

from brz.llm import PlanStep
from brz.orchestrator import repair_violations
from brz.sandbox.runner_client import RunnerClient, RunnerError

KEY = b"k" * 32
TASK = "t1"
FAKE_GH = "ghp_" + "a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8"


def _symlink(target: Path, link: Path) -> None:
    try:
        os.symlink(target, link)
    except OSError:
        pytest.skip("symlinks need a privilege on this machine")


def _ex(tmp_path: Path) -> SubprocessExecutor:
    return SubprocessExecutor(str(tmp_path / "work"), python_bin=sys.executable)


# ------------------------------------------------------------------ work tree belongs to the step
@pytest.mark.parametrize("bad", ["../../etc", "a/b", "..", "", ".hidden", "_rootfs", "x" * 65, "a\nb"])
def test_step_id_must_be_safe(bad: str, tmp_path: Path):
    with pytest.raises(ValueError):
        StepRequest.from_dict({"step_id": bad})
    with pytest.raises(ValueError):
        _ex(tmp_path).prepare(StepRequest(step_id=bad, kind="python", code=""))
    with pytest.raises(ValueError):
        PlanStep(id=bad, title="t", kind="python", code="")


def test_collect_outputs_never_follows_links(tmp_path: Path):
    ex = _ex(tmp_path)
    secret = tmp_path / "secret.txt"
    secret.write_text("TOP-SECRET")
    out = tmp_path / "work" / "out"
    out.mkdir(parents=True)
    (out / "real.txt").write_text("fine")
    _symlink(secret, out / "stolen.txt")
    files, skipped = ex.collect_outputs(str(out))
    assert files == {"real.txt": b"fine"}
    assert skipped == [{"name": "stolen.txt", "reason": "not a regular file"}]


def test_collect_outputs_refuses_a_replaced_out_dir(tmp_path: Path):
    ex = _ex(tmp_path)
    decoy = tmp_path / "decoy"
    decoy.mkdir()
    (decoy / "secret.txt").write_text("TOP-SECRET")
    (tmp_path / "work").mkdir()
    _symlink(decoy, tmp_path / "work" / "out")
    files, skipped = ex.collect_outputs(str(tmp_path / "work" / "out"))
    assert files == {} and skipped[0]["reason"] == "out directory was replaced"


def test_prepare_replaces_planted_links_instead_of_writing_through(tmp_path: Path):
    ex = _ex(tmp_path)
    decoy = tmp_path / "decoy"
    decoy.mkdir()
    work = tmp_path / "work"
    (work / "steps").mkdir(parents=True)
    (work / "input").mkdir()
    _symlink(decoy, work / "steps" / "s2")
    _symlink(decoy / "planted.txt", work / "input" / "data.csv")
    ex.prepare(StepRequest(step_id="s2", kind="python", code="print(1)", files={"data.csv": b"payload"}))
    assert list(decoy.iterdir()) == []
    assert not (work / "steps" / "s2").is_symlink() and (work / "steps" / "s2" / "main.py").is_file()
    assert (work / "input" / "data.csv").read_bytes() == b"payload"


def test_stdout_flood_is_capped_and_drained(tmp_path: Path):
    res = _ex(tmp_path).run(
        StepRequest(
            step_id="flood",
            kind="python",
            code="import sys\nfor _ in range(20): sys.stdout.write('A' * 100000)\nsys.stdout.flush()\nprint('end')",
        )
    )
    assert res.exit_code == 0 and len(res.stdout) == 256_000 and res.stdout_truncated is True


def test_work_quota_kills_the_step(tmp_path: Path):
    ex = SubprocessExecutor(str(tmp_path / "work"), python_bin=sys.executable, work_quota_bytes=1_000_000)
    code = (
        "import os, time\n"
        "with open(os.path.join(os.environ['BRZ_OUT'], 'fill'), 'wb') as f:\n"
        "    for _ in range(3000):\n"
        "        f.write(b'x' * 65536); f.flush(); time.sleep(0.01)\n"
    )
    res = ex.run(StepRequest(step_id="fill", kind="python", code=code, timeout_s=30))
    assert res.exit_code == 125 and "work quota exceeded" in res.error


def test_gvisor_root_is_a_skeleton_not_the_host(tmp_path: Path):
    ex = GvisorExecutor(str(tmp_path / "work"), bundle_root=str(tmp_path / "b"), hosts_file=str(tmp_path / "hosts"))
    (tmp_path / "hosts").write_text("93.184.216.34 example.com\n")
    root = Path(ex.build_rootfs())
    assert "example.com" in (root / "etc" / "hosts").read_text()
    assert (root / "etc" / "nsswitch.conf").read_text().endswith("hosts: files\n")  # no dns source
    cfg = ex.oci_config(StepRequest(step_id="s1", kind="python", code=""), str(tmp_path / "work" / "steps" / "s1"))
    assert cfg["root"]["path"] == str(root)
    binds = [m for m in cfg["mounts"] if m["type"] == "bind" and m["destination"] != "/work"]
    assert binds and all("ro" in m["options"] for m in binds)
    assert not any(m["source"] in ("/", "/etc", "/root", "/home") for m in binds)


# ------------------------------------------------------------------ tokens pin the step, replies are authenticated
def test_token_pins_the_step_body():
    step = {"step_id": "s1", "kind": "python", "code": "print(1)"}
    assert step_digest(step) == step_digest(dict(reversed(list(step.items()))))
    tok = sign_step_token(KEY, task_id=TASK, step=step)
    args = {"task_id": TASK, "action": "exec", "step_id": "s1"}
    assert verify_token(KEY, tok, **args, body_sha256=step_digest(step))
    with pytest.raises(TokenError, match="step body"):
        verify_token(KEY, tok, **args, body_sha256=step_digest({**step, "code": "evil()"}))
    with pytest.raises(TokenError, match="step body"):
        verify_token(
            KEY,
            sign_token(KEY, task_id=TASK, scope=["exec"], step_id="s1"),
            **args,
            body_sha256=step_digest(step),
        )


def test_a_rejected_body_does_not_burn_the_token():
    step = {"step_id": "s1", "code": "a"}
    reg = TokenRegistry(KEY, TASK)
    tok = sign_step_token(KEY, task_id=TASK, step=step)
    with pytest.raises(TokenError):
        reg.consume(tok, action="exec", step_id="s1", body_sha256=step_digest({**step, "code": "b"}))
    assert reg.consume(tok, action="exec", step_id="s1", body_sha256=step_digest(step))


@pytest.fixture
def runner(tmp_path: Path):
    cfg = RunnerConfig(
        task_id=TASK,
        token_key=KEY,
        executor=SubprocessExecutor(str(tmp_path / "work"), python_bin=sys.executable),
        scan_paths=[str(tmp_path / "work")],
        scan_environ={"PATH": "/usr/bin"},
        host="127.0.0.1",
        port=0,
    )
    r = BackgroundRunner(cfg).start()
    yield r
    r.stop()


class _RewriteReplies(httpx.AsyncBaseTransport):
    """A man in the middle who keeps the per-file hash consistent, as a real attacker would."""

    def __init__(self) -> None:
        self.inner = httpx.AsyncHTTPTransport()

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        resp = await self.inner.handle_async_request(request)
        data = json.loads(await resp.aread())
        fake = b"forged"
        data["files"]["r.txt"] = {
            "sha256": hashlib.sha256(fake).hexdigest(),
            "size": len(fake),
            "content_b64": base64.b64encode(fake).decode(),
        }
        headers = [(k, v) for k, v in resp.headers.items() if k.lower() != "content-length"]
        return httpx.Response(resp.status_code, headers=headers, content=json.dumps(data).encode(), request=request)

    async def aclose(self) -> None:
        await self.inner.aclose()


async def test_client_rejects_a_rewritten_reply(runner: BackgroundRunner):
    step = PlanStep(id="s1", title="t", kind="python", code="print(1)")
    honest = RunnerClient(runner.url, task_id=TASK, token_key=KEY)
    assert (await honest.run_step(step)).exit_code == 0
    await honest.aclose()
    mitm = RunnerClient(runner.url, task_id=TASK, token_key=KEY, transport=_RewriteReplies())
    with pytest.raises(RunnerError, match="failed authentication"):
        await mitm.run_step(step)
    await mitm.aclose()


def test_reply_mac_is_bound_to_the_request_token():
    assert reply_mac(KEY, "token-a", b"{}") != reply_mac(KEY, "token-b", b"{}")


# ------------------------------------------------------------------ secrets
async def test_secret_in_stdout_is_redacted_and_fails_the_scan(runner: BackgroundRunner):
    client = RunnerClient(runner.url, task_id=TASK, token_key=KEY)
    code = "t = 'gh' + 'p_' + 'a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8'\nprint('here', t)"
    res = await client.run_step(PlanStep(id="s1", title="t", kind="python", code=code))
    assert FAKE_GH not in res.stdout and res.stdout.startswith("here ghp_")
    assert res.secret_findings[0]["kind"] == "github_token"
    report = await client.scan()
    assert report["clean"] is False and report["findings"][0]["where"] == "step:s1:stdout:1"
    await client.aclose()


def test_scanner_looks_inside_encodings():
    encoded = base64.b64encode(FAKE_GH.encode()).decode()
    assert [f.kind for f in scan_text(encoded, "x")] == ["github_token:base64"]
    assert [f.kind for f in scan_text(FAKE_GH.encode().hex(), "x")] == ["github_token:hex"]
    assert scan_text(hashlib.sha256(b"x").hexdigest(), "x") == []  # a plain hash is not a finding
    text, findings = scan_and_redact(f"a\n{FAKE_GH}\nb {encoded} c\npassword = correct-horse-battery\n", "x")
    assert len(findings) == 3
    assert FAKE_GH not in text and encoded not in text and "correct-horse-battery" not in text
    assert text.startswith("a\nghp_") and "b [redacted encoded secret] c" in text and "password = " in text


def test_scanner_reads_hidden_directories(tmp_path: Path):
    from brz_runner.secretscan import run_scan

    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "x").write_text(FAKE_GH)
    (tmp_path / "run").mkdir()
    (tmp_path / "run" / "y").write_text(FAKE_GH)
    assert len(run_scan([str(tmp_path)], environ={}).findings) == 2


# ------------------------------------------------------------------ egress
def test_vm_ruleset_has_no_dns_and_names_are_pinned():
    rs = build_ruleset(allowed_ipv4=["93.184.216.34"], control_plane_cidr="198.51.100.7/32", runner_port=8700)
    assert "dport 53" not in rs
    resolved = {"example.com": ["93.184.216.34", "93.184.216.35"], "*.pypi.org": ["151.101.0.223"], "gone.test": []}
    assert hosts_lines(resolved) == "93.184.216.34 example.com\n93.184.216.35 example.com\n"


# ------------------------------------------------------------------ repair may not widen the plan
def test_repair_may_change_code_but_not_widen_scope():
    base = PlanStep(id="s1", title="t", kind="python", code="a", expected_outputs=["r.json"], timeout_s=60)
    assert repair_violations(base, base.model_copy(update={"code": "b", "timeout_s": 30})) == []
    assert repair_violations(base, base.model_copy(update={"expected_outputs": ["r.json", "more.txt"]})) == []
    wide = base.model_copy(update={"needs_network": True, "timeout_s": 1800, "expected_outputs": []})
    assert len(repair_violations(base, wide)) == 3
