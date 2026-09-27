"""Base temporaire migrée à `head` et dossier `config/` de test, pour les tests du worker et de l'app."""

import shutil
from pathlib import Path

import pytest
from alembic import command

from tests.integration.db.conftest import RACINE, alembic_config

PIPELINE_COURT = """\
ops:
  heartbeat_interval: 1s
  heartbeat_stale_after: 4s
  watchdog_timeout: 10s
"""
"""Réglages courts des tests de niveau processus : un heartbeat par seconde ; watchdog au minimum accepté, 10 s."""


@pytest.fixture
def base_migree(tmp_path: Path) -> str:
    db_path = str(tmp_path / "radar.db")
    command.upgrade(alembic_config(db_path), "head")
    return db_path


@pytest.fixture
def config_dir(tmp_path: Path) -> Path:
    """Copie des fichiers `config/` de démonstration, avec un `pipeline.yaml` aux réglages courts."""
    path = tmp_path / "config"
    shutil.copytree(RACINE / "config", path)
    (path / "pipeline.yaml").write_text(PIPELINE_COURT, encoding="utf-8")
    return path
