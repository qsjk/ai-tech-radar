"""Authentication at Caddy (T-SEC-03, VII §37.3): /health is public, everything else asks for credentials."""

import httpx2
import pytest

pytestmark = [pytest.mark.e2e, pytest.mark.spec("T-SEC-03")]


def test_health_answers_without_authentication(client: httpx2.Client) -> None:
    response = client.get("/health")
    assert (response.status_code, response.json()) == (200, {"status": "ok"})


@pytest.mark.parametrize("path", ["/", "/index.html", "/api/health", "/api/anything"])
def test_spa_and_api_answer_401_without_credentials(client: httpx2.Client, path: str) -> None:
    response = client.get(path)
    assert response.status_code == 401
    assert response.headers["www-authenticate"].startswith("Basic ")


def test_wrong_credentials_answer_401(client: httpx2.Client) -> None:
    assert client.get("/api/health", auth=("FAKE-e2e-user", "FAKE-wrong-password")).status_code == 401


@pytest.mark.parametrize("path", ["/", "/api/health"])
def test_credentials_open_the_spa_and_the_api(auth_client: httpx2.Client, path: str) -> None:
    assert auth_client.get(path).status_code == 200
