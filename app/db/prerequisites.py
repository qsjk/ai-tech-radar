"""SQLite prerequisites checked at startup (III §10.1): version >= 3.35, FTS5 and JSON1.

The check is separate from the probe: `check_features` is pure and testable by injection; `probe_features` queries
the SQLite library actually used by the engine.
"""

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.exc import OperationalError
from sqlalchemy.ext.asyncio import AsyncEngine

from app.db.engine import READ_ONLY_OPTION

MIN_SQLITE_VERSION = (3, 35, 0)


class PrerequisiteError(RuntimeError):
    """Missing SQLite prerequisite: the process refuses to start (T1.6, T1.7)."""


@dataclass(frozen=True)
class SqliteFeatures:
    version: str
    fts5: bool
    json1: bool


def parse_version(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


def check_features(features: SqliteFeatures) -> None:
    """Raise `PrerequisiteError` listing everything that is missing."""
    missing = []
    if parse_version(features.version) < MIN_SQLITE_VERSION:
        minimum = ".".join(map(str, MIN_SQLITE_VERSION))
        missing.append(f"SQLite {features.version} too old: at least {minimum} is required (RETURNING)")
    if not features.fts5:
        missing.append("FTS5 extension missing (full-text search)")
    if not features.json1:
        missing.append("JSON1 functions missing (JSON columns)")
    if missing:
        raise PrerequisiteError("SQLite prerequisites not met: " + "; ".join(missing))


async def probe_features(engine: AsyncEngine) -> SqliteFeatures:
    """Probe the engine's SQLite library, read-only: no write to the main database."""
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
