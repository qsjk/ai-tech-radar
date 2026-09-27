"""Heartbeat du worker (VII §36.6, §39.3)."""

import asyncio
import json
import os
import sqlite3
from datetime import UTC, datetime, timedelta

import pytest

from app.db.engine import create_engine
from app.db.session import Database
from app.ops.heartbeat import HEARTBEAT_KEY, Heartbeat
from tests.fakes.clock import SteppedClock

DEBUT = datetime(2026, 9, 27, 8, 0, tzinfo=UTC)


def lire_heartbeat(db_path: str) -> tuple[dict[str, object], str]:
    conn = sqlite3.connect(db_path)
    try:
        value, updated_at = conn.execute(
            "SELECT value, updated_at FROM system_state WHERE key = ?", (HEARTBEAT_KEY,)
        ).fetchone()
    finally:
        conn.close()
    return json.loads(value), updated_at


@pytest.mark.spec("T-OPS-10:heartbeat")
def test_beat_ecrit_la_valeur_attendue(base_migree: str) -> None:
    async def scenario() -> None:
        clock = SteppedClock(DEBUT)
        db = Database(create_engine(base_migree), clock)
        try:
            heartbeat = Heartbeat(db, clock, timedelta(seconds=30), version="abc1234")
            await heartbeat.beat()
        finally:
            await db.dispose()

    asyncio.run(scenario())
    value, updated_at = lire_heartbeat(base_migree)
    assert value == {
        "at": "2026-09-27T08:00:00+00:00",
        "started_at": "2026-09-27T08:00:00+00:00",
        "version": "abc1234",
        "pid": os.getpid(),
    }
    assert updated_at == "2026-09-27T08:00:00.000000+00:00"


@pytest.mark.spec("T-OPS-10:heartbeat")
def test_run_ecrit_un_heartbeat_par_intervalle(base_migree: str) -> None:
    async def scenario() -> list[str]:
        clock = SteppedClock(DEBUT)
        db = Database(create_engine(base_migree), clock)
        heartbeat = Heartbeat(db, clock, timedelta(seconds=30), version="v")
        vus = []
        tache = asyncio.create_task(heartbeat.run())
        try:
            for _ in range(3):
                while clock.sleepers == 0:  # la boucle attend son prochain tour
                    await asyncio.sleep(0)
                clock.advance(timedelta(seconds=30))
                while heartbeat.beats < len(vus) + 1:
                    await asyncio.sleep(0.01)
                vus.append(str(lire_heartbeat(base_migree)[0]["at"]))
        finally:
            tache.cancel()
            await asyncio.gather(tache, return_exceptions=True)
            await db.dispose()
        return vus

    assert asyncio.run(scenario()) == [
        "2026-09-27T08:00:30+00:00",
        "2026-09-27T08:01:00+00:00",
        "2026-09-27T08:01:30+00:00",
    ]
