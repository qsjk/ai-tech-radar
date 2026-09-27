"""Two processes on the same database (T-DB-04, T-DB-05). Synchronized by barrier and events, without `sleep`."""

import asyncio
import multiprocessing as mp
from multiprocessing.synchronize import Barrier, Event
from typing import Any

import pytest
from sqlalchemy import text

from app.db.engine import create_engine
from app.db.session import Database
from tests.fakes.clock import ManualClock

TRANSACTIONS = 40
TIMEOUT = 30  # seconds, safety bound of the inter-process waits


def _write_in_loop(db_path: str, name: str, barrier: Barrier, errors: Any) -> None:
    """Writer process: `TRANSACTIONS` `BEGIN IMMEDIATE` transactions, started at the same time as the other one."""

    async def run() -> None:
        db = Database(create_engine(db_path, busy_timeout_ms=10_000), ManualClock())
        try:
            barrier.wait(TIMEOUT)
            for n in range(TRANSACTIONS):

                async def unit(session: Any, n: int = n) -> None:
                    await session.execute(text("INSERT INTO probe (writer, n) VALUES (:w, :n)"), {"w": name, "n": n})

                await db.run_write(unit, attempts=1)
        finally:
            await db.dispose()

    try:
        asyncio.run(run())
    except Exception as error:  # reported to the test process
        errors.put(f"{name}: {error!r}")


@pytest.mark.spec("T-DB-04")
def test_two_processes_write_concurrently_without_immediate_failure(db_path: str) -> None:
    ctx = mp.get_context("spawn")
    barrier = ctx.Barrier(2)
    errors = ctx.Queue()
    processes = [
        ctx.Process(target=_write_in_loop, args=(db_path, name, barrier, errors)) for name in ("app", "worker")
    ]
    for p in processes:
        p.start()
    for p in processes:
        p.join(TIMEOUT)
    assert all(p.exitcode == 0 for p in processes)
    assert errors.empty(), errors.get()

    async def count() -> int:
        db = Database(create_engine(db_path), ManualClock())
        try:
            async with db.read_session() as session:
                return int((await session.execute(text("SELECT count(*) FROM probe"))).scalar_one())
        finally:
            await db.dispose()

    assert asyncio.run(count()) == 2 * TRANSACTIONS


def _hold_a_write(db_path: str, holding: Event, read_done: Event) -> None:
    """Writer process: opens a write, inserts without committing, waits for the read to finish, then rolls back."""

    async def run() -> None:
        db = Database(create_engine(db_path), ManualClock())
        try:
            async with db.write_session() as session, session.begin():
                await session.execute(text("INSERT INTO probe (writer, n) VALUES ('worker', 1)"))
                holding.set()
                read_done.wait(TIMEOUT)
                await session.rollback()
        finally:
            await db.dispose()

    asyncio.run(run())


@pytest.mark.spec("T-DB-05")
def test_read_not_blocked_by_a_write_of_the_other_process(db_path: str) -> None:
    ctx = mp.get_context("spawn")
    holding, read_done = ctx.Event(), ctx.Event()
    writer = ctx.Process(target=_hold_a_write, args=(db_path, holding, read_done))
    writer.start()
    try:
        assert holding.wait(TIMEOUT)

        async def read() -> int:
            # Short busy_timeout: a blocked read would fail instead of waiting.
            db = Database(create_engine(db_path, busy_timeout_ms=100), ManualClock())
            try:
                async with db.read_session() as session, session.begin():
                    return int((await session.execute(text("SELECT count(*) FROM probe"))).scalar_one())
            finally:
                await db.dispose()

        assert asyncio.run(read()) == 0  # the uncommitted write is not visible
    finally:
        read_done.set()
        writer.join(TIMEOUT)
    assert writer.exitcode == 0
