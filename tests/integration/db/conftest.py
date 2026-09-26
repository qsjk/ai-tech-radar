"""Base SQLite temporaire, sur fichier et en WAL (VIII §50.1 : jamais `:memory:`)."""

import sqlite3
from pathlib import Path

import pytest
from alembic.config import Config

RACINE = Path(__file__).resolve().parents[3]
MIGRATIONS = RACINE / "migrations"


@pytest.fixture
def db_path(tmp_path: Path) -> str:
    """Fichier SQLite temporaire, en WAL, avec une table de test `probe` (hors schéma applicatif)."""
    path = tmp_path / "radar.db"
    conn = sqlite3.connect(path, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE probe (id INTEGER PRIMARY KEY, writer TEXT NOT NULL, n INTEGER NOT NULL)")
    conn.close()
    return str(path)


def raw_write_lock_free(db_path: str) -> bool:
    """Sonde indépendante : un autre client obtient-il le verrou d'écriture sans attendre ?"""
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
    """Configuration Alembic du dépôt, pointée sur une base de test et, au besoin, sur une chaîne de test."""
    config = Config(str(RACINE / "alembic.ini"))
    config.set_main_option("script_location", str(script_location))
    config.attributes["radar_db_path"] = db_path
    return config
