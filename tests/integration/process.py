"""Subprocesses of the process-level tests (worker, app): JSON logs read with a timeout, bounded waits."""

import json
import os
import queue
import subprocess
import threading
import time
from pathlib import Path
from typing import Any

from tests.integration.db.conftest import ROOT

TIMEOUT = 30.0
"""Bound of every wait, in seconds: exceeding it fails the test instead of blocking it."""


def coverage_variables() -> dict[str, str]:
    """Coverage variables: measure the subprocess, without any effect on the code under test."""
    return {name: value for name, value in os.environ.items() if name.startswith("COVERAGE_")}


def parse_line(line: str) -> dict[str, Any]:
    """JSON log line; a raw (non-JSON) line is kept, without an event."""
    try:
        value = json.loads(line)
    except json.JSONDecodeError:
        return {"event": None, "raw": line}
    return value if isinstance(value, dict) else {"event": None, "raw": line}


class Process:
    """A subprocess; its JSON logs (stdout) are read by a thread and consulted with a timeout."""

    def __init__(self, args: list[str], env: dict[str, str], cwd: Path = ROOT) -> None:
        self.popen = subprocess.Popen(args, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.logs: list[dict[str, Any]] = []
        self._lines: queue.Queue[str | None] = queue.Queue()
        self._reader = threading.Thread(target=self._read, daemon=True)
        self._reader.start()

    def _read(self) -> None:
        assert self.popen.stdout is not None
        for line in self.popen.stdout:
            self._lines.put(line)
        self._lines.put(None)

    def wait_for_log(self, event: str, *, prefix: bool = False) -> dict[str, Any]:
        """Read logs up to `event` (or, with `prefix`, an event that starts with `event`)."""
        deadline = time.monotonic() + TIMEOUT
        while True:
            line = self._lines.get(timeout=max(0.0, deadline - time.monotonic()))
            if line is None:
                raise AssertionError(f"process ended before {event!r}: {self.logs}")
            log = parse_line(line)
            self.logs.append(log)
            if log["event"] == event or (prefix and str(log["event"]).startswith(event)):
                return log

    def wait_for_exit(self) -> int:
        code = self.popen.wait(timeout=TIMEOUT)
        self._reader.join(timeout=TIMEOUT)
        while (line := self._lines.get_nowait() if not self._lines.empty() else None) is not None:
            self.logs.append(parse_line(line))
        return code

    def events(self, prefix: str = "worker.") -> list[str]:
        """Events of the process, in order (library logs, Alembic for example, are left out)."""
        return [str(entry["event"]) for entry in self.logs if str(entry["event"]).startswith(prefix)]

    def stop(self) -> None:
        if self.popen.poll() is None:
            self.popen.kill()
            self.popen.wait(timeout=TIMEOUT)
        for stream in (self.popen.stdout, self.popen.stderr):
            if stream is not None:
                stream.close()
