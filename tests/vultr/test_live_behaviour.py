"""What the real API did on 2026-11-06 that the mock did not: pinned here so the client keeps handling it."""

from __future__ import annotations

import httpx
import pytest

from brz.vultr import InstanceCreate, VultrClient
from brz.vultr.client import VultrBusy, VultrCapacity, VultrError

LIMIT = {
    "error": "Server add failed: You have reached the maximum number of active instances for this account.",
    "status": 400,
}
INSTANCE = {"instance": {"id": "i-1", "label": "brz-t-primary", "status": "pending"}}
SPEC = InstanceCreate(region="ewr", plan="p", os_id=2284, label="brz-t-primary")


async def no_sleep(_: float) -> None:
    return None


def client(handler, **kw) -> VultrClient:
    ticks = iter(range(10_000))
    return VultrClient(
        "k",
        base_url="http://v/v2",
        transport=httpx.MockTransport(handler),
        sleep=no_sleep,
        clock=lambda: float(next(ticks)),
        **kw,
    )


async def test_error_keeps_vultr_explanation():
    c = client(lambda r: httpx.Response(400, json={"error": "bad plan", "status": 400}))
    with pytest.raises(VultrError, match="bad plan"):
        await c.create_instance(SPEC)
    await c.aclose()


async def test_instance_limit_is_waited_out():
    replies = iter(
        [httpx.Response(400, json=LIMIT), httpx.Response(400, json=LIMIT), httpx.Response(202, json=INSTANCE)]
    )
    c = client(lambda r: next(replies))
    inst = await c.create_instance(SPEC, capacity_wait_s=100)
    await c.aclose()
    assert inst.id == "i-1"


async def test_instance_limit_gives_up_at_the_deadline():
    c = client(lambda r: httpx.Response(400, json=LIMIT))
    with pytest.raises(VultrCapacity):
        await c.create_instance(SPEC, capacity_wait_s=3)
    await c.aclose()


async def test_a_timed_out_create_is_never_sent_twice():
    """The first POST may have worked. A second POST would be a second billing VM."""
    posts = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            posts.append(1)
            raise httpx.ReadTimeout("slow", request=request)
        return httpx.Response(200, json={"instances": [INSTANCE["instance"]], "meta": {"links": {"next": ""}}})

    c = client(handler)
    inst = await c.create_instance(SPEC)
    await c.aclose()
    assert len(posts) == 1
    assert inst.id == "i-1"


async def test_timed_out_create_that_made_nothing_reports_failure():
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "POST":
            raise httpx.ReadTimeout("slow", request=request)
        return httpx.Response(200, json={"instances": [], "meta": {"links": {"next": ""}}})

    c = client(handler)
    with pytest.raises(VultrError):
        await c.create_instance(SPEC)
    await c.aclose()


async def test_delete_while_installing_is_retried_until_accepted():
    deletes = iter(
        [httpx.Response(409, json={"error": "busy"}), httpx.Response(409, json={"error": "busy"}), httpx.Response(204)]
    )

    def handler(request: httpx.Request) -> httpx.Response:
        return next(deletes) if request.method == "DELETE" else httpx.Response(404, json={})

    c = client(handler)
    proof = await c.destroy_and_confirm("i-1", timeout=5)
    await c.aclose()
    assert proof.destroyed


async def test_delete_gives_up_at_the_deadline():
    c = client(lambda r: httpx.Response(409, json={"error": "busy"}))
    with pytest.raises(VultrBusy):
        await c.destroy_and_confirm("i-1", busy_wait_s=3, timeout=5)
    await c.aclose()
