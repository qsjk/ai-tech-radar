"""Deux processus sur la même base (T-DB-04, T-DB-05). Synchronisation par barrière et événements, sans `sleep`."""

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
TIMEOUT = 30  # secondes, garde-fou des attentes inter-processus


def _ecrire_en_boucle(db_path: str, nom: str, barriere: Barrier, erreurs: Any) -> None:
    """Processus écrivain : `TRANSACTIONS` transactions `BEGIN IMMEDIATE`, lancées en même temps que l'autre."""

    async def run() -> None:
        db = Database(create_engine(db_path, busy_timeout_ms=10_000), ManualClock())
        try:
            barriere.wait(TIMEOUT)
            for n in range(TRANSACTIONS):

                async def unite(session: Any, n: int = n) -> None:
                    await session.execute(text("INSERT INTO probe (writer, n) VALUES (:w, :n)"), {"w": nom, "n": n})

                await db.run_write(unite, attempts=1)
        finally:
            await db.dispose()

    try:
        asyncio.run(run())
    except Exception as error:  # remonté au processus du test
        erreurs.put(f"{nom}: {error!r}")


@pytest.mark.spec("T-DB-04")
def test_deux_processus_ecrivent_en_concurrence_sans_echec_immediat(db_path: str) -> None:
    ctx = mp.get_context("spawn")
    barriere = ctx.Barrier(2)
    erreurs = ctx.Queue()
    processus = [
        ctx.Process(target=_ecrire_en_boucle, args=(db_path, nom, barriere, erreurs)) for nom in ("app", "worker")
    ]
    for p in processus:
        p.start()
    for p in processus:
        p.join(TIMEOUT)
    assert all(p.exitcode == 0 for p in processus)
    assert erreurs.empty(), erreurs.get()

    async def compter() -> int:
        db = Database(create_engine(db_path), ManualClock())
        try:
            async with db.read_session() as session:
                return int((await session.execute(text("SELECT count(*) FROM probe"))).scalar_one())
        finally:
            await db.dispose()

    assert asyncio.run(compter()) == 2 * TRANSACTIONS


def _tenir_une_ecriture(db_path: str, tient: Event, lecture_faite: Event) -> None:
    """Processus écrivain : ouvre une écriture, insère sans valider, attend la fin de la lecture, puis annule."""

    async def run() -> None:
        db = Database(create_engine(db_path), ManualClock())
        try:
            async with db.write_session() as session, session.begin():
                await session.execute(text("INSERT INTO probe (writer, n) VALUES ('worker', 1)"))
                tient.set()
                lecture_faite.wait(TIMEOUT)
                await session.rollback()
        finally:
            await db.dispose()

    asyncio.run(run())


@pytest.mark.spec("T-DB-05")
def test_lecture_non_bloquee_par_une_ecriture_de_l_autre_processus(db_path: str) -> None:
    ctx = mp.get_context("spawn")
    tient, lecture_faite = ctx.Event(), ctx.Event()
    ecrivain = ctx.Process(target=_tenir_une_ecriture, args=(db_path, tient, lecture_faite))
    ecrivain.start()
    try:
        assert tient.wait(TIMEOUT)

        async def lire() -> int:
            # busy_timeout court : une lecture bloquée échouerait au lieu d'attendre.
            db = Database(create_engine(db_path, busy_timeout_ms=100), ManualClock())
            try:
                async with db.read_session() as session, session.begin():
                    return int((await session.execute(text("SELECT count(*) FROM probe"))).scalar_one())
            finally:
                await db.dispose()

        assert asyncio.run(lire()) == 0  # l'écriture non validée n'est pas visible
    finally:
        lecture_faite.set()
        ecrivain.join(TIMEOUT)
    assert ecrivain.exitcode == 0
