"""`UTCDateTime` (III §10.6)."""

from datetime import UTC, datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import Column, Integer, MetaData, Table, create_engine, insert, select
from sqlalchemy.exc import StatementError

from app.db.types import UTCDateTime

pytestmark = pytest.mark.spec("T-DB-07")

PARIS_SUMMER = timezone(timedelta(hours=2))


def test_rejects_a_naive_datetime_on_write() -> None:
    with pytest.raises(ValueError, match="naive datetime"):
        UTCDateTime().process_bind_param(datetime(2026, 9, 24, 10, 0), dialect=None)  # type: ignore[arg-type]


def test_converts_to_utc_on_write() -> None:
    stored = UTCDateTime().process_bind_param(datetime(2026, 9, 24, 10, 0, tzinfo=PARIS_SUMMER), dialect=None)  # type: ignore[arg-type]
    assert stored == "2026-09-24T08:00:00.000000+00:00"


def test_sqlite_round_trip_returns_utc(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 't.db'}")
    metadata = MetaData()
    table = Table("t", metadata, Column("id", Integer, primary_key=True), Column("at", UTCDateTime()))
    metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(insert(table).values(id=1, at=datetime(2026, 9, 24, 10, 0, tzinfo=PARIS_SUMMER)))
        read = conn.execute(select(table.c.at)).scalar_one()
        with pytest.raises(StatementError):
            conn.execute(insert(table).values(id=2, at=datetime(2026, 9, 24, 10, 0)))
    assert read == datetime(2026, 9, 24, 8, 0, tzinfo=UTC)
    assert read.tzinfo is not None and read.utcoffset() == timedelta(0)
    engine.dispose()
