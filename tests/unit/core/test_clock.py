"""Horloge injectable (ADR-0016). Pas d'identifiant de catalogue : la `Clock` est une règle transverse (VIII §50.1)."""

import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from app.core.clock import Clock, SystemClock
from tests.fakes.clock import ManualClock


def test_system_clock_renvoie_un_instant_utc_avec_fuseau() -> None:
    now = SystemClock().now()
    assert now.tzinfo is not None
    assert now.utcoffset() == timedelta(0)


def test_manual_clock_avance_sans_attente_reelle() -> None:
    clock: Clock = ManualClock(datetime(2026, 9, 24, 8, 0, tzinfo=UTC))
    asyncio.run(clock.sleep(3600))
    assert clock.now() == datetime(2026, 9, 24, 9, 0, tzinfo=UTC)
    assert clock.monotonic() == 3600.0


def test_manual_clock_refuse_un_instant_naif_et_un_recul() -> None:
    with pytest.raises(ValueError):
        ManualClock(datetime(2026, 9, 24))
    clock = ManualClock()
    with pytest.raises(ValueError):
        clock.advance(timedelta(seconds=-1))
