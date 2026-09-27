"""`python -m app.cli health` : détail de santé sur stdout, calculé par le module unique (VII §40, IX §56.4).

Même calcul que `/api/health` (`app/ops/health.py`), après les vérifications de démarrage (IX §56.3 : prérequis
SQLite, révision à `head`, `pipeline.yaml`). Le composant `app` n'est pas affiché : ses valeurs (`started_at`,
`db_locked_1h`) sont celles du processus uvicorn, que la commande ne voit pas. `journal_size_limit` est ajouté au
composant `database` (IX §56.4).

Codes (IX §56.3) : `0` détail affiché, statut `ok` ou `degraded` · `1` statut `down`, ou échec d'un prérequis, de la
révision ou de la lecture · `2` configuration invalide (`AppSettings`, `pipeline.yaml`) ou usage invalide.
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

# Relatif au répertoire courant : le dépôt en développement et en CI, /app dans l'image (architecture.md §3.2).
DEFAULT_CONFIG_DIR = Path("config")

log = structlog.get_logger()


def register(commands: Any) -> None:
    parser = commands.add_parser("health", help="détail de santé : composants, conditions, révision, WAL")
    parser.add_argument(
        "--config-dir",
        type=Path,
        default=DEFAULT_CONFIG_DIR,
        help="dossier de pipeline.yaml (défaut : config, relatif au répertoire courant)",
    )
    parser.set_defaults(handler=run)


async def health_detail(settings: AppSettings, config_dir: Path, clock: Clock) -> tuple[int, dict[str, Any] | None]:
    """Vérifications de démarrage puis détail de santé ; renvoie le code de sortie et le détail (s'il existe)."""
    db = Database(create_engine(settings.radar_db_path), clock)
    try:
        try:
            pipeline = await check_startup(db, config_dir=config_dir)
        except StartupRefused as error:
            print(f"échec : {error}")
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
        print("configuration invalide : variables d'environnement")
        for problem in error.errors(include_input=False):
            variable = ".".join(str(part) for part in problem["loc"]).upper()
            print(f"  - {variable} : {problem['msg']}" if variable else f"  - {problem['msg']}")
        return EXIT_INVALID
    code, detail = asyncio.run(health_detail(settings, args.config_dir, SystemClock()))
    if detail is not None:
        print(json.dumps(detail, indent=2, ensure_ascii=False))
        log.info("health.checked", status=detail["status"])
    return code
