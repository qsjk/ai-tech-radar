"""Health module (VII §40): status computed at call time, heartbeat age from the `Clock`, read bounded to 2 s."""

import asyncio
import sqlite3
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.exc import OperationalError

from app.db.engine import create_engine
from app.db.session import Database
from app.ops.health import READ_TIMEOUT, HealthChecker, HealthReport, StateSnapshot, Status
from app.ops.heartbeat import Heartbeat
from tests.fakes.clock import ManualClock

START = datetime(2026, 9, 27, 8, 0, tzinfo=UTC)
STALE_AFTER = timedelta(seconds=120)


async def check(db_path: str, clock: ManualClock, **options: object) -> HealthReport:
    db = Database(create_engine(db_path), clock)
    try:
        checker = HealthChecker(
            db,
            clock,
            db_path=db_path,
            heartbeat_stale_after=STALE_AFTER,
            version="abc1234",
            started_at=START,
            **options,  # type: ignore[arg-type]
        )
        return await checker.check()
    finally:
        await db.dispose()


async def write_heartbeat(db_path: str, clock: ManualClock) -> None:
    db = Database(create_engine(db_path), clock)
    try:
        await Heartbeat(db, clock, timedelta(seconds=30), version="w-1", pid=4242).beat()
    finally:
        await db.dispose()


@pytest.mark.spec("T-OPS-02")
def test_fresh_heartbeat_ok_with_the_detail(migrated_db: str) -> None:
    async def scenario() -> HealthReport:
        clock = ManualClock(START)
        await write_heartbeat(migrated_db, clock)
        clock.advance(timedelta(seconds=12))
        return await check(migrated_db, clock)

    report = asyncio.run(scenario())
    assert (report.status, report.http_code, report.public()) == (Status.OK, 200, {"status": "ok"})
    detail = report.detail
    assert detail["checked_at"] == "2026-09-27T08:00:12Z"
    assert detail["version"] == "abc1234"
    assert detail["conditions"] == []
    database, worker, app = (detail["components"][name] for name in ("database", "worker", "app"))
    assert database["status"] == "ok"
    assert database["schema_revision"] == "0001"
    assert database["db_bytes"] > 0
    assert database["wal_bytes"] >= 0
    assert worker == {
        "status": "ok",
        "heartbeat_at": "2026-09-27T08:00:00Z",
        "heartbeat_age_s": 12,
        "started_at": "2026-09-27T08:00:00Z",
        "version": "w-1",
    }
    assert app == {"started_at": "2026-09-27T08:00:00Z", "db_locked_1h": 0}


@pytest.mark.spec("T-OPS-02")
def test_age_computed_at_call_time(migrated_db: str) -> None:
    """Same heartbeat in the database: `ok` at 120 s, `down` at 121 s; only the call-time clock changed."""

    async def scenario() -> tuple[HealthReport, HealthReport]:
        clock = ManualClock(START)
        await write_heartbeat(migrated_db, clock)
        clock.advance(STALE_AFTER)
        at_limit = await check(migrated_db, clock)
        clock.advance(timedelta(seconds=1))
        return at_limit, await check(migrated_db, clock)

    at_limit, stale = asyncio.run(scenario())
    assert (at_limit.status, at_limit.http_code) == (Status.OK, 200)
    assert (stale.status, stale.http_code, stale.public()) == (Status.DOWN, 503, {"status": "down"})
    assert stale.detail["components"]["worker"]["status"] == "down"
    assert stale.detail["components"]["worker"]["heartbeat_age_s"] == 121
    assert stale.detail["components"]["database"]["status"] == "ok"


@pytest.mark.spec("T-OPS-02")
def test_missing_heartbeat_down(migrated_db: str) -> None:
    report = asyncio.run(check(migrated_db, ManualClock(START)))
    assert (report.status, report.http_code) == (Status.DOWN, 503)
    assert report.detail["components"]["worker"] == {"status": "down", "heartbeat_at": None, "heartbeat_age_s": None}


@pytest.mark.spec("T-OPS-02")
def test_unreadable_heartbeat_down(migrated_db: str) -> None:
    async def read(db: Database) -> StateSnapshot:
        return StateSnapshot(schema_revision="0001", heartbeat={"at": "yesterday"})

    report = asyncio.run(check(migrated_db, ManualClock(START), reader=read))
    assert report.status is Status.DOWN
    assert report.detail["components"]["worker"]["status"] == "down"


@pytest.mark.spec("T-OPS-02")
@pytest.mark.parametrize(
    ("at", "started_at"),
    [
        ("2026-09-27T08:00:00", "2026-09-27T08:00:00+00:00"),
        ("2026-09-27T08:00:00+00:00", "2026-09-27T08:00:00"),
    ],
    ids=["naive-at", "naive-started-at"],
)
def test_heartbeat_without_timezone_down(migrated_db: str, at: str, started_at: str) -> None:
    """A timestamp without timezone cannot be compared with the `Clock`: `down` (503), never a 500."""

    async def read(db: Database) -> StateSnapshot:
        heartbeat = {"at": at, "started_at": started_at, "version": "w-1"}
        return StateSnapshot(schema_revision="0001", heartbeat=heartbeat)

    report = asyncio.run(check(migrated_db, ManualClock(START), reader=read))
    assert (report.status, report.http_code, report.public()) == (Status.DOWN, 503, {"status": "down"})
    assert report.detail["components"]["worker"] == {"status": "down", "heartbeat_at": None, "heartbeat_age_s": None}
    assert report.detail["components"]["database"]["status"] == "ok"


@pytest.mark.spec("T-OPS-03")
def test_unreachable_database_down(migrated_db: str) -> None:
    """SQLite error on open, injected: it is what the driver raises when the file is unreachable."""

    async def read(db: Database) -> StateSnapshot:
        raise OperationalError(
            "SELECT version_num FROM alembic_version", {}, sqlite3.OperationalError("unable to open database file")
        )

    report = asyncio.run(check(migrated_db, ManualClock(START), reader=read))
    assert (report.status, report.http_code, report.public()) == (Status.DOWN, 503, {"status": "down"})
    assert report.detail["components"]["database"] == {"status": "down"}


@pytest.mark.spec("T-OPS-03")
def test_failed_read_down(migrated_db: str) -> None:
    async def read(db: Database) -> StateSnapshot:
        raise OSError("disk I/O error")

    report = asyncio.run(check(migrated_db, ManualClock(START), reader=read))
    assert (report.status, report.http_code) == (Status.DOWN, 503)


@pytest.mark.spec("T-OPS-03")
def test_read_beyond_the_timeout_down(migrated_db: str) -> None:
    """A read that never yields back; timeout injected at 0 so nothing is awaited."""

    async def read(db: Database) -> StateSnapshot:
        await asyncio.Event().wait()
        raise AssertionError("unreachable")

    report = asyncio.run(check(migrated_db, ManualClock(START), reader=read, read_timeout=0))
    assert (report.status, report.http_code) == (Status.DOWN, 503)
    assert report.detail["components"]["database"] == {"status": "down"}


@pytest.mark.spec("T-OPS-03")
def test_read_timeout_of_2_s_by_default(migrated_db: str) -> None:
    assert READ_TIMEOUT == 2.0
    checker = HealthChecker(
        Database(create_engine(migrated_db), ManualClock(START)),
        ManualClock(START),
        db_path=migrated_db,
        heartbeat_stale_after=STALE_AFTER,
        version="v",
        started_at=START,
    )
    assert checker.read_timeout == 2.0
    asyncio.run(checker.db.dispose())
