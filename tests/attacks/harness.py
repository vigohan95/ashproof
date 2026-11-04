"""Attack harness: drives the REAL runner (``python -m brz_runner``) over real HTTP with real tokens.

Everything here runs as root inside the WSL distro (or any Linux box with runsc installed): the runner
is the same program cloud-init starts in the throwaway VM, with the same token key file layout. Nothing
is mocked. Only the Python standard library is used, so the harness matches the runner's own constraint.

Safety rules for hostile steps, because the first run of this suite is against code that may be broken:
* canaries and decoys live under /opt/brz-decoy and /root/brz-canary-*; attacks aim at those, never at
  real system files, so a successful attack cannot damage the distro;
* a guard thread SIGKILLs the runner if it grows past ``RSS_GUARD_KB`` (a runaway read of /dev/zero
  would otherwise take the whole WSL VM down);
* every HTTP call has a timeout and every step has ``timeout_s``.
"""

from __future__ import annotations

import base64
import contextlib
import hashlib
import json
import os
import secrets
import shutil
import signal
import socket
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
RUNNER_PATH = REPO / "sandbox" / "runner"
if str(RUNNER_PATH) not in sys.path:
    sys.path.insert(0, str(RUNNER_PATH))

from brz_runner import tokens as brz_tokens  # noqa: E402

RUNSC = "/usr/local/bin/runsc"
KEY_FILE = "/etc/brz/token.key"
ROOT_CANARY = "/root/brz-canary-root.txt"
PUBLIC_CANARY = "/opt/brz-canary/public.txt"
DECOY_DIR = "/opt/brz-decoy"
DECOY_SECRET = f"{DECOY_DIR}/decoy-secret.txt"
ATTACK_ROOT = "/srv/brz-attacks"
RSS_GUARD_KB = 2_000_000
TASK_ID = "attack-suite"


def host_ip() -> str:
    """The distro's primary IPv4 (what a sandbox with a network would see as 'the host')."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("1.1.1.1", 53))  # UDP connect sends nothing; it only selects a route
        return s.getsockname()[0]
    finally:
        s.close()


def free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


@contextlib.contextmanager
def in_netns(name: str):
    """Run this thread in a named network namespace. Sockets made here stay in it after the block ends."""
    clone_newnet = 0x40000000
    home = os.open("/proc/thread-self/ns/net", os.O_RDONLY)
    target = os.open(f"/run/netns/{name}", os.O_RDONLY)
    try:
        os.setns(target, clone_newnet)
        yield
    finally:
        os.setns(home, clone_newnet)
        os.close(home)
        os.close(target)


# ------------------------------------------------------------------ process inspection
def _read(path: str) -> str:
    try:
        with open(path, "rb") as fh:
            return fh.read().decode("utf-8", "replace")
    except OSError:
        return ""


def proc_table() -> dict[int, dict]:
    """pid -> {ppid, state, comm, cmdline, rss_kb, threads}. Dead processes simply do not appear."""
    table: dict[int, dict] = {}
    for entry in os.listdir("/proc"):
        if not entry.isdigit():
            continue
        pid = int(entry)
        stat = _read(f"/proc/{pid}/stat")
        if not stat or ")" not in stat:
            continue
        comm = stat[stat.find("(") + 1 : stat.rfind(")")]
        rest = stat[stat.rfind(")") + 2 :].split()
        table[pid] = {
            "ppid": int(rest[1]),
            "state": rest[0],
            "comm": comm,
            "threads": int(rest[17]),
            "rss_kb": int(rest[21]) * 4,
            "cmdline": _read(f"/proc/{pid}/cmdline").replace("\0", " ").strip(),
        }
    return table


def descendants(root_pid: int, table: dict[int, dict] | None = None) -> list[int]:
    table = table if table is not None else proc_table()
    children: dict[int, list[int]] = {}
    for pid, info in table.items():
        children.setdefault(info["ppid"], []).append(pid)
    out: list[int] = []
    stack = [root_pid]
    while stack:
        for c in children.get(stack.pop(), []):
            out.append(c)
            stack.append(c)
    return out


def is_alive(pid: int) -> bool:
    """True while the pid exists and is not a zombie (a zombie has already stopped executing)."""
    stat = _read(f"/proc/{pid}/stat")
    if not stat or ")" not in stat:
        return False
    return stat[stat.rfind(")") + 2 :].split()[0] not in ("Z", "X")


def sandbox_leftovers() -> list[dict]:
    """Every live runsc/gVisor process on the box. This suite is the only runsc user here."""
    me = os.getpid()
    found = []
    for pid, info in proc_table().items():
        if pid == me or info["state"] in ("Z", "X"):
            continue
        hay = f"{info['comm']} {info['cmdline']}"
        if ("runsc" in hay or "gvisor" in hay) and "brz_runner" not in hay and "timeout" not in info["comm"]:
            found.append({"pid": pid, "comm": info["comm"], "cmdline": info["cmdline"][:160]})
    return found


def runsc_list() -> list[str]:
    try:
        out = subprocess.run([RUNSC, "list", "-quiet"], capture_output=True, text=True, timeout=20, check=False)
        return [ln.strip() for ln in out.stdout.splitlines() if ln.strip()]
    except (OSError, subprocess.TimeoutExpired) as exc:
        return [f"<runsc list failed: {exc}>"]


def clean_containers() -> None:
    for cid in runsc_list():
        if not cid.startswith("<"):
            subprocess.run([RUNSC, "delete", "-force", cid], capture_output=True, timeout=20, check=False)


class Sampler:
    """Background sampler of sandbox-side process count and memory while a hostile step runs."""

    def __init__(self, runner: RunnerHarness, interval_s: float = 0.05):
        self.runner = runner
        self.interval_s = interval_s
        self.peak_procs = 0
        self.peak_threads = 0
        self.peak_rss_kb = 0
        self.health_worst_ms = 0.0
        self.health_failures = 0
        self._stop = threading.Event()
        self._threads = [
            threading.Thread(target=self._sample, daemon=True),
            threading.Thread(target=self._health, daemon=True),
        ]

    def _sample(self) -> None:
        while not self._stop.is_set():
            table = proc_table()
            pids = descendants(self.runner.pid, table)
            self.peak_procs = max(self.peak_procs, len(pids))
            self.peak_threads = max(self.peak_threads, sum(table[p]["threads"] for p in pids if p in table))
            self.peak_rss_kb = max(self.peak_rss_kb, sum(table[p]["rss_kb"] for p in pids if p in table))
            self._stop.wait(self.interval_s)

    def _health(self) -> None:
        while not self._stop.is_set():
            t = time.perf_counter()
            try:
                with urllib.request.urlopen(f"{self.runner.url}/health", timeout=3) as resp:
                    resp.read()
                self.health_worst_ms = max(self.health_worst_ms, (time.perf_counter() - t) * 1000)
            except (OSError, urllib.error.URLError):
                self.health_failures += 1
            self._stop.wait(0.25)

    def __enter__(self) -> Sampler:
        for t in self._threads:
            t.start()
        return self

    def __exit__(self, *exc) -> None:
        self._stop.set()
        for t in self._threads:
            t.join(timeout=5)

    def to_dict(self) -> dict:
        return {
            "peak_host_processes": self.peak_procs,
            "peak_host_threads": self.peak_threads,
            "peak_host_rss_mb": round(self.peak_rss_kb / 1024, 1),
            "runner_health_worst_ms": round(self.health_worst_ms, 1),
            "runner_health_failures": self.health_failures,
        }


# ------------------------------------------------------------------ canaries
@dataclass
class Canaries:
    root_value: str = field(default_factory=lambda: "ROOTCANARY-" + secrets.token_hex(12))
    public_value: str = field(default_factory=lambda: "PUBLICCANARY-" + secrets.token_hex(12))
    decoy_value: str = field(default_factory=lambda: "DECOYCANARY-" + secrets.token_hex(12))

    def install(self) -> None:
        os.makedirs("/etc/brz", mode=0o755, exist_ok=True)
        with open(ROOT_CANARY, "w") as fh:
            fh.write(self.root_value)
        os.chmod(ROOT_CANARY, 0o600)
        os.makedirs(os.path.dirname(PUBLIC_CANARY), exist_ok=True)
        with open(PUBLIC_CANARY, "w") as fh:
            fh.write(self.public_value)
        os.chmod(PUBLIC_CANARY, 0o644)
        self.reset_decoy()

    def reset_decoy(self) -> None:
        shutil.rmtree(DECOY_DIR, ignore_errors=True)
        os.makedirs(DECOY_DIR, mode=0o755)
        with open(DECOY_SECRET, "w") as fh:
            fh.write(self.decoy_value)
        os.chmod(DECOY_SECRET, 0o600)

    def decoy_state(self) -> dict:
        """Everything an attack could have changed in the decoy directory, as seen from the host."""
        st = os.lstat(DECOY_DIR)
        files = {}
        for name in sorted(os.listdir(DECOY_DIR)):
            s = os.lstat(os.path.join(DECOY_DIR, name))
            files[name] = {"uid": s.st_uid, "mode": oct(s.st_mode & 0o7777), "size": s.st_size}
        return {"dir_uid": st.st_uid, "dir_mode": oct(st.st_mode & 0o7777), "files": files}

    def decoy_intact(self) -> bool:
        state = self.decoy_state()
        expected = {"decoy-secret.txt": {"uid": 0, "mode": "0o600", "size": len(self.decoy_value)}}
        return state["dir_uid"] == 0 and state["files"] == expected

    def remove(self) -> None:
        for path in (ROOT_CANARY, KEY_FILE):
            with contextlib.suppress(OSError):
                os.remove(path)
        shutil.rmtree(os.path.dirname(PUBLIC_CANARY), ignore_errors=True)
        shutil.rmtree(DECOY_DIR, ignore_errors=True)


# ------------------------------------------------------------------ the runner under attack
class RunnerHarness:
    def __init__(
        self,
        name: str,
        *,
        key: bytes | None = None,
        bind: str = "127.0.0.1",
        connect_host: str | None = None,
        port: int | None = None,
        wrapper: list[str] | None = None,
        extra_args: list[str] | None = None,
        task_id: str = TASK_ID,
    ):
        self.name = name
        self.key = key or secrets.token_bytes(32)
        self.task_id = task_id
        self.bind = bind
        self.port = port or free_port()
        self.url = f"http://{connect_host or '127.0.0.1'}:{self.port}"
        self.workroot = f"{ATTACK_ROOT}/{name}"
        self.wrapper = wrapper or []
        self.extra_args = extra_args or []
        self.proc: subprocess.Popen | None = None
        self.rss_guard_tripped = False
        self.steps: list[dict] = []  # every request/response, for the evidence file
        self._guard_stop = threading.Event()

    # -- lifecycle
    def start(self) -> RunnerHarness:
        shutil.rmtree(self.workroot, ignore_errors=True)
        os.makedirs(self.workroot, exist_ok=True)
        os.makedirs(os.path.dirname(KEY_FILE), mode=0o755, exist_ok=True)
        with open(KEY_FILE, "w") as fh:  # same file layout as cloud-init: 64 hex chars, root 0600
            fh.write(self.key.hex())
        os.chmod(KEY_FILE, 0o600)
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "PYTHONPATH": str(RUNNER_PATH),
            "PYTHONDONTWRITEBYTECODE": "1",
        }
        cmd = [
            *self.wrapper,
            sys.executable,
            "-m",
            "brz_runner",
            "--task-id",
            self.task_id,
            "--token-key-file",
            KEY_FILE,
            "--workroot",
            self.workroot,
            "--runsc",
            RUNSC,
            "--host",
            self.bind,
            "--port",
            str(self.port),
            "--no-journal",
            "--scan-path",
            self.workroot,
            *self.extra_args,
        ]
        self.log_path = f"{self.workroot}.runner.log"
        log = open(self.log_path, "wb")  # noqa: SIM115 - lives as long as the child
        self.proc = subprocess.Popen(
            cmd, stdout=log, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL, env=env, start_new_session=True
        )
        log.close()
        deadline = time.time() + 15
        while time.time() < deadline:
            status, _ = self.get("/health", timeout=1)
            if status == 200:
                threading.Thread(target=self._rss_guard, daemon=True).start()
                return self
            if self.proc.poll() is not None:
                break
            time.sleep(0.05)
        raise RuntimeError(f"runner did not start: {_read(self.log_path)[-600:]}")

    @property
    def pid(self) -> int:
        assert self.proc is not None
        return self.proc.pid

    def _rss_guard(self) -> None:
        while not self._guard_stop.wait(0.1):
            status = _read(f"/proc/{self.pid}/status")
            for line in status.splitlines():
                if line.startswith("VmRSS:") and int(line.split()[1]) > RSS_GUARD_KB:
                    self.rss_guard_tripped = True
                    with contextlib.suppress(OSError):
                        os.kill(self.pid, signal.SIGKILL)
                    return

    def peak_rss_kb(self) -> int:
        for line in _read(f"/proc/{self.pid}/status").splitlines():
            if line.startswith("VmHWM:"):
                return int(line.split()[1])
        return 0

    def alive(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def stop(self) -> None:
        self._guard_stop.set()
        if self.proc is not None:
            with contextlib.suppress(OSError):
                os.killpg(self.proc.pid, signal.SIGKILL)
            with contextlib.suppress(subprocess.TimeoutExpired):
                self.proc.wait(timeout=5)
        clean_containers()

    def __enter__(self) -> RunnerHarness:
        return self.start()

    def __exit__(self, *exc) -> None:
        self.stop()

    # -- HTTP
    def get(self, path: str, timeout: float = 5) -> tuple[int | None, dict]:
        try:
            with urllib.request.urlopen(self.url + path, timeout=timeout) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            return exc.code, {}
        except (OSError, urllib.error.URLError, ValueError) as exc:
            return None, {"error": repr(exc)}

    def post(self, path: str, body: dict, timeout: float = 60) -> tuple[int | None, dict]:
        data = json.dumps(body).encode("utf-8")
        req = urllib.request.Request(self.url + path, data=data, headers={"content-type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return resp.status, json.loads(resp.read())
        except urllib.error.HTTPError as exc:
            try:
                return exc.code, json.loads(exc.read())
            except ValueError:
                return exc.code, {}
        except (OSError, urllib.error.URLError, ValueError) as exc:
            return None, {"error": repr(exc)}

    # -- tokens
    def step_token(self, step: dict, **kw) -> str:
        """A valid exec token for ``step``. Binds the body hash when the runner supports it."""
        kw.setdefault("step_id", str(step["step_id"]))
        digest = getattr(brz_tokens, "step_digest", None)
        if digest is not None:
            kw.setdefault("body_sha256", digest(step))
        return brz_tokens.sign_token(self.key, task_id=self.task_id, scope=["exec"], **kw)

    def token(self, action: str, **kw) -> str:
        return brz_tokens.sign_token(self.key, task_id=self.task_id, scope=[action], **kw)

    # -- steps
    def step_dict(self, code: str, *, kind: str = "python", step_id: str = "s1", timeout_s: int = 20, **extra) -> dict:
        step = {"step_id": step_id, "kind": kind, "code": code, "timeout_s": timeout_s}
        files = extra.pop("files", None)
        if files:
            step["files"] = {n: base64.b64encode(b).decode("ascii") for n, b in files.items()}
        step.update(extra)
        return step

    def step(self, code: str, *, http_timeout: float | None = None, **kw) -> tuple[int | None, dict]:
        step = self.step_dict(code, **kw)
        t = time.perf_counter()
        status, res = self.post(
            "/steps",
            {"token": self.step_token(step), "step": step},
            timeout=http_timeout or step["timeout_s"] + 25,
        )
        self.record(step, status, res, time.perf_counter() - t)
        return status, res

    def record(self, step: dict, status: int | None, res: dict, wall_s: float) -> None:
        files = res.get("files") or {}
        self.steps.append(
            {
                "step_id": step.get("step_id"),
                "kind": step.get("kind"),
                "code": step.get("code"),
                "needs_network": step.get("needs_network", False),
                "timeout_s": step.get("timeout_s"),
                "http_status": status,
                "wall_s": round(wall_s, 3),
                "executor": res.get("executor"),
                "exit_code": res.get("exit_code"),
                "timed_out": res.get("timed_out"),
                "stdout_tail": str(res.get("stdout", ""))[-1500:],
                "stderr_tail": str(res.get("stderr", ""))[-800:],
                "error": res.get("error", ""),
                "output_files": {n: {"size": m.get("size"), "sha256": m.get("sha256")} for n, m in files.items()},
                "response_keys": sorted(res),
            }
        )

    def file_bytes(self, res: dict, name: str) -> bytes | None:
        meta = (res.get("files") or {}).get(name)
        if not meta or not meta.get("content_b64"):
            return None
        return base64.b64decode(meta["content_b64"])


def sha256_hex(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def json_stdout(res: dict) -> dict:
    """Hostile steps print one JSON object as their last line; anything else means the step broke."""
    for line in reversed(str(res.get("stdout", "")).strip().splitlines()):
        try:
            obj = json.loads(line)
            if isinstance(obj, dict):
                return obj
        except ValueError:
            continue
    return {}
