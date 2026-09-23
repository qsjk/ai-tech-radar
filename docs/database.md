# Modèle de données — SQLite

> Tâche T0.4 (#7), rédigée le 2026-09-23 sur la spec arbitrée par T0.2b (#67).
> Document de référence des migrations Alembic de chaque sprint (Partie IX §55.4, Partie VIII §47.1).
> Il **rassemble** ce que la spec fixe, sans rien trancher : la spec fait foi, et tout écart relevé entre ses parties
> est listé au §7, sans arbitrage.

Références : `docs/spec/partie-<N>.md` est abrégé en « <N> » (par exemple « III §11.2 »). Les décisions du rapport
de cadrage (`docs/sprints/sprint-00-cadrage.md`) sont citées par leur identifiant (E7, CF-15…).

**Règles de lecture des tableaux de colonnes**

- **Null** : `non` ou `oui` quand la spec le dit ; **`n. p.`** (non précisé) sinon. Les colonnes `n. p.` sont
  recensées au §7 : leur nullabilité est à fixer avant la migration qui les crée.
- **Défaut** : seulement les défauts écrits dans la spec ; `—` sinon.
- **Sprint** : sprint de la migration qui crée la colonne, l'index ou le trigger. Il découle du contenu des sprints
  (VIII §47.2) et des arbitrages (E7) ; quand la spec ne le dit pas explicitement, la justification figure sous le
  tableau.
- Les blocs SQL sont **indicatifs** : ils décrivent la cible, ce ne sont pas des migrations (IX §57.6). Les noms de
  tables en SQL suivent ceux que la spec emploie dans ses requêtes (`article`, `aijob`, `embedding`, `article_fts`) ;
  pour les autres tables, le nom `snake_case` est une **proposition**.

---

## 1. Conventions

### 1.1 Clés, horodatage, JSON

- **Clé primaire** : `id INTEGER PRIMARY KEY` partout, sauf les tables de liaison (clé composite) et les tables
  clé/valeur `Setting` et `SystemState` (clé texte) (III §11.0).
- **Horodatage** : `created_at` et, pour les tables modifiables, `updated_at`, de type `UTCDateTime` (III §11.0,
  §10.6). La spec ne dresse pas la liste des tables « modifiables » : les tableaux ci-dessous ne reprennent
  `created_at` et `updated_at` que là où la spec les nomme ou les utilise, et signalent les autres cas (§7, I-02).
- **JSON** : colonne texte JSON (`JSON` côté SQLAlchemy, `TEXT` en SQLite), **validée par un schéma Pydantic à
  l'écriture** (III §11.0). JSON1 est un prérequis vérifié au démarrage (III §10.1).
- **`NULL` = inconnu.** Jamais de valeur inventée par défaut : un quota inconnu est `NULL`, pas `0` (III §11.0).
- **Booléens** : `BOOLEAN` SQLAlchemy, stocké en `INTEGER` 0 / 1 par SQLite (la requête de V-B §28.2 compare
  `clustered_semantic = 0`).

### 1.2 Énumérations

Deux sortes (III §11.0) :

| Sorte | Exemples | Contrôle |
|---|---|---|
| **Machine à états** (fermée) | `status`, `*_origin`, `method`, `relevance`, `extract`, `kind`, `period`, `category`, `channel`, `decision`… | contrainte **`CHECK`** en base |
| **Catégorie extensible** | `Source.type`, `Entity.type`, `AIJob.job_type`, `AIJob.entity_type`, `AIJob.skip_reason` | **validée par le code** (registre), sans `CHECK` : l'étendre ne demande pas de migration |

Ajouter une valeur à un `CHECK` est une migration (reconstruction de la table par `render_as_batch`, §5).

### 1.3 Suppressions et clés étrangères

- **`ON DELETE RESTRICT`** par défaut, avec `PRAGMA foreign_keys=ON` sur chaque connexion (§2.2).
- **Exceptions** : les tables de liaison (`ArticleTopic`, `ArticleEntity`) et `Embedding` suivent la suppression de
  leur article (**`CASCADE`**) (III §11.0).
- Aucune donnée métier n'est supprimée hors des règles de rétention (§6, III §13).
- `AIJob.entity_id` n'a **pas** de clé étrangère : sa cible est polymorphe (III §11.10).

### 1.4 Propriétaire en écriture

Chaque table a **un seul processus écrivain** (II §8.3, III §11.0).

| Table | Écrivain | Lecteurs | Remarque |
|---|---|---|---|
| `Source` | worker | app | upsert depuis `sources.yaml` au démarrage, état de collecte (IV §16.2) |
| `Article` | worker | app | tout le cycle de `status` |
| `CollectorRun` | worker | app | |
| `Topic` | worker | app | y compris les topics `user` créés sur décision de l'app (V-B §30.8) |
| `Entity` · `ArticleTopic` · `ArticleEntity` | worker | app | |
| `Event` | worker | app | compteurs recalculés (CF-15) |
| `Embedding` | worker | — | |
| `AIJob` | worker (claim, exécution, statuts) ; **création** par le worker **et** l'app | app | exception : l'app fait passer un `dead_letter` à `pending` ou `cancelled` (V-A §23.6) |
| `Signal` | worker | app | |
| `EmergingCandidate` | worker | app | dont `resurfaced_at` |
| `AlertLog` | worker | app | |
| `SystemState` | worker | app | un seul écrivain par clé, toutes écrites par le worker (III §11.13) |
| `UserPreference` | **app** | worker | |
| `Setting` | **app** | worker (relu à chaque tick) | |
| `ReadState` | **app** | — | |
| `EmergingDecision` | **app** | worker | upsert (V-B §30.7) |
| `article_fts` | worker (par triggers sur `article`) | app | |

---

## 2. Configuration

### 2.1 Prérequis vérifiés au démarrage

`app` et `worker` refusent de démarrer, avec un message explicite, si l'un manque (III §10.1, T-DB-01, T-DB-02) :
SQLite ≥ 3.35 (`RETURNING` du claim) · FTS5 · JSON1 · révision Alembic en base égale à `head`.

La vérification de T0.3 (V-02) a trouvé SQLite **3.46.1** dans l'image de référence, FTS5 et JSON1 fonctionnels
(rapport de cadrage §3).

### 2.2 PRAGMA de chaque connexion

Appliqués par l'écouteur `connect` à **toute nouvelle connexion** (III §10.2, T-DB-03) :

```sql
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA busy_timeout=5000;            -- ms, configurable
PRAGMA foreign_keys=ON;
PRAGMA journal_size_limit=67108864;  -- 64 Mo, valeur initiale
```

- `synchronous=NORMAL` en WAL : une coupure électrique peut perdre les toutes dernières transactions validées, sans
  jamais corrompre la base (III §10.2).
- Auto-checkpoint WAL à sa valeur par défaut ; `journal_size_limit` tronque le `-wal` après checkpoint, dont la
  taille reste une métrique lisible (III §10.2, VII §39).
- Le fichier vit sur un **volume nommé local** (`radar_data` sur `/data`), jamais un bind mount ni un système de
  fichiers réseau (III §10.4, IX décision 26). T0.3 (V-04) a validé le WAL sur volume nommé partagé par deux
  conteneurs.

### 2.3 Moteur, fabriques de sessions et `BEGIN IMMEDIATE`

- SQLAlchemy 2.x async + `aiosqlite` dans les **deux** processus ; **un moteur par processus**, avec son pool ;
  aucune connexion partagée entre processus ou threads (III §10.3).
- **Deux fabriques de sessions** (III §10.3, décision 9) :
  - `write_session` : transaction ouverte en **`BEGIN IMMEDIATE`** ;
  - `read_session` : transaction différée (`BEGIN DEFERRED`), lecture seule.

**Mécanisme validé en T0.3 (V-03)** : documentation SQLAlchemy 2.0, dialecte SQLite, section *Enabling Non-Legacy
SQLite Transactional Modes with the sqlite3 or aiosqlite driver*, variante *Using SQLAlchemy to emit BEGIN in lieu
of SQLite's transaction control*. L'écouteur `connect` désactive le `BEGIN` implicite du pilote ; l'écouteur `begin`
émet le `BEGIN` ; en asyncio, les deux écouteurs se posent sur `engine.sync_engine`.

```python
engine = create_async_engine("sqlite+aiosqlite:////data/radar.db")

@event.listens_for(engine.sync_engine, "connect")
def _on_connect(dbapi_connection, connection_record):
    dbapi_connection.isolation_level = None          # le pilote n'émet plus de BEGIN
    cursor = dbapi_connection.cursor()
    for pragma in PRAGMAS:                           # §2.2
        cursor.execute(pragma)
    cursor.close()

@event.listens_for(engine.sync_engine, "begin")
def _on_begin(conn):
    mode = "DEFERRED" if conn.get_execution_options().get("readonly") else "IMMEDIATE"
    conn.exec_driver_sql(f"BEGIN {mode}")

write_session = async_sessionmaker(engine)
read_session = async_sessionmaker(engine.execution_options(readonly=True))
```

- **Le nom de l'option `readonly` est une proposition** (rapport de cadrage §3, V-03) : il sera fixé à
  l'implémentation du Sprint 1.
- Résultat de V-03 (SQLAlchemy 2.0.54, aiosqlite 0.22.1) : une connexion B échoue ou attend **dès son `BEGIN`**
  quand A tient une transaction d'écriture ; une session de lecture seule ne prend pas le verrou et ne bloque pas
  les écrivains. Les autres mécanismes (`isolation_level="IMMEDIATE"`, `autocommit=False`) ne prennent le verrou
  qu'à la première écriture et sont écartés.
- Cette recette est incompatible avec le mode `AUTOCOMMIT` de SQLAlchemy au niveau du pilote (documentation
  SQLAlchemy).
- Transactions courtes : lots bornés côté worker, aucune écriture longue côté app, lectures paginées ; un échec
  après `busy_timeout` donne un retry borné et la métrique `db_locked` (III §10.7, II §8.6, T-DB-06).

### 2.4 Dates, heures et temps

- Tout en **UTC**, stocké en texte **ISO-8601** (III §10.6).
- Type `UTCDateTime` (`TypeDecorator` sur `TEXT`) : **refuse un datetime sans fuseau** à l'écriture, renvoie un
  datetime UTC à la lecture (T-DB-07). Conversion en heure locale à l'affichage seulement.
- **Aucune expression temporelle SQL** (`CURRENT_TIMESTAMP`, `datetime('now')`) dans le code ni dans les requêtes :
  l'instant est fourni par l'application via la `Clock` (III §10.6, VIII décision 7, §50.1). Les valeurs par défaut
  de colonnes restent un filet de sécurité (voir `AIJob.next_attempt_at`, §7 I-04).

---

## 3. Modèle cible

### 3.1 Vue d'ensemble

| Table (nom SQL) | Section | Sprint | Écrivain | Référence |
|---|---|---|---|---|
| `SystemState` (`system_state`) | §3.20 | **1** (clé `worker_heartbeat`) ; autres clés aux sprints qui les écrivent | worker | III §11.13 · VII §39.3 |
| `alembic_version` | §5 | **1** | `migrate` (Alembic) | III §10.5 |
| `Source` (`source`) | §3.2 | **2** | worker | III §11.1 |
| `Article` (`article`) | §3.3 | **2** ; colonnes du clustering au **4**, `processed_at` au **7** | worker | III §11.2 |
| `CollectorRun` (`collector_run`) | §3.4 | **2** | worker | III §11.11 · IV §14.4 |
| `Topic` (`topic`) | §3.5 | **2** | worker | III §11.4 |
| `Entity` (`entity`) | §3.6 | **2** | worker | III §11.6 |
| `ArticleTopic` (`article_topic`) | §3.7 | **2** | worker | III §11.5 |
| `ArticleEntity` (`article_entity`) | §3.8 | **2** | worker | III §11.7 |
| `AIJob` (`aijob`) | §3.11 | **2** (E7) | worker ; création aussi par l'app | III §11.10 · V-A §23 |
| `article_fts` (FTS5) + 3 triggers | §3.21 | **3** | worker (triggers) | III §11.14 |
| `Event` (`event`) | §3.9 | **4** | worker | III §11.3 · V-B §28 |
| `Embedding` (`embedding`) | §3.10 | **4** | worker | III §11.9 · §12 |
| `Signal` (`signal`) | §3.12 | **8** | worker | III §11.8 · V-B §29 |
| `EmergingCandidate` (`emerging_candidate`) | §3.13 | **8** | worker | III §11.13 · V-B §30 |
| `EmergingDecision` (`emerging_decision`) | §3.14 | **8** | app | III §11.12 · V-B §30.7 |
| `UserPreference` (`user_preference`) | §3.15 | **9** | app | III §11.12 · VI §34.1 |
| `Setting` (`setting`) | §3.16 | **9** | app | III §11.12 · VI §34.3 |
| `ReadState` (`read_state`) | §3.17 | **9** | app | III §11.12 · VI §31.5 |
| `AlertLog` (`alert_log`) | §3.18 | **10** | worker | III §11.13 · VI §33 |

Justification des sprints, d'après VIII §47.2 : Sprint 1, heartbeat du worker (`SystemState`) et migrations ;
Sprint 2, collecte et runner (`Source`, `Article`, `CollectorRun`, taxonomie, liaisons `keyword`, création des
`enrich_article` dans `AIJob`, **table introduite au Sprint 2 par E7**, jobs `pending` jusqu'au Sprint 5) ;
Sprint 3, index `article_fts` et ses triggers ; Sprint 4, embeddings et clustering ; Sprint 8, Trend Engine,
émergence et décisions ; Sprint 9, préférences, lu / non lu et `Setting` ; Sprint 10, alertes.

Ordre des migrations : une table référencée par une clé étrangère existe avant la colonne qui la référence. D'où
`Article.event_id` (vers `Event`) et `Article.duplicate_of_id` ajoutés au Sprint 4, avec `Event`.

---

## 7. Incohérences relevées

Écarts entre parties de la spec, ou trous, relevés en rédigeant ce document. **Aucun n'est tranché ici** : chacun
cite ses passages. Les identifiants `I-nn` sont stables.

#### I-01 — Nommage SQL des tables

- La spec nomme les tables en `CamelCase` dans les tableaux (III §11) et en minuscules dans ses requêtes : `aijob`,
  `article`, `embedding` (V-A §23.4, §24.4, §24.5), `article_fts` (III §11.14). Elle ne fixe pas le nom SQL des
  tables composées (`CollectorRun`, `ArticleTopic`, `EmergingCandidate`…), ni la convention (`aijob` est écrit sans
  séparateur).

#### I-02 — Liste des tables portant `created_at` et `updated_at`

- **III §11.0** : « `created_at` et, pour les tables modifiables, `updated_at` ».
- Les tables de III §11 ne listent ces colonnes que ponctuellement : `ArticleTopic.created_at` (§11.5),
  `Embedding.created_at` (§11.9), `Setting.updated_at` et `SystemState.updated_at` (§11.12, §11.13). D'autres
  parties utilisent `AIJob.created_at` (V-A §23.3, §23.4) et `Topic.created_at` (V-B §29.3) sans qu'ils figurent
  dans III. Certaines tables portent un horodatage métier qui pourrait en tenir lieu (`ReadState.read_at`,
  `EmergingDecision.decided_at`, `CollectorRun.started_at`, `EmergingCandidate.first_detected_at`).
- Non fixé : quelles tables sont « modifiables », et si l'horodatage métier remplace `created_at` / `updated_at`.

#### I-03 — Nullabilité et défauts non précisés

- **III §11.0** fixe la règle « `NULL` = inconnu », mais la plupart des colonnes de III §11 n'ont ni nullabilité ni
  défaut écrits. Elles sont marquées `n. p.` dans les tableaux du §3 ; la liste par table est donnée en I-15.

#### I-04 — Défaut de `AIJob.next_attempt_at`

- **III §11.10** : `next_attempt_at` « non nul, défaut = maintenant ».
- **III §10.6** : « Aucune expression temporelle SQL (`CURRENT_TIMESTAMP`, `datetime('now')`) dans le code ni dans
  les requêtes […]. Les valeurs par défaut de colonnes, comme celle de `AIJob.next_attempt_at`, restent un filet de
  sécurité. »
- Un défaut SQL « maintenant » ne peut s'écrire qu'avec une expression temporelle, et `CURRENT_TIMESTAMP` produit
  `AAAA-MM-JJ HH:MM:SS`, sans `T` ni fuseau, alors que `UTCDateTime` stocke de l'ISO-8601 avec fuseau (III §10.6).
  Non fixé : défaut SQL (et son format) ou défaut côté SQLAlchemy (`default=` Python, lu par la `Clock`).

<!-- INCOHERENCES -->
