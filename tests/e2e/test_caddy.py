"""Caddy (T-SEC-06, VII §37.3, §42.3): security headers on every response, errors included, no Server header;
credentials never logged; /health not logged; body limit; cache policy of the SPA."""

import base64
import re

import httpx2
import pytest

from tests.e2e.conftest import PASSWORD, USER, logs

pytestmark = [pytest.mark.e2e, pytest.mark.spec("T-SEC-06")]

CSP = (
    "default-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'self'; form-action 'self'; "
    "frame-ancestors 'none'"
)
SECURITY_HEADERS = {
    "content-security-policy": CSP,
    "x-frame-options": "DENY",
    "referrer-policy": "same-origin",
    "x-content-type-options": "nosniff",
    "strict-transport-security": "max-age=31536000",
}


@pytest.mark.parametrize(("path", "status"), [("/health", 200), ("/", 401), ("/api/health", 401)])
def test_security_headers_and_no_server_header(client: httpx2.Client, path: str, status: int) -> None:
    response = client.get(path)
    assert response.status_code == status
    for name, value in SECURITY_HEADERS.items():
        assert response.headers.get(name) == value, name
    assert "server" not in response.headers


@pytest.mark.parametrize("path", ["/", "/api/health"])
def test_authenticated_responses_carry_the_headers_without_server(auth_client: httpx2.Client, path: str) -> None:
    response = auth_client.get(path)
    assert response.status_code == 200
    assert response.headers.get("content-security-policy") == CSP
    assert "server" not in response.headers


def test_small_body_reaches_the_app(auth_client: httpx2.Client) -> None:
    assert auth_client.post("/api/health", content=b"x" * 1024).status_code == 405  # /api/health has no POST


@pytest.mark.xfail(
    strict=True,
    reason="request_body max_size only applies when a body is read; no app route reads one in Sprint 1 (PR gap)",
)
def test_body_over_1_mb_refused(auth_client: httpx2.Client) -> None:
    assert auth_client.post("/api/health", content=b"x" * (1024 * 1024 + 1)).status_code == 413


def test_index_html_never_cached_and_assets_immutable(auth_client: httpx2.Client) -> None:
    for path in ("/", "/index.html"):
        assert auth_client.get(path).headers.get("cache-control") == "no-cache", path
    assets = re.findall(r'"(/assets/[^"]+)"', auth_client.get("/").text)
    assert assets
    for asset in assets:
        response = auth_client.get(asset)
        assert response.status_code == 200
        assert response.headers.get("cache-control") == "public, max-age=31536000, immutable"


def test_credentials_absent_and_health_not_logged(client: httpx2.Client, auth_client: httpx2.Client) -> None:
    for _ in range(3):
        client.get("/health")
    auth_client.get("/api/health")
    entries = [entry for entry in logs("caddy") if str(entry.get("logger", "")).startswith("http.log.access")]
    assert entries, "no access log line"
    text = str(entries)
    token = base64.b64encode(f"{USER}:{PASSWORD}".encode()).decode()
    assert token not in text and PASSWORD not in text
    authorizations = [
        e["request"]["headers"].get("Authorization") for e in entries if "Authorization" in e["request"]["headers"]
    ]
    assert authorizations and all(value == ["REDACTED"] for value in authorizations)
    assert not [e for e in entries if e["request"]["uri"] == "/health"]
