"""Table system_state (docs/database.md §3.19), seule table du Sprint 1.

Révision : 0001
Précédente : aucune
Créée le : 2026-09-26

Réversibilité (VII §36.9) : `downgrade` fourni, il supprime la table.
Aucun défaut SQL : `updated_at` est fourni par l'application, via la `Clock` (III §10.6).
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

import app.db.types

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "system_state",
        sa.Column("key", sa.String(), nullable=False),
        sa.Column("value", app.db.types.JSONText(), nullable=False),
        sa.Column("updated_at", app.db.types.UTCDateTime(), nullable=False),
        sa.PrimaryKeyConstraint("key", name=op.f("pk_system_state")),
    )


def downgrade() -> None:
    op.drop_table("system_state")
