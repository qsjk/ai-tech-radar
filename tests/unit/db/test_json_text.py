"""`JSONText`: JSON stored as text, without SQLite numeric conversion (docs/database.md §1.1)."""

from pathlib import Path

from sqlalchemy import Column, Integer, MetaData, Table, create_engine, insert, select, text

from app.db.types import JSONText


def test_round_trip_and_text_storage(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'j.db'}")
    metadata = MetaData()
    table = Table("t", metadata, Column("id", Integer, primary_key=True), Column("v", JSONText()))
    metadata.create_all(engine)
    # The non-ASCII string is deliberate: JSONText writes with `ensure_ascii=False`.
    values = [{"at": "2026-09-26T08:00:00+00:00", "n": 3}, 42, "non-ASCII: ü 東京", [1, 2]]
    with engine.begin() as conn:
        for i, value in enumerate(values):
            conn.execute(insert(table).values(id=i, v=value))
        read_back = [conn.execute(select(table.c.v).where(table.c.id == i)).scalar_one() for i in range(len(values))]
        types = [conn.execute(text(f"SELECT typeof(v) FROM t WHERE id = {i}")).scalar_one() for i in range(len(values))]
    engine.dispose()
    assert read_back == values
    assert types == ["text"] * len(values)  # 42 stays JSON text, not a SQLite integer
