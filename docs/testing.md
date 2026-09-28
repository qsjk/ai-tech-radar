# Tests et environnement local

Mode d'emploi des tests (IX §55.4). Ce document est créé au Sprint 1 avec sa première section ; les autres (niveaux,
doubles, blocage réseau, horloge, marqueurs `spec`, e2e en local, échec d'audit, `record-llm-fixtures`) arrivent avec
T1.12 et les sprints qui les concernent.

## Environnement local par `radar-dev`

`scripts/radar-dev` est le **seul point d'entrée de Docker** sur le poste de développement (VIII §46.1, E22,
ADR-0021). Claude Code n'appelle jamais `docker` ni `docker compose` en direct : `.claude/settings.json` autorise
`scripts/radar-dev` et refuse les appels directs. Le script est un point d'entrée prévisible, pas une barrière :
l'isolation vient du mode rootless du démon (ADR-0021).

### Prérequis

- Docker en mode rootless, contexte `rootless` par défaut, compte hors du groupe `docker` (#61).
- `net.ipv4.ip_unprivileged_port_start=80` sur le poste, pour que Caddy publie 80 et 443 (ADR-0021, parade (a)).
- Un fichier `.env` local, jamais commité, copié de `.env.example` et complété. Pour le poste :
  `DASHBOARD_URL=https://localhost`, identifiants factices, et un hash bcrypt factice produit par
  `caddy hash-password`. Sans `.env`, les sous-commandes Docker s'arrêtent en code `2` avec un message.

### Sous-commandes

| Commande | Effet |
|---|---|
| `scripts/radar-dev up` | construit les images et démarre le Compose de développement (`up --detach --build`) |
| `scripts/radar-dev down` | arrête et supprime ses conteneurs ; les volumes sont conservés |
| `scripts/radar-dev reset` | Compose neuf : `down --volumes`, puis `up --detach --build` |
| `scripts/radar-dev ps` | liste ses conteneurs, arrêtés compris (`migrate` se termine en `Exited (0)`) |
| `scripts/radar-dev logs <service>` | logs d'un service parmi `migrate`, `app`, `worker`, `caddy` |
| `scripts/radar-dev health` | détail de santé : `python -m app.cli health` dans `app` (IX §56.4) |
| `scripts/radar-dev test` | suite pytest du poste, comme l'étape 4 de la CI (sans Docker) |
| `scripts/radar-dev e2e` | tests e2e dans le projet dédié `radar-dev-e2e` (voir « Tests e2e ») ; aucun `.env` requis |

- **Aucun argument libre** n'est transmis à `docker`. Le seul argument admis est un nom de service, pris dans une
  liste fermée. Une sous-commande ou un argument hors liste renvoie le code `2`, avec l'usage sur stderr, sans rien
  exécuter (T-CFG-11).
- Codes de sortie de IX §56.3 : `0` succès, `1` échec de l'opération (une commande `docker compose` en échec, par
  exemple), `2` usage invalide ou `.env` absent.

### Projet Compose de développement

Le script fixe le projet **`radar-dev`** : conteneurs `radar-dev-<service>-1`, volumes `radar-dev_radar_data`,
`radar-dev_caddy_data` et `radar-dev_caddy_config`. Les projets `radar` (production) et `radar-load` (charge) ne sont
jamais utilisés sur le poste. Le fichier `docker-compose.yml` garde `name: radar` ; le script le remplace par
`--project-name`.

### Écarts du mode rootless

Le poste tourne en Docker rootless, la CI et la production en Docker root (ADR-0021). Écarts relevés à ce jour :

- **Ports 80 et 443** : publiés grâce à `net.ipv4.ip_unprivileged_port_start=80` sur le poste (ADR-0021, parade (a)) ;
  `DASHBOARD_URL` reste sans port, identique à la production.
- **Limites d'E/S de cgroup** : au démarrage du démon, avertissements `No io.max (rbps/wbps/riops/wiops) support`
  (contrôleur non délégué au compte). Sans effet au Sprint 1. La délégation du contrôleur mémoire deviendra nécessaire
  pour `mem_limit` au Sprint 4 (P-07).
- **Réseau** : pile en espace utilisateur (`slirp4netns`, `rootlesskit` 3.1.0), plus lente ; les réseaux `internal`
  et `network_mode: none` fonctionnent (T1.8).
- **uid des volumes** : l'uid 10001 des conteneurs correspond à un sous-uid de l'hôte (`/etc/subuid`). Sans effet vu
  des conteneurs ; seul l'accès direct aux fichiers des volumes depuis l'hôte change.
- **AppArmor** : Ubuntu 24.04 pose `kernel.apparmor_restrict_unprivileged_userns = 1`, sans blocage constaté du
  rootless.

L'e2e de référence reste celui de la CI (VIII §49.2, étape 6) ; tout nouvel écart est ajouté ici.

## Tests e2e

Les tests e2e (niveau E, VIII §50.2) vérifient la stack Compose construite : ils tournent **sur l'hôte**, ou sur le
runner de la CI, contre les conteneurs, jamais dans une image. Ils sont exclus de `uv run pytest` par défaut
(`-m "not e2e"` dans `pyproject.toml`) ; T1.11 les branche à l'étape 6 de la CI.

### Lancement

```
scripts/radar-dev e2e
```

Enchaînement, dans le projet Compose dédié **`radar-dev-e2e`** (décision du propriétaire du 2026-09-27, #99) :

1. `up --detach --build --wait` sur `docker-compose.yml` et la surcharge `docker-compose.test.yml`, avec
   `.env.example` pour l'interpolation : aucun `.env` local n'est requis ;
2. `uv run pytest -m e2e tests/e2e` ;
3. `down --volumes --remove-orphans`, **toujours**, succès, échec ou interruption.

Le code de sortie suit celui des tests : `0` s'ils passent, `1` sinon (IX §56.3). Le projet `radar-dev` n'est jamais
touché : l'e2e peut tourner pendant que l'environnement de développement est démarré.

### Surcharge `docker-compose.test.yml`

- `APP_ENV=test` pour `app` et `worker` ; `HTTP_TEST_ALLOW_HOSTS=fake-gateway,fake-sources` pour le worker
  (VIII décision 23) ;
- secrets factices `FAKE-…` uniquement ; identifiants du tableau de bord `FAKE-e2e-user` et
  `FAKE-dashboard-password`, dont le hash bcrypt factice figure dans la surcharge ;
- images taguées `e2e` (`radar-backend:e2e`, `radar-caddy:e2e`, `radar-fakes:e2e`), distinctes de celles de
  `radar-dev` ;
- aucune option de durcissement relâchée ; les doubles sont durcis comme les services ;
- réseau `egress` en `internal: true` : en e2e, le worker n'a aucune route vers Internet et ne joint que les doubles
  (VIII §50.1 ; revue de #100).

### Taille des corps

Caddy refuse en **413** tout corps annoncé à plus de 1 Mo par `Content-Length`, avant l'authentification et avant
l'app (bloc `@body_too_large` du Caddyfile, revue de #100). La réponse passe par `handle_errors` : elle porte les
en-têtes de sécurité et aucun `Server`. `request_body { max_size 1MB }` reste en place pour les corps effectivement
lus, `chunked` compris. Un corps de 1 Mo ou moins atteint l'app comme avant.

### Ports

| Projet | HTTP | HTTPS |
|---|---|---|
| `radar-dev` | 80 | 443 |
| `radar-dev-e2e` | 8080 | 8443 |
| `radar-dev-e2e-migrate-failure` (T-RES-10, jetable) | 8081 | 8444 |

`DASHBOARD_URL` reste `https://localhost`, sans port (VII §36.7) : Caddy sert le site `localhost` quel que soit le
port publié sur l'hôte.

### Doubles

`tests/fakes/fake_gateway.py` et `tests/fakes/fake_sources.py`, sur une base commune (`tests/fakes/http_double.py`),
sont **vides mais branchés** (VIII §47.2, §50.4) : ils démarrent, répondent `GET /health` et journalisent chaque
requête. Ils tournent en conteneur (`tests/fakes/Dockerfile`) sur les réseaux `edge` et `egress` de la stack e2e ;
`app` et `worker` les joignent sur `http://fake-gateway:8000` et `http://fake-sources:8000`. Leurs comportements
scriptables arrivent avec leurs consommateurs (collectors au Sprint 2, couche LLM au Sprint 6).

### Réseau et TLS

- Les tests ne joignent la stack que par `https://localhost:8443` ; pytest-socket reste actif (hôte local seulement).
- Le certificat de Caddy est **vérifié** contre son autorité interne, lue dans le conteneur `caddy`
  (`/data/caddy/pki/authorities/local/root.crt`).
- Les vérifications qui demandent l'intérieur des conteneurs (`ps`, `logs`, `exec`) passent par `docker compose`
  sur le seul projet e2e, avec des arguments fixes.

### Contenu

| Fichier | Identifiants |
|---|---|
| `tests/e2e/test_auth.py` | T-SEC-03 |
| `tests/e2e/test_caddy.py` | T-SEC-06, dont le 413 d'un corps annoncé à plus de 1 Mo, avec et sans identifiants |
| `tests/e2e/test_read_only.py` | T-SEC-09 [base] : Python, uvicorn, Alembic, sans restic |
| `tests/e2e/test_doubles.py` | doubles branchés (VIII §47.2) ; le worker ne joint aucune adresse externe (délai de 5 s par essai) mais joint toujours les doubles |
| `tests/e2e/test_migrate_failure.py` | T-RES-10, dans le projet jetable `radar-dev-e2e-migrate-failure`, supprimé à la fin |

Les attentes sont bornées (60 s) ; aucun test e2e n'attend sans borne (VIII §49.3).

## CI en six étapes

`.github/workflows/ci.yml` (VIII §49.1, §49.2 ; `architecture.md` §5.1). Un job par étape, dans l'ordre ; chaque étape
bloque les suivantes. Les étapes 1 à 5 tournent sur toute branche et toute PR, l'étape 6 sur `main` et dans les
workflows planifiés. Aucun secret : `.env.example` et les secrets factices `FAKE-…` suffisent. Actions et images sont
épinglées par sha ou par digest.

| Job | Contenu | En local |
|---|---|---|
| `1 · Statique` | `uv lock --check` · ruff · `ruff format --check` · mypy strict · shellcheck · `npm ci` · eslint (`react/no-danger`) · `tsc --noEmit` · gitleaks 8.30.1 sur **tout l'historique** · `scripts/check-test-catalog.py` | `uv run ruff check` … ; `npm run lint`, `npm run typecheck` dans `frontend/` |
| `2 · Configuration` | `validate-config` · `docker compose config` avec `.env.example` · `caddy validate` dans l'image `radar-caddy` (tmpfs sur `/data` et `/config`, variables de `.env.example`) · politique Compose T-SEC-08. L'étape échoue si `docker` est absent, pour que la politique ne soit jamais sautée | `uv run python -m app.cli validate-config` |
| `3 · Audit` | pip-audit 2.10.1 sur `uv.lock` et `npm audit`, confrontés à `.audit-exceptions.yaml` par `scripts/check-audit.py` (action `.github/actions/audit`) | voir ci-dessous |
| `4 · Tests` | pytest (réseau bloqué, couverture dans le résumé) · vitest | `scripts/radar-dev test` ; `npm test` dans `frontend/` |
| `5 · Build` | `radar-backend:<sha>` et `radar-caddy:<sha>` (cache des couches) ; `id -u` = 10001 ; aucun `.env` dans l'historique ni dans le système de fichiers. La vérification « modèle dans l'image » arrive au Sprint 4 (E5) | — |
| `6 · e2e` | images de l'étape 5 chargées **sans reconstruction** (seuls les doubles sont construits) ; projet `radar-dev-e2e`, ports 8080 et 8443, sans `.env` ; `uv run pytest -m e2e` ; logs de la stack publiés en cas d'échec, puis `down --volumes` dans tous les cas | `scripts/radar-dev e2e` |

Durée visée des étapes 1 à 5 : moins de 10 minutes (VIII §49.3), avec les caches uv, npm et des couches Docker.

### Audit et exceptions

- Backend : toute vulnérabilité remontée par pip-audit bloque (pip-audit ne donne pas de sévérité). Frontend : `high`
  et `critical` bloquent ; `moderate` et en dessous figurent dans le résumé du job, sans bloquer.
- `.audit-exceptions.yaml` : une entrée par vulnérabilité acceptée, avec `id`, `package`, `justification` et
  `expires` (au plus 90 jours). Une exception expirée, trop lointaine ou incomplète fait échouer l'étape (VIII §49.4).
- Codes de `scripts/check-audit.py` : `0` OK, `1` constat bloquant ou exception invalide, `2` entrée illisible.

### Rapport de traçabilité

`scripts/check-test-catalog.py` (VIII §50.3, `architecture.md` §5.3) lit le catalogue de VIII §50.5 (motif sur la
première colonne, niveau en troisième), le statut et les « Identifiants visés » de chaque `docs/sprints/sprint-NN.md`,
les marqueurs `spec` (volets compris) sous `tests/` et les tags `[T-FE-nn]` des tests vitest.

- Sprint **clos** : tout identifiant U, I, E ou F visé, et chaque volet, doit avoir un test ; sinon `MISSING … —
  BLOCKING` et code `1`.
- Sprint **en cours** : les manques sont listés `missing … — non-blocking (sprint in progress, P-15)`, code `0`.
- Marqueur inconnu, mal formé ou identifiant M marqué : erreur, code `1`.
- Entrée illisible (section §50.5 absente, identifiant mal formé ou en double, niveau inconnu, statut illisible) :
  code `2`, message sur stderr.

Lancement : `uv run python scripts/check-test-catalog.py`. Le rapport est aussi publié dans le résumé de l'étape 1.

### Workflows planifiés

`.github/workflows/scheduled.yml` (VIII §49.1), sur `main` :

| Déclencheur | Cron (UTC) | Contenu |
|---|---|---|
| nightly | `17 2 * * *` | `ci.yml` complet, étapes 1 à 6, e2e compris |
| hebdomadaire | `43 4 * * 1` (lundi) | étape 3 seule, sur les lockfiles de `main` |
| mensuel | `29 3 1 * *` (le 1er) | `ci.yml` complet, images reconstruites sans cache et images de base téléchargées à nouveau, e2e compris |

## Niveaux et emplacement

Niveaux et exécution : VIII §50.2. Emplacement dans le dépôt :

| Niveau | Emplacement | Lancement |
|---|---|---|
| U — unitaire | `tests/unit/<domaine>/` (`core`, `db`, `cli`, `ops`, `fakes`, `tooling`) | `uv run pytest` (ou `scripts/radar-dev test`) |
| I — intégration | `tests/integration/<domaine>/` (`db`, `ops`, `app`, `cli`) : SQLite réel sur fichier en WAL, migré à `head`, jamais `:memory:` (VIII §50.1) ; sous-processus pour les comportements de niveau processus | `uv run pytest` |
| E — e2e Compose | `tests/e2e/`, marqueur `e2e`, exclu par défaut | `scripts/radar-dev e2e` (voir « Tests e2e ») |
| F — frontend | `frontend/src/**/*.test.tsx` (vitest) | `npm test` dans `frontend/` |
| M — manuel sur VPS | procédure dans `docs/`, preuve dans `go-live.md` ou `measurements.md` (Sprint 11) | — |

Aides partagées : `tests/fakes/` (doubles et horloges), `tests/integration/conftest.py` (base migrée `migrated_db`,
dossier `config_dir` à réglages courts), `tests/integration/process.py` (sous-processus à logs JSON, attentes bornées).
`tests/fixtures/` (réponses HTTP par type, sorties LLM enregistrées…) arrive avec ses consommateurs (VIII §50.2).

## Doubles

Liste, rôle et exigences : VIII §50.4. Au Sprint 1, seuls `fake_gateway.py` et `fake_sources.py` existent, vides mais
branchés : voir « Tests e2e », section « Doubles ». Règle : un double s'ajoute avec son premier consommateur et se
documente ici (IX §55.4). Aucun test n'appelle un vrai provider (VIII §49.3).

## Blocage réseau

Règle : VIII §50.1. Mise en œuvre : `pytest-socket`, par les options de `[tool.pytest.ini_options]` dans
`pyproject.toml` (`--allow-hosts=127.0.0.1,::1 --allow-unix-socket`), pour toute la session ; vérifié par
`tests/unit/tooling/test_network_blocking.py`.

**Limite** (report de la revue de #89) : pytest-socket bloque `connect()` vers tout hôte autre que `127.0.0.1`, `::1`
et les sockets Unix, mais **pas** la résolution DNS (`getaddrinfo`, par la libc) ni un `sendto` UDP sans `connect`.
Un test qui passe un nom d'hôte externe peut donc déclencher une vraie requête DNS avant d'être bloqué.

**Règle** : les tests n'utilisent que des adresses IP (par exemple `192.0.2.1`, adresse de documentation jamais
routée) ou les doubles, **jamais un nom d'hôte externe**. En e2e, les conteneurs ne joignent que les doubles : réseau
`egress` interne et `HTTP_TEST_ALLOW_HOSTS` (voir « Tests e2e »).

## Horloge

Règle : aucun `sleep` réel dans les tests unitaires et d'intégration ; le temps avance par la `Clock` (VIII §49.3,
§50.1 ; `architecture.md` §5.2 ; ADR-0016).

- Le code reçoit une `Clock` (`app/core/clock.py`) ; il ne lit jamais `datetime.now()` ni `time.time()`.
- `tests/fakes/clock.py` :
  - `ManualClock` : l'instant n'avance que par `advance()` ; son `sleep()` avance le temps sans attendre ;
  - `SteppedClock` : son `sleep()` attend que le test avance le temps jusqu'à l'échéance, pour piloter une boucle
    permanente tour par tour (heartbeat, watchdog).
- Les tests de niveau processus et e2e peuvent attendre, mais toujours avec un délai borné (VIII §49.3).

## Marqueurs `spec` et volets

Règle : VIII §50.3 ; format des plans de sprint : `architecture.md` P-11.

- Chaque test d'un identifiant du catalogue porte `@pytest.mark.spec("T-DB-07")`. Un test peut en porter plusieurs,
  un identifiant peut être couvert par plusieurs tests. Côté vitest, un tag `[T-FE-01]` dans le nom du test.
- Identifiant couvert en plusieurs sprints : le plan le vise avec ses volets (`T-DB-13 [pragma, check]`), le test
  déclare le sien (`@pytest.mark.spec("T-DB-13:pragma")`). Un marqueur sans volet couvre l'identifiant entier.
- `--strict-markers` refuse un marqueur non déclaré ; `scripts/check-test-catalog.py` refuse un identifiant inconnu,
  mal formé ou de niveau M (voir « Rapport de traçabilité »).

## Traiter un échec d'audit

Politique : VIII §49.4 ; mise en œuvre : « Audit et exceptions » ci-dessus. Quand l'étape 3 échoue :

1. Lire le rapport dans le résumé du job `3 · Audit` : paquet, identifiant, sévérité.
2. **Corriger d'abord** : mettre à jour la dépendance, par un commit dédié (VIII §46.2).
   - Backend : `uv add --bounds exact <paquet>==<version corrigée>` (ou `uv lock --upgrade-package <paquet>` pour une
     dépendance indirecte), puis tests.
   - Frontend : dans `frontend/`, `npm install --save-exact <paquet>@<version corrigée>` avec npm 11.19.0, puis
     lint, `typecheck` et vitest.
3. **Sinon, exception datée** dans `.audit-exceptions.yaml`, seulement si la vulnérabilité n'est pas exploitable dans
   ce produit ou si aucun correctif n'existe : `id`, `package`, `justification`, `expires` à 90 jours au plus. Elle se
   relit à son expiration : une exception expirée fait échouer l'étape.
4. Rejouer l'étape en local : voir la commande de l'action `.github/actions/audit` (pip-audit par `uvx`,
   `npm audit --package-lock-only --json`, puis `scripts/check-audit.py`).

## Enregistrer des fixtures LLM

À venir avec la couche LLM (Sprint 6) : `scripts/record-llm-fixtures.py`, lancé à la main contre un vrai gateway,
jamais en CI (VIII §50.4).
