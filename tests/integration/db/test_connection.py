"""PRAGMAs of every connection and transaction mode (III §10.2, §10.3)."""

import asyncio

import pytest
from sqlalchemy import text

from app.db.engine import READ_ONLY_OPTION, create_engine
from app.db.session import Database
from tests.fakes.clock import ManualClock
from tests.integration.db.conftest import raw_write_lock_free


@pytest.mark.spec("T-DB-03")
def test_every_new_connection_applies_the_pragmas(db_path: str) -> None:
    async def scenario() -> list[tuple[object, ...]]:
        engine = create_engine(db_path, busy_timeout_ms=1234, journal_size_limit=4_194_304)
        read = []
        try:
            # Two connections open at the same time: the pool creates two, each goes through the `connect` listener.
            # Read-only, so that the two implicit transactions do not compete for the write lock.
            read_only = engine.execution_options(**{READ_ONLY_OPTION: True})
            async with read_only.connect() as c1, read_only.connect() as c2:
                for conn in (c1, c2):
                    values = []
                    for name in ("journal_mode", "synchronous", "busy_timeout", "foreign_keys", "journal_size_limit"):
                        values.append((await conn.execute(text(f"PRAGMA {name}"))).scalar_one())
                    read.append(tuple(values))
        finally:
            await engine.dispose()
        return read

    for values in asyncio.run(scenario()):
        assert values == ("wal", 1, 1234, 1, 4_194_304)


@pytest.mark.spec("T-DB-03")
def test_default_pragma_values(db_path: str) -> None:
    async def scenario() -> tuple[object, object]:
        engine = create_engine(db_path)
        try:
            async with engine.connect() as conn:
                busy = (await conn.execute(text("PRAGMA busy_timeout"))).scalar_one()
                limit = (await conn.execute(text("PRAGMA journal_size_limit"))).scalar_one()
        finally:
            await engine.dispose()
        return busy, limit

    assert asyncio.run(scenario()) == (5000, 67_108_864)


@pytest.mark.spec("T-DB-04")
def test_write_session_takes_the_lock_at_begin(db_path: str) -> None:
    async def scenario() -> bool:
        db = Database(create_engine(db_path), ManualClock())
        try:
            async with db.write_session() as session, session.begin():
                await session.execute(text("SELECT count(*) FROM probe"))  # no write
                return raw_write_lock_free(db_path)
        finally:
            await db.dispose()

    assert asyncio.run(scenario()) is False


@pytest.mark.spec("T-DB-05")
def test_read_session_does_not_take_the_lock(db_path: str) -> None:
    async def scenario() -> bool:
        db = Database(create_engine(db_path), ManualClock())
        try:
            async with db.read_session() as session, session.begin():
                await session.execute(text("SELECT count(*) FROM probe"))
                return raw_write_lock_free(db_path)
        finally:
            await db.dispose()

    assert asyncio.run(scenario()) is True
