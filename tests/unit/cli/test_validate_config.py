"""`python -m app.cli validate-config` et contrat commun des commandes (IX §56.3, §56.4)."""

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

RACINE = Path(__file__).resolve().parents[3]
CONFIG_DU_DEPOT = RACINE / "config"


@pytest.fixture(autouse=True)
def _logs_restaures() -> Iterator[None]:
    root = logging.getLogger()
    handlers, level = root.handlers[:], root.level
    yield
    root.handlers[:] = handlers
    root.setLevel(level)
    structlog.reset_defaults()


def lancer(capsys: pytest.CaptureFixture[str], *argv: str) -> tuple[int, str, str]:
    try:
        code = main(list(argv))
    except SystemExit as sortie:
        code = int(sortie.code or 0)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


@pytest.mark.spec("T-CFG-01")
def test_config_du_depot_acceptee(capsys: pytest.CaptureFixture[str]) -> None:
    code, out, err = lancer(capsys, "validate-config", "--config-dir", str(CONFIG_DU_DEPOT))
    assert code == 0
    assert out.startswith("valid configuration")
    assert [json.loads(ligne)["event"] for ligne in err.splitlines()] == [
        "config.validate.started",
        "config.validate.finished",
    ]


@pytest.mark.spec("T-CFG-01")
def test_point_d_entree_module_depuis_la_racine_du_depot() -> None:
    resultat = subprocess.run(
        [sys.executable, "-m", "app.cli", "validate-config"], cwd=RACINE, capture_output=True, text=True, check=False
    )
    assert resultat.returncode == 0, resultat.stdout + resultat.stderr
    assert resultat.stdout.startswith("valid configuration (config)")
    assert all(json.loads(ligne)["service"] == "worker" for ligne in resultat.stderr.splitlines())


@pytest.mark.spec("T-CFG-10")
def test_configuration_invalide_code_2_resultat_sur_stdout(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    shutil.copytree(CONFIG_DU_DEPOT, tmp_path / "config")
    topics = tmp_path / "config" / "topics.yaml"
    topics.write_text(topics.read_text(encoding="utf-8").replace("parent: anthropic", "parent: absent"), "utf-8")
    code, out, err = lancer(capsys, "validate-config", "--config-dir", str(tmp_path / "config"))
    assert code == 2
    assert "topics.yaml · entry 'claude-code' · field 'parent': parent 'absent' does not exist" in out
    assert "config.validate.invalid" in err and "does not exist" not in err  # logs sur stderr, résultat sur stdout


@pytest.mark.spec("T-CFG-10")
def test_fichier_obligatoire_absent_code_2(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    shutil.copytree(CONFIG_DU_DEPOT, tmp_path / "config")
    (tmp_path / "config" / "entities.yaml").unlink()
    code, out, _ = lancer(capsys, "validate-config", "--config-dir", str(tmp_path / "config"))
    assert code == 2
    assert "entities.yaml: required file missing" in out


@pytest.mark.spec("T-CFG-10")
@pytest.mark.parametrize("argv", [(), ("inconnue",), ("validate-config", "--option-inconnue")])
def test_usage_invalide_code_2_sur_stderr(capsys: pytest.CaptureFixture[str], argv: tuple[str, ...]) -> None:
    code, out, err = lancer(capsys, *argv)
    assert code == 2
    assert out == ""
    assert "usage:" in err


@pytest.mark.spec("T-CFG-10")
def test_echec_de_l_operation_code_1(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    fichier = tmp_path / "pas-un-dossier"
    fichier.write_text("", encoding="utf-8")
    code, out, err = lancer(capsys, "validate-config", "--config-dir", str(fichier))
    assert code == 1
    assert out.startswith("failed: cannot read")
    assert "config.validate.failed" in err
