from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone

import pytest

from brz.vultr.client import VultrClient, VultrError, VultrNotFound, VultrTimeout
from brz.vultr.mock import MockVultrState, age_instances
from brz.vultr.models import FirewallRuleCreate, InstanceCreate

SPEC = InstanceCreate(
    region="ewr",
    plan="vhp-1c-1gb-amd",
    os_id=2284,
    label="brz-task-abc",
    hostname="brz-abc",
    tags=["brz-sandbox", "task-abc"],
    user_data="#cloud-config\nhostname: brz-abc\n",
)


async def test_create_active_delete_404(vultr: VultrClient, vultr_state: MockVultrState):
    inst = await vultr.create_instance(SPEC)
    assert inst.status == "pending"
    assert inst.tags == ["brz-sandbox", "task-abc"]

    # user_data must have been base64-encoded on the wire
    post = vultr_state.calls_for("POST", "/instances")[0]
    assert base64.b64decode(post.body["user_data"]).decode() == SPEC.user_data
    assert post.body["os_id"] == 2284 and "snapshot_id" not in post.body

    active = await vultr.wait_until_active(inst.id, timeout=60, interval=5)
    assert active.is_ready and active.main_ip == "203.0.113.42"
    polls = vultr_state.calls_for("GET", f"/instances/{inst.id}")
    assert len(polls) == vultr_state.activate_after_polls

    proof = await vultr.destroy_and_confirm(inst.id, timeout=30)
    assert proof.destroyed and proof.http_status == 404
    with pytest.raises(VultrNotFound):
        await vultr.get_instance(inst.id)
    # a second DELETE is a 404 too, and must not raise out of destroy_and_confirm
    proof2 = await vultr.destroy_and_confirm(inst.id, timeout=30)
    assert proof2.destroyed
    assert vultr_state.live_instances() == []


async def test_wait_until_active_times_out(vultr: VultrClient, vultr_state: MockVultrState):
    vultr_state.activate_after_polls = 10_000
    inst = await vultr.create_instance(SPEC)
    with pytest.raises(VultrTimeout):
        await vultr.wait_until_active(inst.id, timeout=20, interval=5)


async def test_list_by_tag_and_orphan_cleanup(vultr: VultrClient, vultr_state: MockVultrState):
    a = await vultr.create_instance(SPEC)
    b = await vultr.create_instance(SPEC.model_copy(update={"tags": ["brz-sandbox", "task-b"]}))
    other = await vultr.create_instance(SPEC.model_copy(update={"tags": ["control-plane"]}))

    tagged = await vultr.list_instances(tag="brz-sandbox")
    assert {i.id for i in tagged} == {a.id, b.id}

    # nothing is old enough yet
    assert await vultr.cleanup_orphans("brz-sandbox", older_than_seconds=600) == []

    age_instances(vultr_state, timedelta(minutes=15))
    # make "other" look old too: it must survive because it carries a different tag
    deleted = await vultr.cleanup_orphans("brz-sandbox", older_than_seconds=600)
    assert set(deleted) == {a.id, b.id}
    assert {i.id for i in vultr_state.live_instances()} == {other.id}
    with pytest.raises(VultrNotFound):
        await vultr.get_instance(a.id)


async def test_cleanup_orphans_uses_explicit_now(vultr: VultrClient):
    inst = await vultr.create_instance(SPEC)
    future = datetime.now(timezone.utc) + timedelta(hours=2)
    assert await vultr.cleanup_orphans("brz-sandbox", older_than_seconds=3600, now=future) == [inst.id]


async def test_429_is_retried_with_backoff(vultr: VultrClient, vultr_state: MockVultrState, fake_clock):
    vultr_state.fail_next(429, times=2, method="POST", path_prefix="/instances")
    inst = await vultr.create_instance(SPEC)
    assert inst.id in vultr_state.instances
    posts = vultr_state.calls_for("POST", "/instances")
    assert [c.status for c in posts] == [429, 429, 202]
    assert vultr.retry_count == 2
    # backoff: 0.5 then 1.0 seconds, but Retry-After: 1 raises the first to 1.0
    assert fake_clock.t == pytest.approx(2.0)


async def test_5xx_retries_then_raises(vultr: VultrClient, vultr_state: MockVultrState):
    vultr_state.fail_next(503, times=10, method="GET", path_prefix="/plans")
    with pytest.raises(VultrError) as exc:
        await vultr.list_plans()
    assert exc.value.status == 503
    assert len(vultr_state.calls_for("GET", "/plans")) == 1 + vultr.max_retries


async def test_4xx_is_not_retried(vultr: VultrClient, vultr_state: MockVultrState):
    with pytest.raises(VultrError) as exc:
        await vultr.create_instance(SPEC.model_copy(update={"region": "nowhere"}))
    assert exc.value.status == 400
    assert len(vultr_state.calls_for("POST", "/instances")) == 1


async def test_bad_api_key_is_401(vultr_app):
    import httpx

    client = VultrClient("WRONG", base_url="http://mock-vultr/v2", transport=httpx.ASGITransport(app=vultr_app))
    with pytest.raises(VultrError) as exc:
        await client.list_regions()
    assert exc.value.status == 401
    await client.aclose()


async def test_catalogue_models(vultr: VultrClient):
    plans = await vultr.list_plans()
    vx1 = next(p for p in plans if p.id == "vx1-g-2c-8g")
    assert vx1.effective_hourly_cost() == pytest.approx(0.060)
    vc2 = next(p for p in plans if p.id == "vc2-1c-1gb")
    vc2_no_hourly = vc2.model_copy(update={"hourly_cost": None})
    assert vc2_no_hourly.effective_hourly_cost() == pytest.approx(5.0 / 672, rel=1e-3)
    assert "vx1" in {p.type for p in await vultr.list_plans(plan_type="vx1")}
    regions = await vultr.list_regions()
    assert "ewr" in {r.id for r in regions}
    oses = await vultr.list_os()
    assert any(o.family == "ubuntu" for o in oses)


async def test_snapshot_create_body():
    spec = InstanceCreate(region="ewr", plan="vhp-1c-1gb-amd", snapshot_id="snap-1", firewall_group_id="fw-1")
    body = spec.to_api_body()
    assert body["snapshot_id"] == "snap-1" and "os_id" not in body
    assert body["firewall_group_id"] == "fw-1"
    with pytest.raises(ValueError):
        InstanceCreate(region="ewr", plan="x").to_api_body()


async def test_firewall_group_inbound_only(vultr: VultrClient, vultr_state: MockVultrState):
    group = await vultr.create_inbound_only_group("brz task-abc", "198.51.100.7", 8700)
    rules = await vultr.list_firewall_rules(group.id)
    assert len(rules) == 1
    assert rules[0].subnet == "198.51.100.7" and rules[0].subnet_size == 32 and rules[0].port == "8700"
    extra = await vultr.create_firewall_rule(group.id, FirewallRuleCreate(port="22", notes="ssh for debugging"))
    assert extra.port == "22"
    await vultr.delete_firewall_group(group.id)
    with pytest.raises(VultrNotFound):
        await vultr.list_firewall_rules(group.id)


async def test_object_storage_stubs(vultr: VultrClient):
    created = await vultr.create_object_storage(cluster_id=2, label="brz-receipts")
    assert created.s3_hostname.endswith("vultrobjects.com")
    assert (await vultr.get_object_storage(created.id)).label == "brz-receipts"
    assert [o.id for o in await vultr.list_object_storage()] == [created.id]
