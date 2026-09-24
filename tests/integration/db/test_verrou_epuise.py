"""`busy_timeout` épuisé : retry borné, compteur `db_locked`, aucune écriture partielle (II §8.6, T-DB-06)."""

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


async def _deux_insertions(session: Any) -> None:
    await session.execute(text("INSERT INTO probe (writer, n) VALUES ('app', 1)"))
    await session.execute(text("INSERT INTO probe (writer, n) VALUES ('app', 2)"))


def _compter(db_path: str) -> int:
    conn = sqlite3.connect(db_path)
    try:
        return int(conn.execute("SELECT count(*) FROM probe").fetchone()[0])
    finally:
        conn.close()


def test_retry_borne_compteur_et_aucune_ecriture_partielle(db_path: str) -> None:
    clock = ManualClock()
    autre = sqlite3.connect(db_path, isolation_level=None)  # l'autre processus tient le verrou d'écriture
    autre.execute("BEGIN IMMEDIATE")

    async def scenario() -> None:
        db = Database(create_engine(db_path, busy_timeout_ms=50), clock)
        try:
            with pytest.raises(DatabaseLockedError):
                await db.run_write(_deux_insertions, attempts=3)
            assert db.db_locked.total == 3
            assert db.db_locked.count_in_window() == 3

            autre.execute("ROLLBACK")  # le verrou est libéré : l'écriture passe du premier coup
            await db.run_write(_deux_insertions, attempts=3)
            assert db.db_locked.total == 3

            clock.advance(timedelta(hours=1, seconds=1))
            assert db.db_locked.count_in_window() == 0  # fenêtre d'une heure (VII §39.4)
            assert db.db_locked.total == 3
        finally:
            await db.dispose()

    try:
        assert _compter(db_path) == 0
        asyncio.run(scenario())
    finally:
        autre.close()
    assert _compter(db_path) == 2  # seule la tentative réussie a écrit, en entier


def test_une_erreur_autre_que_le_verrou_n_est_pas_rejouee(db_path: str) -> None:
    async def scenario() -> None:
        db = Database(create_engine(db_path), ManualClock())
        appels = 0

        async def invalide(session: Any) -> None:
            nonlocal appels
            appels += 1
            await session.execute(text("INSERT INTO table_absente VALUES (1)"))

        try:
            with pytest.raises(Exception, match="table_absente"):
                await db.run_write(invalide, attempts=3)
            assert appels == 1
            assert db.db_locked.total == 0
        finally:
            await db.dispose()

    asyncio.run(scenario())
