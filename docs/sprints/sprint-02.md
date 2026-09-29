# Sprint 2 — Collecte & pipeline déterministe

Statut : planifié

> Plan rédigé le 2026-09-29 (#105), à valider par le propriétaire avant toute implémentation (IX §57.8, VIII §47.1,
> #19). Contenu et acceptation : **VIII §47.2, Sprint 2** ; ce plan les découpe en tâches et ne les redéfinit pas.
> Format : `docs/architecture.md` P-11 (statut, identifiants visés avec volets). Traçabilité : P-15, les identifiants
> de ce sprint sont signalés sans bloquer tant qu'il n'est pas clos.

## Objectif

Ingestion complète des six types de sources, sans LLM ni clustering (planning, fiche S2) : `HttpClient` partagé,
collectors et registre, runner jusqu'au résumé de repli, pilotage (disjoncteur, scheduler), validation complète des
fichiers `config/`, faux serveur de sources. Les `enrich_article` sont créés et restent `pending` jusqu'au Sprint 5
(E7).

## Prérequis

- **Sprint 1 clos** : `sprint-01.md` en `Statut : clos` (#104, fusionnée).
- **Gate G2** franchie : démonstration sur Compose neuf et clôture par le propriétaire (#18).
- **Checks obligatoires** sur `main` : étapes 1 à 5 de la CI rendues obligatoires (#39).
- **Plan validé** : ce fichier passe de « planifié » à « en cours » dans la PR qui ouvre le sprint.
- 👤 En parallèle : curation du `config/` réel (planning, fiche S2), sans effet sur ce plan.

## Ordre et contraintes

Contraintes de VIII §48 appliquées au sprint :

- **D3** — les tables du sprint arrivent par migration avant le code qui les écrit : T2.2.
- **D4** — doubles de test avant le premier collector : faux serveur de sources en T2.4 (le blocage réseau est en place
  depuis T1.1).
- **D5** — `HttpClient` partagé, garde anti-SSRF comprise, avant tout collector : T2.5.
- **D6** — runner et écriture par page avant tout collector autre que `rss` : T2.7 (runner et `rss`), puis T2.9.
- **D7 amorcé** — liaisons `keyword` et `entities.yaml` : T2.6 (étages purs) et T2.7 (écriture).
- **D11** — `trends_since` posé dès la première insertion `ready` : T2.7.

```
T2.1 ─► T2.2 ─► T2.3 ─► T2.4 ─► T2.5 ─► T2.6 ─► T2.7 ─► T2.8 ─► T2.9 ─► T2.10 ─► T2.11 ─► T2.13
(dette)  (tables) (config) (D4)   (D5)   (pur)   (D6)  (extract.) (types) (pilotage)  (e2e)   (docs)
T2.12 (skill radar-dev V1) : indépendante, avant T2.11.
```

## Tâches

### T2.1 — Dette du Sprint 1

- **Objectif** : solder les reports de #19 qui précèdent le code du sprint.
- **Fichiers** :
  - `docs/database.md` §3 : les sept lignes qui indiquent encore `JSON` (`Source.config`, `Source.checkpoint`,
    `Article.metrics`, `Topic.keywords`, `EmergingCandidate.evidence`, `EmergingCandidate.suggested_keywords`,
    `Setting.value`) passent à `JSONText`, conformément à §1.1 (décision du 2026-09-26) ;
  - `.github/workflows/ci.yml` : `cancel-in-progress` limité hors de `main` (revue de #101) ;
  - `app/ops/health.py` : un heartbeat dont `at` est sans fuseau donne `down`, pas une erreur 500 (revue de #95).
- **Dépendances** : aucune.
- **Identifiants** : T-OPS-02 (le cas s'ajoute aux tests existants, sans nouvel identifiant).
- **Vérifiable** : `database.md` §3 ne cite plus `JSON` comme type SQLAlchemy ; la CI de `main` ne s'annule plus
  elle-même ; un test fait lire un heartbeat sans fuseau et obtient `down`.

### T2.2 — Migrations du sprint : `Source`, `Article`, `CollectorRun`, taxonomie, liaisons, `AIJob` (D3)

- **Objectif** : les tables du Sprint 2 de `database.md` §3.1, par migration Alembic (`render_as_batch`), avec
  `downgrade` ou en-tête « irréversible ».
- **Fichiers** : `app/db/models.py`, `migrations/versions/…` : `Source`, `Article` (sans `event_id` ni
  `duplicate_of_id`, ajoutés au Sprint 4 ; `CHECK` de `status` avec `duplicate` dès maintenant), `CollectorRun`,
  `Topic`, `Entity`, `ArticleTopic`, `ArticleEntity`, `AIJob` (table complète, index compris, E7) ; `docs/database.md`
  si un détail change.
- **Dépendances** : T2.1 (types JSON alignés).
- **Identifiants** : **T-DB-12 [article-status]** ; T-DB-08 (chaque migration du sprint a son `downgrade` testé).
- **Vérifiable** : `upgrade head` depuis une base vide et `downgrade` testés ; `compare_metadata` sans différence ;
  une valeur hors `CHECK` de `Article.status` est refusée.

### T2.3 — Configuration : `pipeline.yaml` du périmètre IV, reports de validation, `HTTP_TEST_ALLOW_HOSTS`

- **Objectif** : valider les sections de `pipeline.yaml` du périmètre IV (IV §16.6) et les reports de T1.5, sans
  encore le registre des collectors.
- **Fichiers** : `app/core/config_files.py`, `app/core/config.py`, `config/pipeline.yaml`, tests.
  - sections IV §16.6 : `collectors`, `normalization`, `language`, `dedup`, `relevance`, `summary`, `extraction`,
    `http`, `breaker`, `scheduler`, avec leurs défauts ;
  - reports de la revue de #93 (#19) : durées strictement positives ; schéma http ou https de `SourceSpec.url` ;
    défaut de `github_reserved_paths` sur la liste de IV §16.4 ; clé YAML non hachable en `ConfigError` ;
  - `HTTP_TEST_ALLOW_HOSTS` renseignée avec `APP_ENV=production` : le worker refuse de démarrer (VIII décision 23).
- **Dépendances** : T2.2.
- **Identifiants** : **T-CFG-04 [collectors, normalization, relevance, extraction, http]** ; **T-CFG-09** ;
  **T-CFG-03** (voir l'écart relevé dans la PR du plan : son objet, `clustering.*` et `llm.delay.enrich_article`,
  n'existe pas au Sprint 2).
- **Vérifiable** : chaque section refuse une valeur invalide avec fichier, clé et champ ; `pipeline.yaml` absent donne
  les défauts ; `0s` est refusé ; le worker refuse de démarrer sur `HTTP_TEST_ALLOW_HOSTS` en production.

### T2.4 — Faux serveur de sources et fixtures par type (D4)

- **Objectif** : le double qui remplace toute source réelle, avant le premier collector (VIII §50.4).
- **Fichiers** : `tests/fakes/fake_sources.py` (comportements scriptables : fixtures par type, 304, 401, 403 avec et
  sans `x-ratelimit-remaining: 0`, 404, 410, 429, 5xx, timeout, redirections dont vers une adresse privée, corps trop
  gros, `Content-Type` non HTML, pagination interruptible, `robots.txt`) ; `tests/fixtures/sources/<type>/` ;
  arrêt propre sur SIGTERM des doubles (revue de #101, #19) ; `docs/testing.md` (section « Doubles »).
- **Dépendances** : T2.3.
- **Identifiants** : aucun en propre ; il sert T-HTTP-*, T-COL-* et T-RES-04.
- **Vérifiable** : chaque comportement est joignable par un test sur `127.0.0.1` ; le double s'arrête sur SIGTERM sans
  attendre le délai de Docker.

### T2.5 — `HttpClient` partagé (D5)

- **Objectif** : le seul client HTTP du worker (IV §21), anti-SSRF compris, avant tout collector.
- **Fichiers** : `app/http/…` : limiteur par hôte, retry et backoff avec jitter (horloge injectée), `Retry-After`,
  quota (en-têtes GitHub et Reddit), anti-SSRF après résolution DNS et à chaque redirection, liste d'hôtes de test lue
  seulement en `APP_ENV=test`, `robots.txt` avec cache de 24 h, User-Agent (IV §17.3), nettoyage des secrets de niveau
  2 (VII §42.4).
- **Dépendances** : T2.4.
- **Identifiants** : **T-HTTP-01** à **T-HTTP-09**.
- **Vérifiable** : tous les T-HTTP-* verts contre le faux serveur, sans `sleep` réel ; la garde refuse `127.0.0.1` sans
  la liste de test (T-HTTP-08). La résolution DNS des tests passe par un résolveur injecté, jamais par un nom d'hôte
  externe (`testing.md`, « Blocage réseau »).

### T2.6 — Étages purs du pipeline

- **Objectif** : les étages purs (IV §14.1), testés par tables de cas, sans réseau ni base (VIII §50.1).
- **Fichiers** : `app/pipeline/…` : normalisation (IV §18.1, §18.2), canonicalisation d'URL (§18.3), dates (§18.4),
  langue (lingua, §18.5), `content_hash` (§19.2), relevance filter (§20), entités `keyword` et motif `owner/repo`
  (§16.4), résumé de repli (§14.5) ; `pyproject.toml` (lingua épinglé).
- **Dépendances** : T2.3 (réglages `normalization`, `language`, `relevance`, `summary`).
- **Identifiants** : **T-PIPE-01** à **T-PIPE-05**, **T-PIPE-08**, **T-PIPE-09**, **T-PIPE-11**, **T-PIPE-12**,
  **T-COL-13**.
- **Vérifiable** : les tables de cas de IV §18 à §20 passent, sans base ni réseau.

### T2.7 — Registre, runner, écriture par page et collector `rss` (D6, D7, D11)

- **Objectif** : l'interface `Collector` par pages, le registre (canal par type), et le runner qui écrit une
  transaction par page, avec le premier collector.
- **Fichiers** : `app/collectors/base.py`, `registry.py`, `rss.py` ; `app/pipeline/runner.py` : contrôle d'âge,
  dédup exacte en base et filet `ON CONFLICT`, liaisons `keyword` sur le texte final, purge immédiate du contenu des
  `filtered` (IV §14.3), checkpoint dans la transaction de la page, `CollectorRun` et invariant de compteurs, premier
  run plafonné, `trends_since` à la première insertion `ready` (D11), un `enrich_article` par `ready` (E7) ;
  `app/db/session.py` : docstring de `run_write` sur les unités sans effet hors base, et règle « jamais d'écriture par
  `read_session` » tenue dès ce premier usage métier (revue de #91, #19) ; validation `config` par le collector.
- **Dépendances** : T2.5, T2.6.
- **Identifiants** : **T-PIPE-06**, **T-PIPE-07**, **T-PIPE-10** ; **T-COL-01** (type `rss`) ; **T-COL-02** à
  **T-COL-07** ; **T-COL-11**, **T-COL-12** ; **T-CFG-02 [collectors]** (type inconnu, `poll_interval` sous le
  minimum du type, `config` refusée par le collector).
- **Vérifiable** : un run `rss` contre le faux serveur écrit ses articles ; un rejeu ne crée aucun doublon ;
  l'invariant de compteurs tient ; une interruption en milieu de pagination reprend sans doublon ; le double HTTP
  échoue s'il est appelé pendant une `write_session`.

### T2.8 — Extraction ciblée

- **Objectif** : l'extraction du contenu complet des articles `ready` (IV §17), par le `HttpClient`.
- **Fichiers** : `app/pipeline/extraction.py` (déclencheurs, cible `link_url` pour HN et Reddit, denylist,
  remplacement seulement si plus long, garde-fous de taille, de redirections et de `robots.txt`) ; dépendance
  d'extraction épinglée.
- **Dépendances** : T2.7.
- **Identifiants** : **T-COL-08**.
- **Vérifiable** : chaque déclencheur et chaque garde-fou de T-COL-08 est vérifié contre le faux serveur.

### T2.9 — Collectors `github`, `hackernews`, `reddit`, `youtube`, `webpage`

- **Objectif** : les cinq autres types (IV §15), sur le runner de T2.7.
- **Fichiers** : `app/collectors/github.py`, `hackernews.py`, `reddit.py`, `youtube.py`, `webpage.py` ; fixtures
  associées ; nettoyage du jeton GitHub dans les logs du client (VII §42.4).
- **Dépendances** : T2.7, T2.8.
- **Identifiants** : **T-COL-01** (types `github`, `hackernews`, `reddit`, `youtube`, `webpage`) ;
  **T-SEC-01 [github]**.
- **Vérifiable** : chaque type collecte ses fixtures ; `webpage` avec gabarit cassé écarte ses items sans exception ;
  le jeton factice `FAKE-…` n'apparaît dans aucun log.

### T2.10 — Pilotage : disjoncteur, scheduler, credentials, boot et arrêt du worker

- **Objectif** : planifier et protéger la collecte (IV §21.5, §21.6), et étendre la séquence de boot et l'arrêt du
  worker au scheduler (VII §36.6).
- **Fichiers** : `app/scheduler/…` (APScheduler 3.x, `AsyncIOScheduler`, V-07 : jitter de démarrage, `coalesce`,
  `max_instances=1`, sauts de run sans `CollectorRun`, rattrapage des misfires) ; disjoncteur par source ;
  vérification des credentials par type ; `app/worker.py` : scheduler en dernière étape du boot, tâche permanente
  supervisée, arrêt sur SIGTERM sans nouveau run et attente des runs en cours ≤ 20 s ; comportement défini et testé
  d'un SIGTERM reçu pendant les vérifications de boot (revue de #94, #19).
- **Dépendances** : T2.9.
- **Identifiants** : **T-COL-09**, **T-COL-10** ; **T-CFG-06** ; **T-OPS-16** ; **T-OPS-08 [scheduler]** ;
  **T-OPS-10 [scheduler]** ; **T-OPS-11 [runs]**.
- **Vérifiable** : les ticks du scheduler s'appellent directement avec la `Clock` (VIII §50.1) ; une source sans
  credentials n'est pas planifiée et le worker démarre ; un scheduler en exception arrête le worker ; SIGTERM laisse
  finir les runs en cours dans le délai.

### T2.11 — e2e du sprint et démonstration

- **Objectif** : l'acceptation de VIII §47.2 sur la stack Compose, par `radar-dev e2e` et l'étape 6 de la CI.
- **Fichiers** : `docker-compose.test.yml` (faux serveur scripté, `HTTP_TEST_ALLOW_HOSTS`, configuration des sources
  pointée vers le faux serveur), `tests/e2e/…`.
- **Dépendances** : T2.10.
- **Identifiants** : **T-RES-04** ; **T-SEC-09 [lingua]**.
- **Vérifiable** : les six types collectés contre le faux serveur ; rejeu sans doublon ; invariant de compteurs sur
  chaque run ; une source en 5xx ou en timeout n'arrête pas les autres, son disjoncteur s'ouvre et elle reprend ;
  lingua fonctionne sur racine en lecture seule.

### T2.12 — `radar-dev` V1 : skill de projet (#63)

- **Objectif** : le skill `.claude/skills/radar-dev/SKILL.md` de #63 (E22).
- **Fichiers** : `.claude/skills/radar-dev/SKILL.md` ; `docs/testing.md` si un renvoi manque.
- **Dépendances** : aucune dans le sprint ; à livrer avant T2.11, qui s'en sert pour diagnostiquer l'e2e.
- **Identifiants** : aucun.
- **Vérifiable** : les critères de #63. Les sous-commandes que la revue de #102 propose d'évaluer (`restart`,
  `alembic current`, `caddy hash-password`, `logs -f`) relèvent de l'écart signalé dans la PR du plan.

### T2.13 — Documentation du sprint

- **Objectif** : les documents que IX §55.4 prévoit au Sprint 2, et ceux que le sprint modifie.
- **Fichiers** : `docs/collectors.md` (types, configuration, ajout d'une source ou d'un collector, Partie I §2.4) ;
  `docs/testing.md` (fixtures, faux serveur) ; `docs/runbook.md` (procédure de rafraîchissement des images de base
  épinglées par digest, revue de #101, #19 ; toute nouvelle commande) ; `docs/architecture.md` et `database.md` si le
  code s'écarte de la proposition.
- **Dépendances** : T2.11.
- **Identifiants** : aucun.
- **Vérifiable** : les documents renvoient à la spec sans la recopier ; les liens internes sont valides.

## Tableau récapitulatif

| # | Tâche | Dépend de | Identifiants |
|---|---|---|---|
| T2.1 | Dette du Sprint 1 | — | (T-OPS-02, cas ajouté) |
| T2.2 | Migrations du sprint | T2.1 | T-DB-12 [article-status] |
| T2.3 | Configuration | T2.2 | T-CFG-03 · T-CFG-04 [collectors, normalization, relevance, extraction, http] · T-CFG-09 |
| T2.4 | Faux serveur de sources | T2.3 | — |
| T2.5 | `HttpClient` partagé | T2.4 | T-HTTP-01 à 09 |
| T2.6 | Étages purs | T2.3 | T-PIPE-01 à 05, 08, 09, 11, 12 · T-COL-13 |
| T2.7 | Registre, runner, `rss` | T2.5, T2.6 | T-PIPE-06, 07, 10 · T-COL-01 (`rss`), 02 à 07, 11, 12 · T-CFG-02 [collectors] |
| T2.8 | Extraction ciblée | T2.7 | T-COL-08 |
| T2.9 | Cinq autres collectors | T2.7, T2.8 | T-COL-01 (autres types) · T-SEC-01 [github] |
| T2.10 | Pilotage, boot et arrêt | T2.9 | T-COL-09, 10 · T-CFG-06 · T-OPS-16 · T-OPS-08 [scheduler] · T-OPS-10 [scheduler] · T-OPS-11 [runs] |
| T2.11 | e2e et démonstration | T2.10 | T-RES-04 · T-SEC-09 [lingua] |
| T2.12 | Skill `radar-dev` V1 | — | — |
| T2.13 | Documentation | T2.11 | — |

## Identifiants visés

Liste de VIII §47.2, Sprint 2, et volets reportés du Sprint 1 (P-11). Un identifiant sans crochets est visé en entier.

```
T-PIPE-01        T2.6
T-PIPE-02        T2.6
T-PIPE-03        T2.6
T-PIPE-04        T2.6
T-PIPE-05        T2.6
T-PIPE-06        T2.7
T-PIPE-07        T2.7
T-PIPE-08        T2.6
T-PIPE-09        T2.6
T-PIPE-10        T2.7
T-PIPE-11        T2.6
T-PIPE-12        T2.6
T-HTTP-01        T2.5
T-HTTP-02        T2.5
T-HTTP-03        T2.5
T-HTTP-04        T2.5
T-HTTP-05        T2.5
T-HTTP-06        T2.5
T-HTTP-07        T2.5
T-HTTP-08        T2.5
T-HTTP-09        T2.5
T-COL-01         T2.7, T2.9   (rss, puis les cinq autres types)
T-COL-02         T2.7
T-COL-03         T2.7
T-COL-04         T2.7
T-COL-05         T2.7
T-COL-06         T2.7
T-COL-07         T2.7
T-COL-08         T2.8
T-COL-09         T2.10
T-COL-10         T2.10
T-COL-11         T2.7
T-COL-12         T2.7
T-COL-13         T2.6
T-CFG-02 [collectors]                    T2.7   (volet schemas : Sprint 1)
T-CFG-03         T2.3   (écart relevé dans la PR du plan)
T-CFG-04 [collectors, normalization, relevance, extraction, http]   T2.3   (autres sections : leur sprint ; complet au Sprint 11)
T-CFG-05         T1.6   (couvert au Sprint 1, relisté par VIII §47.2)
T-CFG-06         T2.10
T-CFG-09         T2.3
T-DB-12 [article-status]                 T2.2   (AIJob.status : Sprint 5 ; AlertLog.status : Sprint 10)
T-OPS-16         T2.10
T-RES-04         T2.11
T-OPS-08 [scheduler]                     T2.10  (volet reporté du Sprint 1)
T-OPS-10 [scheduler]                     T2.10  (volet reporté du Sprint 1)
T-OPS-11 [runs]                          T2.10  (volet reporté du Sprint 1)
T-SEC-01 [github]                        T2.9   (volet reporté du Sprint 1)
T-SEC-09 [lingua]                        T2.11  (volet reporté du Sprint 1)
```

## Volets reportés du Sprint 1

Règle : VIII §50.3. Sort des volets que `sprint-01.md` pressentait au Sprint 2 :

| Identifiant | Volet | Sort au Sprint 2 |
|---|---|---|
| T-CFG-02 | collectors | visé, T2.7 (le registre porte les minimums et la validation de `config`) |
| T-OPS-08 | scheduler | visé, T2.10 |
| T-OPS-10 | scheduler | visé, T2.10 |
| T-OPS-11 | runs | visé, T2.10 |
| T-SEC-01 | github | visé, T2.9 |
| T-SEC-09 | lingua | visé, T2.11 (e2e sur racine en lecture seule) |

Les autres volets de `sprint-01.md` restent aux sprints pressentis : T-DB-13 [rebuild] (3), T-OPS-08 [embeddings,
boucle-ai, job-failing] (4, 5, 11), T-OPS-09 [modeles] (4), T-OPS-10 [modeles-matrice, requalification-jobs,
requalification-alertes] (4, 5, 10), T-OPS-11 [jobs] (5), T-SEC-01 [llm, alertes, restic] (6, 10, 11), T-SEC-09
[onnxruntime, restic] (4, 11).

## Dette reportée sur #19

| Commentaire de #19 | Point | Sort |
|---|---|---|
| revue de #92 | sept lignes `JSON` de `database.md` §3 | T2.1, avant la migration de `Source` (T2.2) |
| revue de #93 | durées strictement positives et minimum de `poll_interval` par type | T2.3 (durées) et T2.7 (minimum par type, avec le registre) |
| revue de #93 | schéma http ou https de `SourceSpec.url` | T2.3 |
| revue de #93 | défaut de `github_reserved_paths` | T2.3 |
| revue de #93 | clé YAML non hachable en `ConfigError` | T2.3 |
| revue de #101 | concurrence de la CI (`cancel-in-progress` sur `main`) | T2.1 |
| revue de #101 | rafraîchissement des images de base épinglées par digest | T2.13 (procédure documentée dans le runbook) ; un outillage automatique reste une option, à décider |
| revue de #101 | doubles qui ignorent SIGTERM | T2.4 |
| revue de #104 (#91) | docstring de `run_write`, règle d'écriture de `read_session` | T2.7 (premier usage métier) |
| revue de #104 (#95) | heartbeat sans fuseau dans `HealthChecker` | T2.1 |
| revue de #104 (#94) | SIGTERM pendant les vérifications de boot | T2.10 (avec l'extension du boot au scheduler) |

## Critères d'acceptation

Ceux de **VIII §47.2, Sprint 2**, sans ajout :

- avec le `config/` de démonstration, le worker collecte les six types contre le faux serveur ;
- un rejeu complet ne crée aucun doublon ;
- l'invariant de compteurs tient sur chaque run ;
- une source en panne n'arrête pas les autres ;
- identifiants de tests de VIII §47.2 (liste ci-dessus) couverts.

S'y ajoutent la DoD de sprint (VIII §51.2) et les règles de sortie communes du planning (§0).

## Issues à créer à la validation du plan

Milestone **S2**, labels `qui:claude` et `type:tâche`, une issue par tâche. Aucune n'est créée par ce plan.

| Titre | Tâche |
|---|---|
| S2 · T2.1 — Dette du Sprint 1 : types JSON de database.md, concurrence de la CI, heartbeat sans fuseau | T2.1 |
| S2 · T2.2 — Migrations : Source, Article, CollectorRun, taxonomie, liaisons, AIJob | T2.2 |
| S2 · T2.3 — Configuration : pipeline.yaml du périmètre IV, reports de validation, HTTP_TEST_ALLOW_HOSTS | T2.3 |
| S2 · T2.4 — Faux serveur de sources et fixtures par type | T2.4 |
| S2 · T2.5 — HttpClient partagé : limiteur, retry, Retry-After, quota, anti-SSRF, robots.txt | T2.5 |
| S2 · T2.6 — Étages purs du pipeline : normalisation, dates, langue, dédup, relevance, résumé | T2.6 |
| S2 · T2.7 — Registre, runner, écriture par page et collector rss | T2.7 |
| S2 · T2.8 — Extraction ciblée | T2.8 |
| S2 · T2.9 — Collectors github, hackernews, reddit, youtube, webpage | T2.9 |
| S2 · T2.10 — Pilotage : disjoncteur, scheduler, credentials, boot et arrêt du worker | T2.10 |
| S2 · T2.11 — e2e du sprint et démonstration | T2.11 |
| *(existe : #63)* S2 · radar-dev V1 : skill de projet pour l'environnement local | T2.12 |
| S2 · T2.13 — Documentation : collectors.md, testing.md, runbook | T2.13 |

## Bilan

*À remplir en fin de sprint : écarts à la spec, dette tracée, identifiants couverts, sessions consommées.*
