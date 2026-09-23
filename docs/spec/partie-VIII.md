# Partie VIII — Livraison

> **Partie VIII — Livraison.** Version durcie issue de la revue §46–§52.
> Dernière révision : 2026-09-23. Prend les Parties I, II, III, IV, V-A, V-B, VI et VII durcies comme acquis.

**Nature de cette partie : une agrégation.** Les tests, étapes CI et critères de production fléchés par les Parties I à VII sont rassemblés ici, rattachés à un identifiant et organisés par domaine. Les doublons sont réconciliés (§ « Réconciliations ») et seul ce qui manquait est durci à neuf.

**Déjà tranché ailleurs, non repris ici** :
- topologie, images, réseaux, ordre de démarrage et procédure de déploiement (VII §36) ;
- Caddyfile (VII §37) ;
- mécanisme de backup et de test de restauration (VII §38) ;
- métriques, seuils et table des conditions (VII §39) ;
- sémantique de `/health` (VII §40) ;
- check-list des mesures M1–M10 et cibles de performance (VII §45) ;
- calibration `cluster-calibrate` (V-B §28.14) ;
- scénarios de résilience (II §9.5, V-A §26.3).

---

## Décisions tranchées dans cette revue (Partie VIII)

1. **§47 et §48 sont réécrits, pas retouchés.** Le plan V0.3 décrivait l'architecture V0.3 : collector Anthropic, `classify_article`, dédup et clustering dans un même sprint, Caddy au Sprint 11, purge absente.
2. **Numérotation conservée, de 1 à 11**, plus un **Sprint 0** qui correspond à la mission de cadrage (Partie IX §57), sans code applicatif. Le Sprint 11 reste le sprint Production, cité par la Partie VII.
3. **Caddy dès le Sprint 1**, en développement (`DASHBOARD_URL=https://localhost`, autorité interne de Caddy). L'auth, les en-têtes et le service du frontend sont testés dès le départ, jamais découverts au Sprint 11.
4. **Le Compose est conforme à VII §36.5 dès le Sprint 1** : réseaux, utilisateur non-root, `cap_drop`, `read_only`. La racine en lecture seule est donc validée en continu ; le Sprint 11 ne fait que confirmer le cas de restic.
5. **La supervision du worker arrive au Sprint 1** : heartbeat, fail-fast des tâches permanentes, watchdog. `/health` en dépend dès sa première version.
6. **§48 devient une liste de contraintes de dépendance.** La liste linéaire de 29 étapes, qui doublonnait les sprints, est supprimée.
7. **Horloge injectable obligatoire** : une abstraction `Clock` unique. Aucun `datetime.now()`, `time.time()`, `CURRENT_TIMESTAMP` ou `datetime('now')` dans le code métier ou les requêtes : l'instant est toujours passé par l'application. Sans cette règle, les TTL, warm-ups, rétentions, heartbeats et digests ne sont pas testables.
8. **Réseau bloqué techniquement dans les tests** : seules les connexions locales vers les doubles de test sont autorisées. « Aucun test n'appelle un vrai provider » devient vérifiable, pas seulement déclaratif.
9. **Identifiants de test** (`T-<DOMAINE>-nn`) pour chaque entrée du catalogue §50.5, portés par un marqueur pytest `spec`. La CI vérifie que chaque identifiant automatisé a au moins un test (identifiants des sprints clos ; ceux du sprint en cours sont signalés sans bloquer ; tous au Sprint 11 : §50.3), et que chaque marqueur renvoie à un identifiant existant.
10. **Pas de seuil de couverture bloquant.** La couverture est mesurée et affichée ; c'est la **traçabilité du catalogue** qui bloque.
11. **CI en six étapes ordonnées et bloquantes** : statique → configuration → audit → tests → build → e2e Compose (§49.2).
12. **e2e Compose sur `main` et en nightly**, pas à chaque push de branche. Les étapes 1 à 5 tournent à chaque push.
13. **Audit de dépendances bloquant sur `high` et `critical`**, avec un fichier d'exceptions **datées**. Une exception expirée fait échouer la CI. Un workflow hebdomadaire rejoue l'audit ; la reconstruction mensuelle des images (VII §43.2) passe par le même workflow planifié.
14. **Déploiement V1 manuel, verrouillé par la CI** : `scripts/deploy.sh` refuse de déployer un sha dont la CI (e2e compris) n'est pas verte, puis exécute la séquence VII §36.9. Aucun contournement en V1 ; un rollback redéploie un tag précédent, déjà vert.
15. **Fixtures de prompts précisées.**
    - Un snapshot du prompt construit par `PROMPT_VERSION` : modifier un template sans changer la version fait échouer la CI.
    - Le parsing est testé sur des **sorties réelles enregistrées** une fois par `scripts/record-llm-fixtures`, lancé à la main contre un vrai gateway et **jamais en CI**.
16. **Tests frontend limités en V1** : vitest et testing-library sur quelques composants critiques, plus la règle lint. Pas de test navigateur (Playwright) en V1.
17. **Six domaines de tests ajoutés au catalogue**, qui n'avaient jamais été fléchés vers VIII : base et migrations (III), étages purs du pipeline (IV), client HTTP (IV), purge et rétention (II §8.5, III §13), frontend (VI), démarrage et configuration.
18. **Pré-production obligatoire d'au moins 14 jours** sur le VPS cible, avec les sources réelles, avant la décision de mise en production. C'est la durée du warm-up de l'émergence (`emerging.warmup`) ; elle couvre aussi la calibration et les mesures sur données réelles.
19. **L'instance de pré-production est l'instance de production** : sa base est conservée à la bascule, ce qui préserve `trends_since` et l'historique. Une remise à zéro reste permise si la calibration change fortement les seuils, décision consignée dans `docs/go-live.md`.
20. **Tests de charge jamais sur le volume de production** : les profils synthétiques (VII §45.3) tournent dans un projet Compose distinct (`-p radar-load`) avec son propre volume, sur le même VPS.
21. **Un gateway LLM n'est pas requis pour la mise en production.** Le produit fonctionne à 0 € sans LLM (Partie I) ; les résumés restent alors en repli. Si un gateway est configuré, la mesure M6 doit être validée.
22. **La spec vit dans le dépôt** sous `docs/spec/`, une partie par fichier. `SPEC.md` à la racine devient l'index : sommaire, règles de lecture et **lien** vers les décisions verrouillées (Partie IX §53), sans en recopier la liste. La CI extrait les identifiants de test directement de `docs/spec/partie-VIII.md`, source unique.
23. **Liste d'hôtes autorisés réservée aux tests** : les doubles de test tournent sur des adresses privées que la garde anti-SSRF refuse. Une liste d'hôtes autorisés (`HTTP_TEST_ALLOW_HOSTS`) n'est lue que si `APP_ENV=test` ; le worker **refuse de démarrer** si elle est renseignée avec `APP_ENV=production`. Voir Partie IV §21.1.
24. **Procédure de restauration outillée** (`scripts/restore.sh`) pour être testable en e2e. Elle applique le contrat VII §38.5, suppression des `-wal` / `-shm` comprise.
25. **Check-list de mise en production consignée dans `docs/go-live.md`**, avec une preuve par ligne, le sha et la date de décision.

---

## Réconciliations

| Source du conflit | Avant | Tranché |
|---|---|---|
| V0.3 §46 | `Dockerfile` à la racine | `docker/backend.Dockerfile` et `docker/caddy.Dockerfile` (VII §36.5) |
| V0.3 §46 | `config/` = `sources.yaml`, `topics.yaml` | quatre fichiers : `sources.yaml`, `topics.yaml`, `entities.yaml`, `pipeline.yaml` (III, IV) |
| V0.3 §46 | `app/processing/` | `app/pipeline/` (runner + étages purs, IV §14) ; ajout de `app/ops/`, `app/cli/`, `app/backup/`, `app/emerging/`, `app/llm/prompts/` |
| V0.3 §46 | `SPEC.md` monolithique à la racine | `SPEC.md` index + `docs/spec/` (décision 22) |
| V0.3 §47 Sprint 2 | collector « Anthropic/Claude Code » ; Reddit et YouTube avec credentials | releases GitHub `anthropics/claude-code` + collector `webpage` ; Reddit et YouTube en RSS sans credentials (IV) |
| V0.3 §47 Sprint 4 | dédup + relevance + embeddings + clustering | dédup exacte et relevance dans le runner (Sprint 2) ; embeddings et clustering au Sprint 4 |
| V0.3 §47 Sprint 7 | classification · topics · entities · summaries · topic discovery | `enrich_article` (un appel) + `resolve_event` au Sprint 7 ; `discover_topics` au Sprint 8, avec les candidats (V-A) |
| V0.3 §47 Sprint 8 | « novelty » d'Event | `Event.novelty` supprimé ; `novelty` n'existe que sur `Signal` (V-B) |
| V0.3 §47 Sprint 11 | Caddy, HTTPS et Docker prod au Sprint 11 | Caddy et Compose durci dès le Sprint 1 ; le Sprint 11 livre les ops (décisions 3 et 4) |
| V0.3 §47 | purge absente | purge et passe `processed_at` au Sprint 7 |
| V0.3 §48 | 29 étapes linéaires | contraintes de dépendance (décision 6) |
| V0.3 §49 | `push → ruff → mypy → pytest → integration → Docker build` | six étapes, dont configuration, audit et e2e (§49.2) |
| V0.3 §50 | liste de catégories | catalogue identifié par domaine (§50.5) |
| V0.3 §52 | « Reddit/YouTube (si credentials) » | sans objet : aucune credential requise en V1 (IV §22) |
| V0.3 §52 · Partie I §4.3 | critères de résilience cités, non outillés | rattachés aux identifiants `T-RES-*` et aux mesures M7, M10 (§50.6) |
| Partie II §9.4 | restauration « testée mensuellement » | `restore-test` automatisé mensuel (VII §38.4) + exercice manuel avant production |

---

## 46. Repository

### 46.1 Arborescence

Contractuelle sur les dossiers de premier niveau et les fichiers nommés. L'organisation interne des modules est laissée à l'implémenteur, dans le respect des frontières de la spec (collectors sans accès base, app sans exécution de jobs…).

```
ai-tech-radar/
├── SPEC.md                    # index de la spec (décision 22, Partie IX §55.2)
├── CLAUDE.md                  # règles permanentes de Claude Code (Partie IX §55.3)
├── README.md
├── pyproject.toml · uv.lock   # backend, versions verrouillées
├── alembic.ini
├── docker-compose.yml         # VII §36.5
├── docker-compose.test.yml    # surcharge e2e : doubles de test, APP_ENV=test
├── .env.example               # VII §36.7
├── .gitignore · .dockerignore # .env exclu des deux
├── .audit-exceptions.yaml     # exceptions d'audit datées (§49.4)
├── .github/workflows/
│   ├── ci.yml                 # push, PR, main (§49.1)
│   └── scheduled.yml          # nightly, audit hebdomadaire, rebuild mensuel
├── app/
│   ├── main.py                # FastAPI
│   ├── worker.py              # python -m app.worker
│   ├── cli/                   # validate-config, cluster-calibrate, recount-events,
│   │                          # send-test-alert, backup-now, restore-test, health, vacuum
│   ├── core/                  # configuration typée (SecretStr), Clock, logging, redaction
│   ├── db/                    # moteurs, read_session / write_session, UTCDateTime, prérequis
│   ├── models/  schemas/
│   ├── api/                   # routes, anti-CSRF
│   ├── collectors/            # un module par type, registre (canal déclaré)
│   ├── pipeline/              # runner + étages purs (IV §14)
│   ├── http/                  # HttpClient partagé, anti-SSRF, robots.txt
│   ├── embeddings/  clustering/  trends/  emerging/
│   ├── jobs/                  # AIJob : claim, gardes, handlers
│   ├── llm/                   # LLMClient, erreurs typées, disjoncteur, budget
│   │   └── prompts/           # un module par tâche, PROMPT_VERSION
│   ├── alerts/  purge/  backup/
│   └── ops/                   # health.py, ops.tick, conditions, heartbeat, watchdog
├── config/
│   ├── sources.yaml · topics.yaml · entities.yaml · pipeline.yaml
├── migrations/                # Alembic, render_as_batch
├── frontend/
│   ├── package.json · package-lock.json
│   └── src/ …                 # React · TypeScript · Vite
├── docker/
│   ├── backend.Dockerfile     # modèle d'embeddings intégré au build, restic statique
│   ├── caddy.Dockerfile       # multi-stage : build Vite → /srv
│   └── Caddyfile              # VII §37.3
├── scripts/
│   ├── deploy.sh              # §49.5
│   ├── restore.sh             # VII §38.5 outillé (décision 24)
│   ├── check-test-catalog.py  # traçabilité (§50.3)
│   ├── record-llm-fixtures.py # manuel, jamais en CI (§50.4)
│   ├── synthetic-dataset.py   # profils réaliste et cible (VII §45.3)
│   ├── load.py                # script de charge
│   └── radar-dev              # environnement local de développement (E22, ADR-0021)
├── tests/                     # §50.2
└── docs/                      # arbre détaillé : Partie IX §55.1
    ├── spec/                  # partie-I.md … partie-IV.md, partie-V-A.md, partie-V-B.md,
    │                          # partie-VI.md … partie-IX.md
    ├── adr/                   # README.md (index), _template.md, NNNN-slug.md
    ├── sprints/               # sprint-00-cadrage.md, sprint-NN.md (plan + bilan)
    ├── architecture.md · database.md · collectors.md · llm-gateway.md · trends.md
    ├── deployment.md · monitoring.md · backup-restore.md · measurements.md
    └── runbook.md · testing.md · go-live.md
```

**`scripts/radar-dev`** (E22, ADR-0021) : seul point d'entrée de Docker sur le poste de développement.
- **Sous-commandes fixes** : `up`, `down`, `reset`, `ps`, `logs <service>`, `test`, `e2e`, `health`.
- **Aucun argument libre n'est transmis à `docker`** : le seul argument admis, un nom de service, est validé contre une liste fermée. Une sous-commande ou un argument hors liste renvoie le code `2` sans rien exécuter (contrat de la Partie IX §56.3).
- Projet Compose de développement dédié, jamais `radar` ni `radar-load`.
- Outil de développement seulement : ni la CI ni le VPS ne l'utilisent.

### 46.2 Règles

- **Versions épinglées partout** : `uv.lock` et `package-lock.json` commités ; images de base et images tierces (Caddy, gateway) à un tag précis, jamais `latest`. Mise à jour = commit dédié, passé en CI.
- **Aucun secret dans le dépôt** : `.env` dans `.gitignore` et `.dockerignore` ; aucun `COPY .env` ; analyse de secrets en CI (§49.2). Les fixtures ne contiennent que des secrets **factices**, reconnaissables (`FAKE-…`).
- **`config/` est versionné** : c'est la configuration fonctionnelle. Les secrets et les paramètres de déploiement restent dans `.env` (VII §36.7).
- **Branches** : `main` protégée (étapes 1 à 5 de la CI requises avant fusion) ; travail sur branche et PR, même en solo, pour que la CI tourne avant `main`.
- **`mypy` en mode `strict` sur `app/`** ; `ruff` en lint et en format.
- **Frontend** : aucun script ni `<style>` en ligne, aucune bibliothèque de CSS-in-JS à l'exécution (CSP, VII §37.3), sauf ADR.

---

## 47. Sprints

### 47.1 Principes

- **Le système est exécutable à la fin de chaque sprint** : `docker compose up -d` démarre, `/health` répond, la CI est verte.
- **Critères d'acceptation = identifiants du catalogue §50.5 verts + démonstration** du scénario du sprint sur le Compose local.
- **Un sprint ne démarre pas tant que le précédent ne satisfait pas la DoD de sprint** (§51.2).
- **Plan et bilan** : le plan détaillé de chaque sprint est rédigé dans `docs/sprints/sprint-NN.md` et **validé avant l'implémentation** ; le bilan (écarts à la spec, dette tracée, identifiants couverts) y est ajouté en fin de sprint (Partie IX §57.8).
- **Une fonction [core] ne dépend jamais d'un sprint AI** : tout ce qui est livré avant le Sprint 6 fonctionne sans LLM, et continue de fonctionner sans lui ensuite.
- **Migrations par sprint** : chaque sprint ajoute ses tables et colonnes par migration Alembic. Le schéma cible complet est proposé au Sprint 0, mais pas créé d'un bloc.

### 47.2 Plan

#### Sprint 0 — Cadrage *(sans code applicatif)*

Description canonique, contenu, livrables et acceptation : **Partie IX §57**.

#### Sprint 1 — Foundation

**Contenu** :
- **Base** : FastAPI (un processus uvicorn), SQLAlchemy 2.x async + aiosqlite, deux fabriques de sessions (`BEGIN IMMEDIATE` pour l'écriture), PRAGMA par connexion dont `journal_size_limit`, `UTCDateTime`, `Clock`.
- **Migrations** : Alembic avec `render_as_batch`, service one-shot `migrate`, vérification des prérequis et de la révision au démarrage des deux processus.
- **Worker minimal** : heartbeat (30 s), supervision fail-fast, watchdog, séquence de boot, SIGTERM.
- **Santé** : `/health` public (`ok` / `down`) et `/api/health` minimal (composants `database`, `worker`), calculés par `app/ops/health.py`.
- **Configuration** : typée, secrets en `SecretStr` ; `validate-config` sur les quatre fichiers (schémas initiaux) ; refus de démarrer si `HTTP_CONTACT` ou `DASHBOARD_URL` est invalide.
- **Logs** : structlog JSON, nettoyage des secrets aux trois niveaux.
- **Exposition** : Caddy (TLS interne, basic_auth, `/health` public, en-têtes de sécurité, SPA vide servie) et Compose conforme VII §36.5.
- **Tests et CI** : les six étapes opérationnelles, doubles de test vides mais branchés, blocage réseau, traçabilité du catalogue.

**Acceptation** :
- `docker compose up -d` en une commande : `migrate` se termine, puis `app`, `worker` et `caddy` sont `running` ;
- `https://localhost/health` répond `{"status":"ok"}` sans identifiants, et `/api/health` demande une authentification ;
- WAL actif ; `app` et `worker` refusent de démarrer sur un schéma qui n'est pas à `head` ;
- CI verte, e2e compris.
- **Tests** : T-DB-01 à 08 · T-DB-13 (PRAGMA de `migrate` et `foreign_key_check` ; complété au Sprint 3) · T-CFG-01, 02, 05, 07, 10 · T-OPS-01 à 03, 07 à 11 · T-SEC-01 à 03, 05, 06, 08 et 09 (sans restic) · T-RES-10.

#### Sprint 2 — Collecte & pipeline déterministe

**Contenu** :
- **Collecte** : `HttpClient` partagé (limiteur par hôte, retry et backoff, `Retry-After`, quota, anti-SSRF, `robots.txt`, User-Agent) ; interface `Collector` par pages et registre (canal déclaré par type) ; collectors `rss`, `github`, `hackernews`, `reddit`, `youtube`, `webpage`.
- **Runner** : normalisation, contrôle d'âge, canonicalisation, dédup exacte, relevance filter, extraction ciblée, liaisons keyword, résumé de repli, écriture d'une transaction par page, checkpoint, `CollectorRun`.
- **Pilotage** : disjoncteur par source ; scheduler (jitter de démarrage, coalescence, sauts de run) ; vérification des credentials par type ; création des `enrich_article`, qui restent `pending` jusqu'au Sprint 5 : la table `AIJob` est introduite par migration **dès ce sprint** ; la file et son exécution arrivent au Sprint 5.
- **Configuration** : validation complète de `sources.yaml`, `topics.yaml`, `entities.yaml` et des sections de `pipeline.yaml` du périmètre IV.
- **Doubles** : faux serveur de sources avec les fixtures par type.

**Acceptation** :
- avec le `config/` de démonstration, le worker collecte les six types contre le faux serveur ;
- un rejeu complet ne crée aucun doublon ;
- l'invariant de compteurs tient sur chaque run ;
- une source en panne n'arrête pas les autres.
- **Tests** : T-PIPE-* · T-HTTP-* · T-COL-* · T-CFG-02 à 06, 09 (T-CFG-04 sur les sections de `pipeline.yaml` du périmètre IV ; chaque sprint suivant ajoute et teste ses sections) · T-DB-12 (`Article.status`) · T-OPS-16 · T-RES-04.

#### Sprint 3 — Feed

**Contenu** : API de lecture (stories, à ce stade toutes des articles isolés) ; pagination keyset ; filtres ; index FTS5 `article_fts` et ses triggers ; recherche `q` ; frontend React/TS/Vite servi par Caddy (Feed, sources, dates, badge de hotness, indicateur repli / enrichi) ; vitest et règle lint.

**Acceptation** :
- le Feed affiche les articles collectés ;
- la recherche accepte toute saisie, y compris la syntaxe FTS5 ;
- aucun `offset` dans l'API ;
- le build frontend ne contient aucun script en ligne.
- **Tests** : T-DB-11 · T-API-05 à 07 · T-FE-01 à 05, 07 · complément : T-DB-13 (reconstruction d'`article` et triggers d'`article_fts`).

#### Sprint 4 — Embeddings & clustering

**Contenu** :
- **Embeddings** : file dérivée, calcul hors event-loop, lignes en échec, matrice de fenêtre reconstruite au démarrage.
- **Clustering** : Event clustering V-B §28 (deux voies de déclenchement, candidats, fusion, `duplicate` rétroactif même source, représentant, compteurs recalculés, importance, archivage, mode dégradé) ; hotness dans l'API et le Feed (stories = Events + articles isolés).
- **Outillage** : `cluster-calibrate` et `recount-events` ; jeu de données synthétique et script de charge.

**Acceptation** :
- un Event multi-sources forme une seule story ;
- moteur d'embeddings arrêté, le clustering continue par URL et entités ;
- premières mesures M1 et M2 au profil réaliste, consignées **à titre indicatif** dans `docs/measurements.md`.
- **Tests** : T-EMB-* · T-CLU-* (sauf la partie `resolve_event` de T-CLU-08 et T-CLU-12) · T-API-01 (Feed) · T-SEC-10.

#### Sprint 5 — File de jobs

**Contenu** : `AIJob` (registre fermé des `job_type`, claim atomique et ordre de claim, sémaphore, gardes d'éligibilité et `skipped`, TTL, backoff et tentatives, requalification au boot), transitions de l'app sur `dead_letter`, métriques de backlog. Les handlers restent des stubs testables.

**Acceptation** :
- redémarrage du worker pendant un job : le job est requalifié et rejoué, avec un résultat unique ;
- `job_type` inconnu → `failed`, le worker continue.
- **Tests** : T-JOB-* (T-JOB-04 hors `candidate_decided`, complété au Sprint 8) · T-DB-09 · T-DB-12 (`AIJob.status`).

#### Sprint 6 — LLM Gateway & LLMClient

**Contenu** :
- **Client** : `LLMClient` (interface typée, parsing et validation, `TolerantList` / `SoftStr`, erreurs typées, aucun retry interne) ; disjoncteur LLM à trois états ; budget quotidien et réserve de l'app ; gateway non configuré ; observabilité (§25.6).
- **Doubles** : faux gateway OpenAI-compatible.
- **Gateway** : choix documenté dans `docs/llm-gateway.md`, ADR, profil Compose `gateway` si auto-hébergé ; première mesure M6 contre le gateway retenu.

**Acceptation** :
- les huit scénarios de V-A §26.3 passent contre le faux gateway ;
- `LLM_BASE_URL` absent → produit fonctionnel ; dans `/api/health`, le composant `llm_gateway` est en statut `disabled`, raison `not_configured` (VII §40.3).
- **Tests** : T-LLM-01 à 17, 19, 20 · T-RES-01 (partie file de jobs).

#### Sprint 7 — Intelligence & purge

**Contenu** :
- **Tâches LLM** : `enrich_article` (topics, entités et résumé en un appel, canonicalisation des entités) et `resolve_event` (titre et description, déclenchement par marqueur) ; création d'`enrich_article` au changement de représentant.
- **Actions de l'app** : régénération (202, `already_active`, `jobs_in_progress`), relance et abandon d'un `dead_letter` ; middleware anti-CSRF (premier endpoint d'écriture).
- **Purge** : étage de purge et passe `processed_at`, rétention III §13.
- **Prompts** : fixtures par `PROMPT_VERSION`, avec les sorties de référence enregistrées.

**Acceptation** :
- gateway coupé puis rétabli : reprise sans doublon, les plus récents d'abord ;
- contenu purgé selon la table III §13, jamais en présence d'un `dead_letter` ;
- API complète avec le gateway éteint.
- **Tests** : T-LLM-18 (hors volet `discover_topics`, complété au Sprint 8) · T-JOB-06 · T-CLU-08 et 12 · T-PRG-* (T-PRG-06 complété au Sprint 8, volet `AlertLog` de T-PRG-05 au Sprint 10) · T-API-08 à 10, 14 · T-SEC-04 · T-RES-01 · T-RES-02 (hors alertes).

#### Sprint 8 — Trends & émergence

**Contenu** : Trend Engine (Signal horaire, formules, cold start, agrégation parent, catégories) ; moteur d'émergence (termes, critères, warm-up, évolution significative, candidats) ; `discover_topics` ; décisions `follow` / `ignore` / `mute` / `create_topic` et cycle « Create topic » avec backfill ; job analytique horaire.

**Acceptation** :
- sur le jeu synthétique, avec horloge avancée au-delà du warm-up, un terme multi-histoires devient candidat ;
- un « Create topic » produit des liaisons sur les nouveaux articles et un Signal à l'heure suivante ;
- première mesure M5, à titre indicatif.
- **Tests** : T-TRD-* · T-EMG-* · compléments : T-PRG-06, T-LLM-18 (volet `discover_topics`), T-JOB-04 (`candidate_decided`).

#### Sprint 9 — Dashboard

**Contenu** : Overview à six sections ; vues Topic et Event ; Event fusionné et redirection ; lu / non lu ; préférences `follow` / `mute` et sourdine héritée ; related topics ; `Setting` (registre en code) ; bandeau d'état (`/api/status`) ; page des jobs en échec.

**Acceptation** :
- une story n'apparaît qu'une fois dans l'Overview ;
- la sourdine donne le même résultat côté app et côté worker ;
- produit utilisable de bout en bout gateway éteint, hors alertes.
- **Tests** : T-API-01 à 04, 11 à 13 · T-FE-06 · T-CFG-08.

#### Sprint 10 — Alertes

**Contenu** : canaux email et Telegram ; séquence d'envoi au plus une fois (`sending`) ; `important_event` et `emerging_topic` ; fréquence (mode, heures calmes, plafond, fuseau) ; digests déclenchés par le tick ; routage par type ; `send-test-alert` ; historique des alertes dans le dashboard.

**Acceptation** :
- une même alerte part sur les deux canaux, jamais deux fois par canal ;
- digest quotidien reçu sur le canal configuré ;
- canal non configuré → worker démarré, canal désactivé.
- **Tests** : T-ALR-* · T-DB-10 · T-RES-02 (complet) · compléments : T-DB-12 (`AlertLog.status`), T-PRG-05 (volet `AlertLog`).

#### Sprint 11 — Production

**Contenu** :
- **Monitoring** : `ops.tick` et instantané `ops_metrics` ; table des conditions §39.5 ; alertes `system` par épisode ; `/api/health` complet ; statut `degraded` sur `/health`.
- **Backup** : `VACUUM INTO` + restic, `backup-now`, `restore-test` automatisé, `scripts/restore.sh`.
- **Réseau et conteneurs** : validation finale de la segmentation réseau et de la racine en lecture seule avec restic.
- **Déploiement** : `scripts/deploy.sh`.
- **Documentation d'exploitation** : finalisation de `deployment.md`, `monitoring.md`, `backup-restore.md`, `runbook.md` et `go-live.md`, créés au fil des sprints (Partie IX §55.4).
- **Mise en place de la pré-production** (§47.4).

**Acceptation** :
- tous les tests automatisés du catalogue sont verts ;
- la pré-production démarre sur le VPS cible, déployée par `scripts/deploy.sh`.
- **Tests** : T-OPS-* (dont T-OPS-17) · T-BKP-* (dont T-BKP-10 à 12) · T-SEC-* · T-RES-* · T-CFG-04 (complet).

### 47.3 Ce qui est validé au Sprint 11

- **Racine en lecture seule** d'`app` et `worker` avec restic (cache dans `/tmp`, préparation dans `/data/backup/`) : T-SEC-09 complet. onnxruntime et lingua sont validés depuis le Sprint 1.
- **Segmentation réseau** et **politique Compose** sur la configuration de production : T-SEC-07, T-SEC-08.
- **Table §39.5** : chaque condition met son composant en `degraded` et émet une alerte `system` (T-OPS-06, T-OPS-12).
- **Résilience** : tous les `T-RES-*` automatisés en e2e.
- **`mem_limit`** : posés après la mesure M1 sur le VPS cible (pic × 1,5), pendant la pré-production.

### 47.4 Pré-production

Entre la fin du Sprint 11 et la décision de mise en production, **au moins 14 jours** (décisions 18 à 20).

| Étape | Moment | Preuve |
|---|---|---|
| Déploiement sur le VPS cible, `config/` réel, sources réelles | J0 | `docs/go-live.md` |
| Durcissement de l'hôte (VII §43.1) | J0 | `docs/go-live.md` |
| Monitoring externe configuré et testé (arrêt d'`app`) | J0 à J1 | `docs/go-live.md` |
| Canal d'alerte + `send-test-alert` ; backup + `restore-test` | J0 à J1 | `docs/go-live.md` |
| Calibration `cluster-calibrate` (une fenêtre de 72 h de données au moins) et seuils committés dans `pipeline.yaml` | J3 à J7 | `docs/measurements.md` |
| Mesures M1 à M10 : profils synthétiques dans le projet `radar-load`, M3, M4 et M9 aussi sur la charge réelle | J3 à J14 | `docs/measurements.md` |
| Exercice complet de restauration sur machine neuve (M7) | avant J14 | `docs/backup-restore.md` |
| Reboot réel du VPS (M10) | avant J14 | `docs/measurements.md` |
| Fin du warm-up de l'émergence ; job analytique sans erreur | J14 | `/api/health` |
| Revue de la check-list §52, décision | ≥ J14 | `docs/go-live.md` |

---

## 48. Ordre d'implémentation — contraintes de dépendance

L'ordre des sprints (§47) est l'ordre d'implémentation. À l'intérieur d'un sprint, et pour tout réordonnancement, les contraintes suivantes sont **impératives**.

| # | Contrainte | Raison |
|---|---|---|
| D1 | `Clock`, fabriques de sessions, `UTCDateTime` et nettoyage des secrets **avant tout code métier** | tout le reste en dépend ; les rétrofitter coûte une réécriture des tests |
| D2 | Heartbeat et vérification de révision **avant** `/health` | `/health` se calcule sur le heartbeat (II décision 8) |
| D3 | Service `migrate` **avant** toute table métier | aucun processus applicatif ne migre (III §10.5) |
| D4 | Blocage réseau des tests et doubles de test **avant** le premier collector | aucun test ne doit jamais appeler Internet |
| D5 | `HttpClient` partagé (garde anti-SSRF comprise) **avant** tout collector | aucun collector n'a son propre client |
| D6 | Runner et écriture par page **avant** tout collector autre que `rss` | les collectors ne touchent jamais la base (IV décision 1) |
| D7 | Liaisons `keyword` et `entities.yaml` **avant** le clustering | le critère entités ne compte que les liaisons `keyword` (V-A → V-B) |
| D8 | Clustering **avant** l'exécution des `enrich_article` | la garde `event_member` suppose des articles regroupés ; invariant `embedding_wait + tick < enrich_delay` |
| D9 | File `AIJob` et gardes **avant** `LLMClient` ; `LLMClient` et disjoncteur **avant** toute tâche LLM | une tâche ne s'exécute jamais hors de la file |
| D10 | Tâches LLM **avant** la purge ; passe `processed_at` **avant** la purge du contenu `ready` | pas de purge avant l'embedding et l'enrichissement (III §12.2) |
| D11 | Trend Engine **avant** l'émergence ; `trends_since` posé dès la première insertion `ready` (Sprint 2) | le warm-up et le lu / non lu en dépendent |
| D12 | Registre des `Setting` et `UserPreference` **avant** les alertes | les alertes lisent la sourdine et les seuils |
| D13 | Séquence d'envoi des alertes (Sprint 10) **avant** les alertes `system` (Sprint 11) | même séquence T1 → envoi → T2 |
| D14 | `ops.tick` et conditions **avant** le statut `degraded` | l'app ne fait que lire `SystemState` |
| D15 | Backup et `restore-test` **avant** la pré-production | aucune donnée réelle sans backup |

---

## 49. CI/CD

### 49.1 Workflows

| Workflow | Déclencheur | Étapes |
|---|---|---|
| `ci.yml` | push sur toute branche, PR | 1 à 5 |
| `ci.yml` | push sur `main` | 1 à 6 |
| `scheduled.yml` — nightly | chaque nuit, sur `main` | 1 à 6 |
| `scheduled.yml` — hebdomadaire | chaque semaine | 3 (audit), sur les lockfiles de `main` |
| `scheduled.yml` — mensuel | le 1er du mois | 5 et 6 avec reconstruction sans cache et images de base rafraîchies (VII §43.2) |

Aucun workflow ne reçoit de secret de production. La CI n'a besoin d'aucun secret : les valeurs de `.env.example` et les secrets factices suffisent. Aucun workflow ne déploie.

### 49.2 Étapes — ordre et blocage

Chaque étape bloque les suivantes. Les travaux d'une même étape peuvent tourner en parallèle.

| # | Étape | Contenu | Bloquant |
|---|---|---|---|
| 1 | **Statique** | `ruff check` · `ruff format --check` · `mypy` (strict sur `app/`) · eslint (dont `react/no-danger` : interdiction de `dangerouslySetInnerHTML`) · `tsc --noEmit` · `uv lock --check` · `npm ci` · analyse de secrets de type gitleaks, **sur tout l'historique** · **traçabilité du catalogue** (`scripts/check-test-catalog.py`, §50.3) | oui |
| 2 | **Configuration** | `python -m app.cli validate-config` sur `config/`, invariant `clustering.embedding_wait + clustering.tick < llm.delay.enrich_article` compris · `docker compose config` avec `.env.example` · `caddy validate` sur `docker/Caddyfile`, variables de `.env.example` injectées · **politique Compose** (T-SEC-08) sur la sortie de `docker compose config` | oui |
| 3 | **Audit** | audit des dépendances backend (type `pip-audit`, à partir de `uv.lock`) et frontend (`npm audit --audit-level=high`), confronté à `.audit-exceptions.yaml` (§49.4) | oui, sur `high` et `critical` |
| 4 | **Tests** | pytest unitaire et intégration, réseau bloqué (§50.1), couverture mesurée et publiée dans le résumé du job · vitest | oui |
| 5 | **Build** | images `radar-backend:<sha>` et `radar-caddy:<sha>` ; vérifications : modèle d'embeddings présent dans l'image (**activée au Sprint 4**, avec les embeddings), utilisateur non-root, aucun `.env` dans les couches | oui |
| 6 | **e2e Compose** | `docker compose -f docker-compose.yml -f docker-compose.test.yml up` sur les images de l'étape 5, avec les doubles (faux gateway, faux serveur de sources, dépôt restic local) · tests `@pytest.mark.e2e` : `/health`, auth, en-têtes et logs Caddy, réseau, racine en lecture seule, backup et restauration, scénarios `T-RES-*` | oui |

`scripts/deploy.sh` exige que **l'étape 6** soit verte pour le sha déployé.

### 49.3 Règles

- **Aucun test n'appelle un vrai provider** : ni LLM, ni source, ni SMTP, ni Telegram, ni stockage distant. C'est imposé par le blocage réseau (§50.1) et par les doubles (§50.4).
- **Aucun `sleep` réel** dans les tests unitaires et d'intégration : le temps avance par la `Clock`. Les tests e2e peuvent attendre, avec des délais bornés et des réglages de `pipeline.yaml` raccourcis dans la surcharge de test.
- **Tests déterministes** : graines fixées pour le jitter et les jeux synthétiques. Un test instable est corrigé ou mis en quarantaine par un marqueur explicite, tracé dans une issue ; jamais relancé en boucle jusqu'au vert.
- **Durée** : les étapes 1 à 5 visent moins de 10 minutes. Au-delà, on optimise (cache uv, npm, couches Docker) avant de déplacer un test en nightly.

### 49.4 Politique d'audit

- **Bloquant** : toute vulnérabilité `high` ou `critical` sans exception valide.
- **Exception** : une entrée dans `.audit-exceptions.yaml`, avec l'identifiant de la vulnérabilité, le paquet, la justification (non exploitable dans ce produit, correctif indisponible) et une **date d'expiration de 90 jours au plus**. Une exception expirée fait échouer la CI.
- **`moderate` et en dessous** : signalé dans le résumé du job, non bloquant.
- L'audit hebdomadaire échoue de la même façon. Un échec sur `main` sans changement de code signale une vulnérabilité apparue, à traiter par une mise à jour ou une exception.

### 49.5 Déploiement V1

**Manuel, verrouillé par la CI.** `scripts/deploy.sh [<sha>]`, exécuté sur le VPS par l'utilisateur de déploiement :

1. vérifie que l'arbre de travail est propre et que le sha visé est sur `origin/main` ;
2. interroge l'API GitHub : le workflow `ci.yml` de ce sha doit être **terminé et vert, étape 6 comprise**. Sinon, refus avec le lien vers le run ;
3. compare `migrations/versions/` entre le sha déployé et le sha visé : si une migration du sha déployé est **absente** du sha visé (rollback à travers une migration), **refus**, avec la liste de ces migrations, leur réversibilité et le renvoi au runbook (Partie IX §56.6-P2) ;
4. exécute la séquence VII §36.9 :
   - `git checkout <sha>` ;
   - `docker compose build`, tag = sha ;
   - `docker compose exec worker python -m app.cli backup-now` (avec vérification du succès), qui affiche le `snapshot_id` ;
   - `docker compose stop app worker` ;
   - `docker compose up -d` ;
   - attente de `/health = ok` (délai borné), puis `docker compose ps` ;
5. journalise le sha déployé, l'issue et le `snapshot_id` du backup dans `~/radar-deploy.log`.

- **Aucun contournement** en V1 : pas d'option `--force`.
- **Rollback** : `scripts/deploy.sh <sha précédent>` quand aucune migration ne sépare les deux sha ; ce sha est déjà vert, et le contrôle CI passe. Sinon, `deploy.sh` refuse (étape 3) et la procédure Partie IX §56.6-P2 s'applique : *downgrade* si les migrations sont réversibles, restauration par `scripts/restore.sh` du snapshot pris au déploiement sinon.
- **Jeton GitHub** : si le dépôt est privé, le contrôle utilise un jeton *fine-grained* en **lecture seule** (statuts et actions du seul dépôt). Il est stocké hors du `.env` applicatif, avec des droits `600`, et n'est **jamais transmis à un conteneur**. Si le dépôt est public, aucun jeton n'est nécessaire. Sa rotation suit Partie IX §56.6-P5.
- Le build a lieu sur le VPS (VII §36.9). Le modèle d'embeddings est téléchargé au build, jamais au runtime.

---

## 50. Tests

### 50.1 Principes

- **Horloge** : `app/core/clock.py` expose une `Clock` (`now()` UTC avec fuseau, `sleep()`, `monotonic()`). La production utilise `SystemClock` ; les tests, une horloge manuelle qu'ils avancent. APScheduler est piloté par des déclencheurs appelables directement dans les tests : on teste la fonction du tick, pas le passage réel du temps.
- **Temps en base** : aucune expression temporelle SQL (`CURRENT_TIMESTAMP`, `datetime('now')`) dans le code ni dans les requêtes, ni en valeur par défaut de colonne : l'instant est toujours fourni par la `Clock` (Partie III §10.6).
- **Réseau** : un bloqueur de sockets actif pour toute la session pytest (type `pytest-socket`), qui n'autorise que `127.0.0.1` / `::1` et les sockets Unix. Un test qui tente une connexion externe échoue. En e2e, les conteneurs n'atteignent que les doubles : la surcharge de test déclare `APP_ENV=test` et `HTTP_TEST_ALLOW_HOSTS` (décision 23).
- **Anti-SSRF en test** : l'accès des tests d'intégration aux doubles locaux passe par la liste de test injectée au `HttpClient`, jamais par un contournement de la garde. T-HTTP-08 vérifie que la garde refuse `127.0.0.1` en l'absence de cette liste.
- **SQLite réel** : les tests d'intégration utilisent un fichier SQLite temporaire en WAL (jamais `:memory:`, qui masque le WAL et la concurrence), migré par Alembic à `head`.
- **Pureté** : les étages purs du pipeline (IV §14.1) sont testés sans réseau ni base, par tables de cas.
- **Aucun secret réel** : secrets factices reconnaissables, réutilisés par les tests de nettoyage (T-SEC-01).

### 50.2 Niveaux et emplacement

| Niveau | Code | Emplacement | Exécution |
|---|---|---|---|
| Unitaire | U | `tests/unit/<domaine>/` | étape 4, à chaque push |
| Intégration (SQLite réel, doubles HTTP locaux, processus multiples si besoin) | I | `tests/integration/<domaine>/` | étape 4, à chaque push |
| e2e Compose (images construites) | E | `tests/e2e/` | étape 6, sur `main` et en nightly |
| Frontend (vitest) | F | `frontend/src/**/*.test.tsx` | étape 4 |
| Manuel sur le VPS cible | M | procédure dans `docs/`, preuve dans `docs/go-live.md` ou `docs/measurements.md` | pré-production (§47.4) |

Fixtures et doubles : `tests/fixtures/` (réponses HTTP par type, configurations invalides, sorties LLM enregistrées, petits jeux de données) et `tests/fakes/` (faux gateway, faux serveur de sources). Le mode d'emploi figure dans `docs/testing.md`.

### 50.3 Traçabilité du catalogue

- Chaque ligne du §50.5 porte un identifiant `T-<DOMAINE>-nn` et un niveau.
- **Source unique** : `scripts/check-test-catalog.py` extrait les identifiants de `docs/spec/partie-VIII.md`.
- **Marqueur** : un test couvre un identifiant par `@pytest.mark.spec("T-CLU-03")`, ou par un tag `[T-FE-01]` dans le nom d'un test vitest. Un identifiant peut être couvert par plusieurs tests ; un test peut en couvrir plusieurs.
- **Contrôles bloquants** :
  - tout identifiant de niveau U, I, E ou F **d'un sprint clos** a au moins un test. La liste de ces identifiants est lue dans les `docs/sprints/sprint-NN.md` de ces sprints ; le contrôle devient **complet** (tous les identifiants du catalogue) au Sprint 11, critère §52 A2 ;
  - les identifiants du **sprint en cours** sans test figurent dans le rapport **sans bloquer** ; ils deviennent bloquants quand le `sprint-NN.md` passe à `Statut : clos`, dans la PR de bilan du sprint. Sans cette règle, chaque PR du sprint échouerait tant que le dernier test n'existe pas, alors que les étapes de la CI sont obligatoires pour fusionner sur `main` (§46.2) ;
  - tout marqueur renvoie à un identifiant existant ;
  - aucun identifiant de niveau M n'est marqué dans le code.
- Les identifiants de niveau M sont reportés dans `docs/go-live.md`.
- Ajouter une ligne au catalogue est un changement de spec, et le test l'accompagne dans le même commit.

### 50.4 Doubles de test et jeux de données

| Double / jeu | Rôle | Exigences |
|---|---|---|
| **Faux gateway** OpenAI-compatible (`tests/fakes/fake_gateway.py`, aussi en conteneur e2e) | tous les tests LLM | scriptable par test : réponse valide · JSON malformé · sortie tronquée (`finish_reason = length`) · vide · refus · 429 avec ou sans `Retry-After` (secondes et date) · 5xx · 401 / 403 / 404 · 400 / 413 / 422 · latence réglable (timeout) · connexion refusée · `GET /models` ; journal des requêtes reçues, pour vérifier « aucun appel » |
| **Faux serveur de sources** (`tests/fakes/fake_sources.py`, aussi en conteneur e2e) | collectors, extraction, `robots.txt`, SSRF | sert les fixtures par type ; codes 304, 401, 403 (avec et sans `x-ratelimit-remaining: 0`), 404, 410, 429, 5xx, timeout, redirections (dont vers une adresse privée), corps trop gros, `Content-Type` non HTML, pagination interruptible |
| **Fixtures par type** (`tests/fixtures/http/<type>/`) | T-COL-01 | RSS et Atom · GitHub releases · Algolia HN · Reddit RSS avec `[link]` · YouTube RSS · `webpage` avec gabarit conforme et cassé |
| **Fixtures de prompts** (`tests/fixtures/llm/<task>/<PROMPT_VERSION>/`) | T-LLM-16 | snapshot du prompt construit (`system` et `user`) pour une entrée de référence, empreinte du template ; sorties réelles enregistrées (valides, limites, malformées) |
| **`scripts/record-llm-fixtures.py`** | enregistrer des sorties réelles | lancé **à la main** contre un vrai gateway, jamais en CI ; écrit sous `tests/fixtures/llm/` ; aucune donnée d'article réelle non publique |
| **Dépôt restic local** | T-BKP-*, T-RES-07 | dépôt `restic` sur système de fichiers local dans les tests ; dépôt injoignable simulé par un chemin ou un hôte invalide |
| **SMTP et Telegram factices** | T-ALR-*, T-SEC-01 | serveur SMTP local de capture ; faux endpoint Telegram joignable par la liste de test, qui capture le corps et renvoie les erreurs demandées |
| **Jeu synthétique** (`scripts/synthetic-dataset.py`) | T-CLU, T-TRD, T-EMG, mesures | profils **réaliste** (≈ 2 000 `ready` sur 72 h) et **cible** (10 000 items par jour, tous `ready`), graine fixe ; Events multi-sources, releases successives, entités omniprésentes, termes émergents, doublons de même source |
| **Script de charge** (`scripts/load.py`) | mesures M1 à M5, M9 | injecte le jeu dans le projet Compose `radar-load` (jamais `radar`), mesure l'API en lecture ; résultats au format de `docs/measurements.md` |

### 50.5 Catalogue par domaine

Niveaux : **U** unitaire · **I** intégration · **E** e2e Compose · **F** frontend · **M** manuel sur VPS.

#### T-DB — Base & migrations *(III §10–§11)*

| ID | Test | Niv. | Origine |
|---|---|---|---|
| T-DB-01 | SQLite < 3.35, FTS5 absent ou JSON1 absent → `app` et `worker` refusent de démarrer avec un message explicite | U | III §10.1 |
| T-DB-02 | Révision en base ≠ `head` → `app` et `worker` refusent de démarrer | I | III §10.1 · VII §36.3 |
| T-DB-03 | Chaque nouvelle connexion de `app` et `worker` applique `journal_mode=WAL`, `synchronous=NORMAL`, `busy_timeout`, `foreign_keys=ON`, `journal_size_limit` (la connexion de `migrate` est à `foreign_keys=OFF` : T-DB-13) | I | III §10.2 · VII → III |
| T-DB-04 | Deux processus écrivent en concurrence en `BEGIN IMMEDIATE` : aucun échec immédiat « database is locked », attente dans `busy_timeout` | I | III §10.3 · V0.3 §50 |
| T-DB-05 | Lecture de l'app pendant une écriture du worker : lecture non bloquée | I | V0.3 §50 |
| T-DB-06 | `busy_timeout` épuisé → retry borné, échec compté dans la métrique `db_locked`, transaction annulée sans écriture partielle | I | II §8.6, §9.4 |
| T-DB-07 | `UTCDateTime` refuse un datetime sans fuseau à l'écriture et renvoie de l'UTC à la lecture | U | III §10.6 |
| T-DB-08 | Migrations : `upgrade head` depuis une base vide ; chaque migration a un `downgrade` testé ou se déclare irréversible dans son en-tête | I | III §10.5 · VII §36.9 |
| T-DB-09 | Index unique partiel sur les jobs actifs : une seconde demande identique est ignorée sans erreur | I | III §11.10 |
| T-DB-10 | `AlertLog.dedup_key` unique : une seconde insertion identique est refusée | I | III · VI §33.4 |
| T-DB-11 | `article_fts` : triggers d'insertion, de mise à jour du résumé (écriture LLM comprise) et de suppression ; un `UPDATE` de `title` ou de `summary` met l'index à jour, un `UPDATE` de `status` ou d'`event_id` ne le modifie pas (`AFTER UPDATE OF title, summary`) ; recherche insensible aux diacritiques | I | III §11.14 · V-A |
| T-DB-12 | Colonnes à valeurs fermées : une valeur hors `CHECK` est refusée (échantillon : `Article.status`, `AIJob.status`, `AlertLog.status`) | I | III §11 |
| T-DB-13 | Clés étrangères pendant les migrations : la connexion de `migrate` lit `PRAGMA foreign_keys` = 0 ; une violation détectée par `PRAGMA foreign_key_check` fait échouer la migration et annule toute l'exécution : la révision Alembic et le schéma sont ceux d'avant l'exécution ; la reconstruction batch d'`article` conserve `article_topic`, `article_entity` et `embedding`, et recrée les trois triggers d'`article_fts` | I | III §10.5 |

#### T-CFG — Configuration & démarrage *(IV §16, §22 · VI §34.3 · VII §36.7)*

| ID | Test | Niv. | Origine |
|---|---|---|---|
| T-CFG-01 | `validate-config` accepte le `config/` du dépôt | U | IV §16.5 |
| T-CFG-02 | Chaque classe d'erreur fait refuser le démarrage du worker, avec un message qui donne fichier, clé et champ : syntaxe YAML · champ manquant · type inconnu · `poll_interval` sous le minimum · doublon de clé · parent inexistant · cycle · regex invalide · `config` refusée par le collector | U | IV §16.5 |
| T-CFG-03 | `clustering.embedding_wait + clustering.tick ≥ llm.delay.enrich_article` → refusé | U | V-B §28.15 |
| T-CFG-04 | `pipeline.yaml` absent → défauts ; présent, chaque section (`collectors`, `normalization`, `relevance`, `extraction`, `http`, `llm`, `embeddings`, `topic_backfill`, `clustering`, `importance`, `trends`, `emerging`, `alerts`, `ops`, `backup`, `restore_test`) est validée | U | IV §16.6 · V-A §27.8 · V-B · VII §39.7 |
| T-CFG-05 | `HTTP_CONTACT` absent → le worker refuse de démarrer | I | IV §22 |
| T-CFG-06 | `GITHUB_TOKEN` absent → sources `github` non planifiées, log `warning`, état « credentials manquants » exposé ; le worker démarre | I | IV §22 |
| T-CFG-07 | `DASHBOARD_URL` invalide (schéma, chemin, slash final) → `app` et `worker` refusent de démarrer ; `http://localhost` accepté en développement | U | VII §36.7 |
| T-CFG-08 | Registre des `Setting` : clé absente → défaut ; valeur hors schéma refusée par l'API | I | VI §34.3 |
| T-CFG-09 | `HTTP_TEST_ALLOW_HOSTS` renseignée avec `APP_ENV=production` → le worker refuse de démarrer | U | décision 23 |
| T-CFG-10 | Commandes `app.cli` : code de sortie `2` sur usage ou configuration invalide ; résultat sur stdout, logs sur stderr | U | IX §56.3 |

#### T-PIPE — Étages purs du pipeline *(IV §14, §18–§20, §14.5)*

| ID | Test | Niv. | Origine |
|---|---|---|---|
| T-PIPE-01 | `skipped` si `url` absente ou non HTTP(S), titre et contenu vides après nettoyage, ou `published_at` sans fuseau | U | IV §18.1 |
| T-PIPE-02 | Texte : balises HTML retirées (texte de `script` et `style` compris), entités décodées, NFC, espaces fusionnés, titre sur une ligne et ≤ 500, titre vide → 100 premiers caractères coupés sur un mot, contenu coupé à `content_max_length`, auteur vide → `NULL` | U | IV §18.2 |
| T-PIPE-03 | Canonicalisation d'URL, table de cas : règles communes 1 à 8 (minuscules, punycode, port par défaut, fragment, paramètres de tracking, tri, `/` final, `www.` et scheme conservés) et canonicaliseurs YouTube, Reddit et HN | U | IV §18.3 |
| T-PIPE-04 | Dates : conversion UTC ; absente → `discovered_at` ; future (> maintenant + 1 h) → `discovered_at` ; au-delà de 30 j → `too_old` ; une date de repli n'est jamais `too_old` | U | IV §18.4 |
| T-PIPE-05 | Langue : `NULL` sous 20 caractères ou si le détecteur ne tranche pas ; article allemand pertinent → `ready` (aucun filtrage par langue) | U | IV §18.5 |
| T-PIPE-06 | Dédup exacte : ordre `(source_id, external_id)` → `canonical_url` → `content_hash` ; comparaison sur tous les statuts ; doublon dans une même page ; doublon non inséré, compté, avec le critère en log `debug` | I | IV §19.1, §19.3 |
| T-PIPE-07 | Course de deux collectors sur une même `canonical_url` → filet `ON CONFLICT`, compté en `duplicate` | I | IV §14.3 |
| T-PIPE-08 | `content_hash` : minuscules + NFKC + espaces ; `NULL` sous 200 caractères ; jamais recalculé après extraction | U | IV §19.2 |
| T-PIPE-09 | Relevance filter, table `(titre, corps, url, taxonomie) → (score, statut, topics, entités)` avec les cas obligatoires : match titre seul · match corps seul sous le seuil · exclusion par masquage · regex · terme avec ponctuation (`gpt-4o`) · diacritiques · texte FR · URL seule · source `always` sous le seuil | U | IV §20.5 |
| T-PIPE-10 | Liaisons `keyword` calculées sur le texte final des `ready` ; la taxonomie inclut les topics `user` activés de la base et se recharge à la création d'un topic | I | IV décision 11 · V-B décision 25 |
| T-PIPE-11 | Résumé de repli : résumé du flux s'il fait au moins 40 caractères, sinon début du contenu final, sinon titre ; 300 caractères sur une frontière de mot + `…` ; calculé aussi pour les `filtered` ; `summary_origin = fallback` | U | IV §14.5 |
| T-PIPE-12 | Entités `keyword` : dictionnaire et alias de `entities.yaml`, motif `owner/repo` GitHub | U | IV §16.4 |

#### T-HTTP — Client HTTP partagé *(IV §17.3, §21 · VII §43.3)*

| ID | Test | Niv. | Origine |
|---|---|---|---|
| T-HTTP-01 | Classification : rejouables (réseau, timeout, 5xx, 429) contre non rejouables (400, 401, 403 hors rate limit, 404, 410) ; réponse malformée → échec du run sans exception non gérée | I | IV §21.2 · V0.3 §50 |
| T-HTTP-02 | Backoff `1 · 2 · 4 · 8 · 16 s`, plafonné à 60 s, jitter ± 20 %, `max_retries = 5` (horloge manuelle) | U | IV §21.2 |
| T-HTTP-03 | `Retry-After` (secondes et date HTTP) ≤ 60 s → attente dans le run ; > 60 s ou quota épuisé → arrêt du run, `rate_limit_remaining = 0`, `rate_limit_reset_at` renseigné | I | IV §21.3 |
| T-HTTP-04 | GitHub : 403 avec `x-ratelimit-remaining: 0` → traité comme 429 | I | IV §21.3 |
| T-HTTP-05 | Quota : en-têtes GitHub et Reddit lus ; aucun en-tête → `NULL` | U | IV §21.4 |
| T-HTTP-06 | Limiteur par hôte : 1 s par défaut, 5 s pour l'extraction, surcharges de `pipeline.yaml` | I | IV §21.1 |
| T-HTTP-07 | User-Agent `AITechRadar/{version} (+{HTTP_CONTACT})` sur toutes les requêtes | U | IV §17.3 |
| T-HTTP-08 | Anti-SSRF, après résolution DNS et à chaque redirection : refus de `127.0.0.1`, `169.254.169.254`, `10.0.0.0/8`, IPv6 unique-local, adresses non routables et redirection vers une adresse privée ; aucune exception | I | VII §43.3 · IV §21.1 |
| T-HTTP-09 | `robots.txt` : 4xx → tout autorisé ; 5xx ou timeout → tout refusé ; token `AITechRadar`, puis `*` ; cache de 24 h par hôte | I | IV §17.3 |

#### T-COL — Collectors & runner *(IV §14–§17, §21.5–§21.6)*

| ID | Test | Niv. | Origine |
|---|---|---|---|
| T-COL-01 | Fixtures par type : RSS et Atom · GitHub releases (304, rate limit) · Algolia HN · Reddit RSS avec `[link]` → `link_url` · YouTube RSS · `webpage` avec gabarit cassé (items `skipped`, run sans exception) | I | IV → VIII |
| T-COL-02 | Invariant `items_fetched = items_created + items_filtered + items_duplicate + items_skipped + items_too_old` sur chaque run | I | IV §14.4 |
| T-COL-03 | Interruption en milieu de pagination puis reprise par checkpoint : aucun doublon ; checkpoint écrit dans la transaction de la page | I | IV → VIII |
| T-COL-04 | Checkpoint perdu → requêtes supplémentaires, aucun doublon | I | IV décision 4 |
| T-COL-05 | Isolation : une source en panne n'arrête pas les autres ; un item malformé est écarté seul (`items_skipped`), la page continue | I | II §9.3 · IV §14.2 |
| T-COL-06 | Aucun appel réseau pendant une transaction d'écriture (le double HTTP échoue s'il est appelé alors qu'une `write_session` est ouverte) | I | IV §14.2 |
| T-COL-07 | Premier run plafonné à 100 items par source | I | IV §15.3 |
| T-COL-08 | Extraction : déclencheurs (`ready`, `extract: auto`, flux < 500 caractères, cible `link_url` seule pour HN et Reddit, denylist) ; remplacement seulement si plus long ; URL finale canonicalisée ; `Content-Type` non HTML, > 3 Mo, > 5 redirections ou refus robots → contenu du flux conservé, `extractions_failed` incrémenté, pas de retry | I | IV §17 |
| T-COL-09 | Disjoncteur par source : k ≥ 3 → `min(poll_interval × 2^(k−2), 24 h)` ; `partial` ou `success` remet k à 0 ; 401 et 403 comptent | I | IV §21.5 |
| T-COL-10 | Scheduler : run sauté sans `CollectorRun` si quota épuisé avant reset ou disjoncteur ouvert ; jitter de démarrage dans [0, 120 s] ; `coalesce` et `max_instances=1` | I | IV §21.6 |
| T-COL-11 | Canal déclaré par le registre : `rss` et `webpage` → `web` | U | V-B décision 14 |
| T-COL-12 | Insertion d'un `ready` → exactement un `enrich_article`, priorité 60 (source `always`) ou 50, `next_attempt_at = maintenant + 15 min`, dans la transaction de la page | I | V-A → IV |
| T-COL-13 | `Article.metrics` : instantané d'engagement validé à la collecte, jamais mis à jour | U | IV décision 18 |

#### T-PRG — Purge & rétention *(II §8.5 · III §13 · V-A §24.5)*

| ID | Test | Niv. | Origine |
|---|---|---|---|
| T-PRG-01 | `content` d'un `ready` purgé à `processed_at + 1 j` (configurable), pas avant | I | III §13 |
| T-PRG-02 | Jamais de purge tant qu'un job de l'article est en `dead_letter` ; débloquée après relance aboutie ou `cancelled` | I | II §8.5 · III §13 |
| T-PRG-03 | `filtered` et `duplicate` : `content = NULL` immédiatement, `content_purged_at` renseigné | I | III §13 · IV §14.3 |
| T-PRG-04 | Passe `processed_at` : posée seulement quand l'embedding est écrit et les jobs de l'article terminaux (`skipped` compte comme `completed`) ; idempotente | I | V-A §24.5 |
| T-PRG-05 | Suppressions à 30 j : lignes `Article` `filtered`, `AIJob` `completed` / `failed` / `cancelled` / `skipped`, `CollectorRun` ; `dead_letter` conservé ; `AlertLog` conservé 1 an | I | III §13 · V-A |
| T-PRG-06 | `Signal` : valeurs horaires conservées 30 j, puis seule la ligne de 00:00 UTC est conservée | I | III §13 · V-B |
| T-PRG-07 | Chaque passage est journalisé ; aucune autre donnée n'est supprimée (contrôle sur un jeu couvrant toutes les tables) | I | III §13 |

#### T-JOB — File `AIJob` *(V-A §23)*

| ID | Test | Niv. | Origine |
|---|---|---|---|
| T-JOB-01 | Tous les statuts et transitions : `pending → processing → completed / retry / dead_letter / failed / skipped` ; `cancelled` depuis `dead_letter` | I | V0.3 Sprint 5 · III §11.10 |
| T-JOB-02 | Claim atomique : ordre priorité décroissante puis `created_at DESC` ; un job n'est jamais exécuté deux fois ; concurrence bornée par le sémaphore | I | V-A décision 11 · II §8.3 |
| T-JOB-03 | `job_type` inconnu → `failed`, le worker continue | I | II §8.3 |
| T-JOB-04 | Chaque `skip_reason` : `expired` · `article_not_ready` · `event_member` · `event_not_active` · `event_single_source` · `candidate_decided` ; une régénération demandée par l'app n'est jamais sautée pour `event_member` | I | V-A §23.3 |
| T-JOB-05 | TTL par type : 72 h pour `enrich_article`, 7 j pour `resolve_event` et `discover_topics` | U | V-A décision 12 |
| T-JOB-06 | Rejeu idempotent de chaque `job_type` : état final identique, liaisons `keyword` intactes | I | II §9.1 · III §11.10 · V-A |
| T-JOB-07 | Au boot, tout `processing` repasse en `retry` | I | II §9.2 |
| T-JOB-08 | L'app ne peut faire passer un job que de `dead_letter` à `pending` ou à `cancelled` ; toute autre transition est refusée | I | V-A décision 19 |

#### T-LLM — LLMClient, disjoncteur, budget, prompts *(V-A §24–§27)*

| ID | Test | Niv. | Origine |
|---|---|---|---|
| T-LLM-01 | Gateway down (connexion refusée) → disjoncteur ouvert → aucun claim LLM → tentatives inchangées → gateway up → sonde OK → job test OK → reprise, les plus récents d'abord | I | V-A §26.3 |
| T-LLM-02 | 429 avec `Retry-After: 120` → `open_until = +120 s` → `half_open` → job test → `closed` | I | V-A §26.3 |
| T-LLM-03 | 429 persistant sans `Retry-After` → réouvertures à 60 s, 120 s, 240 s…, plafonnées à 6 h | I | V-A §26.3 |
| T-LLM-04 | Réponse non JSON × 3 → `dead_letter` ; purge du contenu bloquée ; relance par l'app → `pending` | I | V-A §26.3 |
| T-LLM-05 | Élément d'entité invalide dans une réponse valide → écarté, `dropped_items = 1`, job `completed` | I | V-A §26.3 |
| T-LLM-06 | 3 timeouts consécutifs → disjoncteur ouvert (cause `unavailable`) | I | V-A §26.3 |
| T-LLM-07 | `LLM_BASE_URL` absent → worker démarré, jobs créés et `pending`, `llm_gateway` à `not_configured` | I | V-A §26.3 |
| T-LLM-08 | `kill -9` après l'appel LLM, avant la transaction → `retry` → rejoué → état final identique | E | V-A §26.3 |
| T-LLM-09 | Erreurs typées : connexion / DNS / 5xx → `LLMUnavailable` · 429 → `LLMRateLimited` · 401 / 403 / 404 → `LLMConfigError` (plus alerte de configuration) · timeout de lecture → `LLMTimeout` · malformé, vide, tronqué, refus → `LLMMalformed` · 400 / 413 / 422 → `LLMBadRequest` → `failed` ; `last_error` sans secret | I | V-A §25.4, §26.1 |
| T-LLM-10 | Extraction du JSON : balises de code retirées, premier objet `{…}` équilibré | U | V-A §25.3 |
| T-LLM-11 | `TolerantList` (élément invalide écarté et compté) et `SoftStr` (coupe au-delà de `max` sur un mot + `…`, erreur sous `min`) | U | V-A §25.3 |
| T-LLM-12 | Aucune écriture avant la fin de la validation ; résultat écrit en une transaction unique | I | V-A §26.2 |
| T-LLM-13 | Entités LLM canonicalisées par les alias de `entities.yaml`, puis par slug déterministe : aucun doublon d'entité | U | V-A décision 17 |
| T-LLM-14 | Budget quotidien : désactivé par défaut ; épuisé → plus de claim côté worker, la réserve reste disponible pour les demandes de l'app ; remise à zéro au changement de jour UTC | I | V-A §24.3 |
| T-LLM-15 | Injection : un contenu d'article porteur d'instructions est placé dans `user` entre délimiteurs ; une sortie hors schéma ou avec des topics hors liste fermée est écartée ; la sortie n'est jamais exécutée | U | V-A §25.5 |
| T-LLM-16 | Fixtures de prompts : snapshot du prompt construit par `PROMPT_VERSION` ; template modifié sans changement de version → échec ; parsing des sorties de référence enregistrées | U | V-A → VIII · décision 15 |
| T-LLM-17 | Observabilité : log par appel avec `task`, `job_id`, latence, tokens, classe d'erreur et `PROMPT_VERSION` ; jamais le prompt ni la réponse au niveau `info` | U | V-A §25.6 |
| T-LLM-18 | `enrich_article` remplace les trois familles `method=llm` en une transaction et passe `summary_origin` à `llm` ; `resolve_event` ne touche ni à l'appartenance ni aux compteurs et passe `title_origin` à `llm` ; `discover_topics` écrit les colonnes `llm_*` du candidat sans jamais l'écarter | I | V-A §27 |
| T-LLM-19 | Indépendance du provider : passer d'un faux gateway à un autre (base URL, clé, modèle différents) par les seules variables `LLM_*`, sans changement de code | I | Partie I §4.3 |
| T-LLM-20 | Le `LLMClient` refuse une redirection vers un autre hôte que celui de `LLM_BASE_URL` | U | V-A §25.2 |

#### T-EMB — Embeddings *(III §12 · V-A §24.4)*

| ID | Test | Niv. | Origine |
|---|---|---|---|
| T-EMB-01 | File dérivée : sélection des `ready` sans `Embedding` pour le modèle courant **et** au contenu non purgé ; aucun ré-embedding de l'historique | I | V-A décision 20 |
| T-EMB-02 | Article poison : échec persistant → ligne `Embedding` en échec (`vector NULL`, `error`), exclue de la similarité ; la file continue | I | V-A → VIII |
| T-EMB-03 | Vecteurs normalisés (norme 1) ; texte d'entrée = titre + 1 000 premiers caractères ; comparaison entre vecteurs du même modèle uniquement | U | III §12.2–§12.4 |
| T-EMB-04 | Matrice de la fenêtre reconstruite au démarrage, identique à celle d'avant l'arrêt | I | III §12.4 |
| T-EMB-05 | Moteur indisponible → `SystemState.embeddings = down` et son horodatage ; retour → `up` | I | V-A · VII |
| T-EMB-06 | Calcul hors event-loop : pendant un lot d'embeddings, le heartbeat et les ticks continuent à l'heure | I | II §8.4 |

#### T-CLU — Clustering *(V-B §28)*

| ID | Test | Niv. | Origine |
|---|---|---|---|
| T-CLU-01 | Post HN dont le contenu extrait égale le billet : même Event, deux sources, aucun `duplicate` | I | V-B → VIII |
| T-CLU-02 | `duplicate` rétroactif : même source, titres normalisés égaux, cosine ≥ seuil haut → `duplicate` ; topics et résumés conservés, article masqué ; sources différentes → même Event, jamais `duplicate` | I | V-B décision 1 · II |
| T-CLU-03 | Releases successives d'un même dépôt : jamais regroupées, jamais en doublon | I | V-B → VIII |
| T-CLU-04 | Entité omniprésente (fréquence documentaire élevée) : ne relie rien ; URL hub (racine de domaine, racine d'owner GitHub, `url_ignore`) ignorée | I | V-B → VIII |
| T-CLU-05 | Premier run de 100 items anciens : aucun regroupement hors proximité `published_at` ≤ 72 h ; `event_max_span` (7 j) respecté | I | V-B → VIII |
| T-CLU-06 | Un Event naît à deux articles ; un article sans candidat reste hors Event | I | V-B décision 7 |
| T-CLU-07 | Moteur d'embeddings down : clustering par URL et entités, puis seconde passe cosine unique au retour | I | V-B → VIII |
| T-CLU-08 | Fusion de deux Events, sur lien fort uniquement : compteurs recalculés, un seul `resolve_event` sur la cible, jobs des sources sautés ; un lien par entités seules ne fusionne pas | I | V-B → VIII |
| T-CLU-09 | Changement de représentant : titre de repli suivi, `enrich_article` créé si le nouveau représentant n'est pas enrichi | I | V-B → VIII |
| T-CLU-10 | Invariant des compteurs après chaque opération (`distinct_source_count`, `distinct_channel_count`, `article_count` = recalcul depuis les membres) ; `recount-events` sans effet sur une base cohérente, correctif sur une base altérée | I | V-B §28.9 |
| T-CLU-11 | `kill -9` pendant une évaluation → reprise sans double rattachement ni compteur faux | E | V-B → VIII |
| T-CLU-12 | `resolve_event` par marqueur `resolve_enqueued_count` : à 2 sources distinctes, puis à 4, 8, 16 articles ; idempotent ; jamais sur un Event mono-source | I | V-B §28.10 |
| T-CLU-13 | `importance` dans [0, 1], indépendante du temps, conforme aux poids de `importance.weights` | U | V-B §28.9 |
| T-CLU-14 | `archived` après 7 j d'inactivité, sans effet sur les rattachements | I | V-B §28.11 |
| T-CLU-15 | Déclenchement : après chaque lot d'embeddings, et par le tick pour un article sans embedding au-delà de `embedding_wait` | I | V-B §28.2 |
| T-CLU-16 | `cluster-calibrate` produit histogramme, échantillons par tranche et fréquences d'entités sur le jeu synthétique | I | V-B §28.14 |

#### T-TRD — Trend Engine *(V-B §29)*

| ID | Test | Niv. | Origine |
|---|---|---|---|
| T-TRD-01 | Cold start : `growth_rate`, `momentum` et `novelty` à `NULL` tant que la couverture ne le permet pas ; warm-up de `novelty` | U | V-B → VIII |
| T-TRD-02 | Parent : union distincte des descendants, sans double compte | I | V-B → VIII |
| T-TRD-03 | EMA après un trou de plusieurs heures : `α` calculé sur l'écart réel, sans rattrapage | U | V-B → VIII |
| T-TRD-04 | Upsert idempotent sur `(topic_id, period, window_end)` | I | V-B → VIII |
| T-TRD-05 | Liaisons `llm` sans effet sur les mentions ; gateway coupé → aucun faux `declining` | I | V-B → VIII · V-A |
| T-TRD-06 | Mentions sur `published_at`, articles `ready` hors doublons ; catégories `established` / `trending` / `rising` / `declining`, `NULL` si le support est insuffisant | U | V-B §29.2, §29.6 |

#### T-EMG — Émergence & « Create topic » *(V-B §30)*

| ID | Test | Niv. | Origine |
|---|---|---|---|
| T-EMG-01 | Warm-up : aucune détection avant `trends_since + emerging.warmup` | I | V-B → VIII |
| T-EMG-02 | Chaque critère de détection isolément, dont « multi-histoires » (au moins deux Events ou articles isolés distincts) | U | V-B → VIII |
| T-EMG-03 | Maximalité des n-grammes | U | V-B → VIII |
| T-EMG-04 | Terme contenant un mot-clé non couvert | U | V-B → VIII |
| T-EMG-05 | Sourdine (`mute`) : jamais reproposé | I | V-B → VIII |
| T-EMG-06 | Réapparition après `ignore`, sur évolution significative | I | V-B → VIII |
| T-EMG-07 | Évolution significative : doublement des mentions ou nouveau canal, au plus une fois par 24 h ; crée un `discover_topics` si aucune décision | I | V-B §30.5 |
| T-EMG-08 | « Create topic » : slug en collision ; backfill interrompu puis repris ; backfill seulement sur les articles `summary_origin = fallback` ; liaisons sur les nouveaux articles ; Signal à l'heure suivante | I | V-B → VIII |
| T-EMG-09 | Dépôts GitHub comme termes (`kind = repository`) | U | V-B décision 19 |

#### T-API — API & logique du dashboard *(VI §31–§34)*

| ID | Test | Niv. | Origine |
|---|---|---|---|
| T-API-01 | Story : un Event multi-sources n'apparaît qu'une fois dans l'Overview, jamais par ses membres ; `duplicate` et `filtered` jamais affichés ; une story au plus une fois sur l'ensemble des six sections | I | VI → VIII · Partie I §3 |
| T-API-02 | Lu / non lu : ré-ouverture sur progression de `last_seen_at` ; historique antérieur à `trends_since` réputé lu ; lecture implicite ; « marquer non lu » ; « tout marquer lu » par lots, avec reprise sur `remaining` | I | VI → VIII |
| T-API-03 | Event fusionné : redirection sur une chaîne de deux fusions ; état de lecture de la cible conservé | I | VI → VIII |
| T-API-04 | Sourdine : règle « tous » sur sources et topics ; héritage parent → enfant ; `follow` explicite d'un enfant prioritaire ; même résultat côté app et côté worker, sur une même table de cas | I | VI → VIII |
| T-API-05 | Pagination keyset stable sous insertion concurrente ; `limit > 50` refusé ; aucun paramètre d'offset | I | VI → VIII |
| T-API-06 | Recherche : saisie contenant la syntaxe FTS5 (`"`, `*`, `NEAR`, `-`) sans erreur | I | VI → VIII |
| T-API-07 | Filtres du Feed : topic, source, entité, date, importance, non lu, suivis, `q` | I | VI décision 10 |
| T-API-08 | Régénération : 202 immédiat ; `already_active` sur un job actif ; `jobs_in_progress` exposé ; action indisponible sur Event mono-source, `archived`, `merged` et LLM `not_configured` | I | VI → VIII |
| T-API-09 | `dead_letter` : relance, abandon, 409 si le statut a changé | I | VI → VIII |
| T-API-10 | API complète gateway éteint, puis gateway non configuré : aucun endpoint en erreur | I | VI → VIII · II §9.5 |
| T-API-11 | Importance exposée sur 0–100, `NULL` si absente ; valeurs de tendance `NULL` jamais converties en 0 | I | VI décision 3 · V-B |
| T-API-12 | Related topics déterministes : parent, enfants, top 5 par co-occurrence `keyword` sur 30 j | I | VI décision 9 |
| T-API-13 | `/api/status`, `/api/health` et `/health` calculés par le même module, avec le même seuil de heartbeat | I | VII §40.1 |
| T-API-14 | Aucune requête HTTP n'exécute de job ni n'attend un résultat LLM ; l'app n'insère que des `job_type` de la liste fermée (`enrich_article`, `resolve_event`) | I | II §8.3 · V-A décision 18 |

#### T-FE — Frontend *(VI · VII §37.3)*

| ID | Test | Niv. | Origine |
|---|---|---|---|
| T-FE-01 | Sortie LLM contenant du HTML ou des balises : rendue en texte brut | F | VI → VIII |
| T-FE-02 | Lint : `dangerouslySetInnerHTML` interdit (règle active, un fichier témoin échoue) | U | VI → VIII |
| T-FE-03 | Badge « N sources · M canaux » ; corroborée (≥ 2 sources) ou isolée | F | VI décision 2 |
| T-FE-04 | Importance `NULL` → « — » ; tendance `NULL` → « données insuffisantes » | F | VI · V-B |
| T-FE-05 | Indicateur discret repli / enrichi selon `summary_origin` et `title_origin` | F | V-A → VI |
| T-FE-06 | Boutons d'action masqués ou « en cours » selon les indicateurs de l'API | F | VI §31.9 |
| T-FE-07 | Build : aucun script ni `<style>` en ligne dans `index.html` et les assets (compatibilité CSP) | U | VII §37.3 |

#### T-ALR — Alertes & digests *(VI §33)*

| ID | Test | Niv. | Origine |
|---|---|---|---|
| T-ALR-01 | Aucune alerte envoyée deux fois sur un même canal (`dedup_key` avec le canal) | I | VI → VIII |
| T-ALR-02 | Une même alerte part sur email **et** Telegram | I | VI → VIII |
| T-ALR-03 | Pas de réémission après la fusion d'un Event déjà alerté (dédup par Event cible) | I | VI → VIII · V-B |
| T-ALR-04 | Aucune rafale après une baisse du seuil (fenêtre `max_age` de 48 h), ni au premier run | I | VI → VIII |
| T-ALR-05 | Attente du titre LLM bornée à 30 min ; envoi immédiat si le disjoncteur est ouvert | I | VI → VIII |
| T-ALR-06 | Heures calmes respectées | I | VI → VIII |
| T-ALR-07 | Plafond quotidien atteint → `suppressed` | I | VI → VIII |
| T-ALR-08 | `sending` requalifié en `failed` au boot | I | VI → VIII |
| T-ALR-09 | Canal non configuré → worker démarré, canal désactivé, état exposé | I | VI → VIII |
| T-ALR-10 | `important_event` : Event seulement (jamais un article isolé) ; seuil 50, seuil abaissé (25) pour les stories suivies ; sourdine respectée | I | VI décisions 3, 17 |
| T-ALR-11 | `emerging_topic` : candidats suivis seulement, et `last_significant_at > decided_at` ; candidats sans décision → digest uniquement | I | VI → V-B · VI décision 19 |
| T-ALR-12 | Mode `digest_only` : aucune alerte instantanée métier | I | VI décision 18 |
| T-ALR-13 | Digests : envoi unique par jour et par canal ; digest vide non envoyé ; worker arrêté à l'heure prévue puis redémarré le même jour → un seul envoi, le lendemain → aucun rattrapage ; changement d'horaire pris en compte | I | VI → VIII |
| T-ALR-14 | Sortie LLM contenant du HTML : rendue en texte brut dans l'email et Telegram | I | VI → VIII |
| T-ALR-15 | Échec d'envoi : journalisé, compté, `failed`, non rejoué (V1) | I | II §9.4 · VI |
| T-ALR-16 | Routage par type d'alerte (défaut : Telegram pour l'instantané, email pour les digests) ; `send-test-alert` n'écrit pas dans `AlertLog` | I | VI §33.9–§33.10 |

#### T-OPS — Santé, supervision & alertes `system` *(VII §36.6, §39–§40)*

| ID | Test | Niv. | Origine |
|---|---|---|---|
| T-OPS-01 | `/health` public : `{status}` seul, `ok` → 200, `degraded` → 200, `down` → 503 ; aucune version, aucun composant, aucun horodatage | I | VII → VIII |
| T-OPS-02 | Heartbeat périmé (âge calculé par l'app au moment de la requête) → 503 | I | VII → VIII |
| T-OPS-03 | Base inaccessible ou lecture > 2 s → 503 | I | VII → VIII |
| T-OPS-04 | Au moins une condition active → `degraded` (200) | I | VII §40.2 |
| T-OPS-05 | `/api/health` : 401 sans identifiants (E) ; composants et statuts (`ok`, `degraded`, `down`, `disabled`, `not_configured`) conformes à la table §39.5 (I) | I · E | VII → VIII |
| T-OPS-06 | Table-driven sur toutes les conditions du §39.5 : condition vraie ⇔ composant `degraded` ⇔ alerte émise par le bon acteur ; informatifs sans effet sur `status` | I | VII §39.5 |
| T-OPS-07 | Watchdog : event-loop gelée au-delà de `ops.watchdog_timeout` → processus arrêté | I | VII → VIII |
| T-OPS-08 | Tâche permanente en exception (boucle AI, file d'embeddings, scheduler, heartbeat) → log `critical`, sortie non nulle ; job planifié en échec → worker maintenu, `job_failing` après 3 échecs | I | VII → VIII · §36.6 |
| T-OPS-09 | Le heartbeat démarre avant le chargement des modèles | I | VII décision 14 |
| T-OPS-10 | Séquence de boot : vérifications → heartbeat → requalification des `processing` et des `sending` → modèles → matrice → scheduler | I | VII §36.6 |
| T-OPS-11 | SIGTERM : plus aucun claim ni run ; attente des jobs en cours ≤ 20 s ; le reste est requalifié au boot suivant | I | VII §36.6 |
| T-OPS-12 | Alertes `system` : une par épisode ; pas de réémission après redémarrage (épisodes dans `ops_conditions`) ; hystérésis du disque (80 / 75, 90 / 85) ; ignorent `alerts.mode`, heures calmes et plafond, et n'y comptent pas ; échec d'envoi sans récursion ; routage par défaut Telegram + email | I | VII → VIII |
| T-OPS-13 | Seuils : `llm_config_error` immédiat ; `llm_down_long` au-delà de 24 h, jamais pour `not_configured` ; `embeddings_down` au-delà de 15 min ; RAM sur 10 échantillons ; `sources_down` à 50 % ; `db_locked` à 10 par heure ; `wal_large` | I | VII §39.4 |
| T-OPS-14 | `ops.tick` écrit `ops_metrics` et `ops_conditions` ; les endpoints de santé ne font que lire `SystemState` (aucune agrégation d'historique dans une requête) | I | VII décision 16 |
| T-OPS-15 | Aucun canal d'alerte configuré → condition `no_alert_channel` | I | VII §39.5 |
| T-OPS-16 | Coalescence des misfires au redémarrage : une seule exécution par job planifié manqué | I | II §8.4 |
| T-OPS-17 | `vacuum` refusé si le heartbeat du worker a moins de `ops.heartbeat_stale_after`, et si l'espace libre de `/data` est inférieur à deux fois la taille de la base | I | IX §56.4.2 |

#### T-BKP — Backup & restauration *(VII §38)*

| ID | Test | Niv. | Origine |
|---|---|---|---|
| T-BKP-01 | `VACUUM INTO` pendant des écritures concurrentes : copie cohérente, écrivains non bloqués | I | VII → VIII |
| T-BKP-02 | Copie corrompue (`integrity_check` ≠ `ok`) ou révision ≠ `head` → échec du backup | I | VII → VIII |
| T-BKP-03 | restic injoignable → `backup_failed`, `backup_last_attempt` renseigné, copie locale supprimée | I | VII → VIII |
| T-BKP-04 | Succès → `last_backup = {at, snapshot_id, size_bytes, duration_s}`, rétention `forget 7/4/3` appliquée, copie locale supprimée | I | VII §38.2 |
| T-BKP-05 | Démarrage avec un dernier succès datant de plus de 24 h → backup lancé | I | VII → VIII |
| T-BKP-06 | `RESTIC_REPOSITORY` absent → `not_configured`, `/health` `degraded`, worker démarré | I | VII §38.3 |
| T-BKP-07 | `restore-test` sur un backup valide → `ok` ; sur un backup tronqué → échec, `last_restore_test` renseigné ; lancé au démarrage si aucun succès depuis 35 j | I | VII → VIII |
| T-BKP-08 | Restauration avec un `-wal` d'une autre base présent : `scripts/restore.sh` le supprime, base restaurée saine | E | VII → VIII · décision 24 |
| T-BKP-09 | `backup-now` : backup immédiat, code de sortie non nul en cas d'échec (utilisé par `deploy.sh`) | I | VII §36.8 · §49.5 |
| T-BKP-10 | `backup-now` affiche le `snapshot_id` du backup réalisé | I | IX §56.4 · décision 19 |
| T-BKP-11 | Verrou de backup `/data/backup/.lock` : `backup-now` ou `restore-test` lancé pendant un job en cours → code `1` et message explicite ; job planifié qui trouve le verrou pris → abstention journalisée, sans `backup_failed` | I | IX §56.4.1 |
| T-BKP-12 | `deploy.sh` refuse un rollback à travers une migration (migration du sha déployé absente du sha visé) et liste les migrations avec leur réversibilité | I | §49.5 · IX §56.6-P2 |

#### T-SEC — Secrets, auth, Caddy, réseau, conteneurs *(VI §32 · VII §36–§37, §42.4, §43)*

| ID | Test | Niv. | Origine |
|---|---|---|---|
| T-SEC-01 | Nettoyage des secrets : secrets factices ; 401 GitHub, 401 LLM, 401 Telegram (token dans l'URL), échec d'auth SMTP, échec restic → aucune valeur factice dans les logs capturés ni dans `Source.last_error`, `AlertLog.error`, `backup_last_attempt.error` et les erreurs d'`AIJob` | I | VII §42.4 |
| T-SEC-02 | Configuration typée : représentation des `SecretStr` masquée ; clés `authorization`, `password`, `token`, `secret`, `api_key`, `cookie` masquées par le processeur de logs | U | VII §42.4 |
| T-SEC-03 | Auth : 401 sans identifiants sur `/` et `/api/*` ; `/health` sans auth | E | VI → VIII · VII |
| T-SEC-04 | Anti-CSRF : 403 sur une écriture sans `X-Radar-Client`, sans `Content-Type: application/json` ou avec un `Origin` étranger | I | VI → VIII |
| T-SEC-05 | `/docs`, `/redoc` et `/openapi.json` absents avec `APP_ENV=production` (défaut) ; présents en `development` | I | VI → VIII · VII §37.4 |
| T-SEC-06 | Caddy : `Authorization` absent des logs ; `/health` non journalisé ; en-têtes de sécurité présents (CSP complète, `X-Frame-Options`, `Referrer-Policy`, `nosniff`, HSTS, pas de `Server`) ; corps > 1 Mo refusé ; `index.html` en `no-cache`, assets `immutable` | E | VII → VIII |
| T-SEC-07 | Réseau : `app` sans sortie Internet ; `worker` ne joint pas `app:8000` ; `migrate` sans réseau | E | VII → VIII |
| T-SEC-08 | Politique Compose : seul `caddy` publie des ports ; aucun montage du socket Docker ; `app` sans secret et variables distribuées par service (VII §36.7) ; utilisateur non-root, `cap_drop: ALL`, `no-new-privileges`, `read_only` sur `app` et `worker` | U | VII §36, §43.2 |
| T-SEC-09 | Racine en lecture seule fonctionnelle : onnxruntime, lingua, restic (cache dans `/tmp`), préparation dans `/data/backup/` | E | VII §36.5 · décision 4 |
| T-SEC-10 | Modèle d'embeddings intégré : le worker démarre et embedde sans aucun accès à un hub de modèles | E | VII décision 9 |
| T-SEC-11 | Aucun secret renvoyé par l'API ni stocké dans `Setting` | I | VI §32.3 |

#### T-RES — Résilience de bout en bout *(Partie I §4.3 · II §9.5 · V-A §26)*

| ID | Test | Niv. | Origine |
|---|---|---|---|
| T-RES-01 | **LLM down** : gateway coupé → ingestion continue → Events créés → hotness affichée → jobs en `retry` sans consommer de tentative → gateway rétabli → reprise sans doublon, les plus récents d'abord | E | II §9.5 · V-A §26.2 |
| T-RES-02 | **Produit sans LLM de bout en bout** (critère de validation de la Partie II) : gateway éteint, puis non configuré → collecte, dédup, Events, hotness, dashboard, recherche et alertes déterministes opérationnels | E | II §9.5 |
| T-RES-03 | **429** : source en 429 (`Retry-After` court et long) et gateway en 429 → aucune rafale, reprise conforme | E | Partie I §4.3 · IV §21.3 · V-A §26.3 |
| T-RES-04 | **Source down** : une source en 5xx ou timeout → les autres continuent, disjoncteur ouvert, reprise au retour | E | Partie I §4.3 · II §9.3 |
| T-RES-05 | **Worker restart** : `kill -9` pendant un job, pendant une pagination, pendant une évaluation de clustering → redémarrage par Docker → requalification → résultat unique, aucun doublon | E | II §9.5 · V-B |
| T-RES-06 | **Reboot simulé** : arrêt brutal de tous les conteneurs puis relance par le démon, sans `migrate` → base disponible, worker et scheduler repris, aucun job dupliqué, aucun misfire en rafale | E | II §9.5 |
| T-RES-07 | **Backup restore** : backup → base détruite → `scripts/restore.sh` → `/health = ok`, dashboard et comptages cohérents | E | Partie I §4.3 · VII §38.5 |
| T-RES-08 | **App arrêtée** : l'ingestion, le clustering et les tendances continuent ; Caddy répond 502 sur `/health` | E | II §9.2 · VII §39.5 |
| T-RES-09 | **Reboot réel du VPS** : `/health = ok` en ≤ 3 min, sans alerte externe (M10) | M | VII §45.4 |
| T-RES-10 | **Échec de `migrate`** → `app` et `worker` ne démarrent pas, `/health` en 502 | E | VII §36.3 |
| T-RES-11 | **Restauration complète sur machine neuve** (`git clone` + `.env` + restauration + `docker compose up -d`) jusqu'au dashboard fonctionnel, durée mesurée (M7) | M | VII §38.4 |
| T-RES-12 | **Monitoring externe** : arrêt d'`app` → alerte reçue après deux sondes en échec ; remise en route → retour à 200 | M | VII §41 |

### 50.6 Les six tests de résilience de la Partie I

| Partie I §4.3 | Automatisé (CI, étape 6) | Sur le VPS cible (pré-production) |
|---|---|---|
| LLM down | T-RES-01, T-RES-02, T-LLM-01 à 07 | — |
| 429 | T-RES-03, T-LLM-02 et 03, T-HTTP-03 | — |
| Source down | T-RES-04, T-COL-05, T-COL-09 | — |
| Worker restart | T-RES-05, T-LLM-08, T-CLU-11 | — |
| VPS reboot | T-RES-06 (simulé) | T-RES-09 (réel, M10) |
| Backup restore | T-RES-07, T-BKP-* | T-RES-11 (machine neuve, M7) |

Le critère « Résilient » de la Partie I est atteint quand toutes les lignes de ce tableau sont vertes.

### 50.7 Performance

- Les mesures M1 à M10 (VII §45.4) ne tournent pas en CI : leur résultat dépend du VPS.
- Elles sont jouées par `scripts/load.py` sur les profils de `scripts/synthetic-dataset.py`, dans le projet Compose `radar-load` (décision 20), et consignées dans `docs/measurements.md`.
- Mesures indicatives en développement : M1 et M2 au Sprint 4, M5 au Sprint 8, M6 au Sprint 6. Mesures **de référence** : en pré-production, sur le VPS cible.

### 50.8 Couverture

Mesurée à l'étape 4 (branches comprises) et publiée dans le résumé du job. **Non bloquante.** Une baisse notable est un signal de revue, pas un critère d'échec : le critère bloquant est la traçabilité (§50.3).

---

## 51. Definition of Done

### 51.1 Fonctionnalité

Une fonctionnalité est terminée quand **tous** les points suivants sont vrais :

1. **Tests** : les identifiants du catalogue qui la concernent sont couverts et verts ; tout comportement nouveau non catalogué a un test, et l'ajout d'une ligne au catalogue l'accompagne si le comportement est contractuel. Aucun test ne touche au réseau externe.
2. **Erreurs** : chaque erreur prévue par la spec est traitée selon sa famille (rejouable ou non, isolée au bon niveau) ; aucun `except` silencieux ; les messages d'erreur écrits en base passent par le nettoyage des secrets.
3. **Logs** : événements structurés aux noms stables (`component.objet.action`), champs du §42.2, aucun secret, aucun prompt ni réponse LLM au niveau `info`.
4. **Observabilité** : les métriques et conditions que la spec associe à la fonctionnalité sont branchées (VII §39.2, §39.5).
5. **Configuration** : tout nouveau réglage vit dans `pipeline.yaml` avec son défaut et sa validation ; toute nouvelle variable figure dans `.env.example` avec son statut ; aucun réglage fonctionnel en variable d'environnement.
6. **Données** : migration Alembic (`render_as_batch`) avec `downgrade` ou en-tête « irréversible » ; valeurs fermées en `CHECK` ou validées par le code comme la spec l'indique ; rétention couverte par la table III §13.
7. **Règles d'architecture respectées** : un seul écrivain par table et par clé `SystemState` ; travail CPU hors event-loop ; aucun appel réseau dans une transaction d'écriture ; aucun appel LLM dans le pipeline ; l'app n'exécute aucun job ; `Clock` utilisée pour tout instant.
8. **Qualité** : `ruff` et `mypy` propres ; CI verte (étapes 1 à 5 sur la branche, 6 sur `main`).
9. **Documentation** : `docs/` à jour pour le composant ; runbook mis à jour pour toute nouvelle commande CLI ou procédure ; ADR pour tout choix structurant.

### 51.2 Sprint

Un sprint est terminé quand :

- son plan, dans `docs/sprints/sprint-NN.md`, a été validé avant l'implémentation, et son bilan y est rédigé (écarts à la spec, dette tracée, identifiants couverts) ;
- toutes ses fonctionnalités satisfont §51.1 ;
- ses critères d'acceptation (§47.2) sont verts, e2e compris sur `main` ;
- la démonstration du sprint passe sur un Compose local neuf (`docker compose down -v` puis `up -d`) ;
- aucune dette n'est laissée sans issue tracée, et aucun test en quarantaine sans issue.

### 51.3 Écart à la spec

Toute divergence entre le code et la spec se résout **avant** la fin du sprint : soit le code est corrigé, soit la spec est mise à jour dans `docs/spec/`, avec un ADR si la décision est structurante ou verrouillée (Partie IX §53–§54). Aucun écart implicite n'est accepté.

---

## 52. Critères de mise en production — check-list de gating

**Règle** : la mise en production est décidée quand **toutes** les lignes sont cochées dans `docs/go-live.md`, chacune avec sa preuve (lien de run CI, extrait de `/api/health`, entrée de `docs/measurements.md`, date). Une mesure hors critère bloque, sauf ADR qui ajuste la cible (VII §45.4). La décision consigne le sha, la date et la durée de pré-production.

### A. Qualité

| # | Critère | Preuve |
|---|---|---|
| A1 | CI verte sur le sha déployé, étape 6 comprise, et nightly verte depuis au moins 7 jours | liens des runs |
| A2 | Catalogue complet : chaque identifiant U, I, E ou F couvert et vert ; chaque identifiant M consigné (T-RES-09, T-RES-11, T-RES-12) | `check-test-catalog`, `go-live.md` |
| A3 | Aucune exception d'audit expirée ; aucun test en quarantaine | `.audit-exceptions.yaml`, CI |

### B. Fonctionnel — sur l'instance de pré-production, données réelles

| # | Critère | Preuve |
|---|---|---|
| B1 | Ingestion automatique de toutes les sources activées de `sources.yaml`, pour les types présents (`rss`, `github`, `hackernews`, `reddit`, `youtube`, `webpage`) ; aucune source en disjoncteur ouvert sans cause identifiée | `/api/health` (`sources`) |
| B2 | Normalisation, dédup exacte et relevance : invariant de compteurs tenu sur les `CollectorRun` des 24 dernières heures | requête de contrôle |
| B3 | Events et hotness : au moins un Event multi-sources, affiché une seule fois dans l'Overview, badge corroboré | capture du dashboard |
| B4 | Topics et entités `keyword` sur les articles `ready` ; `llm` en plus si un gateway est configuré | dashboard |
| B5 | Résumés : repli présent sur tout article `ready` ; enrichis si un gateway est configuré | dashboard |
| B6 | Tendances : Signal horaire calculé, `trends_last_run` à jour, `NULL` affiché « données insuffisantes » pendant le cold start | `/api/health` |
| B7 | Émergence : warm-up terminé ; job analytique exécuté sans erreur depuis au moins 24 h | `/api/health` |
| B8 | Dashboard : toutes les vues ; recherche plein texte ; filtres ; lu / non lu ; préférences | parcours manuel consigné |
| B9 | Alertes : au moins un digest et un `send-test-alert` reçus sur chaque canal configuré | `go-live.md` |
| B10 | Produit sans LLM : T-RES-02 vert | CI |

### C. Résilience

| # | Critère | Preuve |
|---|---|---|
| C1 | Les six tests de la Partie I, tableau §50.6, colonne automatisée : verts | CI |
| C2 | Reboot réel du VPS : T-RES-09 (M10) dans son critère | `measurements.md` |
| C3 | Restauration complète sur machine neuve : T-RES-11 (M7) dans son critère | `backup-restore.md`, `measurements.md` |

### D. Infrastructure & sécurité

| # | Critère | Preuve |
|---|---|---|
| D1 | Compose de production : `caddy`, `app`, `worker` permanents (+ `gateway` en profil), `migrate` one-shot, `restart: unless-stopped` | `docker compose ps` |
| D2 | HTTPS : certificat Let's Encrypt valide, redirection HTTP → HTTPS, DNS A (et AAAA) en place | navigateur, `curl -I` |
| D3 | SQLite : WAL actif, `journal_size_limit` posé, volume local | `app.cli health` |
| D4 | `/health = ok` ; aucune condition active sans cause comprise | `/health`, `/api/health` |
| D5 | Logs JSON avec rotation (10 Mo × 5 par service), `DEBUG` inactif | `docker inspect`, logs |
| D6 | `mem_limit` fixés sur `worker` (et `gateway`) à pic M1 × 1,5 | `docker-compose.yml` |
| D7 | Racine en lecture seule validée sur le VPS (T-SEC-09 rejoué sur place) | `go-live.md` |
| D8 | Hôte durci (VII §43.1) : SSH par clé, `PermitRootLogin no`, pare-feu (SSH, 80, 443/tcp, 443/udp), mises à jour de sécurité automatiques ; seul `caddy` publie des ports | `go-live.md` |
| D9 | `.env` en `600`, copie de référence hors VPS avec `RESTIC_PASSWORD` | `go-live.md` |

### E. Exploitation

| # | Critère | Preuve |
|---|---|---|
| E1 | Au moins un canal d'alerte configuré, `send-test-alert` réussi ; routage du type `system` vers ce canal | `go-live.md` |
| E2 | Dépôt restic configuré ; un backup réussi et un `restore-test` réussi | `/api/health` (`backup`) |
| E3 | Exercice complet de restauration manuel réalisé (C3) | `backup-restore.md` |
| E4 | Monitoring externe configuré (5 min, 2 échecs consécutifs) et testé par l'arrêt d'`app` (T-RES-12) ; surveillance du certificat si le service la propose | `monitoring.md` |
| E5 | Déploiement effectué par `scripts/deploy.sh`, rollback testé une fois (redéploiement du sha précédent) | `~/radar-deploy.log` |

### F. Mesures & calibration

| # | Critère | Preuve |
|---|---|---|
| F1 | M1 à M10 consignés dans `docs/measurements.md`, chacun dans son critère ou couvert par un ADR | `measurements.md` |
| F2 | Calibration `cluster-calibrate` réalisée sur données réelles ; échantillons relus ; seuils retenus committés dans `pipeline.yaml` ; décision de conservation ou de remise à zéro de la base consignée (décision 19) | `measurements.md`, `go-live.md` |
| F3 | Si un gateway est configuré : M6 validée contre le gateway retenu | `measurements.md` |
| F4 | Seuils marqués ⚖ (VII §39.4) recalés d'après M3 | `pipeline.yaml` |

### G. Critères « c'est atteint » de la Partie I §4.3

| # | Qualité | Preuve |
|---|---|---|
| G1 | **Simple** : ≤ 3–4 services permanents, démarrage en une commande | D1 |
| G2 | **Portable** : migration de VPS = backup + `.env` + `docker compose up -d`, sans modification de code | C3 |
| G3 | **Observable** : tout incident majeur détectable via `/health` ou une alerte, sans SSH | T-OPS-06, T-OPS-12, E4 |
| G4 | **Résilient** : tableau §50.6 vert | C1 à C3 |
| G5 | **Low-cost** : coût mensuel estimé ≤ 12 €, détaillé par poste | `go-live.md` |
| G6 | **Provider-independent** : changement de provider par les seules variables `LLM_*` | T-LLM-19 |

### H. Documentation

| # | Critère |
|---|---|
| H1 | Présents et à jour : `docs/architecture.md`, `database.md`, `collectors.md`, `trends.md`, `deployment.md`, `monitoring.md`, `backup-restore.md`, `measurements.md`, `runbook.md`, `testing.md`, `go-live.md`, et `llm-gateway.md` si un gateway est utilisé |
| H2 | ADR présents pour les décisions verrouillées et celles désignées en Parties VII et VIII |
| H3 | Spec dans `docs/spec/` conforme au code déployé (§51.3) |

---

## Points d'interprétation

**Tranchés dans cette partie** (l'implémenteur n'a pas à choisir) :
- arborescence de premier niveau et fichiers nommés ;
- plan des sprints et critères d'acceptation ;
- contraintes de dépendance ;
- workflows, étapes CI, ordre et blocage ;
- politique d'audit ;
- mécanisme de déploiement et son verrou ;
- horloge injectable et blocage réseau ;
- identifiants et traçabilité du catalogue ;
- doubles de test ;
- DoD ;
- check-list de mise en production et lieu de consignation.

**Laissés à l'implémenteur, sans impact sur le contrat** :
- outils exacts d'analyse de secrets et d'audit (gitleaks ou équivalent, `pip-audit` ou équivalent) ;
- bibliothèque de blocage réseau et de serveurs de test ;
- configuration de vitest et d'eslint au-delà des règles imposées ;
- stratégie de cache de la CI ;
- organisation interne des modules de `app/` ;
- forme de `docs/go-live.md` tant qu'il couvre le §52.

**Décisions à poids réel, prises par défaut puis validées avec la partie** (Partie IX décision 12) :
1. Pré-production d'au moins 14 jours avant la décision (décision 18).
2. Instance de pré-production = instance de production, base conservée à la bascule (décision 19).
3. Gateway LLM non requis pour la mise en production (décision 21).
4. Spec dans `docs/spec/`, `SPEC.md` en index, identifiants extraits de la spec par la CI (décision 22).
5. `HTTP_TEST_ALLOW_HOSTS` réservé à `APP_ENV=test`, refus de démarrer en production (décision 23).
6. `scripts/restore.sh` qui outille la procédure VII §38.5 (décision 24).
7. Jeton GitHub de lecture pour `deploy.sh` si le dépôt est privé, hors `.env` et hors conteneurs (§49.5).
8. Watchdog avancé au Sprint 1 (décision 5).

---

## Reporté en V2 (tracé depuis la Partie VIII)

- **Déploiement continu** : `GitHub → CI → image publiée dans un registre → VPS → déploiement → contrôle de santé` (déjà reporté par la V0.3 §49 et la Partie VII).
- **Tests navigateur de bout en bout** (Playwright ou équivalent).
- **Benchmarks de régression de performance en CI** sur une machine de référence.
- **Environnement de staging distinct** de la production.
- **Seuil de couverture bloquant**, si la traçabilité du catalogue s'avère insuffisante.
- **Reconstruction et redéploiement automatiques** des images sur correctif de sécurité.
- **Enregistrement automatisé et périodique** des fixtures LLM contre le gateway retenu.
