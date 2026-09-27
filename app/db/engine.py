"""Asynchronous SQLite engine of a process (docs/database.md §2.2, §2.3; III §10.2, §10.3).

Recipe validated in T0.3 (V-03): the `connect` listener disables the driver's implicit `BEGIN` and applies the PRAGMAs;
the `begin` listener emits `BEGIN IMMEDIATE` for a write, `BEGIN DEFERRED` for a read-only transaction.
"""

from typing import Any

from sqlalchemy import Engine, event
from sqlalchemy import create_engine as create_sync_engine
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.pool import ConnectionPoolEntry

# Execution option that marks a connection as read-only: its `begin` emits `BEGIN DEFERRED`.
READ_ONLY_OPTION = "radar_read_only"

DEFAULT_BUSY_TIMEOUT_MS = 5000  # III §10.2
DEFAULT_JOURNAL_SIZE_LIMIT = 67_108_864  # 64 MiB, initial value (III §10.2)


def database_url(db_path: str) -> str:
    """URL of the application engine, built from `RADAR_DB_PATH` (architecture.md P-01)."""
    return f"sqlite+aiosqlite:///{db_path}"


def connection_pragmas(*, busy_timeout_ms: int, journal_size_limit: int, foreign_keys: bool = True) -> list[str]:
    """PRAGMAs of every connection (III §10.2). `foreign_keys` is `ON` for `app` and `worker`; only the `migrate`
    connection sets it `OFF` (III §10.5, `docs/database.md` §5)."""
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
    """Create the process engine: one per process, with its pool (III §10.3)."""
    engine = create_async_engine(database_url(db_path))
    pragmas = connection_pragmas(busy_timeout_ms=busy_timeout_ms, journal_size_limit=journal_size_limit)

    @event.listens_for(engine.sync_engine, "connect")
    def _on_connect(dbapi_connection: Any, connection_record: ConnectionPoolEntry) -> None:
        dbapi_connection.isolation_level = None  # the driver no longer emits BEGIN
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
    """URL of the synchronous `migrate` engine, built from `RADAR_DB_PATH` (architecture.md P-01)."""
    return f"sqlite:///{db_path}"


def create_migrate_engine(
    db_path: str,
    *,
    busy_timeout_ms: int = DEFAULT_BUSY_TIMEOUT_MS,
    journal_size_limit: int = DEFAULT_JOURNAL_SIZE_LIMIT,
) -> Engine:
    """Synchronous engine dedicated to `migrate` (docs/database.md §5, III §10.5).

    Same technique as the application engine: `isolation_level = None` and PRAGMAs set on the DBAPI connection, hence
    outside any transaction, then `BEGIN IMMEDIATE` emitted by the `begin` listener. Only difference:
    `foreign_keys=OFF`, so that a batch-mode table rebuild triggers no cascade.
    """
    engine = create_sync_engine(migrate_database_url(db_path))
    pragmas = connection_pragmas(
        busy_timeout_ms=busy_timeout_ms, journal_size_limit=journal_size_limit, foreign_keys=False
    )

    @event.listens_for(engine, "connect")
    def _on_connect(dbapi_connection: Any, connection_record: ConnectionPoolEntry) -> None:
        dbapi_connection.isolation_level = None  # pysqlite no longer opens an implicit transaction
        cursor = dbapi_connection.cursor()  # PRAGMAs run outside any transaction
        for pragma in pragmas:
            cursor.execute(pragma)
        cursor.close()

    @event.listens_for(engine, "begin")
    def _on_begin(conn: Connection) -> None:
        conn.exec_driver_sql("BEGIN IMMEDIATE")

    return engine
