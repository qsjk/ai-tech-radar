"""Process-level app: `uvicorn app.main:app` as a subprocess, on 127.0.0.1, port chosen by the system.

Refusal to start (T-CFG-07, T-DB-02, invalid `pipeline.yaml`), nominal start, real `/health`, stop on SIGTERM. Every
wait is bounded; none is a sleep.
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
from tests.integration.process import TIMEOUT, Process, coverage_variables

COMMAND = [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "0"]
COMMAND += ["--workers", "1", "--no-access-log"]

# Simulates, in the subprocess, a SQLite library that is too old and lacks FTS5, then runs the real uvicorn.
OLD_SQLITE = """\
import sys
import uvicorn
from app.db import prerequisites

async def probe(engine):
    return prerequisites.SqliteFeatures(version="3.34.1", fts5=False, json1=True)

prerequisites.probe_features = probe
sys.argv = ["uvicorn", *sys.argv[1:]]
uvicorn.main()
"""

UVICORN_STARTUP_FAILURE = 3
"""uvicorn exit code when the lifespan fails."""


def environment(db_path: str, **variables: str) -> dict[str, str]:
    """Minimal, hermetic environment: only the useful variables, fake secrets."""
    env = {
        "PATH": os.environ["PATH"],
        "RADAR_DB_PATH": db_path,
        "DASHBOARD_URL": "https://radar.example.com",
        "RADAR_VERSION": "abc1234",
        "DASHBOARD_PASSWORD_HASH": "FAKE-hash",
    }
    env.update(variables)
    env.update(coverage_variables())
    return {name: value for name, value in env.items() if value}


@pytest.fixture
def workdir(tmp_path: Path, config_dir: Path) -> Path:
    """Working directory of the app: relative `config/`, as `/app` in the image."""
    root = tmp_path / "app"
    root.mkdir()
    shutil.copytree(config_dir, root / "config")
    return root


@pytest.fixture
def launch(workdir: Path) -> Iterator[Any]:
    launched: list[Process] = []

    def _launch(env: dict[str, str], *, code: str | None = None) -> Process:
        command = [sys.executable, "-c", code, *COMMAND[3:]] if code else COMMAND
        process = Process(command, env, cwd=workdir)
        launched.append(process)
        return process

    yield _launch
    for process in launched:
        process.stop()


def get(url: str) -> tuple[int, bytes]:
    try:
        with urllib.request.urlopen(url, timeout=TIMEOUT) as response:  # noqa: S310 — 127.0.0.1 only
            return int(response.status), bytes(response.read())
    except urllib.error.HTTPError as error:
        return int(error.code), bytes(error.read())


def write_fresh_heartbeat(db_path: str) -> None:
    now = datetime.now(UTC).isoformat()
    value = {"at": now, "started_at": now, "version": "w-1", "pid": 4242}
    conn = sqlite3.connect(db_path)
    try:
        conn.execute(
            "INSERT OR REPLACE INTO system_state (key, value, updated_at) VALUES (?, ?, ?)",
            (HEARTBEAT_KEY, json.dumps(value), now),
        )
        conn.commit()
    finally:
        conn.close()


@pytest.mark.spec("T-CFG-07")
@pytest.mark.parametrize(
    "url", ["ftp://radar.example.com", "https://radar.example.com/", "https://radar.example.com:8443"]
)
def test_invalid_dashboard_url_refused(launch: Any, migrated_db: str, url: str) -> None:
    app = launch(environment(migrated_db, DASHBOARD_URL=url))
    refusal = app.wait_for_log("app.refused")
    assert app.wait_for_exit() == 2
    assert refusal["level"] == "critical"
    assert refusal["service"] == "app"
    assert "DASHBOARD_URL" in " ".join(refusal["problems"])
    assert "Uvicorn running" not in json.dumps(app.logs)


@pytest.mark.spec("T-DB-02")
def test_unmigrated_database_refused(launch: Any, tmp_path: Path) -> None:
    db_path = str(tmp_path / "empty.db")
    sqlite3.connect(db_path).close()
    app = launch(environment(db_path))
    refusal = app.wait_for_log("app.refused")
    assert app.wait_for_exit() == UVICORN_STARTUP_FAILURE
    assert (refusal["level"], refusal["error_class"]) == ("critical", "SchemaRevisionError")
    assert "Uvicorn running" not in json.dumps(app.logs)


@pytest.mark.spec("T-DB-01")
def test_missing_sqlite_prerequisites_refused(launch: Any, migrated_db: str) -> None:
    app = launch(environment(migrated_db), code=OLD_SQLITE)
    refusal = app.wait_for_log("app.refused")
    assert app.wait_for_exit() == UVICORN_STARTUP_FAILURE
    assert (refusal["level"], refusal["error_class"]) == ("critical", "PrerequisiteError")
    assert "SQLite 3.34.1 too old" in refusal["reason"]
    assert "FTS5 extension missing" in refusal["reason"]
    assert "Uvicorn running" not in json.dumps(app.logs)


@pytest.mark.spec("T-CFG-02:schemas")
def test_invalid_pipeline_refused_with_the_worker_message(launch: Any, migrated_db: str, workdir: Path) -> None:
    (workdir / "config" / "pipeline.yaml").write_text("ops:\n  heartbeat_stale_after: soon\n", encoding="utf-8")
    app = launch(environment(migrated_db))
    refusal = app.wait_for_log("app.refused")
    assert app.wait_for_exit() == UVICORN_STARTUP_FAILURE
    assert refusal["level"] == "critical"
    assert refusal["reason"] == "invalid configuration (config)"
    assert refusal["issues"] and "pipeline.yaml" in refusal["issues"][0]
    assert "heartbeat_stale_after" in refusal["issues"][0]


@pytest.mark.spec("T-OPS-01")
def test_start_real_health_without_access_log_then_sigterm(launch: Any, migrated_db: str) -> None:
    write_fresh_heartbeat(migrated_db)
    app = launch(environment(migrated_db))
    start = app.wait_for_log("app.started")
    listening = app.wait_for_log("Uvicorn running on ", prefix=True)
    port = re.search(r"http://127\.0\.0\.1:(\d+)", listening["event"])
    assert port is not None
    base = f"http://127.0.0.1:{port.group(1)}"

    assert get(f"{base}/health") == (200, b'{"status":"ok"}')
    code, body = get(f"{base}/api/health")
    assert code == 200
    detail = json.loads(body)
    assert (detail["status"], detail["version"]) == ("ok", "abc1234")
    assert detail["components"]["database"]["schema_revision"] == "0001"
    assert get(f"{base}/docs")[0] == 404

    app.popen.send_signal(signal.SIGTERM)
    # uvicorn stops cleanly (lifespan closed, `app.stopped`), then re-raises the received signal: ends by SIGTERM.
    assert app.wait_for_exit() == -signal.SIGTERM
    assert "Application shutdown complete." in app.events("Application")
    journal = json.dumps(app.logs)
    assert (start["level"], start["service"]) == ("info", "app")
    assert all(entry["event"] is not None for entry in app.logs), "every line is JSON"
    assert "GET /health" not in journal, "no access log (VII §42.3)"
    assert "FAKE-" not in journal
    assert app.events("app.") == ["app.started", "app.stopped"]


@pytest.mark.spec("T-OPS-02")
def test_health_down_without_heartbeat(launch: Any, migrated_db: str) -> None:
    app = launch(environment(migrated_db))
    listening = app.wait_for_log("Uvicorn running on ", prefix=True)
    port = re.search(r"http://127\.0\.0\.1:(\d+)", listening["event"])
    assert port is not None
    assert get(f"http://127.0.0.1:{port.group(1)}/health") == (503, b'{"status":"down"}')
