from __future__ import annotations

import base64

import pytest
import yaml
from brz_runner.tokens import new_key

from brz.sandbox import SandboxSpec, render_cloud_init, user_data_size_ok
from brz.sandbox.cloudinit import RUNNER_FILES, runner_source_dir

KEY = new_key()


def _spec(**kw) -> SandboxSpec:
    base = dict(
        task_id="task-abc123",
        token_key=KEY,
        allowed_domains=["pypi.org", "Files.PythonHosted.org"],
        control_plane_cidr="198.51.100.7/32",
        runner_port=8700,
        ttl_minutes=20,
    )
    base.update(kw)
    return SandboxSpec(**base)


def test_renders_valid_cloud_config_yaml():
    text = render_cloud_init(_spec())
    assert text.startswith("#cloud-config\n")
    doc = yaml.safe_load(text)
    assert doc["hostname"] == "brz-task-abc123"
    assert doc["users"][0]["name"] == "runner" and doc["users"][0]["lock_passwd"] is True
    assert "sudo" not in doc["users"][0] and "ssh_authorized_keys" not in doc["users"][0]
    assert {"nftables", "python3"} <= set(doc["packages"])
    files = {f["path"]: f for f in doc["write_files"]}
    assert files["/etc/brz/token.key"]["permissions"] == "0600"
    assert files["/etc/brz/token.key"]["content"] == KEY.hex()
    assert files["/etc/brz/allowed_domains.txt"]["content"].split() == ["pypi.org", "files.pythonhosted.org"]
    assert files["/etc/brz/control_plane.cidr"]["content"] == "198.51.100.7/32"
    assert "DNS=1.1.1.1" in files["/etc/systemd/resolved.conf.d/brz.conf"]["content"]
    assert "OnBootSec=20min" in files["/etc/systemd/system/brz-ttl.timer"]["content"]
    assert "systemctl poweroff" in files["/etc/systemd/system/brz-ttl.service"]["content"]
    svc = files["/etc/systemd/system/brz-runner.service"]["content"]
    assert "--task-id task-abc123" in svc and "--port 8700" in svc and "--no-gvisor" not in svc
    assert "TTL_MINUTES=20" in files["/etc/brz/task.env"]["content"]
    assert "--platform" not in svc  # platform is the runner default (systrap)
    assert "sha512sum -c" in files["/usr/local/bin/brz-install-gvisor"]["content"]
    assert "python3 -m brz_runner.egress" in files["/usr/local/bin/brz-egress-apply"]["content"]


def test_runner_package_is_embedded_byte_exact():
    text = render_cloud_init(_spec())
    doc = yaml.safe_load(text)
    files = {f["path"]: f for f in doc["write_files"]}
    src = runner_source_dir()
    for name in RUNNER_FILES:
        entry = files[f"/opt/brz/runner/brz_runner/{name}"]
        assert entry["encoding"] == "b64"
        assert base64.b64decode(entry["content"]) == (src / name).read_bytes()
    assert user_data_size_ok(text, limit=256 * 1024)


def test_runcmd_order_locks_down_before_runner_starts():
    doc = yaml.safe_load(render_cloud_init(_spec()))
    cmds = [" ".join(c) if isinstance(c, list) else c for c in doc["runcmd"]]
    i_gvisor = next(i for i, c in enumerate(cmds) if "brz-install-gvisor" in c)
    i_egress = next(i for i, c in enumerate(cmds) if "brz-egress-apply" in c)
    i_ttl = next(i for i, c in enumerate(cmds) if "brz-ttl.timer" in c)
    i_runner = next(i for i, c in enumerate(cmds) if "brz-runner.service" in c)
    assert i_gvisor < i_egress < i_ttl < i_runner


def test_no_gvisor_variant_and_no_domains():
    doc = yaml.safe_load(render_cloud_init(_spec(inner_isolation="none", allowed_domains=[])))
    files = {f["path"]: f for f in doc["write_files"]}
    assert "--no-gvisor" in files["/etc/systemd/system/brz-runner.service"]["content"]
    assert files["/etc/brz/allowed_domains.txt"]["content"].strip().startswith("#")
    assert "INNER_ISOLATION=none" in files["/etc/brz/task.env"]["content"]


def test_spec_validation():
    with pytest.raises(ValueError):
        _spec(allowed_domains=["evil domain"])
    with pytest.raises(ValueError):
        _spec(control_plane_cidr="nope")
    with pytest.raises(ValueError):
        _spec(task_id="has spaces")
    with pytest.raises(ValueError):
        _spec(token_key=b"short")
    with pytest.raises(ValueError):
        _spec(ttl_minutes=1)
    assert _spec(control_plane_cidr="198.51.100.7").control_plane_cidr == "198.51.100.7/32"


def test_no_cloud_secrets_in_user_data():
    """The template must never carry anything but the per-task token key."""
    text = render_cloud_init(_spec())
    for needle in ("VULTR_API_KEY", "INFERENCE_API_KEY", "api.vultr.com", "vultrinference"):
        assert needle not in text
