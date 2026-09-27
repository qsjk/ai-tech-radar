"""Project-specific SQLAlchemy types (docs/database.md §2.4, III §10.6)."""

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.engine import Dialect
from sqlalchemy.types import String, Text, TypeDecorator


class UTCDateTime(TypeDecorator[datetime]):
    """UTC instant stored as ISO-8601 text.

    On write, a naive datetime is rejected; a timezone-aware datetime is converted to UTC. On read, the value is
    returned in UTC, timezone-aware. The fixed format (microseconds, `+00:00`) keeps text ordering consistent with
    chronological ordering.
    """

    impl = String
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> str | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("UTCDateTime rejects a naive datetime")
        return value.astimezone(UTC).isoformat(timespec="microseconds")

    def process_result_value(self, value: str | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            raise ValueError(f"naive UTCDateTime value in the database: {value!r}")
        return parsed.astimezone(UTC)


class JSONText(TypeDecorator[Any]):
    """JSON value stored as `TEXT` (docs/database.md §1.1).

    SQLAlchemy's `JSON` type declares the column as `JSON` in SQLite, with NUMERIC affinity: a JSON value that looks
    like a number would be converted. `TEXT` keeps the text as is. Content validation belongs to the Pydantic schemas
    of each use (III §11.0).
    """

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Dialect) -> str | None:
        if value is None:
            return None
        return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)

    def process_result_value(self, value: str | None, dialect: Dialect) -> Any:
        if value is None:
            return None
        return json.loads(value)
