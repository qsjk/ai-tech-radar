"""Event-loop watchdog (VII §36.6): logic, with a manual clock and a spy stop action."""

import asyncio
import threading
from datetime import timedelta

import pytest
from structlog.testing import capture_logs

from app.ops.watchdog import REFRESH_INTERVAL, Watchdog
from tests.fakes.clock import ManualClock, SteppedClock


class StopSpy:
    def __init__(self) -> None:
        self.calls = 0
        self.done = threading.Event()

    def __call__(self) -> None:
        self.calls += 1
        self.done.set()


@pytest.mark.spec("T-OPS-07")
def test_no_stop_while_the_timeout_is_not_exceeded() -> None:
    clock = ManualClock()
    stop = StopSpy()
    watchdog = Watchdog(clock, 300, on_timeout=stop)
    clock.advance(timedelta(seconds=300))
    assert watchdog.check() is False
    assert stop.calls == 0


@pytest.mark.spec("T-OPS-07")
def test_stop_beyond_the_timeout_with_a_single_critical_log() -> None:
    clock = ManualClock()
    stop = StopSpy()
    watchdog = Watchdog(clock, 300, on_timeout=stop)
    clock.advance(timedelta(seconds=301))
    with capture_logs() as logs:
        assert watchdog.check() is True
        assert watchdog.check() is True
    assert stop.calls == 1
    assert [(e["event"], e["log_level"], e["timeout_s"]) for e in logs] == [
        ("worker.watchdog.timeout", "critical", 300)
    ]


@pytest.mark.spec("T-OPS-07")
def test_refresh_pushes_the_deadline_back() -> None:
    clock = ManualClock()
    stop = StopSpy()
    watchdog = Watchdog(clock, 300, on_timeout=stop)
    for _ in range(10):
        clock.advance(timedelta(seconds=200))
        watchdog.beat()
        assert watchdog.check() is False
    assert stop.calls == 0


@pytest.mark.spec("T-OPS-07")
def test_the_loop_refreshes_every_5_s() -> None:
    async def scenario() -> list[float]:
        clock = SteppedClock()
        watchdog = Watchdog(clock, 300, on_timeout=StopSpy())
        task = asyncio.create_task(watchdog.refresh())
        frozen = []
        try:
            for _ in range(3):
                while clock.sleepers == 0:
                    await asyncio.sleep(0)
                clock.advance(timedelta(seconds=4))
                frozen.append(watchdog.frozen_for())
                clock.advance(timedelta(seconds=1))
                await asyncio.sleep(0)
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        return frozen

    assert REFRESH_INTERVAL == 5.0
    assert asyncio.run(scenario()) == [4.0, 4.0, 4.0]


@pytest.mark.spec("T-OPS-07")
def test_the_thread_triggers_the_stop_action() -> None:
    clock = ManualClock()
    stop = StopSpy()
    watchdog = Watchdog(clock, 300, on_timeout=stop, check_interval=0.001)
    watchdog.start()
    try:
        clock.advance(timedelta(seconds=301))
        assert stop.done.wait(timeout=5)
    finally:
        watchdog.stop()
    assert stop.calls == 1


@pytest.mark.spec("T-OPS-07")
def test_stop_ends_the_thread_without_action() -> None:
    stop = StopSpy()
    watchdog = Watchdog(ManualClock(), 300, on_timeout=stop, check_interval=0.001)
    watchdog.start()
    watchdog.stop()
    assert stop.calls == 0
