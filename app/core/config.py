"""Configuration typée des processus (VII §36.7, docs/architecture.md §3.3).

Chaque processus déclare **ses seules variables** (distribution par service, VII §36.7) : une variable absente de son
modèle n'est jamais lue. `app` ne reçoit aucun secret. Les secrets sont des `SecretStr`, dont la représentation est
masquée (VII §42.4, niveau 1). Une variable vide dans `.env` vaut « absente ».
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
    """Contrôle `DASHBOARD_URL` (VII §36.7, T-CFG-07) et renvoie l'URL inchangée.

    Schéma `https`, ou `http://localhost` en développement seulement ; un hôte ; ni port, ni chemin, ni slash final,
    ni identifiants, ni requête, ni fragment.
    """
    parts = urlsplit(url)
    if parts.scheme not in ("https", "http"):
        raise ValueError(f"DASHBOARD_URL : schéma « {parts.scheme} » refusé, https attendu")
    if not parts.hostname:
        raise ValueError("DASHBOARD_URL : hôte manquant")
    if parts.scheme == "http" and not (parts.hostname == "localhost" and app_env is AppEnv.DEVELOPMENT):
        raise ValueError("DASHBOARD_URL : http n'est admis que pour localhost, en développement")
    if parts.port is not None:
        raise ValueError("DASHBOARD_URL : aucun port n'est admis")
    if parts.path:
        raise ValueError("DASHBOARD_URL : ni chemin ni slash final")
    if parts.username is not None or parts.password is not None:
        raise ValueError("DASHBOARD_URL : aucun identifiant dans l'URL")
    if parts.query or parts.fragment:
        raise ValueError("DASHBOARD_URL : ni requête ni fragment")
    return url


class _ProcessSettings(BaseSettings):
    """Variables communes à `app` et `worker`."""

    model_config = SettingsConfigDict(env_ignore_empty=True, extra="ignore", frozen=True)

    dashboard_url: str
    app_env: AppEnv = AppEnv.PRODUCTION
    log_level: LogLevel = LogLevel.INFO
    radar_version: str = "dev"

    @model_validator(mode="after")
    def _check_dashboard_url(self) -> Self:
        validate_dashboard_url(self.dashboard_url, self.app_env)
        return self

    def secret_values(self) -> list[str]:
        """Valeurs des secrets configurés, pour le nettoyage des logs par valeur (VII §42.4, niveau 3)."""
        values = []
        for name in type(self).model_fields:
            field = getattr(self, name)
            if isinstance(field, SecretStr):
                value = field.get_secret_value()
                if value:
                    values.append(value)
        return values


class AppSettings(_ProcessSettings):
    """Variables de `app` : `DASHBOARD_URL`, `APP_ENV`, `LOG_LEVEL`, `RADAR_VERSION` — aucun secret (VII §36.7)."""


class WorkerSettings(_ProcessSettings):
    """Variables du worker (VII §36.7) : toutes, sauf celles réservées à `caddy`."""

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
