"""Environnement Alembic du service `migrate` (docs/database.md §5, III §10.5).

- Moteur synchrone propre à `migrate`, sur l'URL construite à partir de `RADAR_DB_PATH` (aucune URL dans
  `alembic.ini`, architecture.md P-01).
- `foreign_keys=OFF` posé à la connexion, hors transaction ; `BEGIN IMMEDIATE` émis à l'ouverture de la transaction.
- `transactional_ddl=True` et `transaction_per_migration=False` : toute l'exécution tient dans **une seule**
  transaction. Alembic déclare SQLite sans DDL transactionnel ; sans ces deux réglages, chaque migration serait validée
  séparément.
- `PRAGMA foreign_key_check` après `run_migrations()`, dans cette transaction, avant le commit : une violation lève une
  exception et annule tout ; la révision Alembic et le schéma restent ceux d'avant l'exécution.
"""

import os

from alembic import context

from app.db.engine import create_migrate_engine
from app.db.models import Base

target_metadata = Base.metadata


class ForeignKeyViolationError(RuntimeError):
    """`PRAGMA foreign_key_check` a trouvé au moins une violation : l'exécution est annulée."""


def _db_path() -> str:
    path = context.config.attributes.get("radar_db_path") or os.environ.get("RADAR_DB_PATH")
    if not path:
        raise RuntimeError("RADAR_DB_PATH absente : chemin de la base inconnu (architecture.md P-01)")
    return str(path)


def run_migrations_online() -> None:
    engine = create_migrate_engine(_db_path())
    try:
        with engine.connect() as connection:
            context.configure(
                connection=connection,
                target_metadata=target_metadata,
                render_as_batch=True,
                transactional_ddl=True,  # Alembic déclare SQLite sans DDL transactionnel
                transaction_per_migration=False,  # une seule transaction pour toute l'exécution
            )
            with context.begin_transaction():
                context.run_migrations()
                violations = connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
                if violations:  # exception : rollback, révision et schéma inchangés
                    raise ForeignKeyViolationError(f"violations de clés étrangères : {violations}")
    finally:
        engine.dispose()


if context.is_offline_mode():
    raise RuntimeError("mode hors ligne (--sql) non pris en charge : migrate s'exécute sur la base (III §10.5)")
run_migrations_online()
