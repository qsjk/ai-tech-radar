"""`python -m app.cli health` (IX §56.3, §56.4) : même détail que `/api/health`, codes 0, 1, 2."""

import asyncio
import json
import logging
import sqlite3
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pytest
import structlog
from structlog.testing import capture_logs

from app.cli.__main__ import main
from app.cli.health import health_detail
from app.core.config import AppSettings
from app.ops.heartbeat import HEARTBEAT_KEY
from tests.fakes.clock import ManualClock

DEBUT = datetime(2026, 9, 27, 8, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _logs_restaures() -> Iterator[None]:
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    yield
    root.handlers[:] = handlers
    root.setLevel(level)
    structlog.reset_defaults()


def reglages(db_path: str) -> AppSettings:
    return AppSettings(radar_db_path=db_path, dashboard_url="https://radar.example.com", radar_version="abc1234")


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


def lancer(capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, str, str]:
    try:
        code = main(list(argv))
    except SystemExit as sortie:
        code = int(sortie.code or 0)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


@pytest.mark.spec("T-OPS-02")
def test_detail_heartbeat_frais_code_0(base_migree: str, config_dir: Path) -> None:
    ecrire_heartbeat(base_migree, DEBUT)
    clock = ManualClock(DEBUT + timedelta(seconds=3))
    code, detail = asyncio.run(health_detail(reglages(base_migree), config_dir, clock))
    assert code == 0
    assert detail is not None
    assert (detail["status"], detail["version"], detail["checked_at"]) == ("ok", "abc1234", "2026-09-27T08:00:03Z")
    assert set(detail["components"]) == {"database", "worker"}
    base: dict[str, Any] = detail["components"]["database"]
    assert (base["status"], base["schema_revision"], base["journal_size_limit"]) == ("ok", "0001", 67_108_864)
    assert detail["components"]["worker"]["heartbeat_age_s"] == 3
    assert detail["conditions"] == []


@pytest.mark.spec("T-OPS-02")
def test_heartbeat_perime_code_1_avec_le_detail(base_migree: str, config_dir: Path) -> None:
    ecrire_heartbeat(base_migree, DEBUT)
    clock = ManualClock(DEBUT + timedelta(seconds=5))  # `heartbeat_stale_after` de test : 4 s
    code, detail = asyncio.run(health_detail(reglages(base_migree), config_dir, clock))
    assert code == 1
    assert detail is not None
    assert (detail["status"], detail["components"]["worker"]["status"]) == ("down", "down")


@pytest.mark.spec("T-DB-02")
def test_base_non_migree_code_1(tmp_path: Path, config_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db_path = str(tmp_path / "vide.db")
    sqlite3.connect(db_path).close()
    with capture_logs() as logs:
        code, detail = asyncio.run(health_detail(reglages(db_path), config_dir, ManualClock(DEBUT)))
    assert (code, detail) == (1, None)
    assert [(e["event"], e["log_level"]) for e in logs] == [("app.refused", "critical")]
    assert capsys.readouterr().out.startswith("échec : base non migrée")


@pytest.mark.spec("T-CFG-10")
def test_pipeline_invalide_code_2(base_migree: str, config_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (config_dir / "pipeline.yaml").write_text("ops:\n  watchdog_timeout: 1s\n", encoding="utf-8")
    with capture_logs() as logs:
        code, detail = asyncio.run(health_detail(reglages(base_migree), config_dir, ManualClock(DEBUT)))
    assert (code, detail) == (2, None)
    assert [(e["event"], e["log_level"]) for e in logs] == [("app.refused", "critical")]
    assert capsys.readouterr().out.startswith("échec : configuration invalide")


@pytest.mark.spec("T-CFG-10")
def test_commande_resultat_sur_stdout_logs_sur_stderr(
    base_migree: str, config_dir: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RADAR_DB_PATH", base_migree)
    monkeypatch.setenv("DASHBOARD_URL", "https://radar.example.com")
    ecrire_heartbeat(base_migree, datetime.now(UTC))
    code, out, err = lancer(capsys, "health", "--config-dir", str(config_dir))
    assert code == 0, out + err
    assert json.loads(out)["status"] == "ok"
    assert [json.loads(ligne)["event"] for ligne in err.splitlines() if "health." in ligne] == ["health.checked"]
    assert all(isinstance(json.loads(ligne), dict) for ligne in err.splitlines())


@pytest.mark.spec("T-CFG-10")
def test_variables_invalides_code_2(
    base_migree: str, config_dir: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RADAR_DB_PATH", base_migree)
    monkeypatch.setenv("DASHBOARD_URL", "https://radar.example.com/")
    code, out, _ = lancer(capsys, "health", "--config-dir", str(config_dir))
    assert code == 2
    assert out.startswith("configuration invalide : variables d'environnement")
    assert "radar.example.com/" not in out.split("\n", 1)[0]
