"""Fake sources server (VIII §50.4): empty but wired in Sprint 1; per-type fixtures come with Sprint 2."""

try:
    from tests.fakes.http_double import serve
except ModuleNotFoundError:  # in its container, the module sits next to this file
    from http_double import serve  # type: ignore[no-redef]

NAME = "fake-sources"

if __name__ == "__main__":
    serve(NAME)
