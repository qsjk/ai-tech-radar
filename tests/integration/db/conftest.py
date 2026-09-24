"""Base SQLite temporaire, sur fichier et en WAL (VIII §50.1 : jamais `:memory:`)."""

import sqlite3
from pathlib import Path

import pytest


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
