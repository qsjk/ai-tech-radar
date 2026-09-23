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

<!-- SUITE -->
