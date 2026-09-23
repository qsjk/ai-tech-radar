"""Blocage réseau des tests (VIII §50.1, D4) : une connexion externe échoue, le bouclage et Unix restent permis."""

import socket
import tempfile
from pathlib import Path

import pytest
from pytest_socket import SocketConnectBlockedError

# Adresse de documentation (TEST-NET-1, RFC 5737) : jamais routée ; le blocage doit intervenir avant tout envoi.
ADRESSE_EXTERNE = ("192.0.2.1", 80)


# pytest-socket émet aussi un avertissement à chaque blocage : il est attendu ici.
@pytest.mark.filterwarnings("ignore:A test tried to use socket")
def test_connexion_externe_bloquee() -> None:
    with pytest.raises(SocketConnectBlockedError):
        socket.create_connection(ADRESSE_EXTERNE, timeout=1)


def test_connexion_de_bouclage_permise() -> None:
    with socket.create_server(("127.0.0.1", 0)) as serveur:
        port = serveur.getsockname()[1]
        with socket.create_connection(("127.0.0.1", port), timeout=1):
            pass


def test_socket_unix_permise() -> None:
    with tempfile.TemporaryDirectory() as dossier:
        chemin = str(Path(dossier) / "s.sock")
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as serveur:
            serveur.bind(chemin)
            serveur.listen(1)
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                client.connect(chemin)
