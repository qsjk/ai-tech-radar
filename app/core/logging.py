"""Logs structurés en JSON et nettoyage des secrets (VII §42.1, §42.4).

- Rendu JSON, une ligne par événement, sur stdout ; les loggers des bibliothèques (module `logging`) passent par le
  même rendu.
- Niveau 1 du nettoyage : les secrets sont des `SecretStr` (`app/core/config.py`).
- Niveau 3 (filet final) : `SecretRedactor` remplace par `***` toute occurrence de la valeur d'un secret configuré,
  dans tous les champs, messages et traces d'exception, et masque les valeurs des clés sensibles.
Le niveau 2 (transport, `HttpClient`) arrive avec la collecte (Sprint 2).
"""

import logging
import sys
from collections.abc import Iterable, Mapping
from typing import Any

import structlog
from structlog.typing import EventDict, Processor, WrappedLogger

from app.core.clock import Clock

MASK = "***"
# Une clé est sensible si son nom, en minuscules et `-` remplacé par `_`, se termine par l'un de ces suffixes
# (VII §42.4 ; décision du 2026-09-24) : `x-api-key`, `set-cookie`, `access_token`, `smtp_password`…
SENSITIVE_SUFFIXES = ("authorization", "password", "token", "secret", "api_key", "cookie")


def is_sensitive_key(name: str) -> bool:
    return name.lower().replace("-", "_").endswith(SENSITIVE_SUFFIXES)


class SecretRedactor:
    """Processeur structlog de nettoyage par valeur et par clé (VII §42.4, niveau 3)."""

    def __init__(self, secrets: Iterable[str]) -> None:
        # Les plus longs d'abord : un secret qui en contient un autre est masqué en entier.
        self._secrets = sorted({s for s in secrets if s}, key=len, reverse=True)

    def __call__(self, logger: WrappedLogger, method_name: str, event_dict: EventDict) -> EventDict:
        return self._clean_mapping(event_dict)

    def _clean_mapping(self, mapping: Mapping[Any, Any]) -> dict[str, Any]:
        # Clés normalisées en texte : une clé non textuelle (ex. un code HTTP) ne doit pas faire perdre la ligne.
        cleaned: dict[str, Any] = {}
        for key, value in mapping.items():
            name = str(key)
            cleaned[name] = MASK if is_sensitive_key(name) else self._clean(value)
        return cleaned

    def _clean(self, value: Any) -> Any:
        if isinstance(value, str):
            return self.clean_text(value)
        if isinstance(value, Mapping):
            return self._clean_mapping(value)
        if isinstance(value, list | tuple | set | frozenset):
            return type(value)(self._clean(item) for item in value)
        if isinstance(value, BaseException):
            return self.clean_text(repr(value))
        return value

    def clean_text(self, text: str) -> str:
        for secret in self._secrets:
            text = text.replace(secret, MASK)
        return text


def _add_timestamp(clock: Clock) -> Processor:
    def processor(logger: WrappedLogger, method_name: str, event_dict: EventDict) -> EventDict:
        event_dict["ts"] = clock.now().isoformat(timespec="milliseconds")
        return event_dict

    return processor


def _add_constants(service: str, version: str) -> Processor:
    def processor(logger: WrappedLogger, method_name: str, event_dict: EventDict) -> EventDict:
        event_dict.setdefault("service", service)
        event_dict.setdefault("version", version)
        return event_dict

    return processor


def build_processors(*, service: str, version: str, clock: Clock, secrets: Iterable[str]) -> list[Processor]:
    """Chaîne commune aux logs structlog et aux logs des bibliothèques. Le nettoyage vient en dernier, après le rendu
    des traces d'exception, pour les couvrir."""
    return [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        _add_timestamp(clock),
        _add_constants(service, version),
        structlog.processors.format_exc_info,
        SecretRedactor(secrets),
    ]


def configure_logging(
    *, service: str, version: str, level: str, clock: Clock, secrets: Iterable[str], stream: Any = None
) -> None:
    """Configure structlog et le module `logging` : JSON sur `stream` (stdout par défaut), niveau `level`."""
    shared = build_processors(service=service, version=version, clock=clock, secrets=list(secrets))
    handler = logging.StreamHandler(stream if stream is not None else sys.stdout)
    handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared,
            processors=[
                structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                structlog.processors.JSONRenderer(),
            ],
        )
    )
    root = logging.getLogger()
    root.handlers[:] = [handler]
    root.setLevel(level)
    structlog.configure(
        processors=[*shared, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=False,
    )
