"""SQLite prerequisites (III §10.1, T-DB-01): check by injection, and probe of the real library."""

import asyncio

import pytest

from app.db.engine import create_engine
from app.db.prerequisites import PrerequisiteError, SqliteFeatures, check_features, check_prerequisites

pytestmark = pytest.mark.spec("T-DB-01")


@pytest.mark.parametrize(
    ("features", "expected"),
    [
        (SqliteFeatures(version="3.34.1", fts5=True, json1=True), "3.34.1 too old"),
        (SqliteFeatures(version="3.46.1", fts5=False, json1=True), "FTS5 extension missing"),
        (SqliteFeatures(version="3.46.1", fts5=True, json1=False), "JSON1 functions missing"),
    ],
)
def test_missing_prerequisite_refused_with_an_explicit_message(features: SqliteFeatures, expected: str) -> None:
    with pytest.raises(PrerequisiteError, match=expected):
        check_features(features)


def test_every_missing_item_is_listed() -> None:
    with pytest.raises(PrerequisiteError) as info:
        check_features(SqliteFeatures(version="3.31.0", fts5=False, json1=False))
    message = str(info.value)
    assert "3.31.0" in message and "FTS5" in message and "JSON1" in message


def test_minimum_version_accepted() -> None:
    check_features(SqliteFeatures(version="3.35.0", fts5=True, json1=True))


def test_engine_sqlite_meets_the_prerequisites(db_path: str) -> None:
    async def scenario() -> SqliteFeatures:
        engine = create_engine(db_path)
        try:
            return await check_prerequisites(engine)
        finally:
            await engine.dispose()

    features = asyncio.run(scenario())
    assert features.fts5 and features.json1
