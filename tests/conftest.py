from __future__ import annotations

import httpx
import pytest

from brz.vultr.client import VultrClient
from brz.vultr.mock import MOCK_API_KEY, MockVultrState, create_mock_app


async def _no_sleep(_: float) -> None:
    return None


class FakeClock:
    """Monotonic clock advanced manually by tests (so wait_until_active can time out instantly)."""

    def __init__(self) -> None:
        self.t = 0.0

    def __call__(self) -> float:
        return self.t

    def advance(self, seconds: float) -> None:
        self.t += seconds


@pytest.fixture
def vultr_state() -> MockVultrState:
    return MockVultrState()


@pytest.fixture
def vultr_app(vultr_state: MockVultrState):
    return create_mock_app(vultr_state)


@pytest.fixture
def fake_clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
async def vultr(vultr_app, fake_clock: FakeClock):
    """A real VultrClient wired to the in-process mock. No network, no real sleeps."""
    transport = httpx.ASGITransport(app=vultr_app)
    client = VultrClient(
        MOCK_API_KEY,
        base_url="http://mock-vultr/v2",
        transport=transport,
        sleep=_sleep_and_tick(fake_clock),
        clock=fake_clock,
    )
    try:
        yield client
    finally:
        await client.aclose()


def _sleep_and_tick(clock: FakeClock):
    async def _sleep(seconds: float) -> None:
        clock.advance(seconds)

    return _sleep
