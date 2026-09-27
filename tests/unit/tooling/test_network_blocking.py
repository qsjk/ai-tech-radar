"""Network blocking in tests (VIII §50.1, D4): an external connection fails, loopback and Unix stay allowed."""

import socket
import tempfile
from pathlib import Path

import pytest
from pytest_socket import SocketConnectBlockedError

# Documentation address (TEST-NET-1, RFC 5737): never routed; the blocking must happen before anything is sent.
EXTERNAL_ADDRESS = ("192.0.2.1", 80)


# pytest-socket also emits a warning on every block: it is expected here.
@pytest.mark.filterwarnings("ignore:A test tried to use socket")
def test_external_connection_blocked() -> None:
    with pytest.raises(SocketConnectBlockedError):
        socket.create_connection(EXTERNAL_ADDRESS, timeout=1)


def test_loopback_connection_allowed() -> None:
    with socket.create_server(("127.0.0.1", 0)) as server:
        port = server.getsockname()[1]
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            pass


def test_unix_socket_allowed() -> None:
    with tempfile.TemporaryDirectory() as directory:
        path = str(Path(directory) / "s.sock")
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as server:
            server.bind(path)
            server.listen(1)
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.connect(path)
