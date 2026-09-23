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
| `scripts/` | `deploy.sh`, `restore.sh`, `check-test-catalog.py` (§5.3), `record-llm-fixtures.py`, `synthetic-dataset.py`, `load.py` ; **`scripts/radar-dev`** : point d'entrée unique de Docker en développement, sous-commandes fixes (VIII §46.1, E22, ADR-0021), livré au Sprint 1 (#62) | VIII §46.1 |
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
  seule source du chemin de la base : `env.py`, `app` et `worker` en construisent l'URL, `alembic.ini` n'en porte
  aucune (P-01).

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
| l'un de ces trois fichiers **absent** | refuse de démarrer ; `validate-config` renvoie `2` | non concerné | IV §16.5 · P-04 |
| `pipeline.yaml` **absent** | démarre avec les défauts | démarre avec les défauts | IV §16.5 |
| `pipeline.yaml` **invalide** | refuse de démarrer | **refuse de démarrer**, même message que le worker | IV §16.5 · CF-22 · P-05 |
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
  tmpfs: [/tmp]                            # seul emplacement inscriptible hors /data ;
                                           # à partir du Sprint 4 : "/tmp:size=256m" (P-07)
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
      RADAR_DB_PATH: /data/radar.db        # seule source du chemin de la base (P-01)
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
    environment:                           # variables « worker » de VII §36.7, une à une (sans ACME_EMAIL, A-05)
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
    networks: [egress]
    depends_on: { migrate: { condition: service_completed_successfully } }
    stop_grace_period: 30s
    # à partir du Sprint 4 (P-07), provisoire, recalé d'après M1 :
    # mem_limit: 2g
    # tmpfs: ["/tmp:size=512m"]           # cache restic compris
    restart: unless-stopped

  caddy:
    image: radar-caddy:${RADAR_VERSION:-dev}
    build: { context: ., dockerfile: docker/caddy.Dockerfile }
    user: "10001:10001"                    # non-root dès le Sprint 1 (P-10)
    read_only: true
    tmpfs: [/tmp]
    ports: ["80:80", "443:443", "443:443/udp"]
    environment:
      DASHBOARD_URL: "${DASHBOARD_URL}"
      DASHBOARD_USER: "${DASHBOARD_USER}"
      DASHBOARD_PASSWORD_HASH: "${DASHBOARD_PASSWORD_HASH}"
      ACME_EMAIL: "${ACME_EMAIL:-}"
    volumes: [caddy_data:/data, caddy_config:/config]
    networks: [edge, public]
    cap_drop: [ALL]                        # sans cap_add : 80 et 443 liés grâce à
                                           # net.ipv4.ip_unprivileged_port_start=0 (Docker ≥ 20.10)
    security_opt: ["no-new-privileges:true"]
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
RUN uv sync --frozen --no-dev --no-editable \
 && /app/.venv/bin/python -m compileall -q app migrations   # bytecode du projet compilé au build

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
# /data et /config de Caddy à l'uid non-root, recopiés dans les volumes à leur création (même mécanisme que §4.4)
RUN mkdir -p /data/caddy /config/caddy \
 && chown -R 10001:10001 /data /config \
 && chmod 0750 /data /config
USER 10001:10001
```

Le `Caddyfile` est celui de VII §37.3.

**`caddy` non-root (P-10)** : utilisateur 10001, `cap_drop: ALL` **sans** `cap_add`, `no-new-privileges`, racine en
lecture seule, tmpfs `/tmp`. Depuis Docker 20.10, chaque conteneur démarre avec
`net.ipv4.ip_unprivileged_port_start=0` dans son propre espace réseau : un processus non-root y lie 80 et 443 sans
`NET_BIND_SERVICE`. `caddy_data` (certificats, compte ACME) et `caddy_config` (configuration auto-sauvegardée)
appartiennent à l'uid 10001 dès leur création. **À vérifier au Sprint 1**, sur l'image épinglée :

- l'image de base ne déclare pas `/data` ni `/config` en `VOLUME` : sinon, les changements de propriétaire faits
  après cette déclaration seraient perdus au build ;
- le binaire `caddy` peut s'exécuter avec `cap_drop: ALL` et `no-new-privileges`, même s'il porte une capacité de
  fichier (`cap_net_bind_service`) ;
- Caddy n'écrit que dans `/data`, `/config` et `/tmp` ;
- en développement rootless, le comportement des ports relève de P-03 (ADR-0021).

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
| Python | `__pycache__` | bytecode compilé au build : dépendances par `UV_COMPILE_BYTECODE`, projet installé sans mode éditable (`--no-editable`) et `app/`, `migrations/` compilés par `compileall` ; `PYTHONDONTWRITEBYTECODE=1` en plus | Sprint 1 |
| Bibliothèques qui écrivent sous `~` | `~/.cache`, `~/.config` | `HOME=/tmp`, `XDG_CACHE_HOME=/tmp/.cache` | Sprint 1 |
| Alembic (`migrate`) | aucun fichier hors base | bytecode de `migrations/` compilé au build (`compileall`) | Sprint 1 |
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
  provisoire pour le worker à partir du Sprint 4 : 2 Gio ; tmpfs borné à 256 Mo (`app`, `migrate`) et 512 Mo
  (`worker`) (P-07). T0.3 a mesuré environ 1,0 Gio de RSS après
  chargement du seul modèle d'embeddings, avec un pic à 1,2 Gio (rapport de cadrage §3, V-01).

---

## 5. Conception

### 5.1 CI en six étapes

Contrat : VIII §49 (workflows §49.1, étapes §49.2, règles §49.3, politique d'audit §49.4). Proposition de mise en
œuvre pour `.github/workflows/ci.yml` :

| Étape | Job | Contenu (VIII §49.2) | Outils (V-08) | Dépend de |
|---|---|---|---|---|
| 1 Statique | `static` | ruff, mypy strict, eslint, `tsc --noEmit`, `uv lock --check`, `npm ci`, analyse de secrets sur tout l'historique, `check-test-catalog.py` | gitleaks 8.30.1 (image officielle, `fetch-depth: 0`) | — |
| 2 Configuration | `config` | `validate-config` sur `config/` ; `docker compose config` avec `.env.example` ; `caddy validate` ; politique Compose (T-SEC-08) | image `caddy` épinglée | 1 |
| 3 Audit | `audit` | backend depuis `uv.lock`, frontend `npm audit --audit-level=high`, confrontés à `.audit-exceptions.yaml` | pip-audit 2.10.1 · npm 11.19.0 | 2 |
| 4 Tests | `tests` | pytest unitaire et intégration, réseau bloqué, couverture publiée ; vitest | pytest-socket, vitest | 3 |
| 5 Build | `build` | images `radar-backend:<sha>` et `radar-caddy:<sha>` ; vérifications d'image | BuildKit | 4 |
| 6 e2e | `e2e` | Compose + `docker-compose.test.yml` sur les images de l'étape 5 ; tests `@pytest.mark.e2e` | Compose v2 | 5 |

- Les étapes 1 à 5 tournent sur toute branche et toute PR ; l'étape 6 sur `main` et en nightly (VIII §49.1).
  `scripts/deploy.sh` exige l'étape 6 verte pour le sha déployé (VIII §49.5).
- Aucun secret : `.env.example` et les secrets factices suffisent (VIII §49.1).
- **Vérifications de l'étape 5**, lancées sur l'image construite, par `docker run --rm --entrypoint …` :
  - utilisateur non-root (`id -u` = 10001) — dès le Sprint 1 ;
  - aucun `.env` dans les couches (inspection de l'historique et du système de fichiers) — dès le Sprint 1 ;
  - **modèle d'embeddings présent dans l'image** : `RADAR_MODEL_DIR` existe et l'empreinte de `model_optimized.onnx`
    est celle de l'ADR-0008 — **ajoutée au Sprint 4**, avec les embeddings (E5). La décision est consignée dans
    `sprint-01.md` (T0.8) : l'étape 5 du Sprint 1 ne contient pas encore cette vérification.
- **Durée** : étapes 1 à 5 sous 10 minutes (VIII §49.3) ; caches uv, npm et couches Docker (R-08).
- `scheduled.yml` : nightly (1 à 6), audit hebdomadaire (3), reconstruction mensuelle sans cache (5 et 6) (VIII §49.1).

### 5.2 `Clock` (DV-18, VIII décision 7, §50.1)

Aucun instant n'est lu par `datetime.now()`, `time.time()` ou en SQL dans le code métier : tout passe par une
`Clock` injectée.

```python
# app/core/clock.py (conception)
class Clock(Protocol):
    def now(self) -> datetime: ...           # UTC, avec fuseau (UTCDateTime refuse le naïf)
    def monotonic(self) -> float: ...        # durées, délais, watchdog
    async def sleep(self, seconds: float) -> None: ...

class SystemClock:                           # production
    def now(self): return datetime.now(timezone.utc)
    def monotonic(self): return time.monotonic()
    async def sleep(self, seconds): await asyncio.sleep(seconds)

class ManualClock:                           # tests (tests/fakes/ ou tests/conftest.py)
    def __init__(self, start: datetime): self._now, self._mono = start, 0.0
    def now(self): return self._now
    def monotonic(self): return self._mono
    def advance(self, delta: timedelta): self._now += delta; self._mono += delta.total_seconds()
    async def sleep(self, seconds): self.advance(timedelta(seconds=seconds)); await asyncio.sleep(0)
```

- **Injection** : une instance par processus, créée au démarrage et passée aux composants (runner, file de jobs,
  disjoncteurs, purge, alertes, `ops.tick`, heartbeat). Les requêtes SQL reçoivent l'instant en paramètre
  (`:now`), jamais `CURRENT_TIMESTAMP` (III §10.6).
- **APScheduler** (`AsyncIOScheduler`, V-07) garde son horloge murale pour **déclencher** ; chaque job appelle une
  fonction de tick qui reçoit la `Clock` et ne lit l'heure que par elle. Les tests appellent **directement** ces
  fonctions de tick avec une `ManualClock`, sans faire tourner le scheduler (VIII §50.1). La coalescence des misfires
  (T-OPS-16) se teste sur la configuration des jobs (`coalesce=True`, `max_instances=1`) et sur la fonction de
  rattrapage au démarrage.
- **Watchdog** (VII §36.6) : le thread compare `clock.monotonic()` à l'horodatage rafraîchi par l'event-loop.
- **Aucun `sleep` réel** dans les tests unitaires et d'intégration (VIII §49.3) ; `ManualClock.sleep` avance le temps.

### 5.3 `scripts/check-test-catalog.py` (VIII §50.3)

**Entrées**

1. `docs/spec/partie-VIII.md`, **§50.5 uniquement** (entre les titres `### 50.5` et `### 50.6`). Une ligne de
   catalogue est reconnue par le motif, appliqué à la **première colonne** d'une ligne de tableau :
   `^\|\s*(T-[A-Z]+-\d{2})\s*\|`. Le niveau est lu dans la troisième colonne (`U`, `I`, `E`, `F`, `M`). Le motif ne
   dépend ni de la largeur des colonnes ni du texte du test (R-07).
2. `docs/sprints/sprint-NN.md` : statut du sprint et identifiants visés (format : P-11).
3. Les tests : marqueurs `@pytest.mark.spec("T-…")` sous `tests/`, tags `[T-FE-nn]` dans les noms des tests vitest.

**Contrôles** (bloquants, étape 1)

- **Sprints clos** (E1, précisé par P-15) : tout identifiant U, I, E ou F **visé par un sprint clos** a au moins un
  test ; sinon, échec. Les identifiants du sprint **en cours** sans test figurent dans le rapport, **sans bloquer** ;
  ils deviennent bloquants quand le `sprint-NN.md` passe à `Statut : clos`, dans la PR de bilan du sprint. Au
  Sprint 11, le contrôle porte sur **tout** le catalogue (critère VIII §52 A2).
- Tout marqueur renvoie à un identifiant existant ; aucun identifiant M n'est marqué dans le code (VIII §50.3).
- Doublons dans le catalogue, identifiant mal formé, sprint sans statut lisible → erreur.

**Identifiant partiel et test couvert en deux sprints** (E3)

Certains identifiants sont couverts en plusieurs temps : T-JOB-04, T-LLM-18, T-PRG-05, T-PRG-06, T-DB-12 (E2, E3) et
T-DB-13 (Sprint 1 : PRAGMA de `migrate` et `foreign_key_check` ; Sprint 3 : reconstruction d'`article` et triggers).
Mécanisme retenu (P-11) :

- le `sprint-NN.md` qui vise un identifiant en partie le déclare avec ses **volets** :
  `T-DB-13 [pragma, check]` au Sprint 1, `T-DB-13 [rebuild]` au Sprint 3 ;
- un test déclare le volet qu'il couvre : `@pytest.mark.spec("T-DB-13:rebuild")` ; `@pytest.mark.spec("T-DB-13")`
  couvre l'identifiant entier ;
- le script exige, pour chaque volet visé par un sprint clos, au moins un test marqué de ce volet ; les volets du
  sprint en cours sont seulement signalés (P-15).
  L'identifiant est **complet** quand tous ses volets, sur l'ensemble des sprints, ont un test ; le Sprint 11 exige
  que tous les identifiants soient complets.

**Sortie** : un rapport lisible sur stdout (identifiants sans test, par sprint et par volet, ceux du sprint en cours
marqués « non bloquant » ; marqueurs inconnus) ;
code `0` si tout est couvert, `1` sinon, `2` sur une entrée illisible (contrat de IX §56.3, appliqué par analogie).
Le script a ses propres tests, sur un catalogue et des sprints factices (R-07).

---

## 6. Points à trancher

Choix que la spec ne fixe pas, présentés avec options et recommandation. Le propriétaire les a tranchés le 2026-09-23
(revue de #71), sauf P-03, tranché par l'ADR-0021 ; chaque décision figure sous son point.

#### P-01 — Source du chemin de la base pour `migrate`, `app` et `worker`

- **Constat** : l'`env.py` de `database.md` §5 lit `sqlalchemy.url` dans la configuration Alembic ; `.env.example`
  (VII §36.7) n'a aucune variable pour la base ; l'esquisse Compose de VII §36.5 passe pourtant
  `RADAR_DB_PATH: /data/radar.db` aux trois services.
- **Options** : A. `RADAR_DB_PATH`, fixé par Compose (hors `.env`), seule source : `env.py`, `app` et `worker`
  construisent `sqlite:///{RADAR_DB_PATH}` (`sqlite+aiosqlite` pour les deux processus) ; `alembic.ini` sans URL.
  B. Variable `DATABASE_URL` ajoutée à `.env.example`. C. URL en dur dans `alembic.ini` et dans le code.
- **Recommandation** : A. La valeur est une constante de déploiement, pas un secret ; elle vit déjà dans VII §36.5.
  `database.md` §5 remplace alors `config.get_main_option("sqlalchemy.url")` par la lecture de `RADAR_DB_PATH`.

Décision (2026-09-23) : option A retenue : `RADAR_DB_PATH`, fixé par Compose, est la seule source du chemin de la base ; `env.py`, `app` et `worker` en construisent l'URL ; `alembic.ini` ne porte aucune URL — appliquée dans ce document (§3.3) et dans `database.md` §2.3, §5 et §7 (I-16).

#### P-02 — uid et gid des conteneurs, propriétaire de `/data`

- **Constat** : VII §36.5 écrit `user: "10001:10001"` dans une esquisse dont « les détails sont à l'implémenteur » ;
  VII §36.4 dit que le Dockerfile crée `/data` avec le propriétaire de l'utilisateur non-root.
- **Options** : A. uid et gid **10001** fixes, dans l'image et dans Compose ; `/data` créé `10001:10001`, `0750`, et
  recopié à la création du volume (§4.4). B. uid de l'utilisateur de l'hôte, passé au build. C. Conteneur
  d'initialisation root qui fait `chown` à chaque démarrage.
- **Recommandation** : A. Pour un volume **déjà existant** avec un autre propriétaire, une correction ponctuelle au
  runbook : `docker compose run --rm --no-deps --user 0 --cap-add CHOWN --cap-add DAC_OVERRIDE migrate chown -R
  10001:10001 /data`. C ajoute un conteneur root permanent au démarrage, contraire à VII §43.2.

Décision (2026-09-23) : option A retenue : uid et gid 10001 fixes ; `/data` créé `10001:10001`, mode `0750`, dans l'image et recopié à la création du volume ; correction ponctuelle au runbook pour un volume existant — appliquée dans §4.1, §4.2 et §4.4.

#### P-03 — Développement en Docker rootless (ADR-0021, T0.9)

Écarts attendus, à signaler dans `deployment.md` et à trancher par l'ADR-0021 (T0.9, #60) :

- **Ports 80 et 443 de Caddy** : un démon rootless ne peut pas lier un port inférieur à 1024, sauf si
  `net.ipv4.ip_unprivileged_port_start` est abaissé sur l'hôte. Sinon, publication sur 8080 et 8443 en
  développement, ce qui change `DASHBOARD_URL` (`https://localhost:8443`) ; VII §36.7 ne dit pas si un port est admis
  dans `DASHBOARD_URL` (A-04).
- **uid des volumes** : l'uid 10001 du conteneur correspond à un sous-uid de l'hôte. Sans effet sur un volume nommé
  vu depuis les conteneurs ; seul l'accès direct aux fichiers du volume depuis l'hôte change.
- **Limites cgroup** : `mem_limit` exige la délégation du contrôleur mémoire de cgroup v2 à l'utilisateur (systemd) ;
  sans elle, la limite est refusée ou ignorée.
- **Réseau** : pile réseau en espace utilisateur (slirp4netns ou pasta), plus lente ; les réseaux `internal` et
  `network_mode: none` restent disponibles.
- **Poste actuel** : démon Docker du snap (Q-01, rapport de cadrage §3.A), nettoyage suivi en #61.
- **Recommandation** : aucun choix ici ; l'ADR-0021 fixe le mode de développement (rootless ou non) et, s'il est
  rootless, la parade retenue pour chaque écart.

Décision (2026-09-23) : tranché par l'ADR-0021, accepté le 2026-09-23 : option A, parade (a). L'écart A-04 lui est rattaché.

Renvoi : [ADR-0021](adr/0021-acces-cloisonne-a-docker-en-developpement.md) — option A, Docker rootless sur le poste de
développement, avec la parade (a) pour les ports 80 et 443 (`net.ipv4.ip_unprivileged_port_start=80` sur le poste).
**ADR-0021 accepté le 2026-09-23, parade (a)** ; la mise en place du poste est l'issue #61.

#### P-04 — Fichier `config/` obligatoire absent

- **Constat** : IV §16.5 dit que `pipeline.yaml` est optionnel et que toute **erreur** fait refuser le démarrage du
  worker ; l'absence de `sources.yaml`, `topics.yaml` ou `entities.yaml` n'est pas traitée.
- **Options** : A. Absence = erreur : le worker refuse de démarrer, `validate-config` renvoie `2`. B. Absence = fichier
  vide (aucune source, aucun topic, aucune entité).
- **Recommandation** : A. Un fichier absent signale une erreur de déploiement, pas un choix.

Décision (2026-09-23) : option A retenue : un fichier `config/` obligatoire absent fait refuser le démarrage du worker, et `validate-config` renvoie `2` — appliquée dans IV §16.5 et §3.6.

#### P-05 — `pipeline.yaml` invalide côté `app` (CF-22, E17)

- **Constat** : l'app lit `pipeline.yaml` avec les mêmes modèles que le worker (IV §16.1) ; la spec ne dit pas ce
  qu'elle fait s'il est invalide.
- **Options** : A. L'app refuse de démarrer, avec le même message que le worker. B. L'app démarre avec les défauts et
  journalise une erreur. C. L'app ne valide que les clés qu'elle lit.
- **Recommandation** : A. Même fichier, même verdict : `validate-config` en CI empêche d'en arriver là, et un `/health`
  calculé sur un seuil par défaut divergerait de celui du worker (VII §40.1).

Décision (2026-09-23) : option A retenue : l'app refuse de démarrer sur un `pipeline.yaml` invalide, comme le worker — appliquée dans IV §16.5 et §3.6.

#### P-06 — Healthchecks Docker

- **Constat** : la spec ne prévoit aucun healthcheck. Compose ne redémarre pas un conteneur `unhealthy` ; un
  healthcheck ne sert qu'à `depends_on: service_healthy` et à l'affichage de `docker compose ps`.
- **Options** : A. Aucun. B. `app` : requête locale sur `/health` (mais `/health` vaut 503 quand le worker est mort :
  `app` apparaîtrait malade à tort). C. `worker` : âge du heartbeat via `app.cli health`.
- **Recommandation** : A. Supervision fail-fast, watchdog, `/health` et monitoring externe couvrent déjà le besoin
  (VII §36.6, §41).

Décision (2026-09-23) : option A retenue : aucun healthcheck Docker — appliquée dans §4.1 et §4.6.

#### P-07 — `mem_limit` et taille du tmpfs, provisoires

- **Constat** : `mem_limit` est fixé après M1 (VII §36.5) ; aucune valeur n'existe avant. Le tmpfs `/tmp` compte dans
  la mémoire du conteneur et n'a pas de taille dans l'esquisse.
- **Options** : A. Aucune limite avant M1. B. Limite provisoire à partir du Sprint 4 : `worker` 2 Gio (T0.3 : RSS
  ≈ 1,0 Gio, pic 1,2 Gio pour le seul modèle, sans lingua ni matrice) ; tmpfs borné (`size=256m` pour `app` et
  `migrate`, `512m` pour `worker`, cache restic compris).
- **Recommandation** : B, recalé d'après M1 en pré-production (pic × 1,5).

Décision (2026-09-23) : option B retenue : limites provisoires à partir du Sprint 4 (`worker` 2 Gio ; tmpfs 256 Mo pour `app` et `migrate`, 512 Mo pour `worker`), recalées d'après M1 — appliquée dans §4.1 et §4.6.

#### P-08 — Horodatage du build et reproductibilité

- **Constat** : VIII §46.2 exige des versions épinglées partout ; la spec ne dit rien de la reproductibilité des
  couches (dates des fichiers, ordre).
- **Recommandation** : hors V1. Le tag par sha Git suffit au rollback (VII décision 2) ; aucune action proposée.

Décision (2026-09-23) : hors V1, aucune action.

#### P-09 — Chargement du modèle épinglé par fastembed

- **Constat** : fastembed télécharge lui-même depuis Hugging Face, sans paramètre de révision documenté dans la
  spec ; T0.3 a relevé le dépôt réel, la révision et les empreintes (V-01).
- **Options** : A. Téléchargement au build par `huggingface_hub.snapshot_download(revision=…)` dans un dossier local,
  contrôle de l'empreinte, puis chargement par fastembed depuis ce dossier, hors ligne (§4.2). B. Laisser fastembed
  télécharger au build, puis contrôler les empreintes du cache.
- **Recommandation** : A, à confirmer au Sprint 4 (option de chargement local de fastembed) et à consigner dans
  l'ADR-0008.

Décision (2026-09-23) : option A retenue, à confirmer au Sprint 4 et à consigner dans l'ADR-0008 — appliquée dans §4.2.

#### P-10 — Utilisateur et privilèges de `caddy`

- **Constat** : VII §43.2 exige utilisateur non-root et `no-new-privileges` pour les conteneurs ; l'esquisse de
  VII §36.5 n'en donne aucun à `caddy` (A-01).
- **Options** : A. `no-new-privileges` ajouté ; utilisateur root conservé, avec `cap_drop: ALL` et
  `NET_BIND_SERVICE` seul. B. En plus, `user` non-root, si l'image Caddy retenue permet de lier 80 et 443 sans root.
- **Recommandation** : A dès le Sprint 1 ; B vérifié au Sprint 1 sur l'image épinglée.

Décision (2026-09-23) : option B retenue : `caddy` non-root dès le Sprint 1. Il lie 80 et 443 grâce à `net.ipv4.ip_unprivileged_port_start=0`, posé par défaut par Docker (≥ 20.10) dans l'espace réseau du conteneur ; `cap_drop: ALL` sans `cap_add`, `no-new-privileges`, `read_only: true`, tmpfs `/tmp` ; `caddy_data` et `caddy_config` appartiennent à cet uid par le même mécanisme que §4.4. Vérification au Sprint 1 sur l'image épinglée — appliquée dans §4.1, §4.3, VII §36.5 et VII §43.2.

#### P-11 — Statut des sprints et format des identifiants visés

- **Constat** : E1 fait lire les identifiants des sprints clos et en cours dans les `sprint-NN.md` ; ni le statut
  d'un sprint ni le format de la liste ne sont fixés.
- **Proposition** : en tête de chaque `sprint-NN.md`, une ligne `Statut : planifié | en cours | clos` ; une section
  « Identifiants visés », une ligne par identifiant, avec ses volets entre crochets s'il est partiel
  (`T-DB-13 [pragma, check]`). Marqueur de volet côté test : `spec("T-DB-13:rebuild")` (§5.3).
- **Recommandation** : cette proposition, reprise dans le plan du Sprint 1 (T0.8).

Décision (2026-09-23) : proposition retenue, reprise dans le plan du Sprint 1 (T0.8) — appliquée dans §5.3.

#### P-12 — `config/` dans l'image ou monté

- **Options** : A. Copié dans l'image au build (§4.2) : une modification passe par un déploiement (IX §56.6-P10).
  B. Monté en lecture seule depuis le clone du dépôt.
- **Recommandation** : A. L'image est alors complète et testée telle quelle en CI (étape 6) ; B introduirait un
  montage de l'hôte hors `/data`.

Décision (2026-09-23) : option A retenue : `config/` copié dans l'image au build — appliquée dans §3.2 et §4.2.

#### P-13 — Versions épinglées des outils de build

- **Constat** : VIII §46.2 impose des versions épinglées ; uv, Node et Caddy n'ont pas de version dans la spec.
- **Recommandation** : épingler au Sprint 1, par tag et digest : uv (dernière version stable à cette date), Node 24 LTS
  (version d'audit de T0.3, V-08), Caddy 2 (dernière version stable). Mise à jour par commit dédié (VIII §46.2).

Décision (2026-09-23) : recommandation retenue : uv, Node 24 LTS et Caddy 2 épinglés par tag et digest au Sprint 1 — appliquée dans §4.2 et §4.3.

#### P-14 — Fichiers temporaires de `vacuum` sur `/data`

- **Constat** : IX §56.4.2 place les fichiers temporaires de SQLite sur `/data`, jamais dans le tmpfs ; le mécanisme
  n'est pas écrit.
- **Options** : A. `SQLITE_TMPDIR=/data/tmp` dans l'environnement de la seule commande `vacuum`. B. `PRAGMA
  temp_store_directory` (déprécié par SQLite).
- **Recommandation** : A, avec création et nettoyage de `/data/tmp` par la commande.

Décision (2026-09-23) : option A retenue : `SQLITE_TMPDIR=/data/tmp` pour la seule commande `vacuum` — appliquée dans §4.5.

#### P-15 — Identifiants du sprint en cours dans `check-test-catalog.py`

- **Constat** (revue de #71) : si les identifiants du sprint **en cours** bloquent l'étape 1 de la CI, chaque PR du
  sprint échoue tant que le dernier test n'existe pas ; les checks étant obligatoires sur `main`, plus rien ne
  pourrait être fusionné.
- **Option retenue** : les identifiants des sprints **clos** bloquent ; ceux du sprint **en cours** figurent dans le
  rapport sans bloquer, et deviennent bloquants quand le `sprint-NN.md` passe à `Statut : clos` (PR de bilan).
  L'intention de E1 est conservée : chaque sprint finit avec une CI verte.

Décision (2026-09-23) : option retenue ci-dessus — appliquée dans §5.3, VIII §50.3 et décision 9, et sous E1 dans
`docs/sprints/sprint-00-cadrage.md`.

---

## 7. Écarts de spec relevés

Relevés en rédigeant ce document, puis traités par les décisions du 2026-09-23 (revue de #71) ou reportés.

| # | Écart | Passages | Statut |
|---|---|---|---|
| A-01 | `caddy` sans `no-new-privileges` ni utilisateur non-root dans l'esquisse Compose, alors que les conteneurs doivent être non-root avec `no-new-privileges` | VII §36.5 · VII §43.2 · T-SEC-08 | **traité** par P-10 : §4.1, §4.3 ; VII §36.5, §43.2, décision 5 |
| A-02 | `alembic` lit `sqlalchemy.url` alors que Compose fournit `RADAR_DB_PATH` et que `.env.example` n'a aucune variable pour la base | `database.md` §5 · VII §36.5, §36.7 | **traité** par P-01 : `database.md` §2.3, §5, §7 (I-16) ; III §10.5 |
| A-03 | Absence d'un fichier `config/` obligatoire non traitée ; comportement de l'app sur un `pipeline.yaml` invalide non écrit | IV §16.1, §16.5 · CF-22 | **traité** par P-04 et P-05 : IV §16.5 ; §3.6 |
| A-04 | `DASHBOARD_URL` : la validation (« schéma `https` ou `http://localhost`, sans chemin ni slash final ») ne dit pas si un port est admis, cas du développement rootless | VII §36.7 · T-CFG-07 | **traité** par l'ADR-0021 (accepté le 2026-09-23, parade (a)) : aucun port admis ; VII §36.7 porte la règle |
| A-05 | `ACME_EMAIL` fait partie de « toutes les autres » variables reçues par le worker, qui n'en a pas l'usage | VII §36.7 (distribution par service) | **traité** : VII §36.7 (`ACME_EMAIL` réservé à `caddy`) ; §4.1 |
| A-06 | `gateway` sans durcissement dans l'esquisse (`cap_drop`, `no-new-privileges`, `read_only`), alors que VII §43.2 vise les conteneurs sans distinction | VII §36.5 · VII §43.2 | **reporté** au Sprint 6, avec le choix du gateway |
| A-07 | `scripts/radar-dev` (T0.9) absent de l'arborescence contractuelle | VIII §46.1 | **traité** : `scripts/radar-dev` ajouté à VIII §46.1 (T0.9, #60) |
| A-08 | Le durcissement de `caddy` décidé par P-10 (non-root, `read_only`, aucune capacité) n'est couvert par aucun identifiant de test : T-SEC-08 ne cite `read_only` que pour `app` et `worker`, et la vérification du Sprint 1 n'a pas d'identifiant | VIII §50.5 (T-SEC-08) · P-10 | **traité** : T-SEC-08 étendu à `caddy` (non-root, `read_only`, aucune capacité), VIII §50.5 (T0.8, #11) ; les vérifications de l'image Caddy (§4.3) sont planifiées au Sprint 1 (`sprint-01.md`) |
