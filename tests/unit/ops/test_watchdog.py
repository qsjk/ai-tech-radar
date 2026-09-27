"""Watchdog de l'event-loop (VII §36.6) : logique, avec une horloge manuelle et une action d'arrêt espionne."""

import asyncio
import threading
from datetime import timedelta

import pytest
from structlog.testing import capture_logs

from app.ops.watchdog import REFRESH_INTERVAL, Watchdog
from tests.fakes.clock import ManualClock, SteppedClock


class Arret:
    def __init__(self) -> None:
        self.appels = 0
        self.fait = threading.Event()

    def __call__(self) -> None:
        self.appels += 1
        self.fait.set()


@pytest.mark.spec("T-OPS-07")
def test_pas_d_arret_tant_que_le_delai_n_est_pas_depasse() -> None:
    clock = ManualClock()
    arret = Arret()
    watchdog = Watchdog(clock, 300, on_timeout=arret)
    clock.advance(timedelta(seconds=300))
    assert watchdog.check() is False
    assert arret.appels == 0


@pytest.mark.spec("T-OPS-07")
def test_arret_au_dela_du_delai_avec_log_critical_une_seule_fois() -> None:
    clock = ManualClock()
    arret = Arret()
    watchdog = Watchdog(clock, 300, on_timeout=arret)
    clock.advance(timedelta(seconds=301))
    with capture_logs() as logs:
        assert watchdog.check() is True
        assert watchdog.check() is True
    assert arret.appels == 1
    assert [(e["event"], e["log_level"], e["timeout_s"]) for e in logs] == [
        ("worker.watchdog.timeout", "critical", 300)
    ]


@pytest.mark.spec("T-OPS-07")
def test_le_rafraichissement_repousse_l_echeance() -> None:
    clock = ManualClock()
    arret = Arret()
    watchdog = Watchdog(clock, 300, on_timeout=arret)
    for _ in range(10):
        clock.advance(timedelta(seconds=200))
        watchdog.beat()
        assert watchdog.check() is False
    assert arret.appels == 0


@pytest.mark.spec("T-OPS-07")
def test_la_boucle_rafraichit_toutes_les_5_s() -> None:
    async def scenario() -> list[float]:
        clock = SteppedClock()
        watchdog = Watchdog(clock, 300, on_timeout=Arret())
        tache = asyncio.create_task(watchdog.refresh())
        figes = []
        try:
            for _ in range(3):
                while clock.sleepers == 0:
                    await asyncio.sleep(0)
                clock.advance(timedelta(seconds=4))
                figes.append(watchdog.frozen_for())
                clock.advance(timedelta(seconds=1))
                await asyncio.sleep(0)
        finally:
            tache.cancel()
            await asyncio.gather(tache, return_exceptions=True)
        return figes

    assert REFRESH_INTERVAL == 5.0
    assert asyncio.run(scenario()) == [4.0, 4.0, 4.0]


@pytest.mark.spec("T-OPS-07")
def test_le_thread_declenche_l_action_d_arret() -> None:
    clock = ManualClock()
    arret = Arret()
    watchdog = Watchdog(clock, 300, on_timeout=arret, check_interval=0.001)
    watchdog.start()
    try:
        clock.advance(timedelta(seconds=301))
        assert arret.fait.wait(timeout=5)
    finally:
        watchdog.stop()
    assert arret.appels == 1


@pytest.mark.spec("T-OPS-07")
def test_stop_arrete_le_thread_sans_action() -> None:
    arret = Arret()
    watchdog = Watchdog(ManualClock(), 300, on_timeout=arret, check_interval=0.001)
    watchdog.start()
    watchdog.stop()
    assert arret.appels == 0
