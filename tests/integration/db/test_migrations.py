"""Migrations Alembic (III §10.5, docs/database.md §5) : chaîne réelle et chaînes de test hors du dépôt."""

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


def lire(db_path: str, sql: str) -> list[tuple[object, ...]]:
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(sql).fetchall()
    finally:
        conn.close()


def revision_en_base(db_path: str) -> str | None:
    tables = {nom for (nom,) in lire(db_path, "SELECT name FROM sqlite_master WHERE type = 'table'")}
    if "alembic_version" not in tables:
        return None
    lignes = lire(db_path, "SELECT version_num FROM alembic_version")
    return str(lignes[0][0]) if lignes else None


def schema(db_path: str) -> list[tuple[object, ...]]:
    return lire(db_path, "SELECT type, name, sql FROM sqlite_master ORDER BY type, name")


@pytest.fixture
def base_vide(tmp_path: Path) -> str:
    return str(tmp_path / "radar.db")


# ── Chaîne réelle ─────────────────────────────────────────────────────────────────────────────────────────────────


@pytest.mark.spec("T-DB-08")
def test_upgrade_head_depuis_une_base_vide(base_vide: str) -> None:
    command.upgrade(alembic_config(base_vide), "head")
    head = ScriptDirectory.from_config(alembic_config(base_vide)).get_current_head()
    assert revision_en_base(base_vide) == head
    engine = create_migrate_engine(base_vide)
    try:
        with engine.connect() as conn:
            colonnes = {c["name"]: c for c in inspect(conn).get_columns("system_state")}
    finally:
        engine.dispose()
    assert set(colonnes) == {"key", "value", "updated_at"}
    assert all(not c["nullable"] for c in colonnes.values())
    assert all(c["default"] is None for c in colonnes.values())  # aucun défaut SQL (III §10.6)


@pytest.mark.spec("T-DB-08")
def test_chaque_migration_a_un_downgrade_teste(base_vide: str) -> None:
    config = alembic_config(base_vide)
    script = ScriptDirectory.from_config(config)
    revisions = list(script.walk_revisions())  # de head vers la base
    command.upgrade(config, "head")
    for revision in revisions:
        assert callable(getattr(revision.module, "downgrade", None)), revision.revision
        command.downgrade(config, "-1")
        assert revision_en_base(base_vide) == revision.down_revision
    assert "system_state" not in {nom for (nom,) in lire(base_vide, "SELECT name FROM sqlite_master")}


@pytest.mark.spec("T-DB-08")
def test_modele_et_migrations_concordent(base_vide: str) -> None:
    command.upgrade(alembic_config(base_vide), "head")
    engine = create_migrate_engine(base_vide)
    try:
        with engine.connect() as conn:
            differences = compare_metadata(MigrationContext.configure(conn, opts={"compare_type": True}), Base.metadata)
    finally:
        engine.dispose()
    assert differences == []


@pytest.mark.spec("T-DB-13:pragma")
def test_connexion_de_migrate_foreign_keys_off_et_pragma(base_vide: str) -> None:
    engine = create_migrate_engine(base_vide)
    try:
        with engine.connect() as conn:
            lus = {
                nom: conn.execute(text(f"PRAGMA {nom}")).scalar_one()
                for nom in ("foreign_keys", "journal_mode", "synchronous", "busy_timeout", "journal_size_limit")
            }
    finally:
        engine.dispose()
    assert lus == {
        "foreign_keys": 0,
        "journal_mode": "wal",
        "synchronous": 1,
        "busy_timeout": 5000,
        "journal_size_limit": 67_108_864,
    }


# ── Chaînes de test, hors du dépôt ─────────────────────────────────────────────────────────────────────────────────

ENTETE = """from alembic import op
import sqlalchemy as sa

revision = "{revision}"
down_revision = {down}
branch_labels = None
depends_on = None

"""


@pytest.fixture
def chaine_de_test(tmp_path: Path) -> Callable[[dict[str, str]], Path]:
    """Crée un dossier de migrations de test, avec le vrai `env.py`, et les migrations données (révision → corps)."""

    def creer(migrations: dict[str, str]) -> Path:
        dossier = tmp_path / "migrations_test"
        (dossier / "versions").mkdir(parents=True)
        shutil.copy(MIGRATIONS / "env.py", dossier / "env.py")
        shutil.copy(MIGRATIONS / "script.py.mako", dossier / "script.py.mako")
        precedente: str | None = None
        for revision, corps in migrations.items():
            entete = ENTETE.format(revision=revision, down=repr(precedente))
            (dossier / "versions" / f"{revision}.py").write_text(entete + corps + "\n\ndef downgrade():\n    pass\n")
            precedente = revision
        return dossier

    return creer


@pytest.mark.spec("T-DB-13:pragma")
def test_pragma_vus_pendant_une_execution_alembic(base_vide: str, chaine_de_test: Callable[..., Path]) -> None:
    dossier = chaine_de_test(
        {
            "p1": """def upgrade():
    bind = op.get_bind()
    op.execute("CREATE TABLE pragma_vu (nom TEXT PRIMARY KEY, valeur TEXT NOT NULL)")
    for nom in ("foreign_keys", "journal_mode", "synchronous"):
        valeur = bind.exec_driver_sql(f"PRAGMA {nom}").scalar()
        bind.exec_driver_sql("INSERT INTO pragma_vu VALUES (?, ?)", (nom, str(valeur)))
"""
        }
    )
    command.upgrade(alembic_config(base_vide, dossier), "head")
    assert dict(lire(base_vide, "SELECT nom, valeur FROM pragma_vu")) == {
        "foreign_keys": "0",
        "journal_mode": "wal",
        "synchronous": "1",
    }


@pytest.mark.spec("T-DB-13:check")
def test_violation_annule_toute_l_execution(base_vide: str, chaine_de_test: Callable[..., Path]) -> None:
    dossier = chaine_de_test(
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
    # foreign_keys=OFF : l'insertion passe ; seul le contrôle de fin d'exécution la détecte.
    op.execute("INSERT INTO child (id, parent_id) VALUES (1, 999)")
""",
        }
    )
    config = alembic_config(base_vide, dossier)
    command.upgrade(config, "m0")
    avant = schema(base_vide)
    assert revision_en_base(base_vide) == "m0"

    with pytest.raises(Exception, match="violations de clés étrangères"):
        command.upgrade(config, "head")  # m1 puis m2, dans une seule transaction

    assert revision_en_base(base_vide) == "m0"  # révision d'avant l'exécution
    assert schema(base_vide) == avant  # ni `parent` ni `child` : m1 est annulée avec m2
