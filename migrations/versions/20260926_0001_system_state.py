"""system_state table (docs/database.md §3.19), the only table of Sprint 1.

Revision: 0001
Revises: none
Created: 2026-09-26

Reversibility (VII §36.9): `downgrade` provided, it drops the table.
No SQL default: `updated_at` is provided by the application, through the `Clock` (III §10.6).
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
