"""Schema revision check at startup (III §10.1, VII §36.3, T-DB-02).

`app` and `worker` never migrate (III §10.5): they compare the Alembic revision in the database with the `head`
revision of the code, and refuse to start if they differ, unmigrated database included. The refusal is wired into
each process (T1.6, T1.7); this module provides the check.
"""

from pathlib import Path

from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Connection
from sqlalchemy.ext.asyncio import AsyncEngine

from app.db.engine import READ_ONLY_OPTION

# The repository and the image share this layout: `migrations/` next to the `app/` package (VIII §46.1).
DEFAULT_SCRIPT_LOCATION = Path(__file__).resolve().parents[2] / "migrations"


class SchemaRevisionError(RuntimeError):
    """The database revision is not `head`: the process refuses to start."""


def head_revision(script_location: Path = DEFAULT_SCRIPT_LOCATION) -> str:
    head = ScriptDirectory(str(script_location)).get_current_head()
    if head is None:
        raise SchemaRevisionError(f"no migration found in {script_location}")
    return head


def _current_revision(connection: Connection) -> str | None:
    return MigrationContext.configure(connection).get_current_revision()


async def current_revision(engine: AsyncEngine) -> str | None:
    """Alembic revision in the database, read-only; `None` if the database is not migrated."""
    async with engine.execution_options(**{READ_ONLY_OPTION: True}).connect() as conn:
        revision = await conn.run_sync(_current_revision)
        await conn.rollback()
    return revision


async def check_revision(engine: AsyncEngine, script_location: Path = DEFAULT_SCRIPT_LOCATION) -> str:
    """Return the revision if it is `head`; otherwise raise `SchemaRevisionError` with an explicit message."""
    expected = head_revision(script_location)
    actual = await current_revision(engine)
    if actual is None:
        raise SchemaRevisionError(
            f"database not migrated: no Alembic revision, `head` expected ({expected}); run the migrate service"
        )
    if actual != expected:
        raise SchemaRevisionError(
            f"schema at revision {actual}, `head` expected ({expected}); run the migrate service, or deploy the "
            "code that matches this revision"
        )
    return actual
