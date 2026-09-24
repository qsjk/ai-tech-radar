"""PRAGMA de chaque connexion et mode des transactions (III §10.2, §10.3)."""

import asyncio

import pytest
from sqlalchemy import text

from app.db.engine import READ_ONLY_OPTION, create_engine
from app.db.session import Database
from tests.fakes.clock import ManualClock
from tests.integration.db.conftest import raw_write_lock_free


@pytest.mark.spec("T-DB-03")
def test_chaque_nouvelle_connexion_applique_les_pragma(db_path: str) -> None:
    async def scenario() -> list[tuple[object, ...]]:
        engine = create_engine(db_path, busy_timeout_ms=1234, journal_size_limit=4_194_304)
        lus = []
        try:
            # Deux connexions ouvertes en même temps : le pool en crée deux, chacune passe par l'écouteur `connect`.
            # En lecture seule, pour que les deux transactions implicites ne se disputent pas le verrou d'écriture.
            lecture = engine.execution_options(**{READ_ONLY_OPTION: True})
            async with lecture.connect() as c1, lecture.connect() as c2:
                for conn in (c1, c2):
                    valeurs = []
                    for name in ("journal_mode", "synchronous", "busy_timeout", "foreign_keys", "journal_size_limit"):
                        valeurs.append((await conn.execute(text(f"PRAGMA {name}"))).scalar_one())
                    lus.append(tuple(valeurs))
        finally:
            await engine.dispose()
        return lus

    for valeurs in asyncio.run(scenario()):
        assert valeurs == ("wal", 1, 1234, 1, 4_194_304)


@pytest.mark.spec("T-DB-03")
def test_valeurs_par_defaut_des_pragma(db_path: str) -> None:
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
def test_write_session_prend_le_verrou_des_le_begin(db_path: str) -> None:
    async def scenario() -> bool:
        db = Database(create_engine(db_path), ManualClock())
        try:
            async with db.write_session() as session, session.begin():
                await session.execute(text("SELECT count(*) FROM probe"))  # aucune écriture
                return raw_write_lock_free(db_path)
        finally:
            await db.dispose()

    assert asyncio.run(scenario()) is False


@pytest.mark.spec("T-DB-05")
def test_read_session_ne_prend_pas_le_verrou(db_path: str) -> None:
    async def scenario() -> bool:
        db = Database(create_engine(db_path), ManualClock())
        try:
            async with db.read_session() as session, session.begin():
                await session.execute(text("SELECT count(*) FROM probe"))
                return raw_write_lock_free(db_path)
        finally:
            await db.dispose()

    assert asyncio.run(scenario()) is True
