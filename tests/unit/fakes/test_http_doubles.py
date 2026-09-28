"""HTTP test doubles, empty but wired (VIII §47.2, §50.4): they start, answer `/health` and record requests."""

import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator

import pytest

from tests.fakes import fake_gateway, fake_sources
from tests.fakes.http_double import DoubleServer


@pytest.fixture(params=[fake_gateway.NAME, fake_sources.NAME])
def double(request: pytest.FixtureRequest) -> Iterator[DoubleServer]:
    server = DoubleServer(request.param, ("127.0.0.1", 0))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def get(server: DoubleServer, path: str) -> tuple[int, dict[str, str]]:
    url = f"http://127.0.0.1:{server.server_address[1]}{path}"
    try:
        with urllib.request.urlopen(url, timeout=5) as response:  # noqa: S310 — loopback only
            return int(response.status), json.loads(response.read())
    except urllib.error.HTTPError as error:
        return int(error.code), json.loads(error.read())


def test_health_answers_ok_with_the_double_name(double: DoubleServer, capsys: pytest.CaptureFixture[str]) -> None:
    assert get(double, "/health") == (200, {"status": "ok", "double": double.name})
    assert double.requests == [("GET", "/health")]
    assert json.loads(capsys.readouterr().out.splitlines()[-1])["event"] == "double.request"


def test_unscripted_route_answers_404_and_is_recorded(double: DoubleServer) -> None:
    assert get(double, "/v1/models")[0] == 404
    assert double.requests == [("GET", "/v1/models")]
