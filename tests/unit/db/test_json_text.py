"""`JSONText` : JSON stocké en texte, sans conversion numérique de SQLite (docs/database.md §1.1)."""

from pathlib import Path

from sqlalchemy import Column, Integer, MetaData, Table, create_engine, insert, select, text

from app.db.types import JSONText


def test_aller_retour_et_stockage_en_texte(tmp_path: Path) -> None:
    engine = create_engine(f"sqlite:///{tmp_path / 'j.db'}")
    metadata = MetaData()
    table = Table("t", metadata, Column("id", Integer, primary_key=True), Column("v", JSONText()))
    metadata.create_all(engine)
    valeurs = [{"at": "2026-09-26T08:00:00+00:00", "n": 3}, 42, "chaîne", [1, 2]]
    with engine.begin() as conn:
        for i, valeur in enumerate(valeurs):
            conn.execute(insert(table).values(id=i, v=valeur))
        relues = [conn.execute(select(table.c.v).where(table.c.id == i)).scalar_one() for i in range(len(valeurs))]
        types = [
            conn.execute(text(f"SELECT typeof(v) FROM t WHERE id = {i}")).scalar_one() for i in range(len(valeurs))
        ]
    engine.dispose()
    assert relues == valeurs
    assert types == ["text"] * len(valeurs)  # 42 reste du texte JSON, pas un entier SQLite
