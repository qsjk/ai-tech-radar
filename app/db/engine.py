"""Moteur SQLite asynchrone d'un processus (docs/database.md §2.2, §2.3 ; III §10.2, §10.3).

Recette validée en T0.3 (V-03) : l'écouteur `connect` désactive le `BEGIN` implicite du pilote et applique les PRAGMA ;
l'écouteur `begin` émet `BEGIN IMMEDIATE` pour une écriture, `BEGIN DEFERRED` pour une lecture seule.
"""

from typing import Any

from sqlalchemy import event
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import ConnectionPoolEntry

# Option d'exécution qui marque une connexion en lecture seule : son `begin` émet `BEGIN DEFERRED`.
READ_ONLY_OPTION = "radar_read_only"

DEFAULT_BUSY_TIMEOUT_MS = 5000  # III §10.2
DEFAULT_JOURNAL_SIZE_LIMIT = 67_108_864  # 64 Mo, valeur initiale (III §10.2)


def database_url(db_path: str) -> str:
    """URL du moteur applicatif, construite à partir de `RADAR_DB_PATH` (architecture.md P-01)."""
    return f"sqlite+aiosqlite:///{db_path}"


def connection_pragmas(*, busy_timeout_ms: int, journal_size_limit: int) -> list[str]:
    """PRAGMA de chaque connexion de `app` et `worker` (III §10.2)."""
    return [
        "PRAGMA journal_mode=WAL",
        "PRAGMA synchronous=NORMAL",
        f"PRAGMA busy_timeout={int(busy_timeout_ms)}",
        "PRAGMA foreign_keys=ON",
        f"PRAGMA journal_size_limit={int(journal_size_limit)}",
    ]


def create_engine(
    db_path: str,
    *,
    busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
    journal_size_limit: int = DEFAULT_JOURNAL_SIZE_LIMIT,
) -> AsyncEngine:
    """Crée le moteur du processus : un par processus, avec son pool (III §10.3)."""
    engine = create_async_engine(database_url(db_path))
    pragmas = connection_pragmas(busy_timeout_ms=busy_timeout_ms, journal_size_limit=journal_size_limit)

    @event.listens_for(engine.sync_engine, "connect")
    def _on_connect(dbapi_connection: Any, connection_record: ConnectionPoolEntry) -> None:
        dbapi_connection.isolation_level = None  # le pilote n'émet plus de BEGIN
        cursor = dbapi_connection.cursor()
        for pragma in pragmas:
            cursor.execute(pragma)
        cursor.close()

    @event.listens_for(engine.sync_engine, "begin")
    def _on_begin(conn: Connection) -> None:
        mode = "DEFERRED" if conn.get_execution_options().get(READ_ONLY_OPTION) else "IMMEDIATE"
        conn.exec_driver_sql(f"BEGIN {mode}")

    return engine
