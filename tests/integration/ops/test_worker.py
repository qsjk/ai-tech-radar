"""In-process worker (VII §36.6): boot sequence, fail-fast supervision, stop, with a stepped clock.

Signals are not installed (`handle_signals=False`) and the watchdog action is a spy: the pytest process is never
stopped. Process-level behaviours are in `test_worker_process.py`.
"""

import asyncio
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine
from structlog.testing import capture_logs

from app.core.config import WorkerSettings
from app.db.prerequisites import PrerequisiteError
from app.ops.heartbeat import HEARTBEAT_KEY
from app.worker import Worker
from tests.fakes.clock import SteppedClock

START = datetime(2026, 9, 27, 8, 0, tzinfo=UTC)


def settings(db_path: str) -> WorkerSettings:
    return WorkerSettings(
        radar_db_path=db_path,
        dashboard_url="https://radar.example.com",
        http_contact="https://example.com/contact",
        radar_version="abc1234",
    )


def heartbeats(db_path: str) -> int:
    conn = sqlite3.connect(db_path)
    try:
        return int(conn.execute("SELECT count(*) FROM system_state WHERE key = ?", (HEARTBEAT_KEY,)).fetchone()[0])
    except sqlite3.OperationalError:
        return 0
    finally:
        conn.close()


def events(logs: list[dict[str, Any]]) -> list[str]:
    return [str(entry["event"]) for entry in logs]


class Spy:
    def __init__(self) -> None:
        self.calls = 0

    def __call__(self) -> None:
        self.calls += 1


def worker(db_path: str, config_dir: Path, clock: SteppedClock, **options: Any) -> Worker:
    return Worker(
        settings(db_path),
        clock=clock,
        config_dir=config_dir,
        on_watchdog_timeout=options.pop("on_watchdog_timeout", Spy()),
        handle_signals=False,
        **options,
    )


async def started(task: asyncio.Task[int], logs: list[dict[str, Any]]) -> None:
    """Wait for `worker.started`, without sleep: the loop yields until the log (or until the task ends)."""
    while "worker.started" not in events(logs) and not task.done():
        await asyncio.sleep(0.01)


@pytest.mark.spec("T-OPS-10:verifications")
@pytest.mark.spec("T-OPS-10:heartbeat")
def test_order_checks_then_heartbeat_then_start(migrated_db: str, config_dir: Path) -> None:
    async def scenario() -> int:
        w = worker(migrated_db, config_dir, SteppedClock(START))
        task = asyncio.create_task(w.run())
        await started(task, logs)
        assert heartbeats(migrated_db) == 1
        w.request_stop()
        return await task

    with capture_logs() as logs:
        assert asyncio.run(scenario()) == 0
    assert events(logs) == [
        "worker.boot.checked",
        "worker.heartbeat.started",
        "worker.started",
        "worker.stop.requested",
        "worker.stopped",
    ]


@pytest.mark.spec("T-OPS-09")
def test_heartbeat_written_before_the_end_of_boot(migrated_db: str, config_dir: Path) -> None:
    """The heartbeat is in the database before `worker.started`: before any later step (models included, upcoming)."""

    async def scenario() -> tuple[int, int]:
        w = worker(migrated_db, config_dir, SteppedClock(START))
        task = asyncio.create_task(w.run())
        seen_at_start = -1
        while not task.done():
            if "worker.heartbeat.started" in events(logs) and seen_at_start < 0:
                seen_at_start = heartbeats(migrated_db)
            if "worker.started" in events(logs):
                break
            await asyncio.sleep(0.01)
        w.request_stop()
        return seen_at_start, await task

    with capture_logs() as logs:
        assert asyncio.run(scenario()) == (1, 0)


@pytest.mark.spec("T-OPS-10:verifications")
@pytest.mark.spec("T-DB-01")
def test_missing_prerequisite_refused_without_heartbeat(migrated_db: str, config_dir: Path) -> None:
    async def missing_prerequisite(engine: AsyncEngine) -> None:
        raise PrerequisiteError("SQLite 3.34.1 < 3.35 required")

    w = worker(migrated_db, config_dir, SteppedClock(START), prerequisites=missing_prerequisite)
    with capture_logs() as logs:
        assert asyncio.run(w.run()) == 1
    assert [(e["event"], e["log_level"], e["reason"]) for e in logs] == [
        ("worker.refused", "critical", "SQLite 3.34.1 < 3.35 required")
    ]
    assert heartbeats(migrated_db) == 0


@pytest.mark.spec("T-OPS-10:verifications")
@pytest.mark.spec("T-DB-02")
def test_unmigrated_database_refused_without_heartbeat(tmp_path: Path, config_dir: Path) -> None:
    db_path = str(tmp_path / "empty.db")
    sqlite3.connect(db_path).close()
    with capture_logs() as logs:
        assert asyncio.run(worker(db_path, config_dir, SteppedClock(START)).run()) == 1
    assert [(e["event"], e["log_level"], e["error_class"]) for e in logs] == [
        ("worker.refused", "critical", "SchemaRevisionError")
    ]
    assert heartbeats(db_path) == 0


@pytest.mark.spec("T-OPS-10:verifications")
def test_invalid_configuration_refused_without_heartbeat(migrated_db: str, config_dir: Path) -> None:
    (config_dir / "topics.yaml").write_text("topics: [{slug: llm}]\n", encoding="utf-8")
    with capture_logs() as logs:
        assert asyncio.run(worker(migrated_db, config_dir, SteppedClock(START)).run()) == 2
    assert [(e["event"], e["log_level"]) for e in logs] == [("worker.refused", "critical")]
    assert logs[0]["issues"]
    assert heartbeats(migrated_db) == 0


@pytest.mark.spec("T-OPS-08:heartbeat")
def test_heartbeat_exception_logs_critical_and_exits_non_zero(migrated_db: str, config_dir: Path) -> None:
    async def scenario() -> int:
        clock = SteppedClock(START)
        w = worker(migrated_db, config_dir, clock)
        task = asyncio.create_task(w.run())
        await started(task, logs)
        conn = sqlite3.connect(migrated_db)
        conn.execute("DROP TABLE system_state")
        conn.commit()
        conn.close()
        while clock.sleepers < 2:  # heartbeat and watchdog refresh waiting
            await asyncio.sleep(0.01)
        clock.advance(timedelta(seconds=1))
        return await task

    with capture_logs() as logs:
        assert asyncio.run(scenario()) == 1
    failures = [e for e in logs if e["event"] == "worker.task.failed"]
    assert [(e["log_level"], e["task"]) for e in failures] == [("critical", "heartbeat")]
    assert "no such table" in str(failures[0]["exc_info"])
    assert events(logs)[-1] == "worker.stopped"


@pytest.mark.spec("T-OPS-11:arret")
def test_stop_request_cancels_the_tasks_and_returns_0(migrated_db: str, config_dir: Path) -> None:
    spy = Spy()

    async def scenario() -> tuple[int, int]:
        w = worker(migrated_db, config_dir, SteppedClock(START), on_watchdog_timeout=spy)
        task = asyncio.create_task(w.run())
        await started(task, logs)
        w.request_stop()
        code = await task
        remaining = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        return code, len(remaining)

    with capture_logs() as logs:
        assert asyncio.run(scenario()) == (0, 0)
    assert [e for e in logs if e["event"] == "worker.stopped"][0]["code"] == 0
    assert spy.calls == 0
