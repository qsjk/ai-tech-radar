"""Revision check at startup (III §10.1, VII §36.3, T-DB-02)."""

import asyncio
import sqlite3
from pathlib import Path

import pytest
from alembic import command

from app.db.engine import create_engine
from app.db.revision import SchemaRevisionError, check_revision, head_revision
from tests.integration.db.conftest import alembic_config

pytestmark = pytest.mark.spec("T-DB-02")


def check(db_path: str) -> str:
    async def run() -> str:
        engine = create_engine(db_path)
        try:
            return await check_revision(engine)
        finally:
            await engine.dispose()

    return asyncio.run(run())


def test_unmigrated_database_detected(tmp_path: Path) -> None:
    with pytest.raises(SchemaRevisionError, match="database not migrated"):
        check(str(tmp_path / "radar.db"))


def test_database_at_head_accepted(tmp_path: Path) -> None:
    db_path = str(tmp_path / "radar.db")
    command.upgrade(alembic_config(db_path), "head")
    assert check(db_path) == head_revision()


def test_revision_other_than_head_detected(tmp_path: Path) -> None:
    db_path = str(tmp_path / "radar.db")
    command.upgrade(alembic_config(db_path), "head")
    conn = sqlite3.connect(db_path)
    conn.execute("UPDATE alembic_version SET version_num = 'ffffffffffff'")
    conn.commit()
    conn.close()
    with pytest.raises(SchemaRevisionError, match=f"revision ffffffffffff, `head` expected \\({head_revision()}\\)"):
        check(db_path)


def test_database_downgraded_to_base_detected(tmp_path: Path) -> None:
    db_path = str(tmp_path / "radar.db")
    config = alembic_config(db_path)
    command.upgrade(config, "head")
    command.downgrade(config, "base")
    with pytest.raises(SchemaRevisionError, match="database not migrated"):
        check(db_path)
