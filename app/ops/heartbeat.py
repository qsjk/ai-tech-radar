"""Heartbeat du worker (VII §36.6, §39.3 ; docs/database.md §3.19).

`SystemState.worker_heartbeat` = `{at, started_at, version, pid}`, écrit toutes les `ops.heartbeat_interval` (30 s).
L'instant vient de la `Clock` ; l'écriture passe par `Database.run_write` (retry borné sur verrou). C'est la preuve de
vie du worker, indépendante de son activité : `/health` la lit (T1.7).
"""

import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

import structlog
from sqlalchemy.dialects.sqlite import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import Clock
from app.db.models import SystemState
from app.db.session import Database, DatabaseLockedError

HEARTBEAT_KEY = "worker_heartbeat"

log = structlog.get_logger()


@dataclass
class Heartbeat:
    """Écrit la preuve de vie du worker. Une seule instance par processus, créée au boot."""

    db: Database
    clock: Clock
    interval: timedelta
    version: str
    pid: int = field(default_factory=os.getpid)
    started_at: datetime = field(init=False)
    beats: int = field(init=False, default=0)

    def __post_init__(self) -> None:
        self.started_at = self.clock.now()

    def value(self, at: datetime) -> dict[str, Any]:
        return {
            "at": at.isoformat(),
            "started_at": self.started_at.isoformat(),
            "version": self.version,
            "pid": self.pid,
        }

    async def beat(self) -> None:
        """Écrit un heartbeat, dans une transaction d'écriture."""
        at = self.clock.now()
        value = self.value(at)

        async def upsert(session: AsyncSession) -> None:
            statement = insert(SystemState).values(key=HEARTBEAT_KEY, value=value, updated_at=at)
            await session.execute(
                statement.on_conflict_do_update(
                    index_elements=[SystemState.key], set_={"value": value, "updated_at": at}
                )
            )

        await self.db.run_write(upsert)
        self.beats += 1

    async def run(self) -> None:
        """Tâche permanente : un heartbeat toutes les `interval`. Le premier est écrit au boot, par `beat()`.

        Un verrou prolongé (`DatabaseLockedError`, déjà compté par `db_locked`) ne tue pas la tâche : le tour est
        sauté et le heartbeat suivant réessaie ; si les échecs persistent, le heartbeat vieillit et `/health` le
        signale. Toute autre exception reste fatale (supervision fail-fast).
        """
        while True:
            await self.clock.sleep(self.interval.total_seconds())
            try:
                await self.beat()
            except DatabaseLockedError as error:
                log.warning("worker.heartbeat.skipped", reason=str(error))
