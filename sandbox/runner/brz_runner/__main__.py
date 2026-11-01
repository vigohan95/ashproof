"""CLI: ``python3 -m brz_runner --task-id T --token-key-file /etc/brz/token.key [--no-gvisor]``.

Inside the VM systemd starts this (see the cloud-init template). Locally::

    python -m brz_runner --task-id demo --token-key-hex <64 hex> --no-gvisor --workroot ./work --port 8700
"""

from __future__ import annotations

import argparse
import os
import sys

from .executor import GvisorExecutor, SubprocessExecutor
from .netlog import JournalEgressReader, NullEgressReader
from .server import DEFAULT_SCAN_PATHS, RunnerConfig, make_server


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="brz_runner", description="Blast Radius Zero in-sandbox step runner")
    p.add_argument("--task-id", required=True)
    key = p.add_mutually_exclusive_group(required=True)
    key.add_argument("--token-key-file", help="file containing the raw 32-byte HMAC key (or hex)")
    key.add_argument("--token-key-hex", help="hex-encoded HMAC key (tests only)")
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=int(os.environ.get("RUNNER_PORT", "8700")))
    p.add_argument("--workroot", default="/work")
    p.add_argument("--no-gvisor", action="store_true", help="run steps as plain subprocesses (local tests)")
    p.add_argument("--runsc", default="/usr/local/bin/runsc")
    p.add_argument("--gvisor-platform", default="systrap")
    p.add_argument("--python-bin", default="python3")
    p.add_argument("--scan-path", action="append", default=None, help="override secret-scan paths")
    p.add_argument("--allow-poweroff", action="store_true", help="honour /revoke {poweroff:true}")
    p.add_argument("--no-journal", action="store_true", help="do not read egress attempts from journalctl")
    return p


def load_key(args: argparse.Namespace) -> bytes:
    if args.token_key_hex:
        return bytes.fromhex(args.token_key_hex)
    with open(args.token_key_file, "rb") as fh:
        raw = fh.read()
    stripped = raw.strip()
    try:
        if len(stripped) == 64:
            return bytes.fromhex(stripped.decode("ascii"))
    except (ValueError, UnicodeDecodeError):
        pass
    return raw  # raw binary key: never strip (it may legitimately start/end with whitespace bytes)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    key = load_key(args)
    if len(key) < 16:
        sys.stderr.write("token key too short\n")
        return 2
    os.makedirs(args.workroot, exist_ok=True)
    if args.no_gvisor:
        executor = SubprocessExecutor(args.workroot, python_bin=args.python_bin)
    else:
        executor = GvisorExecutor(args.workroot, runsc_bin=args.runsc, platform=args.gvisor_platform)
    egress = NullEgressReader() if args.no_journal else JournalEgressReader()
    cfg = RunnerConfig(
        task_id=args.task_id,
        token_key=key,
        executor=executor,
        egress=egress,
        scan_paths=args.scan_path or [args.workroot, *DEFAULT_SCAN_PATHS[1:]],
        host=args.host,
        port=args.port,
        allow_poweroff=args.allow_poweroff,
    )
    server = make_server(cfg)
    sys.stderr.write(f"brz_runner task={args.task_id} executor={executor.name} listening on {args.host}:{args.port}\n")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
