"""Module unique de santé (VII §40, ADR-0012) : `/health`, `/api/health` et `python -m app.cli health`.

Calcul à chaque appel, sans aucun appel réseau (VII §40.2) :

1. une lecture courte en `read_session` de `SystemState` (heartbeat) et de la révision du schéma ; échec ou délai de
   plus de 2 s → `down` (condition `database_down`) ;
2. l'âge du heartbeat, calculé **au moment de l'appel** avec la `Clock` injectée, dépasse
   `ops.heartbeat_stale_after` → `down` : un worker mort ne peut pas écrire qu'il est mort ;
3. au moins une condition active (VII §39.5) → `degraded` ; aucune condition n'existe encore au Sprint 1 ;
4. sinon `ok`.

Composants du Sprint 1 : `database`, `worker`, `app`. Les autres (VII §40.3) arrivent avec leur sprint.
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
"""Délai maximal de la lecture de santé, en secondes (VII §40.2)."""

log = structlog.get_logger()


class Status(StrEnum):
    OK = "ok"
    DEGRADED = "degraded"
    DOWN = "down"


HTTP_CODES = {Status.OK: 200, Status.DEGRADED: 200, Status.DOWN: 503}
"""Code HTTP de `/health` par statut (VII §40.2)."""


@dataclass(frozen=True)
class StateSnapshot:
    """Ce que la lecture courte rapporte de la base."""

    schema_revision: str | None
    heartbeat: dict[str, Any] | None


Reader = Callable[[Database], Awaitable[StateSnapshot]]


async def read_state(db: Database) -> StateSnapshot:
    """Lecture courte, en lecture seule : révision du schéma et `SystemState.worker_heartbeat`."""
    async with db.read_session() as session:
        revision = (await session.execute(text("SELECT version_num FROM alembic_version"))).scalar_one_or_none()
        heartbeat = (
            await session.execute(select(SystemState.value).where(SystemState.key == HEARTBEAT_KEY))
        ).scalar_one_or_none()
    return StateSnapshot(schema_revision=revision, heartbeat=heartbeat)


def iso(moment: datetime) -> str:
    """Horodatage UTC à la seconde, suffixe `Z`, comme dans VII §40.3."""
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
        """Réponse de `/health` : le statut seul, aucune information interne (VII §40.2)."""
        return {"status": self.status.value}


class HealthChecker:
    """Calcule la santé. Une instance par processus ; la lecture et son délai sont injectables pour les tests."""

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
        except Exception as error:  # base inaccessible ou lecture trop longue : `down`, quelle qu'en soit la cause
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
        conditions: list[dict[str, Any]] = []  # conditions de VII §39.5 : évaluées par ops.tick, sprints suivants
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
        """Composant `worker` : âge du heartbeat calculé maintenant ; absent, illisible ou périmé → `down`."""
        if heartbeat is None:
            return {"status": Status.DOWN.value, "heartbeat_at": None, "heartbeat_age_s": None}
        try:
            at = datetime.fromisoformat(heartbeat["at"])
            started_at = datetime.fromisoformat(heartbeat["started_at"])
            version = str(heartbeat["version"])
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
