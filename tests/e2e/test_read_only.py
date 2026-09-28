"""Read-only root filesystem working for Python, uvicorn and Alembic, without restic (T-SEC-09 [base], VIII §47.2)."""

import json

import httpx2
import pytest

from tests.e2e.conftest import compose, logs, services

pytestmark = [pytest.mark.e2e, pytest.mark.spec("T-SEC-09:base")]

PROBE = """
import errno, json, os
result = {"root_read_only": bool(os.statvfs("/").f_flag & os.ST_RDONLY)}
for path in ("/app/probe", "/probe", "/usr/probe"):
    try:
        open(path, "w").close()
        result[path] = "written"
    except OSError as error:
        result[path] = errno.errorcode[error.errno]
for path in ("/tmp/probe", "/data/probe"):
    with open(path, "w") as file:
        file.write("ok")
    os.remove(path)
    result[path] = "written"
print(json.dumps(result))
"""


def test_migrate_ran_alembic_then_exited_0() -> None:
    migrate = services()["migrate"]
    assert (migrate["State"], migrate["ExitCode"]) == ("exited", 0)
    events = [str(entry.get("event", "")) for entry in logs("migrate")]
    assert any(event.startswith("Running upgrade") for event in events) or "Context impl SQLiteImpl." in events


@pytest.mark.parametrize("service", ["app", "worker"])
def test_root_is_read_only_and_only_tmp_and_data_are_writable(service: str) -> None:
    assert services()[service]["State"] == "running"
    result = compose("exec", "-T", service, "python", "-c", PROBE)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "root_read_only": True,
        "/app/probe": "EROFS",
        "/probe": "EROFS",
        "/usr/probe": "EROFS",
        "/tmp/probe": "written",
        "/data/probe": "written",
    }


def test_python_uvicorn_and_worker_work_on_the_read_only_root(auth_client: httpx2.Client) -> None:
    detail = auth_client.get("/api/health").json()
    assert detail["status"] == "ok"
    assert detail["components"]["database"]["schema_revision"] == "0001"
    assert detail["components"]["worker"]["status"] == "ok"


@pytest.mark.parametrize("service", ["migrate", "app", "worker"])
def test_no_write_error_in_the_logs(service: str) -> None:
    text = json.dumps(logs(service)).lower()
    assert "read-only file system" not in text
    assert "traceback" not in text
