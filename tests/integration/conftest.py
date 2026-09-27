"""Temporary database migrated to `head` and test `config/` directory, for the worker and app tests."""

import shutil
from pathlib import Path

import pytest
from alembic import command

from tests.integration.db.conftest import ROOT, alembic_config

SHORT_PIPELINE = """\
ops:
  heartbeat_interval: 1s
  heartbeat_stale_after: 4s
  watchdog_timeout: 10s
"""
"""Short settings for process-level tests: one heartbeat per second; watchdog at the minimum accepted, 10 s."""


@pytest.fixture
def migrated_db(tmp_path: Path) -> str:
    db_path = str(tmp_path / "radar.db")
    command.upgrade(alembic_config(db_path), "head")
    return db_path


@pytest.fixture
def config_dir(tmp_path: Path) -> Path:
    """Copy of the demo `config/` files, with a `pipeline.yaml` holding short settings."""
    path = tmp_path / "config"
    shutil.copytree(ROOT / "config", path)
    (path / "pipeline.yaml").write_text(SHORT_PIPELINE, encoding="utf-8")
    return path
