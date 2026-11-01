"""Step executors (standard library only).

* :class:`SubprocessExecutor` - runs the step as a child process of the runner. Used for
  local tests (``--no-gvisor``) and as the emergency fallback if runsc is unavailable.
* :class:`GvisorExecutor` - wraps the same step in an OCI bundle and runs it with
  ``runsc --platform=systrap`` (user-space kernel, no KVM required, works inside any VM).
  The bundle/config generation is unit-tested; the actual ``runsc run`` is exercised on
  event day (see docs/EVENT-DAY-TODO.md).

Both produce the same :class:`StepResult`: exit code, stdout/stderr (capped), the files
written under ``<work>/out`` (capped), duration, and which executor produced it.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass, field

MAX_STREAM_BYTES = 256_000
MAX_FILE_BYTES = 5_000_000
MAX_TOTAL_FILE_BYTES = 20_000_000


@dataclass
class StepRequest:
    step_id: str
    kind: str  # "python" | "shell"
    code: str
    files: dict[str, bytes] = field(default_factory=dict)  # input files -> <work>/input/<name>
    timeout_s: int = 120
    expected_outputs: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)  # extra NON-secret env (validated by the server)
    needs_network: bool = False  # gVisor: --network=host (VM nftables still decides) vs --network=none

    @classmethod
    def from_dict(cls, d: dict) -> StepRequest:
        import base64

        files = {name: base64.b64decode(b64) for name, b64 in (d.get("files") or {}).items()}
        return cls(
            step_id=str(d["step_id"]),
            kind=str(d.get("kind", "python")),
            code=str(d.get("code", "")),
            files=files,
            timeout_s=int(d.get("timeout_s", 120)),
            expected_outputs=list(d.get("expected_outputs") or []),
            env={str(k): str(v) for k, v in (d.get("env") or {}).items()},
            needs_network=bool(d.get("needs_network", False)),
        )


@dataclass
class StepResult:
    step_id: str
    exit_code: int
    stdout: str
    stderr: str
    duration_s: float
    files: dict[str, bytes] = field(default_factory=dict)
    timed_out: bool = False
    executor: str = ""
    error: str = ""

    def file_hashes(self) -> dict[str, str]:
        return {name: hashlib.sha256(data).hexdigest() for name, data in sorted(self.files.items())}

    def to_dict(self, *, include_content: bool = True) -> dict:
        import base64

        return {
            "step_id": self.step_id,
            "exit_code": self.exit_code,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "stdout_sha256": hashlib.sha256(self.stdout.encode("utf-8")).hexdigest(),
            "stderr_sha256": hashlib.sha256(self.stderr.encode("utf-8")).hexdigest(),
            "duration_s": round(self.duration_s, 3),
            "timed_out": self.timed_out,
            "executor": self.executor,
            "error": self.error,
            "files": {
                name: {
                    "sha256": hashlib.sha256(data).hexdigest(),
                    "size": len(data),
                    "content_b64": base64.b64encode(data).decode("ascii") if include_content else None,
                }
                for name, data in sorted(self.files.items())
            },
        }


def _safe_name(name: str) -> str:
    base = os.path.basename(name.replace("\\", "/"))
    if not base or base in (".", "..") or base != name:
        raise ValueError(f"unsafe file name: {name!r}")
    return base


class BaseExecutor:
    name = "base"

    def __init__(self, workroot: str, *, python_bin: str = "python3", shell_bin: str = "/bin/sh"):
        self.workroot = os.path.abspath(workroot)
        self.python_bin = python_bin
        self.shell_bin = shell_bin
        self._current: subprocess.Popen | None = None

    # -- layout: <workroot>/input, <workroot>/out, <workroot>/steps/<id>/main.py
    def prepare(self, step: StepRequest) -> tuple[str, str, str]:
        inp = os.path.join(self.workroot, "input")
        out = os.path.join(self.workroot, "out")
        step_dir = os.path.join(self.workroot, "steps", step.step_id)
        for d in (inp, out, step_dir):
            os.makedirs(d, exist_ok=True)
        for name, data in step.files.items():
            with open(os.path.join(inp, _safe_name(name)), "wb") as fh:
                fh.write(data)
        if step.kind == "python":
            with open(os.path.join(step_dir, "main.py"), "w", encoding="utf-8", newline="\n") as fh:
                fh.write(step.code)
        elif step.kind == "shell":
            with open(os.path.join(step_dir, "main.sh"), "w", encoding="utf-8", newline="\n") as fh:
                fh.write(step.code if step.code.endswith("\n") else step.code + "\n")
        else:
            raise ValueError(f"unknown step kind {step.kind!r}")
        self._hand_over_ownership([self.workroot, inp, out, os.path.join(self.workroot, "steps"), step_dir])
        return inp, out, step_dir

    # uid/gid the step runs as; None = same user as the runner (SubprocessExecutor)
    step_uid: int | None = None
    step_gid: int | None = None

    def _hand_over_ownership(self, dirs: list[str]) -> None:
        """When the runner is root and steps run as another uid (gVisor), that uid must own /work.

        Found in WSL 2026-11-01: without this the step gets ``PermissionError: /work/out/...``.
        """
        if self.step_uid is None or not hasattr(os, "chown") or not hasattr(os, "geteuid") or os.geteuid() != 0:
            return
        gid = self.step_gid if self.step_gid is not None else self.step_uid
        for d in dirs:
            try:
                os.chown(d, self.step_uid, gid)
                for entry in os.scandir(d):
                    if entry.is_file(follow_symlinks=False):
                        os.chown(entry.path, self.step_uid, gid)
            except OSError:
                pass

    def collect_outputs(self, out_dir: str) -> dict[str, bytes]:
        files: dict[str, bytes] = {}
        total = 0
        for dirpath, _dirs, filenames in os.walk(out_dir):
            for fn in sorted(filenames):
                path = os.path.join(dirpath, fn)
                rel = os.path.relpath(path, out_dir).replace(os.sep, "/")
                try:
                    size = os.path.getsize(path)
                    if size > MAX_FILE_BYTES or total + size > MAX_TOTAL_FILE_BYTES:
                        continue
                    with open(path, "rb") as fh:
                        files[rel] = fh.read()
                    total += size
                except OSError:
                    continue
        return files

    def base_env(self, step: StepRequest, work: str) -> dict[str, str]:
        env = {
            "PATH": os.environ.get("PATH", "/usr/local/bin:/usr/bin:/bin"),
            "HOME": work,
            "LANG": "C.UTF-8",
            "PYTHONIOENCODING": "utf-8",
            "PYTHONDONTWRITEBYTECODE": "1",
            "BRZ_WORK": work,
            "BRZ_INPUT": os.path.join(work, "input"),
            "BRZ_OUT": os.path.join(work, "out"),
            "BRZ_STEP_ID": step.step_id,
        }
        if sys.platform == "win32":  # local tests only
            for k in ("SYSTEMROOT", "TEMP", "TMP", "COMSPEC", "PATHEXT"):
                if k in os.environ:
                    env[k] = os.environ[k]
        env.update(step.env)
        return env

    def kill_current(self) -> bool:
        proc = self._current
        if proc is not None and proc.poll() is None:
            proc.kill()
            return True
        return False

    def command(self, step: StepRequest, step_dir: str) -> list[str]:
        raise NotImplementedError

    def run(self, step: StepRequest) -> StepResult:
        _inp, out, step_dir = self.prepare(step)
        work = self.workroot
        cmd = self.command(step, step_dir)
        start = time.monotonic()
        timed_out = False
        error = ""
        try:
            proc = subprocess.Popen(
                cmd,
                cwd=work,
                env=self.base_env(step, work),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                stdin=subprocess.DEVNULL,
            )
            self._current = proc
            try:
                out_b, err_b = proc.communicate(timeout=step.timeout_s)
            except subprocess.TimeoutExpired:
                proc.kill()
                out_b, err_b = proc.communicate()
                timed_out = True
            exit_code = proc.returncode if proc.returncode is not None else -1
        except (OSError, ValueError) as exc:
            out_b, err_b, exit_code, error = b"", b"", 127, f"{type(exc).__name__}: {exc}"
        finally:
            self._current = None
        duration = time.monotonic() - start
        return StepResult(
            step_id=step.step_id,
            exit_code=exit_code if not timed_out else 124,
            stdout=out_b[:MAX_STREAM_BYTES].decode("utf-8", "replace"),
            stderr=err_b[:MAX_STREAM_BYTES].decode("utf-8", "replace"),
            duration_s=duration,
            files=self.collect_outputs(out),
            timed_out=timed_out,
            executor=self.name,
            error=error,
        )


class SubprocessExecutor(BaseExecutor):
    name = "subprocess"

    def command(self, step: StepRequest, step_dir: str) -> list[str]:
        if step.kind == "python":
            return [self.python_bin, "-I", os.path.join(step_dir, "main.py")]
        if sys.platform == "win32":  # local tests: Git Bash sh if present, else cmd
            sh = shutil.which("sh") or shutil.which("bash")
            if sh:
                return [sh, os.path.join(step_dir, "main.sh")]
            return [os.environ.get("COMSPEC", "cmd.exe"), "/c", step.code]
        return [self.shell_bin, os.path.join(step_dir, "main.sh")]


class GvisorExecutor(BaseExecutor):
    """Run each step in its own gVisor sandbox (OCI bundle, ``runsc --platform=systrap``).

    Inner layer of the two-layer blast radius: even if the step escapes Python it is inside
    a user-space kernel with no access to the runner process, with ``/work`` as the only
    writable host path and the host root mounted read-only.
    """

    name = "gvisor-systrap"

    def __init__(
        self,
        workroot: str,
        *,
        runsc_bin: str = "/usr/local/bin/runsc",
        platform: str = "systrap",
        bundle_root: str = "/var/lib/brz/bundles",
        uid: int = 1000,
        gid: int = 1000,
        memory_limit_bytes: int = 1_500_000_000,
        network: str = "none",  # steps without needs_network get no network at all
        network_when_needed: str = "host",  # steps with needs_network: host networking, filtered by VM nftables
        **kw,
    ):
        super().__init__(workroot, **kw)
        self.runsc_bin = runsc_bin
        self.platform = platform
        self.bundle_root = bundle_root
        self.uid = uid
        self.gid = gid
        self.step_uid = uid
        self.step_gid = gid
        self.memory_limit_bytes = memory_limit_bytes
        self.network = network
        self.network_when_needed = network_when_needed

    def inner_command(self, step: StepRequest, step_dir: str) -> list[str]:
        # paths as seen INSIDE the sandbox: /work is bind-mounted from self.workroot
        rel = os.path.relpath(step_dir, self.workroot).replace(os.sep, "/")
        if step.kind == "python":
            return ["python3", "-I", f"/work/{rel}/main.py"]
        return ["/bin/sh", f"/work/{rel}/main.sh"]

    def oci_config(self, step: StepRequest, step_dir: str) -> dict:
        env = self.base_env(step, "/work")
        env.update(
            {
                "PATH": "/usr/local/bin:/usr/bin:/bin",
                "HOME": "/work",
                "BRZ_INPUT": "/work/input",
                "BRZ_OUT": "/work/out",
            }
        )
        return {
            "ociVersion": "1.0.2",
            "process": {
                "terminal": False,
                "user": {"uid": self.uid, "gid": self.gid},
                "args": self.inner_command(step, step_dir),
                "env": [f"{k}={v}" for k, v in env.items()],
                "cwd": "/work",
                "noNewPrivileges": True,
                "capabilities": {"bounding": [], "effective": [], "permitted": [], "ambient": []},
                "rlimits": [
                    {"type": "RLIMIT_NOFILE", "hard": 4096, "soft": 4096},
                    {"type": "RLIMIT_NPROC", "hard": 256, "soft": 256},
                ],
            },
            "root": {"path": "/", "readonly": True},
            "hostname": "brz-step",
            "mounts": [
                {"destination": "/proc", "type": "proc", "source": "proc"},
                {
                    "destination": "/dev",
                    "type": "tmpfs",
                    "source": "tmpfs",
                    "options": ["nosuid", "noexec", "mode=755"],
                },
                {
                    "destination": "/tmp",
                    "type": "tmpfs",
                    "source": "tmpfs",
                    "options": ["nosuid", "nodev", "size=256m"],
                },
                {"destination": "/work", "type": "bind", "source": self.workroot, "options": ["rbind", "rw"]},
                {"destination": "/etc/brz", "type": "tmpfs", "source": "tmpfs", "options": ["ro", "size=1m"]},
            ],
            "linux": {
                # A fresh (empty) network namespace unless the step may use the network: with --network=host
                # runsc enters the OCI netns, and an empty one has no interfaces (WSL 2026-11-01: "Could not
                # resolve host" even with --network=host until the namespace entry was dropped).
                "namespaces": [{"type": "pid"}, {"type": "ipc"}, {"type": "uts"}, {"type": "mount"}]
                + ([] if step.needs_network else [{"type": "network"}]),
                "resources": {"memory": {"limit": self.memory_limit_bytes}, "pids": {"limit": 256}},
                "maskedPaths": ["/proc/kcore", "/proc/keys", "/proc/sysrq-trigger", "/sys/firmware"],
                "readonlyPaths": ["/proc/sys", "/proc/sysrq-trigger", "/proc/irq", "/proc/bus"],
            },
        }

    def write_bundle(self, step: StepRequest, step_dir: str) -> str:
        bundle = os.path.join(self.bundle_root, step.step_id)
        os.makedirs(bundle, exist_ok=True)
        with open(os.path.join(bundle, "config.json"), "w", encoding="utf-8") as fh:
            json.dump(self.oci_config(step, step_dir), fh, indent=2)
        return bundle

    def command(self, step: StepRequest, step_dir: str) -> list[str]:
        bundle = self.write_bundle(step, step_dir)
        container_id = f"brz-{step.step_id}-{int(time.time())}"
        # WSL 2026-11-01: with an OCI `network` namespace, --network=sandbox has no interface -> no DNS;
        # --network=sandbox on the root namespace would take over the VM's NIC. So: none, or host when needed.
        network = self.network_when_needed if step.needs_network else self.network
        return [
            self.runsc_bin,
            f"--platform={self.platform}",
            f"--network={network}",
            "--rootless=false",
            "--overlay2=none",
            "run",
            "--bundle",
            bundle,
            container_id,
        ]

    def base_env(self, step: StepRequest, work: str) -> dict[str, str]:
        env = super().base_env(step, work)
        env.pop("SYSTEMROOT", None)
        return env
