"""`python -m app.cli health` (IX §56.3, §56.4): same detail as `/api/health`, codes 0, 1, 2."""

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

START = datetime(2026, 9, 27, 8, 0, tzinfo=UTC)


@pytest.fixture(autouse=True)
def _restore_logging() -> Iterator[None]:
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    yield
    root.handlers[:] = handlers
    root.setLevel(level)
    structlog.reset_defaults()


def settings(db_path: str) -> AppSettings:
    return AppSettings(radar_db_path=db_path, dashboard_url="https://radar.example.com", radar_version="abc1234")


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


def run_cli(capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, str, str]:
    try:
        code = main(list(argv))
    except SystemExit as exit_:
        code = int(exit_.code or 0)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


@pytest.mark.spec("T-OPS-02")
def test_fresh_heartbeat_detail_code_0(migrated_db: str, config_dir: Path) -> None:
    write_heartbeat(migrated_db, START)
    clock = ManualClock(START + timedelta(seconds=3))
    code, detail = asyncio.run(health_detail(settings(migrated_db), config_dir, clock))
    assert code == 0
    assert detail is not None
    assert (detail["status"], detail["version"], detail["checked_at"]) == ("ok", "abc1234", "2026-09-27T08:00:03Z")
    assert set(detail["components"]) == {"database", "worker"}
    database: dict[str, Any] = detail["components"]["database"]
    assert (database["status"], database["schema_revision"], database["journal_size_limit"]) == (
        "ok",
        "0001",
        67_108_864,
    )
    assert detail["components"]["worker"]["heartbeat_age_s"] == 3
    assert detail["conditions"] == []


@pytest.mark.spec("T-OPS-02")
def test_stale_heartbeat_code_1_with_the_detail(migrated_db: str, config_dir: Path) -> None:
    write_heartbeat(migrated_db, START)
    clock = ManualClock(START + timedelta(seconds=5))  # test `heartbeat_stale_after`: 4 s
    code, detail = asyncio.run(health_detail(settings(migrated_db), config_dir, clock))
    assert code == 1
    assert detail is not None
    assert (detail["status"], detail["components"]["worker"]["status"]) == ("down", "down")


@pytest.mark.spec("T-DB-02")
def test_unmigrated_database_code_1(tmp_path: Path, config_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
    db_path = str(tmp_path / "empty.db")
    sqlite3.connect(db_path).close()
    with capture_logs() as logs:
        code, detail = asyncio.run(health_detail(settings(db_path), config_dir, ManualClock(START)))
    assert (code, detail) == (1, None)
    assert [(e["event"], e["log_level"]) for e in logs] == [("app.refused", "critical")]
    assert capsys.readouterr().out.startswith("failed: database not migrated")


@pytest.mark.spec("T-CFG-10")
def test_invalid_pipeline_code_2(migrated_db: str, config_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
    (config_dir / "pipeline.yaml").write_text("ops:\n  watchdog_timeout: 1s\n", encoding="utf-8")
    with capture_logs() as logs:
        code, detail = asyncio.run(health_detail(settings(migrated_db), config_dir, ManualClock(START)))
    assert (code, detail) == (2, None)
    assert [(e["event"], e["log_level"]) for e in logs] == [("app.refused", "critical")]
    assert capsys.readouterr().out.startswith("failed: invalid configuration")


@pytest.mark.spec("T-CFG-10")
def test_command_result_on_stdout_logs_on_stderr(
    migrated_db: str, config_dir: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RADAR_DB_PATH", migrated_db)
    monkeypatch.setenv("DASHBOARD_URL", "https://radar.example.com")
    write_heartbeat(migrated_db, datetime.now(UTC))
    code, out, err = run_cli(capsys, "health", "--config-dir", str(config_dir))
    assert code == 0, out + err
    assert json.loads(out)["status"] == "ok"
    assert [json.loads(line)["event"] for line in err.splitlines() if "health." in line] == ["health.checked"]
    assert all(isinstance(json.loads(line), dict) for line in err.splitlines())


@pytest.mark.spec("T-CFG-10")
def test_invalid_variables_code_2(
    migrated_db: str, config_dir: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("RADAR_DB_PATH", migrated_db)
    monkeypatch.setenv("DASHBOARD_URL", "https://radar.example.com/")
    code, out, _ = run_cli(capsys, "health", "--config-dir", str(config_dir))
    assert code == 2
    assert out.startswith("invalid configuration: environment variables")
    assert "radar.example.com/" not in out.split("\n", 1)[0]
