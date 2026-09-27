# Modèle de données — SQLite

> Tâche T0.4 (#7), rédigée le 2026-09-23 sur la spec arbitrée par T0.2b (#67).
> Document de référence des migrations Alembic de chaque sprint (Partie IX §55.4, Partie VIII §47.1).
> Il **rassemble** ce que la spec fixe : la spec fait foi. Les écarts relevés entre ses parties sont listés au §7,
> avec les décisions du propriétaire du 2026-09-23, appliquées par T0.4b (#69).

Références : `docs/spec/partie-<N>.md` est abrégé en « <N> » (par exemple « III §11.2 »). Les décisions du rapport
de cadrage (`docs/sprints/sprint-00-cadrage.md`) sont citées par leur identifiant (E7, CF-15…).

**Règles de lecture des tableaux de colonnes**

- **Null** : règle de III §11.0 (I-03) : **non nul par défaut** ; `oui` seulement si la spec le dit ou si `NULL` a
  un sens (valeur inconnue ou absente). Chaque colonne nullable est justifiée dans la colonne Rôle.
- **Défaut** : seulement les défauts écrits dans la spec ; `—` sinon.
- **Sprint** : sprint de la migration qui crée la colonne, l'index ou le trigger. Il découle du contenu des sprints
  (VIII §47.2) et des arbitrages (E7) ; quand la spec ne le dit pas explicitement, la justification figure sous le
  tableau.
- Les blocs SQL sont **indicatifs** : ils décrivent la cible, ce ne sont pas des migrations (IX §57.6). Les noms de
  tables en SQL sont en `snake_case` ; `aijob` est gardé tel qu'il figure dans les requêtes de V-A (III §11.0,
  I-01).

---

## 1. Conventions

### 1.1 Clés, horodatage, JSON

- **Clé primaire** : `id INTEGER PRIMARY KEY` partout, sauf les tables de liaison (clé composite) et les tables
  clé/valeur `Setting` et `SystemState` (clé texte) (III §11.0).
- **Horodatage** (III §11.0, I-02), type `UTCDateTime` :
  - `created_at` sur toutes les tables à identifiant `id`, ainsi que sur `ArticleTopic` et `ArticleEntity` ;
  - `updated_at` sur les tables dont les lignes sont modifiées après insertion : `Source` · `Article` · `Topic` ·
    `Entity` · `Event` · `Embedding` · `AIJob` · `Signal` · `EmergingCandidate` · `EmergingDecision` ·
    `UserPreference` · `ReadState` · `AlertLog` · `Setting` · `SystemState` ;
  - ni l'un ni l'autre n'a de défaut SQL : l'application fournit l'instant (§2.4).
- **JSON** : colonne texte JSON, **`JSONText` côté SQLAlchemy** (`app/db/types.py`), **`TEXT` en SQLite** ; jamais
  `sqlalchemy.JSON`, dont la colonne déclarée `JSON` a une affinité NUMERIC (décision du 2026-09-26). Validée par un
  schéma Pydantic à l'écriture (III §11.0). JSON1 est un prérequis vérifié au démarrage (III §10.1).
- **`NULL` = inconnu ou absent.** Jamais de valeur inventée par défaut : un quota inconnu est `NULL`, pas `0`. Toute
  colonne est **non nulle par défaut** ; elle n'est nullable que si la spec le dit ou si `NULL` a un sens
  (III §11.0, I-03).
- **Nommage SQL** : tables en `snake_case`, sauf `aijob`, gardé tel qu'il figure dans les requêtes de V-A
  (III §11.0, I-01).
- **Contraintes et index nommés** : les métadonnées portent une convention de nommage (`NAMING_CONVENTION`,
  `app/db/models.py`) — `pk_<table>`, `fk_<table>_<colonnes>_<table référencée>`, `uq_<table>_<colonnes>`,
  `ix_<table>_<colonnes>`, `ck_<table>_<nom>`. Le mode batch d'Alembic en a besoin pour modifier une contrainte sous
  SQLite (III §10.5 ; décision du 2026-09-26).
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

Appliqués par l'écouteur `connect` à **toute nouvelle connexion de `app` et `worker`** (III §10.2, T-DB-03) :

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
- **Seule exception** : la connexion du service `migrate`, qui fonctionne avec `foreign_keys=OFF` pendant les
  migrations, posé par l'écouteur `connect` de son propre moteur (III §10.2, §5).
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
# settings : configuration typée du processus ; radar_db_path vient de RADAR_DB_PATH (P-01 d'architecture.md)
engine = create_async_engine(f"sqlite+aiosqlite:///{settings.radar_db_path}")

@event.listens_for(engine.sync_engine, "connect")
def _on_connect(dbapi_connection, connection_record):
    dbapi_connection.isolation_level = None          # le pilote n'émet plus de BEGIN
    cursor = dbapi_connection.cursor()
    for pragma in PRAGMAS:                           # §2.2
        cursor.execute(pragma)
    cursor.close()

@event.listens_for(engine.sync_engine, "begin")
def _on_begin(conn):
    mode = "DEFERRED" if conn.get_execution_options().get("radar_read_only") else "IMMEDIATE"
    conn.exec_driver_sql(f"BEGIN {mode}")

write_session = async_sessionmaker(engine)
read_session = async_sessionmaker(engine.execution_options(radar_read_only=True))
```

- **Option de lecture seule : `radar_read_only`** (`app/db/engine.py`, constante `READ_ONLY_OPTION`), fixée en T1.3
  (#80). Le préfixe évite toute collision avec une option d'exécution de SQLAlchemy ou d'un dialecte.
- Résultat de V-03 (SQLAlchemy 2.0.54, aiosqlite 0.22.1) : une connexion B échoue ou attend **dès son `BEGIN`**
  quand A tient une transaction d'écriture ; une session de lecture seule ne prend pas le verrou et ne bloque pas
  les écrivains. Les autres mécanismes (`isolation_level="IMMEDIATE"`, `autocommit=False`) ne prennent le verrou
  qu'à la première écriture et sont écartés.
- Cette recette est incompatible avec le mode `AUTOCOMMIT` de SQLAlchemy au niveau du pilote (documentation
  SQLAlchemy).
- Transactions courtes : lots bornés côté worker, aucune écriture longue côté app, lectures paginées ; un échec
  après `busy_timeout` donne un retry borné et la métrique `db_locked` (III §10.7, II §8.6, T-DB-06).
  Mise en œuvre (T1.3) : `Database.run_write` (`app/db/session.py`) rejoue l'unité d'écriture au plus 3 fois en tout,
  immédiatement, `busy_timeout` portant déjà l'attente ; chaque échec « database is locked » est compté par le
  compteur `db_locked` du processus, horodaté par la `Clock`, sur une fenêtre glissante d'une heure (VII §39.4).

### 2.4 Dates, heures et temps

- Tout en **UTC**, stocké en texte **ISO-8601** (III §10.6).
- Type `UTCDateTime` (`TypeDecorator` sur `TEXT`) : **refuse un datetime sans fuseau** à l'écriture, renvoie un
  datetime UTC à la lecture (T-DB-07). Conversion en heure locale à l'affichage seulement.
- **Aucune expression temporelle SQL** (`CURRENT_TIMESTAMP`, `datetime('now')`) dans le code ni dans les requêtes :
  l'instant est fourni par l'application via la `Clock` (III §10.6, VIII décision 7, §50.1). Aucune colonne n'a de
  défaut temporel en SQL : `AIJob.next_attempt_at` est fourni par l'application (III §11.10, I-04).

---

## 3. Modèle cible

### 3.1 Vue d'ensemble

| Table (nom SQL) | Section | Sprint | Écrivain | Référence |
|---|---|---|---|---|
| `SystemState` (`system_state`) | §3.19 | **1** (clé `worker_heartbeat`) ; autres clés aux sprints qui les écrivent | worker | III §11.13 · VII §39.3 |
| `alembic_version` | §5 | **1** | `migrate` (Alembic) | III §10.5 |
| `Source` (`source`) | §3.2 | **2** | worker | III §11.1 |
| `Article` (`article`) | §3.3 | **2** ; colonnes du clustering au **4**, `processed_at` au **7** | worker | III §11.2 |
| `CollectorRun` (`collector_run`) | §3.4 | **2** | worker | III §11.11 · IV §14.4 |
| `Topic` (`topic`) | §3.5 | **2** | worker | III §11.4 |
| `Entity` (`entity`) | §3.6 | **2** | worker | III §11.6 |
| `ArticleTopic` (`article_topic`) | §3.7 | **2** | worker | III §11.5 |
| `ArticleEntity` (`article_entity`) | §3.8 | **2** | worker | III §11.7 |
| `AIJob` (`aijob`) | §3.11 | **2** (E7) | worker ; création aussi par l'app | III §11.10 · V-A §23 |
| `article_fts` (FTS5) + 3 triggers | §3.20 | **3** | worker (triggers) | III §11.14 |
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

### 3.2 `Source` — *écrit par le worker*

Une ligne par source de `config/sources.yaml`, upsertée au démarrage du worker sur `key` ; jamais supprimée
(`enabled = false` si la clé disparaît du fichier, FK `RESTRICT`) (IV §16.2).

| Colonne | SQLite | SQLAlchemy | Null | Défaut | Contrainte | Rôle | Réf. | Sprint |
|---|---|---|---|---|---|---|---|---|
| `id` | `INTEGER` | `Integer` | non | — | PK | | III §11.0 | 2 |
| `key` | `TEXT` | `String` | non | — | **UNIQUE** | identifiant stable de `sources.yaml`, slug `[a-z0-9-]+`, clé d'upsert, immuable | III §11.1 · IV §16.2 | 2 |
| `name` | `TEXT` | `String` | non | — | | libellé affiché | III §11.1 | 2 |
| `type` | `TEXT` | `String` | non | — | validé par le code (registre des collectors) | V1 : `rss · github · hackernews · reddit · youtube · webpage` ; ne change jamais pour une `key` | III §11.1, décision 7 · IV §16.2 | 2 |
| `url` | `TEXT` | `String` | non | — | | URL lisible de la source (page de liste pour `webpage`) | III §11.1 · IV §16.2 | 2 |
| `config` | `TEXT` (JSON) | `JSON` | oui | — | Pydantic : `config_model` du collector | paramètres propres au collector — `NULL` pour un type de collector sans paramètres : `config` n'est obligatoire que selon le type (IV §16.2). | III §11.1 · IV §16.2 | 2 |
| `enabled` | `INTEGER` | `Boolean` | non | — | | source planifiée ou non | III §11.1 | 2 |
| `poll_interval` | `INTEGER` | `Integer` | non | — | | intervalle en secondes, ≥ minimum du type | III §11.1 · IV §16.2 | 2 |
| `relevance` | `TEXT` | `String` | non | — | `CHECK IN ('filter','always')` | `always` : article toujours `ready` | III §11.1 · IV §20.3 | 2 |
| `extract` | `TEXT` | `String` | non | — | `CHECK IN ('auto','never')` | extraction ciblée autorisée ou non | III §11.1 · IV §17.1 | 2 |
| `checkpoint` | `TEXT` (JSON) | `JSON` | oui | — | Pydantic | curseur, `ETag`, `Last-Modified`, date de dernière collecte ; vide à l'insertion ; jamais écrasé par le YAML — `NULL` tant qu'aucune page n'a été collectée (checkpoint vide à l'insertion, IV §16.2). | III §11.1 · IV §14.3, §16.1 | 2 |
| `last_success_at` | `TEXT` | `UTCDateTime` | oui | — | | fin du dernier run `success` ou `partial` — `NULL` tant qu'aucun run n'a réussi. | III §11.1 · IV §14.4 | 2 |
| `last_error` | `TEXT` | `Text` | oui | — | | dernier run `partial` ou `failed`, après nettoyage des secrets par valeur — `NULL` tant qu'aucun run n'a échoué. | III §11.1 · IV §14.4 · VII §42.4 | 2 |
| `last_http_status` | `INTEGER` | `Integer` | oui | — | | état de santé — `NULL` tant qu'aucune réponse HTTP n'a été reçue. | III §11.1 | 2 |
| `rate_limit_remaining` | `INTEGER` | `Integer` | oui | — | | `NULL` = quota inconnu | III §11.1 · IV §21.4 | 2 |
| `rate_limit_reset_at` | `TEXT` | `UTCDateTime` | oui | — | | `NULL` = inconnu | III §11.1 · IV §21.3 | 2 |
| `created_at` | `TEXT` | `UTCDateTime` | non | — | | insertion de la ligne | III §11.0 | 2 |
| `updated_at` | `TEXT` | `UTCDateTime` | non | — | | dernière modification de la ligne | III §11.0 | 2 |

- Champs de configuration (mis à jour par l'upsert) : `name`, `url`, `config`, `enabled`, `poll_interval`,
  `relevance`, `extract`. Champs d'état (jamais touchés par le YAML) : `checkpoint`, `last_*`, `rate_limit_*`
  (IV §16.1, §16.2).
- Aucun état de disjoncteur en colonne : il se lit dans `CollectorRun` (IV §21.5).

```sql
CREATE TABLE source (
  id                   INTEGER PRIMARY KEY,
  key                  TEXT NOT NULL UNIQUE,
  name                 TEXT NOT NULL,
  type                 TEXT NOT NULL,
  url                  TEXT NOT NULL,
  config               TEXT,  -- JSON
  enabled              INTEGER NOT NULL,
  poll_interval        INTEGER NOT NULL,
  relevance            TEXT NOT NULL CHECK (relevance IN ('filter','always')),
  extract              TEXT NOT NULL CHECK (extract IN ('auto','never')),
  checkpoint           TEXT,  -- JSON
  last_success_at      TEXT,
  last_error           TEXT,
  last_http_status     INTEGER,
  rate_limit_remaining INTEGER,
  rate_limit_reset_at  TEXT,
  created_at           TEXT NOT NULL,
  updated_at           TEXT NOT NULL
);
```

### 3.3 `Article` — *écrit par le worker*

Insertion par le runner, une transaction `BEGIN IMMEDIATE` par page (IV §14.3). Un doublon exact n'est **pas**
inséré ; un item malformé non plus (III décision 6).

| Colonne | SQLite | SQLAlchemy | Null | Défaut | Contrainte | Rôle | Réf. | Sprint |
|---|---|---|---|---|---|---|---|---|
| `id` | `INTEGER` | `Integer` | non | — | PK | | III §11.0 | 2 |
| `source_id` | `INTEGER` | `Integer` | non | — | FK `source(id)` `RESTRICT` | | III §11.2 | 2 |
| `external_id` | `TEXT` | `String` | oui | — | voir unicité partielle | identifiant chez le provider | III §11.2 | 2 |
| `url` | `TEXT` | `String` | non | — | | URL **propre à l'item** | III §11.2, décision 3 | 2 |
| `canonical_url` | `TEXT` | `String` | non | — | **UNIQUE** | base de la dédup exacte | III §11.2 · IV §18.3, §19.1 | 2 |
| `link_url` | `TEXT` | `String` | oui | — | | URL **pointée** (lien externe) | III §11.2 | 2 |
| `canonical_link_url` | `TEXT` | `String` | oui | — | index | critère « URL croisée » du clustering | III §11.2 · V-B §28.4 | 2 |
| `title` | `TEXT` | `Text` | non | — | | titre normalisé, une ligne, ≤ 500 caractères | III §11.2 · IV §18.2 | 2 |
| `author` | `TEXT` | `String` | oui | — | | auteur vide → `NULL` | III §11.2 · IV §18.2 | 2 |
| `language` | `TEXT` | `String` | oui | — | | `NULL` sous 20 caractères ou si le détecteur ne tranche pas | III §11.2 · IV §18.5 | 2 |
| `published_at` | `TEXT` | `UTCDateTime` | **non** | — | index | absent ou futur → repli sur `discovered_at` | III §11.2 · IV §18.4 | 2 |
| `discovered_at` | `TEXT` | `UTCDateTime` | **non** | — | | instant UTC du traitement de la page | III §11.2 · IV §14.2 | 2 |
| `content` | `TEXT` | `Text` | oui | — | | **tampon de traitement**, purgé ; `NULL` dès l'insertion pour un `filtered` | III §11.2 · IV §14.3 · II §8.5 | 2 |
| `content_hash` | `TEXT` | `String` | oui | — | index (non unique) | `NULL` sous 200 caractères ; conservé après purge ; jamais recalculé après extraction | III §11.2 · IV §19.2 | 2 |
| `content_purged_at` | `TEXT` | `UTCDateTime` | oui | — | | posé à l'insertion d'un `filtered`, puis par la purge | III §11.2 · IV §14.3 | 2 |
| `relevance_score` | `REAL` | `Float` | non | — | | score du relevance filter | III §11.2 · IV §20 | 2 |
| `status` | `TEXT` | `String` | non | — | `CHECK IN ('ready','filtered','duplicate')` ; index | insertion en `ready` ou `filtered` ; seule transition : `ready → duplicate` | III §11.2 | 2 |
| `summary` | `TEXT` | `Text` | **non** (E12) | — | | aperçu : repli à l'insertion (`ready` **et** `filtered`), puis synthèse LLM | III §11.2 · IV §14.5 | 2 |
| `summary_origin` | `TEXT` | `String` | non | — | `CHECK IN ('fallback','llm')` | | III §11.2 | 2 |
| `summary_lang` | `TEXT` | `String` | oui | — | | langue du résumé ; au repli, `language` (éventuellement `NULL`) | III §11.2 · IV §14.5 | 2 |
| `metrics` | `TEXT` (JSON) | `JSON` | oui | — | Pydantic | engagement à la collecte (points HN, vues YouTube…), instantané jamais mis à jour — `NULL` quand le provider ne fournit aucune métrique d'engagement (métrique absente, V-B §28.9). | III §11.2 · IV §15.4 | 2 |
| `event_id` | `INTEGER` | `Integer` | oui | — | FK `event(id)` `RESTRICT` ; index | appartenance à un Event | III §11.2, décision 4 · V-B §28.5 | **4** |
| `duplicate_of_id` | `INTEGER` | `Integer` | oui | — | FK `article(id)` `RESTRICT` | renseigné si `duplicate` | III §11.2 · V-B §28.7 | **4** |
| `clustered_at` | `TEXT` | `UTCDateTime` | oui | — | index partiel | article évalué par le clustering | III §11.2 · V-B §28.2 | **4** |
| `clustered_semantic` | `INTEGER` | `Boolean` | non | `false` | | critère cosine évalué | III §11.2 · V-B §28.2 | **4** |
| `importance` | `REAL` | `Float` | oui | — | | importance de l'article hors Event, dans [0, 1] | III §11.2 · V-B §28.9 | **4** |
| `processed_at` | `TEXT` | `UTCDateTime` | oui | — | | tous traitements terminés ; posé par la seule passe `processed_at` de la purge | III §11.2 · V-A §24.5 | **7** |
| `created_at` | `TEXT` | `UTCDateTime` | non | — | | insertion de la ligne | III §11.0 | 2 |
| `updated_at` | `TEXT` | `UTCDateTime` | non | — | | dernière modification de la ligne | III §11.0 | 2 |

**Contraintes et index**

| Élément | Définition | Réf. | Sprint |
|---|---|---|---|
| unicité | `UNIQUE(canonical_url)` | III §11.2 | 2 |
| unicité partielle | `UNIQUE(source_id, external_id) WHERE external_id IS NOT NULL` | III §11.2 | 2 |
| index | `published_at` | III §11.2 | 2 |
| index | `canonical_link_url` | III §11.2 | 2 |
| index | `content_hash` (non unique) | III §11.2 | 2 |
| index | `status` | III §11.2 | 2 |
| index | `event_id` | III §11.2 | 4 |
| index partiel | `clustered_at WHERE clustered_at IS NULL AND status = 'ready'` (sélection du clustering) | III §11.2 · V-B §28.2 | 4 |
| index | `(status, event_id, published_at)` (stories) | III §11.2 · VI §31.1 | 4 |

- **Sprints** : le Sprint 2 insère les articles avec résumé de repli et purge immédiate du contenu des `filtered`
  (IV §14.3) ; le Sprint 4 livre le clustering, qui écrit `event_id`, `status = duplicate`, `duplicate_of_id`,
  `clustered_at`, `clustered_semantic` et `importance` (V-B §28.1) ; `event_id` référence `Event`, créé au même
  sprint. Le Sprint 7 livre la purge et la passe `processed_at` (VIII §47.2). Le `CHECK` de `status` comprend
  `duplicate` dès le Sprint 2, pour éviter une reconstruction de la table.
- `Article.content` est lu par l'embedding (Sprint 4) tant que `content_purged_at IS NULL` (V-A §24.4).
- Un article `duplicate` conserve ses topics et son résumé ; il est masqué à l'affichage (III §11.2).

```sql
CREATE TABLE article (
  id                 INTEGER PRIMARY KEY,
  source_id          INTEGER NOT NULL REFERENCES source(id) ON DELETE RESTRICT,
  external_id        TEXT,
  url                TEXT NOT NULL,
  canonical_url      TEXT NOT NULL UNIQUE,
  link_url           TEXT,
  canonical_link_url TEXT,
  title              TEXT NOT NULL,
  author             TEXT,
  language           TEXT,
  published_at       TEXT NOT NULL,
  discovered_at      TEXT NOT NULL,
  content            TEXT,
  content_hash       TEXT,
  content_purged_at  TEXT,
  relevance_score    REAL NOT NULL,
  status             TEXT NOT NULL CHECK (status IN ('ready','filtered','duplicate')),
  summary            TEXT NOT NULL,
  summary_origin     TEXT NOT NULL CHECK (summary_origin IN ('fallback','llm')),
  summary_lang       TEXT,
  metrics            TEXT,  -- JSON
  created_at         TEXT NOT NULL,
  updated_at         TEXT NOT NULL,
  -- Sprint 4
  event_id           INTEGER REFERENCES event(id) ON DELETE RESTRICT,
  duplicate_of_id    INTEGER REFERENCES article(id) ON DELETE RESTRICT,
  clustered_at       TEXT,
  clustered_semantic INTEGER NOT NULL DEFAULT 0,
  importance         REAL,
  -- Sprint 7
  processed_at       TEXT
);
CREATE UNIQUE INDEX ux_article_source_external ON article(source_id, external_id)
  WHERE external_id IS NOT NULL;
CREATE INDEX ix_article_published_at       ON article(published_at);
CREATE INDEX ix_article_canonical_link_url ON article(canonical_link_url);
CREATE INDEX ix_article_content_hash       ON article(content_hash);
CREATE INDEX ix_article_status             ON article(status);
-- Sprint 4
CREATE INDEX ix_article_event_id           ON article(event_id);
CREATE INDEX ix_article_to_cluster         ON article(clustered_at)
  WHERE clustered_at IS NULL AND status = 'ready';
CREATE INDEX ix_article_stories            ON article(status, event_id, published_at);
```

### 3.4 `CollectorRun` — *écrit par le worker*

Une ligne **à la fin** de chaque run d'un collector ; un worker tué en cours de run n'en écrit pas (IV §14.4).
Alimente les métriques par source (VII §39) et le disjoncteur par source (IV §21.5).

| Colonne | SQLite | SQLAlchemy | Null | Défaut | Contrainte | Rôle | Réf. | Sprint |
|---|---|---|---|---|---|---|---|---|
| `id` | `INTEGER` | `Integer` | non | — | PK | | III §11.0 | 2 |
| `source_id` | `INTEGER` | `Integer` | non | — | FK `source(id)` `RESTRICT` | | III §11.11 | 2 |
| `started_at` · `finished_at` | `TEXT` | `UTCDateTime` | non | — | | bornes du run | III §11.11 | 2 |
| `status` | `TEXT` | `String` | non | — | `CHECK IN ('success','partial','failed')` | | III §11.11 · IV §14.4 | 2 |
| `items_fetched` | `INTEGER` | `Integer` | non | — | | entrées renvoyées par le provider, malformées comprises | III §11.11 · IV §14.4 | 2 |
| `items_created` | `INTEGER` | `Integer` | non | — | | insérés en `ready` | idem | 2 |
| `items_duplicate` | `INTEGER` | `Integer` | non | — | | doublons exacts non insérés, conflits `ON CONFLICT` compris | idem | 2 |
| `items_filtered` | `INTEGER` | `Integer` | non | — | | insérés en `filtered` | idem | 2 |
| `items_skipped` | `INTEGER` | `Integer` | non | — | | entrées malformées, non persistées | idem | 2 |
| `items_too_old` | `INTEGER` | `Integer` | non | — | | plus anciennes que `max_item_age` | idem | 2 |
| `extractions_attempted` · `extractions_failed` | `INTEGER` | `Integer` | non | — | | extraction ciblée (IV §17) | idem | 2 |
| `requests_count` | `INTEGER` | `Integer` | non | — | | requêtes HTTP du run, extraction comprise | idem | 2 |
| `http_status` | `INTEGER` | `Integer` | oui | — | | `NULL` si le run n'a reçu aucune réponse HTTP (erreur réseau, timeout). | III §11.11 | 2 |
| `error` | `TEXT` | `Text` | oui | — | | `NULL` pour un run sans erreur. | III §11.11 | 2 |
| `created_at` | `TEXT` | `UTCDateTime` | non | — | | insertion de la ligne | III §11.0 | 2 |

- **Invariant testé** : `items_fetched = items_created + items_filtered + items_duplicate + items_skipped +
  items_too_old` (IV §14.4).
- **Index** : `(source_id, finished_at)` : disjoncteur par source (IV §21.5) et rétention (III §11.11, §13, I-07), Sprint 2.

```sql
CREATE TABLE collector_run (
  id                    INTEGER PRIMARY KEY,
  source_id             INTEGER NOT NULL REFERENCES source(id) ON DELETE RESTRICT,
  started_at            TEXT NOT NULL,
  finished_at           TEXT NOT NULL,
  status                TEXT NOT NULL CHECK (status IN ('success','partial','failed')),
  items_fetched         INTEGER NOT NULL,
  items_created         INTEGER NOT NULL,
  items_duplicate       INTEGER NOT NULL,
  items_filtered        INTEGER NOT NULL,
  items_skipped         INTEGER NOT NULL,
  items_too_old         INTEGER NOT NULL,
  extractions_attempted INTEGER NOT NULL,
  extractions_failed    INTEGER NOT NULL,
  requests_count        INTEGER NOT NULL,
  http_status           INTEGER,
  error                 TEXT,
  created_at            TEXT NOT NULL
);
CREATE INDEX ix_collector_run_source_finished ON collector_run(source_id, finished_at);
```

### 3.5 `Topic` — *écrit par le worker*

Upserté depuis `topics.yaml` au démarrage (clé `slug`, `origin = seeded`) ; créé en `origin = user` par le worker
sur une décision `create_topic` de l'app (IV §16.3, V-B §30.8). `origin = discovered` n'est produit par aucun
mécanisme en V1 (V-A §24.6). Le suivi et la sourdine ne sont pas ici : ce sont des préférences (§3.15).

| Colonne | SQLite | SQLAlchemy | Null | Défaut | Contrainte | Rôle | Réf. | Sprint |
|---|---|---|---|---|---|---|---|---|
| `id` | `INTEGER` | `Integer` | non | — | PK | | III §11.0 | 2 |
| `slug` | `TEXT` | `String` | non | — | **UNIQUE** | clé d'upsert ; suffixe `-2`, `-3`… en collision pour un topic `user` | III §11.4 · IV §16.3 · V-B §30.8 | 2 |
| `name` | `TEXT` | `String` | non | — | | | III §11.4 | 2 |
| `description` | `TEXT` | `Text` | oui | — | | `null` par défaut dans le YAML ; `llm_description` ou `NULL` pour un topic `user` | III §11.4 · IV §16.3 · V-B §30.8 | 2 |
| `parent_id` | `INTEGER` | `Integer` | oui | — | FK `topic(id)` `RESTRICT` | hiérarchie ; `NULL` pour un topic `user` | III §11.4 · IV §16.3 · V-B §30.8 | 2 |
| `origin` | `TEXT` | `String` | non | — | `CHECK IN ('seeded','discovered','user')` | | III §11.4 | 2 |
| `keywords` | `TEXT` (JSON) | `JSON` | non | — | Pydantic | `{include, exclude}` : mots-clés et motifs du relevance filter, termes masqués avant matching | III §11.4 · IV §16.3, §20.3 | 2 |
| `enabled` | `INTEGER` | `Boolean` | non | — | | un topic désactivé n'est pas utilisé par le scoring et n'a plus de Signal | III §11.4 · IV §16.3 · V-B §29.7 | 2 |
| `created_at` | `TEXT` | `UTCDateTime` | non | — | | couverture d'un topic `user` : `created_at − topic_backfill.window` | III §11.0 · V-B §29.3 | 2 |
| `updated_at` | `TEXT` | `UTCDateTime` | non | — | | dernière modification de la ligne | III §11.0 | 2 |

- Les exclusions (`exclude`) de `topics.yaml` sont stockées dans `keywords`, sous la clé `exclude` (III §11.4, IV §16.3, I-05).

```sql
CREATE TABLE topic (
  id          INTEGER PRIMARY KEY,
  slug        TEXT NOT NULL UNIQUE,
  name        TEXT NOT NULL,
  description TEXT,
  parent_id   INTEGER REFERENCES topic(id) ON DELETE RESTRICT,
  origin      TEXT NOT NULL CHECK (origin IN ('seeded','discovered','user')),
  keywords    TEXT NOT NULL,  -- JSON
  enabled     INTEGER NOT NULL,
  created_at  TEXT NOT NULL,
  updated_at  TEXT NOT NULL
);
```

### 3.6 `Entity` — *écrit par le worker*

Upsertée depuis `entities.yaml` (clé `(type, canonical_name)`, `origin = dictionary`) ; créée à la volée par le
motif GitHub `owner/repo` (`origin = dictionary`) ou par `enrich_article` (`origin = llm`) (IV §16.4, V-A §27).
**Les alias ne sont pas en base** : ils sont déclarés à la main dans `entities.yaml` et gardés en mémoire (III §11.6,
CF-19). Alias et fusion automatiques en base : V2.

| Colonne | SQLite | SQLAlchemy | Null | Défaut | Contrainte | Rôle | Réf. | Sprint |
|---|---|---|---|---|---|---|---|---|
| `id` | `INTEGER` | `Integer` | non | — | PK | | III §11.0 | 2 |
| `type` | `TEXT` | `String` | non | — | validé par le code | `company · product · person · project · technology · model · repository` | III §11.6 | 2 |
| `name` | `TEXT` | `String` | non | — | | libellé affiché, mis à jour par l'upsert | III §11.6 · IV §16.4 | 2 |
| `canonical_name` | `TEXT` | `String` | non | — | voir unicité | minuscules ; `owner/repo` pour un dépôt | III §11.6 · IV §16.4 | 2 |
| `origin` | `TEXT` | `String` | non | — | `CHECK IN ('dictionary','llm')` | | III §11.6 | 2 |
| `created_at` | `TEXT` | `UTCDateTime` | non | — | | insertion de la ligne | III §11.0 | 2 |
| `updated_at` | `TEXT` | `UTCDateTime` | non | — | | dernière modification de la ligne | III §11.0 | 2 |

**Unicité** : `UNIQUE(type, canonical_name)` (III §11.6), Sprint 2.

```sql
CREATE TABLE entity (
  id             INTEGER PRIMARY KEY,
  type           TEXT NOT NULL,
  name           TEXT NOT NULL,
  canonical_name TEXT NOT NULL,
  origin         TEXT NOT NULL CHECK (origin IN ('dictionary','llm')),
  created_at     TEXT NOT NULL,
  updated_at     TEXT NOT NULL,
  UNIQUE (type, canonical_name)
);
```

### 3.7 `ArticleTopic` — *écrit par le worker*

Liaisons `keyword` écrites par le runner (Sprint 2) et par le backfill d'un topic créé (Sprint 8) ; liaisons `llm`
remplacées en bloc par `enrich_article` (Sprint 7) (IV §14.3, V-A §24.6, §27).

| Colonne | SQLite | SQLAlchemy | Null | Défaut | Contrainte | Rôle | Réf. | Sprint |
|---|---|---|---|---|---|---|---|---|
| `article_id` | `INTEGER` | `Integer` | non (PK) | — | FK `article(id)` **`CASCADE`** | | III §11.5 · §11.0 | 2 |
| `topic_id` | `INTEGER` | `Integer` | non (PK) | — | FK `topic(id)` `RESTRICT` | | III §11.5 | 2 |
| `method` | `TEXT` | `String` | non (PK) | — | `CHECK IN ('keyword','llm')` | un même topic peut être attribué par les deux méthodes | III §11.5 | 2 |
| `confidence` | `REAL` | `Float` | non | — | | | III §11.5 | 2 |
| `created_at` | `TEXT` | `UTCDateTime` | non | — | | | III §11.5 | 2 |

**Clé primaire** : `(article_id, topic_id, method)`. Les tendances comptent les **articles distincts** (III §11.5).
**Index** : `topic_id` (lecture par topic : Trend Engine, vue Topic) (III §11.5, I-07), Sprint 2.

```sql
CREATE TABLE article_topic (
  article_id INTEGER NOT NULL REFERENCES article(id) ON DELETE CASCADE,
  topic_id   INTEGER NOT NULL REFERENCES topic(id) ON DELETE RESTRICT,
  method     TEXT NOT NULL CHECK (method IN ('keyword','llm')),
  confidence REAL NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (article_id, topic_id, method)
);
CREATE INDEX ix_article_topic_topic_id ON article_topic(topic_id);
```

### 3.8 `ArticleEntity` — *écrit par le worker*

| Colonne | SQLite | SQLAlchemy | Null | Défaut | Contrainte | Rôle | Réf. | Sprint |
|---|---|---|---|---|---|---|---|---|
| `article_id` | `INTEGER` | `Integer` | non (PK) | — | FK `article(id)` **`CASCADE`** | | III §11.7 · §11.0 | 2 |
| `entity_id` | `INTEGER` | `Integer` | non (PK) | — | FK `entity(id)` `RESTRICT` | | III §11.7 | 2 |
| `method` | `TEXT` | `String` | non (PK) | — | `CHECK IN ('keyword','llm')` | | III §11.7 | 2 |
| `confidence` | `REAL` | `Float` | non | — | | | III §11.7 | 2 |
| `created_at` | `TEXT` | `UTCDateTime` | non | — | | insertion de la ligne | III §11.0 | 2 |

**Clé primaire** : `(article_id, entity_id, method)` (III §11.7). `created_at`, comme `ArticleTopic` (I-06).
**Index** : `entity_id` (entités communes du clustering, V-B §28.4) (III §11.7, I-07), Sprint 2.

```sql
CREATE TABLE article_entity (
  article_id INTEGER NOT NULL REFERENCES article(id) ON DELETE CASCADE,
  entity_id  INTEGER NOT NULL REFERENCES entity(id) ON DELETE RESTRICT,
  method     TEXT NOT NULL CHECK (method IN ('keyword','llm')),
  confidence REAL NOT NULL,
  created_at TEXT NOT NULL,
  PRIMARY KEY (article_id, entity_id, method)
);
CREATE INDEX ix_article_entity_entity_id ON article_entity(entity_id);
```

### 3.9 `Event` — *écrit par le worker*

Créé sans LLM par le clustering, dès deux articles (V-B décision 7) ; titre de repli, puis enrichi par
`resolve_event` sans toucher à l'appartenance ni aux compteurs (II §7.3, V-A §27.3). **Compteurs recalculés depuis
les membres dans chaque transaction qui modifie l'Event, jamais incrémentés** (V-B décision 9, §28.9 ; CF-15).

| Colonne | SQLite | SQLAlchemy | Null | Défaut | Contrainte | Rôle | Réf. | Sprint |
|---|---|---|---|---|---|---|---|---|
| `id` | `INTEGER` | `Integer` | non | — | PK | | III §11.0 | 4 |
| `title` | `TEXT` | `Text` | **non** | — | | repli = titre du représentant ; synthèse LLM ensuite | III §11.3 · V-B §28.5, §28.8 | 4 |
| `title_origin` | `TEXT` | `String` | non | — | `CHECK IN ('fallback','llm')` | ce que `resolve_event` doit encore enrichir | III §11.3 | 4 |
| `description` | `TEXT` | `Text` | oui | — | | produite par `resolve_event` ; `NULL` à la création | III §11.3 · V-B §28.5 | 4 |
| `representative_article_id` | `INTEGER` | `Integer` | non | — | FK `article(id)` `RESTRICT` | membre `ready` le plus ancien par `published_at` | III §11.3 · II §7.2 · V-B §28.8, décision 10 | 4 |
| `first_seen_at` · `last_seen_at` | `TEXT` | `UTCDateTime` | non | — | | min · max de `published_at` des membres `ready` | III §11.3 · V-B §28.9 | 4 |
| `article_count` | `INTEGER` | `Integer` | non | — | | membres `ready` | III §11.3 · V-B §28.9 | 4 |
| `distinct_source_count` | `INTEGER` | `Integer` | **non** | `1` | | `source_id` distincts des membres `ready` (**hotness**) | III §11.3 · V-B §28.9 | 4 |
| `distinct_channel_count` | `INTEGER` | `Integer` | **non** | `1` | | canaux distincts des membres `ready` | III §11.3, décision 16 · V-B §28.9 | 4 |
| `importance` | `REAL` | `Float` | **non** | `0` | | dans [0, 1], indépendante du temps | III §11.3 · V-B §28.9 | 4 |
| `resolve_enqueued_count` | `INTEGER` | `Integer` | oui | — | | `article_count` au dernier enqueue de `resolve_event` | III §11.3 · V-B §28.10 | 4 |
| `status` | `TEXT` | `String` | non | — | `CHECK IN ('active','merged','archived')` | `archived` = inactif depuis 7 j, informatif | III §11.3 · V-B §28.11 | 4 |
| `merged_into_id` | `INTEGER` | `Integer` | oui | — | FK `event(id)` `RESTRICT` | renseigné si `merged` | III §11.3 · V-B §28.6 | 4 |
| `created_at` | `TEXT` | `UTCDateTime` | non | — | | insertion de la ligne | III §11.0 | 4 |
| `updated_at` | `TEXT` | `UTCDateTime` | non | — | | dernière modification de la ligne | III §11.0 | 4 |

- **Invariant testé** : `article_count`, `distinct_source_count` et `distinct_channel_count` égalent leur recalcul
  depuis les membres `ready` ; contrôlable et corrigé par `python -m app.cli recount-events` (III §11.3, V-B §28.9).
- `novelty` n'existe pas sur `Event` : elle se calcule à la lecture depuis `first_seen_at` (III §11.3, V-B décision 13).
- Clés étrangères croisées : `article.event_id → event` et `event.representative_article_id → article`.

**Index** (III §11.3, stories VI) : `(status, last_seen_at)` · `(status, importance)`, Sprint 4.

```sql
CREATE TABLE event (
  id                        INTEGER PRIMARY KEY,
  title                     TEXT NOT NULL,
  title_origin              TEXT NOT NULL CHECK (title_origin IN ('fallback','llm')),
  description               TEXT,
  representative_article_id INTEGER NOT NULL REFERENCES article(id) ON DELETE RESTRICT,
  first_seen_at             TEXT NOT NULL,
  last_seen_at              TEXT NOT NULL,
  article_count             INTEGER NOT NULL,
  distinct_source_count     INTEGER NOT NULL DEFAULT 1,
  distinct_channel_count    INTEGER NOT NULL DEFAULT 1,
  importance                REAL NOT NULL DEFAULT 0,
  resolve_enqueued_count    INTEGER,
  status                    TEXT NOT NULL CHECK (status IN ('active','merged','archived')),
  merged_into_id            INTEGER REFERENCES event(id) ON DELETE RESTRICT,
  created_at                TEXT NOT NULL,
  updated_at                TEXT NOT NULL
);
CREATE INDEX ix_event_status_last_seen  ON event(status, last_seen_at);
CREATE INDEX ix_event_status_importance ON event(status, importance);
```

### 3.10 `Embedding` — *écrit par le worker*

Écrit par la file dérivée des embeddings, sans `AIJob` (V-A §24.4). Stockage du vecteur : §4.

| Colonne | SQLite | SQLAlchemy | Null | Défaut | Contrainte | Rôle | Réf. | Sprint |
|---|---|---|---|---|---|---|---|---|
| `id` | `INTEGER` | `Integer` | non | — | PK | | III §11.0 | 4 |
| `article_id` | `INTEGER` | `Integer` | non | — | FK `article(id)` **`CASCADE`** | | III §11.9 · §11.0 | 4 |
| `model` | `TEXT` | `String` | non | — | voir unicité | nom du modèle fastembed + `@` + révision courte, ex. `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2@faf4aa42` ; un changement de révision produit de nouvelles lignes | III §11.9 · §12.4 | 4 |
| `dim` | `INTEGER` | `Integer` | oui | — | | dimension du vecteur (384) | III §11.9 | 4 |
| `vector` | `BLOB` | `LargeBinary` | oui | — | | `float32` normalisé (§4) ; `NULL` = échec définitif | III §11.9 · §12.3 | 4 |
| `error` | `TEXT` | `Text` | oui | — | | renseigné quand `vector` est `NULL` | III §11.9 · V-A §24.4 | 4 |
| `created_at` | `TEXT` | `UTCDateTime` | non | — | | | III §11.9 | 4 |
| `updated_at` | `TEXT` | `UTCDateTime` | non | — | | dernière modification de la ligne | III §11.0 | 4 |

- **Unicité** : `UNIQUE(article_id, model)` (III §11.9), Sprint 4. Rejouer un embedding écrase la ligne (II §9.1).
- Une ligne à `vector` `NULL` (après `embeddings.max_failures` échecs) compte comme **traitée** pour `processed_at` et
  est **exclue** de la similarité et de la seconde passe cosine (III §11.9, V-A §24.4, V-B §28.2).

```sql
CREATE TABLE embedding (
  id         INTEGER PRIMARY KEY,
  article_id INTEGER NOT NULL REFERENCES article(id) ON DELETE CASCADE,
  model      TEXT NOT NULL,
  dim        INTEGER,
  vector     BLOB,
  error      TEXT,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL,
  UNIQUE (article_id, model)
);
```

### 3.11 `AIJob` — *créé par le worker ou l'app ; exécuté par le worker*

**Table introduite au Sprint 2** (E7) : le runner y crée un `enrich_article` par article `ready` dès ce sprint ; les
jobs restent `pending` jusqu'au Sprint 5, qui livre la file (claim, gardes, TTL, retry). La table est donc créée
complète au Sprint 2, index compris.

| Colonne | SQLite | SQLAlchemy | Null | Défaut | Contrainte | Rôle | Réf. | Sprint |
|---|---|---|---|---|---|---|---|---|
| `id` | `INTEGER` | `Integer` | non | — | PK | | III §11.0 | 2 |
| `job_type` | `TEXT` | `String` | non | — | validé par le code (registre) | V1 : `enrich_article · resolve_event · discover_topics` ; inconnu → `failed` | III §11.10 · V-A §23.1, §23.2 | 2 |
| `entity_type` | `TEXT` | `String` | non | — | validé par le code | `article · event · emerging_candidate` | III §11.10 | 2 |
| `entity_id` | `INTEGER` | `Integer` | non | — | **sans FK** | cible du job | III §11.10 | 2 |
| `priority` | `INTEGER` | `Integer` | non | — | | 60 / 50 / 10 selon le type ; 100 pour un job de l'app | III §11.10 · V-A §23.2 | 2 |
| `status` | `TEXT` | `String` | non | — | `CHECK IN ('pending','processing','completed','failed','retry','dead_letter','cancelled','skipped')` | | III §11.10 | 2 |
| `skip_reason` | `TEXT` | `String` | oui | — | validé par le code | `expired · article_not_ready · event_member · event_not_active · event_single_source · candidate_decided` | III §11.10 · V-A §23.3 | 2 |
| `attempts` · `max_attempts` | `INTEGER` | `Integer` | non | — | | `max_attempts = 3` | III §11.10 · V-A §23.5 | 2 |
| `next_attempt_at` | `TEXT` | `UTCDateTime` | **non** | — | index de claim | **fourni par l'application** (la `Clock`), sans défaut SQL : maintenant + délai du type à la création par le worker, maintenant pour un job de l'app | III §11.10 · V-A §23.1 | 2 |
| `last_error` | `TEXT` | `Text` | oui | — | | sans secret — `NULL` tant qu'aucune tentative n'a échoué. | III §11.10 · VIII T-LLM-09 | 2 |
| `created_by` | `TEXT` | `String` | non | — | `CHECK IN ('worker','app')` | | III §11.10 · V-A §23.6 | 2 |
| `started_at` · `completed_at` | `TEXT` | `UTCDateTime` | oui | — | | `started_at` : `NULL` avant le premier claim. `completed_at` : renseigné par l'application (la `Clock`) à toute transition vers `completed`, `failed`, `cancelled` ou `skipped` ; `NULL` sinon, `dead_letter` compris (une relance le laisse ou le remet à `NULL`) ; départ de la rétention de 30 jours (§6) | III §11.10, §13 · V-A §23.3, §23.6 | 2 |
| `created_at` | `TEXT` | `UTCDateTime` | non | — | | TTL (`now − created_at > ttl`) et ordre de claim | III §11.0 · V-A §23.3, §23.4 | 2 |
| `updated_at` | `TEXT` | `UTCDateTime` | non | — | | dernière modification de la ligne | III §11.0 | 2 |

**Statuts terminaux** : `completed` · `failed` · `dead_letter` · `cancelled` · `skipped`. L'app ne fait que deux
transitions, `dead_letter → pending` et `dead_letter → cancelled`, par un `UPDATE … WHERE status = 'dead_letter'`
(III §11.10, V-A §23.6).

**Contraintes et index**

| Élément | Définition | Réf. | Sprint |
|---|---|---|---|
| **unicité partielle** (un seul job actif par cible et par type) | `UNIQUE(job_type, entity_type, entity_id) WHERE status IN ('pending','processing','retry')` ; une seconde demande identique est ignorée sans erreur | III §11.10 · V-A §23.2 | 2 (testé au Sprint 5, T-DB-09) |
| index de claim | `(status, next_attempt_at, priority)` | III §11.10 | 2 |

- Le claim (`UPDATE … RETURNING`, SQLite ≥ 3.35) filtre sur `status IN ('pending','retry')`,
  `next_attempt_at <= :now`, `job_type` et `priority`, et trie par `priority DESC, created_at DESC` (V-A §23.4).
- **Idempotence des résultats** : portée par les tables métier. Un job remplace ses propres résultats pour sa cible
  dans une seule transaction : `enrich_article` supprime puis réécrit les lignes `method=llm` de l'article (III §11.10, I-08).

```sql
CREATE TABLE aijob (
  id              INTEGER PRIMARY KEY,
  job_type        TEXT NOT NULL,
  entity_type     TEXT NOT NULL,
  entity_id       INTEGER NOT NULL,
  priority        INTEGER NOT NULL,
  status          TEXT NOT NULL CHECK (status IN ('pending','processing','completed','failed','retry','dead_letter','cancelled','skipped')),
  skip_reason     TEXT,
  attempts        INTEGER NOT NULL,
  max_attempts    INTEGER NOT NULL,
  next_attempt_at TEXT NOT NULL,
  last_error      TEXT,
  created_by      TEXT NOT NULL CHECK (created_by IN ('worker','app')),
  started_at      TEXT,
  completed_at    TEXT,
  created_at      TEXT NOT NULL,
  updated_at      TEXT NOT NULL
);
CREATE UNIQUE INDEX ux_aijob_active ON aijob(job_type, entity_type, entity_id)
  WHERE status IN ('pending','processing','retry');
CREATE INDEX ix_aijob_claim ON aijob(status, next_attempt_at, priority);
```

### 3.12 `Signal` — *écrit par le worker*

Upsert horaire par le Trend Engine, sur liaisons `keyword` uniquement (V-B §29).

| Colonne | SQLite | SQLAlchemy | Null | Défaut | Contrainte | Rôle | Réf. | Sprint |
|---|---|---|---|---|---|---|---|---|
| `id` | `INTEGER` | `Integer` | non | — | PK | | III §11.0 | 8 |
| `topic_id` | `INTEGER` | `Integer` | non | — | FK `topic(id)` `RESTRICT` | | III §11.8 | 8 |
| `period` | `TEXT` | `String` | non | — | `CHECK IN ('24h','7d','30d')` | | III §11.8 | 8 |
| `computed_at` | `TEXT` | `UTCDateTime` | non | — | | | III §11.8 | 8 |
| `window_start` · `window_end` | `TEXT` | `UTCDateTime` | non | — | | fenêtre du calcul | III §11.8 · V-B §29.4 | 8 |
| `mentions` | `INTEGER` | `Integer` | non | — | | articles distincts | III §11.8 · V-B §29.2 | 8 |
| `unique_sources` · `unique_authors` · `unique_companies` | `INTEGER` | `Integer` | non | — | | | III §11.8 · V-B §29.2 | 8 |
| `growth_rate` | `REAL` | `Float` | oui | — | | `NULL` en cold start | III §11.8 · V-B §29.5, décision 17 | 8 |
| `velocity` | `REAL` | `Float` | non | — | | | III §11.8 · V-B §29.5 | 8 |
| `novelty` · `momentum` | `REAL` | `Float` | oui | — | | `NULL` en cold start | III §11.8 · V-B §29.5, décision 17 | 8 |
| `category` | `TEXT` | `String` | **oui** | — | `CHECK IN ('established','trending','rising','declining')` | `NULL` = support insuffisant | III §11.8 · V-B §29.6 | 8 |
| `created_at` | `TEXT` | `UTCDateTime` | non | — | | insertion de la ligne | III §11.0 | 8 |
| `updated_at` | `TEXT` | `UTCDateTime` | non | — | | dernière modification de la ligne | III §11.0 | 8 |

**Contraintes et index** (Sprint 8) : `UNIQUE(topic_id, period, window_end)` (upsert horaire) · index
`(topic_id, period, computed_at)` (III §11.8, V-B §29.4).

```sql
CREATE TABLE signal (
  id               INTEGER PRIMARY KEY,
  topic_id         INTEGER NOT NULL REFERENCES topic(id) ON DELETE RESTRICT,
  period           TEXT NOT NULL CHECK (period IN ('24h','7d','30d')),
  computed_at      TEXT NOT NULL,
  window_start     TEXT NOT NULL,
  window_end       TEXT NOT NULL,
  mentions         INTEGER NOT NULL,
  unique_sources   INTEGER NOT NULL,
  unique_authors   INTEGER NOT NULL,
  unique_companies INTEGER NOT NULL,
  growth_rate      REAL,
  velocity         REAL NOT NULL,
  novelty          REAL,
  momentum         REAL,
  category         TEXT CHECK (category IN ('established','trending','rising','declining')),
  created_at       TEXT NOT NULL,
  updated_at       TEXT NOT NULL,
  UNIQUE (topic_id, period, window_end)
);
CREATE INDEX ix_signal_topic_period_computed ON signal(topic_id, period, computed_at);
```

### 3.13 `EmergingCandidate` — *écrit par le worker*

Termes émergents (n-grammes des titres, dépôts GitHub) et résultat indicatif de `discover_topics` (V-B §30,
V-A §27). Le statut du candidat (`converted`, `active`…) est **dérivé à la lecture**, sans colonne (V-B §30.4).

| Colonne | SQLite | SQLAlchemy | Null | Défaut | Contrainte | Rôle | Réf. | Sprint |
|---|---|---|---|---|---|---|---|---|
| `id` | `INTEGER` | `Integer` | non | — | PK | | III §11.0 | 8 |
| `key` | `TEXT` | `String` | non | — | **UNIQUE** | terme normalisé | III §11.13 | 8 |
| `kind` | `TEXT` | `String` | non | — | `CHECK IN ('ngram','repository')` | | III §11.13 · V-B §30.2 | 8 |
| `label` | `TEXT` | `String` | non | — | | | III §11.13 | 8 |
| `first_detected_at` | `TEXT` | `UTCDateTime` | non | — | | | III §11.13 | 8 |
| `last_evidence_at` | `TEXT` | `UTCDateTime` | non | — | | dernière mise à jour de `evidence` | III §11.13 · V-B §30.4 | 8 |
| `evidence` | `TEXT` (JSON) | `JSON` | non | — | Pydantic | `mentions_7d · mentions_prev7d · growth · sources · authors · channels · stories · first_seen_at · article_ids` (≤ 20) | III §11.13 · V-B §30.4 | 8 |
| `ref_mentions` · `ref_channel_count` | `INTEGER` | `Integer` | non | — | | référence de l'évolution significative | III §11.13 · V-B §30.5 | 8 |
| `last_significant_at` | `TEXT` | `UTCDateTime` | non | — | | dernière évolution significative | III §11.13 · V-B §30.5 | 8 |
| `resurfaced_at` | `TEXT` | `UTCDateTime` | oui | — | | réapparition d'un candidat ignoré | III §11.13 · V-B §30.7 | 8 |
| `backfilled_at` | `TEXT` | `UTCDateTime` | **oui** | — | | fin du backfill d'un topic créé ; `NULL` avec `topic_id` renseigné = backfill à reprendre | III §11.13 · V-B §30.8 | 8 |
| `topic_id` | `INTEGER` | `Integer` | **oui** | — | FK `topic(id)` `RESTRICT` | topic créé sur `create_topic` | III §11.13 · V-B §30.8 | 8 |
| `llm_label` · `llm_description` | `TEXT` | `Text` | oui | — | | résultat de `discover_topics` | III §11.13 · V-A §27 | 8 |
| `covered_by_topic_id` | `INTEGER` | `Integer` | **oui** | — | FK `topic(id)` `RESTRICT` | suggestion, jamais d'écartement automatique | III §11.13 · V-A §27 | 8 |
| `suggested_keywords` | `TEXT` (JSON) | `JSON` | oui | — | Pydantic | mots-clés suggérés pour « Create topic » — `NULL` tant que `discover_topics` n'a pas évalué le candidat. | III §11.13 · V-B §30.8 | 8 |
| `assessed_at` | `TEXT` | `UTCDateTime` | oui | — | | dernier `discover_topics` — `NULL` tant que `discover_topics` n'a pas évalué le candidat. | III §11.13 | 8 |
| `created_at` | `TEXT` | `UTCDateTime` | non | — | | insertion de la ligne | III §11.0 | 8 |
| `updated_at` | `TEXT` | `UTCDateTime` | non | — | | dernière modification de la ligne | III §11.0 | 8 |

**Unicité** : `UNIQUE(key)` (III §11.13), Sprint 8.

```sql
CREATE TABLE emerging_candidate (
  id                  INTEGER PRIMARY KEY,
  key                 TEXT NOT NULL UNIQUE,
  kind                TEXT NOT NULL CHECK (kind IN ('ngram','repository')),
  label               TEXT NOT NULL,
  first_detected_at   TEXT NOT NULL,
  last_evidence_at    TEXT NOT NULL,
  evidence            TEXT NOT NULL,  -- JSON
  ref_mentions        INTEGER NOT NULL,
  ref_channel_count   INTEGER NOT NULL,
  last_significant_at TEXT NOT NULL,
  resurfaced_at       TEXT,
  backfilled_at       TEXT,
  topic_id            INTEGER REFERENCES topic(id) ON DELETE RESTRICT,
  llm_label           TEXT,
  llm_description     TEXT,
  covered_by_topic_id INTEGER REFERENCES topic(id) ON DELETE RESTRICT,
  suggested_keywords  TEXT,  -- JSON
  assessed_at         TEXT,
  created_at          TEXT NOT NULL,
  updated_at          TEXT NOT NULL
);
```

### 3.14 `EmergingDecision` — *écrit par l'app*

Décision de l'utilisateur sur un candidat. Table distincte de `EmergingCandidate` pour respecter la règle d'un seul
écrivain par table (III §11.13). **Upsert** sur `candidate_id` (mise à jour de `decision` et `decided_at`), sauf
après `create_topic`, définitif ; pas de suppression en V1 (III §11.12, V-B §30.7).

| Colonne | SQLite | SQLAlchemy | Null | Défaut | Contrainte | Rôle | Réf. | Sprint |
|---|---|---|---|---|---|---|---|---|
| `id` | `INTEGER` | `Integer` | non | — | PK | | III §11.0 | 8 |
| `candidate_id` | `INTEGER` | `Integer` | non | — | FK `emerging_candidate(id)` `RESTRICT` ; **UNIQUE** | | III §11.12 | 8 |
| `decision` | `TEXT` | `String` | non | — | `CHECK IN ('follow','ignore','mute','create_topic')` | | III §11.12 · V-B §30.7 | 8 |
| `decided_at` | `TEXT` | `UTCDateTime` | non | — | | comparé à `last_significant_at` (alerte) et `resurfaced_at` (réapparition) | III §11.12 · V-B §30.5, §30.7 | 8 |
| `created_at` | `TEXT` | `UTCDateTime` | non | — | | insertion de la ligne | III §11.0 | 8 |
| `updated_at` | `TEXT` | `UTCDateTime` | non | — | | dernière modification de la ligne | III §11.0 | 8 |

```sql
CREATE TABLE emerging_decision (
  id           INTEGER PRIMARY KEY,
  candidate_id INTEGER NOT NULL UNIQUE REFERENCES emerging_candidate(id) ON DELETE RESTRICT,
  decision     TEXT NOT NULL CHECK (decision IN ('follow','ignore','mute','create_topic')),
  decided_at   TEXT NOT NULL,
  created_at   TEXT NOT NULL,
  updated_at   TEXT NOT NULL
);
```

### 3.15 `UserPreference` — *écrit par l'app*

Suivi et sourdine d'un topic ou d'une source, **exclusifs** : poser l'un remplace l'autre (upsert), supprimer la
ligne ramène au neutre. Lu par l'app (affichage) et le worker (alertes) (VI §34.1–§34.2).

| Colonne | SQLite | SQLAlchemy | Null | Défaut | Contrainte | Rôle | Réf. | Sprint |
|---|---|---|---|---|---|---|---|---|
| `id` | `INTEGER` | `Integer` | non | — | PK | | III §11.0 | 9 |
| `subject_type` | `TEXT` | `String` | non | — | `CHECK IN ('topic','source')` | | III §11.12 · VI §34.1 | 9 |
| `subject_id` | `INTEGER` | `Integer` | non | — | sans FK (cible selon `subject_type`) | | III §11.12 | 9 |
| `action` | `TEXT` | `String` | non | — | `CHECK IN ('follow','mute')` | | III §11.12 · VI §34.1 | 9 |
| `created_at` | `TEXT` | `UTCDateTime` | non | — | | insertion de la ligne | III §11.0 | 9 |
| `updated_at` | `TEXT` | `UTCDateTime` | non | — | | dernière modification de la ligne | III §11.0 | 9 |

**Unicité** : `UNIQUE(subject_type, subject_id)` (III §11.12), Sprint 9.

```sql
CREATE TABLE user_preference (
  id           INTEGER PRIMARY KEY,
  subject_type TEXT NOT NULL CHECK (subject_type IN ('topic','source')),
  subject_id   INTEGER NOT NULL,
  action       TEXT NOT NULL CHECK (action IN ('follow','mute')),
  created_at   TEXT NOT NULL,
  updated_at   TEXT NOT NULL,
  UNIQUE (subject_type, subject_id)
);
```

### 3.16 `Setting` — *écrit par l'app*

Réglages globaux modifiables dans le dashboard. **Registre en code** : pour chaque clé, un schéma Pydantic et un
défaut. Une clé absente de la table vaut son défaut ; une valeur stockée invalide est ignorée au profit du défaut,
avec un log `warning` ; l'API valide à l'écriture (422). Le worker relit les réglages à chaque tick (VI §34.3,
T-CFG-08).

| Colonne | SQLite | SQLAlchemy | Null | Défaut | Contrainte | Rôle | Réf. | Sprint |
|---|---|---|---|---|---|---|---|---|
| `key` | `TEXT` | `String` | non | — | **PK** | clé du registre | III §11.12 · VI §34.3 | 9 |
| `value` | `TEXT` (JSON) | `JSON` | non | — | Pydantic (schéma de la clé) | | III §11.12 | 9 |
| `updated_at` | `TEXT` | `UTCDateTime` | non | — | | | III §11.12 | 9 |

**Registre en code** (VI §34.3 fait foi ; rappel des clés) :

| Clé | Type | Défaut | Utilisée à partir du |
|---|---|---|---|
| `timezone` | nom IANA | `Europe/Paris` | Sprint 9 (affichage), 10 (heures calmes, digests) |
| `display.importance_threshold` | entier 0–100 | 0 | Sprint 9 |
| `alerts.mode` | `immediate` \| `digest_only` | `immediate` | Sprint 10 |
| `alerts.importance_threshold` | entier 0–100 | 50 | Sprint 10 |
| `alerts.followed_threshold` | entier 0–100 | 25 | Sprint 10 |
| `alerts.max_age` | heures | 48 | Sprint 10 |
| `alerts.title_wait` | minutes | 30 | Sprint 10 |
| `alerts.quiet_hours` | `{start, end}` \| `null` | `null` | Sprint 10 |
| `alerts.max_per_day` | entier | 20 | Sprint 10 |
| `alerts.routing` | type → liste de canaux | VI §33.9 | Sprint 10 |
| `digest.daily` | `{enabled, time}` | `{true, "08:00"}` | Sprint 10 |
| `digest.weekly` | `{enabled, day, time}` | `{true, "monday", "08:00"}` | Sprint 10 |
| `digest.max_items` | entier | 10 | Sprint 10 |

Ajouter une clé ne demande pas de migration : c'est une entrée du registre. `alerts.tick` et `alerts.send_timeout`
vivent dans `pipeline.yaml`, pas ici. Aucun secret n'est stocké dans `Setting` (VI §32.3).

```sql
CREATE TABLE setting (
  key        TEXT PRIMARY KEY,
  value      TEXT NOT NULL,  -- JSON
  updated_at TEXT NOT NULL
);
```

### 3.17 `ReadState` — *écrit par l'app*

État « lu » au niveau de l'Event, ou de l'article s'il n'appartient à aucun Event (III décision 11). « Marquer non
lu » supprime la ligne ; un `ReadState` sur un Event `merged` est ignoré (VI §31.5).

| Colonne | SQLite | SQLAlchemy | Null | Défaut | Contrainte | Rôle | Réf. | Sprint |
|---|---|---|---|---|---|---|---|---|
| `id` | `INTEGER` | `Integer` | non | — | PK | | III §11.0 | 9 |
| `subject_type` | `TEXT` | `String` | non | — | `CHECK IN ('event','article')` | | III §11.12 | 9 |
| `subject_id` | `INTEGER` | `Integer` | non | — | sans FK (cible selon `subject_type`) | | III §11.12 | 9 |
| `read_at` | `TEXT` | `UTCDateTime` | non | — | | comparé à `activity_at` de la story | III §11.12 · VI §31.5 | 9 |
| `created_at` | `TEXT` | `UTCDateTime` | non | — | | insertion de la ligne | III §11.0 | 9 |
| `updated_at` | `TEXT` | `UTCDateTime` | non | — | | dernière modification de la ligne | III §11.0 | 9 |

**Unicité** : `UNIQUE(subject_type, subject_id)`, qui sert aussi d'index de lecture (III §11.12), Sprint 9.

```sql
CREATE TABLE read_state (
  id           INTEGER PRIMARY KEY,
  subject_type TEXT NOT NULL CHECK (subject_type IN ('event','article')),
  subject_id   INTEGER NOT NULL,
  read_at      TEXT NOT NULL,
  created_at   TEXT NOT NULL,
  updated_at   TEXT NOT NULL,
  UNIQUE (subject_type, subject_id)
);
```

### 3.18 `AlertLog` — *écrit par le worker*

Journal des alertes, qui sert aussi à leur **déduplication** : le log précède l'envoi (T1 `sending`, envoi hors
transaction, T2 `sent` ou `failed`), garantie « au plus une fois », sans reprise en V1 (VI §33.5).

| Colonne | SQLite | SQLAlchemy | Null | Défaut | Contrainte | Rôle | Réf. | Sprint |
|---|---|---|---|---|---|---|---|---|
| `id` | `INTEGER` | `Integer` | non | — | PK | | III §11.0 | 10 |
| `alert_type` | `TEXT` | `String` | non | — | `CHECK IN ('important_event','emerging_topic','daily_digest','weekly_digest','system')` | `system` : alertes d'exploitation (Sprint 11) | III §11.13 · VII §39.6 | 10 |
| `subject_type` | `TEXT` | `String` | non | — | `CHECK IN ('event','emerging_candidate','digest','system')` | `event` (`important_event`), `emerging_candidate` (`emerging_topic`), `digest` (digests), `system` | III §11.13 · VI §33.3 | 10 |
| `subject_id` | `INTEGER` | `Integer` | oui | — | | `NULL` pour `digest` et `system` : la période ou la condition est portée par `dedup_key` | III §11.13 · VI §33.4 · VII §39.6 | 10 |
| `channel` | `TEXT` | `String` | non | — | `CHECK IN ('email','telegram')` | | III §11.13 | 10 |
| `status` | `TEXT` | `String` | non | — | `CHECK IN ('sending','sent','failed','suppressed')` | `suppressed` : plafond quotidien atteint, jamais émise ; `sending` → `failed` au démarrage (`error = 'interrupted'`) | III §11.13 · VI §33.5, §33.6 | 10 |
| `error` | `TEXT` | `Text` | oui | — | | après nettoyage des secrets par valeur — `NULL` si l'envoi n'a pas échoué. | III §11.13 · VII §42.4 | 10 |
| `dedup_key` | `TEXT` | `String` | non | — | **UNIQUE** | inclut le canal (formats en VI §33.4) | III §11.13 · VI §33.4 | 10 |
| `created_at` | `TEXT` | `UTCDateTime` | non | — | | insertion de la ligne | III §11.0 | 10 |
| `updated_at` | `TEXT` | `UTCDateTime` | non | — | | dernière modification de la ligne | III §11.0 | 10 |

**Contraintes et index** (Sprint 10) : `UNIQUE(dedup_key)` (T-DB-10) · index `(alert_type, subject_type, subject_id)`
(III §11.13).

| Type | `dedup_key` (VI §33.4) |
|---|---|
| `important_event` | `important_event:{event_id}:{channel}` |
| `emerging_topic` | `emerging:{candidate_id}:{last_significant_at}:{channel}` |
| `daily_digest` | `daily:{date locale AAAA-MM-JJ}:{channel}` |
| `weekly_digest` | `weekly:{année ISO}-W{semaine ISO}:{channel}` |
| `system` | `system:{condition}:{since}:{channel}` |

```sql
CREATE TABLE alert_log (
  id           INTEGER PRIMARY KEY,
  alert_type   TEXT NOT NULL CHECK (alert_type IN ('important_event','emerging_topic','daily_digest','weekly_digest','system')),
  subject_type TEXT NOT NULL CHECK (subject_type IN ('event','emerging_candidate','digest','system')),
  subject_id   INTEGER,
  channel      TEXT NOT NULL CHECK (channel IN ('email','telegram')),
  status       TEXT NOT NULL CHECK (status IN ('sending','sent','failed','suppressed')),
  error        TEXT,
  dedup_key    TEXT NOT NULL UNIQUE,
  created_at   TEXT NOT NULL,
  updated_at   TEXT NOT NULL
);
CREATE INDEX ix_alert_log_subject ON alert_log(alert_type, subject_type, subject_id);
```

### 3.19 `SystemState` — *écrit par le worker*

Table clé/valeur ; **chaque clé a un seul écrivain**, et toutes sont écrites par le worker (III §11.13,
VII §39.3). L'app les lit pour `/health`, `/api/health`, `/api/status` et le lu / non lu (II §8.3).

| Colonne | SQLite | SQLAlchemy | Null | Défaut | Contrainte | Rôle | Réf. | Sprint |
|---|---|---|---|---|---|---|---|---|
| `key` | `TEXT` | `String` | non | — | **PK** | | III §11.13 | 1 |
| `value` | `TEXT` (JSON) | `JSONText` | non | — | Pydantic (schéma par clé) | | III §11.13 | 1 |
| `updated_at` | `TEXT` | `UTCDateTime` | non | — | | | III §11.13 | 1 |

**Clés et schéma de leur valeur** — une clé n'est pas une migration : elle apparaît au sprint qui l'écrit.

| Clé | Valeur | Écrite | Réf. | Sprint |
|---|---|---|---|---|
| `worker_heartbeat` | `{at, started_at, version, pid}` | toutes les 30 s, avant le chargement des modèles | III §11.13 · VII §39.3, décision 14 | 1 |
| `trends_since` | `{at}` : première insertion d'un article `ready` | une seule fois, par le runner | III §11.13 · IV §14.3 · V-B §29.3 | 2 |
| `embeddings` | `{state, since}` : état du moteur (`up` / `down`) et depuis quand | à chaque changement d'état | III §11.13 · V-A §24.4 · VII §39.2 | 4 |
| `llm_gateway` | `{state, since, reason, open_until}` | à chaque transition du disjoncteur | III §11.13 · V-A §24.2 | 6 |
| `llm_usage` | `{day, requests}` (jour UTC) | à chaque appel ayant reçu une réponse | III §11.13 · V-A §24.3 | 6 |
| `trends_last_run` | `{at, duration_s, status, error}` : dernier calcul du Trend Engine | à chaque passe horaire | III §11.13 · V-B §29.1 · VII §39.2 | 8 |
| `alerting` | `{email: enabled\|disabled, telegram: enabled\|disabled, interrupted_at_boot: n}` | au démarrage | III §11.13 · VII §39.3 | 10 |
| `ops_metrics` | instantané des métriques de VII §39.2, avec `computed_at` | toutes les 60 s | III §11.13 · VII §39.3 | 11 |
| `ops_conditions` | conditions actives : `{name: {since, alerted_at}}` (épisodes persistés) | à chaque transition | III §11.13 · VII §39.3, §39.6 | 11 |
| `last_backup` | `{at, snapshot_id, size_bytes, duration_s}` | backup réussi | III §11.13 · VII §38.2 | 11 |
| `backup_last_attempt` | `{at, status, error}` | chaque tentative de backup | III §11.13 · VII §38.2 | 11 |
| `last_restore_test` | `{at, status, snapshot_id, error}` | chaque test de restauration | III §11.13 · VII §38.4 | 11 |

Sprints des clés : heartbeat au Sprint 1, `trends_since` avec le runner (Sprint 2), `embeddings` avec la file dérivée
(Sprint 4), disjoncteur et budget LLM (Sprint 6), Trend Engine (Sprint 8), canaux d'alerte (Sprint 10), monitoring
et backup (Sprint 11) (VIII §47.2).

```sql
CREATE TABLE system_state (
  key        TEXT PRIMARY KEY,
  value      TEXT NOT NULL,  -- JSON
  updated_at TEXT NOT NULL
);
```

### 3.20 `article_fts` — index plein texte *(écrit par le worker, via triggers)*

Table virtuelle **FTS5** sur `title` et `summary`, en mode *external content* adossé à `article`, tokenizer
`unicode61 remove_diacritics 2`. Maintenue par **trois triggers** sur insertion, mise à jour de `title` ou `summary` et
suppression d'`article` : la mise à jour d'un résumé par le LLM met l'index à jour automatiquement (III §11.14, T-DB-11). La
recherche accepte toute saisie, syntaxe FTS5 comprise (VI §31.4.1, VIII §47.2 Sprint 3).

| Élément | Définition | Réf. | Sprint |
|---|---|---|---|
| table virtuelle | `article_fts` (`title`, `summary`), `content='article'`, `content_rowid='id'` | III §11.14 | 3 |
| trigger d'insertion | `AFTER INSERT ON article` | III §11.14 | 3 |
| trigger de mise à jour | `AFTER UPDATE OF title, summary ON article` : seules les colonnes indexées déclenchent la mise à jour (I-18, T-DB-11) | III §11.14 | 3 |
| trigger de suppression | `AFTER DELETE ON article` (dont la suppression des `filtered` à 30 j) | III §11.14 · §13 | 3 |

- **Sprint 3** : la migration crée la table et les triggers alors que des articles existent déjà (Sprint 2) ; elle
  remplit l'index par la commande FTS5 `rebuild`.
- L'index couvre toutes les lignes d'`article` (mode *external content*) ; le filtrage par `status` se fait dans la
  requête de recherche, jointe à `article`.

```sql
CREATE VIRTUAL TABLE article_fts USING fts5(
  title, summary,
  content='article', content_rowid='id',
  tokenize='unicode61 remove_diacritics 2'
);

CREATE TRIGGER article_fts_ai AFTER INSERT ON article BEGIN
  INSERT INTO article_fts(rowid, title, summary) VALUES (new.id, new.title, new.summary);
END;

CREATE TRIGGER article_fts_ad AFTER DELETE ON article BEGIN
  INSERT INTO article_fts(article_fts, rowid, title, summary)
  VALUES ('delete', old.id, old.title, old.summary);
END;

CREATE TRIGGER article_fts_au AFTER UPDATE OF title, summary ON article BEGIN
  INSERT INTO article_fts(article_fts, rowid, title, summary)
  VALUES ('delete', old.id, old.title, old.summary);
  INSERT INTO article_fts(rowid, title, summary) VALUES (new.id, new.title, new.summary);
END;

-- à la création, sur une table article déjà remplie (Sprint 3)
INSERT INTO article_fts(article_fts) VALUES ('rebuild');
```

---

## 4. Embeddings : stockage des vecteurs

- **Format** : BLOB de `float32`, **normalisé à la norme 1 à l'écriture** ; la similarité cosine devient un produit
  scalaire (III §12.3). Modèle cible de 384 dimensions (III décision 12, §12.1), soit 1 536 octets par vecteur.
- **Conversion à l'écriture** : fastembed renvoie des vecteurs **`float64`** (constat de T0.3, V-01, fastembed
  0.8.1). Le worker convertit en `float32`, normalise, puis sérialise :

  ```python
  v = np.asarray(raw, dtype=np.float32)
  v /= np.linalg.norm(v)
  row.vector, row.dim = v.tobytes(), v.shape[0]
  ```

  À la lecture : `np.frombuffer(row.vector, dtype=np.float32)`.
- **Modèle** : cible `paraphrase-multilingual-MiniLM-L12-v2` ; révision et empreintes relevées en T0.3 et reprises
  dans l'ADR-0008 (rapport de cadrage §3, V-01). On ne compare que des vecteurs du **même** `model` (III §12.4).
- **Ce qui est embeddé** : articles `ready` seulement, titre + 1 000 premiers caractères du contenu, avant la purge
  du contenu (III §12.2).
- **Fenêtre de similarité** : matrice en mémoire du worker, reconstruite depuis la base au démarrage ; environ 3 Mo
  pour 2 000 articles (III §12.4).
- **Changement de modèle** : nouvelles lignes pour le nouveau `model` ; pas de ré-embedding automatique de
  l'historique (sélection sur `content_purged_at IS NULL`, V-A §24.4 ; III §12.5).

## 5. Migrations

- **Alembic**, avec `render_as_batch=True` : SQLite ne sait pas modifier une contrainte par `ALTER`, le mode batch
  reconstruit la table (III §10.5).
- **Une migration par sprint au moins** : chaque sprint ajoute ses tables, colonnes, index et triggers ; le schéma
  cible de ce document n'est pas créé d'un bloc (VIII §47.1). Les colonnes « Sprint » du §3 donnent l'ordre.
- **Service one-shot `migrate`** (`alembic upgrade head`, image backend, sans réseau) : `app` et `worker` démarrent
  après sa réussite (`depends_on: condition: service_completed_successfully`). **Aucun des deux processus
  applicatifs ne migre** (III §10.5, décision 15 ; VII §36.2, §36.3).
- **Vérification au démarrage** : `app` et `worker` comparent la révision en base à la révision `head` du code et
  **refusent de démarrer** si elles diffèrent (III §10.1, VII §36.3, T-DB-02). Au reboot du VPS, `migrate` n'est pas
  rejoué : cette vérification est le garde-fou (VII §36.3).
- **Réversibilité** : chaque migration fournit un `downgrade`, **ou se déclare irréversible dans son en-tête**
  (VII §36.9, T-DB-08). `scripts/deploy.sh` refuse un rollback à travers une migration ; la procédure IX §56.6-P2
  s'applique (*downgrade* avec l'image courante, ou restauration du snapshot pris au déploiement) (VIII §49.5).
- **Moteur de `migrate`** (III §10.5) : moteur **synchrone** propre à `migrate`, créé par `env.py` sur l'URL
  construite à partir de `RADAR_DB_PATH`, fixé par Compose ; `alembic.ini` ne porte aucune URL (P-01 de
  `architecture.md`). Même technique que §2.3 : l'écouteur `connect` pose `isolation_level = None` (pysqlite n'ouvre
  plus de transaction implicite) et exécute les PRAGMA hors transaction ; l'écouteur `begin` émet `BEGIN IMMEDIATE`.
  Seul `foreign_keys` diffère.
- **Clés étrangères désactivées pendant les migrations** (III §10.2, §10.5 ; I-16) : `PRAGMA foreign_keys=OFF` est
  posé dans l'écouteur `connect`, sur la connexion DBAPI, donc avant toute transaction : SQLite l'ignore à
  l'intérieur d'une transaction. Sans ce PRAGMA, la reconstruction d'une table en mode batch
  (copie, `DROP TABLE` de l'ancienne, renommage) exécuterait un `DELETE` implicite qui déclencherait les
  `ON DELETE CASCADE` de `article_topic`, `article_entity` et `embedding`, ou échouerait sur les `RESTRICT`.
- **Une seule transaction par exécution** : `transactional_ddl=True` et `transaction_per_migration=False`.
  Alembic déclare SQLite sans DDL transactionnel : sans `transactional_ddl=True`, `context.begin_transaction()` ne fait rien et chaque migration est validée séparément. Et pysqlite, dans son mode par défaut, n'émet pas de `BEGIN` avant une instruction DDL, qui serait validée aussitôt : `isolation_level = None` et l'écouteur `begin` placent tout le DDL de l'exécution dans une seule transaction explicite.
- **Contrôle d'intégrité** : `env.py` exécute `PRAGMA foreign_key_check` après `context.run_migrations()`, dans la
  même transaction, avant le commit ; une violation lève une exception et annule tout : la révision Alembic et le
  schéma restent ceux d'avant l'exécution (III §10.5).
- **Test** : **T-DB-13** (VIII §50.5) vérifie `foreign_keys` = 0 sur la connexion de `migrate`, l'échec sur violation
  avec révision et schéma inchangés (Sprint 1), puis la conservation des tables filles et la recréation des triggers d'`article_fts` lors
  d'une reconstruction d'`article` (complément au Sprint 3).
- **Connexions applicatives** : `app` et `worker` gardent toujours `foreign_keys=ON` (§2.2).
- **Index plein texte** : la table virtuelle `article_fts` et ses triggers ne sont pas produits par l'autogénération
  d'Alembic ; ils s'écrivent en SQL explicite dans la migration du Sprint 3. Une migration qui reconstruit `article`
  supprime l'ancienne table, et avec elle ses triggers : elle **recrée les trois triggers de `article_fts`**
  (III §10.5, §11.14).

```python
# env.py (indicatif) — moteur synchrone propre à migrate, distinct de celui de app et worker
import os
from alembic import context
from sqlalchemy import create_engine, event

# chemin fixé par Compose (RADAR_DB_PATH=/data/radar.db) ; alembic.ini ne porte aucune URL (P-01)
engine = create_engine(f"sqlite:///{os.environ['RADAR_DB_PATH']}")

@event.listens_for(engine, "connect")
def _on_connect(dbapi_connection, connection_record):
    dbapi_connection.isolation_level = None   # pysqlite n'ouvre plus de transaction implicite
    cursor = dbapi_connection.cursor()        # PRAGMA exécutés hors transaction
    for pragma in MIGRATE_PRAGMAS:            # PRAGMA du §2.2, avec foreign_keys=OFF au lieu de ON
        cursor.execute(pragma)
    cursor.close()

@event.listens_for(engine, "begin")
def _on_begin(conn):
    conn.exec_driver_sql("BEGIN IMMEDIATE")   # même technique que III §10.3

with engine.connect() as connection:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,
        transactional_ddl=True,               # Alembic déclare SQLite sans DDL transactionnel
        transaction_per_migration=False,      # une seule transaction pour toute l'exécution
    )
    with context.begin_transaction():
        context.run_migrations()
        violations = connection.exec_driver_sql("PRAGMA foreign_key_check").fetchall()
        if violations:                        # exception : rollback, révision et schéma inchangés
            raise RuntimeError(f"violations de clés étrangères : {violations}")
```

## 6. Rétention

La table de rétention fait foi : **III §13**. Toute suppression est exécutée par l'**étage de purge** du worker,
journalisée à chaque passage ; aucune donnée métier n'est supprimée hors de ce tableau (II §8.5, III §13).

En résumé, pour le schéma :

- **Contenu** (`article.content`) : tampon de traitement. Purgé immédiatement pour `filtered` et `duplicate` ; pour
  un `ready`, après `processed_at` + délai de grâce, jamais tant qu'un job de l'article est en `dead_letter`.
  `content_purged_at` trace la purge, `content_hash` est conservé.
- **Lignes supprimées** : articles `filtered` (les liaisons et embeddings suivent par `CASCADE`, l'index
  `article_fts` par son trigger), jobs terminaux hors `dead_letter`, `CollectorRun`, puis `AlertLog` au-delà de son
  délai ; `Signal` horaires réduits à une valeur par jour.
- **Conservé indéfiniment** : articles `ready` et `duplicate` (sans contenu), `Event`, `Topic`, `Entity`, liaisons,
  `Embedding`, préférences, réglages, candidats et décisions, `SystemState`.
- **Départ des délais** (III §13, I-17) : `aijob.completed_at` · `collector_run.finished_at` · `article.discovered_at`
  (articles `filtered`) · `alert_log.created_at`.


---

## 7. Incohérences relevées

Écarts entre parties de la spec, ou trous, relevés en rédigeant ce document (T0.4, #68), puis à sa revue (I-18).
Chacun cite ses passages. Le propriétaire les a tous tranchés le 2026-09-23 ; les décisions sont appliquées à la spec
et à ce document par T0.4b (#69). Les identifiants `I-nn` sont stables.

#### I-01 — Nommage SQL des tables

- La spec nomme les tables en `CamelCase` dans les tableaux (III §11) et en minuscules dans ses requêtes : `aijob`,
  `article`, `embedding` (V-A §23.4, §24.4, §24.5), `article_fts` (III §11.14). Elle ne fixe pas le nom SQL des
  tables composées (`CollectorRun`, `ArticleTopic`, `EmergingCandidate`…), ni la convention (`aijob` est écrit sans
  séparateur).

Décision (2026-09-23) : tables SQL en `snake_case` ; `aijob` est gardé tel qu'il figure dans les requêtes de V-A — appliquée dans III §11.0 et dans ce document (en-tête, §1.1, blocs SQL du §3).

#### I-02 — Liste des tables portant `created_at` et `updated_at`

- **III §11.0** : « `created_at` et, pour les tables modifiables, `updated_at` ».
- Les tables de III §11 ne listent ces colonnes que ponctuellement : `ArticleTopic.created_at` (§11.5),
  `Embedding.created_at` (§11.9), `Setting.updated_at` et `SystemState.updated_at` (§11.12, §11.13). D'autres
  parties utilisent `AIJob.created_at` (V-A §23.3, §23.4) et `Topic.created_at` (V-B §29.3) sans qu'ils figurent
  dans III. Certaines tables portent un horodatage métier qui pourrait en tenir lieu (`ReadState.read_at`,
  `EmergingDecision.decided_at`, `CollectorRun.started_at`, `EmergingCandidate.first_detected_at`).
- Non fixé : quelles tables sont « modifiables », et si l'horodatage métier remplace `created_at` / `updated_at`.

Décision (2026-09-23) : `created_at` sur toutes les tables à identifiant `id` et sur les deux tables de liaison ; `updated_at` sur les tables dont les lignes sont modifiées après insertion, listées explicitement — appliquée dans III §11.0 et dans ce document (§1.1, §3).

#### I-03 — Nullabilité et défauts non précisés

- **III §11.0** fixe la règle « `NULL` = inconnu », mais la plupart des colonnes de III §11 n'ont ni nullabilité ni
  défaut écrits. Elles étaient marquées « non précisé » dans les tableaux du §3 ; la liste par table est donnée en
  I-15.

Décision (2026-09-23) : non nul par défaut ; nullable seulement si la spec le dit ou si `NULL` a un sens (valeur inconnue ou absente), chaque colonne nullable étant justifiée — appliquée dans III §11.0 et dans ce document (§1.1, tous les tableaux du §3).

#### I-04 — Défaut de `AIJob.next_attempt_at`

- **III §11.10** : `next_attempt_at` « non nul, défaut = maintenant ».
- **III §10.6** : « Aucune expression temporelle SQL (`CURRENT_TIMESTAMP`, `datetime('now')`) dans le code ni dans
  les requêtes […]. Les valeurs par défaut de colonnes, comme celle de `AIJob.next_attempt_at`, restent un filet de
  sécurité. »
- Un défaut SQL « maintenant » ne peut s'écrire qu'avec une expression temporelle, et `CURRENT_TIMESTAMP` produit
  `AAAA-MM-JJ HH:MM:SS`, sans `T` ni fuseau, alors que `UTCDateTime` stocke de l'ISO-8601 avec fuseau (III §10.6).
  Non fixé : défaut SQL (et son format) ou défaut côté SQLAlchemy (`default=` Python, lu par la `Clock`).

Décision (2026-09-23) : `AIJob.next_attempt_at` est non nul et fourni par l'application (la `Clock`), sans défaut SQL — appliquée dans III §10.6, §11.10 et dans ce document (§2.4, §3.11).

#### I-05 — Exclusions des topics sans colonne

- **IV §16.3** : chaque topic de `topics.yaml` porte une liste `exclude` (termes masqués avant matching, §20.3).
- **III §11.4** : colonnes de `Topic` = `slug · name · description · parent_id · origin · keywords · enabled` ;
  `keywords` est décrit comme « mots-clés et motifs utilisés par le relevance filter ». Non fixé : si `exclude` est
  stocké dans `keywords`, dans une autre colonne, ou seulement en mémoire.

Décision (2026-09-23) : `Topic.keywords` porte `{include, exclude}` — appliquée dans III §11.4, IV §16.3 et dans ce document (§3.5).

#### I-06 — `created_at` sur `ArticleTopic` mais pas sur `ArticleEntity`

- **III §11.5** : `ArticleTopic` = `article_id · topic_id · method · confidence · created_at`.
- **III §11.7** : `ArticleEntity` = `article_id · entity_id · method · confidence`, sans `created_at`.

Décision (2026-09-23) : `created_at` sur `ArticleEntity`, comme sur `ArticleTopic` — appliquée dans III §11.0, §11.7 et dans ce document (§3.8).

#### I-07 — Index de lecture non spécifiés

- **IV §21.5** : le disjoncteur par source lit les runs `failed` consécutifs les plus récents dans `CollectorRun` ;
  **III §13** : `CollectorRun` supprimé à 30 jours. **III §11.11** ne spécifie aucun index sur `CollectorRun`.
- **V-B §29** (Trend Engine) et **VI §31.6** (vue Topic) lisent les liaisons par topic ; **V-B §28.4** compte les
  entités communes. **III §11.5, §11.7** ne donnent que la clé primaire `(article_id, …)`, sans index sur `topic_id`
  ni `entity_id`.
- La spec ne dit pas si ces index sont voulus ou laissés à l'implémenteur (VII « Points d'interprétation » ne les
  cite pas).

Décision (2026-09-23) : index `collector_run(source_id, finished_at)`, `article_topic(topic_id)` et `article_entity(entity_id)` — appliquée dans III §11.5, §11.7, §11.11 et dans ce document (§3.4, §3.7, §3.8).

#### I-08 — Exemple d'idempotence avec un `job_type` supprimé

- **III §11.10** : « par exemple `extract_topics` supprime puis réécrit les lignes `method=llm` de l'article ».
- **V-A §23.2** et **V-A décision 3** : catalogue V1 réduit à `enrich_article · resolve_event · discover_topics` ;
  `extract_topics` est fusionné dans `enrich_article`.

Décision (2026-09-23) : l'exemple d'idempotence cite `enrich_article` — appliquée dans III §11.10.

#### I-09 — Création d'`AIJob` par l'app pour le rattachement de l'historique

- **II §8.3** (« Deux conséquences ») : l'app insère des jobs « en réponse à une action utilisateur — régénérer un
  résumé, **rattacher l'historique à un topic créé**, relancer un `dead_letter` ».
- **V-A décision 18, §24.6** et **V-B §30.8** : le rattachement de l'historique est un traitement **déterministe,
  hors `AIJob`**, déclenché par la lecture des `EmergingDecision` ; les jobs créables par l'app sont
  `enrich_article` et `resolve_event` (régénération). **V-A §23.6** : la relance d'un `dead_letter` est un `UPDATE`,
  pas une création.

Décision (2026-09-23) : le rattachement de l'historique à un topic créé est un traitement déterministe, sans `AIJob` ; l'app ne crée que des jobs de régénération — appliquée dans II §8.3.

#### I-10 — Représentant d'un Event

- **III §11.3** : `representative_article_id` = « article le plus ancien du groupe » (sans critère de date ni de
  statut) ; **II §7.2** : titre de repli = « titre de l'article le plus ancien du groupe ».
- **V-B décision 10, §28.8** : représentant = **membre `ready` le plus ancien par `published_at`**.

Décision (2026-09-23) : représentant d'un Event = membre `ready` le plus ancien par `published_at` — appliquée dans III §11.3, II §7.2 et dans ce document (§3.9).

#### I-11 — Valeur de `Embedding.model`

- **III §11.9, §12.4** : colonne `model`, et comparaison « que des vecteurs produits par le même modèle ».
- **III §12.1** : révision et empreinte du modèle épinglées au build (ADR-0008). La spec ne dit pas ce que contient
  `model` (nom fastembed, dépôt Hugging Face réellement téléchargé, révision), alors que T0.3 a constaté que le nom
  fastembed (`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`) et le dépôt téléchargé
  (`qdrant/paraphrase-multilingual-MiniLM-L12-v2-onnx-Q`) diffèrent (rapport de cadrage §3, V-01).

Décision (2026-09-23) : `Embedding.model` = nom du modèle fastembed + `@` + révision courte ; un changement de révision produit de nouvelles lignes — appliquée dans III §11.9, §12.4 et dans ce document (§3.10).

#### I-12 — `AlertLog.subject_type` et `subject_id` hors alertes `system`

- **III §11.13** : `subject_type` · `subject_id`, sans liste de valeurs ni `CHECK` ; seule la valeur du type
  `system` est fixée (`subject_type = 'system'`, `subject_id` `NULL`, III §11.13, VII §39.6).
- **VI §33.3** : sujets = Event (`important_event`), candidat (`emerging_topic`), jour (`daily_digest`), semaine
  (`weekly_digest`). Les valeurs de `subject_type` et le contenu de `subject_id` pour un digest (jour, semaine) ne
  sont pas écrits.

Décision (2026-09-23) : `AlertLog.subject_type` ∈ {`event`, `emerging_candidate`, `digest`, `system`} avec `CHECK` ; `subject_id` `NULL` pour `digest` et `system` — appliquée dans III §11.13 et dans ce document (§3.18).

#### I-13 — `AlertLog` sans horodatage

- **III §11.13** : colonnes de `AlertLog` sans `created_at` ni date d'envoi.
- Pourtant : **VI §33.10**, l'historique expose « type, sujet, canal, statut, erreur, **date** » ; **VI §33.6**, le
  plafond compte les alertes « par jour local » ; **III §13**, `AlertLog` est conservé **1 an** ; **VII §39.2**,
  alertes par statut « sur 24 h ». La convention III §11.0 (`created_at`) couvrirait le besoin, mais la table ne le
  liste pas (voir aussi I-02).

Décision (2026-09-23) : `AlertLog` reçoit `created_at` (et `updated_at`, par I-02) — appliquée dans III §11.0, §11.13 et dans ce document (§3.18).

#### I-14 — Schémas de valeur de certaines clés `SystemState`

- **`trends_last_run`** : « dernier calcul du Trend Engine » (III §11.13, V-B §29.1) ; **VII §39.2** y lit « la
  dernière exécution » et la durée du job analytique est « en mémoire ; `SystemState.trends_last_run` ». Aucun schéma
  de valeur n'est écrit.
- **`embeddings`** : **V-A §24.4** dit seulement qu'il « passe à `down` » ; **VII §39.2** : « état du moteur (`up` /
  `down`, depuis) » ; **VII §40.3** montre `{"state": "up", "since": …}` dans la réponse de `/api/health`. Pas de
  schéma écrit pour la valeur stockée.
- **`trends_since`** : « horodatage » (V-B §29.3), sans forme JSON précisée (chaîne ISO-8601 ou objet).

Décision (2026-09-23) : `trends_last_run` = `{at, duration_s, status, error}` · `embeddings` = `{state, since}` · `trends_since` = `{at}` — appliquée dans III §11.13 et dans ce document (§3.19).

#### I-15 — Colonnes dont la nullabilité n'est pas écrite

Complète I-03. Colonnes dont la nullabilité n'était pas écrite (III §11 ne disait ni « non nul » ni « nullable ») :

- `Source` : `key`, `name`, `type`, `url`, `config`, `enabled`, `poll_interval`, `relevance`, `extract`, `checkpoint`, `last_success_at`, `last_error`, `last_http_status`.
- `Article` : `source_id`, `url`, `canonical_url`, `title`, `relevance_score`, `status`, `summary_origin`, `metrics`, `clustered_semantic`.
- `CollectorRun` : `source_id`, `started_at` · `finished_at`, `status`, `items_fetched`, `items_created`, `items_duplicate`, `items_filtered`, `items_skipped`, `items_too_old`, `extractions_attempted` · `extractions_failed`, `requests_count`, `http_status`, `error`.
- `Topic` : `slug`, `name`, `origin`, `keywords`, `enabled`, `created_at`.
- `Entity` : `type`, `name`, `canonical_name`, `origin`.
- `ArticleTopic` : `confidence`, `created_at`.
- `ArticleEntity` : `confidence`.
- `Event` : `title_origin`, `representative_article_id`, `first_seen_at` · `last_seen_at`, `article_count`, `status`.
- `Embedding` : `article_id`, `model`, `created_at`.
- `AIJob` : `job_type`, `entity_type`, `entity_id`, `priority`, `status`, `attempts` · `max_attempts`, `last_error`, `created_by`, `created_at`.
- `Signal` : `topic_id`, `period`, `computed_at`, `window_start` · `window_end`, `mentions`, `unique_sources` · `unique_authors` · `unique_companies`, `velocity`.
- `EmergingCandidate` : `key`, `kind`, `label`, `first_detected_at`, `last_evidence_at`, `evidence`, `ref_mentions` · `ref_channel_count`, `last_significant_at`, `suggested_keywords`, `assessed_at`.
- `EmergingDecision` : `candidate_id`, `decision`, `decided_at`.
- `UserPreference` : `subject_type`, `subject_id`, `action`.
- `Setting` : `value`, `updated_at`.
- `ReadState` : `subject_type`, `subject_id`, `read_at`.
- `AlertLog` : `alert_type`, `subject_type`, `channel`, `status`, `error`, `dedup_key`.
- `SystemState` : `value`, `updated_at`.

Décision (2026-09-23) : même règle que I-03 : chaque colonne de la liste est désormais `non` ou `oui`, chaque `oui` justifié — appliquée dans III §11.0 et dans ce document (§3).

#### I-16 — Reconstruction de table et `PRAGMA foreign_keys=ON`

- **III §10.2** : `PRAGMA foreign_keys=ON` sur **toute nouvelle connexion**, par l'écouteur `connect`.
- **III §10.5** : migrations Alembic en `render_as_batch=True`, qui reconstruit une table (copie, suppression de
  l'ancienne, renommage) quand `ALTER` ne suffit pas.
- Avec les clés étrangères actives, SQLite exécute un `DELETE` implicite avant un `DROP TABLE` : supprimer l'ancienne
  `article` déclencherait les `ON DELETE CASCADE` de `article_topic`, `article_entity` et `embedding` (§1.3), ou
  échouerait sur les `RESTRICT`. La spec ne dit pas si la connexion du service `migrate` désactive les clés
  étrangères pendant une reconstruction.

Décision (2026-09-23) : la connexion de `migrate` fonctionne avec `PRAGMA foreign_keys=OFF`, posé par l'écouteur `connect` du moteur synchrone de `migrate` (URL construite à partir de `RADAR_DB_PATH`, `alembic.ini` sans URL : P-01 de `architecture.md`) sur la connexion DBAPI (`isolation_level = None`), avant toute transaction ; l'écouteur `begin` émet `BEGIN IMMEDIATE` ; `transactional_ddl=True` et `transaction_per_migration=False` font de l'exécution une seule transaction ; `env.py` exécute `PRAGMA foreign_key_check` après `run_migrations()`, dans cette transaction, et une violation annule tout, révision comprise (mécanisme précisé aux deux revues de #70, testé par T-DB-13) ; une migration qui reconstruit `article` recrée les triggers de `article_fts` ; `app` et `worker` gardent `foreign_keys=ON` — appliquée dans III §10.2, §10.5 et dans ce document (§2.2, §5).

#### I-17 — Dates de référence des rétentions

- **III §13** : `AIJob` terminés « supprimés à 30 jours », `CollectorRun` « 30 jours », ligne `Article` `filtered`
  « supprimée à 30 jours », `AlertLog` « 1 an ».
- Les colonnes qui portent ces délais ne sont pas nommées : `created_at` ou `completed_at` pour `AIJob` ;
  `started_at` ou `finished_at` pour `CollectorRun` ; `discovered_at` ou `published_at` pour `Article` ; aucune
  colonne de date pour `AlertLog` (I-13).

Décision (2026-09-23) : départ des délais : `AIJob` → `completed_at` · `CollectorRun` → `finished_at` · article `filtered` → `discovered_at` · `AlertLog` → `created_at` — appliquée dans III §13 et dans ce document (§6).

#### I-18 — Déclenchement du trigger de mise à jour d'`article_fts`

- **III §11.14** : l'index est maintenu par des triggers « sur insertion, mise à jour et suppression d'`Article` ».
- **Ce document, §3.20** (T0.4, #68) : trigger `AFTER UPDATE ON article`. Constat de la revue de #68 : toute mise à
  jour d'un article (`event_id`, `status`, `clustered_at`, `processed_at`, purge du contenu…) réécrirait son entrée
  dans l'index, alors que seules `title` et `summary` sont indexées.

Décision (2026-09-23) : le trigger de mise à jour ne se déclenche que sur `UPDATE OF title, summary` — appliquée dans
III §11.14 et dans ce document (§3.20).
