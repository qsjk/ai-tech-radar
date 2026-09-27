"""Process-level worker: `python -m app.worker` as a subprocess, on a temporary migrated database.

Refusal to start, non-zero exit, SIGTERM and real watchdog. Short settings in the test `pipeline.yaml`; every wait is
bounded (log reads with a timeout, `wait(timeout=...)`), without sleep.
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
from tests.integration.process import Process, coverage_variables

# Makes the heartbeat inert in the subprocess: the loop freezes, the watchdog must stop the process.
FROZEN_LOOP = """\
import sys, time
from app import worker
from app.ops.heartbeat import Heartbeat

async def freeze(self):
    time.sleep(3600)

Heartbeat.run = freeze
sys.exit(worker.main(sys.argv[1:]))
"""


def environment(db_path: str, **variables: str) -> dict[str, str]:
    """Minimal, hermetic environment: only the useful variables, fake secrets."""
    env = {
        "PATH": os.environ["PATH"],
        "RADAR_DB_PATH": db_path,
        "DASHBOARD_URL": "https://radar.example.com",
        "HTTP_CONTACT": "https://example.com/contact",
        "RADAR_VERSION": "abc1234",
        "SMTP_PASSWORD": "FAKE-smtp-password",
    }
    env.update(variables)
    env.update(coverage_variables())
    return {name: value for name, value in env.items() if value}


@pytest.fixture
def launch(config_dir: Path) -> Iterator[Any]:
    launched: list[Process] = []

    def _launch(env: dict[str, str], *, code: str | None = None) -> Process:
        args = [sys.executable, "-c", code] if code else [sys.executable, "-m", "app.worker"]
        process = Process([*args, "--config-dir", str(config_dir)], env)
        launched.append(process)
        return process

    yield _launch
    for process in launched:
        process.stop()


def read_heartbeat(db_path: str) -> dict[str, Any]:
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute("SELECT value FROM system_state WHERE key = ?", (HEARTBEAT_KEY,)).fetchone()
    finally:
        conn.close()
    value: dict[str, Any] = json.loads(row[0])
    return value


@pytest.mark.spec("T-CFG-05")
def test_missing_http_contact_refused(launch: Any, migrated_db: str) -> None:
    worker = launch(environment(migrated_db, HTTP_CONTACT=""))
    refusal = worker.wait_for_log("worker.refused")
    assert worker.wait_for_exit() == 2
    assert refusal["level"] == "critical"
    assert refusal["problems"] == ["HTTP_CONTACT: Field required"]
    assert worker.events() == ["worker.refused"]


@pytest.mark.spec("T-CFG-07")
@pytest.mark.parametrize(
    "url", ["ftp://radar.example.com", "https://radar.example.com/", "https://radar.example.com:8443"]
)
def test_invalid_dashboard_url_refused(launch: Any, migrated_db: str, url: str) -> None:
    worker = launch(environment(migrated_db, DASHBOARD_URL=url))
    refusal = worker.wait_for_log("worker.refused")
    assert worker.wait_for_exit() == 2
    assert refusal["level"] == "critical"
    assert "DASHBOARD_URL" in " ".join(refusal["problems"])


@pytest.mark.spec("T-DB-02")
def test_unmigrated_database_refused(launch: Any, tmp_path: Path) -> None:
    db_path = str(tmp_path / "empty.db")
    sqlite3.connect(db_path).close()
    worker = launch(environment(db_path))
    refusal = worker.wait_for_log("worker.refused")
    assert worker.wait_for_exit() == 1
    assert (refusal["level"], refusal["error_class"]) == ("critical", "SchemaRevisionError")
    assert "head" in refusal["reason"]


@pytest.mark.spec("T-OPS-10:verifications")
@pytest.mark.spec("T-OPS-10:heartbeat")
@pytest.mark.spec("T-OPS-11:arret")
def test_sigterm_clean_stop_code_0(launch: Any, migrated_db: str) -> None:
    worker = launch(environment(migrated_db))
    start = worker.wait_for_log("worker.started")
    heartbeat = read_heartbeat(migrated_db)
    assert heartbeat["pid"] == start["pid"] == worker.popen.pid
    assert heartbeat["version"] == "abc1234"
    begin = time.monotonic()
    worker.popen.send_signal(signal.SIGTERM)
    assert worker.wait_for_exit() == 0
    assert time.monotonic() - begin < 20
    assert "FAKE-" not in json.dumps(worker.logs)
    assert worker.events() == [
        "worker.boot.started",
        "worker.boot.checked",
        "worker.heartbeat.started",
        "worker.started",
        "worker.stop.requested",
        "worker.stopped",
    ]


@pytest.mark.spec("T-OPS-08:heartbeat")
def test_heartbeat_exception_exits_non_zero(launch: Any, migrated_db: str) -> None:
    worker = launch(environment(migrated_db))
    worker.wait_for_log("worker.started")
    conn = sqlite3.connect(migrated_db)
    conn.execute("DROP TABLE system_state")
    conn.commit()
    conn.close()
    failure = worker.wait_for_log("worker.task.failed")
    assert worker.wait_for_exit() == 1
    assert (failure["level"], failure["task"]) == ("critical", "heartbeat")
    assert "no such table" in failure["exception"]


@pytest.mark.spec("T-OPS-07")
def test_frozen_loop_watchdog_stops_the_process(launch: Any, migrated_db: str) -> None:
    worker = launch(environment(migrated_db), code=FROZEN_LOOP)
    worker.wait_for_log("worker.started")
    alert = worker.wait_for_log("worker.watchdog.timeout")
    assert worker.wait_for_exit() == 1
    assert (alert["level"], alert["timeout_s"]) == ("critical", 10.0)
    assert "worker.stopped" not in worker.events()
