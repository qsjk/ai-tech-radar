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


class SteppedClock(ManualClock):
    """Horloge manuelle dont `sleep` attend que le test avance le temps jusqu'à l'échéance.

    Utile pour les boucles permanentes (heartbeat, watchdog) : chaque tour n'a lieu que quand le test appelle
    `advance`, sans attente réelle.
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
        """Nombre de tâches en attente dans `sleep`."""
        return sum(1 for _, future in self._sleepers if not future.done())
