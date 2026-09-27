"""FastAPI app (ADR-0005): a single uvicorn process, `/health` and `/api/health` (VII §40).

Launch (VII §36.5): `uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 --no-access-log`.

`app` is built on first attribute access (PEP 562), not at import: tests import `create_app` without reading the
environment. Refusal to start:

- invalid `AppSettings` (including `DASHBOARD_URL`): `critical` log `app.refused`, exit code 2, before listening;
- in the lifespan, in order: SQLite prerequisites (III §10.1), revision at `head`, `pipeline.yaml` loaded alone
  (E17, P-05, same message as the worker); a failure → `critical` log `app.refused`, uvicorn exits with code 3.
"""

import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncEngine

from app.cli import EXIT_INVALID
from app.core.clock import Clock, SystemClock
from app.core.config import AppEnv, AppSettings
from app.core.config_files import ConfigError, PipelineConfig, load_pipeline
from app.core.logging import configure_logging
from app.db.engine import create_engine
from app.db.prerequisites import PrerequisiteError, check_prerequisites
from app.db.revision import DEFAULT_SCRIPT_LOCATION, SchemaRevisionError, check_revision
from app.db.session import Database
from app.ops.health import READ_TIMEOUT, HealthChecker, Reader, read_state

# Relative to the working directory: the repository in development and CI, /app in the image (architecture.md §3.2).
DEFAULT_CONFIG_DIR = Path("config")

log = structlog.get_logger()


class StartupRefused(RuntimeError):
    """A startup check failed: the app refuses to start (III §10.1, P-05)."""


async def check_startup(
    db: Database,
    *,
    config_dir: Path,
    script_location: Path = DEFAULT_SCRIPT_LOCATION,
    prerequisites: Callable[[AsyncEngine], Awaitable[object]] = check_prerequisites,
) -> PipelineConfig:
    """Startup checks shared by the app and `app.cli health`; raise `StartupRefused` after a `critical` log."""
    try:
        await prerequisites(db.engine)
        await check_revision(db.engine, script_location)
    except (PrerequisiteError, SchemaRevisionError) as error:
        log.critical("app.refused", reason=str(error), error_class=error.__class__.__name__)
        raise StartupRefused(str(error)) from error
    try:
        return load_pipeline(config_dir)
    except ConfigError as error:
        log.critical(
            "app.refused",
            reason=f"invalid configuration ({config_dir})",
            issues=[str(issue) for issue in error.issues],
        )
        raise StartupRefused(f"invalid configuration ({config_dir})") from error


def create_app(
    settings: AppSettings,
    *,
    clock: Clock | None = None,
    config_dir: Path = DEFAULT_CONFIG_DIR,
    script_location: Path = DEFAULT_SCRIPT_LOCATION,
    prerequisites: Callable[[AsyncEngine], Awaitable[object]] = check_prerequisites,
    reader: Reader = read_state,
    read_timeout: float = READ_TIMEOUT,
) -> FastAPI:
    """Build the app. External dependencies (clock, prerequisites, health read) are injectable."""
    app_clock: Clock = clock if clock is not None else SystemClock()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        started_at = app_clock.now()
        db = Database(create_engine(settings.radar_db_path), app_clock)
        try:
            pipeline = await check_startup(
                db, config_dir=config_dir, script_location=script_location, prerequisites=prerequisites
            )
            app.state.health = HealthChecker(
                db,
                app_clock,
                db_path=settings.radar_db_path,
                heartbeat_stale_after=pipeline.ops.heartbeat_stale_after,
                version=settings.radar_version,
                started_at=started_at,
                reader=reader,
                read_timeout=read_timeout,
            )
            log.info("app.started", version=settings.radar_version, app_env=settings.app_env.value)
            yield
            log.info("app.stopped")
        finally:
            await db.dispose()

    # Interactive documentation in development only (T-SEC-05, VII §37.4).
    development = settings.app_env is AppEnv.DEVELOPMENT
    app = FastAPI(
        title="AI Tech Radar",
        version=settings.radar_version,
        docs_url="/docs" if development else None,
        redoc_url="/redoc" if development else None,
        openapi_url="/openapi.json" if development else None,
        lifespan=lifespan,
    )

    @app.get("/health")
    async def health(request: Request) -> JSONResponse:
        """Public probe: `{status}` alone; 200 for `ok` and `degraded`, 503 for `down` (VII §40.2)."""
        report = await request.app.state.health.check()
        return JSONResponse(report.public(), status_code=report.http_code)

    @app.get("/api/health")
    async def api_health(request: Request) -> JSONResponse:
        """Per-component detail (VII §40.3); authentication is handled by Caddy."""
        report = await request.app.state.health.check()
        return JSONResponse(report.detail)

    return app


def load_settings(clock: Clock) -> AppSettings:
    """Read `AppSettings` and configure logging (`service="app"`); invalid settings → code 2, value not shown."""
    try:
        settings = AppSettings()
    except ValidationError as error:
        configure_logging(service="app", version="dev", level="INFO", clock=clock, secrets=[])
        problems = []
        for detail in error.errors(include_input=False):
            variable = ".".join(str(part) for part in detail["loc"]).upper()
            problems.append(f"{variable}: {detail['msg']}" if variable else detail["msg"])
        log.critical("app.refused", reason="invalid environment variables", problems=problems)
        raise SystemExit(EXIT_INVALID) from None
    configure_logging(
        service="app",
        version=settings.radar_version,
        level=settings.log_level,
        clock=clock,
        secrets=settings.secret_values(),
    )
    return settings


def route_uvicorn_logs() -> None:
    """uvicorn logs go through the common JSON rendering (VII §42.1); the access log stays off (§42.3)."""
    for name in ("uvicorn", "uvicorn.error"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True


_app: FastAPI | None = None


def __getattr__(name: str) -> Any:
    """`app.main:app` for uvicorn: built on first access (PEP 562)."""
    global _app
    if name != "app":
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    if _app is None:
        clock = SystemClock()
        settings = load_settings(clock)
        route_uvicorn_logs()
        _app = create_app(settings, clock=clock)
    return _app
