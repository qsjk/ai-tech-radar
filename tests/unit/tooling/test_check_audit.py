"""`scripts/check-audit.py`, stage 3 of the CI (VIII §49.4): audits confronted with the exceptions file."""

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from tests.integration.db.conftest import ROOT

SCRIPT = ROOT / "scripts" / "check-audit.py"
TODAY = "2026-09-28"
PIP_CLEAN: dict[str, Any] = {"dependencies": [{"name": "fastapi", "version": "0.141.1", "vulns": []}]}
PIP_VULN: dict[str, Any] = {
    "dependencies": [
        {"name": "Jinja2", "version": "3.0.0", "vulns": [{"id": "PYSEC-2099-1", "aliases": ["GHSA-aaaa"]}]}
    ]
}
NPM_CLEAN: dict[str, Any] = {"vulnerabilities": {}}


def npm(severity: str) -> dict[str, Any]:
    via = [{"source": 1, "url": "https://github.com/advisories/GHSA-bbbb", "severity": severity}]
    return {"vulnerabilities": {"vite": {"severity": severity, "via": via}}}


def run(tmp_path: Path, pip: Any, npm_report: Any, exceptions: str) -> subprocess.CompletedProcess[str]:
    (tmp_path / "pip.json").write_text(json.dumps(pip), encoding="utf-8")
    (tmp_path / "npm.json").write_text(json.dumps(npm_report), encoding="utf-8")
    (tmp_path / "exceptions.yaml").write_text(exceptions, encoding="utf-8")
    command = [sys.executable, str(SCRIPT), "--pip-audit", str(tmp_path / "pip.json")]
    command += ["--npm-audit", str(tmp_path / "npm.json"), "--exceptions", str(tmp_path / "exceptions.yaml")]
    return subprocess.run([*command, "--today", TODAY], capture_output=True, text=True, timeout=30, check=False)


def exception(identifier: str, package: str, expires: str) -> str:
    return (
        f"exceptions:\n  - id: {identifier}\n    package: {package}\n"
        f"    justification: not reachable in this product\n    expires: {expires}\n"
    )


def test_clean_audits_and_empty_exceptions_pass(tmp_path: Path) -> None:
    result = run(tmp_path, PIP_CLEAN, NPM_CLEAN, "exceptions: []\n")
    assert result.returncode == 0
    assert result.stdout.rstrip().endswith("result: OK")


def test_repository_exceptions_file_is_valid(tmp_path: Path) -> None:
    result = run(tmp_path, PIP_CLEAN, NPM_CLEAN, (ROOT / ".audit-exceptions.yaml").read_text(encoding="utf-8"))
    assert result.returncode == 0, result.stdout + result.stderr


def test_backend_vulnerability_blocks(tmp_path: Path) -> None:
    result = run(tmp_path, PIP_VULN, NPM_CLEAN, "exceptions: []\n")
    assert result.returncode == 1
    assert "BLOCKING pip jinja2" in result.stdout


@pytest.mark.parametrize(("severity", "code"), [("critical", 1), ("high", 1), ("moderate", 0), ("low", 0)])
def test_frontend_high_and_critical_block_moderate_is_reported(tmp_path: Path, severity: str, code: int) -> None:
    result = run(tmp_path, PIP_CLEAN, npm(severity), "exceptions: []\n")
    assert result.returncode == code
    assert ("BLOCKING npm vite" in result.stdout) == (code == 1)
    assert ("(non-blocking)" in result.stdout) == (code == 0)


def test_valid_exception_covers_the_finding(tmp_path: Path) -> None:
    exceptions = exception("GHSA-aaaa", "jinja2", "2026-12-01") + exception("GHSA-bbbb", "vite", "2026-10-15")[12:]
    result = run(tmp_path, PIP_VULN, npm("high"), exceptions)
    assert result.returncode == 0, result.stdout
    assert "excepted pip jinja2" in result.stdout and "excepted npm vite" in result.stdout


def test_expired_exception_fails_the_stage(tmp_path: Path) -> None:
    result = run(tmp_path, PIP_VULN, NPM_CLEAN, exception("GHSA-aaaa", "jinja2", "2026-09-27"))
    assert result.returncode == 1
    assert "expired on 2026-09-27" in result.stdout
    assert "BLOCKING pip jinja2" in result.stdout


def test_exception_expiring_more_than_90_days_ahead_fails(tmp_path: Path) -> None:
    result = run(tmp_path, PIP_VULN, NPM_CLEAN, exception("GHSA-aaaa", "jinja2", "2026-12-28"))
    assert result.returncode == 1
    assert "more than 90 days ahead" in result.stdout


def test_incomplete_exception_fails(tmp_path: Path) -> None:
    result = run(tmp_path, PIP_CLEAN, NPM_CLEAN, "exceptions:\n  - id: GHSA-aaaa\n    package: jinja2\n")
    assert result.returncode == 1
    assert "are all required" in result.stdout


@pytest.mark.parametrize(
    ("pip_text", "exceptions"),
    [("{", "exceptions: []\n"), (json.dumps(PIP_CLEAN), "exceptions: {}\n"), ('{"x": 1}', "exceptions: []\n")],
)
def test_unreadable_input_exits_2(tmp_path: Path, pip_text: str, exceptions: str) -> None:
    run(tmp_path, PIP_CLEAN, NPM_CLEAN, exceptions)
    (tmp_path / "pip.json").write_text(pip_text, encoding="utf-8")
    command = [sys.executable, str(SCRIPT), "--pip-audit", str(tmp_path / "pip.json"), "--today", TODAY]
    command += ["--npm-audit", str(tmp_path / "npm.json"), "--exceptions", str(tmp_path / "exceptions.yaml")]
    result = subprocess.run(command, capture_output=True, text=True, timeout=30, check=False)
    assert result.returncode == 2
    assert result.stderr.startswith("check-audit: ")
