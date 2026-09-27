"""Module de santé (VII §40) : statut calculé à l'appel, âge du heartbeat par la `Clock`, lecture bornée à 2 s."""

import asyncio
import sqlite3
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.exc import OperationalError

from app.db.engine import create_engine
from app.db.session import Database
from app.ops.health import READ_TIMEOUT, HealthChecker, HealthReport, StateSnapshot, Status
from app.ops.heartbeat import Heartbeat
from tests.fakes.clock import ManualClock

DEBUT = datetime(2026, 9, 27, 8, 0, tzinfo=UTC)
PERIME_APRES = timedelta(seconds=120)


async def verifier(db_path: str, clock: ManualClock, **options: object) -> HealthReport:
    db = Database(create_engine(db_path), clock)
    try:
        checker = HealthChecker(
            db,
            clock,
            db_path=db_path,
            heartbeat_stale_after=PERIME_APRES,
            version="abc1234",
            started_at=DEBUT,
            **options,  # type: ignore[arg-type]
        )
        return await checker.check()
    finally:
        await db.dispose()


async def ecrire_heartbeat(db_path: str, clock: ManualClock) -> None:
    db = Database(create_engine(db_path), clock)
    try:
        await Heartbeat(db, clock, timedelta(seconds=30), version="w-1", pid=4242).beat()
    finally:
        await db.dispose()


@pytest.mark.spec("T-OPS-02")
def test_heartbeat_frais_ok_avec_le_detail(base_migree: str) -> None:
    async def scenario() -> HealthReport:
        clock = ManualClock(DEBUT)
        await ecrire_heartbeat(base_migree, clock)
        clock.advance(timedelta(seconds=12))
        return await verifier(base_migree, clock)

    rapport = asyncio.run(scenario())
    assert (rapport.status, rapport.http_code, rapport.public()) == (Status.OK, 200, {"status": "ok"})
    detail = rapport.detail
    assert detail["checked_at"] == "2026-09-27T08:00:12Z"
    assert detail["version"] == "abc1234"
    assert detail["conditions"] == []
    base, worker, app = (detail["components"][nom] for nom in ("database", "worker", "app"))
    assert base["status"] == "ok"
    assert base["schema_revision"] == "0001"
    assert base["db_bytes"] > 0
    assert base["wal_bytes"] >= 0
    assert worker == {
        "status": "ok",
        "heartbeat_at": "2026-09-27T08:00:00Z",
        "heartbeat_age_s": 12,
        "started_at": "2026-09-27T08:00:00Z",
        "version": "w-1",
    }
    assert app == {"started_at": "2026-09-27T08:00:00Z", "db_locked_1h": 0}


@pytest.mark.spec("T-OPS-02")
def test_age_calcule_au_moment_de_l_appel(base_migree: str) -> None:
    """Même heartbeat en base : `ok` à 120 s, `down` à 121 s ; seule l'horloge de l'appel a changé."""

    async def scenario() -> tuple[HealthReport, HealthReport]:
        clock = ManualClock(DEBUT)
        await ecrire_heartbeat(base_migree, clock)
        clock.advance(PERIME_APRES)
        a_la_limite = await verifier(base_migree, clock)
        clock.advance(timedelta(seconds=1))
        return a_la_limite, await verifier(base_migree, clock)

    a_la_limite, perime = asyncio.run(scenario())
    assert (a_la_limite.status, a_la_limite.http_code) == (Status.OK, 200)
    assert (perime.status, perime.http_code, perime.public()) == (Status.DOWN, 503, {"status": "down"})
    assert perime.detail["components"]["worker"]["status"] == "down"
    assert perime.detail["components"]["worker"]["heartbeat_age_s"] == 121
    assert perime.detail["components"]["database"]["status"] == "ok"


@pytest.mark.spec("T-OPS-02")
def test_heartbeat_absent_down(base_migree: str) -> None:
    rapport = asyncio.run(verifier(base_migree, ManualClock(DEBUT)))
    assert (rapport.status, rapport.http_code) == (Status.DOWN, 503)
    assert rapport.detail["components"]["worker"] == {"status": "down", "heartbeat_at": None, "heartbeat_age_s": None}


@pytest.mark.spec("T-OPS-02")
def test_heartbeat_illisible_down(base_migree: str) -> None:
    async def lecture(db: Database) -> StateSnapshot:
        return StateSnapshot(schema_revision="0001", heartbeat={"at": "hier"})

    rapport = asyncio.run(verifier(base_migree, ManualClock(DEBUT), reader=lecture))
    assert rapport.status is Status.DOWN
    assert rapport.detail["components"]["worker"]["status"] == "down"


@pytest.mark.spec("T-OPS-03")
def test_base_inaccessible_down(base_migree: str) -> None:
    """Erreur de SQLite à l'ouverture, injectée : c'est ce que lève le pilote quand le fichier est inaccessible."""

    async def lecture(db: Database) -> StateSnapshot:
        raise OperationalError(
            "SELECT version_num FROM alembic_version", {}, sqlite3.OperationalError("unable to open database file")
        )

    rapport = asyncio.run(verifier(base_migree, ManualClock(DEBUT), reader=lecture))
    assert (rapport.status, rapport.http_code, rapport.public()) == (Status.DOWN, 503, {"status": "down"})
    assert rapport.detail["components"]["database"] == {"status": "down"}


@pytest.mark.spec("T-OPS-03")
def test_lecture_en_echec_down(base_migree: str) -> None:
    async def lecture(db: Database) -> StateSnapshot:
        raise OSError("disk I/O error")

    rapport = asyncio.run(verifier(base_migree, ManualClock(DEBUT), reader=lecture))
    assert (rapport.status, rapport.http_code) == (Status.DOWN, 503)


@pytest.mark.spec("T-OPS-03")
def test_lecture_au_dela_du_delai_down(base_migree: str) -> None:
    """Lecture qui ne rend jamais la main ; délai injecté à 0 pour ne rien attendre."""

    async def lecture(db: Database) -> StateSnapshot:
        await asyncio.Event().wait()
        raise AssertionError("inatteignable")

    rapport = asyncio.run(verifier(base_migree, ManualClock(DEBUT), reader=lecture, read_timeout=0))
    assert (rapport.status, rapport.http_code) == (Status.DOWN, 503)
    assert rapport.detail["components"]["database"] == {"status": "down"}


@pytest.mark.spec("T-OPS-03")
def test_delai_de_lecture_de_2_s_par_defaut(base_migree: str) -> None:
    assert READ_TIMEOUT == 2.0
    checker = HealthChecker(
        Database(create_engine(base_migree), ManualClock(DEBUT)),
        ManualClock(DEBUT),
        db_path=base_migree,
        heartbeat_stale_after=PERIME_APRES,
        version="v",
        started_at=DEBUT,
    )
    assert checker.read_timeout == 2.0
    asyncio.run(checker.db.dispose())
