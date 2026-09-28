"""HTTP test doubles wired in the e2e stack (VIII §47.2, §50.4, decision 23): they run, and app and worker reach them;
the worker runs with APP_ENV=test and HTTP_TEST_ALLOW_HOSTS listing them."""

import json

import pytest

from tests.e2e.conftest import compose, services

pytestmark = pytest.mark.e2e

REACH = """
import json, sys, urllib.request
answers = {}
for host in ("fake-gateway", "fake-sources"):
    with urllib.request.urlopen(f"http://{host}:8000/health", timeout=10) as response:
        answers[host] = json.loads(response.read())
print(json.dumps(answers))
"""


def test_doubles_are_running() -> None:
    state = services()
    assert state["fake-gateway"]["State"] == "running"
    assert state["fake-sources"]["State"] == "running"


@pytest.mark.parametrize("service", ["app", "worker"])
def test_app_and_worker_reach_the_doubles(service: str) -> None:
    result = compose("exec", "-T", service, "python", "-c", REACH)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {
        "fake-gateway": {"status": "ok", "double": "fake-gateway"},
        "fake-sources": {"status": "ok", "double": "fake-sources"},
    }


OUTSIDE = """
import json, socket, time
results = {}
# A public resolver address and a documentation address (TEST-NET-1): neither must be reachable from egress.
for address in (("1.1.1.1", 443), ("192.0.2.1", 80)):
    start = time.monotonic()
    try:
        socket.create_connection(address, timeout=5).close()
        results[address[0]] = "connected"
    except OSError as error:
        results[address[0]] = type(error).__name__
    results[address[0] + "_s"] = round(time.monotonic() - start, 1)
print(json.dumps(results))
"""


def test_worker_reaches_no_external_address_but_still_the_doubles() -> None:
    """egress is internal in e2e (review of #100): no route out (5 s per attempt); the doubles stay reachable."""
    result = compose("exec", "-T", "worker", "python", "-c", OUTSIDE)
    assert result.returncode == 0, result.stderr
    outcome = json.loads(result.stdout)
    for address in ("1.1.1.1", "192.0.2.1"):
        assert outcome[address] != "connected", outcome
        assert outcome[f"{address}_s"] <= 6, outcome
    reach = compose("exec", "-T", "worker", "python", "-c", REACH)
    assert reach.returncode == 0, reach.stderr
    assert set(json.loads(reach.stdout)) == {"fake-gateway", "fake-sources"}


def test_worker_runs_in_test_mode_with_the_allow_list() -> None:
    result = compose(
        "exec",
        "-T",
        "worker",
        "python",
        "-c",
        "import os; print(os.environ['APP_ENV'], os.environ['HTTP_TEST_ALLOW_HOSTS'])",
    )
    assert result.stdout.split() == ["test", "fake-gateway,fake-sources"]
