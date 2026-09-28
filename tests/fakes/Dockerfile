# syntax=docker/dockerfile:1.7
# Image of the HTTP test doubles for the e2e stack (docker-compose.test.yml, VIII §50.4). Build context: tests/fakes.
# Same base image as the backend, pinned by digest (E16); standard library only.
ARG PYTHON_IMAGE=python:3.12.14-slim-trixie@sha256:2f17fc044b579bab302c2e8054d3a686e2cb9a83de48e70534b94cd8ebbe06a9
FROM ${PYTHON_IMAGE}
WORKDIR /fakes
COPY http_double.py fake_gateway.py fake_sources.py ./
RUN python -m compileall -q /fakes
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 HOME=/tmp
USER 10001:10001
