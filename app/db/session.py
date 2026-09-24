"""Fabriques de sessions, retry borné sur verrou et compteur `db_locked` (III §10.3, §10.7 ; II §8.6).

- `write_session` : transaction ouverte en `BEGIN IMMEDIATE`.
- `read_session` : transaction différée (`BEGIN DEFERRED`), lecture seule ; ne prend pas le verrou d'écriture.
- `Database.run_write` : exécute une unité d'écriture dans une transaction ; si `busy_timeout` est épuisé
  (« database is locked »), la transaction est annulée, l'échec est compté dans `db_locked`, puis l'unité est rejouée,
  au plus `attempts` fois en tout. `busy_timeout` porte déjà l'attente : le rejeu est immédiat.
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
DB_LOCKED_WINDOW = timedelta(hours=1)  # fenêtre de la condition db_locked (VII §39.4, ops.db_locked_max_per_hour)

log = structlog.get_logger()


class DatabaseLockedError(RuntimeError):
    """Écriture abandonnée : `busy_timeout` épuisé à chaque tentative."""


def is_database_locked(error: OperationalError) -> bool:
    return "database is locked" in str(error.orig).lower()


class DbLockedCounter:
    """Compteur `db_locked` du processus : horodatages des échecs, lus par la `Clock` injectée."""

    def __init__(self, clock: Clock, window: timedelta = DB_LOCKED_WINDOW) -> None:
        self._clock = clock
        self._window = window
        self._events: deque[datetime] = deque()
        self.total = 0

    def record(self) -> None:
        self._events.append(self._clock.now())
        self.total += 1

    def count_in_window(self) -> int:
        """Nombre d'échecs dans la dernière fenêtre (une heure par défaut)."""
        horizon = self._clock.now() - self._window
        while self._events and self._events[0] <= horizon:
            self._events.popleft()
        return len(self._events)


@dataclass
class Database:
    """Accès base d'un processus : moteur, fabriques de sessions et compteur `db_locked`."""

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
        """Exécute `unit` dans une transaction d'écriture ; rejoue sur verrou, au plus `attempts` fois en tout."""
        if attempts < 1:
            raise ValueError("attempts doit valoir au moins 1")
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
        raise DatabaseLockedError(f"écriture abandonnée après {attempts} tentatives : database is locked")

    async def dispose(self) -> None:
        await self.engine.dispose()
