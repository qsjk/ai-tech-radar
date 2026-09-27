"""Injectable clock (ADR-0016). No catalogue identifier: the `Clock` is a cross-cutting rule (VIII §50.1)."""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from app.core.clock import Clock, SystemClock
from tests.fakes.clock import ManualClock


def test_system_clock_returns_a_timezone_aware_utc_instant() -> None:
    now = SystemClock().now()
    assert now.tzinfo is not None
    assert now.utcoffset() == timedelta(0)


def test_manual_clock_advances_without_real_wait() -> None:
    clock: Clock = ManualClock(datetime(2026, 9, 24, 8, 0, tzinfo=UTC))
    asyncio.run(clock.sleep(3600))
    assert clock.now() == datetime(2026, 9, 24, 9, 0, tzinfo=UTC)
    assert clock.monotonic() == 3600.0


def test_manual_clock_rejects_a_naive_instant_and_going_back() -> None:
    with pytest.raises(ValueError):
        ManualClock(datetime(2026, 9, 24))
    clock = ManualClock()
    with pytest.raises(ValueError):
        clock.advance(timedelta(seconds=-1))
