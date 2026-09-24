"""Configuration typée (VII §36.7, §42.4 niveau 1)."""

import pytest
from pydantic import ValidationError

from app.core.config import AppEnv, AppSettings, WorkerSettings

FAKE_GITHUB = "FAKE-github-token-0001"
FAKE_LLM = "FAKE-llm-api-key-0002"
FAKE_TELEGRAM = "FAKE-telegram-bot-token-0003"
FAKE_SMTP = "FAKE-smtp-password-0004"
FAKE_RESTIC = "FAKE-restic-password-0005"


@pytest.fixture(autouse=True)
def _environnement_vide(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("DASHBOARD_URL", "APP_ENV", "LOG_LEVEL", "RADAR_VERSION", "HTTP_CONTACT", "GITHUB_TOKEN"):
        monkeypatch.delenv(name, raising=False)


@pytest.mark.spec("T-CFG-07")
@pytest.mark.parametrize(
    "url",
    [
        "http://radar.example.com",  # http hors localhost
        "ftp://radar.example.com",  # schéma
        "https://radar.example.com/",  # slash final
        "https://radar.example.com/radar",  # chemin
        "https://radar.example.com:8443",  # port
        "https://localhost:443",  # port, même par défaut
        "https://moi@radar.example.com",  # identifiants
        "https://radar.example.com?x=1",  # requête
        "https://",  # hôte manquant
        "radar.example.com",  # pas d'URL
    ],
)
def test_dashboard_url_invalide_refusee(url: str) -> None:
    with pytest.raises(ValidationError):
        AppSettings(dashboard_url=url)
    with pytest.raises(ValidationError):
        WorkerSettings(dashboard_url=url, http_contact="https://github.com/qsjk/ai-tech-radar")


@pytest.mark.spec("T-CFG-07")
def test_http_localhost_admise_en_developpement_seulement() -> None:
    assert AppSettings(dashboard_url="http://localhost", app_env=AppEnv.DEVELOPMENT).dashboard_url == "http://localhost"
    with pytest.raises(ValidationError):
        AppSettings(dashboard_url="http://localhost")  # production par défaut
    with pytest.raises(ValidationError):
        AppSettings(dashboard_url="http://localhost", app_env=AppEnv.TEST)


@pytest.mark.spec("T-CFG-07")
@pytest.mark.parametrize("url", ["https://radar.example.com", "https://localhost"])
def test_dashboard_url_valide_acceptee(url: str) -> None:
    assert AppSettings(dashboard_url=url).dashboard_url == url


@pytest.mark.spec("T-CFG-07")
def test_dashboard_url_lue_dans_l_environnement(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DASHBOARD_URL", "https://radar.example.com/")
    with pytest.raises(ValidationError):
        AppSettings()  # type: ignore[call-arg]
    monkeypatch.setenv("DASHBOARD_URL", "https://radar.example.com")
    monkeypatch.setenv("APP_ENV", "development")
    assert AppSettings().app_env is AppEnv.DEVELOPMENT  # type: ignore[call-arg]


@pytest.mark.spec("T-SEC-02")
def test_representation_des_secrets_masquee() -> None:
    settings = WorkerSettings(
        dashboard_url="https://radar.example.com",
        http_contact="https://github.com/qsjk/ai-tech-radar",
        github_token=FAKE_GITHUB,  # type: ignore[arg-type]
        llm_api_key=FAKE_LLM,  # type: ignore[arg-type]
        telegram_bot_token=FAKE_TELEGRAM,  # type: ignore[arg-type]
        smtp_password=FAKE_SMTP,  # type: ignore[arg-type]
        restic_password=FAKE_RESTIC,  # type: ignore[arg-type]
    )
    shown = f"{settings!r} {settings} {settings.model_dump()} {settings.model_dump_json()}"
    for fake in (FAKE_GITHUB, FAKE_LLM, FAKE_TELEGRAM, FAKE_SMTP, FAKE_RESTIC):
        assert fake not in shown
    assert sorted(settings.secret_values()) == sorted([FAKE_GITHUB, FAKE_LLM, FAKE_TELEGRAM, FAKE_SMTP, FAKE_RESTIC])


@pytest.mark.spec("T-SEC-02")
def test_app_ne_declare_aucun_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", FAKE_GITHUB)
    settings = AppSettings(dashboard_url="https://radar.example.com")
    assert set(AppSettings.model_fields) == {"dashboard_url", "app_env", "log_level", "radar_version"}
    assert settings.secret_values() == []
    assert FAKE_GITHUB not in settings.model_dump_json()


@pytest.mark.spec("T-SEC-02")
def test_variable_vide_vaut_absente(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "")
    settings = WorkerSettings(
        dashboard_url="https://radar.example.com", http_contact="https://github.com/qsjk/ai-tech-radar"
    )
    assert settings.github_token is None
