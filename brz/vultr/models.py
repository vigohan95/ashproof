"""Typed models for the subset of the Vultr API v2 that Blast Radius Zero uses.

Field names follow the official v2 shapes (see govultr `instance.go`, `plan.go`,
`region.go`, `os.go`, `firewall_rule.go`). Only the fields we read are typed;
unknown fields are kept in ``raw`` via ``extra="allow"`` so nothing is lost when
Vultr adds something.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

INSTANCE_STATUS_PENDING = "pending"
INSTANCE_STATUS_ACTIVE = "active"


class _Extra(BaseModel):
    model_config = ConfigDict(extra="allow")


class Region(_Extra):
    id: str
    city: str = ""
    country: str = ""
    continent: str = ""
    options: list[str] = Field(default_factory=list)


class Plan(_Extra):
    id: str
    vcpu_count: int = 0
    ram: int = 0  # MB
    disk: int = 0  # GB
    bandwidth: int = 0  # GB
    monthly_cost: float = 0.0
    hourly_cost: float | None = None  # newer plan payloads include it; may be absent
    type: str = ""
    locations: list[str] = Field(default_factory=list)

    def effective_hourly_cost(self, hours_per_month: int = 672) -> float:
        """Vultr bills hourly with a 672-hour monthly cap (VX1 has no cap but the rate is the same)."""
        if self.hourly_cost is not None:
            return float(self.hourly_cost)
        return round(self.monthly_cost / hours_per_month, 6)


class OperatingSystem(_Extra):
    id: int
    name: str = ""
    arch: str = ""
    family: str = ""


class Instance(_Extra):
    id: str
    label: str = ""
    status: str = INSTANCE_STATUS_PENDING  # pending | active | suspended | resizing
    power_status: str = ""  # running | stopped
    server_status: str = ""  # none | locked | installingbooting | ok
    main_ip: str = "0.0.0.0"
    plan: str = ""
    region: str = ""
    os_id: int = 0
    tags: list[str] = Field(default_factory=list)
    hostname: str = ""
    date_created: datetime | None = None
    user_scheme: str = ""

    @property
    def is_active(self) -> bool:
        return self.status == INSTANCE_STATUS_ACTIVE and self.power_status == "running"

    @property
    def is_ready(self) -> bool:
        """Active, running, and the OS install has finished (server_status ok)."""
        return self.is_active and self.server_status in ("ok", "")


class InstanceCreate(BaseModel):
    """Body for POST /v2/instances. ``user_data`` is plain text here; the client base64-encodes it."""

    region: str
    plan: str
    os_id: int | None = None
    snapshot_id: str | None = None
    label: str = ""
    hostname: str = ""
    tags: list[str] = Field(default_factory=list)
    user_data: str | None = None
    firewall_group_id: str | None = None
    sshkey_id: list[str] = Field(default_factory=list)
    enable_ipv6: bool = False
    backups: str = "disabled"
    ddos_protection: bool = False
    activation_email: bool = False

    def to_api_body(self) -> dict[str, Any]:
        import base64

        body: dict[str, Any] = {
            "region": self.region,
            "plan": self.plan,
            "label": self.label,
            "hostname": self.hostname,
            "tags": list(self.tags),
            "enable_ipv6": self.enable_ipv6,
            "backups": self.backups,
            "ddos_protection": self.ddos_protection,
            "activation_email": self.activation_email,
        }
        if self.snapshot_id:
            body["snapshot_id"] = self.snapshot_id
        elif self.os_id is not None:
            body["os_id"] = self.os_id
        else:
            raise ValueError("InstanceCreate needs os_id or snapshot_id")
        if self.user_data is not None:
            body["user_data"] = base64.b64encode(self.user_data.encode("utf-8")).decode("ascii")
        if self.firewall_group_id:
            body["firewall_group_id"] = self.firewall_group_id
        if self.sshkey_id:
            body["sshkey_id"] = list(self.sshkey_id)
        return body


class FirewallGroup(_Extra):
    id: str
    description: str = ""
    date_created: datetime | None = None
    rule_count: int = 0
    instance_count: int = 0


class FirewallRuleCreate(BaseModel):
    """Body for POST /v2/firewalls/{id}/rules. Vultr firewall groups filter INBOUND only."""

    ip_type: str = "v4"  # v4 | v6
    protocol: str = "tcp"  # tcp | udp | icmp | gre | esp | ah
    subnet: str = "0.0.0.0"
    subnet_size: int = 0
    port: str = ""  # "22" or "8000:8100"
    source: str = ""  # "" | "cloudflare"
    notes: str = ""


class FirewallRule(_Extra):
    id: int
    ip_type: str = "v4"
    protocol: str = "tcp"
    subnet: str = ""
    subnet_size: int = 0
    port: str = ""
    source: str = ""
    notes: str = ""
    action: str = "accept"


class ObjectStorage(_Extra):
    id: str
    label: str = ""
    cluster_id: int = 0
    region: str = ""
    status: str = ""
    s3_hostname: str = ""
    s3_access_key: str = ""
    s3_secret_key: str = ""


class ProofOfDestruction(BaseModel):
    """What we store in the receipt to prove the throwaway VM no longer exists."""

    instance_id: str
    method: str = "GET /v2/instances/{id}"
    http_status: int
    observed_at: datetime
    attempts: int = 1

    @property
    def destroyed(self) -> bool:
        return self.http_status == 404
