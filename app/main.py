"""App FastAPI (ADR-0005) : un seul processus uvicorn, `/health` et `/api/health` (VII §40).

Lancement (VII §36.5) : `uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1 --no-access-log`.

`app` est construite au premier accès à l'attribut (PEP 562), pas à l'import : les tests importent `create_app` sans
lire l'environnement. Refus de démarrer :

- `AppSettings` invalide (dont `DASHBOARD_URL`) : log `critical` `app.refused`, sortie en code 2, avant l'écoute ;
- dans le lifespan, dans l'ordre : prérequis SQLite (III §10.1), révision à `head`, `pipeline.yaml` lu seul
  (E17, P-05, même message que le worker) ; un échec → log `critical` `app.refused`, uvicorn sort en code 3.
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

# Relatif au répertoire courant : le dépôt en développement et en CI, /app dans l'image (architecture.md §3.2).
DEFAULT_CONFIG_DIR = Path("config")

log = structlog.get_logger()


class StartupRefused(RuntimeError):
    """Un contrôle de démarrage a échoué : l'app refuse de démarrer (III §10.1, P-05)."""


async def check_startup(
    db: Database,
    *,
    config_dir: Path,
    script_location: Path = DEFAULT_SCRIPT_LOCATION,
    prerequisites: Callable[[AsyncEngine], Awaitable[object]] = check_prerequisites,
) -> PipelineConfig:
    """Contrôles de démarrage communs à l'app et à `app.cli health` ; lève `StartupRefused` après un log `critical`."""
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
            reason=f"configuration invalide ({config_dir})",
            issues=[str(issue) for issue in error.issues],
        )
        raise StartupRefused(f"configuration invalide ({config_dir})") from error


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
    """Construit l'app. Les dépendances externes (horloge, prérequis, lecture de santé) sont injectables."""
    horloge: Clock = clock if clock is not None else SystemClock()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        started_at = horloge.now()
        db = Database(create_engine(settings.radar_db_path), horloge)
        try:
            pipeline = await check_startup(
                db, config_dir=config_dir, script_location=script_location, prerequisites=prerequisites
            )
            app.state.health = HealthChecker(
                db,
                horloge,
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

    # Documentation interactive seulement en développement (T-SEC-05, VII §37.4).
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
        """Sonde publique : `{status}` seul ; 200 pour `ok` et `degraded`, 503 pour `down` (VII §40.2)."""
        report = await request.app.state.health.check()
        return JSONResponse(report.public(), status_code=report.http_code)

    @app.get("/api/health")
    async def api_health(request: Request) -> JSONResponse:
        """Détail par composant (VII §40.3) ; l'authentification est portée par Caddy."""
        report = await request.app.state.health.check()
        return JSONResponse(report.detail)

    return app


def load_settings(clock: Clock) -> AppSettings:
    """Lit `AppSettings` et configure les logs (`service="app"`) ; réglages invalides → code 2, sans valeur reçue."""
    try:
        settings = AppSettings()
    except ValidationError as error:
        configure_logging(service="app", version="dev", level="INFO", clock=clock, secrets=[])
        problems = []
        for detail in error.errors(include_input=False):
            variable = ".".join(str(part) for part in detail["loc"]).upper()
            problems.append(f"{variable} : {detail['msg']}" if variable else detail["msg"])
        log.critical("app.refused", reason="variables d'environnement invalides", problems=problems)
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
    """Les logs d'uvicorn passent par le rendu JSON commun (VII §42.1) ; l'access log reste coupé (§42.3)."""
    for name in ("uvicorn", "uvicorn.error"):
        logger = logging.getLogger(name)
        logger.handlers.clear()
        logger.propagate = True


_app: FastAPI | None = None


def __getattr__(name: str) -> Any:
    """`app.main:app` pour uvicorn : construite au premier accès (PEP 562)."""
    global _app
    if name != "app":
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    if _app is None:
        clock = SystemClock()
        settings = load_settings(clock)
        route_uvicorn_logs()
        _app = create_app(settings, clock=clock)
    return _app
