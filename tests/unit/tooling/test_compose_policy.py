"""Compose policy (T-SEC-08) on the output of `docker compose config` with `.env.example` (VII §36, §43.2).

Only caddy publishes ports; the Docker socket is never mounted; variables are distributed per service (VII §36.7),
`app` receiving no secret; non-root user, `cap_drop: ALL`, `no-new-privileges` and `read_only` on every service, no
`cap_add`, caddy included (uid 10001). The `gateway` service, under a profile, is out of the default configuration: its
hardening comes with its choice in Sprint 6 (A-06).
"""

import copy
import json
import shutil
import subprocess
from typing import Any

import pytest

from tests.integration.db.conftest import ROOT

pytestmark = pytest.mark.spec("T-SEC-08")

HARDENED = ("migrate", "app", "worker", "caddy")
ALLOWED_ENV = {
    "migrate": {"TZ", "RADAR_DB_PATH", "LOG_LEVEL"},
    "app": {"TZ", "RADAR_DB_PATH", "APP_ENV", "LOG_LEVEL", "DASHBOARD_URL", "RADAR_VERSION"},
    "caddy": {"DASHBOARD_URL", "DASHBOARD_USER", "DASHBOARD_PASSWORD_HASH", "ACME_EMAIL"},
}
CADDY_ONLY_ENV = {"DASHBOARD_USER", "DASHBOARD_PASSWORD_HASH", "ACME_EMAIL"}


def violations(config: dict[str, Any]) -> list[str]:
    """Every breach of the policy in a `docker compose config --format json` document."""
    found: list[str] = []
    services: dict[str, dict[str, Any]] = config["services"]
    missing = set(HARDENED) - set(services)
    found += [f"{name}: service missing" for name in sorted(missing)]
    for name, service in services.items():
        if service.get("ports") and name != "caddy":
            found.append(f"{name}: publishes ports")
        for volume in service.get("volumes", []):
            if "docker.sock" in str(volume.get("source", "")) or "docker.sock" in str(volume.get("target", "")):
                found.append(f"{name}: mounts the Docker socket")
        if service.get("cap_add"):
            found.append(f"{name}: cap_add {service['cap_add']}")
        if service.get("privileged"):
            found.append(f"{name}: privileged")
    for name in HARDENED:
        service = services.get(name)
        if service is None:
            continue
        user = str(service.get("user", ""))
        if not user or user.split(":")[0] in ("0", "root"):
            found.append(f"{name}: runs as root")
        if "ALL" not in service.get("cap_drop", []):
            found.append(f"{name}: cap_drop without ALL")
        if "no-new-privileges:true" not in service.get("security_opt", []):
            found.append(f"{name}: no-new-privileges missing")
        if service.get("read_only") is not True:
            found.append(f"{name}: root filesystem not read-only")
        env = set(service.get("environment") or {})
        if name in ALLOWED_ENV and env - ALLOWED_ENV[name]:
            found.append(f"{name}: unexpected variables {sorted(env - ALLOWED_ENV[name])}")
        if name == "worker" and env & CADDY_ONLY_ENV:
            found.append(f"worker: caddy variables {sorted(env & CADDY_ONLY_ENV)}")
    caddy = services.get("caddy", {})
    if caddy and str(caddy.get("user")) != "10001:10001":
        found.append(f"caddy: user {caddy.get('user')!r}, 10001:10001 expected")
    return found


@pytest.fixture(scope="module")
def compose_config() -> dict[str, Any]:
    docker = shutil.which("docker")
    if docker is None:
        pytest.skip("docker is not installed: the Compose policy needs `docker compose config`")
    result = subprocess.run(
        [docker, "compose", "--env-file", ".env.example", "config", "--format", "json"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    config: dict[str, Any] = json.loads(result.stdout)
    return config


def test_repository_compose_respects_the_policy(compose_config: dict[str, Any]) -> None:
    assert sorted(compose_config["services"]) == ["app", "caddy", "migrate", "worker"]
    assert violations(compose_config) == []


def test_app_receives_no_secret(compose_config: dict[str, Any]) -> None:
    env = set(compose_config["services"]["app"]["environment"])
    assert env == ALLOWED_ENV["app"]


@pytest.mark.parametrize(
    ("change", "expected"),
    [
        (lambda s: s["app"].update(ports=[{"target": 8000, "published": "8000"}]), "app: publishes ports"),
        (
            lambda s: s["worker"]["volumes"].append({"type": "bind", "source": "/var/run/docker.sock"}),
            "worker: mounts the Docker socket",
        ),
        (lambda s: s["app"]["environment"].update(GITHUB_TOKEN="x"), "app: unexpected variables ['GITHUB_TOKEN']"),
        (lambda s: s["worker"]["environment"].update(ACME_EMAIL="x"), "worker: caddy variables ['ACME_EMAIL']"),
        (lambda s: s["caddy"].update(cap_add=["NET_BIND_SERVICE"]), "caddy: cap_add ['NET_BIND_SERVICE']"),
        (lambda s: s["worker"].update(user="0:0"), "worker: runs as root"),
        (lambda s: s["caddy"].pop("user"), "caddy: runs as root"),
        (lambda s: s["app"].update(cap_drop=[]), "app: cap_drop without ALL"),
        (lambda s: s["caddy"].update(security_opt=[]), "caddy: no-new-privileges missing"),
        (lambda s: s["worker"].update(read_only=False), "worker: root filesystem not read-only"),
        (lambda s: s["caddy"].update(user="10002:10002"), "caddy: user '10002:10002', 10001:10001 expected"),
    ],
)
def test_each_breach_is_detected(compose_config: dict[str, Any], change: Any, expected: str) -> None:
    config = copy.deepcopy(compose_config)
    change(config["services"])
    assert expected in violations(config)
