"""Worker: `python -m app.worker` (VII §36.6, VIII §48 D2).

Startup sequence (VII §36.6), in order:

1. checks: environment variables (`WorkerSettings`, `HTTP_CONTACT` included), SQLite prerequisites (III §10.1),
   schema revision equal to `head`, `config/` files (`validate-config`);
2. heartbeat started: first `worker_heartbeat` written, then the permanent task;
3. upcoming steps, to be inserted here in this order: requalification of `processing` and `sending`, model loading,
   similarity matrix rebuild, scheduler.

Fail-fast supervision: a permanent task that ends (unhandled exception included) → `critical` log → non-zero exit,
Docker restarts. Watchdog: a thread that stops the process if the event loop freezes beyond `ops.watchdog_timeout`.
SIGTERM (or SIGINT): clean stop, tasks cancelled and awaited for at most 20 s, code 0.

Exit codes, aligned with the command contract (IX §56.3): `0` clean stop · `1` failure (SQLite prerequisites, schema
revision, dead permanent task, watchdog) · `2` invalid configuration (environment or `config/`).
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

# Relative to the working directory: the repository in development and CI, /app in the image (architecture.md §3.2).
DEFAULT_CONFIG_DIR = Path("config")

STOP_TIMEOUT = 20.0
"""Maximum wait for running tasks on SIGTERM, in seconds (VII §36.6)."""

log = structlog.get_logger()


class Worker:
    """A worker process. External dependencies (clock, checks, watchdog action) are injectable."""

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
        """Clean stop request: called by the SIGTERM handler."""
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
        """Step 1: checks, before any write. A failure refuses the start."""
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
                reason=f"invalid configuration ({self.config_dir})",
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
        # Step 2: heartbeat started, before any other step.
        heartbeat = Heartbeat(db, self.clock, ops.heartbeat_interval, version=self.settings.radar_version)
        await heartbeat.beat()
        log.info("worker.heartbeat.started", interval_s=ops.heartbeat_interval.total_seconds(), pid=heartbeat.pid)
        # Upcoming steps (VII §36.6): requalification, model loading, similarity matrix, scheduler.

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
        """Wait for the first to finish: a permanent task (failure) or the stop request (code 0)."""
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
    """Readable settings problem: the variable concerned (if known) and the message, without the received value."""
    variable = ".".join(str(part) for part in loc).upper()
    return f"{variable}: {message}" if variable else message


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="python -m app.worker", description="AI Tech Radar worker.")
    parser.add_argument(
        "--config-dir",
        type=Path,
        default=DEFAULT_CONFIG_DIR,
        help="directory of the configuration files (default: config, relative to the working directory)",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    clock = SystemClock()
    version = os.environ.get("RADAR_VERSION") or "dev"
    try:
        settings = WorkerSettings()
    except ValidationError as error:
        # Unreadable settings: logs at the default level, without the received values (a secret may be among them).
        configure_logging(service="worker", version=version, level="INFO", clock=clock, secrets=[])
        problems = [_problem(e["loc"], e["msg"]) for e in error.errors(include_input=False)]
        log.critical("worker.refused", reason="invalid environment variables", problems=problems)
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
