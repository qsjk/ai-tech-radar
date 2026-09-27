"""Watchdog de l'event-loop du worker (VII §36.6).

Un thread surveille un horodatage (`Clock.monotonic`) que l'event-loop rafraîchit toutes les 5 s ; au-delà de
`ops.watchdog_timeout` (300 s) sans rafraîchissement, log `critical` et arrêt immédiat du processus. Le travail CPU
étant hors event-loop, un gel de cette durée est un bug.

L'action d'arrêt est injectable : les tests unitaires la remplacent pour ne pas arrêter le processus de pytest.
"""

import logging
import os
import sys
import threading
from collections.abc import Callable

import structlog

from app.core.clock import Clock

REFRESH_INTERVAL = 5.0
"""Période de rafraîchissement de l'horodatage par l'event-loop, et de contrôle par le thread, en secondes."""

EXIT_WATCHDOG = 1

log = structlog.get_logger()


def exit_process() -> None:
    """Action par défaut : arrêt immédiat, sans attendre l'event-loop gelée (`os._exit`)."""
    for handler in logging.getLogger().handlers:
        handler.flush()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(EXIT_WATCHDOG)


class Watchdog:
    def __init__(
        self,
        clock: Clock,
        timeout: float,
        *,
        on_timeout: Callable[[], None] = exit_process,
        check_interval: float = REFRESH_INTERVAL,
    ) -> None:
        self._clock = clock
        self._timeout = timeout
        self._on_timeout = on_timeout
        self._check_interval = check_interval
        self._last = clock.monotonic()
        self._fired = False
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def beat(self) -> None:
        """Rafraîchit l'horodatage : appelé par l'event-loop."""
        self._last = self._clock.monotonic()

    def frozen_for(self) -> float:
        """Secondes écoulées depuis le dernier rafraîchissement."""
        return self._clock.monotonic() - self._last

    def check(self) -> bool:
        """Contrôle du thread : au-delà du délai, log `critical` puis action d'arrêt, une seule fois."""
        frozen_for = self.frozen_for()
        if frozen_for <= self._timeout:
            return False
        if not self._fired:
            self._fired = True
            log.critical("worker.watchdog.timeout", frozen_for_s=round(frozen_for, 1), timeout_s=self._timeout)
            self._on_timeout()
        return True

    async def refresh(self) -> None:
        """Tâche permanente de l'event-loop : rafraîchit l'horodatage toutes les 5 s."""
        while True:
            self.beat()
            await self._clock.sleep(REFRESH_INTERVAL)

    def start(self) -> None:
        self.beat()
        self._thread = threading.Thread(target=self._watch, name="watchdog", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join()

    def _watch(self) -> None:
        while not self._stop.wait(self._check_interval):
            if self.check():
                return
