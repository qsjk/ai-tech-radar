"""`python -m app.cli validate-config` : valide les quatre fichiers `config/`, sans base (IV §16.5, IX §56.4).

Codes : `0` configuration valide · `2` configuration invalide, fichier obligatoire absent compris (P-04), ou usage
invalide · `1` échec de l'opération (dossier illisible, par exemple). Le résultat va sur stdout ; chaque problème donne
fichier, entrée (clé) et champ.
"""

import argparse
from pathlib import Path
from typing import Any

import structlog

from app.cli import EXIT_FAILURE, EXIT_INVALID, EXIT_OK
from app.core.config_files import ConfigError, load_config_files

# Relatif au répertoire courant : le dépôt en développement et en CI, /app dans l'image (architecture.md §3.2).
DEFAULT_CONFIG_DIR = Path("config")

log = structlog.get_logger()


def register(commands: Any) -> None:
    parser = commands.add_parser("validate-config", help="valide les fichiers config/, sans base")
    parser.add_argument(
        "--config-dir",
        type=Path,
        default=DEFAULT_CONFIG_DIR,
        help="dossier des fichiers de configuration (défaut : config, relatif au répertoire courant)",
    )
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace) -> int:
    config_dir: Path = args.config_dir
    log.info("config.validate.started", config_dir=str(config_dir))
    try:
        config = load_config_files(config_dir)
    except ConfigError as error:
        print(f"configuration invalide ({config_dir}) : {len(error.issues)} problème(s)")
        for issue in error.issues:
            print(f"  - {issue}")
        log.warning("config.validate.invalid", config_dir=str(config_dir), issues=len(error.issues))
        return EXIT_INVALID
    except OSError as error:
        print(f"échec : lecture de {config_dir} impossible ({error.__class__.__name__} : {error})")
        log.error("config.validate.failed", config_dir=str(config_dir), error_class=error.__class__.__name__)
        return EXIT_FAILURE
    print(
        f"configuration valide ({config_dir}) : {len(config.sources.sources)} source(s), "
        f"{len(config.topics.topics)} topic(s), {len(config.entities.entities)} entité(s)"
    )
    log.info("config.validate.finished", config_dir=str(config_dir))
    return EXIT_OK
