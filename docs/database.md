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
| `key` | `TEXT` | `String` | n. p. | — | **UNIQUE** | identifiant stable de `sources.yaml`, slug `[a-z0-9-]+`, clé d'upsert, immuable | III §11.1 · IV §16.2 | 2 |
| `name` | `TEXT` | `String` | n. p. | — | | libellé affiché | III §11.1 | 2 |
| `type` | `TEXT` | `String` | n. p. | — | validé par le code (registre des collectors) | V1 : `rss · github · hackernews · reddit · youtube · webpage` ; ne change jamais pour une `key` | III §11.1, décision 7 · IV §16.2 | 2 |
| `url` | `TEXT` | `String` | n. p. | — | | URL lisible de la source (page de liste pour `webpage`) | III §11.1 · IV §16.2 | 2 |
| `config` | `TEXT` (JSON) | `JSON` | n. p. | — | Pydantic : `config_model` du collector | paramètres propres au collector | III §11.1 · IV §16.2 | 2 |
| `enabled` | `INTEGER` | `Boolean` | n. p. | — | | source planifiée ou non | III §11.1 | 2 |
| `poll_interval` | `INTEGER` | `Integer` | n. p. | — | | intervalle en secondes, ≥ minimum du type | III §11.1 · IV §16.2 | 2 |
| `relevance` | `TEXT` | `String` | n. p. | — | `CHECK IN ('filter','always')` | `always` : article toujours `ready` | III §11.1 · IV §20.3 | 2 |
| `extract` | `TEXT` | `String` | n. p. | — | `CHECK IN ('auto','never')` | extraction ciblée autorisée ou non | III §11.1 · IV §17.1 | 2 |
| `checkpoint` | `TEXT` (JSON) | `JSON` | n. p. | — | Pydantic | curseur, `ETag`, `Last-Modified`, date de dernière collecte ; vide à l'insertion ; jamais écrasé par le YAML | III §11.1 · IV §14.3, §16.1 | 2 |
| `last_success_at` | `TEXT` | `UTCDateTime` | n. p. | — | | fin du dernier run `success` ou `partial` | III §11.1 · IV §14.4 | 2 |
| `last_error` | `TEXT` | `Text` | n. p. | — | | dernier run `partial` ou `failed`, après nettoyage des secrets par valeur | III §11.1 · IV §14.4 · VII §42.4 | 2 |
| `last_http_status` | `INTEGER` | `Integer` | n. p. | — | | état de santé | III §11.1 | 2 |
| `rate_limit_remaining` | `INTEGER` | `Integer` | oui | — | | `NULL` = quota inconnu | III §11.1 · IV §21.4 | 2 |
| `rate_limit_reset_at` | `TEXT` | `UTCDateTime` | oui | — | | `NULL` = inconnu | III §11.1 · IV §21.3 | 2 |

- Champs de configuration (mis à jour par l'upsert) : `name`, `url`, `config`, `enabled`, `poll_interval`,
  `relevance`, `extract`. Champs d'état (jamais touchés par le YAML) : `checkpoint`, `last_*`, `rate_limit_*`
  (IV §16.1, §16.2).
- Aucun état de disjoncteur en colonne : il se lit dans `CollectorRun` (IV §21.5).

```sql
CREATE TABLE source (
  id                   INTEGER PRIMARY KEY,
  key                  TEXT UNIQUE,
  name                 TEXT,
  type                 TEXT,
  url                  TEXT,
  config               TEXT,          -- JSON
  enabled              INTEGER,
  poll_interval        INTEGER,       -- secondes
  relevance            TEXT CHECK (relevance IN ('filter','always')),
  extract              TEXT CHECK (extract IN ('auto','never')),
  checkpoint           TEXT,          -- JSON
  last_success_at      TEXT,
  last_error           TEXT,
  last_http_status     INTEGER,
  rate_limit_remaining INTEGER,
  rate_limit_reset_at  TEXT
);
```

### 3.3 `Article` — *écrit par le worker*

Insertion par le runner, une transaction `BEGIN IMMEDIATE` par page (IV §14.3). Un doublon exact n'est **pas**
inséré ; un item malformé non plus (III décision 6).

| Colonne | SQLite | SQLAlchemy | Null | Défaut | Contrainte | Rôle | Réf. | Sprint |
|---|---|---|---|---|---|---|---|---|
| `id` | `INTEGER` | `Integer` | non | — | PK | | III §11.0 | 2 |
| `source_id` | `INTEGER` | `Integer` | n. p. | — | FK `source(id)` `RESTRICT` | | III §11.2 | 2 |
| `external_id` | `TEXT` | `String` | oui | — | voir unicité partielle | identifiant chez le provider | III §11.2 | 2 |
| `url` | `TEXT` | `String` | n. p. | — | | URL **propre à l'item** | III §11.2, décision 3 | 2 |
| `canonical_url` | `TEXT` | `String` | n. p. | — | **UNIQUE** | base de la dédup exacte | III §11.2 · IV §18.3, §19.1 | 2 |
| `link_url` | `TEXT` | `String` | oui | — | | URL **pointée** (lien externe) | III §11.2 | 2 |
| `canonical_link_url` | `TEXT` | `String` | oui | — | index | critère « URL croisée » du clustering | III §11.2 · V-B §28.4 | 2 |
| `title` | `TEXT` | `Text` | n. p. | — | | titre normalisé, une ligne, ≤ 500 caractères | III §11.2 · IV §18.2 | 2 |
| `author` | `TEXT` | `String` | oui | — | | auteur vide → `NULL` | III §11.2 · IV §18.2 | 2 |
| `language` | `TEXT` | `String` | oui | — | | `NULL` sous 20 caractères ou si le détecteur ne tranche pas | III §11.2 · IV §18.5 | 2 |
| `published_at` | `TEXT` | `UTCDateTime` | **non** | — | index | absent ou futur → repli sur `discovered_at` | III §11.2 · IV §18.4 | 2 |
| `discovered_at` | `TEXT` | `UTCDateTime` | **non** | — | | instant UTC du traitement de la page | III §11.2 · IV §14.2 | 2 |
| `content` | `TEXT` | `Text` | oui | — | | **tampon de traitement**, purgé ; `NULL` dès l'insertion pour un `filtered` | III §11.2 · IV §14.3 · II §8.5 | 2 |
| `content_hash` | `TEXT` | `String` | oui | — | index (non unique) | `NULL` sous 200 caractères ; conservé après purge ; jamais recalculé après extraction | III §11.2 · IV §19.2 | 2 |
| `content_purged_at` | `TEXT` | `UTCDateTime` | oui | — | | posé à l'insertion d'un `filtered`, puis par la purge | III §11.2 · IV §14.3 | 2 |
| `relevance_score` | `REAL` | `Float` | n. p. | — | | score du relevance filter | III §11.2 · IV §20 | 2 |
| `status` | `TEXT` | `String` | n. p. | — | `CHECK IN ('ready','filtered','duplicate')` ; index | insertion en `ready` ou `filtered` ; seule transition : `ready → duplicate` | III §11.2 | 2 |
| `summary` | `TEXT` | `Text` | **non** (E12) | — | | aperçu : repli à l'insertion (`ready` **et** `filtered`), puis synthèse LLM | III §11.2 · IV §14.5 | 2 |
| `summary_origin` | `TEXT` | `String` | n. p. | — | `CHECK IN ('fallback','llm')` | | III §11.2 | 2 |
| `summary_lang` | `TEXT` | `String` | oui | — | | langue du résumé ; au repli, `language` (éventuellement `NULL`) | III §11.2 · IV §14.5 | 2 |
| `metrics` | `TEXT` (JSON) | `JSON` | n. p. | — | Pydantic | engagement à la collecte (points HN, vues YouTube…), instantané jamais mis à jour | III §11.2 · IV §15.4 | 2 |
| `event_id` | `INTEGER` | `Integer` | oui | — | FK `event(id)` `RESTRICT` ; index | appartenance à un Event | III §11.2, décision 4 · V-B §28.5 | **4** |
| `duplicate_of_id` | `INTEGER` | `Integer` | oui | — | FK `article(id)` `RESTRICT` | renseigné si `duplicate` | III §11.2 · V-B §28.7 | **4** |
| `clustered_at` | `TEXT` | `UTCDateTime` | oui | — | index partiel | article évalué par le clustering | III §11.2 · V-B §28.2 | **4** |
| `clustered_semantic` | `INTEGER` | `Boolean` | n. p. | `false` | | critère cosine évalué | III §11.2 · V-B §28.2 | **4** |
| `importance` | `REAL` | `Float` | oui | — | | importance de l'article hors Event, dans [0, 1] | III §11.2 · V-B §28.9 | **4** |
| `processed_at` | `TEXT` | `UTCDateTime` | oui | — | | tous traitements terminés ; posé par la seule passe `processed_at` de la purge | III §11.2 · V-A §24.5 | **7** |

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
  source_id          INTEGER REFERENCES source(id) ON DELETE RESTRICT,
  external_id        TEXT,
  url                TEXT,
  canonical_url      TEXT UNIQUE,
  link_url           TEXT,
  canonical_link_url TEXT,
  title              TEXT,
  author             TEXT,
  language           TEXT,
  published_at       TEXT NOT NULL,
  discovered_at      TEXT NOT NULL,
  content            TEXT,
  content_hash       TEXT,
  content_purged_at  TEXT,
  relevance_score    REAL,
  status             TEXT CHECK (status IN ('ready','filtered','duplicate')),
  summary            TEXT NOT NULL,
  summary_origin     TEXT CHECK (summary_origin IN ('fallback','llm')),
  summary_lang       TEXT,
  metrics            TEXT,                                            -- JSON
  -- Sprint 4
  event_id           INTEGER REFERENCES event(id) ON DELETE RESTRICT,
  duplicate_of_id    INTEGER REFERENCES article(id) ON DELETE RESTRICT,
  clustered_at       TEXT,
  clustered_semantic INTEGER DEFAULT 0,
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
| `source_id` | `INTEGER` | `Integer` | n. p. | — | FK `source(id)` `RESTRICT` | | III §11.11 | 2 |
| `started_at` · `finished_at` | `TEXT` | `UTCDateTime` | n. p. | — | | bornes du run | III §11.11 | 2 |
| `status` | `TEXT` | `String` | n. p. | — | `CHECK IN ('success','partial','failed')` | | III §11.11 · IV §14.4 | 2 |
| `items_fetched` | `INTEGER` | `Integer` | n. p. | — | | entrées renvoyées par le provider, malformées comprises | III §11.11 · IV §14.4 | 2 |
| `items_created` | `INTEGER` | `Integer` | n. p. | — | | insérés en `ready` | idem | 2 |
| `items_duplicate` | `INTEGER` | `Integer` | n. p. | — | | doublons exacts non insérés, conflits `ON CONFLICT` compris | idem | 2 |
| `items_filtered` | `INTEGER` | `Integer` | n. p. | — | | insérés en `filtered` | idem | 2 |
| `items_skipped` | `INTEGER` | `Integer` | n. p. | — | | entrées malformées, non persistées | idem | 2 |
| `items_too_old` | `INTEGER` | `Integer` | n. p. | — | | plus anciennes que `max_item_age` | idem | 2 |
| `extractions_attempted` · `extractions_failed` | `INTEGER` | `Integer` | n. p. | — | | extraction ciblée (IV §17) | idem | 2 |
| `requests_count` | `INTEGER` | `Integer` | n. p. | — | | requêtes HTTP du run, extraction comprise | idem | 2 |
| `http_status` | `INTEGER` | `Integer` | n. p. | — | | | III §11.11 | 2 |
| `error` | `TEXT` | `Text` | n. p. | — | | | III §11.11 | 2 |

- **Invariant testé** : `items_fetched = items_created + items_filtered + items_duplicate + items_skipped +
  items_too_old` (IV §14.4).
- Aucun index secondaire n'est spécifié (§7, I-07).

```sql
CREATE TABLE collector_run (
  id                    INTEGER PRIMARY KEY,
  source_id             INTEGER REFERENCES source(id) ON DELETE RESTRICT,
  started_at            TEXT,
  finished_at           TEXT,
  status                TEXT CHECK (status IN ('success','partial','failed')),
  items_fetched         INTEGER,
  items_created         INTEGER,
  items_duplicate       INTEGER,
  items_filtered        INTEGER,
  items_skipped         INTEGER,
  items_too_old         INTEGER,
  extractions_attempted INTEGER,
  extractions_failed    INTEGER,
  requests_count        INTEGER,
  http_status           INTEGER,
  error                 TEXT
);
```

### 3.5 `Topic` — *écrit par le worker*

Upserté depuis `topics.yaml` au démarrage (clé `slug`, `origin = seeded`) ; créé en `origin = user` par le worker
sur une décision `create_topic` de l'app (IV §16.3, V-B §30.8). `origin = discovered` n'est produit par aucun
mécanisme en V1 (V-A §24.6). Le suivi et la sourdine ne sont pas ici : ce sont des préférences (§3.15).

| Colonne | SQLite | SQLAlchemy | Null | Défaut | Contrainte | Rôle | Réf. | Sprint |
|---|---|---|---|---|---|---|---|---|
| `id` | `INTEGER` | `Integer` | non | — | PK | | III §11.0 | 2 |
| `slug` | `TEXT` | `String` | n. p. | — | **UNIQUE** | clé d'upsert ; suffixe `-2`, `-3`… en collision pour un topic `user` | III §11.4 · IV §16.3 · V-B §30.8 | 2 |
| `name` | `TEXT` | `String` | n. p. | — | | | III §11.4 | 2 |
| `description` | `TEXT` | `Text` | oui | — | | `null` par défaut dans le YAML ; `llm_description` ou `NULL` pour un topic `user` | III §11.4 · IV §16.3 · V-B §30.8 | 2 |
| `parent_id` | `INTEGER` | `Integer` | oui | — | FK `topic(id)` `RESTRICT` | hiérarchie ; `NULL` pour un topic `user` | III §11.4 · IV §16.3 · V-B §30.8 | 2 |
| `origin` | `TEXT` | `String` | n. p. | — | `CHECK IN ('seeded','discovered','user')` | | III §11.4 | 2 |
| `keywords` | `TEXT` (JSON) | `JSON` | n. p. | — | Pydantic | mots-clés et motifs du relevance filter | III §11.4 · IV §16.3 | 2 |
| `enabled` | `INTEGER` | `Boolean` | n. p. | — | | un topic désactivé n'est pas utilisé par le scoring et n'a plus de Signal | III §11.4 · IV §16.3 · V-B §29.7 | 2 |
| `created_at` | `TEXT` | `UTCDateTime` | n. p. | — | | couverture d'un topic `user` : `created_at − topic_backfill.window` | III §11.0 · V-B §29.3 | 2 |

- Les exclusions (`exclude`) de `topics.yaml` n'ont pas de colonne (§7, I-05).

```sql
CREATE TABLE topic (
  id          INTEGER PRIMARY KEY,
  slug        TEXT UNIQUE,
  name        TEXT,
  description TEXT,
  parent_id   INTEGER REFERENCES topic(id) ON DELETE RESTRICT,
  origin      TEXT CHECK (origin IN ('seeded','discovered','user')),
  keywords    TEXT,       -- JSON
  enabled     INTEGER,
  created_at  TEXT
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
| `type` | `TEXT` | `String` | n. p. | — | validé par le code | `company · product · person · project · technology · model · repository` | III §11.6 | 2 |
| `name` | `TEXT` | `String` | n. p. | — | | libellé affiché, mis à jour par l'upsert | III §11.6 · IV §16.4 | 2 |
| `canonical_name` | `TEXT` | `String` | n. p. | — | voir unicité | minuscules ; `owner/repo` pour un dépôt | III §11.6 · IV §16.4 | 2 |
| `origin` | `TEXT` | `String` | n. p. | — | `CHECK IN ('dictionary','llm')` | | III §11.6 | 2 |

**Unicité** : `UNIQUE(type, canonical_name)` (III §11.6), Sprint 2.

```sql
CREATE TABLE entity (
  id             INTEGER PRIMARY KEY,
  type           TEXT,
  name           TEXT,
  canonical_name TEXT,
  origin         TEXT CHECK (origin IN ('dictionary','llm')),
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
| `confidence` | `REAL` | `Float` | n. p. | — | | | III §11.5 | 2 |
| `created_at` | `TEXT` | `UTCDateTime` | n. p. | — | | | III §11.5 | 2 |

**Clé primaire** : `(article_id, topic_id, method)`. Les tendances comptent les **articles distincts** (III §11.5).

```sql
CREATE TABLE article_topic (
  article_id INTEGER REFERENCES article(id) ON DELETE CASCADE,
  topic_id   INTEGER REFERENCES topic(id)   ON DELETE RESTRICT,
  method     TEXT CHECK (method IN ('keyword','llm')),
  confidence REAL,
  created_at TEXT,
  PRIMARY KEY (article_id, topic_id, method)
);
```

### 3.8 `ArticleEntity` — *écrit par le worker*

| Colonne | SQLite | SQLAlchemy | Null | Défaut | Contrainte | Rôle | Réf. | Sprint |
|---|---|---|---|---|---|---|---|---|
| `article_id` | `INTEGER` | `Integer` | non (PK) | — | FK `article(id)` **`CASCADE`** | | III §11.7 · §11.0 | 2 |
| `entity_id` | `INTEGER` | `Integer` | non (PK) | — | FK `entity(id)` `RESTRICT` | | III §11.7 | 2 |
| `method` | `TEXT` | `String` | non (PK) | — | `CHECK IN ('keyword','llm')` | | III §11.7 | 2 |
| `confidence` | `REAL` | `Float` | n. p. | — | | | III §11.7 | 2 |

**Clé primaire** : `(article_id, entity_id, method)` (III §11.7). Pas de `created_at`, contrairement à
`ArticleTopic` (§7, I-06).

```sql
CREATE TABLE article_entity (
  article_id INTEGER REFERENCES article(id) ON DELETE CASCADE,
  entity_id  INTEGER REFERENCES entity(id)  ON DELETE RESTRICT,
  method     TEXT CHECK (method IN ('keyword','llm')),
  confidence REAL,
  PRIMARY KEY (article_id, entity_id, method)
);
```

### 3.9 `Event` — *écrit par le worker*

Créé sans LLM par le clustering, dès deux articles (V-B décision 7) ; titre de repli, puis enrichi par
`resolve_event` sans toucher à l'appartenance ni aux compteurs (II §7.3, V-A §27.3). **Compteurs recalculés depuis
les membres dans chaque transaction qui modifie l'Event, jamais incrémentés** (V-B décision 9, §28.9 ; CF-15).

| Colonne | SQLite | SQLAlchemy | Null | Défaut | Contrainte | Rôle | Réf. | Sprint |
|---|---|---|---|---|---|---|---|---|
| `id` | `INTEGER` | `Integer` | non | — | PK | | III §11.0 | 4 |
| `title` | `TEXT` | `Text` | **non** | — | | repli = titre du représentant ; synthèse LLM ensuite | III §11.3 · V-B §28.5, §28.8 | 4 |
| `title_origin` | `TEXT` | `String` | n. p. | — | `CHECK IN ('fallback','llm')` | ce que `resolve_event` doit encore enrichir | III §11.3 | 4 |
| `description` | `TEXT` | `Text` | oui | — | | produite par `resolve_event` ; `NULL` à la création | III §11.3 · V-B §28.5 | 4 |
| `representative_article_id` | `INTEGER` | `Integer` | n. p. | — | FK `article(id)` `RESTRICT` | membre `ready` le plus ancien par `published_at` | III §11.3 · V-B §28.8, décision 10 | 4 |
| `first_seen_at` · `last_seen_at` | `TEXT` | `UTCDateTime` | n. p. | — | | min · max de `published_at` des membres `ready` | III §11.3 · V-B §28.9 | 4 |
| `article_count` | `INTEGER` | `Integer` | n. p. | — | | membres `ready` | III §11.3 · V-B §28.9 | 4 |
| `distinct_source_count` | `INTEGER` | `Integer` | **non** | `1` | | `source_id` distincts des membres `ready` (**hotness**) | III §11.3 · V-B §28.9 | 4 |
| `distinct_channel_count` | `INTEGER` | `Integer` | **non** | `1` | | canaux distincts des membres `ready` | III §11.3, décision 16 · V-B §28.9 | 4 |
| `importance` | `REAL` | `Float` | **non** | `0` | | dans [0, 1], indépendante du temps | III §11.3 · V-B §28.9 | 4 |
| `resolve_enqueued_count` | `INTEGER` | `Integer` | oui | — | | `article_count` au dernier enqueue de `resolve_event` | III §11.3 · V-B §28.10 | 4 |
| `status` | `TEXT` | `String` | n. p. | — | `CHECK IN ('active','merged','archived')` | `archived` = inactif depuis 7 j, informatif | III §11.3 · V-B §28.11 | 4 |
| `merged_into_id` | `INTEGER` | `Integer` | oui | — | FK `event(id)` `RESTRICT` | renseigné si `merged` | III §11.3 · V-B §28.6 | 4 |

- **Invariant testé** : `article_count`, `distinct_source_count` et `distinct_channel_count` égalent leur recalcul
  depuis les membres `ready` ; contrôlable et corrigé par `python -m app.cli recount-events` (III §11.3, V-B §28.9).
- `novelty` n'existe pas sur `Event` : elle se calcule à la lecture depuis `first_seen_at` (III §11.3, V-B décision 13).
- Clés étrangères croisées : `article.event_id → event` et `event.representative_article_id → article`.

**Index** (III §11.3, stories VI) : `(status, last_seen_at)` · `(status, importance)`, Sprint 4.

```sql
CREATE TABLE event (
  id                        INTEGER PRIMARY KEY,
  title                     TEXT NOT NULL,
  title_origin              TEXT CHECK (title_origin IN ('fallback','llm')),
  description               TEXT,
  representative_article_id INTEGER REFERENCES article(id) ON DELETE RESTRICT,
  first_seen_at             TEXT,
  last_seen_at              TEXT,
  article_count             INTEGER,
  distinct_source_count     INTEGER NOT NULL DEFAULT 1,
  distinct_channel_count    INTEGER NOT NULL DEFAULT 1,
  importance                REAL    NOT NULL DEFAULT 0,
  resolve_enqueued_count    INTEGER,
  status                    TEXT CHECK (status IN ('active','merged','archived')),
  merged_into_id            INTEGER REFERENCES event(id) ON DELETE RESTRICT
);
CREATE INDEX ix_event_status_last_seen  ON event(status, last_seen_at);
CREATE INDEX ix_event_status_importance ON event(status, importance);
```

### 3.10 `Embedding` — *écrit par le worker*

Écrit par la file dérivée des embeddings, sans `AIJob` (V-A §24.4). Stockage du vecteur : §4.

| Colonne | SQLite | SQLAlchemy | Null | Défaut | Contrainte | Rôle | Réf. | Sprint |
|---|---|---|---|---|---|---|---|---|
| `id` | `INTEGER` | `Integer` | non | — | PK | | III §11.0 | 4 |
| `article_id` | `INTEGER` | `Integer` | n. p. | — | FK `article(id)` **`CASCADE`** | | III §11.9 · §11.0 | 4 |
| `model` | `TEXT` | `String` | n. p. | — | voir unicité | modèle qui a produit le vecteur | III §11.9 · §12.4 | 4 |
| `dim` | `INTEGER` | `Integer` | oui | — | | dimension du vecteur (384) | III §11.9 | 4 |
| `vector` | `BLOB` | `LargeBinary` | oui | — | | `float32` normalisé (§4) ; `NULL` = échec définitif | III §11.9 · §12.3 | 4 |
| `error` | `TEXT` | `Text` | oui | — | | renseigné quand `vector` est `NULL` | III §11.9 · V-A §24.4 | 4 |
| `created_at` | `TEXT` | `UTCDateTime` | n. p. | — | | | III §11.9 | 4 |

- **Unicité** : `UNIQUE(article_id, model)` (III §11.9), Sprint 4. Rejouer un embedding écrase la ligne (II §9.1).
- Une ligne à `vector` `NULL` (après `embeddings.max_failures` échecs) compte comme **traitée** pour `processed_at` et
  est **exclue** de la similarité et de la seconde passe cosine (III §11.9, V-A §24.4, V-B §28.2).

```sql
CREATE TABLE embedding (
  id         INTEGER PRIMARY KEY,
  article_id INTEGER REFERENCES article(id) ON DELETE CASCADE,
  model      TEXT,
  dim        INTEGER,
  vector     BLOB,       -- float32 normalisé, NULL = échec définitif
  error      TEXT,
  created_at TEXT,
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
| `job_type` | `TEXT` | `String` | n. p. | — | validé par le code (registre) | V1 : `enrich_article · resolve_event · discover_topics` ; inconnu → `failed` | III §11.10 · V-A §23.1, §23.2 | 2 |
| `entity_type` | `TEXT` | `String` | n. p. | — | validé par le code | `article · event · emerging_candidate` | III §11.10 | 2 |
| `entity_id` | `INTEGER` | `Integer` | n. p. | — | **sans FK** | cible du job | III §11.10 | 2 |
| `priority` | `INTEGER` | `Integer` | n. p. | — | | 60 / 50 / 10 selon le type ; 100 pour un job de l'app | III §11.10 · V-A §23.2 | 2 |
| `status` | `TEXT` | `String` | n. p. | — | `CHECK IN ('pending','processing','completed','failed','retry','dead_letter','cancelled','skipped')` | | III §11.10 | 2 |
| `skip_reason` | `TEXT` | `String` | oui | — | validé par le code | `expired · article_not_ready · event_member · event_not_active · event_single_source · candidate_decided` | III §11.10 · V-A §23.3 | 2 |
| `attempts` · `max_attempts` | `INTEGER` | `Integer` | n. p. | — | | `max_attempts = 3` | III §11.10 · V-A §23.5 | 2 |
| `next_attempt_at` | `TEXT` | `UTCDateTime` | **non** | « maintenant » (§7, I-04) | index de claim | à la création par le worker : maintenant + délai du type | III §11.10 · V-A §23.1 | 2 |
| `last_error` | `TEXT` | `Text` | n. p. | — | | sans secret | III §11.10 · VIII T-LLM-09 | 2 |
| `created_by` | `TEXT` | `String` | n. p. | — | `CHECK IN ('worker','app')` | | III §11.10 · V-A §23.6 | 2 |
| `started_at` · `completed_at` | `TEXT` | `UTCDateTime` | oui | — | | `completed_at` posé aussi pour `skipped` | III §11.10 · V-A §23.3 | 2 |
| `created_at` | `TEXT` | `UTCDateTime` | n. p. | — | | TTL (`now − created_at > ttl`) et ordre de claim | III §11.0 · V-A §23.3, §23.4 | 2 |

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
  dans une seule transaction (III §11.10) ; voir §7, I-08, pour l'exemple cité par III.

```sql
CREATE TABLE aijob (
  id              INTEGER PRIMARY KEY,
  job_type        TEXT,
  entity_type     TEXT,
  entity_id       INTEGER,            -- sans FK
  priority        INTEGER,
  status          TEXT CHECK (status IN ('pending','processing','completed','failed',
                                         'retry','dead_letter','cancelled','skipped')),
  skip_reason     TEXT,
  attempts        INTEGER,
  max_attempts    INTEGER,
  next_attempt_at TEXT NOT NULL,      -- défaut « maintenant » : voir I-04
  last_error      TEXT,
  created_by      TEXT CHECK (created_by IN ('worker','app')),
  started_at      TEXT,
  completed_at    TEXT,
  created_at      TEXT
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
| `topic_id` | `INTEGER` | `Integer` | n. p. | — | FK `topic(id)` `RESTRICT` | | III §11.8 | 8 |
| `period` | `TEXT` | `String` | n. p. | — | `CHECK IN ('24h','7d','30d')` | | III §11.8 | 8 |
| `computed_at` | `TEXT` | `UTCDateTime` | n. p. | — | | | III §11.8 | 8 |
| `window_start` · `window_end` | `TEXT` | `UTCDateTime` | n. p. | — | | fenêtre du calcul | III §11.8 · V-B §29.4 | 8 |
| `mentions` | `INTEGER` | `Integer` | n. p. | — | | articles distincts | III §11.8 · V-B §29.2 | 8 |
| `unique_sources` · `unique_authors` · `unique_companies` | `INTEGER` | `Integer` | n. p. | — | | | III §11.8 · V-B §29.2 | 8 |
| `growth_rate` | `REAL` | `Float` | oui | — | | `NULL` en cold start | III §11.8 · V-B §29.5, décision 17 | 8 |
| `velocity` | `REAL` | `Float` | n. p. | — | | | III §11.8 · V-B §29.5 | 8 |
| `novelty` · `momentum` | `REAL` | `Float` | oui | — | | `NULL` en cold start | III §11.8 · V-B §29.5, décision 17 | 8 |
| `category` | `TEXT` | `String` | **oui** | — | `CHECK IN ('established','trending','rising','declining')` | `NULL` = support insuffisant | III §11.8 · V-B §29.6 | 8 |

**Contraintes et index** (Sprint 8) : `UNIQUE(topic_id, period, window_end)` (upsert horaire) · index
`(topic_id, period, computed_at)` (III §11.8, V-B §29.4).

```sql
CREATE TABLE signal (
  id               INTEGER PRIMARY KEY,
  topic_id         INTEGER REFERENCES topic(id) ON DELETE RESTRICT,
  period           TEXT CHECK (period IN ('24h','7d','30d')),
  computed_at      TEXT,
  window_start     TEXT,
  window_end       TEXT,
  mentions         INTEGER,
  unique_sources   INTEGER,
  unique_authors   INTEGER,
  unique_companies INTEGER,
  growth_rate      REAL,
  velocity         REAL,
  novelty          REAL,
  momentum         REAL,
  category         TEXT CHECK (category IN ('established','trending','rising','declining')),
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
| `key` | `TEXT` | `String` | n. p. | — | **UNIQUE** | terme normalisé | III §11.13 | 8 |
| `kind` | `TEXT` | `String` | n. p. | — | `CHECK IN ('ngram','repository')` | | III §11.13 · V-B §30.2 | 8 |
| `label` | `TEXT` | `String` | n. p. | — | | | III §11.13 | 8 |
| `first_detected_at` | `TEXT` | `UTCDateTime` | n. p. | — | | | III §11.13 | 8 |
| `last_evidence_at` | `TEXT` | `UTCDateTime` | n. p. | — | | dernière mise à jour de `evidence` | III §11.13 · V-B §30.4 | 8 |
| `evidence` | `TEXT` (JSON) | `JSON` | n. p. | — | Pydantic | `mentions_7d · mentions_prev7d · growth · sources · authors · channels · stories · first_seen_at · article_ids` (≤ 20) | III §11.13 · V-B §30.4 | 8 |
| `ref_mentions` · `ref_channel_count` | `INTEGER` | `Integer` | n. p. | — | | référence de l'évolution significative | III §11.13 · V-B §30.5 | 8 |
| `last_significant_at` | `TEXT` | `UTCDateTime` | n. p. | — | | dernière évolution significative | III §11.13 · V-B §30.5 | 8 |
| `resurfaced_at` | `TEXT` | `UTCDateTime` | oui | — | | réapparition d'un candidat ignoré | III §11.13 · V-B §30.7 | 8 |
| `backfilled_at` | `TEXT` | `UTCDateTime` | **oui** | — | | fin du backfill d'un topic créé ; `NULL` avec `topic_id` renseigné = backfill à reprendre | III §11.13 · V-B §30.8 | 8 |
| `topic_id` | `INTEGER` | `Integer` | **oui** | — | FK `topic(id)` `RESTRICT` | topic créé sur `create_topic` | III §11.13 · V-B §30.8 | 8 |
| `llm_label` · `llm_description` | `TEXT` | `Text` | oui | — | | résultat de `discover_topics` | III §11.13 · V-A §27 | 8 |
| `covered_by_topic_id` | `INTEGER` | `Integer` | **oui** | — | FK `topic(id)` `RESTRICT` | suggestion, jamais d'écartement automatique | III §11.13 · V-A §27 | 8 |
| `suggested_keywords` | `TEXT` (JSON) | `JSON` | n. p. | — | Pydantic | mots-clés suggérés pour « Create topic » | III §11.13 · V-B §30.8 | 8 |
| `assessed_at` | `TEXT` | `UTCDateTime` | n. p. | — | | dernier `discover_topics` | III §11.13 | 8 |

**Unicité** : `UNIQUE(key)` (III §11.13), Sprint 8.

```sql
CREATE TABLE emerging_candidate (
  id                  INTEGER PRIMARY KEY,
  key                 TEXT UNIQUE,
  kind                TEXT CHECK (kind IN ('ngram','repository')),
  label               TEXT,
  first_detected_at   TEXT,
  last_evidence_at    TEXT,
  evidence            TEXT,      -- JSON
  ref_mentions        INTEGER,
  ref_channel_count   INTEGER,
  last_significant_at TEXT,
  resurfaced_at       TEXT,
  backfilled_at       TEXT,
  topic_id            INTEGER REFERENCES topic(id) ON DELETE RESTRICT,
  llm_label           TEXT,
  llm_description     TEXT,
  covered_by_topic_id INTEGER REFERENCES topic(id) ON DELETE RESTRICT,
  suggested_keywords  TEXT,      -- JSON
  assessed_at         TEXT
);
```

<!-- TABLES -->

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

<!-- SECTIONS -->

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

#### I-05 — Exclusions des topics sans colonne

- **IV §16.3** : chaque topic de `topics.yaml` porte une liste `exclude` (termes masqués avant matching, §20.3).
- **III §11.4** : colonnes de `Topic` = `slug · name · description · parent_id · origin · keywords · enabled` ;
  `keywords` est décrit comme « mots-clés et motifs utilisés par le relevance filter ». Non fixé : si `exclude` est
  stocké dans `keywords`, dans une autre colonne, ou seulement en mémoire.

#### I-06 — `created_at` sur `ArticleTopic` mais pas sur `ArticleEntity`

- **III §11.5** : `ArticleTopic` = `article_id · topic_id · method · confidence · created_at`.
- **III §11.7** : `ArticleEntity` = `article_id · entity_id · method · confidence`, sans `created_at`.

#### I-07 — Index de lecture non spécifiés

- **IV §21.5** : le disjoncteur par source lit les runs `failed` consécutifs les plus récents dans `CollectorRun` ;
  **III §13** : `CollectorRun` supprimé à 30 jours. **III §11.11** ne spécifie aucun index sur `CollectorRun`.
- **V-B §29** (Trend Engine) et **VI §31.6** (vue Topic) lisent les liaisons par topic ; **V-B §28.4** compte les
  entités communes. **III §11.5, §11.7** ne donnent que la clé primaire `(article_id, …)`, sans index sur `topic_id`
  ni `entity_id`.
- La spec ne dit pas si ces index sont voulus ou laissés à l'implémenteur (VII « Points d'interprétation » ne les
  cite pas).

#### I-08 — Exemple d'idempotence avec un `job_type` supprimé

- **III §11.10** : « par exemple `extract_topics` supprime puis réécrit les lignes `method=llm` de l'article ».
- **V-A §23.2** et **V-A décision 3** : catalogue V1 réduit à `enrich_article · resolve_event · discover_topics` ;
  `extract_topics` est fusionné dans `enrich_article`.

#### I-09 — Création d'`AIJob` par l'app pour le rattachement de l'historique

- **II §8.3** (« Deux conséquences ») : l'app insère des jobs « en réponse à une action utilisateur — régénérer un
  résumé, **rattacher l'historique à un topic créé**, relancer un `dead_letter` ».
- **V-A décision 18, §24.6** et **V-B §30.8** : le rattachement de l'historique est un traitement **déterministe,
  hors `AIJob`**, déclenché par la lecture des `EmergingDecision` ; les jobs créables par l'app sont
  `enrich_article` et `resolve_event` (régénération). **V-A §23.6** : la relance d'un `dead_letter` est un `UPDATE`,
  pas une création.

#### I-10 — Représentant d'un Event

- **III §11.3** : `representative_article_id` = « article le plus ancien du groupe » (sans critère de date ni de
  statut) ; **II §7.2** : titre de repli = « titre de l'article le plus ancien du groupe ».
- **V-B décision 10, §28.8** : représentant = **membre `ready` le plus ancien par `published_at`**.

#### I-11 — Valeur de `Embedding.model`

- **III §11.9, §12.4** : colonne `model`, et comparaison « que des vecteurs produits par le même modèle ».
- **III §12.1** : révision et empreinte du modèle épinglées au build (ADR-0008). La spec ne dit pas ce que contient
  `model` (nom fastembed, dépôt Hugging Face réellement téléchargé, révision), alors que T0.3 a constaté que le nom
  fastembed (`sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`) et le dépôt téléchargé
  (`qdrant/paraphrase-multilingual-MiniLM-L12-v2-onnx-Q`) diffèrent (rapport de cadrage §3, V-01).

<!-- INCOHERENCES -->
