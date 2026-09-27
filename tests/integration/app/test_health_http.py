"""`/health`, `/api/health` et documentation, par le client de test (VII §40, T-SEC-05).

L'horloge est une `ManualClock` injectée : l'âge du heartbeat se règle sans attendre. Le délai de lecture et la base
inaccessible passent par une lecture injectée, sans sleep.
"""

import asyncio
import json
import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncEngine
from structlog.testing import capture_logs

from app.core.config import AppEnv, AppSettings
from app.db.prerequisites import PrerequisiteError
from app.db.session import Database
from app.main import StartupRefused, create_app
from app.ops.health import HealthReport, StateSnapshot, Status
from app.ops.heartbeat import HEARTBEAT_KEY
from tests.fakes.clock import ManualClock

DEBUT = datetime(2026, 9, 27, 8, 0, tzinfo=UTC)
PERIME_APRES = timedelta(seconds=4)  # `pipeline.yaml` de test (tests/integration/conftest.py)


def reglages(db_path: str, app_env: AppEnv = AppEnv.PRODUCTION) -> AppSettings:
    return AppSettings(
        radar_db_path=db_path, dashboard_url="https://radar.example.com", app_env=app_env, radar_version="abc1234"
    )


def ecrire_heartbeat(db_path: str, at: datetime) -> None:
    valeur = {"at": at.isoformat(), "started_at": at.isoformat(), "version": "w-1", "pid": 4242}
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO system_state (key, value, updated_at) VALUES (?, ?, ?)",
            (HEARTBEAT_KEY, json.dumps(valeur), at.isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def clock() -> ManualClock:
    return ManualClock(DEBUT)


@pytest.fixture
def client(base_migree: str, config_dir: Path, clock: ManualClock) -> Iterator[TestClient]:
    with TestClient(create_app(reglages(base_migree), clock=clock, config_dir=config_dir)) as client:
        yield client


@pytest.mark.spec("T-OPS-01")
def test_health_ok_statut_seul(client: TestClient, base_migree: str, clock: ManualClock) -> None:
    ecrire_heartbeat(base_migree, DEBUT)
    clock.advance(timedelta(seconds=2))
    reponse = client.get("/health")
    assert reponse.status_code == 200
    assert reponse.json() == {"status": "ok"}
    # Aucune information interne : ni version, ni composant, ni horodatage, dans le corps comme dans les en-têtes.
    assert reponse.content == b'{"status":"ok"}'
    assert "abc1234" not in str(reponse.headers)
    assert "2026" not in str(reponse.headers).replace(reponse.headers.get("date", ""), "")


@pytest.mark.spec("T-OPS-01")
def test_health_down_503_statut_seul(client: TestClient) -> None:
    reponse = client.get("/health")  # aucun heartbeat : worker mort
    assert reponse.status_code == 503
    assert reponse.content == b'{"status":"down"}'


@pytest.mark.spec("T-OPS-01")
def test_health_degraded_200(client: TestClient) -> None:
    """Aucune condition n'existe encore (VII §39.5) : l'état `degraded` est injecté pour vérifier son code HTTP."""

    async def degrade() -> HealthReport:
        return HealthReport(Status.DEGRADED, {"status": "degraded", "version": "abc1234"})

    client.app.state.health.check = degrade  # type: ignore[attr-defined]
    reponse = client.get("/health")
    assert reponse.status_code == 200
    assert reponse.content == b'{"status":"degraded"}'


@pytest.mark.spec("T-OPS-02")
def test_heartbeat_perime_503(client: TestClient, base_migree: str, clock: ManualClock) -> None:
    ecrire_heartbeat(base_migree, DEBUT)
    clock.advance(PERIME_APRES)
    assert client.get("/health").status_code == 200
    clock.advance(timedelta(seconds=1))
    reponse = client.get("/health")
    assert (reponse.status_code, reponse.json()) == (503, {"status": "down"})


@pytest.mark.spec("T-OPS-03")
@pytest.mark.parametrize("cas", ["erreur", "delai"])
def test_base_inaccessible_ou_lecture_trop_longue_503(base_migree: str, config_dir: Path, cas: str) -> None:
    async def lecture(db: Database) -> StateSnapshot:
        if cas == "erreur":
            raise sqlite3.OperationalError("unable to open database file")
        await asyncio.Event().wait()  # ne rend jamais la main ; le délai injecté à 0 l'interrompt
        raise AssertionError("inatteignable")

    app = create_app(reglages(base_migree), clock=ManualClock(DEBUT), config_dir=config_dir, reader=lecture)
    with TestClient(app) as client:
        client.app.state.health.read_timeout = 0  # type: ignore[attr-defined]
        reponse = client.get("/health")
        detail = client.get("/api/health").json()
    assert (reponse.status_code, reponse.content) == (503, b'{"status":"down"}')
    assert detail["components"]["database"] == {"status": "down"}


@pytest.mark.spec("T-OPS-02")
def test_api_health_detail(client: TestClient, base_migree: str, clock: ManualClock) -> None:
    ecrire_heartbeat(base_migree, DEBUT)
    clock.advance(timedelta(seconds=3))
    reponse = client.get("/api/health")
    assert reponse.status_code == 200
    detail: dict[str, Any] = reponse.json()
    assert detail["status"] == "ok"
    assert detail["version"] == "abc1234"
    assert detail["checked_at"] == "2026-09-27T08:00:03Z"
    assert set(detail["components"]) == {"database", "worker", "app"}
    assert detail["components"]["worker"]["heartbeat_age_s"] == 3
    assert detail["components"]["database"]["schema_revision"] == "0001"
    assert detail["components"]["app"] == {"started_at": "2026-09-27T08:00:00Z", "db_locked_1h": 0}
    assert detail["conditions"] == []


@pytest.mark.spec("T-SEC-05")
def test_documentation_absente_en_production(client: TestClient) -> None:
    for chemin in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(chemin).status_code == 404


@pytest.mark.spec("T-SEC-05")
def test_documentation_absente_par_defaut(base_migree: str, config_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APP_ENV", raising=False)
    settings = AppSettings(radar_db_path=base_migree, dashboard_url="https://radar.example.com")
    assert settings.app_env is AppEnv.PRODUCTION
    with TestClient(create_app(settings, clock=ManualClock(DEBUT), config_dir=config_dir)) as client:
        for chemin in ("/docs", "/redoc", "/openapi.json"):
            assert client.get(chemin).status_code == 404


@pytest.mark.spec("T-SEC-05")
def test_documentation_presente_en_development(base_migree: str, config_dir: Path) -> None:
    app = create_app(reglages(base_migree, AppEnv.DEVELOPMENT), clock=ManualClock(DEBUT), config_dir=config_dir)
    with TestClient(app) as client:
        for chemin in ("/docs", "/redoc", "/openapi.json"):
            assert client.get(chemin).status_code == 200


@pytest.mark.spec("T-DB-01")
def test_prerequis_absent_refus_au_demarrage(base_migree: str, config_dir: Path) -> None:
    async def prerequis_absent(engine: AsyncEngine) -> None:
        raise PrerequisiteError("SQLite 3.34.1 < 3.35 requis")

    app = create_app(
        reglages(base_migree), clock=ManualClock(DEBUT), config_dir=config_dir, prerequisites=prerequis_absent
    )
    with capture_logs() as logs, pytest.raises(StartupRefused), TestClient(app):
        pass
    assert [(e["event"], e["log_level"], e["reason"]) for e in logs] == [
        ("app.refused", "critical", "SQLite 3.34.1 < 3.35 requis")
    ]
