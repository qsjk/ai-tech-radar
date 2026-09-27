"""Manual test clock (docs/architecture.md §5.2): time only moves on request, without any real wait."""

import asyncio
from datetime import UTC, datetime, timedelta


class ManualClock:
    def __init__(self, start: datetime | None = None) -> None:
        if start is None:
            start = datetime(2026, 1, 1, tzinfo=UTC)
        if start.tzinfo is None:
            raise ValueError("ManualClock requires a timezone-aware instant")
        self._now = start.astimezone(UTC)
        self._monotonic = 0.0

    def now(self) -> datetime:
        return self._now

    def monotonic(self) -> float:
        return self._monotonic

    def advance(self, delta: timedelta) -> None:
        if delta < timedelta(0):
            raise ValueError("time does not go backwards")
        self._now += delta
        self._monotonic += delta.total_seconds()

    async def sleep(self, seconds: float) -> None:
        self.advance(timedelta(seconds=seconds))
        await asyncio.sleep(0)  # yield to the loop, without any real wait


class SteppedClock(ManualClock):
    """Manual clock whose `sleep` waits until the test advances time up to the deadline.

    Useful for permanent loops (heartbeat, watchdog): each round only happens when the test calls `advance`, without
    any real wait.
    """

    def __init__(self, start: datetime | None = None) -> None:
        super().__init__(start)
        self._sleepers: list[tuple[float, asyncio.Future[None]]] = []

    async def sleep(self, seconds: float) -> None:
        future: asyncio.Future[None] = asyncio.get_running_loop().create_future()
        self._sleepers.append((self.monotonic() + seconds, future))
        await future

    def advance(self, delta: timedelta) -> None:
        super().advance(delta)
        remaining = []
        for deadline, future in self._sleepers:
            if deadline <= self.monotonic():
                if not future.done():
                    future.set_result(None)
            else:
                remaining.append((deadline, future))
        self._sleepers = remaining

    @property
    def sleepers(self) -> int:
        """Number of tasks waiting in `sleep`."""
        return sum(1 for _, future in self._sleepers if not future.done())
