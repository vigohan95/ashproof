"""Runner tests: executor without gVisor, the HTTP server with real tokens, kill switch, gVisor bundle."""

from __future__ import annotations

import json
import os
import sys
import threading
import time
from pathlib import Path

import httpx
import pytest
from brz_runner.executor import GvisorExecutor, StepRequest, SubprocessExecutor
from brz_runner.netlog import StaticEgressReader
from brz_runner.server import BackgroundRunner, RunnerConfig
from brz_runner.tokens import new_key, sign_token

from brz.llm import PlanStep
from brz.sandbox import RunnerClient, RunnerError

KEY = new_key()
TASK = "task-runner-1"

PY_STEP = """
import csv, json, os, sys
inp = os.path.join(os.environ["BRZ_INPUT"], "sales.csv")
out = os.path.join(os.environ["BRZ_OUT"], "summary.json")
totals = {}
with open(inp, newline="") as fh:
    for row in csv.DictReader(fh):
        totals[row["region"]] = totals.get(row["region"], 0) + float(row["amount"])
with open(out, "w") as fh:
    json.dump(dict(sorted(totals.items())), fh, sort_keys=True)
print("regions:", len(totals))
sys.stderr.write("note: stderr is captured too\\n")
"""
CSV = b"region,amount\nnorth,10\nsouth,20\nnorth,5\n"


# ----------------------------------------------------------------- executor
def test_subprocess_executor_runs_python_step(tmp_path: Path):
    ex = SubprocessExecutor(str(tmp_path), python_bin=sys.executable)
    res = ex.run(
        StepRequest(
            step_id="s1",
            kind="python",
            code=PY_STEP,
            files={"sales.csv": CSV},
            expected_outputs=["summary.json"],
            timeout_s=60,
        )
    )
    assert res.exit_code == 0 and not res.timed_out and res.executor == "subprocess"
    assert res.stdout.strip() == "regions: 2" and "stderr is captured" in res.stderr
    assert json.loads(res.files["summary.json"]) == {"north": 15.0, "south": 20.0}
    assert res.file_hashes()["summary.json"] == __import__("hashlib").sha256(res.files["summary.json"]).hexdigest()
    d = res.to_dict()
    assert d["files"]["summary.json"]["size"] == len(res.files["summary.json"]) and d["stdout_sha256"]
    # step code is run with -I (isolated): no site, no user env PYTHONPATH tricks
    assert (tmp_path / "steps" / "s1" / "main.py").read_text() == PY_STEP


def test_subprocess_executor_timeout_and_failure(tmp_path: Path):
    ex = SubprocessExecutor(str(tmp_path), python_bin=sys.executable)
    slow = ex.run(StepRequest(step_id="slow", kind="python", code="import time; time.sleep(30)", timeout_s=1))
    assert slow.timed_out and slow.exit_code == 124 and slow.duration_s < 10
    bad = ex.run(StepRequest(step_id="bad", kind="python", code="raise SystemExit(3)"))
    assert bad.exit_code == 3
    with pytest.raises(ValueError):
        ex.run(StepRequest(step_id="x", kind="python", code="", files={"../escape.txt": b"x"}))
    with pytest.raises(ValueError):
        ex.run(StepRequest(step_id="x", kind="ruby", code="puts 1"))


@pytest.mark.skipif(sys.platform == "win32" and not __import__("shutil").which("sh"), reason="needs sh")
def test_subprocess_executor_shell_step(tmp_path: Path):
    ex = SubprocessExecutor(str(tmp_path), python_bin=sys.executable)
    res = ex.run(
        StepRequest(step_id="sh1", kind="shell", code='echo "hello $BRZ_STEP_ID" > "$BRZ_OUT/hi.txt"; echo done')
    )
    assert res.exit_code == 0 and res.stdout.strip() == "done"
    assert res.files["hi.txt"].strip() == b"hello sh1"


def test_executor_env_has_no_host_secrets(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("VULTR_API_KEY", "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY")
    ex = SubprocessExecutor(str(tmp_path), python_bin=sys.executable)
    res = ex.run(
        StepRequest(step_id="env", kind="python", code="import os, json; print(json.dumps(sorted(os.environ)))")
    )
    names = json.loads(res.stdout)
    assert "VULTR_API_KEY" not in names and "AWS_SECRET_ACCESS_KEY" not in names
    assert {"BRZ_WORK", "BRZ_OUT", "BRZ_INPUT", "PATH"} <= set(names)


def test_gvisor_executor_bundle_config(tmp_path: Path):
    ex = GvisorExecutor(str(tmp_path / "work"), bundle_root=str(tmp_path / "bundles"), runsc_bin="/usr/local/bin/runsc")
    step = StepRequest(step_id="s1", kind="python", code="print(1)")
    _inp, _out, step_dir = ex.prepare(step)
    cmd = ex.command(step, step_dir)
    assert cmd[:4] == ["/usr/local/bin/runsc", "--platform=systrap", "--network=sandbox", "--rootless=false"]
    assert "run" in cmd and "--bundle" in cmd
    cfg = json.loads((tmp_path / "bundles" / "s1" / "config.json").read_text())
    assert cfg["process"]["args"] == ["python3", "-I", "/work/steps/s1/main.py"]
    assert cfg["process"]["user"] == {"uid": 1000, "gid": 1000}
    assert cfg["process"]["noNewPrivileges"] is True and cfg["process"]["capabilities"]["bounding"] == []
    assert cfg["root"] == {"path": "/", "readonly": True}
    work_mount = next(m for m in cfg["mounts"] if m["destination"] == "/work")
    assert work_mount["source"] == str(tmp_path / "work") and "rw" in work_mount["options"]
    assert {ns["type"] for ns in cfg["linux"]["namespaces"]} == {"pid", "network", "ipc", "uts", "mount"}
    assert cfg["linux"]["resources"]["memory"]["limit"] == 1_500_000_000
    assert any(e.startswith("BRZ_OUT=/work/out") for e in cfg["process"]["env"])
    shell = StepRequest(step_id="s2", kind="shell", code="echo hi")
    _i, _o, sd2 = ex.prepare(shell)
    assert ex.inner_command(shell, sd2) == ["/bin/sh", "/work/steps/s2/main.sh"]


# -------------------------------------------------------------------- server
@pytest.fixture
def runner(tmp_path: Path):
    deny_line = (
        "2026-11-05T12:00:03+0000 brz kernel: BRZ-EGRESS-DENY IN= OUT=eth0 SRC=10.0.0.5 "
        "DST=93.184.216.34 PROTO=TCP SPT=1 DPT=443"
    )
    cfg = RunnerConfig(
        task_id=TASK,
        token_key=KEY,
        executor=SubprocessExecutor(str(tmp_path / "work"), python_bin=sys.executable),
        egress=StaticEgressReader([deny_line]),
        scan_paths=[str(tmp_path / "work")],
        scan_environ={"PATH": "/usr/bin", "BRZ_WORK": str(tmp_path / "work")},  # the VM's env, not this host's
        host="127.0.0.1",
        port=0,
    )
    bg = BackgroundRunner(cfg).start()
    yield bg
    bg.stop()


@pytest.fixture
async def client(runner: BackgroundRunner):
    c = RunnerClient(runner.url, task_id=TASK, token_key=KEY)
    yield c
    await c.aclose()


async def test_server_health_step_scan_egress(client: RunnerClient, runner: BackgroundRunner):
    h = await client.wait_ready(timeout=5)
    assert h["ok"] and h["task_id"] == TASK and h["executor"] == "subprocess" and h["egress_source"] == "static"

    step = PlanStep(id="s1", title="aggregate", kind="python", code=PY_STEP, expected_outputs=["summary.json"])
    res = await client.run_step(step, files={"sales.csv": CSV})
    assert res.exit_code == 0 and res.missing_expected_outputs == []
    assert json.loads(res.file_text("summary.json")) == {"north": 15.0, "south": 20.0}
    assert res.file_hashes["summary.json"] == res.files["summary.json"].sha256
    assert len(res.egress_attempts) == 1 and res.egress_attempts[0]["verdict"] == "denied"

    scan = await client.scan()
    assert scan["clean"] is True and scan["files_scanned"] >= 2 and scan["env_vars_checked"] > 0

    # plant a fake key in the work tree -> scan now reports it, redacted
    (Path(runner.state.cfg.executor.workroot) / "out" / "leak.txt").write_text("ghp_" + "Q" * 36)
    scan2 = await client.scan()
    assert scan2["clean"] is False and scan2["findings"][0]["kind"] == "github_token"
    assert "Q" * 36 not in json.dumps(scan2)

    egress = await client.egress()
    assert egress and egress[0]["dst_ip"] == "93.184.216.34"
    assert client.tokens_issued == 4  # step + scan + scan + egress (health needs no token)


async def test_server_rejects_bad_tokens(client: RunnerClient, runner: BackgroundRunner):
    await client.wait_ready(timeout=5)
    async with httpx.AsyncClient(base_url=runner.url) as raw:
        # no token
        r = await raw.post("/steps", json={"step": {"step_id": "s1", "kind": "python", "code": "print(1)"}})
        assert r.status_code == 401
        # wrong key
        bad = sign_token(new_key(), task_id=TASK, scope=["exec"], step_id="s1")
        r = await raw.post(
            "/steps", json={"token": bad, "step": {"step_id": "s1", "kind": "python", "code": "print(1)"}}
        )
        assert r.status_code == 403 and "bad signature" in r.json()["error"]
        # exec token used for revoke -> scope error
        tok = sign_token(KEY, task_id=TASK, scope=["exec"], step_id="s1")
        r = await raw.post("/revoke", json={"token": tok})
        assert r.status_code == 403 and "scope" in r.json()["error"]
        # token bound to s1 used for s2
        r = await raw.post(
            "/steps", json={"token": tok, "step": {"step_id": "s2", "kind": "python", "code": "print(1)"}}
        )
        assert r.status_code == 403 and "bound to step" in r.json()["error"]
        # replay: valid token twice
        r1 = await raw.post(
            "/steps", json={"token": tok, "step": {"step_id": "s1", "kind": "python", "code": "print(1)"}}
        )
        assert r1.status_code == 200 and r1.json()["stdout"].strip() == "1"
        r2 = await raw.post(
            "/steps", json={"token": tok, "step": {"step_id": "s1", "kind": "python", "code": "print(1)"}}
        )
        assert r2.status_code == 403 and "already used" in r2.json()["error"]
        # secrets cannot be smuggled in via step env
        tok3 = sign_token(KEY, task_id=TASK, scope=["exec"], step_id="s3")
        r = await raw.post(
            "/steps",
            json={
                "token": tok3,
                "step": {"step_id": "s3", "kind": "python", "code": "print(1)", "env": {"OPENAI_API_KEY": "sk-xxx"}},
            },
        )
        assert r.status_code == 400 and "no secrets reach the sandbox" in r.json()["error"]
        # unknown route / bad json
        assert (await raw.post("/nope", json={})).status_code == 404
        assert (await raw.post("/steps", content=b"not json")).status_code == 400
        assert (await raw.get("/nope")).status_code == 404


async def test_kill_switch_revokes_and_kills_running_step(client: RunnerClient, runner: BackgroundRunner):
    await client.wait_ready(timeout=5)
    results: dict = {}

    def run_slow():
        import asyncio

        async def go():
            c = RunnerClient(runner.url, task_id=TASK, token_key=KEY)
            try:
                try:
                    results["res"] = await c.run_step(
                        PlanStep(
                            id="slow",
                            title="sleep",
                            kind="python",
                            code="import time; time.sleep(20); print('late')",
                            timeout_s=60,
                        )
                    )
                except RunnerError as exc:
                    results["err"] = exc
            finally:
                await c.aclose()

        asyncio.run(go())

    t = threading.Thread(target=run_slow)
    t.start()
    deadline = time.time() + 5
    while time.time() < deadline and runner.state.cfg.executor._current is None:
        time.sleep(0.05)
    assert runner.state.cfg.executor._current is not None, "slow step did not start"

    rev = await client.revoke()
    assert rev["revoked"] is True and rev["killed_running_step"] is True and rev["poweroff"] is False
    t.join(timeout=10)
    assert "err" in results and results["err"].status == 410  # step reported as revoked mid-run

    h = await client.health()
    assert h["ok"] is False and h["revoked"] is True
    with pytest.raises(RunnerError) as exc:
        await client.scan()
    assert exc.value.status == 403 and "revoked" in str(exc.value)
    with pytest.raises(RunnerError):
        await client.run_step(PlanStep(id="s9", title="x", kind="python", code="print(1)"))
    kinds = [e["kind"] for e in runner.state.events]
    assert "revoked" in kinds and "auth.denied" in kinds


async def test_wait_ready_times_out_against_dead_port():
    c = RunnerClient("http://127.0.0.1:9", task_id=TASK, token_key=KEY, timeout=0.5)

    async def no_sleep(_):
        return None

    clock = iter([0.0, 10.0, 20.0, 30.0])
    with pytest.raises(RunnerError, match="not ready"):
        await c.wait_ready(timeout=5, interval=1, sleep=no_sleep, clock=lambda: next(clock))
    await c.aclose()


def test_runner_cli_parser(tmp_path: Path):
    from brz_runner.__main__ import build_parser, load_key

    args = build_parser().parse_args(["--task-id", "t", "--token-key-hex", KEY.hex(), "--no-gvisor", "--port", "1"])
    assert load_key(args) == KEY and args.no_gvisor and args.port == 1
    kf = tmp_path / "token.key"
    kf.write_text(KEY.hex())
    args = build_parser().parse_args(["--task-id", "t", "--token-key-file", str(kf)])
    assert load_key(args) == KEY
    kf.write_bytes(KEY)
    assert load_key(build_parser().parse_args(["--task-id", "t", "--token-key-file", str(kf)])) == KEY
    assert os.path.basename(args.workroot) == "work"
