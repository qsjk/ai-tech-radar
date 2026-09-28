"""Failure of migrate (T-RES-10, VII §36.3): app and worker do not start, and /health answers 502.

Runs in a throwaway project, `radar-dev-e2e-migrate-failure`, with the e2e images already built and its own host ports;
the project is removed with its volumes at the end, whatever the outcome.
"""

from collections.abc import Iterator
from pathlib import Path

import httpx2
import pytest

from tests.e2e.conftest import COMPOSE_FILES, ca_context, compose, services, wait_for

pytestmark = [pytest.mark.e2e, pytest.mark.spec("T-RES-10")]

PROJECT = "radar-dev-e2e-migrate-failure"
FAILURE = """\
services:
  migrate:
    # An unknown revision: alembic exits with a non-zero code.
    command: ["alembic", "upgrade", "does-not-exist"]
  caddy:
    ports: !override ["8081:80", "8444:443"]
"""


@pytest.fixture(scope="module")
def failed_stack(tmp_path_factory: pytest.TempPathFactory) -> Iterator[tuple[list[Path], Path]]:
    directory = tmp_path_factory.mktemp("migrate-failure")
    override = directory / "docker-compose.migrate-failure.yml"
    override.write_text(FAILURE, encoding="utf-8")
    files = [*COMPOSE_FILES, override]
    try:
        up = compose("up", "--detach", project=PROJECT, files=files)
        assert up.returncode != 0, "up must fail when migrate fails"
        yield files, directory
    finally:
        compose("down", "--volumes", "--remove-orphans", project=PROJECT, files=files)


def test_app_and_worker_do_not_start(failed_stack: tuple[list[Path], Path]) -> None:
    files, _ = failed_stack
    state = services(project=PROJECT, files=files)
    assert state["migrate"]["State"] == "exited" and state["migrate"]["ExitCode"] != 0
    assert state["app"]["State"] == "created"
    assert state["worker"]["State"] == "created"
    assert state["caddy"]["State"] == "running"


def test_health_answers_502(failed_stack: tuple[list[Path], Path]) -> None:
    files, directory = failed_stack
    tls = ca_context(directory, project=PROJECT, files=files)
    with httpx2.Client(base_url="https://localhost:8444", verify=tls, timeout=10) as client:
        response = wait_for(client, "/health", 502)
    assert response.status_code == 502
