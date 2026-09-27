"""Injectable clock (ADR-0016, VIII decision 7, §50.1).

Business code never reads an instant through `datetime.now()` or `time.time()`: it goes through a `Clock`, injected
at the start of each process. Tests use a manual clock (`tests/fakes/clock.py`).
"""

import asyncio
import time
from datetime import UTC, datetime
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime:
        """Current instant, in UTC, timezone-aware."""
        ...

    def monotonic(self) -> float:
        """Monotonic clock, in seconds: durations, timeouts, watchdog."""
        ...

    async def sleep(self, seconds: float) -> None:
        """Wait for `seconds` seconds."""
        ...


class SystemClock:
    """Production clock."""

    def now(self) -> datetime:
        return datetime.now(UTC)

    def monotonic(self) -> float:
        return time.monotonic()

    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds)
