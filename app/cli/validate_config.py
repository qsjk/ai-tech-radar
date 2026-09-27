"""`python -m app.cli validate-config`: validate the four `config/` files, without a database (IV §16.5, IX §56.4).

Codes: `0` valid configuration · `2` invalid configuration, missing required file included (P-04), or invalid usage ·
`1` operation failed (unreadable directory, for example). The result goes to stdout; each problem gives file, entry
(key) and field.
"""

import argparse
from pathlib import Path
from typing import Any

import structlog

from app.cli import EXIT_FAILURE, EXIT_INVALID, EXIT_OK
from app.core.config_files import ConfigError, load_config_files

# Relative to the working directory: the repository in development and CI, /app in the image (architecture.md §3.2).
DEFAULT_CONFIG_DIR = Path("config")

log = structlog.get_logger()


def register(commands: Any) -> None:
    parser = commands.add_parser("validate-config", help="validate the config/ files, without a database")
    parser.add_argument(
        "--config-dir",
        type=Path,
        default=DEFAULT_CONFIG_DIR,
        help="directory of the configuration files (default: config, relative to the working directory)",
    )
    parser.set_defaults(handler=run)


def run(args: argparse.Namespace) -> int:
    config_dir: Path = args.config_dir
    log.info("config.validate.started", config_dir=str(config_dir))
    try:
        config = load_config_files(config_dir)
    except ConfigError as error:
        print(f"invalid configuration ({config_dir}): {len(error.issues)} problem(s)")
        for issue in error.issues:
            print(f"  - {issue}")
        log.warning("config.validate.invalid", config_dir=str(config_dir), issues=len(error.issues))
        return EXIT_INVALID
    except OSError as error:
        print(f"failed: cannot read {config_dir} ({error.__class__.__name__}: {error})")
        log.error("config.validate.failed", config_dir=str(config_dir), error_class=error.__class__.__name__)
        return EXIT_FAILURE
    print(
        f"valid configuration ({config_dir}): {len(config.sources.sources)} source(s), "
        f"{len(config.topics.topics)} topic(s), {len(config.entities.entities)} entity(ies)"
    )
    log.info("config.validate.finished", config_dir=str(config_dir))
    return EXIT_OK
