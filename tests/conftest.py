"""Shared test configuration.

Network blocking for the whole pytest session (VIII §50.1) is set by `pytest-socket`, through the options of
`[tool.pytest.ini_options]` in `pyproject.toml`: only connections to 127.0.0.1 and ::1, and Unix sockets, are allowed.
No test calls the Internet.
"""
