"""Egress attempt log: parse nftables ``log prefix`` lines from the kernel log.

The sandbox nftables ruleset (see :mod:`brz_runner.egress`) logs every outbound packet
decision with the prefixes ``BRZ-EGRESS-DENY`` / ``BRZ-EGRESS-ALLOW``. A kernel log line
looks like::

    2026-11-05T12:00:03+0000 brz-task kernel: BRZ-EGRESS-DENY IN= OUT=enp1s0 SRC=10.0.0.5
    DST=93.184.216.34 LEN=60 TOS=0x00 PREC=0x00 TTL=64 ID=1234 DF PROTO=TCP SPT=43210 DPT=443 ...

:func:`parse_line` is pure and unit-tested; :class:`JournalEgressReader` shells out to
``journalctl -k`` (or tails ``/var/log/kern.log``) and is exercised on event day.
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import asdict, dataclass

PREFIX_RE = re.compile(r"BRZ-EGRESS-(?P<verdict>DENY|ALLOW)\b")
KV_RE = re.compile(r"\b(?P<k>[A-Z]+)=(?P<v>\S*)")
TS_RE = re.compile(
    r"^(?P<ts>\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?|\w{3}\s+\d{1,2} \d{2}:\d{2}:\d{2})"
)


@dataclass
class EgressAttempt:
    ts: str
    verdict: str  # "denied" | "allowed"
    dst_ip: str
    dst_port: int | None
    proto: str
    src_ip: str = ""
    domain: str | None = None
    raw: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def parse_line(line: str) -> EgressAttempt | None:
    m = PREFIX_RE.search(line)
    if not m:
        return None
    kv = {k.upper(): v for k, v in KV_RE.findall(line[m.end() :])}
    ts_m = TS_RE.match(line.strip())
    port = kv.get("DPT")
    return EgressAttempt(
        ts=ts_m.group("ts") if ts_m else "",
        verdict="denied" if m.group("verdict") == "DENY" else "allowed",
        dst_ip=kv.get("DST", ""),
        dst_port=int(port) if port and port.isdigit() else None,
        proto=kv.get("PROTO", "").lower(),
        src_ip=kv.get("SRC", ""),
        raw=line.strip()[:400],
    )


def parse_lines(lines) -> list[EgressAttempt]:
    out: list[EgressAttempt] = []
    for line in lines:
        a = parse_line(line)
        if a is not None:
            out.append(a)
    return out


class EgressReader:
    """Interface the runner server uses; swap in a fake for tests."""

    def read_since(self, since_iso: str | None) -> list[EgressAttempt]:
        raise NotImplementedError


class NullEgressReader(EgressReader):
    source = "none"

    def read_since(self, since_iso: str | None) -> list[EgressAttempt]:
        return []


class StaticEgressReader(EgressReader):
    """Replays canned kernel-log lines (tests / offline demo)."""

    source = "static"

    def __init__(self, lines: list[str]):
        self.lines = list(lines)

    def read_since(self, since_iso: str | None) -> list[EgressAttempt]:
        return parse_lines(self.lines)


class JournalEgressReader(EgressReader):
    source = "journalctl -k"

    def __init__(self, journalctl_bin: str = "journalctl", kern_log: str = "/var/log/kern.log"):
        self.journalctl_bin = journalctl_bin
        self.kern_log = kern_log

    def read_since(self, since_iso: str | None) -> list[EgressAttempt]:
        cmd = [self.journalctl_bin, "-k", "--no-pager", "-o", "short-iso", "--grep", "BRZ-EGRESS-"]
        if since_iso:
            cmd += ["--since", since_iso]
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=10, check=False)
            if proc.returncode == 0:
                return parse_lines(proc.stdout.splitlines())
        except (OSError, subprocess.TimeoutExpired):
            pass
        try:
            with open(self.kern_log, encoding="utf-8", errors="replace") as fh:
                return parse_lines(fh.readlines()[-5000:])
        except OSError:
            return []
