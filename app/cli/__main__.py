"""Entry point `python -m app.cli`: one subcommand per command of IX §56.4."""

import argparse
import os
import sys
from collections.abc import Sequence

from app.cli import health, validate_config
from app.core.clock import SystemClock
from app.core.logging import configure_logging


def build_parser() -> argparse.ArgumentParser:
    # Invalid usage: argparse prints the usage on stderr and exits with code 2, as the contract requires (IX §56.3).
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="Operations commands (IX §56.4).")
    commands = parser.add_subparsers(dest="command", required=True)
    validate_config.register(commands)
    health.register(commands)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    # Logs on stderr (IX §56.3); the commands run in the worker container (IX §56.4).
    configure_logging(
        service="worker",
        version=os.environ.get("RADAR_VERSION") or "dev",
        level=os.environ.get("LOG_LEVEL") or "INFO",
        clock=SystemClock(),
        secrets=[],
        stream=sys.stderr,
    )
    code: int = args.handler(args)
    return code


if __name__ == "__main__":
    sys.exit(main())
