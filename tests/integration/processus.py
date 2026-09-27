"""Sous-processus des tests de niveau processus (worker, app) : logs JSON lus avec délai, attentes bornées."""

import json
import os
import queue
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from tests.integration.db.conftest import RACINE

DELAI = 30.0
"""Borne de chaque attente, en secondes : un dépassement fait échouer le test, il ne le bloque pas."""


def variables_coverage() -> dict[str, str]:
    """Variables de coverage : mesure du sous-processus, sans effet sur le code testé."""
    return {name: value for name, value in os.environ.items() if name.startswith("COVERAGE_")}


def entree(ligne: str) -> dict[str, Any]:
    """Ligne de log JSON ; une ligne brute (hors JSON) est gardée, sans événement."""
    try:
        valeur = json.loads(ligne)
    except json.JSONDecodeError:
        return {"event": None, "brut": ligne}
    return valeur if isinstance(valeur, dict) else {"event": None, "brut": ligne}


class Processus:
    """Sous-processus ; ses logs JSON (stdout) sont lus par un thread et consultés avec délai."""

    def __init__(self, args: list[str], env: dict[str, str], cwd: Path = RACINE) -> None:
        self.popen = subprocess.Popen(args, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.logs: list[dict[str, Any]] = []
        self._lignes: queue.Queue[str | None] = queue.Queue()
        self._lecteur = threading.Thread(target=self._lire, daemon=True)
        self._lecteur.start()

    def _lire(self) -> None:
        assert self.popen.stdout is not None
        for ligne in self.popen.stdout:
            self._lignes.put(ligne)
        self._lignes.put(None)

    def attendre_log(self, event: str, *, debut: bool = False) -> dict[str, Any]:
        """Lit les logs jusqu'à `event` (ou, avec `debut`, un événement qui commence par `event`)."""
        echeance = time.monotonic() + DELAI
        while True:
            ligne = self._lignes.get(timeout=max(0.0, echeance - time.monotonic()))
            if ligne is None:
                raise AssertionError(f"fin du processus avant {event!r} : {self.logs}")
            log = entree(ligne)
            self.logs.append(log)
            if log["event"] == event or (debut and str(log["event"]).startswith(event)):
                return log

    def attendre_fin(self) -> int:
        code = self.popen.wait(timeout=DELAI)
        self._lecteur.join(timeout=DELAI)
        while (ligne := self._lignes.get_nowait() if not self._lignes.empty() else None) is not None:
            self.logs.append(entree(ligne))
        return code

    def evenements(self, prefixe: str = "worker.") -> list[str]:
        """Événements du processus, dans l'ordre (les logs des bibliothèques, Alembic par exemple, sont écartés)."""
        return [str(entree["event"]) for entree in self.logs if str(entree["event"]).startswith(prefixe)]

    def arreter(self) -> None:
        if self.popen.poll() is None:
            self.popen.kill()
            self.popen.wait(timeout=DELAI)
        for flux in (self.popen.stdout, self.popen.stderr):
            if flux is not None:
                flux.close()
