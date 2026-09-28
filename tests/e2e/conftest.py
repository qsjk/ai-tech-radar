"""e2e harness (VIII §49.2 stage 6): tests run on the host against the Compose stack, never inside the images.

The stack is started by `scripts/radar-dev e2e` in the dedicated project `radar-dev-e2e` (docker-compose.yml plus
docker-compose.test.yml), and removed afterwards. The tests reach it through Caddy on https://localhost:8443 only; the
network stays limited to the local host (pytest-socket). Caddy's certificate is verified against its internal CA,
read from the caddy container. Waits are bounded (VIII §49.3).
"""

import json
import ssl
import subprocess
import time
from collections.abc import Iterator, Sequence
from pathlib import Path
from typing import Any

import httpx2
import pytest

ROOT = Path(__file__).resolve().parents[2]
PROJECT = "radar-dev-e2e"
COMPOSE_FILES = (ROOT / "docker-compose.yml", ROOT / "docker-compose.test.yml")
BASE_URL = "https://localhost:8443"
USER = "FAKE-e2e-user"
PASSWORD = "FAKE-dashboard-password"
CA_PATH = "/data/caddy/pki/authorities/local/root.crt"
TIMEOUT = 60.0
"""Bound of every wait, in seconds."""


def compose_command(project: str, files: Sequence[Path]) -> list[str]:
    command = ["docker", "compose", "--project-name", project, "--project-directory", str(ROOT)]
    for file in files:
        command += ["--file", str(file)]
    return [*command, "--env-file", str(ROOT / ".env.example")]


def compose(
    *args: str, project: str = PROJECT, files: Sequence[Path] = COMPOSE_FILES
) -> subprocess.CompletedProcess[str]:
    """`docker compose` on an e2e project, with fixed arguments; never radar nor radar-dev."""
    assert project.startswith("radar-dev-e2e")
    return subprocess.run(
        [*compose_command(project, files), *args], capture_output=True, text=True, timeout=300, check=False
    )


def services(project: str = PROJECT, files: Sequence[Path] = COMPOSE_FILES) -> dict[str, dict[str, Any]]:
    """State of every container of the project, by service (`ps --all --format json`)."""
    result = compose("ps", "--all", "--format", "json", project=project, files=files)
    assert result.returncode == 0, result.stderr
    entries = [json.loads(line) for line in result.stdout.splitlines() if line.strip()]
    return {entry["Service"]: entry for entry in entries}


def logs(service: str) -> list[dict[str, Any]]:
    """JSON log lines of one service of the e2e stack."""
    result = compose("logs", "--no-color", "--no-log-prefix", service)
    assert result.returncode == 0, result.stderr
    lines = []
    for line in result.stdout.splitlines():
        try:
            lines.append(json.loads(line))
        except json.JSONDecodeError:
            lines.append({"raw": line})
    return lines


def ca_context(tmp_dir: Path, project: str = PROJECT, files: Sequence[Path] = COMPOSE_FILES) -> ssl.SSLContext:
    """TLS context that trusts only the internal CA of the project's Caddy (read once it exists)."""
    deadline = time.monotonic() + TIMEOUT
    while True:
        result = compose("exec", "-T", "caddy", "cat", CA_PATH, project=project, files=files)
        if result.returncode == 0 and "BEGIN CERTIFICATE" in result.stdout:
            break
        if time.monotonic() > deadline:
            raise AssertionError(f"no internal CA in {project}: {result.stderr}")
        time.sleep(1)
    path = tmp_dir / f"{project}-root.crt"
    path.write_text(result.stdout, encoding="utf-8")
    return ssl.create_default_context(cafile=str(path))


def wait_for(client: httpx2.Client, path: str, status: int) -> httpx2.Response:
    """Poll `path` until it answers `status`, within the bound."""
    deadline = time.monotonic() + TIMEOUT
    while True:
        try:
            response = client.get(path)
            if response.status_code == status:
                return response
        except httpx2.TransportError:
            pass
        if time.monotonic() > deadline:
            raise AssertionError(f"{path} did not answer {status} within {TIMEOUT} s")
        time.sleep(1)


@pytest.fixture(scope="session")
def tls(tmp_path_factory: pytest.TempPathFactory) -> ssl.SSLContext:
    return ca_context(tmp_path_factory.mktemp("ca"))


@pytest.fixture(scope="session")
def client(tls: ssl.SSLContext) -> Iterator[httpx2.Client]:
    """Anonymous client; waits until /health answers 200 (worker heartbeat written)."""
    with httpx2.Client(base_url=BASE_URL, verify=tls, timeout=10) as client:
        wait_for(client, "/health", 200)
        yield client


@pytest.fixture(scope="session")
def auth_client(tls: ssl.SSLContext, client: httpx2.Client) -> Iterator[httpx2.Client]:
    with httpx2.Client(base_url=BASE_URL, verify=tls, timeout=10, auth=(USER, PASSWORD)) as auth_client:
        yield auth_client
