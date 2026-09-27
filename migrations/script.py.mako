"""${message}

Révision : ${up_revision}
Précédente : ${down_revision | comma,n}
Créée le : ${create_date}

Réversibilité (VII §36.9) : ce fichier fournit un `downgrade`, ou déclare ici « irréversible » avec la raison.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
${imports if imports else ""}

revision: str = ${repr(up_revision)}
down_revision: str | Sequence[str] | None = ${repr(down_revision)}
branch_labels: str | Sequence[str] | None = ${repr(branch_labels)}
depends_on: str | Sequence[str] | None = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
