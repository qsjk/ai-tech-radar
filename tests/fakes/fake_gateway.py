"""Fake OpenAI-compatible gateway (VIII §50.4): empty but wired in Sprint 1; scriptable behaviours come in Sprint 6."""

try:
    from tests.fakes.http_double import serve
except ModuleNotFoundError:  # in its container, the module sits next to this file
    from http_double import serve  # type: ignore[no-redef]

NAME = "fake-gateway"

if __name__ == "__main__":
    serve(NAME)
