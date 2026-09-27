"""Worker au niveau du processus : `python -m app.worker` en sous-processus, sur une base temporaire migrée.

Refus de démarrer, sortie non nulle, SIGTERM et watchdog réel. Réglages courts dans le `pipeline.yaml` de test ;
chaque attente est bornée (lecture des logs avec délai, `wait(timeout=…)`), sans sleep.
"""

import json
import os
import signal
import sqlite3
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from app.ops.heartbeat import HEARTBEAT_KEY
from tests.integration.processus import Processus, variables_coverage

# Rend inerte, dans le sous-processus, le heartbeat : la boucle se fige, le watchdog doit arrêter le processus.
GEL_DE_LA_BOUCLE = """\
import sys, time
from app import worker
from app.ops.heartbeat import Heartbeat

async def gel(self):
    time.sleep(3600)

Heartbeat.run = gel
sys.exit(worker.main(sys.argv[1:]))
"""


def environnement(db_path: str, **variables: str) -> dict[str, str]:
    """Environnement minimal et hermétique : seules les variables utiles, secrets factices."""
    env = {
        "PATH": os.environ["PATH"],
        "RADAR_DB_PATH": db_path,
        "DASHBOARD_URL": "https://radar.example.com",
        "HTTP_CONTACT": "https://example.com/contact",
        "RADAR_VERSION": "abc1234",
        "SMTP_PASSWORD": "FAKE-smtp-password",
    }
    env.update(variables)
    env.update(variables_coverage())
    return {name: value for name, value in env.items() if value}


@pytest.fixture
def lancer(config_dir: Path) -> Iterator[Any]:
    lances: list[Processus] = []

    def _lancer(env: dict[str, str], *, code: str | None = None) -> Processus:
        args = [sys.executable, "-c", code] if code else [sys.executable, "-m", "app.worker"]
        processus = Processus([*args, "--config-dir", str(config_dir)], env)
        lances.append(processus)
        return processus

    yield _lancer
    for processus in lances:
        processus.arreter()


def lire_heartbeat(db_path: str) -> dict[str, Any]:
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute("SELECT value FROM system_state WHERE key = ?", (HEARTBEAT_KEY,)).fetchone()
    finally:
        conn.close()
    value: dict[str, Any] = json.loads(row[0])
    return value


@pytest.mark.spec("T-CFG-05")
def test_http_contact_absent_refus(lancer: Any, base_migree: str) -> None:
    worker = lancer(environnement(base_migree, HTTP_CONTACT=""))
    refus = worker.attendre_log("worker.refused")
    assert worker.attendre_fin() == 2
    assert refus["level"] == "critical"
    assert refus["problems"] == ["HTTP_CONTACT: Field required"]
    assert worker.evenements() == ["worker.refused"]


@pytest.mark.spec("T-CFG-07")
@pytest.mark.parametrize(
    "url", ["ftp://radar.example.com", "https://radar.example.com/", "https://radar.example.com:8443"]
)
def test_dashboard_url_invalide_refus(lancer: Any, base_migree: str, url: str) -> None:
    worker = lancer(environnement(base_migree, DASHBOARD_URL=url))
    refus = worker.attendre_log("worker.refused")
    assert worker.attendre_fin() == 2
    assert refus["level"] == "critical"
    assert "DASHBOARD_URL" in " ".join(refus["problems"])


@pytest.mark.spec("T-DB-02")
def test_base_non_migree_refus(lancer: Any, tmp_path: Path) -> None:
    db_path = str(tmp_path / "vide.db")
    sqlite3.connect(db_path).close()
    worker = lancer(environnement(db_path))
    refus = worker.attendre_log("worker.refused")
    assert worker.attendre_fin() == 1
    assert (refus["level"], refus["error_class"]) == ("critical", "SchemaRevisionError")
    assert "head" in refus["reason"]


@pytest.mark.spec("T-OPS-10:verifications")
@pytest.mark.spec("T-OPS-10:heartbeat")
@pytest.mark.spec("T-OPS-11:arret")
def test_sigterm_arret_propre_code_0(lancer: Any, base_migree: str) -> None:
    worker = lancer(environnement(base_migree))
    demarrage = worker.attendre_log("worker.started")
    heartbeat = lire_heartbeat(base_migree)
    assert heartbeat["pid"] == demarrage["pid"] == worker.popen.pid
    assert heartbeat["version"] == "abc1234"
    debut = time.monotonic()
    worker.popen.send_signal(signal.SIGTERM)
    assert worker.attendre_fin() == 0
    assert time.monotonic() - debut < 20
    assert "FAKE-" not in json.dumps(worker.logs)
    assert worker.evenements() == [
        "worker.boot.started",
        "worker.boot.checked",
        "worker.heartbeat.started",
        "worker.started",
        "worker.stop.requested",
        "worker.stopped",
    ]


@pytest.mark.spec("T-OPS-08:heartbeat")
def test_heartbeat_en_exception_sortie_non_nulle(lancer: Any, base_migree: str) -> None:
    worker = lancer(environnement(base_migree))
    worker.attendre_log("worker.started")
    conn = sqlite3.connect(base_migree)
    conn.execute("DROP TABLE system_state")
    conn.commit()
    conn.close()
    echec = worker.attendre_log("worker.task.failed")
    assert worker.attendre_fin() == 1
    assert (echec["level"], echec["task"]) == ("critical", "heartbeat")
    assert "no such table" in echec["exception"]


@pytest.mark.spec("T-OPS-07")
def test_boucle_gelee_watchdog_arrete_le_processus(lancer: Any, base_migree: str) -> None:
    worker = lancer(environnement(base_migree), code=GEL_DE_LA_BOUCLE)
    worker.attendre_log("worker.started")
    alerte = worker.attendre_log("worker.watchdog.timeout")
    assert worker.attendre_fin() == 1
    assert (alerte["level"], alerte["timeout_s"]) == ("critical", 10.0)
    assert "worker.stopped" not in worker.evenements()
