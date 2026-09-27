"""Worker heartbeat (VII §36.6, §39.3; docs/database.md §3.19).

`SystemState.worker_heartbeat` = `{at, started_at, version, pid}`, written every `ops.heartbeat_interval` (30 s).
The instant comes from the `Clock`; the write goes through `Database.run_write` (bounded retry on lock). It is the
worker's proof of life, independent of its activity: `/health` reads it (T1.7).
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
    """Write the worker's proof of life. A single instance per process, created at boot."""

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
        """Write one heartbeat, in a write transaction."""
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
        """Permanent task: one heartbeat every `interval`. The first one is written at boot, by `beat()`.

        A prolonged lock (`DatabaseLockedError`, already counted by `db_locked`) does not kill the task: the round is
        skipped and the next heartbeat retries; if failures persist, the heartbeat ages and `/health` reports it. Any
        other exception stays fatal (fail-fast supervision).
        """
        while True:
            await self.clock.sleep(self.interval.total_seconds())
            try:
                await self.beat()
            except DatabaseLockedError as error:
                log.warning("worker.heartbeat.skipped", reason=str(error))
