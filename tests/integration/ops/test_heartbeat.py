"""Worker heartbeat (VII §36.6, §39.3)."""

import asyncio
import json
import os
import sqlite3
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from structlog.testing import capture_logs

from app.db.engine import create_engine
from app.db.session import Database
from app.ops.heartbeat import HEARTBEAT_KEY, Heartbeat
from tests.fakes.clock import SteppedClock

START = datetime(2026, 9, 27, 8, 0, tzinfo=UTC)


def read_heartbeat(db_path: str) -> tuple[dict[str, object], str]:
    conn = sqlite3.connect(db_path)
    try:
        value, updated_at = conn.execute(
            "SELECT value, updated_at FROM system_state WHERE key = ?", (HEARTBEAT_KEY,)
        ).fetchone()
    finally:
        conn.close()
    return json.loads(value), updated_at


@pytest.mark.spec("T-OPS-10:heartbeat")
def test_beat_writes_the_expected_value(migrated_db: str) -> None:
    async def scenario() -> None:
        clock = SteppedClock(START)
        db = Database(create_engine(migrated_db), clock)
        try:
            heartbeat = Heartbeat(db, clock, timedelta(seconds=30), version="abc1234")
            await heartbeat.beat()
        finally:
            await db.dispose()

    asyncio.run(scenario())
    value, updated_at = read_heartbeat(migrated_db)
    assert value == {
        "at": "2026-09-27T08:00:00+00:00",
        "started_at": "2026-09-27T08:00:00+00:00",
        "version": "abc1234",
        "pid": os.getpid(),
    }
    assert updated_at == "2026-09-27T08:00:00.000000+00:00"


@pytest.mark.spec("T-OPS-10:heartbeat")
def test_run_writes_one_heartbeat_per_interval(migrated_db: str) -> None:
    async def scenario() -> list[str]:
        clock = SteppedClock(START)
        db = Database(create_engine(migrated_db), clock)
        heartbeat = Heartbeat(db, clock, timedelta(seconds=30), version="v")
        seen = []
        task = asyncio.create_task(heartbeat.run())
        try:
            for _ in range(3):
                while clock.sleepers == 0:  # the loop waits for its next round
                    await asyncio.sleep(0)
                clock.advance(timedelta(seconds=30))
                while heartbeat.beats < len(seen) + 1:
                    await asyncio.sleep(0.01)
                seen.append(str(read_heartbeat(migrated_db)[0]["at"]))
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            await db.dispose()
        return seen

    assert asyncio.run(scenario()) == [
        "2026-09-27T08:00:30+00:00",
        "2026-09-27T08:01:00+00:00",
        "2026-09-27T08:01:30+00:00",
    ]


async def play_round(clock: SteppedClock, heartbeat: Heartbeat, task: asyncio.Task[None]) -> None:
    """Play one loop round: wait until it sleeps, advance one interval, wait for the round to end."""
    while clock.sleepers == 0 and not task.done():
        await asyncio.sleep(0)
    clock.advance(heartbeat.interval)
    while clock.sleepers == 0 and not task.done():  # round over: the loop sleeps again, or the task died
        await asyncio.sleep(0.01)


@pytest.mark.spec("T-OPS-08:heartbeat")
def test_prolonged_lock_does_not_kill_the_task_and_the_next_heartbeat_is_written(migrated_db: str) -> None:
    """Write lock held by another client during one round: round skipped, task alive, next round written."""

    async def scenario() -> tuple[bool, int, int, str]:
        clock = SteppedClock(START)
        db = Database(create_engine(migrated_db, busy_timeout_ms=0), clock)
        heartbeat = Heartbeat(db, clock, timedelta(seconds=30), version="v")
        await heartbeat.beat()
        task = asyncio.create_task(heartbeat.run())
        blocker = sqlite3.connect(migrated_db, isolation_level=None)
        try:
            blocker.execute("BEGIN IMMEDIATE")
            await play_round(clock, heartbeat, task)
            blocker.execute("ROLLBACK")
            locks = db.db_locked.total
            await play_round(clock, heartbeat, task)
            alive = not task.done()
        finally:
            blocker.close()
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            await db.dispose()
        return alive, locks, heartbeat.beats, str(read_heartbeat(migrated_db)[0]["at"])

    with capture_logs() as logs:
        alive, locks, beats, at = asyncio.run(scenario())
    assert alive
    assert locks == 3  # the three run_write attempts, counted by db_locked
    assert beats == 2  # the boot one and the third-round one; the second was skipped
    assert at == "2026-09-27T08:01:00+00:00"
    skipped = [e for e in logs if e["event"] == "worker.heartbeat.skipped"]
    assert [e["log_level"] for e in skipped] == ["warning"]
    assert "database is locked" in skipped[0]["reason"]


@pytest.mark.spec("T-OPS-08:heartbeat")
def test_any_other_exception_still_kills_the_task(migrated_db: str) -> None:
    async def scenario() -> BaseException | None:
        clock = SteppedClock(START)
        db = Database(create_engine(migrated_db), clock)
        heartbeat = Heartbeat(db, clock, timedelta(seconds=30), version="v")
        task = asyncio.create_task(heartbeat.run())
        try:
            conn = sqlite3.connect(migrated_db)
            conn.execute("DROP TABLE system_state")
            conn.commit()
            conn.close()
            await play_round(clock, heartbeat, task)
            await asyncio.wait({task}, timeout=5)
            return task.exception()
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            await db.dispose()

    with capture_logs() as logs:
        error: Any = asyncio.run(scenario())
    assert error is not None
    assert "no such table" in str(error)
    assert [e for e in logs if e["event"] == "worker.heartbeat.skipped"] == []
