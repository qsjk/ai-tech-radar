#!/usr/bin/env python3
"""Traceability of the test catalogue (VIII §50.3, docs/architecture.md §5.3, ADR-0018).

Inputs:
1. `docs/spec/partie-VIII.md`, §50.5 only: a catalogue row is recognised by the CATALOGUE_ROW pattern on its first
   column; the level is read in the third column (U, I, E, F, M, or several joined by "·").
2. `docs/sprints/sprint-NN.md`: the `Statut : planifié | en cours | clos` line and the "Identifiants visés" block, one
   identifier per line, with its parts in brackets when partial (`T-DB-13 [pragma, check]`, P-11).
3. The tests: `spec("T-…")` or `spec("T-…:part")` markers under `tests/`, `[T-FE-nn]` tags in the vitest files.

Checks: every U, I, E or F identifier (and part) targeted by a **closed** sprint has a test, otherwise failure; those of
the sprint **in progress** are reported as non-blocking (P-15). Every marker refers to an existing identifier; no M
identifier is marked. Exit codes (IX §56.3 by analogy): 0 all covered, 1 missing coverage or invalid marker,
2 unreadable input (missing section, malformed or duplicate identifier, unknown level, unreadable status).
"""

import argparse
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

ID = r"T-[A-Z]+-\d{2}"
CATALOGUE_ROW = re.compile(rf"^\|\s*({ID})\s*\|")
CATALOGUE_LIKE_ROW = re.compile(r"^\|\s*(T-[^|\s]*)\s*\|")
LEVELS = {"U", "I", "E", "F", "M"}
CHECKED_LEVELS = {"U", "I", "E", "F"}
STATUS = re.compile(r"^Statut : (planifié|en cours|clos)\s*$", re.MULTILINE)
STATUS_LIKE = re.compile(r"^Statut\s*:", re.MULTILINE)
TARGET = re.compile(rf"^({ID})(?:\s*\[([^\]]*)\])?(?:\s|$)")
SPRINT_FILE = re.compile(r"^sprint-(\d{2})\.md$")
MARKER = re.compile(r"""\.spec\(\s*["']([^"']*)["']\s*\)""")
MARKER_VALUE = re.compile(rf"^({ID})(?::([a-z0-9_-]+))?$")
VITEST_TAG = re.compile(r"\[(T-FE-\d{2})\]")

EXIT_OK, EXIT_FAILURE, EXIT_INVALID = 0, 1, 2


class InputError(Exception):
    """Unreadable input: the script cannot judge the coverage (exit code 2)."""


@dataclass
class Sprint:
    number: str
    status: str
    targets: dict[str, set[str]] = field(default_factory=dict)  # identifier -> parts (empty: whole identifier)


@dataclass
class Coverage:
    whole: set[str] = field(default_factory=set)
    parts: dict[str, set[str]] = field(default_factory=dict)
    invalid: list[str] = field(default_factory=list)  # "file: marker" of malformed markers


def read(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as error:
        raise InputError(f"{path}: unreadable ({error.__class__.__name__})") from None


def parse_catalogue(text: str) -> dict[str, set[str]]:
    """Identifiers of VIII §50.5 and their levels."""
    start = text.find("### 50.5")
    end = text.find("### 50.6", start)
    if start < 0 or end < 0:
        raise InputError("partie-VIII.md: section §50.5 not found (between '### 50.5' and '### 50.6')")
    catalogue: dict[str, set[str]] = {}
    for line in text[start:end].splitlines():
        match = CATALOGUE_ROW.match(line)
        if match is None:
            like = CATALOGUE_LIKE_ROW.match(line)
            if like is not None:
                raise InputError(f"partie-VIII.md: malformed identifier {like.group(1)!r}")
            continue
        identifier = match.group(1)
        columns = [column.strip() for column in line.split("|")]
        if len(columns) < 4:
            raise InputError(f"partie-VIII.md: {identifier} has no level column")
        levels = {level.strip() for level in columns[3].split("·")}
        if not levels <= LEVELS:
            raise InputError(f"partie-VIII.md: {identifier} has an unknown level {columns[3]!r}")
        if identifier in catalogue:
            raise InputError(f"partie-VIII.md: duplicate identifier {identifier}")
        catalogue[identifier] = levels
    if not catalogue:
        raise InputError("partie-VIII.md: no identifier in §50.5")
    return catalogue


def parse_sprint(number: str, text: str) -> Sprint:
    statuses = STATUS.findall(text)
    if len(statuses) != 1 or len(STATUS_LIKE.findall(text)) != 1:
        raise InputError(f"sprint-{number}.md: status unreadable (one line 'Statut : planifié | en cours | clos')")
    sprint = Sprint(number, statuses[0])
    heading = text.find("## Identifiants visés")
    if heading < 0:
        return sprint
    block = re.search(r"```[^\n]*\n(.*?)```", text[heading:], re.DOTALL)
    if block is None:
        raise InputError(f"sprint-{number}.md: 'Identifiants visés' has no code block")
    for line in block.group(1).splitlines():
        if not line.strip():
            continue
        match = TARGET.match(line.strip())
        if match is None:
            raise InputError(f"sprint-{number}.md: unreadable target line {line.strip()!r}")
        identifier, parts = match.group(1), match.group(2)
        names = {part.strip() for part in parts.split(",")} if parts is not None else set()
        if "" in names:
            raise InputError(f"sprint-{number}.md: empty part for {identifier}")
        if identifier in sprint.targets:
            raise InputError(f"sprint-{number}.md: {identifier} targeted twice")
        sprint.targets[identifier] = names
    return sprint


def read_sprints(directory: Path) -> list[Sprint]:
    if not directory.is_dir():
        raise InputError(f"{directory}: not found")
    sprints = []
    for path in sorted(directory.iterdir()):
        match = SPRINT_FILE.match(path.name)
        if match is not None:
            sprints.append(parse_sprint(match.group(1), read(path)))
    return sprints


def collect_coverage(tests: Path, frontend: Path) -> Coverage:
    coverage = Coverage()
    for path in sorted(tests.rglob("*.py")) if tests.is_dir() else []:
        for value in MARKER.findall(read(path)):
            match = MARKER_VALUE.match(value)
            if match is None:
                coverage.invalid.append(f"{path}: spec({value!r})")
            elif match.group(2) is None:
                coverage.whole.add(match.group(1))
            else:
                coverage.parts.setdefault(match.group(1), set()).add(match.group(2))
    if frontend.is_dir():
        for pattern in ("*.test.ts", "*.test.tsx"):
            for path in sorted(frontend.rglob(pattern)):
                if "node_modules" not in path.parts:
                    coverage.whole.update(VITEST_TAG.findall(read(path)))
    return coverage


def check(root: Path) -> tuple[int, list[str]]:
    catalogue = parse_catalogue(read(root / "docs" / "spec" / "partie-VIII.md"))
    sprints = read_sprints(root / "docs" / "sprints")
    coverage = collect_coverage(root / "tests", root / "frontend" / "src")
    report: list[str] = []
    blocking = False

    for marker in coverage.invalid:
        report.append(f"ERROR malformed marker: {marker}")
        blocking = True
    marked = coverage.whole | set(coverage.parts)
    for identifier in sorted(marked - set(catalogue)):
        report.append(f"ERROR unknown identifier marked: {identifier}")
        blocking = True
    for identifier in sorted(marked & set(catalogue)):
        if catalogue[identifier] == {"M"}:
            report.append(f"ERROR level M identifier marked in the code: {identifier}")
            blocking = True

    for sprint in sprints:
        missing: list[str] = []
        for identifier, parts in sorted(sprint.targets.items()):
            if identifier not in catalogue:
                report.append(f"ERROR sprint-{sprint.number}.md targets an unknown identifier: {identifier}")
                blocking = True
                continue
            if not catalogue[identifier] & CHECKED_LEVELS:
                continue
            if identifier in coverage.whole:
                continue
            if not parts:
                missing.append(identifier)
            else:
                covered = coverage.parts.get(identifier, set())
                missing += [f"{identifier}:{part}" for part in sorted(parts - covered)]
        label = {"clos": "BLOCKING", "en cours": "non-blocking (sprint in progress, P-15)"}.get(sprint.status)
        targeted = len(sprint.targets)
        report.append(
            f"sprint-{sprint.number} ({sprint.status}): {targeted} identifier(s) targeted, {len(missing)} without test"
        )
        if label is None:
            continue
        for item in missing:
            report.append(f"  {'MISSING' if sprint.status == 'clos' else 'missing'} {item} — {label}")
        if missing and sprint.status == "clos":
            blocking = True

    report.append("result: " + ("FAILURE" if blocking else "OK"))
    return (EXIT_FAILURE if blocking else EXIT_OK), report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Traceability of the VIII §50.5 test catalogue (VIII §50.3).")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1], help="repository root")
    args = parser.parse_args(argv)
    try:
        code, report = check(args.root)
    except InputError as error:
        print(f"check-test-catalog: {error}", file=sys.stderr)
        return EXIT_INVALID
    print("\n".join(report))
    return code


if __name__ == "__main__":
    sys.exit(main())
