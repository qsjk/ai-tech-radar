# Architecture — AI Tech Radar

> Tâche T0.5 (#8), rédigée le 2026-09-23 sur la spec arbitrée (#67, #70) et `docs/database.md`.
> Vue d'ensemble technique : processus, arborescence, configuration, conteneurs, CI, `Clock`, traçabilité des tests
> (IX §55.4, §57.3). Le document **renvoie** à la spec et à `database.md` au lieu de les recopier (IX §55.5).
> Au Sprint 0, Compose, Dockerfile et CI sont **proposés sous forme de blocs** : aucun fichier exécutable n'est créé
> (IX §57.6). Ce qui n'est pas fixé par la spec est listé au §6, avec une recommandation, sans être tranché.

Références : « VII §36.5 » = `docs/spec/partie-VII.md`, §36.5. Les décisions du rapport de cadrage
(`docs/sprints/sprint-00-cadrage.md`) sont citées par leur identifiant (CF-03, E17…), les points à trancher de ce
document par `P-nn` (§6), les écarts de spec par `A-nn` (§7).

---

## 1. Vue d'ensemble

### 1.1 Services

Trois services permanents, un one-shot et un optionnel (VII §36.1–§36.2, DV-11).

| Service | Image | Rôle | Réseaux | Cycle de vie |
|---|---|---|---|---|
| `caddy` | `radar-caddy:<sha>` | seul point d'entrée : TLS, SPA statique, `basic_auth`, reverse proxy de `/api` et `/health` vers `app` (VII §37) | `edge`, `public` | permanent, seul à publier des ports (80, 443/tcp, 443/udp) |
| `app` | `radar-backend:<sha>` | FastAPI, un seul processus uvicorn : API de lecture, actions de l'utilisateur, `/health`, `/api/health` (VI §31, VII §40) | `edge` (aucune sortie Internet) | permanent |
| `worker` | `radar-backend:<sha>` | scheduler, collecte et pipeline, embeddings, clustering, trends, émergence, jobs LLM, alertes, `ops.tick`, backup (II §8.1, VII §36.6) | `egress` (ne joint pas `app`) | permanent, supervision fail-fast et watchdog |
| `migrate` | `radar-backend:<sha>` | `alembic upgrade head`, puis sortie (III §10.5, `database.md` §5) | aucun (`network_mode: none`) | one-shot, avant `app` et `worker` |
| `gateway` | image épinglée du gateway retenu | gateway LLM auto-hébergé, **profil Compose `gateway`** (V-A §25, VII §36.2) | `egress` | optionnel ; choix au Sprint 6 |

- Une seule image backend pour `migrate`, `app` et `worker` ; une image Caddy qui embarque le build Vite. Le tag est
  le sha Git (VII décision 2).
- `app` et `worker` ne communiquent **que par la base** : aucun IPC (II §8.2). Chacun a son moteur SQLAlchemy et son
  pool (III §10.3, `database.md` §2.3).
- Avec un gateway auto-hébergé : `LLM_BASE_URL=http://gateway:<port>/v1` (VII §36.2).

```
          Internet
             │ 80 · 443
        ┌────▼────┐   public
        │  caddy  │──────────── ACME (Let's Encrypt)
        └────┬────┘
             │ edge (internal)
        ┌────▼────┐          ┌──────────┐   egress   sources · LLM (gateway) ·
        │   app   │          │  worker  │──────────▶ SMTP · Telegram · dépôt restic
        └────┬────┘          └────┬─────┘
             │   volume radar_data (/data) : radar.db, -wal, -shm, backup/
             └──────────┬─────────┘
                   ┌────▼────┐
                   │ migrate │  one-shot, sans réseau
                   └─────────┘
```

### 1.2 Qui lit et écrit quoi

La propriété de chaque table (un seul écrivain par table) est fixée par II §8.3 et détaillée dans
**`database.md` §1.4** ; elle n'est pas reprise ici. En résumé, par processus :

| | `app` | `worker` |
|---|---|---|
| **Écrit en base** | `UserPreference`, `Setting`, `ReadState`, `EmergingDecision` ; création d'`AIJob` de régénération ; transitions `dead_letter → pending / cancelled` (V-A §23.6) | toutes les autres tables, dont `SystemState` ; `article_fts` par triggers |
| **Lit en base** | tout, pour l'API et la santé (`SystemState` : heartbeat, `trends_since`, états LLM et embeddings) | les tables écrites par l'app : préférences (sourdine), `Setting` à chaque tick, décisions sur les candidats |
| **Lit sur disque** | `config/pipeline.yaml` en lecture seule (E17, IV §16.1) | les quatre fichiers `config/` au démarrage ; modèle d'embeddings intégré à l'image |
| **Réseau sortant** | aucun (réseau `edge` interne) | sources, gateway LLM, SMTP, Telegram, dépôt restic |
| **N'exécute jamais** | aucun job (II §8.3) | aucune requête HTTP entrante |

`migrate` n'écrit que le schéma et `alembic_version` (`database.md` §5) ; `caddy` ne touche pas à la base.

---

## 2. Arborescence du dépôt

L'arbre contractuel est celui de **VIII §46.1** pour le code et de **IX §55.1** pour `docs/` (qui remplace le bloc
`docs/` de VIII §46.1). Il n'est pas recopié. Précisions utiles au Sprint 1 :

| Chemin | Contenu | Réf. |
|---|---|---|
| `app/core/` | configuration typée (§3), `Clock` (§5.2), logging structlog, nettoyage des secrets | VIII §46.1 · VII §42 |
| `app/db/` | moteurs, `read_session` / `write_session`, `UTCDateTime`, vérification des prérequis | `database.md` §2 |
| `app/cli/` | une commande par fichier : `validate-config`, `health`, `backup-now`, `restore-test`, `vacuum`… ; contrat commun des codes de sortie | IX §56.3, §56.4 |
| `app/api/` | routes FastAPI, anti-CSRF | VI §31, §32 |
| `app/ops/` | `health.py` (module unique de calcul de santé), heartbeat, watchdog, `ops.tick` | VII §39–§40 |
| `app/collectors/` · `pipeline/` · `http/` · `embeddings/` · `clustering/` · `trends/` · `emerging/` · `jobs/` · `llm/` · `alerts/` · `purge/` · `backup/` | un package par étage, introduit au sprint qui le livre | VIII §46.1, §47.2 |
| `frontend/` | React · TypeScript · Vite ; **stylage en CSS Modules** (`*.module.css`, compilés par Vite), aucun style en ligne ni CSS-in-JS à l'exécution | E20 · VII §37.3 |
| `migrations/` | Alembic, `render_as_batch`, `env.py` de `database.md` §5 | III §10.5 |
| `config/` | `sources.yaml`, `topics.yaml`, `entities.yaml`, `pipeline.yaml` (§3.2) ; au Sprint 1, un jeu de démonstration minimal (Q-04) | IV §16 |
| `docker/` | `backend.Dockerfile`, `caddy.Dockerfile`, `Caddyfile` (§4) | VII §36.5, §37.3 |
| `scripts/` | `deploy.sh`, `restore.sh`, `check-test-catalog.py` (§5.3), `record-llm-fixtures.py`, `synthetic-dataset.py`, `load.py` ; **`scripts/radar-dev`, ajouté par T0.9 (#60)**, non conçu ici | VIII §46.1 |
| `tests/` | `unit/<domaine>/`, `integration/<domaine>/`, `e2e/`, `fixtures/`, `fakes/` | VIII §50.2 |
| `docs/` | spec, ADR, sprints, `architecture.md`, `database.md`, puis les documents de IX §55.4 au fil des sprints | IX §55.1 |

Fichiers de la racine (VIII §46.1) : `SPEC.md`, `CLAUDE.md` (T0.7), `README.md`, `pyproject.toml` et `uv.lock`,
`alembic.ini`, `docker-compose.yml`, `docker-compose.test.yml` (surcharge e2e), `.env.example`, `.gitignore`,
`.dockerignore`, `.audit-exceptions.yaml`, `.github/workflows/ci.yml` et `scheduled.yml`. **Aucun n'est créé au
Sprint 0** (IX §57.6) : ils arrivent au Sprint 1.

---

## 3. Stratégie de configuration

### 3.1 Quatre sources, quatre usages

| Source | Contient | Versionnée | Modifiée par | Prise en compte |
|---|---|---|---|---|
| `config/*.yaml` | configuration **fonctionnelle** : sources, taxonomie, entités, réglages du pipeline | oui (Git) | commit, PR, CI, déploiement (IX §56.6-P10) | redémarrage du processus qui la lit |
| `.env` | **secrets** et **paramètres de déploiement** (VII §36.7) | **jamais** | l'exploitant, sur le VPS | `docker compose up -d <service>` (IX décision 22) |
| `Setting` (table) | réglages **modifiables depuis le dashboard** : fuseau, seuils, alertes, digests (VI §34.3) | non (base) | l'utilisateur, par l'API | worker : relu à chaque tick ; app : à chaque requête |
| Constantes du code | registres (collectors, `job_type`, clés `Setting`), schémas Pydantic, défauts | oui | code | déploiement |

Règle : un réglage fonctionnel vit dans `config/pipeline.yaml` ou dans `Setting`, **jamais** dans `.env` ; un secret
vit dans `.env`, **jamais** ailleurs (VII §36.7, VIII §46.2).

### 3.2 Fichiers `config/`

| Fichier | Chargé par | Quand | Destination | Réf. |
|---|---|---|---|---|
| `sources.yaml` | worker | démarrage, avant le scheduler | upsert `Source` (clé `key`) | IV §16.1, §16.2 |
| `topics.yaml` | worker | démarrage | upsert `Topic` (clé `slug`, `origin = seeded`) ; `keywords` = `{include, exclude}` | IV §16.3 · III §11.4 |
| `entities.yaml` | worker | démarrage | upsert `Entity` ; alias gardés **en mémoire**, jamais en base (CF-19) | IV §16.4 |
| `pipeline.yaml` | worker **et app** (lecture seule) | démarrage de chaque processus | mémoire uniquement ; **optionnel** : absent → défauts | IV §16.1, §16.5, §16.6 · E17 |

- **Emplacement** : `config/` est copié dans l'image backend au build (`COPY config/ /app/config/`). Aucun montage :
  une modification de `config/` passe par un commit et un déploiement (IX §56.6-P10). Voir P-12.
- **L'app** charge `pipeline.yaml` avec **les mêmes modèles Pydantic** que le worker, pour les seuls réglages qu'elle
  utilise : `ops.heartbeat_stale_after`, `emerging.warmup`, `llm.daily_request_budget`, `llm.app_reserve` (IV §16.1,
  E17, CF-22). Elle ne lit jamais les trois autres fichiers et n'écrit rien en base à partir de `config/`.
- **Upsert en une transaction** d'écriture, idempotent ; le YAML n'écrase jamais les champs d'état (`checkpoint`,
  `last_*`, `rate_limit_*`) (IV §16.1).
- **Validation** : un modèle Pydantic par fichier, plus les contraintes croisées, dont
  `clustering.embedding_wait + clustering.tick < llm.delay.enrich_article` (IV §16.5, V-B §28.15). Les sections de
  `pipeline.yaml` sont ajoutées **sprint par sprint**, chacune avec ses tests (E6, T-CFG-04 complet au Sprint 11).

Module proposé : `app/core/config.py` expose `load_config_files(path) -> ConfigFiles` (les quatre fichiers, pour le
worker et `validate-config`) et `load_pipeline(path) -> PipelineConfig` (pour l'app). Les deux fonctions partagent
les modèles et lèvent une erreur typée qui porte **fichier, clé et champ**.

### 3.3 Variables d'environnement

- **Liste unique** : `.env.example`, VII §36.7 (obligatoire, obligatoire en production, optionnel, réservé aux tests,
  réservé V2). **Distribution par service** : tableau de VII §36.7 ; `app` ne reçoit **aucun secret**.
- **Chargement** : un modèle `pydantic-settings` par processus (`AppSettings`, `WorkerSettings`), secrets en
  `SecretStr` (VIII §46.1, T-SEC-02). Chaque processus ne déclare que ses variables : une variable absente du
  modèle n'est jamais lue.
- **Refus de démarrer** : `HTTP_CONTACT` absent (worker, IV §22) ; `DASHBOARD_URL` invalide (app et worker, VII §36.7,
  T-CFG-07) ; `HTTP_TEST_ALLOW_HOSTS` renseignée avec `APP_ENV=production` (worker, VIII décision 23, T-CFG-09).
- **Non bloquantes** : `GITHUB_TOKEN` absent → sources `github` non planifiées (IV §22) ; `LLM_BASE_URL` absent →
  disjoncteur `not_configured` (V-A §24.2) ; `RESTIC_REPOSITORY` absent → backup `not_configured` (VII §38.3) ;
  canal d'alerte incomplet → canal désactivé (VII §36.7).
- **Paramètres fixés par Compose**, hors `.env` : `TZ=UTC` et `RADAR_DB_PATH=/data/radar.db` (VII §36.5). La source
  de l'URL de la base pour Alembic est le point **P-01**.

### 3.4 `Setting`

Table et registre en code : `database.md` §3.16 et VI §34.3. Écrits par l'app seule, validés à l'écriture (422) ; une
clé absente vaut son défaut, une valeur stockée invalide est ignorée au profit du défaut avec un `warning`. Aucun
secret (T-SEC-11). Le worker les relit à chaque tick : un changement ne demande ni redémarrage ni déploiement.

### 3.5 `validate-config`

- `python -m app.cli validate-config` : même validation que le démarrage du worker, **sans base** (IV §16.5).
- Exécution sur le VPS : `docker compose run --rm --no-deps worker python -m app.cli validate-config` (IX §56.4).
  En CI : étape 2, sur le `config/` du dépôt (VIII §49.2, T-CFG-01).
- Codes de sortie du contrat commun (IX §56.3, T-CFG-10) : `0` valide · `2` configuration invalide, avec fichier, clé
  et champ sur stdout. Le code `1` (échec de l'opération) ne sert pas ici.

### 3.6 Fichier absent ou invalide

| Situation | `worker` | `app` | Réf. |
|---|---|---|---|
| `sources.yaml`, `topics.yaml` ou `entities.yaml` **invalide** | refuse de démarrer, message avec fichier, clé et champ | non concerné | IV §16.5, T-CFG-02 |
| l'un de ces trois fichiers **absent** | non écrit par la spec (P-04) | non concerné | — |
| `pipeline.yaml` **absent** | démarre avec les défauts | démarre avec les défauts | IV §16.5 |
| `pipeline.yaml` **invalide** | refuse de démarrer | **non écrit par la spec** (P-05) | IV §16.5 · CF-22 |
| `pipeline.yaml` **modifié** | pris en compte au redémarrage | pris en compte au redémarrage | IV §16.1 |
| variable obligatoire absente ou invalide | refuse de démarrer (§3.3) | refuse de démarrer si `DASHBOARD_URL` est invalide | VII §36.7 |

Un worker qui refuse de démarrer sort en code non nul ; Docker le relance en boucle (`restart: unless-stopped`) et
`/health` passe à `down` quand le heartbeat est périmé (VII §40.2). La réponse d'exploitation est
`validate-config` (IX §56.4, §56.6-P11).

---

## 4. Conteneurs

Proposition conforme à VII §36 et §43.2. Les blocs ci-dessous seront les fichiers du Sprint 1 ; au Sprint 0, ce ne
sont que des propositions (IX §57.6). Les écarts à l'esquisse de VII §36.5 sont marqués `# ajout proposé`.

### 4.1 `docker-compose.yml` proposé

```yaml
name: radar

x-backend: &backend
  image: radar-backend:${RADAR_VERSION:-dev}
  build: { context: ., dockerfile: docker/backend.Dockerfile }
  user: "10001:10001"                      # uid/gid fixes : P-02
  read_only: true                          # dès le Sprint 1 (CF-03, VIII décision 4)
  tmpfs: [/tmp]                            # seul emplacement inscriptible hors /data
  cap_drop: [ALL]
  security_opt: ["no-new-privileges:true"]
  volumes: [radar_data:/data]              # volume nommé, jamais de bind mount (IX décision 26)
  logging:
    driver: json-file
    options: { max-size: "10m", max-file: "5" }

services:
  migrate:
    <<: *backend
    command: ["alembic", "upgrade", "head"]
    environment:
      TZ: UTC
      RADAR_DB_PATH: /data/radar.db        # lu par env.py : P-01
      LOG_LEVEL: "${LOG_LEVEL:-INFO}"
    network_mode: none
    restart: "no"

  app:
    <<: *backend
    command: ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000",
              "--workers", "1", "--no-access-log"]
    environment:                           # aucun secret (VII §36.7)
      TZ: UTC
      RADAR_DB_PATH: /data/radar.db
      APP_ENV: "${APP_ENV:-production}"
      LOG_LEVEL: "${LOG_LEVEL:-INFO}"
      DASHBOARD_URL: "${DASHBOARD_URL}"
      RADAR_VERSION: "${RADAR_VERSION:-dev}"
    expose: ["8000"]
    networks: [edge]
    depends_on: { migrate: { condition: service_completed_successfully } }
    restart: unless-stopped

  worker:
    <<: *backend
    command: ["python", "-m", "app.worker"]
    environment:                           # toutes les variables « worker » de VII §36.7, une à une
      TZ: UTC
      RADAR_DB_PATH: /data/radar.db
      APP_ENV: "${APP_ENV:-production}"
      LOG_LEVEL: "${LOG_LEVEL:-INFO}"
      RADAR_VERSION: "${RADAR_VERSION:-dev}"
      HTTP_CONTACT: "${HTTP_CONTACT}"
      DASHBOARD_URL: "${DASHBOARD_URL}"
      GITHUB_TOKEN: "${GITHUB_TOKEN:-}"
      RESTIC_REPOSITORY: "${RESTIC_REPOSITORY:-}"
      RESTIC_PASSWORD: "${RESTIC_PASSWORD:-}"
      AWS_ACCESS_KEY_ID: "${AWS_ACCESS_KEY_ID:-}"
      AWS_SECRET_ACCESS_KEY: "${AWS_SECRET_ACCESS_KEY:-}"
      LLM_BASE_URL: "${LLM_BASE_URL:-}"
      LLM_API_KEY: "${LLM_API_KEY:-}"
      LLM_MODEL: "${LLM_MODEL:-}"
      SMTP_HOST: "${SMTP_HOST:-}"
      SMTP_PORT: "${SMTP_PORT:-587}"
      SMTP_USER: "${SMTP_USER:-}"
      SMTP_PASSWORD: "${SMTP_PASSWORD:-}"
      SMTP_FROM: "${SMTP_FROM:-}"
      ALERT_EMAIL_TO: "${ALERT_EMAIL_TO:-}"
      TELEGRAM_BOT_TOKEN: "${TELEGRAM_BOT_TOKEN:-}"
      TELEGRAM_CHAT_ID: "${TELEGRAM_CHAT_ID:-}"
      ACME_EMAIL: "${ACME_EMAIL:-}"        # « toutes les autres » (VII §36.7) : sans usage côté worker, A-05
    networks: [egress]
    depends_on: { migrate: { condition: service_completed_successfully } }
    stop_grace_period: 30s
    # mem_limit: 2g                        # ajout proposé au Sprint 4, provisoire, recalé d'après M1 (P-07)
    restart: unless-stopped

  caddy:
    image: radar-caddy:${RADAR_VERSION:-dev}
    build: { context: ., dockerfile: docker/caddy.Dockerfile }
    ports: ["80:80", "443:443", "443:443/udp"]
    environment:
      DASHBOARD_URL: "${DASHBOARD_URL}"
      DASHBOARD_USER: "${DASHBOARD_USER}"
      DASHBOARD_PASSWORD_HASH: "${DASHBOARD_PASSWORD_HASH}"
      ACME_EMAIL: "${ACME_EMAIL:-}"
    volumes: [caddy_data:/data, caddy_config:/config]
    networks: [edge, public]
    cap_drop: [ALL]
    cap_add: [NET_BIND_SERVICE]
    security_opt: ["no-new-privileges:true"]   # ajout proposé (VII §43.2, T-SEC-08) : A-01, P-10
    logging: { driver: json-file, options: { max-size: "10m", max-file: "5" } }
    restart: unless-stopped

  gateway:
    profiles: [gateway]
    image: <gateway-retenu>:<version>@sha256:<digest>
    networks: [egress]
    # mem_limit : fixé d'après M1 et M6 (VII §36.5)
    restart: unless-stopped

networks:
  edge: { internal: true }
  public: {}
  egress: {}

volumes:
  radar_data: { driver: local }
  caddy_data: {}
  caddy_config: {}
```

- **Aucun healthcheck** Docker n'est proposé : la spec n'en prévoit pas, `depends_on` n'attend que la fin de
  `migrate`, et la santé est portée par `/health`, le heartbeat, la supervision fail-fast et le monitoring externe
  (VII §36.6, §40, §41). Voir P-06.
- **Surcharge e2e** `docker-compose.test.yml` (VIII §46.1, §49.2) : `APP_ENV=test`, `HTTP_TEST_ALLOW_HOSTS`, doubles
  (faux gateway, faux serveur de sources, dépôt restic local), réglages de `pipeline.yaml` raccourcis. Elle ne relâche
  aucune option de durcissement.

### 4.2 `docker/backend.Dockerfile` proposé

```dockerfile
# syntax=docker/dockerfile:1.7
# Image de base vérifiée en T0.3 (E16, V-02) : tag complet ET digest de l'index multi-architecture.
ARG PYTHON_IMAGE=python:3.12.14-slim-trixie@sha256:2f17fc044b579bab302c2e8054d3a686e2cb9a83de48e70534b94cd8ebbe06a9

# ── 1. Dépendances et code ───────────────────────────────────────────────────
FROM ${PYTHON_IMAGE} AS build
# version de uv épinglée : P-13
COPY --from=ghcr.io/astral-sh/uv:<version>@sha256:<digest> /uv /usr/local/bin/uv
WORKDIR /app
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project
COPY app/ app/
COPY migrations/ migrations/
COPY alembic.ini ./
RUN uv sync --frozen --no-dev            # bytecode compilé ici : rien à écrire au runtime

# ── 2. Modèle d'embeddings (à partir du Sprint 4) ────────────────────────────
# Révision et empreinte relevées en T0.3 (V-01), consignées dans l'ADR-0008.
FROM build AS model
ARG MODEL_REPO=qdrant/paraphrase-multilingual-MiniLM-L12-v2-onnx-Q
ARG MODEL_REVISION=faf4aa4225822f3bc6376869cb1164e8e3feedd0
ARG MODEL_ONNX_SHA256=634d0f66c29dc934c8fa72b8a4fe91dd4d420a22f1d82a241058d4316e659a99
RUN /app/.venv/bin/python - <<'PY'
import hashlib, os
from huggingface_hub import snapshot_download
d = snapshot_download(os.environ["MODEL_REPO"], revision=os.environ["MODEL_REVISION"],
                      local_dir="/opt/models/embedding")
h = hashlib.sha256(open(f"{d}/model_optimized.onnx", "rb").read()).hexdigest()
assert h == os.environ["MODEL_ONNX_SHA256"], h
PY

# ── 3. restic statique (vérifié en T0.3, V-05) ──────────────────────────────
FROM ${PYTHON_IMAGE} AS restic
ARG RESTIC_VERSION=0.19.1
ADD --checksum=sha256:f415415624dcc452f2a02b8c33641791a8c6d6d3b65bbb3543fcf9a25151585c \
    https://github.com/restic/restic/releases/download/v${RESTIC_VERSION}/restic_${RESTIC_VERSION}_linux_amd64.bz2 \
    /tmp/restic.bz2
RUN python -c "import bz2,shutil; shutil.copyfileobj(bz2.open('/tmp/restic.bz2'), open('/usr/local/bin/restic','wb'))" \
 && chmod 0755 /usr/local/bin/restic

# ── 4. Image finale ──────────────────────────────────────────────────────────
FROM ${PYTHON_IMAGE}
RUN groupadd --gid 10001 radar \
 && useradd --uid 10001 --gid 10001 --no-create-home --home-dir /nonexistent --shell /usr/sbin/nologin radar \
 && mkdir -p /data && chown 10001:10001 /data && chmod 0750 /data            # propriétaire de /data : §4.4
COPY --from=build  /app /app
# à partir du Sprint 4
COPY --from=model  /opt/models /opt/models
# à partir du Sprint 11
COPY --from=restic /usr/local/bin/restic /usr/local/bin/restic
COPY config/ /app/config/
ENV PATH=/app/.venv/bin:$PATH \
    PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    HOME=/tmp TMPDIR=/tmp XDG_CACHE_HOME=/tmp/.cache \
    HF_HUB_OFFLINE=1 RADAR_MODEL_DIR=/opt/models/embedding \
    RESTIC_CACHE_DIR=/tmp/restic-cache
WORKDIR /app
USER 10001:10001
```

- Dans un Dockerfile, un commentaire occupe sa propre ligne ; les `#` en fin de `RUN` sont des commentaires du shell.
- **Pas d'instruction `VOLUME`** : elle créerait un volume anonyme ; `/data` est toujours le volume nommé de Compose.
- **Code et modèle appartiennent à root**, en lecture seule pour l'uid 10001 : même sans `read_only`, le processus ne
  peut pas modifier son code.
- Les étapes 2 et 3 n'entrent dans l'image qu'aux sprints qui les utilisent (4 et 11) ; la vérification « modèle
  présent dans l'image » de la CI suit le même calendrier (E5, §5.1).
- Le chargement du modèle par fastembed depuis `RADAR_MODEL_DIR`, sans réseau, est à confirmer au Sprint 4 (P-09).

### 4.3 `docker/caddy.Dockerfile` proposé

```dockerfile
# syntax=docker/dockerfile:1.7
# versions de Node et de Caddy épinglées : P-13
FROM node:<24-lts>-slim@sha256:<digest> AS front
WORKDIR /front
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build                        # CSS Modules compilés par Vite, aucun style en ligne (E20)

FROM caddy:<2.x>@sha256:<digest>
COPY docker/Caddyfile /etc/caddy/Caddyfile
COPY --from=front /front/dist /srv
```

Le `Caddyfile` est celui de VII §37.3.

### 4.4 Volume `/data` et propriétaire

- `radar_data` est un **volume nommé local**, monté sur `/data` par `migrate`, `app` et `worker` (VII §36.4,
  IX décision 26). Il contient `radar.db`, `-wal`, `-shm` et `/data/backup/`.
- **Propriétaire dès la création** : l'image crée `/data` avec pour propriétaire l'uid et le gid 10001, mode `0750`.
  À la **première** montée d'un volume nommé **vide**, Docker y recopie le contenu et les droits du point de montage
  de l'image : le volume appartient donc à 10001 sans aucune étape manuelle. `migrate`, qui démarre le premier, le
  crée ; `app` et `worker` le trouvent dans cet état.
- Cette recopie n'a lieu ni pour un bind mount (interdit), ni pour un volume déjà peuplé, ni avec l'option `nocopy`.
  Un volume créé auparavant avec un autre propriétaire doit être corrigé une fois : P-02.
- `/data/backup/` est créé par le worker au premier backup (VII §38.2) ; il ne vit jamais dans le tmpfs.

### 4.5 Racine en lecture seule, tmpfs et caches (R-04)

La racine de `app`, `worker` et `migrate` est en lecture seule **dès le Sprint 1** (CF-03, VIII décision 4) ; T-SEC-09
la vérifie à l'arrivée de chaque bibliothèque (Sprint 1, puis Sprints 2, 4 et 11). Seuls `/tmp` (tmpfs, en mémoire)
et `/data` (volume) sont inscriptibles.

| Composant | Risque d'écriture | Parade | Vérifié au |
|---|---|---|---|
| Python | `__pycache__` | bytecode compilé au build (`UV_COMPILE_BYTECODE`), `PYTHONDONTWRITEBYTECODE=1` | Sprint 1 |
| Bibliothèques qui écrivent sous `~` | `~/.cache`, `~/.config` | `HOME=/tmp`, `XDG_CACHE_HOME=/tmp/.cache` | Sprint 1 |
| Alembic (`migrate`) | aucun fichier hors base | bytecode de `migrations/` compilé au build | Sprint 1 |
| lingua | modèles de langues chargés depuis le paquet, en mémoire | aucune écriture attendue ; `TMPDIR=/tmp` par précaution | Sprint 2 |
| fastembed, huggingface_hub | téléchargement et cache du modèle | modèle intégré à l'image (`/opt/models`, lecture seule), `HF_HUB_OFFLINE=1`, chargement local (P-09) | Sprint 4 (T-SEC-09, T-SEC-10) |
| onnxruntime | aucun cache disque par défaut | `TMPDIR=/tmp` | Sprint 4 |
| restic | cache local | `RESTIC_CACHE_DIR=/tmp/restic-cache` (VII §36.5) | Sprint 11 |
| SQLite | fichiers temporaires (tris, index) | `TMPDIR=/tmp` ; pour `vacuum`, fichiers temporaires sur `/data` (IX §56.4.2) : P-14 | Sprint 1 · 11 |

Le tmpfs occupe de la mémoire : sa taille compte dans `mem_limit` (P-07).

### 4.6 Démarrage et ressources

- **Ordre** : `migrate` → (`service_completed_successfully`) → `app` et `worker` ; `caddy` indépendant, 502 sur `/api`
  tant que `app` n'est pas prêt (VII §36.3). Au reboot, `migrate` n'est pas rejoué ; la vérification de révision au
  démarrage est le garde-fou (`database.md` §5).
- **Healthchecks** : aucun (§4.1, P-06).
- **`mem_limit`** : sur `worker` et `gateway`, fixé à pic mesuré × 1,5 après M1 (VII §36.5, §45.4). Valeur
  provisoire proposée pour le worker à partir du Sprint 4 : P-07. T0.3 a mesuré environ 1,0 Gio de RSS après
  chargement du seul modèle d'embeddings, avec un pic à 1,2 Gio (rapport de cadrage §3, V-01).

<!-- SUITE -->
