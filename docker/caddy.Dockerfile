# syntax=docker/dockerfile:1.7
# Caddy image with the SPA built by Vite (docs/architecture.md §4.3, VII §37.3).
# Node 24 LTS and Caddy 2 pinned by full tag and multi-arch index digest (P-13).
ARG NODE_IMAGE=node:24.21.0-trixie-slim@sha256:8ec5d7557396cfe32d21c3f9c13072355ceab22b584578ca4bb28af31120cffe
ARG CADDY_IMAGE=caddy:2.11.4@sha256:0c994536bddb66445885237f1a5dcc1916bccea922661c76b4e9fc24061f9b52

# ── 1. SPA build ─────────────────────────────────────────────────────────────────────────────────────────────────────
FROM ${NODE_IMAGE} AS front
WORKDIR /front
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ ./
# CSS Modules compiled by Vite, no inline script or style (E20).
RUN npm run build

# ── 2. Final image ───────────────────────────────────────────────────────────────────────────────────────────────────
FROM ${CADDY_IMAGE}
# The base image sets the file capability cap_net_bind_service on /usr/bin/caddy: with cap_drop: ALL, exec then fails
# with "operation not permitted". A plain copy drops the extended attributes; 80 and 443 are bound without any
# capability thanks to net.ipv4.ip_unprivileged_port_start (P-10, sprint-01.md T1.8).
RUN cp /usr/bin/caddy /usr/bin/caddy.nocap \
 && mv /usr/bin/caddy.nocap /usr/bin/caddy \
 && chmod 0755 /usr/bin/caddy \
 && if getcap /usr/bin/caddy | grep -q cap_; then echo "caddy still carries a file capability" >&2; exit 1; fi
COPY docker/Caddyfile /etc/caddy/Caddyfile
COPY --from=front /front/dist /srv
# Caddy's /data and /config belong to the non-root uid; the base image declares no VOLUME, so the ownership set here
# is copied into the named volumes when they are created (same mechanism as architecture.md §4.4).
RUN mkdir -p /data/caddy /config/caddy \
 && chown -R 10001:10001 /data /config \
 && chmod 0750 /data /config /data/caddy /config/caddy
USER 10001:10001
