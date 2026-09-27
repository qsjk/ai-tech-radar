"""Worker en processus (VII §36.6) : séquence de boot, supervision fail-fast, arrêt, avec une horloge pas à pas.

Les signaux ne sont pas installés (`handle_signals=False`) et l'action du watchdog est une espionne : le processus de
pytest n'est jamais arrêté. Les comportements de niveau processus sont dans `test_worker_processus.py`.
"""

import asyncio
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine
from structlog.testing import capture_logs

from app.core.config import WorkerSettings
from app.db.prerequisites import PrerequisiteError
from app.ops.heartbeat import HEARTBEAT_KEY
from app.worker import Worker
from tests.fakes.clock import SteppedClock

DEBUT = datetime(2026, 9, 27, 8, 0, tzinfo=UTC)


def reglages(db_path: str) -> WorkerSettings:
    return WorkerSettings(
        radar_db_path=db_path,
        dashboard_url="https://radar.example.com",
        http_contact="https://example.com/contact",
        radar_version="abc1234",
    )


def heartbeats(db_path: str) -> int:
    conn = sqlite3.connect(db_path)
    try:
        return int(conn.execute("SELECT count(*) FROM system_state WHERE key = ?", (HEARTBEAT_KEY,)).fetchone()[0])
    except sqlite3.OperationalError:
        return 0
    finally:
        conn.close()


def evenements(logs: list[dict[str, Any]]) -> list[str]:
    return [str(entry["event"]) for entry in logs]


class Espion:
    def __init__(self) -> None:
        self.appels = 0

    def __call__(self) -> None:
        self.appels += 1


def worker(db_path: str, config_dir: Path, clock: SteppedClock, **options: Any) -> Worker:
    return Worker(
        reglages(db_path),
        clock=clock,
        config_dir=config_dir,
        on_watchdog_timeout=options.pop("on_watchdog_timeout", Espion()),
        handle_signals=False,
        **options,
    )


async def demarre(tache: asyncio.Task[int], logs: list[dict[str, Any]]) -> None:
    """Attend `worker.started`, sans sleep : la boucle cède la main jusqu'au log (ou jusqu'à la fin de la tâche)."""
    while "worker.started" not in evenements(logs) and not tache.done():
        await asyncio.sleep(0.01)


@pytest.mark.spec("T-OPS-10:verifications")
@pytest.mark.spec("T-OPS-10:heartbeat")
def test_ordre_verifications_puis_heartbeat_puis_demarrage(base_migree: str, config_dir: Path) -> None:
    async def scenario() -> int:
        w = worker(base_migree, config_dir, SteppedClock(DEBUT))
        tache = asyncio.create_task(w.run())
        await demarre(tache, logs)
        assert heartbeats(base_migree) == 1
        w.request_stop()
        return await tache

    with capture_logs() as logs:
        assert asyncio.run(scenario()) == 0
    assert evenements(logs) == [
        "worker.boot.checked",
        "worker.heartbeat.started",
        "worker.started",
        "worker.stop.requested",
        "worker.stopped",
    ]


@pytest.mark.spec("T-OPS-09")
def test_heartbeat_ecrit_avant_la_fin_du_boot(base_migree: str, config_dir: Path) -> None:
    """Le heartbeat est en base avant `worker.started` : avant toute étape suivante (modèles compris, à venir)."""

    async def scenario() -> tuple[int, int]:
        w = worker(base_migree, config_dir, SteppedClock(DEBUT))
        tache = asyncio.create_task(w.run())
        vus_au_demarrage = -1
        while not tache.done():
            if "worker.heartbeat.started" in evenements(logs) and vus_au_demarrage < 0:
                vus_au_demarrage = heartbeats(base_migree)
            if "worker.started" in evenements(logs):
                break
            await asyncio.sleep(0.01)
        w.request_stop()
        return vus_au_demarrage, await tache

    with capture_logs() as logs:
        assert asyncio.run(scenario()) == (1, 0)


@pytest.mark.spec("T-OPS-10:verifications")
@pytest.mark.spec("T-DB-01")
def test_prerequis_absent_refus_sans_heartbeat(base_migree: str, config_dir: Path) -> None:
    async def prerequis_absent(engine: AsyncEngine) -> None:
        raise PrerequisiteError("SQLite 3.34.1 < 3.35 requis")

    w = worker(base_migree, config_dir, SteppedClock(DEBUT), prerequisites=prerequis_absent)
    with capture_logs() as logs:
        assert asyncio.run(w.run()) == 1
    assert [(e["event"], e["log_level"], e["reason"]) for e in logs] == [
        ("worker.refused", "critical", "SQLite 3.34.1 < 3.35 requis")
    ]
    assert heartbeats(base_migree) == 0


@pytest.mark.spec("T-OPS-10:verifications")
@pytest.mark.spec("T-DB-02")
def test_base_non_migree_refus_sans_heartbeat(tmp_path: Path, config_dir: Path) -> None:
    db_path = str(tmp_path / "vide.db")
    sqlite3.connect(db_path).close()
    with capture_logs() as logs:
        assert asyncio.run(worker(db_path, config_dir, SteppedClock(DEBUT)).run()) == 1
    assert [(e["event"], e["log_level"], e["error_class"]) for e in logs] == [
        ("worker.refused", "critical", "SchemaRevisionError")
    ]
    assert heartbeats(db_path) == 0


@pytest.mark.spec("T-OPS-10:verifications")
def test_configuration_invalide_refus_sans_heartbeat(base_migree: str, config_dir: Path) -> None:
    (config_dir / "topics.yaml").write_text("topics: [{slug: llm}]\n", encoding="utf-8")
    with capture_logs() as logs:
        assert asyncio.run(worker(base_migree, config_dir, SteppedClock(DEBUT)).run()) == 2
    assert [(e["event"], e["log_level"]) for e in logs] == [("worker.refused", "critical")]
    assert logs[0]["issues"]
    assert heartbeats(base_migree) == 0


@pytest.mark.spec("T-OPS-08:heartbeat")
def test_heartbeat_en_exception_log_critical_et_sortie_non_nulle(base_migree: str, config_dir: Path) -> None:
    async def scenario() -> int:
        clock = SteppedClock(DEBUT)
        w = worker(base_migree, config_dir, clock)
        tache = asyncio.create_task(w.run())
        await demarre(tache, logs)
        conn = sqlite3.connect(base_migree)
        conn.execute("DROP TABLE system_state")
        conn.commit()
        conn.close()
        while clock.sleepers < 2:  # heartbeat et rafraîchissement du watchdog en attente
            await asyncio.sleep(0.01)
        clock.advance(timedelta(seconds=1))
        return await tache

    with capture_logs() as logs:
        assert asyncio.run(scenario()) == 1
    echecs = [e for e in logs if e["event"] == "worker.task.failed"]
    assert [(e["log_level"], e["task"]) for e in echecs] == [("critical", "heartbeat")]
    assert "no such table" in str(echecs[0]["exc_info"])
    assert evenements(logs)[-1] == "worker.stopped"


@pytest.mark.spec("T-OPS-11:arret")
def test_arret_demande_annule_les_taches_et_renvoie_0(base_migree: str, config_dir: Path) -> None:
    espion = Espion()

    async def scenario() -> tuple[int, int]:
        w = worker(base_migree, config_dir, SteppedClock(DEBUT), on_watchdog_timeout=espion)
        tache = asyncio.create_task(w.run())
        await demarre(tache, logs)
        w.request_stop()
        code = await tache
        restantes = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        return code, len(restantes)

    with capture_logs() as logs:
        assert asyncio.run(scenario()) == (0, 0)
    assert [e for e in logs if e["event"] == "worker.stopped"][0]["code"] == 0
    assert espion.appels == 0
