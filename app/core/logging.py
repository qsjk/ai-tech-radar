"""Structured JSON logs and secret redaction (VII §42.1, §42.4).

- JSON rendering, one line per event, on stdout; library loggers (`logging` module) go through the same rendering.
- Redaction level 1: secrets are `SecretStr` (`app/core/config.py`).
- Level 3 (final safety net): `SecretRedactor` replaces with `***` every occurrence of a configured secret value, in
  every field, message and exception traceback, and masks the values of sensitive keys.
Level 2 (transport, `HttpClient`) comes with collection (Sprint 2).
"""

import logging
import sys
from collections.abc import Iterable, Mapping
from typing import Any

import structlog
from structlog.typing import EventDict, Processor, WrappedLogger

from app.core.clock import Clock

MASK = "***"
# A key is sensitive if its name, lowercased with `-` replaced by `_`, ends with one of these suffixes
# (VII §42.4; decision of 2026-09-24): `x-api-key`, `set-cookie`, `access_token`, `smtp_password`...
SENSITIVE_SUFFIXES = ("authorization", "password", "token", "secret", "api_key", "cookie")


def is_sensitive_key(name: str) -> bool:
    return name.lower().replace("-", "_").endswith(SENSITIVE_SUFFIXES)


class SecretRedactor:
    """structlog processor redacting by value and by key (VII §42.4, level 3)."""

    def __init__(self, secrets: Iterable[str]) -> None:
        # Longest first: a secret that contains another one is masked in full.
        self._secrets = sorted({s for s in secrets if s}, key=len, reverse=True)

    def __call__(self, logger: WrappedLogger, method_name: str, event_dict: EventDict) -> EventDict:
        return self._clean_mapping(event_dict)

    def _clean_mapping(self, mapping: Mapping[Any, Any]) -> dict[str, Any]:
        # Keys normalized to text: a non-text key (e.g. an HTTP status code) must not make the line fail.
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
    """Chain shared by structlog logs and library logs. Redaction comes last, after exception tracebacks are
    rendered, so that it covers them."""
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
    """Configure structlog and the `logging` module: JSON on `stream` (stdout by default), at level `level`."""
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
