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
- aucune option de durcissement relâchée ; les doubles sont durcis comme les services.

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
| `tests/e2e/test_caddy.py` | T-SEC-06 (le volet « corps > 1 Mo refusé » est en `xfail` strict : voir la PR de T1.10) |
| `tests/e2e/test_read_only.py` | T-SEC-09 [base] : Python, uvicorn, Alembic, sans restic |
| `tests/e2e/test_doubles.py` | doubles branchés (VIII §47.2) |
| `tests/e2e/test_migrate_failure.py` | T-RES-10, dans le projet jetable `radar-dev-e2e-migrate-failure`, supprimé à la fin |

Les attentes sont bornées (60 s) ; aucun test e2e n'attend sans borne (VIII §49.3).
