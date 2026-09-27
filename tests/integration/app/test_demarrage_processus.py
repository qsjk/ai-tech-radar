"""App au niveau du processus : `uvicorn app.main:app` en sous-processus, sur 127.0.0.1, port choisi par le système.

Refus de démarrer (T-CFG-07, T-DB-02, `pipeline.yaml` invalide), démarrage nominal, `/health` réel, arrêt sur SIGTERM.
Chaque attente est bornée ; aucune n'est un sleep.
"""

import json
import os
import re
import shutil
import signal
import sqlite3
import sys
import urllib.error
import urllib.request
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from app.ops.heartbeat import HEARTBEAT_KEY
from tests.integration.processus import DELAI, Processus, variables_coverage

COMMANDE = [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "0"]
COMMANDE += ["--workers", "1", "--no-access-log"]

# Simule, dans le sous-processus, une bibliothèque SQLite trop ancienne et sans FTS5, puis lance le vrai uvicorn.
SQLITE_ANCIEN = """\
import sys
import uvicorn
from app.db import prerequisites

async def sonde(engine):
    return prerequisites.SqliteFeatures(version="3.34.1", fts5=False, json1=True)

prerequisites.probe_features = sonde
sys.argv = ["uvicorn", *sys.argv[1:]]
uvicorn.main()
"""

UVICORN_STARTUP_FAILURE = 3
"""Code de sortie d'uvicorn quand le lifespan échoue."""


def environnement(db_path: str, **variables: str) -> dict[str, str]:
    """Environnement minimal et hermétique : seules les variables utiles, secrets factices."""
    env = {
        "PATH": os.environ["PATH"],
        "RADAR_DB_PATH": db_path,
        "DASHBOARD_URL": "https://radar.example.com",
        "RADAR_VERSION": "abc1234",
        "DASHBOARD_PASSWORD_HASH": "FAKE-hash",
    }
    env.update(variables)
    env.update(variables_coverage())
    return {name: value for name, value in env.items() if value}


@pytest.fixture
def repertoire(tmp_path: Path, config_dir: Path) -> Path:
    """Répertoire courant de l'app : `config/` relatif, comme `/app` dans l'image."""
    racine = tmp_path / "app"
    racine.mkdir()
    shutil.copytree(config_dir, racine / "config")
    return racine


@pytest.fixture
def lancer(repertoire: Path) -> Iterator[Any]:
    lances: list[Processus] = []

    def _lancer(env: dict[str, str], *, code: str | None = None) -> Processus:
        commande = [sys.executable, "-c", code, *COMMANDE[3:]] if code else COMMANDE
        processus = Processus(commande, env, cwd=repertoire)
        lances.append(processus)
        return processus

    yield _lancer
    for processus in lances:
        processus.arreter()


def get(url: str) -> tuple[int, bytes]:
    try:
        with urllib.request.urlopen(url, timeout=DELAI) as reponse:  # noqa: S310 — 127.0.0.1 uniquement
            return int(reponse.status), bytes(reponse.read())
    except urllib.error.HTTPError as erreur:
        return int(erreur.code), bytes(erreur.read())


def ecrire_heartbeat_frais(db_path: str) -> None:
    maintenant = datetime.now(UTC).isoformat()
    valeur = {"at": maintenant, "started_at": maintenant, "version": "w-1", "pid": 4242}
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO system_state (key, value, updated_at) VALUES (?, ?, ?)",
            (HEARTBEAT_KEY, json.dumps(valeur), maintenant),
        )
        conn.commit()
    finally:
        conn.close()


@pytest.mark.spec("T-CFG-07")
@pytest.mark.parametrize(
    "url", ["ftp://radar.example.com", "https://radar.example.com/", "https://radar.example.com:8443"]
)
def test_dashboard_url_invalide_refus(lancer: Any, base_migree: str, url: str) -> None:
    app = lancer(environnement(base_migree, DASHBOARD_URL=url))
    refus = app.attendre_log("app.refused")
    assert app.attendre_fin() == 2
    assert refus["level"] == "critical"
    assert refus["service"] == "app"
    assert "DASHBOARD_URL" in " ".join(refus["problems"])
    assert "Uvicorn running" not in json.dumps(app.logs)


@pytest.mark.spec("T-DB-02")
def test_base_non_migree_refus(lancer: Any, tmp_path: Path) -> None:
    db_path = str(tmp_path / "vide.db")
    sqlite3.connect(db_path).close()
    app = lancer(environnement(db_path))
    refus = app.attendre_log("app.refused")
    assert app.attendre_fin() == UVICORN_STARTUP_FAILURE
    assert (refus["level"], refus["error_class"]) == ("critical", "SchemaRevisionError")
    assert "Uvicorn running" not in json.dumps(app.logs)


@pytest.mark.spec("T-DB-01")
def test_prerequis_sqlite_absents_refus(lancer: Any, base_migree: str) -> None:
    app = lancer(environnement(base_migree), code=SQLITE_ANCIEN)
    refus = app.attendre_log("app.refused")
    assert app.attendre_fin() == UVICORN_STARTUP_FAILURE
    assert (refus["level"], refus["error_class"]) == ("critical", "PrerequisiteError")
    assert "SQLite 3.34.1 trop ancien" in refus["reason"]
    assert "FTS5 absente" in refus["reason"]
    assert "Uvicorn running" not in json.dumps(app.logs)


@pytest.mark.spec("T-CFG-02:schemas")
def test_pipeline_invalide_refus_meme_message_que_le_worker(lancer: Any, base_migree: str, repertoire: Path) -> None:
    (repertoire / "config" / "pipeline.yaml").write_text("ops:\n  heartbeat_stale_after: bientôt\n", encoding="utf-8")
    app = lancer(environnement(base_migree))
    refus = app.attendre_log("app.refused")
    assert app.attendre_fin() == UVICORN_STARTUP_FAILURE
    assert refus["level"] == "critical"
    assert refus["reason"] == "configuration invalide (config)"
    assert refus["issues"] and "pipeline.yaml" in refus["issues"][0]
    assert "heartbeat_stale_after" in refus["issues"][0]


@pytest.mark.spec("T-OPS-01")
def test_demarrage_health_reel_sans_access_log_puis_sigterm(lancer: Any, base_migree: str) -> None:
    ecrire_heartbeat_frais(base_migree)
    app = lancer(environnement(base_migree))
    demarrage = app.attendre_log("app.started")
    ecoute = app.attendre_log("Uvicorn running on ", debut=True)
    port = re.search(r"http://127\.0\.0\.1:(\d+)", ecoute["event"])
    assert port is not None
    base = f"http://127.0.0.1:{port.group(1)}"

    assert get(f"{base}/health") == (200, b'{"status":"ok"}')
    code, corps = get(f"{base}/api/health")
    assert code == 200
    detail = json.loads(corps)
    assert (detail["status"], detail["version"]) == ("ok", "abc1234")
    assert detail["components"]["database"]["schema_revision"] == "0001"
    assert get(f"{base}/docs")[0] == 404

    app.popen.send_signal(signal.SIGTERM)
    # uvicorn s'arrête proprement (lifespan fermé, `app.stopped`), puis relève le signal reçu : fin par SIGTERM.
    assert app.attendre_fin() == -signal.SIGTERM
    assert "Application shutdown complete." in app.evenements("Application")
    journal = json.dumps(app.logs)
    assert (demarrage["level"], demarrage["service"]) == ("info", "app")
    assert all(entree["event"] is not None for entree in app.logs), "toutes les lignes sont en JSON"
    assert "GET /health" not in journal, "aucun access log (VII §42.3)"
    assert "FAKE-" not in journal
    assert app.evenements("app.") == ["app.started", "app.stopped"]


@pytest.mark.spec("T-OPS-02")
def test_health_down_sans_heartbeat(lancer: Any, base_migree: str) -> None:
    app = lancer(environnement(base_migree))
    ecoute = app.attendre_log("Uvicorn running on ", debut=True)
    port = re.search(r"http://127\.0\.0\.1:(\d+)", ecoute["event"])
    assert port is not None
    assert get(f"http://127.0.0.1:{port.group(1)}/health") == (503, b'{"status":"down"}')
