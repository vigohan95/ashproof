"""Step executors (standard library only).

* :class:`SubprocessExecutor` - runs the step as a child process of the runner. Used for
  local tests (``--no-gvisor``) and as the emergency fallback if runsc is unavailable.
* :class:`GvisorExecutor` - wraps the same step in an OCI bundle and runs it with
  ``runsc --platform=systrap`` (user-space kernel, no KVM required, works inside any VM).
  Exercised for real by ``tests/attacks`` (see docs/evidence/).

Both produce the same :class:`StepResult`: exit code, stdout/stderr (capped), the files
written under ``<work>/out`` (capped), duration, and which executor produced it.

Everything under the work root belongs to the step, and the runner around it is root. So the runner
never follows a link in there: directories are re-checked with ``lstat`` before each step, files are
written with ``O_NOFOLLOW``, ownership is changed without following links, and outputs are collected
only if they are regular files. The checks are not racy because at most one step runs at a time and
the sandbox of the previous step is gone before the next ``prepare`` (attack A14 measures that).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field

MAX_STREAM_BYTES = 256_000
MAX_FILE_BYTES = 5_000_000
MAX_TOTAL_FILE_BYTES = 20_000_000
DEFAULT_WORK_QUOTA_BYTES = 2 * 1024 * 1024 * 1024
QUOTA_POLL_S = 0.05
EXIT_TIMEOUT = 124
EXIT_QUOTA = 125

# A step id becomes a directory name, a bundle path and part of a container id.
STEP_ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")
_O_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)
_O_NONBLOCK = getattr(os, "O_NONBLOCK", 0)
_O_BINARY = getattr(os, "O_BINARY", 0)


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

        step_id = str(d["step_id"])
        if not STEP_ID_RE.match(step_id):
            raise ValueError(f"unsafe step id: {step_id!r}")
        files = {name: base64.b64decode(b64) for name, b64 in (d.get("files") or {}).items()}
        return cls(
            step_id=step_id,
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
    skipped_outputs: list[dict] = field(default_factory=list)  # {name, reason}: not returned, and why
    stdout_truncated: bool = False
    stderr_truncated: bool = False

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
            "skipped_outputs": self.skipped_outputs,
            "stdout_truncated": self.stdout_truncated,
            "stderr_truncated": self.stderr_truncated,
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


def _real_dir(path: str) -> None:
    """Ensure ``path`` is a real directory. Whatever else a step left there is removed, not followed."""
    try:
        st = os.lstat(path)
    except FileNotFoundError:
        os.mkdir(path)
        return
    if not stat.S_ISDIR(st.st_mode):
        os.unlink(path)
        os.mkdir(path)


def _write_file(path: str, data: bytes) -> None:
    """Create ``path`` fresh: an existing entry (link, hard link, directory) is replaced, never written through."""
    try:
        if stat.S_ISDIR(os.lstat(path).st_mode):
            shutil.rmtree(path)
        else:
            os.unlink(path)
    except FileNotFoundError:
        pass
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | _O_NOFOLLOW | _O_BINARY, 0o644)
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)


def _disk_usage(root: str) -> int:
    """Bytes allocated under ``root``, links not followed. Blocks, so sparse files are not overcounted."""
    total = 0
    stack = [root]
    while stack:
        try:
            with os.scandir(stack.pop()) as it:
                for entry in it:
                    try:
                        st = os.lstat(entry.path)
                    except OSError:
                        continue
                    total += getattr(st, "st_blocks", 0) * 512 or st.st_size
                    if stat.S_ISDIR(st.st_mode):
                        stack.append(entry.path)
        except OSError:
            continue
    return total


class _CappedReader(threading.Thread):
    """Drain a pipe to its end but keep only the first ``limit`` bytes.

    ``Popen.communicate`` buffers everything, which lets a step that floods stdout grow the root
    runner without bound (attack A13). The pipe must still be drained or the step would just block.
    """

    def __init__(self, pipe, limit: int):
        super().__init__(daemon=True)
        self.pipe = pipe
        self.limit = limit
        self.data = bytearray()
        self.truncated = False

    def run(self) -> None:
        try:
            while True:
                chunk = self.pipe.read(65536)
                if not chunk:
                    return
                room = self.limit - len(self.data)
                if room > 0:
                    self.data += chunk[:room]
                if len(chunk) > room:
                    self.truncated = True
        except (OSError, ValueError):
            return


class BaseExecutor:
    name = "base"

    def __init__(
        self,
        workroot: str,
        *,
        python_bin: str = "python3",
        shell_bin: str = "/bin/sh",
        work_quota_bytes: int = DEFAULT_WORK_QUOTA_BYTES,
    ):
        self.workroot = os.path.abspath(workroot)
        self.python_bin = python_bin
        self.shell_bin = shell_bin
        self.work_quota_bytes = work_quota_bytes
        self._current: subprocess.Popen | None = None

    # -- layout: <workroot>/input, <workroot>/out, <workroot>/steps/<id>/main.py
    def prepare(self, step: StepRequest) -> tuple[str, str, str]:
        if not STEP_ID_RE.match(step.step_id):
            raise ValueError(f"unsafe step id: {step.step_id!r}")
        inp = os.path.join(self.workroot, "input")
        out = os.path.join(self.workroot, "out")
        steps = os.path.join(self.workroot, "steps")
        step_dir = os.path.join(steps, step.step_id)
        os.makedirs(self.workroot, exist_ok=True)
        for d in (inp, out, steps, step_dir):  # parents first: each is checked before anything goes inside it
            _real_dir(d)
        for name, data in step.files.items():
            _write_file(os.path.join(inp, _safe_name(name)), data)
        if step.kind == "python":
            _write_file(os.path.join(step_dir, "main.py"), step.code.encode("utf-8"))
        elif step.kind == "shell":
            code = step.code if step.code.endswith("\n") else step.code + "\n"
            _write_file(os.path.join(step_dir, "main.sh"), code.encode("utf-8"))
        else:
            raise ValueError(f"unknown step kind {step.kind!r}")
        self._hand_over_ownership([self.workroot, inp, out, steps, step_dir])
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
                os.chown(d, self.step_uid, gid, follow_symlinks=False)
                for entry in os.scandir(d):
                    if entry.is_file(follow_symlinks=False):
                        os.chown(entry.path, self.step_uid, gid, follow_symlinks=False)
            except OSError:
                pass

    def collect_outputs(self, out_dir: str) -> tuple[dict[str, bytes], list[dict]]:
        """Regular files under ``out_dir``, read without following links; anything else is listed as skipped."""
        files: dict[str, bytes] = {}
        skipped: list[dict] = []
        total = 0
        try:
            if not stat.S_ISDIR(os.lstat(out_dir).st_mode):
                return {}, [{"name": ".", "reason": "out directory was replaced"}]
        except OSError:
            return {}, [{"name": ".", "reason": "out directory is missing"}]
        for dirpath, dirnames, filenames in os.walk(out_dir, followlinks=False):
            for name in sorted(dirnames + filenames):
                path = os.path.join(dirpath, name)
                rel = os.path.relpath(path, out_dir).replace(os.sep, "/")
                try:
                    st = os.lstat(path)
                    if stat.S_ISDIR(st.st_mode):
                        continue
                    if not stat.S_ISREG(st.st_mode):
                        skipped.append({"name": rel, "reason": "not a regular file"})
                    elif st.st_size > MAX_FILE_BYTES or total + st.st_size > MAX_TOTAL_FILE_BYTES:
                        skipped.append({"name": rel, "reason": f"too large ({st.st_size} bytes)"})
                    else:
                        fd = os.open(path, os.O_RDONLY | _O_NOFOLLOW | _O_NONBLOCK | _O_BINARY)
                        with os.fdopen(fd, "rb") as fh:
                            files[rel] = fh.read(MAX_FILE_BYTES + 1)[:MAX_FILE_BYTES]
                        total += len(files[rel])
                except OSError as exc:
                    skipped.append({"name": rel, "reason": type(exc).__name__})
        return files, skipped

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

    def _watch_quota(self, proc: subprocess.Popen, done: threading.Event, hit: list[int]) -> None:
        """/work is a host path, so no sandbox limit applies to it. Poll it and kill the step over quota."""
        while not done.wait(QUOTA_POLL_S):
            used = _disk_usage(self.workroot)
            if used > self.work_quota_bytes:
                hit.append(used)
                proc.kill()
                return

    def run(self, step: StepRequest) -> StepResult:
        _inp, out, step_dir = self.prepare(step)
        work = self.workroot
        cmd = self.command(step, step_dir)
        start = time.monotonic()
        timed_out = False
        error = ""
        stdout = stderr = None
        quota_hit: list[int] = []
        done = threading.Event()
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
            stdout = _CappedReader(proc.stdout, MAX_STREAM_BYTES)
            stderr = _CappedReader(proc.stderr, MAX_STREAM_BYTES)
            stdout.start()
            stderr.start()
            threading.Thread(target=self._watch_quota, args=(proc, done, quota_hit), daemon=True).start()
            try:
                proc.wait(timeout=step.timeout_s)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
                timed_out = True
            exit_code = proc.returncode if proc.returncode is not None else -1
        except (OSError, ValueError) as exc:
            exit_code, error = 127, f"{type(exc).__name__}: {exc}"
        finally:
            done.set()
            self._current = None
        for reader in (stdout, stderr):
            if reader is not None:
                reader.join(timeout=5)  # a stray child may hold the pipe open; never wait on it for ever
        if timed_out:
            exit_code = EXIT_TIMEOUT
        elif quota_hit:
            exit_code = EXIT_QUOTA
            error = f"work quota exceeded: {quota_hit[0]} bytes used, limit {self.work_quota_bytes}"
        duration = time.monotonic() - start
        files, skipped = self.collect_outputs(out)
        return StepResult(
            step_id=step.step_id,
            exit_code=exit_code,
            stdout=bytes(stdout.data).decode("utf-8", "replace") if stdout else "",
            stderr=bytes(stderr.data).decode("utf-8", "replace") if stderr else "",
            duration_s=duration,
            files=files,
            timed_out=timed_out,
            executor=self.name,
            error=error,
            skipped_outputs=skipped,
            stdout_truncated=bool(stdout and stdout.truncated),
            stderr_truncated=bool(stderr and stderr.truncated),
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


ROOT_LINK_DIRS = ("/bin", "/sbin", "/lib", "/lib32", "/lib64", "/libx32")  # links into /usr on merged-usr systems
ETC_DIRS = ("/etc/ssl", "/etc/alternatives")


class GvisorExecutor(BaseExecutor):
    """Run each step in its own gVisor sandbox (OCI bundle, ``runsc --platform=systrap``).

    Inner layer of the two-layer blast radius: even if the step escapes Python it is inside
    a user-space kernel with no access to the runner process, with ``/work`` as the only
    writable host path. The root filesystem is a skeleton holding only ``/usr`` (read-only) and a
    handful of ``/etc`` entries, so the step cannot read anything else on the machine, world-readable
    or not (attack A02 found the original "host root, read-only" layout exposed all of it).
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
        hosts_file: str = "/etc/brz/hosts",  # names pinned at boot; steps get no DNS (see brz_runner.egress)
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
        self.hosts_file = hosts_file

    @property
    def rootfs(self) -> str:
        return os.path.join(self.bundle_root, "_rootfs")  # step ids cannot start with "_"

    def _rootfs_mounts(self) -> list[dict]:
        """Read-only binds that make up the step's view of the system, for what exists on this host."""
        ro = ["rbind", "ro", "nosuid", "nodev"]
        dirs = ["/usr"]
        dirs += [d for d in ROOT_LINK_DIRS if os.path.isdir(d) and not os.path.islink(d)]
        dirs += [d for d in ETC_DIRS if os.path.isdir(d)]
        return [{"destination": d, "type": "bind", "source": d, "options": ro} for d in dirs]

    def build_rootfs(self) -> str:
        """Create or refresh the skeleton. It is mounted read-only; the step never owns anything in it."""
        root = self.rootfs
        for d in ("proc", "dev", "tmp", "work", "usr", "etc"):
            os.makedirs(os.path.join(root, d), exist_ok=True)
        for d in ROOT_LINK_DIRS:
            target = os.path.join(root, d.lstrip("/"))
            if os.path.islink(d) and not os.path.lexists(target):
                os.symlink(os.readlink(d), target)  # merged-usr: /bin -> usr/bin
            elif os.path.isdir(d) and not os.path.islink(d):
                os.makedirs(target, exist_ok=True)
        for d in ETC_DIRS:
            if os.path.isdir(d):
                os.makedirs(os.path.join(root, d.lstrip("/")), exist_ok=True)
        hosts = "127.0.0.1 localhost\n"
        try:
            with open(self.hosts_file, encoding="utf-8") as fh:
                hosts += fh.read()
        except OSError:
            pass
        etc = {
            "passwd": f"root:x:0:0::/nonexistent:/usr/sbin/nologin\nrunner:x:{self.uid}:{self.gid}::/work:/bin/sh\n",
            "group": f"root:x:0:\nrunner:x:{self.gid}:\n",
            "hosts": hosts,
            "nsswitch.conf": "passwd: files\ngroup: files\nhosts: files\n",
            "resolv.conf": "",
        }
        for name, content in etc.items():
            _write_file(os.path.join(root, "etc", name), content.encode("utf-8"))
        if os.path.isfile("/etc/ld.so.cache"):
            shutil.copyfile("/etc/ld.so.cache", os.path.join(root, "etc", "ld.so.cache"))
        return root

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
            "root": {"path": self.rootfs, "readonly": True},
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
                *self._rootfs_mounts(),
            ],
            "linux": {
                # A fresh (empty) network namespace unless the step may use the network: with --network=host
                # runsc enters the OCI netns, and an empty one has no interfaces (WSL 2026-11-01: "Could not
                # resolve host" even with --network=host until the namespace entry was dropped).
                "namespaces": [{"type": "pid"}, {"type": "ipc"}, {"type": "uts"}, {"type": "mount"}]
                + ([] if step.needs_network else [{"type": "network"}]),
                # swap == limit means no swap on top: without it the cgroup let a step reach limit + all host swap
                "resources": {
                    "memory": {"limit": self.memory_limit_bytes, "swap": self.memory_limit_bytes},
                    "pids": {"limit": 256},
                },
                "maskedPaths": ["/proc/kcore", "/proc/keys", "/proc/sysrq-trigger", "/sys/firmware"],
                "readonlyPaths": ["/proc/sys", "/proc/sysrq-trigger", "/proc/irq", "/proc/bus"],
            },
        }

    def write_bundle(self, step: StepRequest, step_dir: str) -> str:
        self.build_rootfs()
        bundle = os.path.join(self.bundle_root, step.step_id)
        os.makedirs(bundle, exist_ok=True)
        with open(os.path.join(bundle, "config.json"), "w", encoding="utf-8") as fh:
            json.dump(self.oci_config(step, step_dir), fh, indent=2)
        return bundle

    def command(self, step: StepRequest, step_dir: str) -> list[str]:
        bundle = self.write_bundle(step, step_dir)
        container_id = f"brz-{step.step_id}-{time.time_ns()}"
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
