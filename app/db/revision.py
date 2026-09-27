"""Vérification de la révision du schéma au démarrage (III §10.1, VII §36.3, T-DB-02).

`app` et `worker` ne migrent jamais (III §10.5) : ils comparent la révision Alembic en base à la révision `head` du
code, et refusent de démarrer si elles diffèrent, base non migrée comprise. Le refus est câblé dans chaque processus
(T1.6, T1.7) ; ce module fournit la vérification.
"""

from pathlib import Path

from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Connection
from sqlalchemy.ext.asyncio import AsyncEngine

from app.db.engine import READ_ONLY_OPTION

# Dépôt et image partagent cette disposition : `migrations/` à côté du paquet `app/` (VIII §46.1).
DEFAULT_SCRIPT_LOCATION = Path(__file__).resolve().parents[2] / "migrations"


class SchemaRevisionError(RuntimeError):
    """La révision en base n'est pas `head` : le processus refuse de démarrer."""


def head_revision(script_location: Path = DEFAULT_SCRIPT_LOCATION) -> str:
    head = ScriptDirectory(str(script_location)).get_current_head()
    if head is None:
        raise SchemaRevisionError(f"aucune migration trouvée dans {script_location}")
    return head


def _current_revision(connection: Connection) -> str | None:
    return MigrationContext.configure(connection).get_current_revision()


async def current_revision(engine: AsyncEngine) -> str | None:
    """Révision Alembic en base, lue en lecture seule ; `None` si la base n'est pas migrée."""
    async with engine.execution_options(**{READ_ONLY_OPTION: True}).connect() as conn:
        revision = await conn.run_sync(_current_revision)
        await conn.rollback()
    return revision


async def check_revision(engine: AsyncEngine, script_location: Path = DEFAULT_SCRIPT_LOCATION) -> str:
    """Renvoie la révision si elle est `head` ; lève `SchemaRevisionError` avec un message explicite sinon."""
    expected = head_revision(script_location)
    actual = await current_revision(engine)
    if actual is None:
        raise SchemaRevisionError(
            f"base non migrée : aucune révision Alembic, `head` attendue ({expected}) ; lancer le service migrate"
        )
    if actual != expected:
        raise SchemaRevisionError(
            f"schéma à la révision {actual}, `head` attendue ({expected}) ; lancer le service migrate, ou déployer le "
            "code qui correspond à cette révision"
        )
    return actual
