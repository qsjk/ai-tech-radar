"""Shared base of the HTTP test doubles (VIII §50.4): a small standard-library server, run in a container in e2e.

Sprint 1 doubles are empty but wired (VIII §47.2, D4): they start, answer `GET /health` and record every request they
receive. Their scriptable behaviours (VIII §50.4) come with their consumers: the collectors (Sprint 2) and the LLM
layer (Sprint 6).
"""

import json
import os
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

DEFAULT_PORT = 8000


class RecordingHandler(BaseHTTPRequestHandler):
    """Answers `GET /health` with `{"status": "ok", "double": <name>}`, 404 otherwise; records each request."""

    server: "DoubleServer"

    def do_GET(self) -> None:  # noqa: N802 — name imposed by http.server
        self.server.record(self.command, self.path)
        if self.path == "/health":
            self._reply(200, {"status": "ok", "double": self.server.name})
        else:
            self._reply(404, {"error": "not scripted yet", "double": self.server.name})

    def _reply(self, status: int, body: dict[str, Any]) -> None:
        payload = json.dumps(body).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, format: str, *args: Any) -> None:  # noqa: A002 — signature of the base class
        """One JSON line per request on stdout, like the services (VII §42.1)."""
        print(json.dumps({"event": "double.request", "double": self.server.name, "line": format % args}), flush=True)


class DoubleServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, name: str, address: tuple[str, int]) -> None:
        super().__init__(address, RecordingHandler)
        self.name = name
        self.requests: list[tuple[str, str]] = []
        self._lock = threading.Lock()

    def record(self, method: str, path: str) -> None:
        with self._lock:
            self.requests.append((method, path))


def serve(name: str) -> None:
    """Entry point of a double's container: listen on all interfaces, port `DOUBLE_PORT` (8000 by default)."""
    port = int(os.environ.get("DOUBLE_PORT", DEFAULT_PORT))
    server = DoubleServer(name, ("0.0.0.0", port))  # noqa: S104 — container network only
    print(json.dumps({"event": "double.started", "double": name, "port": port}), flush=True)
    server.serve_forever()
