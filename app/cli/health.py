"""`python -m app.cli health`: health detail on stdout, computed by the single module (VII §40, IX §56.4).

Same computation as `/api/health` (`app/ops/health.py`), after the startup checks (IX §56.3: SQLite prerequisites,
revision at `head`, `pipeline.yaml`). The `app` component is not shown: its values (`started_at`, `db_locked_1h`)
belong to the uvicorn process, which the command cannot see. `journal_size_limit` is added to the `database`
component (IX §56.4).

Codes (IX §56.3): `0` detail shown, status `ok` or `degraded` · `1` status `down`, or a failed prerequisite, revision
or read · `2` invalid configuration (`AppSettings`, `pipeline.yaml`) or invalid usage.
"""

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

import structlog
from pydantic import ValidationError
from sqlalchemy import text

from app.cli import EXIT_FAILURE, EXIT_INVALID, EXIT_OK
from app.core.clock import Clock, SystemClock
from app.core.config import AppSettings
from app.core.config_files import ConfigError
from app.db.engine import create_engine
from app.db.session import Database
from app.main import StartupRefused, check_startup
from app.ops.health import HealthChecker, Status

# Relative to the working directory: the repository in development and CI, /app in the image (architecture.md §3.2).
DEFAULT_CONFIG_DIR = Path("config")

log = structlog.get_logger()


def register(commands: Any) -> None:
    parser = commands.add_parser("health", help="health detail: components, conditions, revision, WAL")
    parser.add_argument(
        "--config-dir",
        type=Path,
        default=DEFAULT_CONFIG_DIR,
        help="directory of pipeline.yaml (default: config, relative to the working directory)",
    )
    parser.set_defaults(handler=run)


async def health_detail(settings: AppSettings, config_dir: Path, clock: Clock) -> tuple[int, dict[str, Any] | None]:
    """Startup checks, then health detail; return the exit code and the detail (if any)."""
    db = Database(create_engine(settings.radar_db_path), clock)
    try:
        try:
            pipeline = await check_startup(db, config_dir=config_dir)
        except StartupRefused as error:
            print(f"failed: {error}")
            return (EXIT_INVALID if isinstance(error.__cause__, ConfigError) else EXIT_FAILURE), None
        checker = HealthChecker(
            db,
            clock,
            db_path=settings.radar_db_path,
            heartbeat_stale_after=pipeline.ops.heartbeat_stale_after,
            version=settings.radar_version,
            started_at=clock.now(),
        )
        report = await checker.check()
        detail = report.detail
        detail["components"].pop("app")
        if detail["components"]["database"]["status"] == Status.OK.value:
            async with db.read_session() as session:
                limit = (await session.execute(text("PRAGMA journal_size_limit"))).scalar_one()
            detail["components"]["database"]["journal_size_limit"] = limit
        return (EXIT_FAILURE if report.status is Status.DOWN else EXIT_OK), detail
    finally:
        await db.dispose()


def run(args: argparse.Namespace) -> int:
    try:
        settings = AppSettings()
    except ValidationError as error:
        print("invalid configuration: environment variables")
        for problem in error.errors(include_input=False):
            variable = ".".join(str(part) for part in problem["loc"]).upper()
            print(f"  - {variable}: {problem['msg']}" if variable else f"  - {problem['msg']}")
        return EXIT_INVALID
    code, detail = asyncio.run(health_detail(settings, args.config_dir, SystemClock()))
    if detail is not None:
        print(json.dumps(detail, indent=2, ensure_ascii=False))
        log.info("health.checked", status=detail["status"])
    return code
