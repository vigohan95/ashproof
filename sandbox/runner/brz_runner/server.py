"""Runner HTTP server (standard library ``http.server``; threaded).

Endpoints (all JSON):

* ``GET  /health``   -> {ok, task_id, executor, revoked, version}
* ``POST /steps``    {token, step:{step_id, kind, code, files{name:b64}, timeout_s, expected_outputs}}
                     -> StepResult + egress attempts observed during the step + secret findings.
                     stdout and stderr are redacted before they leave the runner: they feed model
                     prompts on the control plane.
* ``POST /scan``     {token, paths?} -> secret-hygiene report (env + work tree + system env files)
* ``POST /egress``   {token} -> all egress attempts seen so far
* ``POST /revoke``   {token, poweroff?} -> kill switch: reject every later request, kill running step

Every POST needs a single-use capability token for that action (scope ``exec``, ``scan``,
``egress`` or ``revoke``); an ``exec`` token also pins the step body. Successful replies carry
``X-BRZ-Reply-MAC``. The token key arrives via cloud-init at /etc/brz/token.key.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import __version__
from .executor import BaseExecutor, StepRequest
from .netlog import EgressReader, NullEgressReader
from .secretscan import Finding, run_scan, scan_and_redact, scan_text
from .tokens import TokenError, TokenRegistry, reply_mac, step_digest

DEFAULT_SCAN_PATHS = ["/work", "/etc/environment", "/etc/profile.d", "/root", "/home", "/etc/brz/task.env"]
ALLOWED_STEP_ENV_PREFIXES = ("BRZ_", "TASK_", "LC_", "LANG", "TZ", "PYTHON")


@dataclass
class RunnerConfig:
    task_id: str
    token_key: bytes
    executor: BaseExecutor
    egress: EgressReader = field(default_factory=NullEgressReader)
    scan_paths: list[str] = field(default_factory=lambda: list(DEFAULT_SCAN_PATHS))
    host: str = "0.0.0.0"
    port: int = 8700
    allow_poweroff: bool = False  # True inside the VM: /revoke {poweroff:true} runs systemctl poweroff
    scan_environ: dict[str, str] | None = None  # None = the runner's real os.environ (tests pass a fixed dict)
    max_body_bytes: int = 64_000_000


class RunnerState:
    def __init__(self, cfg: RunnerConfig):
        self.cfg = cfg
        self.tokens = TokenRegistry(cfg.token_key, cfg.task_id)
        self.started_at = datetime.now(timezone.utc)
        self.steps_run = 0
        self.lock = threading.Lock()  # one step at a time
        self.events: list[dict] = []
        self.step_findings: list[Finding] = []  # secrets seen in step output; /scan reports them too

    def _note(self, event: str, **data) -> None:
        self.events.append({"ts": datetime.now(timezone.utc).isoformat(), "kind": event, **data})


class _Handler(BaseHTTPRequestHandler):
    server_version = f"brz-runner/{__version__}"
    state: RunnerState  # injected by make_server
    _reply_token: str | None = None

    # ---- plumbing
    def log_message(self, fmt: str, *args) -> None:  # quiet by default
        if os.environ.get("BRZ_RUNNER_DEBUG"):
            sys.stderr.write(f"{self.address_string()} - {fmt % args}\n")

    def _send(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if self._reply_token is not None and status < 400:
            self.send_header("X-BRZ-Reply-MAC", reply_mac(self.state.cfg.token_key, self._reply_token, body))
        self.end_headers()
        self.wfile.write(body)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length") or 0)
        if length > self.state.cfg.max_body_bytes:
            raise ValueError("body too large")
        raw = self.rfile.read(length) if length else b"{}"
        data = json.loads(raw.decode("utf-8") or "{}")
        if not isinstance(data, dict):
            raise ValueError("body must be a JSON object")
        return data

    def _authorize(
        self, body: dict, action: str, step_id: str | None = None, body_sha256: str | None = None
    ) -> dict | None:
        token = body.get("token")
        if not isinstance(token, str):
            self._send(401, {"error": "token required"})
            return None
        try:
            payload = self.state.tokens.consume(token, action=action, step_id=step_id, body_sha256=body_sha256)
            self._reply_token = token
            return payload
        except TokenError as exc:
            self.state._note("auth.denied", action=action, reason=str(exc))
            self._send(403, {"error": f"token rejected: {exc}"})
            return None

    # ---- routes
    def do_GET(self) -> None:  # noqa: N802
        if self.path.split("?")[0] == "/health":
            st = self.state
            self._send(
                200,
                {
                    "ok": not st.tokens.revoked,
                    "task_id": st.cfg.task_id,
                    "executor": st.cfg.executor.name,
                    "revoked": st.tokens.revoked,
                    "steps_run": st.steps_run,
                    "started_at": st.started_at.isoformat(),
                    "version": __version__,
                    "egress_source": getattr(st.cfg.egress, "source", "unknown"),
                },
            )
            return
        self._send(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        path = self.path.split("?")[0]
        self._reply_token = None
        try:
            body = self._read_json()
        except ValueError as exc:
            self._send(400, {"error": f"bad request: {exc}"})
            return
        if path == "/steps":
            self._post_steps(body)
        elif path == "/scan":
            self._post_scan(body)
        elif path == "/egress":
            self._post_egress(body)
        elif path == "/revoke":
            self._post_revoke(body)
        else:
            self._send(404, {"error": "not found"})

    def _post_steps(self, body: dict) -> None:
        st = self.state
        step_dict = body.get("step")
        if not isinstance(step_dict, dict) or "step_id" not in step_dict:
            self._send(400, {"error": "step object with step_id required"})
            return
        step_id = str(step_dict["step_id"])
        if self._authorize(body, "exec", step_id, step_digest(step_dict)) is None:
            return
        try:
            step = StepRequest.from_dict(step_dict)
        except (KeyError, ValueError) as exc:
            self._send(400, {"error": f"invalid step: {exc}"})
            return
        bad_env = [k for k in step.env if not k.startswith(ALLOWED_STEP_ENV_PREFIXES)]
        if bad_env:
            self._send(400, {"error": f"step env not allowed (no secrets reach the sandbox): {bad_env}"})
            return
        if not st.lock.acquire(timeout=1.0):
            self._send(409, {"error": "another step is running"})
            return
        try:
            since = datetime.now(timezone.utc).isoformat()
            st._note("step.start", step_id=step_id, kind=step.kind)
            result = st.cfg.executor.run(step)
            st.steps_run += 1
            attempts = [a.to_dict() for a in st.cfg.egress.read_since(since)]
            findings = self._screen_output(result)
            st._note("step.end", step_id=step_id, exit_code=result.exit_code, egress_attempts=len(attempts))
        finally:
            st.lock.release()
        if st.tokens.revoked:  # killed mid-step
            self._send(410, {"error": "task revoked during step", "result": result.to_dict(include_content=False)})
            return
        payload = result.to_dict()
        payload["egress_attempts"] = attempts
        payload["missing_expected_outputs"] = [n for n in step.expected_outputs if n not in result.files]
        payload["secret_findings"] = [asdict(f) for f in findings]
        self._send(200, payload)

    def _screen_output(self, result) -> list[Finding]:
        """Redact secrets from the streams and remember every finding, so the final scan cannot miss them."""
        result.stdout, findings = scan_and_redact(result.stdout, f"step:{result.step_id}:stdout")
        result.stderr, more = scan_and_redact(result.stderr, f"step:{result.step_id}:stderr")
        findings = findings + more
        for name, data in result.files.items():
            findings += scan_text(data.decode("utf-8", "replace"), f"step:{result.step_id}:file:{name}")
        self.state.step_findings.extend(findings)
        return findings

    def _post_scan(self, body: dict) -> None:
        if self._authorize(body, "scan") is None:
            return
        paths = body.get("paths") or self.state.cfg.scan_paths
        report = run_scan([str(p) for p in paths], environ=self.state.cfg.scan_environ)
        report.findings = [*self.state.step_findings, *report.findings]
        report.clean = not report.findings
        self.state._note("scan.done", clean=report.clean, findings=len(report.findings))
        self._send(200, report.to_dict())

    def _post_egress(self, body: dict) -> None:
        if self._authorize(body, "egress") is None:
            return
        attempts = [a.to_dict() for a in self.state.cfg.egress.read_since(None)]
        self._send(200, {"attempts": attempts, "source": getattr(self.state.cfg.egress, "source", "unknown")})

    def _post_revoke(self, body: dict) -> None:
        st = self.state
        if self._authorize(body, "revoke") is None:
            return
        st.tokens.revoke_all()
        killed = st.cfg.executor.kill_current()
        st._note("revoked", killed_running_step=killed)
        poweroff = bool(body.get("poweroff")) and st.cfg.allow_poweroff
        self._send(
            200,
            {
                "revoked": True,
                "killed_running_step": killed,
                "poweroff": poweroff,
                "revoked_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        if poweroff:
            threading.Timer(1.0, lambda: subprocess.run(["systemctl", "poweroff"], check=False)).start()


def make_server(cfg: RunnerConfig) -> ThreadingHTTPServer:
    state = RunnerState(cfg)
    handler = type("BoundHandler", (_Handler,), {"state": state})
    server = ThreadingHTTPServer((cfg.host, cfg.port), handler)
    server.daemon_threads = True
    server.brz_state = state  # type: ignore[attr-defined]
    return server


class BackgroundRunner:
    """Run the server in a daemon thread (tests + local sandbox backend)."""

    def __init__(self, cfg: RunnerConfig):
        self.server = make_server(cfg)
        self.thread = threading.Thread(target=self.server.serve_forever, name="brz-runner", daemon=True)

    @property
    def port(self) -> int:
        return int(self.server.server_address[1])

    @property
    def url(self) -> str:
        host = self.server.server_address[0]
        if host in ("0.0.0.0", "::"):
            host = "127.0.0.1"
        return f"http://{host}:{self.port}"

    @property
    def state(self) -> RunnerState:
        return self.server.brz_state  # type: ignore[attr-defined]

    def start(self) -> BackgroundRunner:
        self.thread.start()
        deadline = time.time() + 5
        while time.time() < deadline and not self.thread.is_alive():
            time.sleep(0.01)
        return self

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()
