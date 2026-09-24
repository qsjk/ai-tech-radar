"""Types SQLAlchemy propres au projet (docs/database.md §2.4, III §10.6)."""

from datetime import UTC, datetime

from sqlalchemy.engine import Dialect
from sqlalchemy.types import String, TypeDecorator


class UTCDateTime(TypeDecorator[datetime]):
    """Instant UTC stocké en texte ISO-8601.

    À l'écriture, un datetime sans fuseau est refusé ; un datetime avec fuseau est converti en UTC. À la lecture, la
    valeur est renvoyée en UTC, avec fuseau. Le format fixe (microsecondes, `+00:00`) garde le tri textuel cohérent
    avec l'ordre chronologique.
    """

    impl = String
    cache_ok = True

    def process_bind_param(self, value: datetime | None, dialect: Dialect) -> str | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("UTCDateTime refuse un datetime sans fuseau")
        return value.astimezone(UTC).isoformat(timespec="microseconds")

    def process_result_value(self, value: str | None, dialect: Dialect) -> datetime | None:
        if value is None:
            return None
        parsed = datetime.fromisoformat(value)
        if parsed.tzinfo is None:
            raise ValueError(f"valeur UTCDateTime sans fuseau en base : {value!r}")
        return parsed.astimezone(UTC)
