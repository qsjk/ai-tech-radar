"""Moteur SQLite asynchrone d'un processus (docs/database.md §2.2, §2.3 ; III §10.2, §10.3).

Recette validée en T0.3 (V-03) : l'écouteur `connect` désactive le `BEGIN` implicite du pilote et applique les PRAGMA ;
l'écouteur `begin` émet `BEGIN IMMEDIATE` pour une écriture, `BEGIN DEFERRED` pour une lecture seule.
"""

from typing import Any

from sqlalchemy import Engine, event
from sqlalchemy import create_engine as create_sync_engine
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


def connection_pragmas(*, busy_timeout_ms: int, journal_size_limit: int, foreign_keys: bool = True) -> list[str]:
    """PRAGMA de chaque connexion (III §10.2). `foreign_keys` vaut `ON` pour `app` et `worker` ; seule la connexion de
    `migrate` le pose à `OFF` (III §10.5, `docs/database.md` §5)."""
    return [
        "PRAGMA journal_mode=WAL",
        "PRAGMA synchronous=NORMAL",
        f"PRAGMA busy_timeout={int(busy_timeout_ms)}",
        f"PRAGMA foreign_keys={'ON' if foreign_keys else 'OFF'}",
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


def migrate_database_url(db_path: str) -> str:
    """URL du moteur synchrone de `migrate`, construite à partir de `RADAR_DB_PATH` (architecture.md P-01)."""
    return f"sqlite:///{db_path}"


def create_migrate_engine(
    db_path: str,
    *,
    busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
    journal_size_limit: int = DEFAULT_JOURNAL_SIZE_LIMIT,
) -> Engine:
    """Moteur synchrone propre à `migrate` (docs/database.md §5, III §10.5).

    Même technique que le moteur applicatif : `isolation_level = None` et PRAGMA posés sur la connexion DBAPI, donc
    hors de toute transaction, puis `BEGIN IMMEDIATE` émis par l'écouteur `begin`. Seule différence :
    `foreign_keys=OFF`, pour qu'une reconstruction de table en mode batch ne déclenche aucune cascade.
    """
    engine = create_sync_engine(migrate_database_url(db_path))
    pragmas = connection_pragmas(
        busy_timeout_ms=busy_timeout_ms, journal_size_limit=journal_size_limit, foreign_keys=False
    )

    @event.listens_for(engine, "connect")
    def _on_connect(dbapi_connection: Any, connection_record: ConnectionPoolEntry) -> None:
        dbapi_connection.isolation_level = None  # pysqlite n'ouvre plus de transaction implicite
        cursor = dbapi_connection.cursor()  # PRAGMA exécutés hors transaction
        for pragma in pragmas:
            cursor.execute(pragma)
        cursor.close()

    @event.listens_for(engine, "begin")
    def _on_begin(conn: Connection) -> None:
        conn.exec_driver_sql("BEGIN IMMEDIATE")

    return engine
