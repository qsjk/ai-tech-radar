"""Horloge manuelle des tests (docs/architecture.md §5.2) : le temps n'avance que sur demande, sans attente réelle."""

import asyncio
from datetime import UTC, datetime, timedelta


class ManualClock:
    def __init__(self, start: datetime | None = None) -> None:
        if start is None:
            start = datetime(2026, 1, 1, tzinfo=UTC)
        if start.tzinfo is None:
            raise ValueError("ManualClock exige un instant avec fuseau")
        self._now = start.astimezone(UTC)
        self._monotonic = 0.0

    def now(self) -> datetime:
        return self._now

    def monotonic(self) -> float:
        return self._monotonic

    def advance(self, delta: timedelta) -> None:
        if delta < timedelta(0):
            raise ValueError("le temps ne recule pas")
        self._now += delta
        self._monotonic += delta.total_seconds()

    async def sleep(self, seconds: float) -> None:
        self.advance(timedelta(seconds=seconds))
        await asyncio.sleep(0)  # cède la main à la boucle, sans attente réelle
