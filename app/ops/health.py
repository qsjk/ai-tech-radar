"""Single health module (VII §40, ADR-0012): `/health`, `/api/health` and `python -m app.cli health`.

Computed on every call, without any network call (VII §40.2):

1. a short `read_session` read of `SystemState` (heartbeat) and of the schema revision; failure or a read longer than
   2 s → `down` (`database_down` condition);
2. the heartbeat age, computed **at call time** with the injected `Clock`, exceeds `ops.heartbeat_stale_after` →
   `down`: a dead worker cannot write that it is dead;
3. at least one active condition (VII §39.5) → `degraded`; no condition exists yet in Sprint 1;
4. otherwise `ok`.

Sprint 1 components: `database`, `worker`, `app`. The others (VII §40.3) come with their sprint.
"""

import asyncio
import os
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

import structlog
from sqlalchemy import select, text

from app.core.clock import Clock
from app.db.models import SystemState
from app.db.session import Database
from app.ops.heartbeat import HEARTBEAT_KEY

READ_TIMEOUT = 2.0
"""Maximum duration of the health read, in seconds (VII §40.2)."""

log = structlog.get_logger()


class Status(StrEnum):
    OK = "ok"
    DEGRADED = "degraded"
    DOWN = "down"


HTTP_CODES = {Status.OK: 200, Status.DEGRADED: 200, Status.DOWN: 503}
"""HTTP status code of `/health` per status (VII §40.2)."""


@dataclass(frozen=True)
class StateSnapshot:
    """What the short read brings back from the database."""

    schema_revision: str | None
    heartbeat: dict[str, Any] | None


Reader = Callable[[Database], Awaitable[StateSnapshot]]


async def read_state(db: Database) -> StateSnapshot:
    """Short read-only read: schema revision and `SystemState.worker_heartbeat`."""
    async with db.read_session() as session:
        revision = (await session.execute(text("SELECT version_num FROM alembic_version"))).scalar_one_or_none()
        heartbeat = (
            await session.execute(select(SystemState.value).where(SystemState.key == HEARTBEAT_KEY))
        ).scalar_one_or_none()
    return StateSnapshot(schema_revision=revision, heartbeat=heartbeat)


def iso(moment: datetime) -> str:
    """UTC timestamp to the second, `Z` suffix, as in VII §40.3."""
    return moment.astimezone(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


def file_size(path: str) -> int:
    try:
        return os.stat(path).st_size
    except FileNotFoundError:
        return 0


@dataclass(frozen=True)
class HealthReport:
    status: Status
    detail: dict[str, Any]

    @property
    def http_code(self) -> int:
        return HTTP_CODES[self.status]

    def public(self) -> dict[str, str]:
        """`/health` response: the status alone, no internal information (VII §40.2)."""
        return {"status": self.status.value}


class HealthChecker:
    """Compute health. One instance per process; the read and its timeout are injectable for tests."""

    def __init__(
        self,
        db: Database,
        clock: Clock,
        *,
        db_path: str,
        heartbeat_stale_after: timedelta,
        version: str,
        started_at: datetime,
        reader: Reader = read_state,
        read_timeout: float = READ_TIMEOUT,
    ) -> None:
        self.db = db
        self.clock = clock
        self.db_path = db_path
        self.heartbeat_stale_after = heartbeat_stale_after
        self.version = version
        self.started_at = started_at
        self.reader = reader
        self.read_timeout = read_timeout

    async def check(self) -> HealthReport:
        checked_at = self.clock.now()
        try:
            async with asyncio.timeout(self.read_timeout):
                snapshot = await self.reader(self.db)
        except Exception as error:  # unreachable database or read too long: `down`, whatever the cause
            timed_out = isinstance(error, TimeoutError)
            log.warning(
                "health.database.down",
                reason="timeout" if timed_out else "error",
                error_class=error.__class__.__name__,
                timeout_s=self.read_timeout,
            )
            database: dict[str, Any] = {"status": Status.DOWN.value}
            worker: dict[str, Any] = {"status": Status.DOWN.value, "heartbeat_at": None, "heartbeat_age_s": None}
            status = Status.DOWN
        else:
            database = {
                "status": Status.OK.value,
                "schema_revision": snapshot.schema_revision,
                "db_bytes": file_size(self.db_path),
                "wal_bytes": file_size(f"{self.db_path}-wal"),
            }
            worker = self._worker(snapshot.heartbeat, checked_at)
            status = Status.DOWN if worker["status"] == Status.DOWN.value else Status.OK
        conditions: list[dict[str, Any]] = []  # VII §39.5 conditions: evaluated by ops.tick, later sprints
        if status is Status.OK and conditions:
            status = Status.DEGRADED
        detail = {
            "status": status.value,
            "checked_at": iso(checked_at),
            "version": self.version,
            "components": {
                "database": database,
                "worker": worker,
                "app": {"started_at": iso(self.started_at), "db_locked_1h": self.db.db_locked.count_in_window()},
            },
            "conditions": conditions,
        }
        return HealthReport(status, detail)

    def _worker(self, heartbeat: dict[str, Any] | None, checked_at: datetime) -> dict[str, Any]:
        """`worker` component: heartbeat age computed now; missing, unreadable or stale → `down`.

        A timestamp without timezone is unreadable: it cannot be compared with the aware `Clock`.
        """
        if heartbeat is None:
            return {"status": Status.DOWN.value, "heartbeat_at": None, "heartbeat_age_s": None}
        try:
            at = datetime.fromisoformat(heartbeat["at"])
            started_at = datetime.fromisoformat(heartbeat["started_at"])
            version = str(heartbeat["version"])
            if at.tzinfo is None or started_at.tzinfo is None:
                raise ValueError("heartbeat timestamp without timezone")
        except (KeyError, TypeError, ValueError):
            log.warning("health.heartbeat.unreadable")
            return {"status": Status.DOWN.value, "heartbeat_at": None, "heartbeat_age_s": None}
        age = checked_at - at
        stale = age > self.heartbeat_stale_after
        return {
            "status": (Status.DOWN if stale else Status.OK).value,
            "heartbeat_at": iso(at),
            "heartbeat_age_s": int(age.total_seconds()),
            "started_at": iso(started_at),
            "version": version,
        }
