"""`/health`, `/api/health` and documentation, through the test client (VII §40, T-SEC-05).

The clock is an injected `ManualClock`: the heartbeat age is set without waiting. The read timeout and the unreachable
database go through an injected read, without sleep.
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

START = datetime(2026, 9, 27, 8, 0, tzinfo=UTC)
STALE_AFTER = timedelta(seconds=4)  # test `pipeline.yaml` (tests/integration/conftest.py)


def settings(db_path: str, app_env: AppEnv = AppEnv.PRODUCTION) -> AppSettings:
    return AppSettings(
        radar_db_path=db_path, dashboard_url="https://radar.example.com", app_env=app_env, radar_version="abc1234"
    )


def write_heartbeat(db_path: str, at: datetime) -> None:
    value = {"at": at.isoformat(), "started_at": at.isoformat(), "version": "w-1", "pid": 4242}
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO system_state (key, value, updated_at) VALUES (?, ?, ?)",
            (HEARTBEAT_KEY, json.dumps(value), at.isoformat()),
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture
def clock() -> ManualClock:
    return ManualClock(START)


@pytest.fixture
def client(migrated_db: str, config_dir: Path, clock: ManualClock) -> Iterator[TestClient]:
    with TestClient(create_app(settings(migrated_db), clock=clock, config_dir=config_dir)) as client:
        yield client


@pytest.mark.spec("T-OPS-01")
def test_health_ok_status_only(client: TestClient, migrated_db: str, clock: ManualClock) -> None:
    write_heartbeat(migrated_db, START)
    clock.advance(timedelta(seconds=2))
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
    # No internal information: no version, component or timestamp, in the body as in the headers.
    assert response.content == b'{"status":"ok"}'
    assert "abc1234" not in str(response.headers)
    assert "2026" not in str(response.headers).replace(response.headers.get("date", ""), "")


@pytest.mark.spec("T-OPS-01")
def test_health_down_503_status_only(client: TestClient) -> None:
    response = client.get("/health")  # no heartbeat: dead worker
    assert response.status_code == 503
    assert response.content == b'{"status":"down"}'


@pytest.mark.spec("T-OPS-01")
def test_health_degraded_200(client: TestClient) -> None:
    """No condition exists yet (VII §39.5): the `degraded` state is injected to check its HTTP code."""

    async def degrade() -> HealthReport:
        return HealthReport(Status.DEGRADED, {"status": "degraded", "version": "abc1234"})

    client.app.state.health.check = degrade  # type: ignore[attr-defined]
    response = client.get("/health")
    assert response.status_code == 200
    assert response.content == b'{"status":"degraded"}'


@pytest.mark.spec("T-OPS-02")
def test_stale_heartbeat_503(client: TestClient, migrated_db: str, clock: ManualClock) -> None:
    write_heartbeat(migrated_db, START)
    clock.advance(STALE_AFTER)
    assert client.get("/health").status_code == 200
    clock.advance(timedelta(seconds=1))
    response = client.get("/health")
    assert (response.status_code, response.json()) == (503, {"status": "down"})


@pytest.mark.spec("T-OPS-03")
@pytest.mark.parametrize("case", ["error", "timeout"])
def test_unreachable_database_or_read_too_long_503(migrated_db: str, config_dir: Path, case: str) -> None:
    async def read(db: Database) -> StateSnapshot:
        if case == "error":
            raise sqlite3.OperationalError("unable to open database file")
        await asyncio.Event().wait()  # never yields back; the timeout injected at 0 interrupts it
        raise AssertionError("unreachable")

    app = create_app(settings(migrated_db), clock=ManualClock(START), config_dir=config_dir, reader=read)
    with TestClient(app) as client:
        client.app.state.health.read_timeout = 0  # type: ignore[attr-defined]
        response = client.get("/health")
        detail = client.get("/api/health").json()
    assert (response.status_code, response.content) == (503, b'{"status":"down"}')
    assert detail["components"]["database"] == {"status": "down"}


@pytest.mark.spec("T-OPS-02")
def test_api_health_detail(client: TestClient, migrated_db: str, clock: ManualClock) -> None:
    write_heartbeat(migrated_db, START)
    clock.advance(timedelta(seconds=3))
    response = client.get("/api/health")
    assert response.status_code == 200
    detail: dict[str, Any] = response.json()
    assert detail["status"] == "ok"
    assert detail["version"] == "abc1234"
    assert detail["checked_at"] == "2026-09-27T08:00:03Z"
    assert set(detail["components"]) == {"database", "worker", "app"}
    assert detail["components"]["worker"]["heartbeat_age_s"] == 3
    assert detail["components"]["database"]["schema_revision"] == "0001"
    assert detail["components"]["app"] == {"started_at": "2026-09-27T08:00:00Z", "db_locked_1h": 0}
    assert detail["conditions"] == []


@pytest.mark.spec("T-SEC-05")
def test_documentation_absent_in_production(client: TestClient) -> None:
    for path in ("/docs", "/redoc", "/openapi.json"):
        assert client.get(path).status_code == 404


@pytest.mark.spec("T-SEC-05")
def test_documentation_absent_by_default(migrated_db: str, config_dir: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("APP_ENV", raising=False)
    default_settings = AppSettings(radar_db_path=migrated_db, dashboard_url="https://radar.example.com")
    assert default_settings.app_env is AppEnv.PRODUCTION
    with TestClient(create_app(default_settings, clock=ManualClock(START), config_dir=config_dir)) as client:
        for path in ("/docs", "/redoc", "/openapi.json"):
            assert client.get(path).status_code == 404


@pytest.mark.spec("T-SEC-05")
def test_documentation_present_in_development(migrated_db: str, config_dir: Path) -> None:
    app = create_app(settings(migrated_db, AppEnv.DEVELOPMENT), clock=ManualClock(START), config_dir=config_dir)
    with TestClient(app) as client:
        for path in ("/docs", "/redoc", "/openapi.json"):
            assert client.get(path).status_code == 200


@pytest.mark.spec("T-DB-01")
def test_missing_prerequisite_refused_at_startup(migrated_db: str, config_dir: Path) -> None:
    async def missing_prerequisite(engine: AsyncEngine) -> None:
        raise PrerequisiteError("SQLite 3.34.1 < 3.35 required")

    app = create_app(
        settings(migrated_db), clock=ManualClock(START), config_dir=config_dir, prerequisites=missing_prerequisite
    )
    with capture_logs() as logs, pytest.raises(StartupRefused), TestClient(app):
        pass
    assert [(e["event"], e["log_level"], e["reason"]) for e in logs] == [
        ("app.refused", "critical", "SQLite 3.34.1 < 3.35 required")
    ]
