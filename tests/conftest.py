"""Configuration commune des tests.

Le blocage réseau de toute la session pytest (VIII §50.1) est posé par `pytest-socket`, via les options de
`[tool.pytest.ini_options]` dans `pyproject.toml` : seules les connexions vers 127.0.0.1 et ::1, et les sockets Unix,
sont permises. Aucun test n'appelle Internet.
"""
