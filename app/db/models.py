"""Modèles SQLAlchemy : les métadonnées du code, cible des migrations Alembic (docs/database.md §3)."""

from datetime import datetime
from typing import Any

from sqlalchemy import MetaData, String
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.db.types import JSONText, UTCDateTime

# Contraintes et index nommés : le mode batch d'Alembic en a besoin pour les modifier sous SQLite (III §10.5).
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NAMING_CONVENTION)


class SystemState(Base):
    """Table clé/valeur écrite par le worker (docs/database.md §3.19).

    Aucun défaut SQL : l'instant vient de la `Clock` (III §10.6).
    """

    __tablename__ = "system_state"

    key: Mapped[str] = mapped_column(String, primary_key=True)
    value: Mapped[Any] = mapped_column(JSONText(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
