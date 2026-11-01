"""Render the cloud-init user_data for a throwaway sandbox VM.

The template (``templates/cloud-init.yaml.tmpl``) uses ``@@{name}`` placeholders so that
the many ``$`` signs in embedded shell scripts need no escaping. The runner package
(``brz_runner``) is embedded file-by-file (base64 ``write_files``) so a bare Ubuntu image
needs nothing but cloud-init to become a sandbox; no git clone, no pip, no registry.

Security notes that the template implements:

* The only secret written into the VM is the per-task token key. It authenticates the
  control plane to *this* runner and is useless anywhere else.
* Egress lock-down (``brz-egress-apply``) runs AFTER package install and gVisor download,
  so there is a short open window during boot. Event-day mitigation: bake a snapshot with
  packages + runsc preinstalled and pass ``inner_isolation="gvisor-preinstalled"`` so the
  lock-down is the first runcmd (see docs/EVENT-DAY-TODO.md).
* TTL watchdog: a systemd timer powers the VM off after ``ttl_minutes`` even if the
  control plane dies; the control plane's orphan sweep then deletes it by tag.
"""

from __future__ import annotations

import base64
import ipaddress
import re
import string
from importlib import resources
from pathlib import Path

from pydantic import BaseModel, Field, field_validator

GVISOR_RELEASE_URL = "https://storage.googleapis.com/gvisor/releases/release/latest"
RUNNER_FILES = (
    "__init__.py",
    "__main__.py",
    "egress.py",
    "executor.py",
    "netlog.py",
    "secretscan.py",
    "server.py",
    "tokens.py",
)
_HOST_RE = re.compile(r"^(\*\.)?([a-z0-9-]+\.)+[a-z0-9-]{2,}$")


class _Tmpl(string.Template):
    delimiter = "@@"


class SandboxSpec(BaseModel):
    task_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    token_key: bytes = Field(min_length=16)
    allowed_domains: list[str] = Field(default_factory=list)
    control_plane_cidr: str = "0.0.0.0/0"  # tighten to <control plane ip>/32 in production
    runner_port: int = Field(default=8700, ge=1024, le=65535)
    ttl_minutes: int = Field(default=20, ge=2, le=720)
    dns_server: str = "1.1.1.1"
    inner_isolation: str = "gvisor"  # "gvisor" | "none" (plain subprocess; local/dev only)
    gvisor_release_url: str = GVISOR_RELEASE_URL
    hostname: str | None = None

    @field_validator("allowed_domains")
    @classmethod
    def _domains(cls, v: list[str]) -> list[str]:
        out = []
        for d in v:
            d = d.strip().lower()
            if not _HOST_RE.match(d):
                raise ValueError(f"invalid domain {d!r}")
            if d not in out:
                out.append(d)
        return out

    @field_validator("control_plane_cidr")
    @classmethod
    def _cidr(cls, v: str) -> str:
        return str(ipaddress.ip_network(v, strict=False))

    @field_validator("dns_server")
    @classmethod
    def _dns(cls, v: str) -> str:
        return str(ipaddress.ip_address(v))

    @property
    def host(self) -> str:
        return self.hostname or f"brz-{self.task_id.lower()[:40]}"


def _template_text() -> str:
    return resources.files("brz.sandbox").joinpath("templates/cloud-init.yaml.tmpl").read_text(encoding="utf-8")


def runner_source_dir() -> Path:
    import brz_runner

    return Path(brz_runner.__file__).parent


def _runner_files_block(src_dir: Path, indent: str = "  ") -> str:
    chunks = []
    for name in RUNNER_FILES:
        data = (src_dir / name).read_bytes()
        b64 = base64.b64encode(data).decode("ascii")
        wrapped = "\n".join(indent + "      " + b64[i : i + 76] for i in range(0, len(b64), 76))
        chunks.append(
            f"{indent}- path: /opt/brz/runner/brz_runner/{name}\n"
            f'{indent}  permissions: "0644"\n'
            f"{indent}  encoding: b64\n"
            f"{indent}  content: |\n{wrapped}"
        )
    return "\n".join(chunks)


def render_cloud_init(spec: SandboxSpec, *, runner_dir: Path | None = None) -> str:
    src = runner_dir or runner_source_dir()
    domains_block = "\n".join("      " + d for d in spec.allowed_domains) or "      # (none approved)"
    extra_args = " --no-gvisor" if spec.inner_isolation == "none" else ""  # leading space: no trailing blank
    text = _Tmpl(_template_text()).substitute(
        task_id=spec.task_id,
        hostname=spec.host,
        runner_port=str(spec.runner_port),
        ttl_minutes=str(spec.ttl_minutes),
        dns_server=spec.dns_server,
        inner_isolation=spec.inner_isolation,
        token_key_hex=spec.token_key.hex(),
        allowed_domains_block=domains_block,
        control_plane_cidr=spec.control_plane_cidr,
        gvisor_release_url=spec.gvisor_release_url.rstrip("/"),
        runner_extra_args=extra_args,
        runner_files_block=_runner_files_block(src),
    )
    if not text.startswith("#cloud-config"):
        raise RuntimeError("rendered user_data must start with #cloud-config")
    return text


def user_data_size_ok(text: str, limit: int = 64 * 1024) -> bool:
    """Vultr accepts fairly large user_data, but cloud-init tooling warns above ~64 KiB; keep an eye on it."""
    return len(text.encode("utf-8")) <= limit
