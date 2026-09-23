# Sprint 1 — Foundation

Statut : planifié

> Plan rédigé le 2026-09-23 (T0.8, #11), à valider par le propriétaire avant toute implémentation (IX §57.8,
> VIII §47.1). Contenu et acceptation : **VIII §47.2, Sprint 1** ; ce plan les découpe en tâches et ne les redéfinit pas.
> Format : `docs/architecture.md` P-11 (statut, identifiants visés avec volets). Traçabilité : P-15, seuls les sprints
> **clos** bloquent la CI ; les identifiants de ce sprint sont signalés sans bloquer jusqu'à la PR de bilan.

## Objectif

Un socle exécutable, durci et outillé, sans fonction métier : base et migrations, worker minimal, santé, configuration,
logs, Caddy et Compose conformes à VII §36.5, environnement local `radar-dev`, CI en six étapes (VIII §47.2).

## Prérequis

- **Sprint 0 accepté** : check-list IX §57.7 cochée, PR du Sprint 0 fusionnées, ADR 0001–0019 et 0021 acceptés.
- **Plan validé** : ce fichier passe de « planifié » à « en cours » dans la PR qui ouvre le sprint.
- **Poste de développement en Docker rootless** (#61, ADR-0021) **avant le premier Compose** (T1.8) : démon snap
  retiré, `docker-ce` seul, mode rootless, compte hors du groupe `docker`, réglage
  `net.ipv4.ip_unprivileged_port_start=80` (parade (a)). Les tâches T1.1 à T1.7 n'ont pas besoin de Docker.

## Ordre et contraintes

Contraintes de VIII §48 appliquées au sprint :

- **D1** — `Clock`, fabriques de sessions, `UTCDateTime`, nettoyage des secrets avant tout code métier : T1.2, T1.3.
- **D2** — heartbeat et vérification de révision avant `/health` : T1.4 et T1.6 avant T1.7.
- **D3** — service `migrate` avant toute table : T1.4 crée `migrate` et la seule table du sprint, `system_state`.
- **D4** — blocage réseau des tests et doubles avant le premier collector : blocage en T1.1, doubles branchés en T1.10
  (le premier collector arrive au Sprint 2).
- `radar-dev` V0 juste après le socle Compose (VIII §47.2, #62) : T1.9 après T1.8.

```
T1.1 ─► T1.2 ─► T1.3 ─► T1.4 ─► T1.5 ─► T1.6 ─► T1.7 ─► T1.8 ─► T1.9 ─► T1.10 ─► T1.11 ─► T1.12
                               (migrate)          (/health) (Compose) (radar-dev) (e2e)   (CI)    (docs)
```

## Tâches

### T1.1 — Squelette du dépôt et blocage réseau des tests

- **Objectif** : projet Python installable et outillage qualité, tests déjà coupés du réseau (D4).
- **Fichiers** : `pyproject.toml`, `uv.lock`, `app/__init__.py`, `tests/conftest.py`, configuration de ruff, mypy
  (strict sur `app/`) et pytest, blocage des sockets (type `pytest-socket`, VIII §50.1), `.gitignore`, `.dockerignore`.
- **Dépendances** : aucune.
- **Identifiants** : aucun du catalogue (le blocage réseau est une règle de VIII §50.1, vérifiée par un test de
  l'outillage : une connexion externe échoue).
- **Vérifiable** : `ruff check`, `ruff format --check`, `mypy` et `pytest` passent ; un test qui ouvre une connexion
  externe échoue.

### T1.2 — Noyau : `Clock`, `UTCDateTime`, configuration typée, logs et nettoyage des secrets (D1)

- **Objectif** : les briques transverses dont tout le reste dépend.
- **Fichiers** : `app/core/clock.py` (`Clock`, `SystemClock` ; `ManualClock` pour les tests, `architecture.md` §5.2),
  `app/db/types.py` (`UTCDateTime`), `app/core/config.py` (`AppSettings`, `WorkerSettings`, `SecretStr`, validation de
  `DASHBOARD_URL`), `app/core/logging.py` (structlog JSON, nettoyage des secrets aux trois niveaux, VII §42.4).
- **Dépendances** : T1.1.
- **Identifiants** : T-DB-07 · T-SEC-02 · T-SEC-01 [logs] · T-CFG-07.
- **Vérifiable** : `UTCDateTime` refuse un datetime naïf ; un secret factice n'apparaît dans aucun log capturé ;
  `DASHBOARD_URL` invalide refusée, `http://localhost` acceptée en développement.

### T1.3 — Accès base : moteurs, sessions, `BEGIN IMMEDIATE`, prérequis (D1)

- **Objectif** : l'accès SQLite de `database.md` §2, validé en T0.3 (V-03).
- **Fichiers** : `app/db/engine.py` (URL construite à partir de `RADAR_DB_PATH`, P-01 ; écouteurs `connect` et
  `begin` sur `engine.sync_engine`), `app/db/session.py` (`read_session`, `write_session` ; nom de l'option de lecture
  seule fixé ici), `app/db/prerequisites.py` (SQLite ≥ 3.35, FTS5, JSON1).
- **Dépendances** : T1.2.
- **Identifiants** : T-DB-01 · T-DB-03 · T-DB-04 · T-DB-05 · T-DB-06.
- **Vérifiable** : chaque connexion de `app` et `worker` porte les PRAGMA de III §10.2 ; deux processus écrivent en
  concurrence sans échec immédiat ; une lecture n'est pas bloquée par une écriture.

### T1.4 — Migrations : Alembic, `env.py`, `system_state`, vérification de révision (D3, D2)

- **Objectif** : le cadre de migration de `database.md` §5 et la première migration.
- **Fichiers** : `alembic.ini` (sans URL, P-01), `migrations/env.py` (moteur synchrone propre à `migrate`,
  `foreign_keys=OFF` posé dans l'écouteur `connect`, `BEGIN IMMEDIATE`, `transactional_ddl=True`,
  `transaction_per_migration=False`, `PRAGMA foreign_key_check` avant le commit), première migration `system_state`
  (`database.md` §3.19), `app/db/revision.py` (refus de démarrer hors `head`).
- **Dépendances** : T1.3.
- **Identifiants** : T-DB-02 · T-DB-08 · **T-DB-13 [pragma, check]**. Le volet `check` s'appuie sur une **migration de
  test**, dans une fixture, hors de la chaîne réelle : `system_state` n'a aucune clé étrangère. La fixture crée deux
  tables liées, introduit une violation, et vérifie l'échec de la migration, la révision Alembic et le schéma
  inchangés. Le volet `rebuild` (reconstruction d'`article`, triggers d'`article_fts`) est au Sprint 3 (VIII §47.2).
- **Vérifiable** : `alembic upgrade head` depuis une base vide ; `downgrade` testé ; la connexion de `migrate` lit
  `foreign_keys` = 0 ; une révision en base différente de `head` fait refuser le démarrage.

### T1.5 — Fichiers `config/` et `validate-config`

- **Objectif** : schémas initiaux des quatre fichiers et la commande de validation (IV §16.5, IX §56.3–§56.4).
- **Fichiers** : `config/sources.yaml`, `topics.yaml`, `entities.yaml`, `pipeline.yaml` — **jeu de démonstration
  minimal** (Q-04) ; `app/core/config_files.py` (modèles Pydantic, `load_config_files`, `load_pipeline`,
  `architecture.md` §3.2) ; `app/cli/validate_config.py` et le contrat commun des commandes (codes `0` / `1` / `2`,
  stdout / stderr).
- **Dépendances** : T1.2.
- **Identifiants** : T-CFG-01 · T-CFG-02 [schemas] · T-CFG-10.
- **Vérifiable** : `validate-config` accepte le `config/` du dépôt ; un fichier invalide ou un fichier obligatoire
  absent donne le code `2` avec fichier, clé et champ (IV §16.5, P-04).

### T1.6 — Worker minimal : heartbeat, boot, supervision, watchdog, SIGTERM (D2)

- **Objectif** : le worker de VII §36.6, sans tâche métier.
- **Fichiers** : `app/worker.py`, `app/ops/heartbeat.py` (`SystemState.worker_heartbeat` toutes les 30 s),
  `app/ops/watchdog.py`, supervision fail-fast des tâches permanentes.
- **Dépendances** : T1.4 (table `system_state`), T1.5 (vérifications du boot : `validate-config`).
- **Identifiants** : T-CFG-05 · T-OPS-07 · T-OPS-08 [heartbeat] · T-OPS-09 · T-OPS-10 [verifications, heartbeat] ·
  T-OPS-11 [arret].
- **Vérifiable** : sans `HTTP_CONTACT`, le worker refuse de démarrer ; heartbeat écrit avant toute autre étape de
  boot ; event-loop gelée → arrêt ; tâche permanente en exception → sortie non nulle ; SIGTERM → arrêt propre.

### T1.7 — Santé : `/health`, `/api/health` minimal, `app.cli health` (D2)

- **Objectif** : FastAPI (un processus uvicorn) et le module unique de santé (VII §40, `app/ops/health.py`).
- **Fichiers** : `app/main.py` (docs désactivées hors `development`), `app/ops/health.py` (composants `database`,
  `worker`), routes `/health` et `/api/health`, lecture de `pipeline.yaml` par l'app (`ops.heartbeat_stale_after`, E17 ;
  refus de démarrer si invalide, P-05), `app/cli/health.py` (runbook du Sprint 1, IX §55.4).
- **Dépendances** : T1.3, T1.5, T1.6.
- **Identifiants** : T-OPS-01 · T-OPS-02 · T-OPS-03 · T-SEC-05.
- **Vérifiable** : `/health` = `{"status":"ok"}` (200) avec un heartbeat frais ; 503 si le heartbeat est périmé ou la
  base inaccessible ; `/docs` absent en production.

### T1.8 — Images et Compose : backend, Caddy, SPA vide

- **Objectif** : les blocs proposés en `architecture.md` §4, devenus fichiers ; premier Compose (après #61).
- **Fichiers** : `docker/backend.Dockerfile` (image `python:3.12.14-slim-trixie` épinglée par digest, E16 ; bytecode
  compilé ; **ni modèle d'embeddings (Sprint 4, E5) ni restic (Sprint 11)**), `docker/caddy.Dockerfile`,
  `docker/Caddyfile` (VII §37.3), `frontend/` minimal (React · TypeScript · Vite, CSS Modules, E20 ; SPA vide),
  `docker-compose.yml` (VII §36.5 ; `caddy` non-root, uid 10001, sans capacité, en lecture seule, P-10),
  `.env.example` (VII §36.7).
- **Vérifications de l'image Caddy** (`architecture.md` §4.3), sur l'image épinglée :
  - le binaire `caddy` s'exécute avec `cap_drop: ALL` et `no-new-privileges` ; s'il porte une capacité de fichier
    qui l'en empêche, parade probable : recopier le binaire sans ses attributs étendus ;
  - l'image de base ne déclare pas `/data` ni `/config` en `VOLUME` (sinon le `chown` du build est perdu) ;
  - Caddy n'écrit que dans `/data`, `/config` et `/tmp`.
  Le résultat est consigné dans le bilan.
- **Dépendances** : T1.7 ; **#61** (poste en rootless) avant le premier `docker compose up`.
- **Identifiants** : T-SEC-08 (politique Compose, `caddy` compris).
- **Vérifiable** : `docker compose config` valide ; `caddy validate` passe ; la politique Compose (T-SEC-08) passe sur
  la sortie de `docker compose config`.

### T1.9 — `scripts/radar-dev` V0 (#62)

- **Objectif** : le seul point d'entrée de Docker en développement (VIII §46.1, ADR-0021).
- **Fichiers** : `scripts/radar-dev` (sous-commandes fixes `up`, `down`, `reset`, `ps`, `logs <service>`, `test`,
  `e2e`, `health` ; liste fermée des services ; projet Compose de développement dédié) ; `.claude/settings.json`
  (`scripts/radar-dev` autorisé, appel direct à `docker` refusé, **ligne `Co-Authored-By` désactivée** :
  `includeCoAuthoredBy: false`, commentaire de revue de #62) ; section d'usage dans `docs/testing.md`.
- **Dépendances** : T1.8 ; #61.
- **Identifiants** : **T-CFG-11**.
- **Vérifiable** : chaque sous-commande fonctionne sur le Compose de T1.8 ; hors liste → code `2`, aucun appel à
  `docker` ; le script passe shellcheck.

### T1.10 — Surcharge e2e, doubles branchés et tests e2e

- **Objectif** : l'e2e du sprint, sur les images de T1.8, joué par `radar-dev e2e` (D4 : doubles avant le premier
  collector).
- **Fichiers** : `docker-compose.test.yml` (`APP_ENV=test`, `HTTP_TEST_ALLOW_HOSTS`, doubles), `tests/fakes/` (faux
  gateway et faux serveur de sources **vides mais branchés**, VIII §47.2), `tests/e2e/`.
- **Dépendances** : T1.8, T1.9.
- **Identifiants** : T-SEC-03 · T-SEC-06 · T-SEC-09 [base] (racine en lecture seule : Python, uvicorn, Alembic ;
  « sans restic », VIII §47.2) · T-RES-10.
- **Vérifiable** : `radar-dev e2e` vert : `/health` sans authentification, `/` et `/api/*` en 401, en-têtes de Caddy,
  racine en lecture seule fonctionnelle, échec de `migrate` → `app` et `worker` ne démarrent pas.

### T1.11 — CI en six étapes et traçabilité du catalogue

- **Objectif** : `.github/workflows/ci.yml` et `scheduled.yml` (VIII §49, `architecture.md` §5.1), et
  `scripts/check-test-catalog.py` (§5.3 : motif sur la première colonne, sprints clos bloquants, sprint en cours
  signalé, volets).
- **Fichiers** : workflows, `scripts/check-test-catalog.py` et ses tests, `.audit-exceptions.yaml`.
- **Étape 5 au Sprint 1** : utilisateur non-root, aucun `.env` dans les couches ; **pas de vérification « modèle dans
  l'image »**, ajoutée au Sprint 4 (E5).
- **Dépendances** : T1.10.
- **Identifiants** : aucun du catalogue en propre ; la CI exécute tous ceux du sprint.
- **Vérifiable** : les six étapes vertes sur `main`, e2e compris ; `check-test-catalog.py` lit ce plan et signale les
  identifiants du sprint sans bloquer (P-15).

### T1.12 — Documentation d'exploitation du Sprint 1 et modèles GitHub

- **Objectif** : les documents créés au Sprint 1 (IX §55.4) et les modèles d'issue et de PR (planning, fiche S1).
- **Fichiers** : `docs/runbook.md` (`validate-config`, `health`, commandes de base, IX §56.5), `docs/testing.md`
  (niveaux, doubles, blocage réseau, `Clock`, marqueurs `spec`, `radar-dev`, écarts du rootless constatés avec #61),
  `docs/deployment.md` (développement : Compose local, `https://localhost`), `.github/` (modèles d'issue et de PR avec
  la check-list VIII §51.1).
- **Dépendances** : T1.9, T1.11.
- **Identifiants** : aucun.
- **Vérifiable** : les trois documents existent et renvoient à la spec ; les modèles sont utilisés par les PR suivantes.

## Tableau récapitulatif

| # | Tâche | Dépend de | Identifiants |
|---|---|---|---|
| T1.1 | Squelette et blocage réseau | — | — |
| T1.2 | Noyau (`Clock`, `UTCDateTime`, configuration, logs) | T1.1 | T-DB-07, T-SEC-02, T-SEC-01 [logs], T-CFG-07 |
| T1.3 | Accès base | T1.2 | T-DB-01, 03, 04, 05, 06 |
| T1.4 | Migrations et `system_state` | T1.3 | T-DB-02, 08, T-DB-13 [pragma, check] |
| T1.5 | `config/` et `validate-config` | T1.2 | T-CFG-01, T-CFG-02 [schemas], T-CFG-10 |
| T1.6 | Worker minimal | T1.4, T1.5 | T-CFG-05, T-OPS-07, 08 [heartbeat], 09, 10 [verifications, heartbeat], 11 [arret] |
| T1.7 | Santé | T1.3, T1.5, T1.6 | T-OPS-01, 02, 03, T-SEC-05 |
| T1.8 | Images et Compose | T1.7, #61 | T-SEC-08 |
| T1.9 | `radar-dev` V0 (#62) | T1.8, #61 | T-CFG-11 |
| T1.10 | e2e et doubles | T1.8, T1.9 | T-SEC-03, 06, T-SEC-09 [base], T-RES-10 |
| T1.11 | CI et traçabilité | T1.10 | — |
| T1.12 | Documentation et modèles GitHub | T1.9, T1.11 | — |

## Identifiants visés

Liste de VIII §47.2, Sprint 1, avec les volets de ce sprint (P-11). Un identifiant sans crochets est visé en entier.

```
T-DB-01          T1.3
T-DB-02          T1.4
T-DB-03          T1.3
T-DB-04          T1.3
T-DB-05          T1.3
T-DB-06          T1.3
T-DB-07          T1.2
T-DB-08          T1.4
T-DB-13 [pragma, check]                  T1.4   (volet rebuild : Sprint 3)
T-CFG-01         T1.5
T-CFG-02 [schemas]                       T1.5   (volet collectors : Sprint 2, VIII §47.2)
T-CFG-05         T1.6
T-CFG-07         T1.2
T-CFG-10         T1.5
T-CFG-11         T1.9
T-OPS-01         T1.7
T-OPS-02         T1.7
T-OPS-03         T1.7
T-OPS-07         T1.6
T-OPS-08 [heartbeat]                     T1.6   (autres volets : voir « Écarts relevés »)
T-OPS-09         T1.6
T-OPS-10 [verifications, heartbeat]      T1.6   (autres volets : voir « Écarts relevés »)
T-OPS-11 [arret]                         T1.6   (volet jobs : voir « Écarts relevés »)
T-SEC-01 [logs]                          T1.2   (volet clients : voir « Écarts relevés »)
T-SEC-02         T1.2
T-SEC-03         T1.10
T-SEC-05         T1.7
T-SEC-06         T1.10
T-SEC-08         T1.8
T-SEC-09 [base]                          T1.10  (sans restic, VIII §47.2 ; lingua et onnxruntime : voir « Écarts relevés »)
T-RES-10         T1.10
```

## Critères d'acceptation

Ceux de **VIII §47.2, Sprint 1**, sans ajout :

- `docker compose up -d` en une commande : `migrate` se termine, puis `app`, `worker` et `caddy` sont `running` ;
- `https://localhost/health` répond `{"status":"ok"}` sans identifiants, et `/api/health` demande une authentification ;
- WAL actif ; `app` et `worker` refusent de démarrer sur un schéma qui n'est pas à `head` ;
- CI verte, e2e compris ;
- identifiants de tests de VIII §47.2 (liste ci-dessus) couverts.

S'y ajoutent la DoD de sprint (VIII §51.2) et les règles de sortie communes du planning (§0).

## Issues à créer à la validation du plan

Milestone **S1**, label `type:tâche`, une issue par tâche. Aucune n'est créée par ce plan.

| Titre | Tâche |
|---|---|
| S1 · T1.1 — Squelette du dépôt et blocage réseau des tests | T1.1 |
| S1 · T1.2 — Noyau : Clock, UTCDateTime, configuration typée, logs et nettoyage des secrets | T1.2 |
| S1 · T1.3 — Accès base : moteurs, sessions, BEGIN IMMEDIATE, prérequis | T1.3 |
| S1 · T1.4 — Migrations : Alembic, env.py, system_state, vérification de révision | T1.4 |
| S1 · T1.5 — Fichiers config/ de démonstration et validate-config | T1.5 |
| S1 · T1.6 — Worker minimal : heartbeat, boot, supervision, watchdog, SIGTERM | T1.6 |
| S1 · T1.7 — Santé : /health, /api/health minimal, app.cli health | T1.7 |
| S1 · T1.8 — Images et Compose : backend, Caddy, SPA vide | T1.8 |
| *(existe : #62)* S1 · radar-dev V0 | T1.9 |
| S1 · T1.10 — Surcharge e2e, doubles branchés et tests e2e | T1.10 |
| S1 · T1.11 — CI en six étapes et traçabilité du catalogue | T1.11 |
| S1 · T1.12 — Documentation d'exploitation et modèles GitHub | T1.12 |

Issue 👤 déjà ouverte : **#61** (poste en Docker rootless), prérequis de T1.8 et T1.9.

## Écarts relevés

Identifiants que VIII §47.2 place au Sprint 1 alors qu'une partie de leur objet arrive plus tard. Ce plan ne vise au
Sprint 1 que le volet qui existe ; le reste n'a pas de sprint explicite dans VIII §47.2, hors joker du Sprint 11
(« T-OPS-* · T-SEC-* »). À trancher par le propriétaire (placement des volets restants), comme pour E3 :

- **T-OPS-08** : la boucle AI (Sprint 5), la file d'embeddings (Sprint 4), le scheduler (Sprint 2) et la condition
  `job_failing` (Sprint 11) n'existent pas au Sprint 1.
- **T-OPS-10** : requalification des `processing` (`AIJob`, Sprint 2 et 5) et des `sending` (`AlertLog`, Sprint 10),
  modèles et matrice (Sprint 4), scheduler (Sprint 2).
- **T-OPS-11** : aucun job ni run à attendre avant les Sprints 2 et 5.
- **T-SEC-01** : les clients GitHub, LLM, Telegram, SMTP et restic arrivent aux Sprints 2, 6, 10 et 11.
- **T-SEC-09** : « sans restic » au Sprint 1, mais lingua (Sprint 2) et onnxruntime (Sprint 4) ne sont pas encore dans
  l'image ; `architecture.md` §4.5 prévoit une vérification à leur arrivée, que VIII §47.2 ne liste pas aux Sprints 2
  et 4.
- **T-OPS-09** : sans modèle avant le Sprint 4, « le heartbeat démarre avant le chargement des modèles » se vérifie
  au Sprint 1 sur la seule séquence existante.
- **Planning, fiche S1** : sa ligne « Tests » ne cite ni T-DB-13, ni T-CFG-10, ni T-CFG-11.

## Bilan

*À remplir en fin de sprint : écarts à la spec, dette tracée, identifiants couverts, résultat des vérifications de
l'image Caddy, écarts du Docker rootless constatés.*
