"""Point d'entrée `python -m app.cli` : une sous-commande par commande de IX §56.4."""

import argparse
import os
import sys
from collections.abc import Sequence

from app.cli import validate_config
from app.core.clock import SystemClock
from app.core.logging import configure_logging


def build_parser() -> argparse.ArgumentParser:
    # Usage invalide : argparse écrit l'usage sur stderr et sort avec le code 2, conforme au contrat (IX §56.3).
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="Commandes d'exploitation (IX §56.4).")
    commands = parser.add_subparsers(dest="command", required=True)
    validate_config.register(commands)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    # Logs sur stderr (IX §56.3) ; les commandes tournent dans le conteneur du worker (IX §56.4).
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
