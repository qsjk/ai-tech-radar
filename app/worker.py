"""Worker : `python -m app.worker` (VII §36.6, VIII §48 D2).

Séquence de démarrage (VII §36.6), dans l'ordre :

1. vérifications : variables d'environnement (`WorkerSettings`, `HTTP_CONTACT` compris), prérequis SQLite
   (III §10.1), révision du schéma égale à `head`, fichiers `config/` (`validate-config`) ;
2. heartbeat démarré : premier `worker_heartbeat` écrit, puis tâche permanente ;
3. étapes à venir, à insérer ici dans cet ordre : requalification des `processing` et des `sending`, chargement des
   modèles, reconstruction de la matrice de similarité, scheduler.

Supervision fail-fast : une tâche permanente qui se termine (exception non gérée comprise) → log `critical` → sortie
en code non nul, Docker relance. Watchdog : thread qui arrête le processus si l'event-loop gèle au-delà de
`ops.watchdog_timeout`. SIGTERM (ou SIGINT) : arrêt propre, tâches annulées et attendues au plus 20 s, code 0.

Codes de sortie, alignés sur le contrat des commandes (IX §56.3) : `0` arrêt propre · `1` échec (prérequis SQLite,
révision du schéma, tâche permanente morte, watchdog) · `2` configuration invalide (environnement ou `config/`).
"""

import argparse
import asyncio
import os
import signal
import sys
from collections.abc import Awaitable, Callable, Sequence
from pathlib import Path
from typing import Any

import structlog
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncEngine

from app.cli import EXIT_FAILURE, EXIT_INVALID, EXIT_OK
from app.core.clock import Clock, SystemClock
from app.core.config import WorkerSettings
from app.core.config_files import ConfigError, ConfigFiles, load_config_files
from app.core.logging import configure_logging
from app.db.engine import create_engine
from app.db.prerequisites import PrerequisiteError, check_prerequisites
from app.db.revision import DEFAULT_SCRIPT_LOCATION, SchemaRevisionError, check_revision
from app.db.session import Database
from app.ops.heartbeat import Heartbeat
from app.ops.watchdog import Watchdog, exit_process

# Relatif au répertoire courant : le dépôt en développement et en CI, /app dans l'image (architecture.md §3.2).
DEFAULT_CONFIG_DIR = Path("config")

STOP_TIMEOUT = 20.0
"""Attente maximale des tâches en cours sur SIGTERM, en secondes (VII §36.6)."""

log = structlog.get_logger()


class Worker:
    """Un processus worker. Les dépendances externes (horloge, vérifications, action du watchdog) sont injectables."""

    def __init__(
        self,
        settings: WorkerSettings,
        *,
        clock: Clock,
        config_dir: Path = DEFAULT_CONFIG_DIR,
        script_location: Path = DEFAULT_SCRIPT_LOCATION,
        prerequisites: Callable[[AsyncEngine], Awaitable[object]] = check_prerequisites,
        on_watchdog_timeout: Callable[[], None] = exit_process,
        handle_signals: bool = True,
    ) -> None:
        self.settings = settings
        self.clock = clock
        self.config_dir = config_dir
        self.script_location = script_location
        self.prerequisites = prerequisites
        self.on_watchdog_timeout = on_watchdog_timeout
        self.handle_signals = handle_signals
        self._stop = asyncio.Event()

    def request_stop(self) -> None:
        """Demande d'arrêt propre : appelé par le gestionnaire de SIGTERM."""
        if not self._stop.is_set():
            log.info("worker.stop.requested")
        self._stop.set()

    async def run(self) -> int:
        db = Database(create_engine(self.settings.radar_db_path), self.clock)
        try:
            config = await self._check(db)
            if isinstance(config, int):
                return config
            return await self._serve(db, config)
        finally:
            await db.dispose()

    async def _check(self, db: Database) -> ConfigFiles | int:
        """Étape 1 : vérifications, avant toute écriture. Un échec refuse le démarrage."""
        try:
            await self.prerequisites(db.engine)
            await check_revision(db.engine, self.script_location)
        except (PrerequisiteError, SchemaRevisionError) as error:
            log.critical("worker.refused", reason=str(error), error_class=error.__class__.__name__)
            return EXIT_FAILURE
        try:
            config = load_config_files(self.config_dir)
        except ConfigError as error:
            log.critical(
                "worker.refused",
                reason=f"configuration invalide ({self.config_dir})",
                issues=[str(issue) for issue in error.issues],
            )
            return EXIT_INVALID
        except OSError as error:
            log.critical("worker.refused", reason=str(error), error_class=error.__class__.__name__)
            return EXIT_FAILURE
        log.info("worker.boot.checked", config_dir=str(self.config_dir))
        return config

    async def _serve(self, db: Database, config: ConfigFiles) -> int:
        ops = config.pipeline.ops
        # Étape 2 : heartbeat démarré, avant toute autre étape.
        heartbeat = Heartbeat(db, self.clock, ops.heartbeat_interval, version=self.settings.radar_version)
        await heartbeat.beat()
        log.info("worker.heartbeat.started", interval_s=ops.heartbeat_interval.total_seconds(), pid=heartbeat.pid)
        # Étapes à venir (VII §36.6) : requalification, chargement des modèles, matrice de similarité, scheduler.

        watchdog = Watchdog(self.clock, ops.watchdog_timeout.total_seconds(), on_timeout=self.on_watchdog_timeout)
        tasks = {
            asyncio.create_task(heartbeat.run(), name="heartbeat"),
            asyncio.create_task(watchdog.refresh(), name="watchdog"),
        }
        watchdog.start()
        self._install_signal_handlers()
        log.info("worker.started", version=self.settings.radar_version, pid=heartbeat.pid)
        try:
            return await self._supervise(tasks)
        finally:
            self._remove_signal_handlers()
            watchdog.stop()

    async def _supervise(self, tasks: set[asyncio.Task[None]]) -> int:
        """Attend la première fin : une tâche permanente (échec) ou la demande d'arrêt (code 0)."""
        stop = asyncio.create_task(self._stop.wait(), name="stop")
        done, _ = await asyncio.wait({*tasks, stop}, return_when=asyncio.FIRST_COMPLETED)
        code = EXIT_OK
        for task in done - {stop}:
            code = EXIT_FAILURE
            error = task.exception() if not task.cancelled() else None
            log.critical("worker.task.failed", task=task.get_name(), exc_info=error)
        await self._shutdown({*tasks, stop})
        log.info("worker.stopped", code=code)
        return code

    async def _shutdown(self, tasks: set[asyncio.Task[Any]]) -> None:
        pending = {task for task in tasks if not task.done()}
        for task in pending:
            task.cancel()
        if pending:
            _, still = await asyncio.wait(pending, timeout=STOP_TIMEOUT)
            if still:
                log.error("worker.stop.timeout", tasks=sorted(task.get_name() for task in still))

    def _install_signal_handlers(self) -> None:
        if self.handle_signals:
            loop = asyncio.get_running_loop()
            for signum in (signal.SIGTERM, signal.SIGINT):
                loop.add_signal_handler(signum, self.request_stop)

    def _remove_signal_handlers(self) -> None:
        if self.handle_signals:
            loop = asyncio.get_running_loop()
            for signum in (signal.SIGTERM, signal.SIGINT):
                loop.remove_signal_handler(signum)


def _problem(loc: tuple[int | str, ...], message: str) -> str:
    """Problème de réglage lisible : variable concernée (si connue) et message, sans la valeur reçue."""
    variable = ".".join(str(part) for part in loc).upper()
    return f"{variable} : {message}" if variable else message


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.worker", description="Worker de l'AI Tech Radar.")
    parser.add_argument(
        "--config-dir",
        type=Path,
        default=DEFAULT_CONFIG_DIR,
        help="dossier des fichiers de configuration (défaut : config, relatif au répertoire courant)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    clock = SystemClock()
    version = os.environ.get("RADAR_VERSION") or "dev"
    try:
        settings = WorkerSettings()
    except ValidationError as error:
        # Réglages illisibles : logs au niveau par défaut, sans les valeurs reçues (un secret peut y figurer).
        configure_logging(service="worker", version=version, level="INFO", clock=clock, secrets=[])
        problems = [_problem(e["loc"], e["msg"]) for e in error.errors(include_input=False)]
        log.critical("worker.refused", reason="variables d'environnement invalides", problems=problems)
        return EXIT_INVALID
    configure_logging(
        service="worker",
        version=settings.radar_version,
        level=settings.log_level,
        clock=clock,
        secrets=settings.secret_values(),
    )
    log.info("worker.boot.started", config_dir=str(args.config_dir))
    try:
        return asyncio.run(Worker(settings, clock=clock, config_dir=args.config_dir).run())
    except Exception:
        log.critical("worker.failed", exc_info=True)
        return EXIT_FAILURE


if __name__ == "__main__":
    sys.exit(main())
