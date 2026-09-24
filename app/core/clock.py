"""Horloge injectable (ADR-0016, VIII décision 7, §50.1).

Aucun instant n'est lu par `datetime.now()` ou `time.time()` dans le code métier : il passe par une `Clock`,
injectée au démarrage de chaque processus. Les tests utilisent une horloge manuelle (`tests/fakes/clock.py`).
"""

import asyncio
import time
from datetime import UTC, datetime
from typing import Protocol


class Clock(Protocol):
    def now(self) -> datetime:
        """Instant courant, en UTC, avec fuseau."""
        ...

    def monotonic(self) -> float:
        """Horloge monotone, en secondes : durées, délais, watchdog."""
        ...

    async def sleep(self, seconds: float) -> None:
        """Attente de `seconds` secondes."""
        ...


class SystemClock:
    """Horloge de production."""

    def now(self) -> datetime:
        return datetime.now(UTC)

    def monotonic(self) -> float:
        return time.monotonic()

    async def sleep(self, seconds: float) -> None:
        await asyncio.sleep(seconds)
