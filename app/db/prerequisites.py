"""Prérequis SQLite vérifiés au démarrage (III §10.1) : version ≥ 3.35, FTS5 et JSON1.

La vérification est séparée de la sonde : `check_features` est pure et testable par injection ; `probe_features`
interroge la bibliothèque SQLite réellement utilisée par le moteur.
"""

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncEngine

from app.db.engine import READ_ONLY_OPTION

MIN_SQLITE_VERSION = (3, 35, 0)


class PrerequisiteError(RuntimeError):
    """Prérequis SQLite manquant : le processus refuse de démarrer (T1.6, T1.7)."""


@dataclass(frozen=True)
class SqliteFeatures:
    version: str
    fts5: bool
    json1: bool


def parse_version(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def check_features(features: SqliteFeatures) -> None:
    """Lève `PrerequisiteError` avec la liste de tout ce qui manque."""
    missing = []
    if parse_version(features.version) < MIN_SQLITE_VERSION:
        minimum = ".".join(map(str, MIN_SQLITE_VERSION))
        missing.append(f"SQLite {features.version} trop ancien : {minimum} au moins est requis (RETURNING)")
    if not features.fts5:
        missing.append("extension FTS5 absente (recherche plein texte)")
    if not features.json1:
        missing.append("fonctions JSON1 absentes (colonnes JSON)")
    if missing:
        raise PrerequisiteError("prérequis SQLite non satisfaits : " + " ; ".join(missing))


async def probe_features(engine: AsyncEngine) -> SqliteFeatures:
    """Sonde la bibliothèque SQLite du moteur, en lecture seule : aucune écriture dans la base principale."""
    async with engine.execution_options(**{READ_ONLY_OPTION: True}).connect() as conn:
        version = (await conn.execute(text("SELECT sqlite_version()"))).scalar_one()
        try:
            await conn.execute(text("SELECT json('{}')"))
            json1 = True
        except OperationalError:
            json1 = False
        try:
            await conn.execute(text("CREATE VIRTUAL TABLE temp.radar_probe_fts USING fts5(x)"))
            await conn.execute(text("DROP TABLE temp.radar_probe_fts"))
            fts5 = True
        except OperationalError:
            fts5 = False
        await conn.rollback()
    return SqliteFeatures(version=str(version), fts5=fts5, json1=json1)


async def check_prerequisites(engine: AsyncEngine) -> SqliteFeatures:
    features = await probe_features(engine)
    check_features(features)
    return features
