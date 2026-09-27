"""Temporary SQLite database, on file and in WAL mode (VIII §50.1: never `:memory:`)."""

import sqlite3
from pathlib import Path

import pytest
from alembic.config import Config

ROOT = Path(__file__).resolve().parents[3]
MIGRATIONS = ROOT / "migrations"


@pytest.fixture
def db_path(tmp_path: Path) -> str:
    """Temporary SQLite file, in WAL mode, with a `probe` test table (outside the application schema)."""
    path = tmp_path / "radar.db"
    conn = sqlite3.connect(path, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE probe (id INTEGER PRIMARY KEY, writer TEXT NOT NULL, n INTEGER NOT NULL)")
    conn.close()
    return str(path)


def raw_write_lock_free(db_path: str) -> bool:
    """Independent probe: does another client get the write lock without waiting?"""
    conn = sqlite3.connect(db_path, timeout=0, isolation_level=None)
    try:
        conn.execute("BEGIN IMMEDIATE")
        conn.execute("ROLLBACK")
        return True
    except sqlite3.OperationalError:
        return False
    finally:
        conn.close()


def alembic_config(db_path: str, script_location: Path = MIGRATIONS) -> Config:
    """Alembic configuration of the repository, pointed at a test database and, if needed, at a test chain."""
    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(script_location))
    config.attributes["radar_db_path"] = db_path
    return config
