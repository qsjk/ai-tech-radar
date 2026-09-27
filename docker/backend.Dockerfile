# syntax=docker/dockerfile:1.7
# Backend image shared by migrate, app and worker (docs/architecture.md §4.2, VII §36.5).
# Base image pinned by full tag and multi-arch index digest, as verified in T0.3 (E16, V-02).
ARG PYTHON_IMAGE=python:3.12.14-slim-trixie@sha256:2f17fc044b579bab302c2e8054d3a686e2cb9a83de48e70534b94cd8ebbe06a9
# uv pinned by tag and digest (P-13), same version as [tool.uv] required-version.
ARG UV_IMAGE=ghcr.io/astral-sh/uv:0.12.18@sha256:3adc3706091ce7c2fe595e669628caedd6d951551b92b258b7e7dbe06d9440bc

FROM ${UV_IMAGE} AS uv

# ── 1. Dependencies and code ─────────────────────────────────────────────────────────────────────────────────────────
FROM ${PYTHON_IMAGE} AS build
COPY --from=uv /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never
COPY pyproject.toml uv.lock ./
# Dependencies only, bytecode compiled. The project itself is not installed in the venv: the code stays in /app, with
# the same layout as the repository, so that app/db/revision.py finds /app/migrations next to the app/ package.
RUN uv sync --frozen --no-dev --no-install-project
COPY app/ app/
COPY migrations/ migrations/
COPY alembic.ini ./
# Project bytecode compiled at build time: the root filesystem is read-only at run time (architecture.md §4.5).
RUN /app/.venv/bin/python -m compileall -q app migrations

# ── 2. Final image ───────────────────────────────────────────────────────────────────────────────────────────────────
# The embedding model (Sprint 4, E5) and restic (Sprint 11) are added by their sprints.
FROM ${PYTHON_IMAGE}
RUN groupadd --gid 10001 radar \
 && useradd --uid 10001 --gid 10001 --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin radar \
 && mkdir -p /data && chown 10001:10001 /data && chmod 0750 /data
# Code, venv and configuration belong to root, read-only for uid 10001.
COPY --from=build /app /app
COPY config/ /app/config/
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONPATH=/app \
    PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    HOME=/tmp TMPDIR=/tmp XDG_CACHE_HOME=/tmp/.cache
WORKDIR /app
# Build-time check of the layout: the migrations are found from the app/ package, and head is readable.
RUN python -c "from app.db.revision import DEFAULT_SCRIPT_LOCATION, head_revision; print(DEFAULT_SCRIPT_LOCATION, head_revision())"
USER 10001:10001
