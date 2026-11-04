"""Default-deny egress: build and apply the nftables ruleset inside the sandbox VM.

Policy (table ``inet brz``):

* **output**: policy drop. Allowed: loopback, established/related, and TCP 80/443 to the IPv4
  addresses the approved domains resolved to at boot (set ``allow4``). Everything else is logged
  with prefix ``BRZ-EGRESS-DENY`` and dropped. Allowed packets to the allowlist are logged
  (rate-limited) with ``BRZ-EGRESS-ALLOW`` so the receipt shows both.
* **no DNS after lock-down**: names are resolved once before the ruleset is applied and pinned in
  ``/etc/brz/hosts``, which steps see as ``/etc/hosts``. Attack A20 showed why: with port 53 open to
  one resolver, a step can tunnel data out inside query names, whatever the allowlist says.
* **input**: policy drop. Allowed: loopback, established/related, the runner port from the
  control plane CIDR only. (Vultr firewall groups do the same at the edge; this is defence
  in depth and also applies to traffic that never crosses the Vultr firewall.)

Known limitation (documented in README): domains are resolved once at boot; a CDN that retires
an address mid-task can break an allowed domain, a wildcard only pins its apex, and any other
hostname that happens to share an allowed IP is reachable.

``main()`` is what cloud-init runs (``brz-egress-apply``); :func:`build_ruleset` is pure.
"""

from __future__ import annotations

import ipaddress
import os
import socket
import subprocess
import sys

ALLOW_PORTS = (80, 443)
LOG_RATE = "50/second"


def resolve_domains(domains: list[str], *, resolver=None) -> dict[str, list[str]]:
    """Resolve each hostname to IPv4 addresses. ``resolver(host) -> list[str]`` is injectable."""
    resolver = resolver or _getaddrinfo_v4
    out: dict[str, list[str]] = {}
    for d in domains:
        host = d[2:] if d.startswith("*.") else d  # wildcard: resolve the apex, best effort
        try:
            addrs = sorted(set(resolver(host)))
        except OSError:
            addrs = []
        out[d] = [a for a in addrs if _is_public_v4(a)]
    return out


def _getaddrinfo_v4(host: str) -> list[str]:
    return [info[4][0] for info in socket.getaddrinfo(host, 443, socket.AF_INET, socket.SOCK_STREAM)]


def _is_public_v4(addr: str) -> bool:
    try:
        ip = ipaddress.IPv4Address(addr)
    except ValueError:
        return False
    return not (ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_reserved)


def build_ruleset(
    *,
    allowed_ipv4: list[str],
    control_plane_cidr: str,
    runner_port: int,
    dns_server: str | None = None,  # None (what the VM uses): port 53 stays closed
    allow_ports=ALLOW_PORTS,
    extra_admin_cidr: str | None = None,
) -> str:
    ipaddress.ip_network(control_plane_cidr, strict=False)  # validate
    if dns_server is not None:
        ipaddress.ip_address(dns_server)
    for a in allowed_ipv4:
        ipaddress.IPv4Address(a)
    elements = ", ".join(sorted(set(allowed_ipv4))) or ""
    ports = ", ".join(str(p) for p in allow_ports)
    lines = [
        "#!/usr/sbin/nft -f",
        "flush ruleset",
        "table inet brz {",
        "  set allow4 {",
        "    type ipv4_addr",
        "    flags interval",
        f"    elements = {{ {elements} }}" if elements else "    # empty: no egress allowed",
        "  }",
        "  chain input {",
        "    type filter hook input priority 0; policy drop;",
        "    iif lo accept",
        "    ct state established,related accept",
        "    ct state invalid drop",
        f"    ip saddr {control_plane_cidr} tcp dport {runner_port} accept",
    ]
    if extra_admin_cidr:
        lines.append(f"    ip saddr {extra_admin_cidr} tcp dport 22 accept")
    lines += [
        "    icmp type echo-request limit rate 5/second accept",
        "  }",
        "  chain output {",
        "    type filter hook output priority 0; policy drop;",
        "    oif lo accept",
        "    ct state established,related accept",
        "    ct state invalid drop",
    ]
    if dns_server is not None:
        lines += [f"    ip daddr {dns_server} udp dport 53 accept", f"    ip daddr {dns_server} tcp dport 53 accept"]
    lines += [
        f'    ip daddr @allow4 tcp dport {{ {ports} }} limit rate {LOG_RATE} log prefix "BRZ-EGRESS-ALLOW "',
        f"    ip daddr @allow4 tcp dport {{ {ports} }} accept",
        f'    limit rate {LOG_RATE} log prefix "BRZ-EGRESS-DENY "',
        "    drop",
        "  }",
        "  chain forward {",
        "    type filter hook forward priority 0; policy drop;",
        "  }",
        "}",
        "",
    ]
    return "\n".join(lines)


def hosts_lines(resolved: dict[str, list[str]]) -> str:
    """/etc/hosts content for the names resolved at boot. A wildcard has no single name to pin."""
    return "".join(f"{ip} {d}\n" for d, addrs in resolved.items() if not d.startswith("*.") for ip in addrs)


def read_list(path: str) -> list[str]:
    try:
        with open(path, encoding="utf-8") as fh:
            return [ln.strip() for ln in fh if ln.strip() and not ln.startswith("#")]
    except OSError:
        return []


def main(argv: list[str] | None = None) -> int:
    """cloud-init entry point: resolve /etc/brz/allowed_domains.txt, write and apply /etc/nftables.conf."""
    argv = sys.argv[1:] if argv is None else argv
    conf_dir = os.environ.get("BRZ_CONF_DIR", "/etc/brz")
    domains = read_list(os.path.join(conf_dir, "allowed_domains.txt"))
    cp = (read_list(os.path.join(conf_dir, "control_plane.cidr")) or ["0.0.0.0/0"])[0]
    env = dict(ln.split("=", 1) for ln in read_list(os.path.join(conf_dir, "task.env")) if "=" in ln)
    port = int(env.get("RUNNER_PORT", "8700"))
    resolved = resolve_domains(domains)
    ips = sorted({ip for addrs in resolved.values() for ip in addrs})
    ruleset = build_ruleset(
        allowed_ipv4=ips,
        control_plane_cidr=cp,
        runner_port=port,
        extra_admin_cidr=env.get("ADMIN_CIDR") or None,
    )
    out_path = "/etc/nftables.conf" if "--dry-run" not in argv else "/dev/stdout"
    with open(os.path.join(conf_dir, "resolved_domains.txt"), "w", encoding="utf-8") as fh:
        for d, addrs in resolved.items():
            fh.write(f"{d} {' '.join(addrs) or '-'}\n")
    with open(os.path.join(conf_dir, "hosts"), "w", encoding="utf-8") as fh:
        fh.write(hosts_lines(resolved))
    if out_path == "/dev/stdout":
        sys.stdout.write(ruleset)
        return 0
    with open(out_path, "w", encoding="utf-8") as fh:
        fh.write(ruleset)
    proc = subprocess.run(["nft", "-f", out_path], capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        sys.stderr.write(proc.stderr)
        return proc.returncode
    subprocess.run(["systemctl", "enable", "nftables"], capture_output=True, check=False)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
