"""Alembic migrations (III §10.5, docs/database.md §5): real chain and test chains outside the repository."""

import shutil
import sqlite3
from collections.abc import Callable
from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import inspect, text

from app.db.engine import create_migrate_engine
from app.db.models import Base
from tests.integration.db.conftest import MIGRATIONS, alembic_config


def read(db_path: str, sql: str) -> list[tuple[object, ...]]:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


def db_revision(db_path: str) -> str | None:
    tables = {name for (name,) in read(db_path, "SELECT name FROM sqlite_master WHERE type = 'table'")}
    if "alembic_version" not in tables:
        return None
    rows = read(db_path, "SELECT version_num FROM alembic_version")
    return str(rows[0][0]) if rows else None


def schema(db_path: str) -> list[tuple[object, ...]]:
    return read(db_path, "SELECT type, name, sql FROM sqlite_master ORDER BY type, name")


@pytest.fixture
def empty_db(tmp_path: Path) -> str:
    return str(tmp_path / "radar.db")


# ── Real chain ────────────────────────────────────────────────────────────────────────────────────────────────────────


@pytest.mark.spec("T-DB-08")
def test_upgrade_head_from_an_empty_database(empty_db: str) -> None:
    command.upgrade(alembic_config(empty_db), "head")
    head = ScriptDirectory.from_config(alembic_config(empty_db)).get_current_head()
    assert db_revision(empty_db) == head
    engine = create_migrate_engine(empty_db)
    try:
        with engine.connect() as conn:
            columns = {c["name"]: c for c in inspect(conn).get_columns("system_state")}
    finally:
        engine.dispose()
    assert set(columns) == {"key", "value", "updated_at"}
    assert all(not c["nullable"] for c in columns.values())
    assert all(c["default"] is None for c in columns.values())  # no SQL default (III §10.6)


@pytest.mark.spec("T-DB-08")
def test_every_migration_has_a_tested_downgrade(empty_db: str) -> None:
    config = alembic_config(empty_db)
    script = ScriptDirectory.from_config(config)
    revisions = list(script.walk_revisions())  # from head down to base
    command.upgrade(config, "head")
    for revision in revisions:
        assert callable(getattr(revision.module, "downgrade", None)), revision.revision
        command.downgrade(config, "-1")
        assert db_revision(empty_db) == revision.down_revision
    assert "system_state" not in {name for (name,) in read(empty_db, "SELECT name FROM sqlite_master")}


@pytest.mark.spec("T-DB-08")
def test_model_and_migrations_match(empty_db: str) -> None:
    command.upgrade(alembic_config(empty_db), "head")
    engine = create_migrate_engine(empty_db)
    try:
        with engine.connect() as conn:
            differences = compare_metadata(MigrationContext.configure(conn, opts={"compare_type": True}), Base.metadata)
    finally:
        engine.dispose()
    assert differences == []


@pytest.mark.spec("T-DB-13:pragma")
def test_migrate_connection_foreign_keys_off_and_pragmas(empty_db: str) -> None:
    engine = create_migrate_engine(empty_db)
    try:
        with engine.connect() as conn:
            values = {
                name: conn.execute(text(f"PRAGMA {name}")).scalar_one()
                for name in ("foreign_keys", "journal_mode", "synchronous", "busy_timeout", "journal_size_limit")
            }
    finally:
        engine.dispose()
    assert values == {
        "foreign_keys": 0,
        "journal_mode": "wal",
        "synchronous": 1,
        "busy_timeout": 5000,
        "journal_size_limit": 67_108_864,
    }


# ── Test chains, outside the repository ───────────────────────────────────────────────────────────────────────────────

HEADER = """from alembic import op
import sqlalchemy as sa

revision = "{revision}"
down_revision = {down}
branch_labels = None
depends_on = None

"""


@pytest.fixture
def test_chain(tmp_path: Path) -> Callable[[dict[str, str]], Path]:
    """Create a test migrations directory, with the real `env.py`, and the given migrations (revision → body)."""

    def create(migrations: dict[str, str]) -> Path:
        directory = tmp_path / "migrations_test"
        (directory / "versions").mkdir(parents=True)
        shutil.copy(MIGRATIONS / "env.py", directory / "env.py")
        shutil.copy(MIGRATIONS / "script.py.mako", directory / "script.py.mako")
        previous: str | None = None
        for revision, body in migrations.items():
            header = HEADER.format(revision=revision, down=repr(previous))
            (directory / "versions" / f"{revision}.py").write_text(header + body + "\n\ndef downgrade():\n    pass\n")
            previous = revision
        return directory

    return create


@pytest.mark.spec("T-DB-13:pragma")
def test_pragmas_seen_during_an_alembic_run(empty_db: str, test_chain: Callable[..., Path]) -> None:
    directory = test_chain(
        {
            "p1": """def upgrade():
    bind = op.get_bind()
    op.execute("CREATE TABLE pragma_seen (name TEXT PRIMARY KEY, value TEXT NOT NULL)")
    for name in ("foreign_keys", "journal_mode", "synchronous"):
        value = bind.exec_driver_sql(f"PRAGMA {name}").scalar()
        bind.exec_driver_sql("INSERT INTO pragma_seen VALUES (?, ?)", (name, str(value)))
"""
        }
    )
    command.upgrade(alembic_config(empty_db, directory), "head")
    assert dict(read(empty_db, "SELECT name, value FROM pragma_seen")) == {
        "foreign_keys": "0",
        "journal_mode": "wal",
        "synchronous": "1",
    }


@pytest.mark.spec("T-DB-13:check")
def test_violation_rolls_back_the_whole_run(empty_db: str, test_chain: Callable[..., Path]) -> None:
    directory = test_chain(
        {
            "m0": """def upgrade():
    op.create_table("t0", sa.Column("id", sa.Integer, primary_key=True))
""",
            "m1": """def upgrade():
    op.create_table("parent", sa.Column("id", sa.Integer, primary_key=True))
    op.create_table(
        "child",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("parent_id", sa.Integer, sa.ForeignKey("parent.id"), nullable=False),
    )
""",
            "m2": """def upgrade():
    # foreign_keys=OFF: the insert goes through; only the end-of-run check detects it.
    op.execute("INSERT INTO child (id, parent_id) VALUES (1, 999)")
""",
        }
    )
    config = alembic_config(empty_db, directory)
    command.upgrade(config, "m0")
    before = schema(empty_db)
    assert db_revision(empty_db) == "m0"

    with pytest.raises(Exception, match="foreign key violations"):
        command.upgrade(config, "head")  # m1 then m2, in a single transaction

    assert db_revision(empty_db) == "m0"  # revision from before the run
    assert schema(empty_db) == before  # neither `parent` nor `child`: m1 is rolled back with m2
