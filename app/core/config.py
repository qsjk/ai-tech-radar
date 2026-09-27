"""Typed process configuration (VII §36.7, docs/architecture.md §3.3).

Each process declares **only its own variables** (per-service distribution, VII §36.7): a variable missing from its
model is never read. `app` receives no secret. Secrets are `SecretStr`, whose representation is masked (VII §42.4,
level 1). An empty variable in `.env` counts as absent.
"""

from enum import StrEnum
from typing import Self
from urllib.parse import urlsplit

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEnv(StrEnum):
    PRODUCTION = "production"
    DEVELOPMENT = "development"
    TEST = "test"


class LogLevel(StrEnum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


def validate_dashboard_url(url: str, app_env: AppEnv) -> str:
    """Check `DASHBOARD_URL` (VII §36.7, T-CFG-07) and return the URL unchanged.

    `https` scheme, or `http://localhost` in development only; a host; no port, path, trailing slash, credentials,
    query or fragment.
    """
    parts = urlsplit(url)
    if parts.scheme not in ("https", "http"):
        raise ValueError(f"DASHBOARD_URL: scheme '{parts.scheme}' rejected, https expected")
    if not parts.hostname:
        raise ValueError("DASHBOARD_URL: missing host")
    if parts.scheme == "http" and not (parts.hostname == "localhost" and app_env is AppEnv.DEVELOPMENT):
        raise ValueError("DASHBOARD_URL: http is only allowed for localhost, in development")
    if parts.port is not None:
        raise ValueError("DASHBOARD_URL: no port allowed")
    if parts.path:
        raise ValueError("DASHBOARD_URL: no path and no trailing slash")
    if parts.username is not None or parts.password is not None:
        raise ValueError("DASHBOARD_URL: no credentials in the URL")
    if parts.query or parts.fragment:
        raise ValueError("DASHBOARD_URL: no query and no fragment")
    return url


class _ProcessSettings(BaseSettings):
    """Variables shared by `app` and `worker`.

    `RADAR_DB_PATH` is set by Compose (`/data/radar.db`, VII §36.5): it is the only source of the database path
    (`architecture.md` P-01).
    """

    model_config = SettingsConfigDict(env_ignore_empty=True, extra="ignore", frozen=True)

    radar_db_path: str
    dashboard_url: str
    app_env: AppEnv = AppEnv.PRODUCTION
    log_level: LogLevel = LogLevel.INFO
    radar_version: str = "dev"

    @model_validator(mode="after")
    def _check_dashboard_url(self) -> Self:
        validate_dashboard_url(self.dashboard_url, self.app_env)
        return self

    def secret_values(self) -> list[str]:
        """Values of the configured secrets, for value-based log redaction (VII §42.4, level 3)."""
        values = []
        for name in type(self).model_fields:
            field = getattr(self, name)
            if isinstance(field, SecretStr):
                value = field.get_secret_value()
                if value:
                    values.append(value)
        return values


class AppSettings(_ProcessSettings):
    """Variables of `app`: `RADAR_DB_PATH`, `DASHBOARD_URL`, `APP_ENV`, `LOG_LEVEL`, `RADAR_VERSION`; no secret
    (VII §36.7)."""


class WorkerSettings(_ProcessSettings):
    """Worker variables (VII §36.7): all of them, except those reserved for `caddy`."""

    http_contact: str
    github_token: SecretStr | None = None
    restic_repository: str | None = None
    restic_password: SecretStr | None = None
    aws_access_key_id: SecretStr | None = None
    aws_secret_access_key: SecretStr | None = None
    llm_base_url: str | None = None
    llm_api_key: SecretStr | None = None
    llm_model: str | None = None
    smtp_host: str | None = None
    smtp_port: int = 587
    smtp_user: str | None = None
    smtp_password: SecretStr | None = None
    smtp_from: str | None = None
    alert_email_to: str | None = None
    telegram_bot_token: SecretStr | None = None
    telegram_chat_id: str | None = None
    http_test_allow_hosts: str | None = None
