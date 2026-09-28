#!/usr/bin/env python3
"""Stage 3 of the CI (VIII §49.2, §49.4): confront the dependency audits with `.audit-exceptions.yaml`.

Inputs: the JSON report of pip-audit (backend, from `uv.lock`), the JSON report of `npm audit` (frontend) and the
exceptions file. Blocking: every backend vulnerability (pip-audit reports no severity) and every frontend one rated
`high` or `critical`, unless a valid exception covers it; an exception that is expired, expires more than 90 days
ahead, or lacks a field fails the stage. `moderate` and below are reported, never blocking. Exit codes: 0 OK,
1 blocking finding, 2 unreadable input.
"""

import argparse
import datetime as dt
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

MAX_DAYS = 90
BLOCKING_NPM = {"high", "critical"}
FIELDS = ("id", "package", "justification", "expires")

EXIT_OK, EXIT_FAILURE, EXIT_INVALID = 0, 1, 2


class InputError(Exception):
    pass


@dataclass(frozen=True)
class Finding:
    source: str
    package: str
    ids: frozenset[str]
    severity: str

    @property
    def label(self) -> str:
        return f"{self.source} {self.package} {'/'.join(sorted(self.ids)) or '-'} ({self.severity})"


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise InputError(f"{path}: unreadable ({error.__class__.__name__})") from None


def load_exceptions(path: Path, today: dt.date) -> tuple[list[dict[str, Any]], list[str]]:
    """Valid exceptions, and the errors of the invalid ones (expired, too far ahead, incomplete)."""
    try:
        data = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError) as error:
        raise InputError(f"{path}: unreadable ({error.__class__.__name__})") from None
    if not isinstance(data, dict) or not isinstance(data.get("exceptions"), list):
        raise InputError(f"{path}: a top-level 'exceptions' list is expected")
    valid, errors = [], []
    for index, entry in enumerate(data["exceptions"], start=1):
        name = f"exception #{index}"
        if not isinstance(entry, dict) or any(not entry.get(field) for field in FIELDS):
            errors.append(f"{name}: fields {', '.join(FIELDS)} are all required")
            continue
        expires = entry["expires"]
        if isinstance(expires, str):
            try:
                expires = dt.date.fromisoformat(expires)
            except ValueError:
                errors.append(f"{name} ({entry['id']}): expires {entry['expires']!r} is not a YYYY-MM-DD date")
                continue
        if not isinstance(expires, dt.date):
            errors.append(f"{name} ({entry['id']}): expires is not a date")
        elif expires < today:
            errors.append(f"{name} ({entry['id']}): expired on {expires.isoformat()}")
        elif expires > today + dt.timedelta(days=MAX_DAYS):
            errors.append(f"{name} ({entry['id']}): expires {expires.isoformat()}, more than {MAX_DAYS} days ahead")
        else:
            valid.append(entry)
    return valid, errors


def pip_findings(report: Any) -> list[Finding]:
    if not isinstance(report, dict) or not isinstance(report.get("dependencies"), list):
        raise InputError("pip-audit report: a 'dependencies' list is expected")
    findings = []
    for dependency in report["dependencies"]:
        for vuln in dependency.get("vulns", []):
            ids = frozenset([vuln["id"], *vuln.get("aliases", [])])
            findings.append(Finding("pip", str(dependency["name"]).lower(), ids, "unrated"))
    return findings


def npm_findings(report: Any) -> list[Finding]:
    if not isinstance(report, dict) or not isinstance(report.get("vulnerabilities", {}), dict):
        raise InputError("npm audit report: a 'vulnerabilities' mapping is expected")
    findings = []
    for name, vulnerability in report.get("vulnerabilities", {}).items():
        ids = set()
        for via in vulnerability.get("via", []):
            if isinstance(via, dict):
                url = str(via.get("url", ""))
                if url:
                    ids.add(url.rsplit("/", 1)[-1])
        findings.append(Finding("npm", name, frozenset(ids), str(vulnerability.get("severity", "unknown"))))
    return findings


def covered(finding: Finding, exceptions: list[dict[str, Any]]) -> bool:
    return any(
        str(entry["package"]).lower() == finding.package and str(entry["id"]) in finding.ids for entry in exceptions
    )


def check(pip: Path, npm: Path, exceptions_path: Path, today: dt.date) -> tuple[int, list[str]]:
    exceptions, errors = load_exceptions(exceptions_path, today)
    findings = pip_findings(load_json(pip)) + npm_findings(load_json(npm))
    report = [f"ERROR {error}" for error in errors]
    blocking = bool(errors)
    for finding in findings:
        is_blocking = finding.source == "pip" or finding.severity in BLOCKING_NPM
        if covered(finding, exceptions):
            report.append(f"excepted {finding.label}")
        elif is_blocking:
            report.append(f"BLOCKING {finding.label}")
            blocking = True
        else:
            report.append(f"reported {finding.label} (non-blocking)")
    report.append(f"{len(findings)} finding(s), {len(exceptions)} valid exception(s)")
    report.append("result: " + ("FAILURE" if blocking else "OK"))
    return (EXIT_FAILURE if blocking else EXIT_OK), report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Confront the audits with .audit-exceptions.yaml (VIII §49.4).")
    parser.add_argument("--pip-audit", type=Path, required=True, help="pip-audit JSON report")
    parser.add_argument("--npm-audit", type=Path, required=True, help="npm audit JSON report")
    parser.add_argument("--exceptions", type=Path, default=Path(".audit-exceptions.yaml"))
    parser.add_argument("--today", type=dt.date.fromisoformat, default=dt.date.today(), help="YYYY-MM-DD, for tests")
    args = parser.parse_args(argv)
    try:
        code, report = check(args.pip_audit, args.npm_audit, args.exceptions, args.today)
    except InputError as error:
        print(f"check-audit: {error}", file=sys.stderr)
        return EXIT_INVALID
    print("\n".join(report))
    return code


if __name__ == "__main__":
    sys.exit(main())
