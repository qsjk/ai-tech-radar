"""JSON logs and secret redaction (VII §42.1, §42.4 levels 1 and 3)."""

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
def log_stream() -> Iterator[io.StringIO]:
    """Configure logging as the worker would, with fake secrets, and capture the output."""
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


def lines(stream: io.StringIO) -> list[dict[str, object]]:
    return [json.loads(line) for line in stream.getvalue().splitlines()]


def test_json_rendering_with_the_common_fields(log_stream: io.StringIO) -> None:
    structlog.get_logger().info("worker.started")
    (line,) = lines(log_stream)
    assert line["event"] == "worker.started"
    assert line["level"] == "info"
    assert line["service"] == "worker"
    assert line["version"] == "abc1234"
    assert line["ts"] == "2026-09-24T08:00:00.000+00:00"


@pytest.mark.spec("T-SEC-01:logs")
def test_no_fake_secret_in_the_captured_logs(log_stream: io.StringIO) -> None:
    log = structlog.get_logger()
    log.warning("collector.run.failed", error=f"401 Unauthorized, token {FAKE_GITHUB}", detail={"key": FAKE_LLM})
    log.error(f"alert: https://api.telegram.org/bot{FAKE_TELEGRAM}/sendMessage")
    try:
        raise RuntimeError(f"SMTP AUTH refused for password {FAKE_SMTP}")
    except RuntimeError:
        log.exception("alert.send.failed")
    try:
        raise OSError(f"restic: failed with {FAKE_RESTIC}")
    except OSError:
        logging.getLogger("httpx").exception("library: https://api.telegram.org/bot%s/getMe", FAKE_TELEGRAM)

    output = log_stream.getvalue()
    assert len(lines(log_stream)) == 4
    for fake in FAKES:
        assert fake not in output
    assert MASK in output
    assert "RuntimeError" in output and "OSError" in output  # tracebacks are present, redacted


@pytest.mark.spec("T-SEC-02")
@pytest.mark.parametrize(
    "key",
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
def test_sensitive_keys_masked(key: str) -> None:
    event = SecretRedactor([])(None, "info", {"event": "http.request", key: "any-value"})
    assert event[key] == MASK
    assert event["event"] == "http.request"


@pytest.mark.spec("T-SEC-02")
@pytest.mark.parametrize("key", ["prompt_tokens", "token_count"])
def test_similar_keys_not_masked(key: str) -> None:
    event = SecretRedactor([])(None, "info", {"event": "llm.call", key: 1234})
    assert event[key] == 1234


@pytest.mark.spec("T-SEC-02")
def test_sensitive_keys_masked_in_depth() -> None:
    event = SecretRedactor([])(
        None, "info", {"event": "x", "headers": {"authorization": "Bearer abc", "accept": "*/*"}}
    )
    assert event["headers"] == {"authorization": MASK, "accept": "*/*"}


@pytest.mark.spec("T-SEC-02")
def test_non_text_key_in_a_nested_dict() -> None:
    event = SecretRedactor(["FAKE-x"])(None, "info", {"event": "x", "by_status": {200: "ok FAKE-x", 401: "refused"}})
    assert event["by_status"] == {"200": f"ok {MASK}", "401": "refused"}
