"""A quiet step must not be blamed for packets from boot. On a real VM journalctl exited 1 on "-- No entries --"."""

from __future__ import annotations

import subprocess

from brz_runner import netlog
from brz_runner.netlog import JournalEgressReader, only_since

BOOT = (
    "2026-11-06T06:39:19.130756+00:00 vm kernel: BRZ-EGRESS-DENY IN= OUT=enp1s0 SRC=45.63.16.175 "
    "DST=108.61.10.10 LEN=59 PROTO=UDP SPT=33182 DPT=53 LEN=39\n"
)
STEP = (
    "2026-11-06T06:39:46.000000+00:00 vm kernel: BRZ-EGRESS-DENY IN= OUT=enp1s0 SRC=45.63.16.175 "
    "DST=1.1.1.1 LEN=60 PROTO=TCP SPT=46250 DPT=443 SYN\n"
)
SINCE = "2026-11-06T06:39:45.000000+00:00"


def reader(tmp_path, monkeypatch, returncode, stdout="", raises=None):
    log = tmp_path / "kern.log"
    log.write_text(BOOT + STEP, encoding="utf-8")

    def run(cmd, **kw):
        if raises:
            raise raises
        return subprocess.CompletedProcess(cmd, returncode, stdout=stdout, stderr="")

    monkeypatch.setattr(netlog.subprocess, "run", run)
    return JournalEgressReader(kern_log=str(log))


def test_no_entries_means_no_attempts(tmp_path, monkeypatch):
    assert reader(tmp_path, monkeypatch, 1, "-- No entries --\n").read_since(SINCE) == []


def test_entries_come_from_the_journal(tmp_path, monkeypatch):
    got = reader(tmp_path, monkeypatch, 0, STEP).read_since(SINCE)
    assert [a.dst_ip for a in got] == ["1.1.1.1"]


def test_kernel_log_fallback_keeps_the_time_window(tmp_path, monkeypatch):
    got = reader(tmp_path, monkeypatch, 0, raises=OSError("no journalctl")).read_since(SINCE)
    assert [a.dst_ip for a in got] == ["1.1.1.1"]


def test_journal_failure_also_falls_back_inside_the_window(tmp_path, monkeypatch):
    got = reader(tmp_path, monkeypatch, 2).read_since(SINCE)
    assert [a.dst_ip for a in got] == ["1.1.1.1"]


def test_lines_without_a_usable_time_are_not_attributed():
    attempts = netlog.parse_lines(["Nov  6 06:39:46 vm kernel: BRZ-EGRESS-DENY DST=1.1.1.1 PROTO=TCP DPT=443"])
    assert only_since(attempts, SINCE) == []


def test_without_a_start_time_everything_is_returned(tmp_path, monkeypatch):
    got = reader(tmp_path, monkeypatch, 2).read_since(None)
    assert len(got) == 2
