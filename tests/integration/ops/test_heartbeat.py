"""Heartbeat du worker (VII §36.6, §39.3)."""

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


async def tour(clock: SteppedClock, heartbeat: Heartbeat, tache: asyncio.Task[None]) -> None:
    """Fait jouer un tour de la boucle : attend qu'elle dorme, avance d'un intervalle, attend la fin du tour."""
    while clock.sleepers == 0 and not tache.done():
        await asyncio.sleep(0)
    clock.advance(heartbeat.interval)
    while clock.sleepers == 0 and not tache.done():  # tour fini : la boucle se rendort, ou la tâche est morte
        await asyncio.sleep(0.01)


@pytest.mark.spec("T-OPS-08:heartbeat")
def test_verrou_prolonge_ne_tue_pas_la_tache_et_le_heartbeat_suivant_est_ecrit(base_migree: str) -> None:
    """Verrou d'écriture tenu par un autre client pendant un tour : tour sauté, tâche vivante, tour suivant écrit."""

    async def scenario() -> tuple[bool, int, int, str]:
        clock = SteppedClock(DEBUT)
        db = Database(create_engine(base_migree, busy_timeout_ms=0), clock)
        heartbeat = Heartbeat(db, clock, timedelta(seconds=30), version="v")
        await heartbeat.beat()
        tache = asyncio.create_task(heartbeat.run())
        bloqueur = sqlite3.connect(base_migree, isolation_level=None)
        try:
            bloqueur.execute("BEGIN IMMEDIATE")
            await tour(clock, heartbeat, tache)
            bloqueur.execute("ROLLBACK")
            verrous = db.db_locked.total
            await tour(clock, heartbeat, tache)
            vivante = not tache.done()
        finally:
            bloqueur.close()
            tache.cancel()
            await asyncio.gather(tache, return_exceptions=True)
            await db.dispose()
        return vivante, verrous, heartbeat.beats, str(lire_heartbeat(base_migree)[0]["at"])

    with capture_logs() as logs:
        vivante, verrous, beats, at = asyncio.run(scenario())
    assert vivante
    assert verrous == 3  # les trois tentatives de run_write, comptées par db_locked
    assert beats == 2  # celui du boot et celui du troisième tour ; le deuxième a été sauté
    assert at == "2026-09-27T08:01:00+00:00"
    sautes = [e for e in logs if e["event"] == "worker.heartbeat.skipped"]
    assert [e["log_level"] for e in sautes] == ["warning"]
    assert "database is locked" in sautes[0]["reason"]


@pytest.mark.spec("T-OPS-08:heartbeat")
def test_autre_exception_tue_toujours_la_tache(base_migree: str) -> None:
    async def scenario() -> BaseException | None:
        clock = SteppedClock(DEBUT)
        db = Database(create_engine(base_migree), clock)
        heartbeat = Heartbeat(db, clock, timedelta(seconds=30), version="v")
        tache = asyncio.create_task(heartbeat.run())
        try:
            conn = sqlite3.connect(base_migree)
            conn.execute("DROP TABLE system_state")
            conn.commit()
            conn.close()
            await tour(clock, heartbeat, tache)
            await asyncio.wait({tache}, timeout=5)
            return tache.exception()
        finally:
            tache.cancel()
            await asyncio.gather(tache, return_exceptions=True)
            await db.dispose()

    with capture_logs() as logs:
        erreur: Any = asyncio.run(scenario())
    assert erreur is not None
    assert "no such table" in str(erreur)
    assert [e for e in logs if e["event"] == "worker.heartbeat.skipped"] == []
