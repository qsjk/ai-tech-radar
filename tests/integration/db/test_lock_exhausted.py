"""`busy_timeout` exhausted: bounded retry, `db_locked` counter, no partial write (II §8.6, T-DB-06)."""

import asyncio
import sqlite3
from datetime import timedelta
from typing import Any

import pytest
from sqlalchemy import text

from app.db.engine import create_engine
from app.db.session import Database, DatabaseLockedError
from tests.fakes.clock import ManualClock

pytestmark = pytest.mark.spec("T-DB-06")


async def _two_inserts(session: Any) -> None:
    await session.execute(text("INSERT INTO probe (writer, n) VALUES ('app', 1)"))
    await session.execute(text("INSERT INTO probe (writer, n) VALUES ('app', 2)"))


def _count(db_path: str) -> int:
    conn = sqlite3.connect(db_path)
    try:
        return int(conn.execute("SELECT count(*) FROM probe").fetchone()[0])
    finally:
        conn.close()


def test_bounded_retry_counter_and_no_partial_write(db_path: str) -> None:
    clock = ManualClock()
    other = sqlite3.connect(db_path, isolation_level=None)  # the other process holds the write lock
    other.execute("BEGIN IMMEDIATE")

    async def scenario() -> None:
        db = Database(create_engine(db_path, busy_timeout_ms=50), clock)
        try:
            with pytest.raises(DatabaseLockedError):
                await db.run_write(_two_inserts, attempts=3)
            assert db.db_locked.total == 3
            assert db.db_locked.count_in_window() == 3

            other.execute("ROLLBACK")  # the lock is released: the write succeeds on the first try
            await db.run_write(_two_inserts, attempts=3)
            assert db.db_locked.total == 3

            clock.advance(timedelta(hours=1, seconds=1))
            assert db.db_locked.count_in_window() == 0  # one-hour window (VII §39.4)
            assert db.db_locked.total == 3
        finally:
            await db.dispose()

    try:
        assert _count(db_path) == 0
        asyncio.run(scenario())
    finally:
        other.close()
    assert _count(db_path) == 2  # only the successful attempt wrote, in full


def test_an_error_other_than_the_lock_is_not_replayed(db_path: str) -> None:
    async def scenario() -> None:
        db = Database(create_engine(db_path), ManualClock())
        calls = 0

        async def invalid(session: Any) -> None:
            nonlocal calls
            calls += 1
            await session.execute(text("INSERT INTO missing_table VALUES (1)"))

        try:
            with pytest.raises(Exception, match="missing_table"):
                await db.run_write(invalid, attempts=3)
            assert calls == 1
            assert db.db_locked.total == 0
        finally:
            await db.dispose()

    asyncio.run(scenario())
