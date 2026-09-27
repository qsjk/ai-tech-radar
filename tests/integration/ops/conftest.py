"""Base temporaire migrée à `head`, pour les tests du worker."""

from pathlib import Path

import pytest
from alembic import command

from tests.integration.db.conftest import alembic_config


@pytest.fixture
def base_migree(tmp_path: Path) -> str:
    db_path = str(tmp_path / "radar.db")
    command.upgrade(alembic_config(db_path), "head")
    return db_path
