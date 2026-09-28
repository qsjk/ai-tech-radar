"""`scripts/radar-dev` (VIII §46.1, IX §56.3, ADR-0021): fixed subcommands, closed list of services.

The script runs in a sandbox copy of the repository layout, with a fake `docker` (and a fake `uv`) at the head of
`PATH` that record their calls: a refused invocation must record none (T-CFG-11), a valid one exactly the expected
command.
"""

import os
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

from tests.integration.db.conftest import ROOT

SCRIPT = ROOT / "scripts" / "radar-dev"
PROJECT = "radar-dev"
E2E_PROJECT = "radar-dev-e2e"

FAKE = """\
#!/bin/sh
# Fake {name}: records its arguments, one call per line, then exits with {exit_var} (0 by default).
printf '{name}' >> "$FAKE_CALLS"
for arg in "$@"; do printf ' %s' "$arg" >> "$FAKE_CALLS"; done
printf '\\n' >> "$FAKE_CALLS"
exit "${{{exit_var}:-0}}"
"""


class Sandbox:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.calls = root / "calls.log"
        self.bin = root / "fakebin"

    def run(self, *args: str, fake_exit: int = 0, uv_exit: int = 0) -> subprocess.CompletedProcess[str]:
        self.calls.write_text("", encoding="utf-8")
        env = {
            "PATH": f"{self.bin}:/usr/bin:/bin",
            "FAKE_CALLS": str(self.calls),
            "DOCKER_EXIT": str(fake_exit),
            "UV_EXIT": str(uv_exit),
        }
        return subprocess.run(
            [str(self.root / "scripts" / "radar-dev"), *args],
            env=env,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )

    def recorded(self) -> list[str]:
        return self.calls.read_text(encoding="utf-8").splitlines()

    def compose(self, *args: str) -> str:
        base = f"docker compose --project-name {PROJECT} --project-directory {self.root}"
        return f"{base} --file {self.root}/docker-compose.yml --env-file {self.root}/.env {' '.join(args)}"

    def compose_e2e(self, *args: str) -> str:
        base = f"docker compose --project-name {E2E_PROJECT} --project-directory {self.root}"
        files = f"--file {self.root}/docker-compose.yml --file {self.root}/docker-compose.test.yml"
        return f"{base} {files} --env-file {self.root}/.env.example {' '.join(args)}"

    def enable_e2e(self) -> None:
        (self.root / "docker-compose.test.yml").write_text("services: {}\n", encoding="utf-8")
        (self.root / "tests" / "e2e").mkdir(parents=True)


@pytest.fixture
def sandbox(tmp_path: Path) -> Sandbox:
    (tmp_path / "scripts").mkdir()
    shutil.copy(SCRIPT, tmp_path / "scripts" / "radar-dev")
    (tmp_path / "docker-compose.yml").write_text("services: {}\n", encoding="utf-8")
    (tmp_path / ".env").write_text("DASHBOARD_URL=https://localhost\n", encoding="utf-8")
    fakebin = tmp_path / "fakebin"
    fakebin.mkdir()
    for name in ("docker", "uv"):
        fake = fakebin / name
        fake.write_text(FAKE.format(name=name, exit_var=f"{name.upper()}_EXIT"), encoding="utf-8")
        fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    return Sandbox(tmp_path)


@pytest.mark.spec("T-CFG-11")
@pytest.mark.parametrize(
    "argv",
    [
        (),
        ("unknown",),
        ("UP",),
        ("compose",),
        ("up", "--build"),
        ("down", "-v"),
        ("reset", "now"),
        ("ps", "-a"),
        ("logs",),
        ("logs", "db"),
        ("logs", "app", "worker"),
        ("logs", "--tail=5"),
        ("logs", "app; rm -rf /"),
        ("health", "app"),
        ("test", "-k", "x"),
        ("e2e", "--keep"),
    ],
)
def test_out_of_list_exits_2_without_calling_docker(sandbox: Sandbox, argv: tuple[str, ...]) -> None:
    result = sandbox.run(*argv)
    assert result.returncode == 2
    assert result.stdout == ""
    assert result.stderr.startswith("radar-dev: ")
    assert "usage: scripts/radar-dev" in result.stderr
    assert sandbox.recorded() == []


@pytest.mark.spec("T-CFG-11")
def test_missing_env_file_exits_2_without_calling_docker(sandbox: Sandbox) -> None:
    (sandbox.root / ".env").unlink()
    result = sandbox.run("up")
    assert result.returncode == 2
    assert ".env.example" in result.stderr
    assert sandbox.recorded() == []


@pytest.mark.spec("T-CFG-11")
@pytest.mark.parametrize(
    ("argv", "expected"),
    [
        (("up",), [("up", "--detach", "--build")]),
        (("down",), [("down",)]),
        (("reset",), [("down", "--volumes"), ("up", "--detach", "--build")]),
        (("ps",), [("ps", "--all")]),
        (("logs", "migrate"), [("logs", "--no-color", "migrate")]),
        (("logs", "app"), [("logs", "--no-color", "app")]),
        (("logs", "worker"), [("logs", "--no-color", "worker")]),
        (("logs", "caddy"), [("logs", "--no-color", "caddy")]),
        (("health",), [("exec", "-T", "app", "python", "-m", "app.cli", "health")]),
    ],
)
def test_valid_command_builds_the_expected_docker_call(
    sandbox: Sandbox, argv: tuple[str, ...], expected: list[tuple[str, ...]]
) -> None:
    result = sandbox.run(*argv)
    assert result.returncode == 0, result.stderr
    assert sandbox.recorded() == [sandbox.compose(*call) for call in expected]


@pytest.mark.spec("T-CFG-11")
def test_project_is_the_dedicated_development_one() -> None:
    text = SCRIPT.read_text(encoding="utf-8")
    assert f'readonly PROJECT="{PROJECT}"' in text
    assert PROJECT not in ("radar", "radar-load")


@pytest.mark.spec("T-CFG-11")
def test_test_runs_the_local_pytest_suite_without_docker(sandbox: Sandbox) -> None:
    (sandbox.root / ".env").unlink()  # the local suite needs no .env
    result = sandbox.run("test")
    assert result.returncode == 0, result.stderr
    assert sandbox.recorded() == ["uv run pytest"]


@pytest.mark.spec("T-CFG-11")
def test_docker_failure_exits_1(sandbox: Sandbox) -> None:
    result = sandbox.run("up", fake_exit=3)
    assert result.returncode == 1
    assert "docker compose up failed" in result.stderr


@pytest.mark.spec("T-CFG-11")
def test_e2e_without_override_or_tests_exits_1_without_calling_docker(sandbox: Sandbox) -> None:
    result = sandbox.run("e2e")
    assert result.returncode == 1
    assert "e2e is not available" in result.stderr
    assert sandbox.recorded() == []


E2E_UP = ("up", "--detach", "--build", "--wait", "--wait-timeout", "180")
E2E_DOWN = ("down", "--volumes", "--remove-orphans")


@pytest.mark.spec("T-CFG-11")
def test_e2e_runs_in_its_own_project_then_removes_it(sandbox: Sandbox) -> None:
    sandbox.enable_e2e()
    (sandbox.root / ".env").unlink()  # the e2e stack needs no local .env
    result = sandbox.run("e2e")
    assert result.returncode == 0, result.stderr
    assert sandbox.recorded() == [
        sandbox.compose_e2e(*E2E_UP),
        f"uv run pytest -m e2e --no-cov -p no:cacheprovider {sandbox.root}/tests/e2e",
        sandbox.compose_e2e(*E2E_DOWN),
    ]
    assert all(f"--project-name {PROJECT} " not in call for call in sandbox.recorded())


@pytest.mark.spec("T-CFG-11")
def test_e2e_failing_tests_exit_1_and_still_remove_the_project(sandbox: Sandbox) -> None:
    sandbox.enable_e2e()
    result = sandbox.run("e2e", uv_exit=1)
    assert result.returncode == 1
    assert "e2e tests failed" in result.stderr
    assert sandbox.recorded()[-1] == sandbox.compose_e2e(*E2E_DOWN)


@pytest.mark.spec("T-CFG-11")
def test_e2e_stack_that_does_not_start_exits_1_and_is_removed(sandbox: Sandbox) -> None:
    sandbox.enable_e2e()
    result = sandbox.run("e2e", fake_exit=1)
    assert result.returncode == 1
    assert "the e2e stack did not start" in result.stderr
    assert sandbox.recorded() == [sandbox.compose_e2e(*E2E_UP), sandbox.compose_e2e(*E2E_DOWN)]


@pytest.mark.spec("T-CFG-11")
def test_script_is_executable() -> None:
    assert os.access(SCRIPT, os.X_OK)


@pytest.mark.spec("T-CFG-11")
def test_e2e_project_is_shared_by_the_script_and_the_e2e_harness() -> None:
    from tests.e2e.conftest import PROJECT as HARNESS_PROJECT

    assert HARNESS_PROJECT == E2E_PROJECT
    assert f'readonly E2E_PROJECT="{E2E_PROJECT}"' in SCRIPT.read_text(encoding="utf-8")
