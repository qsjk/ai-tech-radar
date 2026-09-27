"""Session factories, bounded retry on lock and `db_locked` counter (III §10.3, §10.7; II §8.6).

- `write_session`: transaction opened with `BEGIN IMMEDIATE`.
- `read_session`: deferred transaction (`BEGIN DEFERRED`), read-only; does not take the write lock.
- `Database.run_write`: runs a write unit in a transaction; if `busy_timeout` is exhausted ("database is locked"),
  the transaction is rolled back, the failure is counted in `db_locked`, then the unit is replayed, at most `attempts`
  times in total. `busy_timeout` already carries the wait: the replay is immediate.
"""

from collections import deque
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta

import structlog
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.core.clock import Clock
from app.db.engine import READ_ONLY_OPTION

DEFAULT_WRITE_ATTEMPTS = 3
DB_LOCKED_WINDOW = timedelta(hours=1)  # window of the db_locked condition (VII §39.4, ops.db_locked_max_per_hour)

log = structlog.get_logger()


class DatabaseLockedError(RuntimeError):
    """Write abandoned: `busy_timeout` exhausted on every attempt."""


def is_database_locked(error: OperationalError) -> bool:
    return "database is locked" in str(error.orig).lower()


class DbLockedCounter:
    """`db_locked` counter of the process: failure timestamps, read from the injected `Clock`."""

    def __init__(self, clock: Clock, window: timedelta = DB_LOCKED_WINDOW) -> None:
        self._clock = clock
        self._window = window
        self._events: deque[datetime] = deque()
        self.total = 0

    def record(self) -> None:
        self._events.append(self._clock.now())
        self.total += 1

    def count_in_window(self) -> int:
        """Number of failures in the last window (one hour by default)."""
        horizon = self._clock.now() - self._window
        while self._events and self._events[0] <= horizon:
            self._events.popleft()
        return len(self._events)


@dataclass
class Database:
    """Database access of a process: engine, session factories and `db_locked` counter."""

    engine: AsyncEngine
    clock: Clock
    write_session: async_sessionmaker[AsyncSession] = field(init=False)
    read_session: async_sessionmaker[AsyncSession] = field(init=False)
    db_locked: DbLockedCounter = field(init=False)

    def __post_init__(self) -> None:
        self.write_session = async_sessionmaker(self.engine, expire_on_commit=False)
        self.read_session = async_sessionmaker(
            self.engine.execution_options(**{READ_ONLY_OPTION: True}), expire_on_commit=False
        )
        self.db_locked = DbLockedCounter(self.clock)

    async def run_write[T](
        self, unit: Callable[[AsyncSession], Awaitable[T]], *, attempts: int = DEFAULT_WRITE_ATTEMPTS
    ) -> T:
        """Run `unit` in a write transaction; replay on lock, at most `attempts` times in total."""
        if attempts < 1:
            raise ValueError("attempts must be at least 1")
        for attempt in range(1, attempts + 1):
            try:
                async with self.write_session() as session, session.begin():
                    return await unit(session)
            except OperationalError as error:
                if not is_database_locked(error):
                    raise
                self.db_locked.record()
                log.warning("db.locked", attempt=attempt, attempts=attempts)
        log.error("db.write.abandoned", attempts=attempts)
        raise DatabaseLockedError(f"write abandoned after {attempts} attempts: database is locked")

    async def dispose(self) -> None:
        await self.engine.dispose()
