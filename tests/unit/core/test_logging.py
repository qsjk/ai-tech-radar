"""Logs JSON et nettoyage des secrets (VII §42.1, §42.4 niveaux 1 et 3)."""

import io
import json
import logging
from collections.abc import Iterator
from datetime import UTC, datetime

import pytest
import structlog

from app.core.config import WorkerSettings
from app.core.logging import MASK, SENSITIVE_SUFFIXES, SecretRedactor, configure_logging
from tests.fakes.clock import ManualClock

DB = "/data/radar.db"
FAKE_GITHUB = "FAKE-github-token-0001"
FAKE_LLM = "FAKE-llm-api-key-0002"
FAKE_TELEGRAM = "123456:FAKE-telegram-bot-token-0003"
FAKE_SMTP = "FAKE-smtp-password-0004"
FAKE_RESTIC = "FAKE-restic-password-0005"
FAKES = (FAKE_GITHUB, FAKE_LLM, FAKE_TELEGRAM, FAKE_SMTP, FAKE_RESTIC)


@pytest.fixture
def journal() -> Iterator[io.StringIO]:
    """Configure les logs comme le ferait le worker, avec des secrets factices, et capture la sortie."""
    settings = WorkerSettings(
        radar_db_path=DB,
        dashboard_url="https://radar.example.com",
        http_contact="https://github.com/qsjk/ai-tech-radar",
        github_token=FAKE_GITHUB,  # type: ignore[arg-type]
        llm_api_key=FAKE_LLM,  # type: ignore[arg-type]
        telegram_bot_token=FAKE_TELEGRAM,  # type: ignore[arg-type]
        smtp_password=FAKE_SMTP,  # type: ignore[arg-type]
        restic_password=FAKE_RESTIC,  # type: ignore[arg-type]
    )
    root = logging.getLogger()
    saved = (root.handlers[:], root.level)
    stream = io.StringIO()
    configure_logging(
        service="worker",
        version="abc1234",
        level="INFO",
        clock=ManualClock(datetime(2026, 9, 24, 8, 0, tzinfo=UTC)),
        secrets=settings.secret_values(),
        stream=stream,
    )
    yield stream
    root.handlers[:], _ = saved
    root.setLevel(saved[1])
    structlog.reset_defaults()


def lignes(stream: io.StringIO) -> list[dict[str, object]]:
    return [json.loads(line) for line in stream.getvalue().splitlines()]


def test_rendu_json_avec_les_champs_communs(journal: io.StringIO) -> None:
    structlog.get_logger().info("worker.started")
    (ligne,) = lignes(journal)
    assert ligne["event"] == "worker.started"
    assert ligne["level"] == "info"
    assert ligne["service"] == "worker"
    assert ligne["version"] == "abc1234"
    assert ligne["ts"] == "2026-09-24T08:00:00.000+00:00"


@pytest.mark.spec("T-SEC-01:logs")
def test_aucun_secret_factice_dans_les_logs_captures(journal: io.StringIO) -> None:
    log = structlog.get_logger()
    log.warning("collector.run.failed", error=f"401 Unauthorized, token {FAKE_GITHUB}", detail={"cle": FAKE_LLM})
    log.error(f"alerte : https://api.telegram.org/bot{FAKE_TELEGRAM}/sendMessage")
    try:
        raise RuntimeError(f"SMTP AUTH refusée pour le mot de passe {FAKE_SMTP}")
    except RuntimeError:
        log.exception("alert.send.failed")
    try:
        raise OSError(f"restic : échec avec {FAKE_RESTIC}")
    except OSError:
        logging.getLogger("httpx").exception("bibliothèque : https://api.telegram.org/bot%s/getMe", FAKE_TELEGRAM)

    sortie = journal.getvalue()
    assert len(lignes(journal)) == 4
    for fake in FAKES:
        assert fake not in sortie
    assert MASK in sortie
    assert "RuntimeError" in sortie and "OSError" in sortie  # les traces sont présentes, nettoyées


@pytest.mark.spec("T-SEC-02")
@pytest.mark.parametrize(
    "cle",
    [
        *SENSITIVE_SUFFIXES,
        "Authorization",
        "PASSWORD",
        "x-api-key",
        "set-cookie",
        "access_token",
        "proxy-authorization",
        "smtp_password",
    ],
)
def test_cles_sensibles_masquees(cle: str) -> None:
    event = SecretRedactor([])(None, "info", {"event": "http.request", cle: "valeur-quelconque"})
    assert event[cle] == MASK
    assert event["event"] == "http.request"


@pytest.mark.spec("T-SEC-02")
@pytest.mark.parametrize("cle", ["prompt_tokens", "token_count"])
def test_cles_proches_non_masquees(cle: str) -> None:
    event = SecretRedactor([])(None, "info", {"event": "llm.call", cle: 1234})
    assert event[cle] == 1234


@pytest.mark.spec("T-SEC-02")
def test_cles_sensibles_masquees_en_profondeur() -> None:
    event = SecretRedactor([])(
        None, "info", {"event": "x", "headers": {"authorization": "Bearer abc", "accept": "*/*"}}
    )
    assert event["headers"] == {"authorization": MASK, "accept": "*/*"}


@pytest.mark.spec("T-SEC-02")
def test_cle_non_textuelle_dans_un_dict_imbrique() -> None:
    event = SecretRedactor(["FAKE-x"])(None, "info", {"event": "x", "par_statut": {200: "ok FAKE-x", 401: "refusé"}})
    assert event["par_statut"] == {"200": f"ok {MASK}", "401": "refusé"}
