"""`python -m app.cli validate-config` and common command contract (IX §56.3, §56.4)."""

import json
import logging
import shutil
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path

import pytest
import structlog

from app.cli.__main__ import main

ROOT = Path(__file__).resolve().parents[3]
REPOSITORY_CONFIG = ROOT / "config"


@pytest.fixture(autouse=True)
def _restore_logging() -> Iterator[None]:
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    yield
    root.handlers[:] = handlers
    root.setLevel(level)
    structlog.reset_defaults()


def run_cli(capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, str, str]:
    try:
        code = main(list(argv))
    except SystemExit as exit_:
        code = int(exit_.code or 0)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


@pytest.mark.spec("T-CFG-01")
def test_repository_config_accepted(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, err = run_cli(capsys, "validate-config", "--config-dir", str(REPOSITORY_CONFIG))
    assert code == 0
    assert out.startswith("valid configuration")
    assert [json.loads(line)["event"] for line in err.splitlines()] == [
        "config.validate.started",
        "config.validate.finished",
    ]


@pytest.mark.spec("T-CFG-01")
def test_module_entry_point_from_the_repository_root() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "app.cli", "validate-config"], cwd=ROOT, capture_output=True, text=True, check=False
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.startswith("valid configuration (config)")
    assert all(json.loads(line)["service"] == "worker" for line in result.stderr.splitlines())


@pytest.mark.spec("T-CFG-10")
def test_invalid_configuration_code_2_result_on_stdout(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    shutil.copytree(REPOSITORY_CONFIG, tmp_path / "config")
    topics = tmp_path / "config" / "topics.yaml"
    topics.write_text(topics.read_text(encoding="utf-8").replace("parent: anthropic", "parent: absent"), "utf-8")
    code, out, err = run_cli(capsys, "validate-config", "--config-dir", str(tmp_path / "config"))
    assert code == 2
    assert "topics.yaml · entry 'claude-code' · field 'parent': parent 'absent' does not exist" in out
    assert "config.validate.invalid" in err and "does not exist" not in err  # logs on stderr, result on stdout


@pytest.mark.spec("T-CFG-10")
def test_missing_required_file_code_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    shutil.copytree(REPOSITORY_CONFIG, tmp_path / "config")
    (tmp_path / "config" / "entities.yaml").unlink()
    code, out, _ = run_cli(capsys, "validate-config", "--config-dir", str(tmp_path / "config"))
    assert code == 2
    assert "entities.yaml: required file missing" in out


@pytest.mark.spec("T-CFG-10")
@pytest.mark.parametrize("argv", [(), ("unknown",), ("validate-config", "--unknown-option")])
def test_invalid_usage_code_2_on_stderr(capsys: pytest.CaptureFixture[str], argv: tuple[str, ...]) -> None:
    code, out, err = run_cli(capsys, *argv)
    assert code == 2
    assert out == ""
    assert "usage:" in err


@pytest.mark.spec("T-CFG-10")
def test_failed_operation_code_1(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    file = tmp_path / "not-a-directory"
    file.write_text("", encoding="utf-8")
    code, out, err = run_cli(capsys, "validate-config", "--config-dir", str(file))
    assert code == 1
    assert out.startswith("failed: cannot read")
    assert "config.validate.failed" in err
