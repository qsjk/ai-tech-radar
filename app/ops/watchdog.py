"""Watchdog of the worker event loop (VII §36.6).

A thread watches a timestamp (`Clock.monotonic`) that the event loop refreshes every 5 s; beyond
`ops.watchdog_timeout` (300 s) without a refresh, it logs `critical` and stops the process immediately. CPU work runs
outside the event loop, so a freeze that long is a bug.

The stop action is injectable: unit tests replace it so as not to stop the pytest process.
"""

import logging
import os
import sys
import threading
from collections.abc import Callable

import structlog

from app.core.clock import Clock

REFRESH_INTERVAL = 5.0
"""Period of the timestamp refresh by the event loop, and of the check by the thread, in seconds."""

EXIT_WATCHDOG = 1

log = structlog.get_logger()


def exit_process() -> None:
    """Default action: immediate stop, without waiting for the frozen event loop (`os._exit`)."""
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
        """Refresh the timestamp: called by the event loop."""
        self._last = self._clock.monotonic()

    def frozen_for(self) -> float:
        """Seconds elapsed since the last refresh."""
        return self._clock.monotonic() - self._last

    def check(self) -> bool:
        """Thread check: beyond the timeout, log `critical` then run the stop action, only once."""
        frozen_for = self.frozen_for()
        if frozen_for <= self._timeout:
            return False
        if not self._fired:
            self._fired = True
            log.critical("worker.watchdog.timeout", frozen_for_s=round(frozen_for, 1), timeout_s=self._timeout)
            self._on_timeout()
        return True

    async def refresh(self) -> None:
        """Permanent event-loop task: refresh the timestamp every 5 s."""
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
