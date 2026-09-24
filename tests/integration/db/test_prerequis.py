"""Prérequis SQLite (III §10.1, T-DB-01) : vérification par injection, et sonde de la bibliothèque réelle."""

import asyncio

import pytest

from app.db.engine import create_engine
from app.db.prerequisites import PrerequisiteError, SqliteFeatures, check_features, check_prerequisites

pytestmark = pytest.mark.spec("T-DB-01")


@pytest.mark.parametrize(
    ("features", "attendu"),
    [
        (SqliteFeatures(version="3.34.1", fts5=True, json1=True), "3.34.1 trop ancien"),
        (SqliteFeatures(version="3.46.1", fts5=False, json1=True), "FTS5 absente"),
        (SqliteFeatures(version="3.46.1", fts5=True, json1=False), "JSON1 absentes"),
    ],
)
def test_prerequis_manquant_refuse_avec_un_message_explicite(features: SqliteFeatures, attendu: str) -> None:
    with pytest.raises(PrerequisiteError, match=attendu):
        check_features(features)


def test_tous_les_manques_sont_listes() -> None:
    with pytest.raises(PrerequisiteError) as info:
        check_features(SqliteFeatures(version="3.31.0", fts5=False, json1=False))
    message = str(info.value)
    assert "3.31.0" in message and "FTS5" in message and "JSON1" in message


def test_version_minimale_acceptee() -> None:
    check_features(SqliteFeatures(version="3.35.0", fts5=True, json1=True))


def test_sqlite_du_moteur_satisfait_les_prerequis(db_path: str) -> None:
    async def scenario() -> SqliteFeatures:
        engine = create_engine(db_path)
        try:
            return await check_prerequisites(engine)
        finally:
            await engine.dispose()

    features = asyncio.run(scenario())
    assert features.fts5 and features.json1
