"""`scripts/check-test-catalog.py` (VIII §50.3, docs/architecture.md §5.3): on a fake catalogue and fake sprints.

The fake repositories are written in a temporary directory; the markers of their tests are built at run time, so that
the script never mistakes this file's fixtures for real markers when it scans the repository's `tests/`.
"""

import subprocess
import sys
from pathlib import Path

import pytest

from tests.integration.db.conftest import ROOT

SCRIPT = ROOT / "scripts" / "check-test-catalog.py"
SPEC = "spec"

# French headings and status values are the format of the spec documents (P-11), kept as is.
CATALOGUE = """\
# Partie VIII

### 50.5 Catalogue par domaine

| ID | Test | Niv. | Origine |
|---|---|---|---|
| T-AA-01 | unit rule | U | x |
| T-AA-02 | integration rule | I | x |
| T-AA-03 | partial rule | I | x |
| T-AA-04 | manual check | M | x |
| T-AA-05 | two levels | I · E | x |
| T-FE-01 | frontend rule | F | x |

### 50.6 Suite
| T-ZZ-99 | outside §50.5, ignored | U | x |
"""


def sprint(status: str, *targets: str) -> str:
    body = "\n".join(targets)
    return f"# Sprint\n\nStatut : {status}\n\n## Identifiants visés\n\n```\n{body}\n```\n"


def marker(value: str) -> str:
    return f"@pytest.mark.{SPEC}({value!r})\ndef test_x() -> None:\n    pass\n"


def repository(
    root: Path,
    *,
    catalogue: str = CATALOGUE,
    sprints: dict[str, str] | None = None,
    markers: tuple[str, ...] = (),
    vitest: str = "",
) -> Path:
    (root / "docs" / "spec").mkdir(parents=True)
    (root / "docs" / "spec" / "partie-VIII.md").write_text(catalogue, encoding="utf-8")
    (root / "docs" / "sprints").mkdir()
    for number, text in (sprints or {}).items():
        (root / "docs" / "sprints" / f"sprint-{number}.md").write_text(text, encoding="utf-8")
    (root / "docs" / "sprints" / "sprint-00-cadrage.md").write_text("# no status line: not a sprint plan\n")
    (root / "tests").mkdir()
    (root / "tests" / "test_fake.py").write_text("\n".join(marker(value) for value in markers), encoding="utf-8")
    if vitest:
        (root / "frontend" / "src").mkdir(parents=True)
        (root / "frontend" / "src" / "App.test.tsx").write_text(vitest, encoding="utf-8")
    return root


def run(root: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root)], capture_output=True, text=True, timeout=30, check=False
    )


ALL_MARKERS = ("T-AA-01", "T-AA-02", "T-AA-03:pragma", "T-AA-03:check", "T-AA-05")
ALL_TARGETS = ("T-AA-01          T1.1", "T-AA-02", "T-AA-03 [pragma, check]   T1.4   (rebuild: Sprint 3)", "T-AA-05")


def test_closed_sprint_fully_covered_exits_0(tmp_path: Path) -> None:
    result = run(repository(tmp_path, sprints={"01": sprint("clos", *ALL_TARGETS)}, markers=ALL_MARKERS))
    assert result.returncode == 0, result.stdout + result.stderr
    assert "sprint-01 (clos): 4 identifier(s) targeted, 0 without test" in result.stdout
    assert result.stdout.rstrip().endswith("result: OK")


def test_closed_sprint_with_an_identifier_without_test_exits_1(tmp_path: Path) -> None:
    markers = tuple(m for m in ALL_MARKERS if m != "T-AA-02")
    result = run(repository(tmp_path, sprints={"01": sprint("clos", *ALL_TARGETS)}, markers=markers))
    assert result.returncode == 1
    assert "MISSING T-AA-02 — BLOCKING" in result.stdout


def test_closed_sprint_with_a_part_without_test_exits_1(tmp_path: Path) -> None:
    markers = tuple(m for m in ALL_MARKERS if m != "T-AA-03:check")
    result = run(repository(tmp_path, sprints={"01": sprint("clos", *ALL_TARGETS)}, markers=markers))
    assert result.returncode == 1
    assert "MISSING T-AA-03:check — BLOCKING" in result.stdout
    assert "T-AA-03:pragma" not in result.stdout


def test_sprint_in_progress_is_reported_without_blocking(tmp_path: Path) -> None:
    result = run(repository(tmp_path, sprints={"02": sprint("en cours", *ALL_TARGETS)}, markers=("T-AA-01",)))
    assert result.returncode == 0
    assert "missing T-AA-02 — non-blocking (sprint in progress, P-15)" in result.stdout
    assert "missing T-AA-03:pragma" in result.stdout


def test_planned_sprint_is_not_checked(tmp_path: Path) -> None:
    result = run(repository(tmp_path, sprints={"03": sprint("planifié", *ALL_TARGETS)}))
    assert result.returncode == 0
    assert "missing" not in result.stdout.lower()


def test_whole_marker_covers_every_part_but_a_part_does_not_cover_the_whole(tmp_path: Path) -> None:
    whole = run(
        repository(tmp_path / "a", sprints={"01": sprint("clos", "T-AA-03 [pragma, check]")}, markers=("T-AA-03",))
    )
    assert whole.returncode == 0
    part = run(repository(tmp_path / "b", sprints={"01": sprint("clos", "T-AA-02")}, markers=("T-AA-02:base",)))
    assert part.returncode == 1


def test_manual_identifier_targeted_needs_no_test(tmp_path: Path) -> None:
    assert run(repository(tmp_path, sprints={"01": sprint("clos", "T-AA-04")})).returncode == 0


def test_vitest_tag_covers_a_frontend_identifier(tmp_path: Path) -> None:
    tagged = repository(tmp_path, sprints={"01": sprint("clos", "T-FE-01")}, vitest="it('[T-FE-01] renders', () => {})")
    assert run(tagged).returncode == 0
    assert run(repository(tmp_path / "b", sprints={"01": sprint("clos", "T-FE-01")})).returncode == 1


@pytest.mark.parametrize(
    ("markers", "message"),
    [
        (("T-AA-42",), "unknown identifier marked: T-AA-42"),
        (("T-AA-04",), "level M identifier marked in the code: T-AA-04"),
        (("T-AA-4",), "malformed marker"),
        (("T-AA-01:Bad Part",), "malformed marker"),
    ],
)
def test_invalid_marker_is_an_error(tmp_path: Path, markers: tuple[str, ...], message: str) -> None:
    result = run(repository(tmp_path, markers=markers))
    assert result.returncode == 1
    assert message in result.stdout


def test_sprint_targeting_an_unknown_identifier_is_an_error(tmp_path: Path) -> None:
    result = run(repository(tmp_path, sprints={"01": sprint("en cours", "T-AA-77")}))
    assert result.returncode == 1
    assert "targets an unknown identifier: T-AA-77" in result.stdout


@pytest.mark.parametrize(
    ("catalogue", "sprints", "message"),
    [
        (CATALOGUE.replace("### 50.5", "### 50.4"), {}, "section §50.5 not found"),
        (CATALOGUE.replace("| T-AA-02 |", "| T-AA-01 |"), {}, "duplicate identifier T-AA-01"),
        (CATALOGUE.replace("| T-AA-02 | integration rule | I |", "| T-AA-02 | x | Z |"), {}, "unknown level"),
        (CATALOGUE.replace("| T-AA-02 |", "| T-aa-2 |"), {}, "malformed identifier"),
        (CATALOGUE, {"01": "# Sprint\n\nStatut : terminé\n"}, "status unreadable"),
        (CATALOGUE, {"01": "# Sprint\n\nno status\n"}, "status unreadable"),
        (CATALOGUE, {"01": sprint("clos", "not an identifier")}, "unreadable target line"),
        (CATALOGUE, {"01": sprint("clos", "T-AA-01", "T-AA-01")}, "targeted twice"),
    ],
)
def test_unreadable_input_exits_2(tmp_path: Path, catalogue: str, sprints: dict[str, str], message: str) -> None:
    result = run(repository(tmp_path, catalogue=catalogue, sprints=sprints))
    assert result.returncode == 2, result.stdout
    assert message in result.stderr
    assert result.stdout == ""


def test_repository_catalogue_and_sprint_01() -> None:
    result = run(ROOT)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "sprint-01 (clos): 31 identifier(s) targeted, 0 without test" in result.stdout
