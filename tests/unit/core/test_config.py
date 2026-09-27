"""Typed configuration (VII §36.7, §42.4 level 1)."""

import pytest
from pydantic import ValidationError

from app.core.config import AppEnv, AppSettings, WorkerSettings

DB = "/data/radar.db"
FAKE_GITHUB = "FAKE-github-token-0001"
FAKE_LLM = "FAKE-llm-api-key-0002"
FAKE_TELEGRAM = "FAKE-telegram-bot-token-0003"
FAKE_SMTP = "FAKE-smtp-password-0004"
FAKE_RESTIC = "FAKE-restic-password-0005"


@pytest.fixture(autouse=True)
def _empty_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hermetic test: no variable declared by the models comes from the environment of the machine or the CI."""
    for model in (AppSettings, WorkerSettings):
        for name in model.model_fields:
            monkeypatch.delenv(name.upper(), raising=False)


@pytest.mark.spec("T-CFG-07")
@pytest.mark.parametrize(
    "url",
    [
        "http://radar.example.com",  # http outside localhost
        "ftp://radar.example.com",  # scheme
        "https://radar.example.com/",  # trailing slash
        "https://radar.example.com/radar",  # path
        "https://radar.example.com:8443",  # port
        "https://localhost:443",  # port, even the default one
        "https://me@radar.example.com",  # credentials
        "https://radar.example.com?x=1",  # query
        "https://",  # missing host
        "radar.example.com",  # not a URL
    ],
)
def test_invalid_dashboard_url_refused(url: str) -> None:
    with pytest.raises(ValidationError):
        AppSettings(radar_db_path=DB, dashboard_url=url)
    with pytest.raises(ValidationError):
        WorkerSettings(radar_db_path=DB, dashboard_url=url, http_contact="https://github.com/qsjk/ai-tech-radar")


@pytest.mark.spec("T-CFG-07")
def test_http_localhost_allowed_in_development_only() -> None:
    assert (
        AppSettings(radar_db_path=DB, dashboard_url="http://localhost", app_env=AppEnv.DEVELOPMENT).dashboard_url
        == "http://localhost"
    )
    with pytest.raises(ValidationError):
        AppSettings(radar_db_path=DB, dashboard_url="http://localhost")  # production by default
    with pytest.raises(ValidationError):
        AppSettings(radar_db_path=DB, dashboard_url="http://localhost", app_env=AppEnv.TEST)


@pytest.mark.spec("T-CFG-07")
@pytest.mark.parametrize("url", ["https://radar.example.com", "https://localhost"])
def test_valid_dashboard_url_accepted(url: str) -> None:
    assert AppSettings(radar_db_path=DB, dashboard_url=url).dashboard_url == url


@pytest.mark.spec("T-CFG-07")
def test_dashboard_url_read_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RADAR_DB_PATH", DB)
    monkeypatch.setenv("DASHBOARD_URL", "https://radar.example.com/")
    with pytest.raises(ValidationError):
        AppSettings()
    monkeypatch.setenv("DASHBOARD_URL", "https://radar.example.com")
    monkeypatch.setenv("APP_ENV", "development")
    assert AppSettings().app_env is AppEnv.DEVELOPMENT


@pytest.mark.spec("T-SEC-02")
def test_secret_representation_masked() -> None:
    settings = WorkerSettings(
        radar_db_path=DB,
        dashboard_url="https://radar.example.com",
        http_contact="https://github.com/qsjk/ai-tech-radar",
        github_token=FAKE_GITHUB,
        llm_api_key=FAKE_LLM,
        telegram_bot_token=FAKE_TELEGRAM,
        smtp_password=FAKE_SMTP,
        restic_password=FAKE_RESTIC,
    )
    shown = f"{settings!r} {settings} {settings.model_dump()} {settings.model_dump_json()}"
    for fake in (FAKE_GITHUB, FAKE_LLM, FAKE_TELEGRAM, FAKE_SMTP, FAKE_RESTIC):
        assert fake not in shown
    assert sorted(settings.secret_values()) == sorted([FAKE_GITHUB, FAKE_LLM, FAKE_TELEGRAM, FAKE_SMTP, FAKE_RESTIC])


@pytest.mark.spec("T-SEC-02")
def test_app_declares_no_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", FAKE_GITHUB)
    settings = AppSettings(radar_db_path=DB, dashboard_url="https://radar.example.com")
    assert set(AppSettings.model_fields) == {"radar_db_path", "dashboard_url", "app_env", "log_level", "radar_version"}
    assert settings.secret_values() == []
    assert FAKE_GITHUB not in settings.model_dump_json()


@pytest.mark.spec("T-SEC-02")
def test_empty_variable_counts_as_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GITHUB_TOKEN", "")
    settings = WorkerSettings(
        radar_db_path=DB,
        dashboard_url="https://radar.example.com",
        http_contact="https://github.com/qsjk/ai-tech-radar",
    )
    assert settings.github_token is None


def test_radar_db_path_required_and_read_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    with pytest.raises(ValidationError):
        AppSettings(dashboard_url="https://radar.example.com")
    monkeypatch.setenv("RADAR_DB_PATH", "/tmp/other.db")
    assert AppSettings(dashboard_url="https://radar.example.com").radar_db_path == "/tmp/other.db"
