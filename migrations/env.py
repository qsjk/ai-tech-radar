"""Alembic environment of the `migrate` service (docs/database.md §5, III §10.5).

- Synchronous engine dedicated to `migrate`, on the URL built from `RADAR_DB_PATH` (no URL in `alembic.ini`,
  architecture.md P-01).
- `foreign_keys=OFF` set on connect, outside any transaction; `BEGIN IMMEDIATE` emitted when the transaction opens.
- `transactional_ddl=True` and `transaction_per_migration=False`: the whole run fits in **a single** transaction.
  Alembic declares SQLite without transactional DDL; without these two settings, each migration would be committed
  separately.
- `PRAGMA foreign_key_check` after `run_migrations()`, in that transaction, before the commit: a violation raises an
  exception and rolls everything back; the Alembic revision and the schema stay as they were before the run.
"""

import os

from alembic import context

from app.db.engine import create_migrate_engine
from app.db.models import Base

target_metadata = Base.metadata


class ForeignKeyViolationError(RuntimeError):
    """`PRAGMA foreign_key_check` found at least one violation: the run is rolled back."""


def _db_path() -> str:
    path = context.config.attributes.get("radar_db_path") or os.environ.get("RADAR_DB_PATH")
    if not path:
        raise RuntimeError("RADAR_DB_PATH missing: database path unknown (architecture.md P-01)")
    return str(path)


def run_migrations_online() -> None:
    engine = create_migrate_engine(_db_path())
    try:
        with engine.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                render_as_batch=True,
                transactional_ddl=True,  # Alembic declares SQLite without transactional DDL
                transaction_per_migration=False,  # a single transaction for the whole run
            )
            with context.begin_transaction():
                context.run_migrations()
                violations = connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
                if violations:  # exception: rollback, revision and schema unchanged
                    raise ForeignKeyViolationError(f"foreign key violations: {violations}")
    finally:
        engine.dispose()


if context.is_offline_mode():
    raise RuntimeError("offline mode (--sql) not supported: migrate runs against the database (III §10.5)")
run_migrations_online()
