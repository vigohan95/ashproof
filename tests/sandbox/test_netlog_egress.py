from __future__ import annotations

import os
from pathlib import Path

import pytest
from brz_runner.egress import build_ruleset, resolve_domains
from brz_runner.egress import main as egress_main
from brz_runner.netlog import NullEgressReader, StaticEgressReader, parse_line, parse_lines

DENY = (
    "2026-11-05T12:00:03+0000 brz-task kernel: BRZ-EGRESS-DENY IN= OUT=enp1s0 SRC=10.0.0.5 DST=93.184.216.34 "
    "LEN=60 TOS=0x00 PREC=0x00 TTL=64 ID=1234 DF PROTO=TCP SPT=43210 DPT=443 WINDOW=64240 RES=0x00 SYN URGP=0"
)
ALLOW = (
    "Nov  5 12:00:04 brz-task kernel: [  123.456] BRZ-EGRESS-ALLOW IN= OUT=enp1s0 SRC=10.0.0.5 DST=151.101.1.63 "
    "LEN=60 PROTO=TCP SPT=43211 DPT=443 SYN"
)
ICMP = "2026-11-05T12:00:05+0000 host kernel: BRZ-EGRESS-DENY IN= OUT=enp1s0 SRC=10.0.0.5 DST=8.8.8.8 PROTO=ICMP TYPE=8"


def test_parse_deny_and_allow_lines():
    a = parse_line(DENY)
    assert a is not None
    assert a.verdict == "denied" and a.dst_ip == "93.184.216.34" and a.dst_port == 443 and a.proto == "tcp"
    assert a.src_ip == "10.0.0.5" and a.ts == "2026-11-05T12:00:03+0000"
    b = parse_line(ALLOW)
    assert b is not None and b.verdict == "allowed" and b.dst_ip == "151.101.1.63" and b.ts == "Nov  5 12:00:04"
    c = parse_line(ICMP)
    assert c is not None and c.dst_port is None and c.proto == "icmp"
    assert parse_line("Nov  5 12:00:05 host systemd[1]: Started brz-runner.service") is None
    assert [x.verdict for x in parse_lines([DENY, "noise", ALLOW])] == ["denied", "allowed"]
    assert a.to_dict()["raw"].startswith("2026-11-05T12:00:03")


def test_readers():
    assert NullEgressReader().read_since(None) == []
    r = StaticEgressReader([DENY, ALLOW])
    assert len(r.read_since("2026-11-05T00:00:00")) == 2 and r.source == "static"


def test_build_ruleset_default_deny_with_allowlist():
    rs = build_ruleset(
        allowed_ipv4=["151.101.1.63", "151.101.65.63"],
        control_plane_cidr="198.51.100.7/32",
        runner_port=8700,
        dns_server="1.1.1.1",
    )
    assert "table inet brz" in rs
    assert "chain output" in rs and "policy drop" in rs
    assert "elements = { 151.101.1.63, 151.101.65.63 }" in rs
    assert "ip saddr 198.51.100.7/32 tcp dport 8700 accept" in rs
    assert "ip daddr 1.1.1.1 udp dport 53 accept" in rs
    assert 'log prefix "BRZ-EGRESS-DENY "' in rs and 'log prefix "BRZ-EGRESS-ALLOW "' in rs
    assert "ip daddr @allow4 tcp dport { 80, 443 } accept" in rs
    assert "dport 22" not in rs  # no ssh unless an admin cidr is given
    # deny-log comes after the allow rules and before the final drop
    assert rs.index("BRZ-EGRESS-ALLOW") < rs.index("BRZ-EGRESS-DENY") < rs.rindex("drop")


def test_build_ruleset_empty_allowlist_and_validation():
    rs = build_ruleset(allowed_ipv4=[], control_plane_cidr="0.0.0.0/0", runner_port=8700, dns_server="9.9.9.9")
    assert "# empty: no egress allowed" in rs and "elements" not in rs
    with pytest.raises(ValueError):
        build_ruleset(allowed_ipv4=["not-an-ip"], control_plane_cidr="0.0.0.0/0", runner_port=1, dns_server="1.1.1.1")
    with pytest.raises(ValueError):
        build_ruleset(allowed_ipv4=[], control_plane_cidr="bogus", runner_port=1, dns_server="1.1.1.1")
    admin = build_ruleset(
        allowed_ipv4=[],
        control_plane_cidr="10.0.0.0/8",
        runner_port=1,
        dns_server="1.1.1.1",
        extra_admin_cidr="203.0.113.9/32",
    )
    assert "ip saddr 203.0.113.9/32 tcp dport 22 accept" in admin


def test_resolve_domains_filters_private_and_handles_failures():
    table = {"pypi.org": ["151.101.0.223", "10.0.0.1", "127.0.0.1"], "example.com": ["93.184.216.34"]}

    def fake_resolver(host: str) -> list[str]:
        if host not in table:
            raise OSError("NXDOMAIN")
        return table[host]

    out = resolve_domains(["pypi.org", "*.example.com", "nope.invalid"], resolver=fake_resolver)
    assert out == {"pypi.org": ["151.101.0.223"], "*.example.com": ["93.184.216.34"], "nope.invalid": []}


def test_egress_main_dry_run(tmp_path: Path, capsys, monkeypatch):
    conf = tmp_path / "brz"
    conf.mkdir()
    (conf / "allowed_domains.txt").write_text("# none\n")
    (conf / "control_plane.cidr").write_text("198.51.100.7/32\n")
    (conf / "task.env").write_text("TASK_ID=t1\nRUNNER_PORT=8701\nDNS_SERVER=1.0.0.1\n")
    monkeypatch.setenv("BRZ_CONF_DIR", str(conf))
    assert egress_main(["--dry-run"]) == 0
    out = capsys.readouterr().out
    assert "ip saddr 198.51.100.7/32 tcp dport 8701 accept" in out
    assert "dport 53" not in out  # no DNS after lock-down: a resolver is a tunnel out
    assert os.path.exists(conf / "resolved_domains.txt") and (conf / "hosts").read_text() == ""
