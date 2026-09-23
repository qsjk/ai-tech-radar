# Partie III — Données

> **Partie III — Données.** Version durcie issue de la revue §10–§13.
> Dernière révision : 2026-09-23. Prend les Parties I et II durcies comme acquis.

---

## Décisions tranchées dans cette revue (Partie III)

1. **Topics et entités à double origine.** Un rattachement article↔topic ou article↔entité est produit soit **de façon déterministe** (mots-clés de `config/topics.yaml`, dictionnaire `config/entities.yaml`), soit par le **LLM**. Champ `method` ∈ `{keyword, llm}` sur les tables de liaison. Garantit que **les tendances et le clustering par entités fonctionnent sans LLM**, et corrige une incohérence de la Partie II.
2. **Nouveau fichier `config/entities.yaml`** : dictionnaire d'entités connues + motifs simples (dépôts GitHub `owner/repo`, noms de modèles).
3. **Deux URLs par article** : l'URL **propre à l'item** (page de discussion HN, post Reddit…) sert à la dédup exacte ; l'URL **pointée** (lien externe) sert de critère « URL croisée » au clustering. Évite qu'un post HN soit écrasé comme doublon de l'article qu'il commente — et qu'on perde une source distincte.
4. **`Article.event_id`** matérialise enfin la relation Article → Event (absente en V0.3).
5. **Le résumé a sa colonne** : `Article.summary` + `summary_origin` ∈ `{fallback, llm}`. Il est initialisé au repli déterministe **dès l'insertion** : un article `ready` n'a jamais de résumé vide.
6. **Statuts d'article réduits à `{ready, filtered, duplicate}`.** `discovered` / `normalized` étaient des étapes en mémoire, jamais persistées. Un **doublon exact n'est pas inséré** (il est seulement compté) ; `duplicate` ne désigne que le doublon **sémantique rétroactif**. Un item malformé n'est pas persisté non plus.
7. **`Source.type` en texte libre**, validé par le registre des collectors côté code — pas de contrainte en base. Ajouter un canal ne touche pas au schéma (Partie I §2.4). Valeurs V1 : `rss · github · hackernews · reddit · youtube · webpage`.
8. **Accès base asynchrone** dans les deux processus : SQLAlchemy 2.x async + `aiosqlite`.
9. **Toute transaction d'écriture démarre en `BEGIN IMMEDIATE`** (deux fabriques de sessions : lecture / écriture).
10. **SQLite ≥ 3.35 et FTS5 obligatoires**, vérifiés au démarrage des deux processus (arrêt immédiat avec message clair sinon).
11. **État « lu » au niveau de l'Event** (ou de l'article s'il n'appartient à aucun Event).
12. **Modèle d'embedding multilingue** (sources EN + FR), 384 dimensions, vecteurs normalisés.
13. **Tables ajoutées** : `CollectorRun` · `Setting` · `UserPreference` · `ReadState` · `EmergingCandidate` · `EmergingDecision` · `AlertLog` · `SystemState` · index `article_fts`.
14. **Rétention** : jobs terminés purgés à 30 j (sauf `dead_letter`) · embeddings conservés indéfiniment · articles `filtered` supprimés à 30 j · contenu des `filtered` / `duplicate` purgé immédiatement.
15. Service Docker **one-shot `migrate`** qui applique les migrations avant le démarrage de `app` et `worker` — évite que deux processus migrent en même temps. Chaque processus refuse de démarrer si le schéma n'est pas à jour.
16. `Event.distinct_channel_count` (nombre de **types** de canaux distincts) en plus de `distinct_source_count` : alimente l'indicateur « écosystèmes » des sujets émergents.
17. Statut `AIJob` **`cancelled`** : un `dead_letter` peut être abandonné depuis le dashboard, ce qui débloque la purge de l'article (règle Partie II §8.5).
18. `AlertLog.dedup_key` unique : garantit qu'une même alerte n'est jamais envoyée deux fois.
19. `Signal` : historique horaire conservé 30 jours, puis **une valeur par jour** et par topic/fenêtre.

---

## 10. SQLite

SQLite est la base de données V1 (décision verrouillée §53).

### 10.1 Prérequis vérifiés au démarrage

Chaque processus (`app`, `worker`) vérifie au démarrage, et **refuse de démarrer** avec un message explicite si l'un manque :

- **SQLite ≥ 3.35** (requis par le `RETURNING` du claim de jobs, §23) ;
- **FTS5** compilé (recherche plein texte, fonction 13) ;
- **JSON1** (colonnes JSON) ;
- **schéma à jour** : la révision Alembic en base est égale à la révision `head` du code.

### 10.2 Configuration de chaque connexion

Appliquée par un listener SQLAlchemy sur l'événement `connect`, pour **toute nouvelle connexion** :

```sql
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
PRAGMA busy_timeout=5000;   -- ms, configurable
PRAGMA foreign_keys=ON;
PRAGMA journal_size_limit=67108864;  -- 64 Mo, valeur initiale
```

**Conséquence assumée de `synchronous=NORMAL` en WAL** : en cas de coupure électrique, les toutes dernières transactions validées peuvent être perdues ; la base n'est **jamais corrompue**. Acceptable pour ce produit.

L'auto-checkpoint WAL reste à sa valeur par défaut ; la taille du fichier `-wal` est surveillée (Partie II §8.6). `journal_size_limit` fait tronquer le `-wal` après checkpoint : sa taille reste ainsi une métrique lisible.

**Seule exception : la connexion du service `migrate`** fonctionne avec `PRAGMA foreign_keys=OFF` pendant les migrations, posé par l'écouteur `connect` de son propre moteur (§10.5). Les connexions de `app` et `worker` gardent toujours `foreign_keys=ON`.

### 10.3 Accès et transactions

- **Pilote** : SQLAlchemy 2.x en mode async avec `aiosqlite`, dans les **deux** processus.
- **Un moteur par processus**, avec son propre pool. Aucune connexion partagée entre processus ou threads.
- **Deux fabriques de sessions** :
  - `read_session` — transaction différée (défaut), lecture seule ;
  - `write_session` — transaction ouverte en **`BEGIN IMMEDIATE`**.

> **Pourquoi `BEGIN IMMEDIATE`** : par défaut, une transaction démarre en lecture et ne demande le verrou d'écriture qu'au premier `INSERT`/`UPDATE`. Si l'autre processus a écrit entre-temps, SQLite échoue **immédiatement**, sans attendre `busy_timeout`. Ouvrir d'emblée en écriture fait attendre proprement dans la limite du timeout. C'est le piège principal d'une base partagée par deux processus.

La mise en œuvre suit la technique documentée par SQLAlchemy (désactivation du `BEGIN` implicite du pilote, `BEGIN` émis via le listener `begin`).

### 10.4 Emplacement du fichier

- Le fichier SQLite vit sur un **volume Docker local**, monté par `app` et `worker`, **sur le même hôte** (le mode WAL repose sur une mémoire partagée, fichier `-shm`).
- **Interdit** : tout système de fichiers réseau (NFS, SMB, volume distant).
- `/data` est **toujours un volume nommé**, jamais un bind mount, en développement comme en production, quel que soit l'OS de développement.

### 10.5 Migrations

- Alembic avec **`render_as_batch=True`** (SQLite ne sait pas modifier une contrainte par `ALTER`).
- Les migrations sont appliquées par un **service one-shot `migrate`** (`alembic upgrade head`) ; `app` et `worker` démarrent après sa réussite (`depends_on` + `service_completed_successfully`). Aucun des deux processus applicatifs ne migre lui-même.
- **Moteur de `migrate`** : l'environnement Alembic (`env.py`) crée un moteur **synchrone** propre à `migrate`, sur l'URL de la base lue dans la configuration (aucun chemin en dur). Il reprend la technique de §10.3 : son écouteur `connect` pose `isolation_level = None` sur la connexion DBAPI (pysqlite n'ouvre plus de transaction implicite) puis exécute les PRAGMA de §10.2, **hors transaction** ; son écouteur `begin` émet `BEGIN IMMEDIATE`. Seul `foreign_keys` diffère.
- **Clés étrangères pendant les migrations** : ce PRAGMA est posé à `OFF` dans l'écouteur `connect`, sur la connexion DBAPI (curseur brut), donc avant toute transaction : à l'intérieur d'une transaction, SQLite l'ignore. Sans ce PRAGMA, la reconstruction d'une table par le mode batch (copie, `DROP TABLE` de l'ancienne, renommage) exécuterait un `DELETE` implicite qui déclencherait les `ON DELETE CASCADE` des tables filles, ou échouerait sur les `RESTRICT`.
- **Une seule transaction par exécution** : `context.configure(..., render_as_batch=True, transactional_ddl=True)`, avec `transaction_per_migration=False`. Alembic déclare SQLite sans DDL transactionnel : sans `transactional_ddl=True`, `context.begin_transaction()` ne fait rien et chaque migration est validée séparément. Et pysqlite, dans son mode par défaut, n'émet pas de `BEGIN` avant une instruction DDL, qui serait validée aussitôt : `isolation_level = None` et l'écouteur `begin` placent tout le DDL de l'exécution dans une seule transaction explicite.
- **Contrôle d'intégrité** : `env.py` exécute `PRAGMA foreign_key_check` après `context.run_migrations()`, **dans la même transaction, avant le commit** ; une violation lève une exception, et la transaction est annulée en entier : la révision Alembic et le schéma restent ceux d'avant l'exécution.
- **Index plein texte** : une migration qui reconstruit `Article` **recrée les triggers de `article_fts`** (§11.14), supprimés avec l'ancienne table.

### 10.6 Dates et heures

- **Tout en UTC** en base, stocké en texte ISO-8601.
- Un type SQLAlchemy dédié (`UTCDateTime`) **refuse les datetimes sans fuseau** à l'écriture et renvoie des datetimes UTC à la lecture. Conversion en heure locale **uniquement à l'affichage**.
- **Aucune expression temporelle SQL** (`CURRENT_TIMESTAMP`, `datetime('now')`) dans le code ni dans les requêtes : l'instant est toujours fourni par l'application, via la `Clock` (Partie VIII décision 7). Aucune colonne n'a de défaut temporel en SQL : `AIJob.next_attempt_at` est fourni par l'application (§11.10).

### 10.7 Transactions courtes

Rappel des contraintes de la Partie II §8.6 : transactions d'écriture découpées en lots bornés côté worker ; aucune écriture longue côté app ; lectures paginées. Échec après `busy_timeout` = retry borné + métrique dédiée. En cas de verrous persistants : **instrumenter avant de changer d'architecture**.

## 11. Modèle de données

### 11.0 Conventions

- **Nommage SQL** : tables en `snake_case` (`article`, `article_topic`, `emerging_candidate`…). Exception : `aijob`, gardé tel qu'il figure dans les requêtes de la Partie V-A.
- **Clé primaire** : `id INTEGER PRIMARY KEY` partout (sauf tables de liaison et clé/valeur).
- **Horodatage** — type `UTCDateTime` (§10.6) :
  - `created_at` sur **toutes les tables à identifiant `id`**, ainsi que sur les tables de liaison `ArticleTopic` et `ArticleEntity` ;
  - `updated_at` sur les tables dont les lignes sont **modifiées après insertion** : `Source` · `Article` · `Topic` · `Entity` · `Event` · `Embedding` (rejeu, Partie II §9.1) · `AIJob` · `Signal` (upsert horaire) · `EmergingCandidate` · `EmergingDecision` (upsert) · `UserPreference` (upsert) · `ReadState` · `AlertLog` (T2 de la séquence d'envoi) · `Setting` · `SystemState` ;
  - pas de `updated_at` sur `CollectorRun` (écrit une fois, en fin de run), `ArticleTopic` et `ArticleEntity` (remplacées par suppression puis insertion).
- **Nullabilité** : **non nul par défaut**. Une colonne n'est nullable que si la spec le dit ou si `NULL` a un sens (valeur inconnue ou absente). `docs/database.md` donne la nullabilité de chaque colonne et justifie chaque colonne nullable.
- **JSON** : colonnes texte JSON, **validées par un schéma Pydantic** à l'écriture.
- **Deux sortes d'énumérations** :
  - les **machines à états** (`status`, `*_origin`, `method`) sont fermées → contrainte `CHECK` en base ;
  - les **catégories extensibles** (`Source.type`, `Entity.type`, `AIJob.job_type`) sont **validées par le code**, sans `CHECK` — les étendre ne demande pas de migration.
- **Suppressions** : `ON DELETE RESTRICT` par défaut. Seules exceptions : les tables de liaison et `Embedding` suivent la suppression de leur article (`CASCADE`). Aucune donnée métier n'est supprimée hors des règles de rétention (§13).
- **`NULL` = inconnu.** Jamais de valeur inventée par défaut (ex. un quota inconnu est `NULL`, pas `0`).
- **Propriétaire en écriture** : chaque table a un seul processus écrivain (Partie II §8.3) — indiqué ci-dessous.

### 11.1 Source — *écrit par le worker*

| Colonne | Type / contrainte | Rôle |
|---|---|---|
| `key` | texte, **UNIQUE** | identifiant stable défini dans `sources.yaml`, clé de l'upsert au démarrage |
| `name` | texte | libellé affiché |
| `type` | texte (validé par le code) | V1 : `rss · github · hackernews · reddit · youtube · webpage` |
| `url` | texte | endpoint ou flux |
| `config` | JSON | paramètres propres au collector (subreddit, dépôt, requête…) |
| `enabled` | booléen | |
| `poll_interval` | entier (secondes) | |
| `relevance` | `CHECK {filter, always}` | `always` : source de confiance, article toujours `ready` (Partie IV §20.3) |
| `extract` | `CHECK {auto, never}` | extraction ciblée autorisée ou non (Partie IV §17.1) |
| `checkpoint` | JSON | reprise de collecte : curseur, `ETag`, `Last-Modified`, date de dernière collecte |
| `last_success_at` · `last_error` · `last_http_status` | | état de santé |
| `rate_limit_remaining` · `rate_limit_reset_at` | nullable | `NULL` = quota inconnu |

### 11.2 Article — *écrit par le worker*

| Colonne | Type / contrainte | Rôle |
|---|---|---|
| `source_id` | FK `Source` | |
| `external_id` | texte, nullable | identifiant chez le provider |
| `url` · `canonical_url` | texte ; `canonical_url` **UNIQUE** | URL **propre à l'item** — base de la dédup exacte |
| `link_url` · `canonical_link_url` | texte, nullable ; index | URL **pointée** (lien externe) — critère « URL croisée » du clustering |
| `title` · `author` · `language` | | |
| `published_at` · `discovered_at` | `UTCDateTime`, **non nuls** ; index sur `published_at` | `published_at` absent → repli sur `discovered_at` (Partie IV §18.4) |
| `content` | texte, nullable | **tampon de traitement**, purgé (Partie II §8.5) |
| `content_hash` | texte ; index (non unique) | conservé après purge |
| `content_purged_at` | nullable | |
| `relevance_score` | réel | |
| `status` | `CHECK {ready, filtered, duplicate}` ; index | |
| `duplicate_of_id` | FK `Article`, nullable | renseigné si `duplicate` |
| `event_id` | FK `Event`, nullable ; index | appartenance à un événement |
| `summary` | texte, **non nul** | aperçu : repli à l'insertion (articles `ready` **et** `filtered`), puis synthèse LLM |
| `summary_origin` | `CHECK {fallback, llm}` | |
| `summary_lang` | texte | |
| `processed_at` | nullable | posé quand **tous** les traitements de l'article sont terminés ; point de départ du délai de grâce |
| `metrics` | JSON, validé par Pydantic | engagement fourni par le provider à la collecte (points HN, vues YouTube…) ; instantané, **jamais mis à jour** (Partie IV §15.4) |
| `clustered_at` | nullable | posé quand l'article a été évalué par le clustering (Partie V-B §28.2) |
| `clustered_semantic` | booléen, défaut `false` | le critère cosine a été évalué pour l'article |
| `importance` | réel, nullable | importance de l'article hors Event (Partie V-B §28.9) |

**Contraintes** : `UNIQUE(canonical_url)` · `UNIQUE(source_id, external_id)` partielle, `WHERE external_id IS NOT NULL`.

**Index** : partiel sur `clustered_at` `WHERE clustered_at IS NULL AND status = 'ready'` (sélection du clustering) · `(status, event_id, published_at)` (stories, Partie VI).

**Transitions de `status`** : l'insertion se fait en `ready` ou `filtered`. Seule transition autorisée ensuite : `ready → duplicate` (dédup sémantique rétroactive). Un article `duplicate` **conserve** ses topics et son résumé ; il est seulement **masqué à l'affichage**.

### 11.3 Event — *écrit par le worker*

| Colonne | Type / contrainte | Rôle |
|---|---|---|
| `title` | texte, non nul | repli = titre de l'article représentatif |
| `title_origin` | `CHECK {fallback, llm}` | indique ce que `resolve_event` doit encore enrichir |
| `description` | nullable | produite par `resolve_event` |
| `representative_article_id` | FK `Article` | membre `ready` le plus ancien par `published_at` (Partie V-B §28.8) |
| `first_seen_at` · `last_seen_at` | | |
| `article_count` | entier | nombre de membres `ready` |
| `distinct_source_count` | entier, non nul, défaut 1 | **hotness** |
| `distinct_channel_count` | entier, non nul, défaut 1 | nombre de canaux distincts (Partie V-B §28.9) |
| `importance` | réel, **non nul**, défaut 0 | Partie V-B §28.9 |
| `resolve_enqueued_count` | entier, nullable | `article_count` au dernier enqueue de `resolve_event` (Partie V-B §28.10) |
| `status` | `CHECK {active, merged, archived}` | |
| `merged_into_id` | FK `Event`, nullable | renseigné si `merged` |

`novelty` n'existe pas sur `Event` : c'est une fonction du temps, calculable à la lecture depuis `first_seen_at` (Partie V-B §28.9).

**Index** : `(status, last_seen_at)` · `(status, importance)` (stories, Partie VI).

**Invariant** : `distinct_source_count` = nombre de `source_id` distincts parmi les articles `ready` rattachés (étendu à `article_count` et `distinct_channel_count` par la Partie V-B §28.9). Il est mis à jour **dans la même transaction** que le rattachement ; un contrôle de cohérence peut le recalculer. L'invariant est testé.

### 11.4 Topic — *écrit par le worker*

`slug` (**UNIQUE**) · `name` · `description` · `parent_id` (FK `Topic`) · `origin` `CHECK {seeded, discovered, user}` · `keywords` (JSON `{include, exclude}` — `include` : mots-clés et motifs utilisés par le relevance filter ; `exclude` : termes masqués avant matching, Partie IV §16.3, §20.3) · `enabled`.

`origin` remplace le booléen `seeded` de la V0.3. Le suivi et la mise en sourdine ne sont **pas** ici : ce sont des préférences (§11.12).

### 11.5 ArticleTopic — *écrit par le worker*

`article_id` · `topic_id` · `method` `CHECK {keyword, llm}` · `confidence` · `created_at`.
**Clé** : `(article_id, topic_id, method)` — un même topic peut être attribué par les deux méthodes ; les tendances comptent les **articles distincts**.
**Index** : `topic_id` (lecture par topic : Trend Engine, vue Topic).

### 11.6 Entity — *écrit par le worker*

`type` (validé par le code : `company · product · person · project · technology · model · repository`) · `name` · `canonical_name` · `origin` `CHECK {dictionary, llm}`.
**Contrainte** : `UNIQUE(type, canonical_name)`.

Les **alias** d'entités ne sont pas en base : ils vivent dans `config/entities.yaml`, chargés en mémoire par le worker (Partie IV §16.4).

### 11.7 ArticleEntity — *écrit par le worker*

`article_id` · `entity_id` · `method` `CHECK {keyword, llm}` · `confidence` · `created_at`.
**Clé** : `(article_id, entity_id, method)`.
**Index** : `entity_id` (entités communes du clustering, Partie V-B §28.4).

### 11.8 Signal — *écrit par le worker*

`topic_id` · `period` `CHECK {24h, 7d, 30d}` · `computed_at` · `window_start` · `window_end` · `mentions` · `unique_sources` · `unique_authors` · `unique_companies` · `growth_rate` · `velocity` · `novelty` · `momentum` · `category` nullable, `CHECK {established, trending, rising, declining}` (`NULL` = support insuffisant, Partie V-B §29.6).
**Contrainte** : `UNIQUE(topic_id, period, window_end)` (upsert horaire, Partie V-B §29.4).
**Index** : `(topic_id, period, computed_at)`.

### 11.9 Embedding — *écrit par le worker*

`article_id` · `model` · `dim` (nullable) · `vector` (BLOB, `float32`, **normalisé**, nullable) · `error` (texte, nullable) · `created_at`.
**Contrainte** : `UNIQUE(article_id, model)`. Détails en §12.

`model` = nom du modèle fastembed + `@` + révision courte (ex. `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2@faf4aa42`). Un changement de révision produit de nouvelles lignes, comme un changement de modèle (§12.5).

Une ligne **sans vecteur** (`vector` `NULL`, `error` renseigné) enregistre un échec définitif d'embedding (Partie V-A §24.4) : elle compte comme traitée et elle est **exclue de la similarité**.

### 11.10 AIJob — *créé par le worker ou l'app ; exécuté par le worker*

| Colonne | Type / contrainte | Rôle |
|---|---|---|
| `job_type` | texte (validé par le code) | V1 : `enrich_article · resolve_event · discover_topics` (Partie V-A §23.2) |
| `entity_type` · `entity_id` | texte (validé par le code : `article · event · emerging_candidate`) · entier (sans FK) | cible du job |
| `priority` | entier | |
| `status` | `CHECK {pending, processing, completed, failed, retry, dead_letter, cancelled, skipped}` | |
| `skip_reason` | texte, nullable (validé par le code) | motif d'un `skipped` (Partie V-A §23.3) |
| `attempts` · `max_attempts` | entiers | |
| `next_attempt_at` | non nul, **fourni par l'application** (la `Clock`), sans défaut SQL | |
| `last_error` | texte | |
| `created_by` | `CHECK {worker, app}` | |
| `started_at` · `completed_at` | nullable | `completed_at` est renseigné par l'application (la `Clock`) à toute transition vers `completed`, `failed`, `cancelled` ou `skipped` ; `NULL` sinon, `dead_letter` compris — une relance (`dead_letter → pending`) le laisse ou le remet à `NULL`. Point de départ de la rétention (§13) |

**Statuts terminaux** : `completed` · `failed` (erreur non rejouable, ex. `job_type` inconnu) · `dead_letter` (tentatives épuisées) · `cancelled` — `dead_letter` abandonné par l'utilisateur · `skipped` — job sauté par sa garde d'éligibilité, sans appel LLM (Partie V-A §23.3). Un `dead_letter` peut aussi être **remis en `pending`** depuis le dashboard.

**Contraintes** :

- **Un seul job actif par cible et par type** : index unique partiel sur `(job_type, entity_type, entity_id)` `WHERE status IN ('pending','processing','retry')`. Une seconde demande identique est ignorée sans erreur.
- **Index de claim** : `(status, next_attempt_at, priority)`.

**Idempotence des résultats** : elle ne repose pas sur `AIJob` mais sur les tables métier. Un job **remplace** ses propres résultats pour sa cible dans une seule transaction — par exemple `enrich_article` supprime puis réécrit les lignes `method=llm` de l'article, sans toucher aux lignes `method=keyword`. Rejouer un job produit donc le même état final.

### 11.11 CollectorRun — *écrit par le worker* (nouveau)

Une ligne par exécution d'un collector : `source_id` · `started_at` · `finished_at` · `status` `CHECK {success, partial, failed}` · `items_fetched` · `items_created` · `items_duplicate` · `items_filtered` · `items_skipped` · `items_too_old` · `extractions_attempted` · `extractions_failed` · `requests_count` · `http_status` · `error`.
Alimente les métriques par source (§39) ; `items_skipped` compte les items malformés, non persistés. Définition des compteurs et invariant : Partie IV §14.4.
**Index** : `(source_id, finished_at)` (disjoncteur par source, Partie IV §21.5 ; rétention §13).

### 11.12 Tables écrites par l'app (nouvelles)

| Table | Colonnes | Contrainte |
|---|---|---|
| **`UserPreference`** | `subject_type` `CHECK {topic, source}` · `subject_id` · `action` `CHECK {follow, mute}` | `UNIQUE(subject_type, subject_id)` |
| **`Setting`** | `key` (PK) · `value` (JSON) · `updated_at` | réglages globaux ; clés, schémas et défauts dans le registre en code (Partie VI §34.3) |
| **`ReadState`** | `subject_type` `CHECK {event, article}` · `subject_id` · `read_at` | `UNIQUE(subject_type, subject_id)`, qui sert aussi d'index de lecture |
| **`EmergingDecision`** | `candidate_id` (FK) · `decision` `CHECK {follow, ignore, mute, create_topic}` · `decided_at` | `UNIQUE(candidate_id)` ; **upsert** autorisé, sauf après `create_topic`, définitif ; pas de suppression en V1 (Partie V-B §30.7) |

**Règle « lu »** : un article rattaché à un Event est lu quand son Event est lu ; `ReadState` sur un article ne sert qu'aux articles sans Event.

### 11.13 Tables écrites par le worker (nouvelles)

| Table | Colonnes | Contrainte |
|---|---|---|
| **`EmergingCandidate`** | `key` (terme normalisé) · `kind` `CHECK {ngram, repository}` · `label` · `first_detected_at` · `last_evidence_at` · `evidence` (JSON validé par Pydantic, Partie V-B §30.4) · `ref_mentions` · `ref_channel_count` · `last_significant_at` · `resurfaced_at` · `backfilled_at` · `topic_id` (FK, renseigné quand le worker crée le topic suite à `create_topic`) · résultat de `discover_topics` : `llm_label` · `llm_description` · `covered_by_topic_id` (FK `Topic`, nullable) · `suggested_keywords` (JSON) · `assessed_at` | `UNIQUE(key)` |
| **`AlertLog`** | `alert_type` `CHECK {important_event, emerging_topic, daily_digest, weekly_digest, system}` · `subject_type` `CHECK {event, emerging_candidate, digest, system}` · `subject_id` (`NULL` pour `digest` et `system`) · `channel` `CHECK {email, telegram}` · `status` `CHECK {sending, sent, failed, suppressed}` · `error` · `dedup_key` · `created_at` · `updated_at` | `UNIQUE(dedup_key)` — une alerte n'est jamais émise deux fois sur un même canal, même en échec (pas de reprise en V1) ; `dedup_key` inclut le canal (Partie VI §33.4) ; index `(alert_type, subject_type, subject_id)` |
| **`SystemState`** | `key` (PK) · `value` (JSON) · `updated_at` | chaque clé a un seul écrivain ; clés ci-dessous |

Pour le type `system`, `subject_type = 'system'` et `subject_id` est `NULL` : la condition est portée par `dedup_key` (Partie VII §39.6). Pour un digest, `subject_type = 'digest'` et `subject_id` est `NULL` : la période est portée par `dedup_key` (Partie VI §33.4).

**Clés `SystemState`**, toutes écrites par le worker :

| Clé | Valeur | Référence |
|---|---|---|
| `worker_heartbeat` | `{at, started_at, version, pid}` | Partie VII §39.3 |
| `last_backup` | `{at, snapshot_id, size_bytes, duration_s}` | Partie VII §38.2 |
| `backup_last_attempt` · `last_restore_test` | dernier essai de backup · dernier test de restauration | Partie VII §38 |
| `ops_metrics` · `ops_conditions` · `alerting` | instantané des métriques · conditions actives · état des canaux | Partie VII §39.3 |
| `llm_gateway` · `llm_usage` | disjoncteur LLM · budget quotidien | Partie V-A §24 |
| `embeddings` | `{state, since}` : état du moteur d'embeddings (`up` / `down`) | Partie V-A §24.4 |
| `trends_since` | `{at}` : première insertion d'un article `ready`, écrite une fois par le runner | Partie V-B §29.3 |
| `trends_last_run` | `{at, duration_s, status, error}` : dernier calcul du Trend Engine | Partie V-B §29.1 |

Le candidat émergent et la décision de l'utilisateur sont **deux tables distinctes** pour respecter la règle d'un seul écrivain par table.

### 11.14 Index plein texte `article_fts`

Table virtuelle **FTS5** sur `title` et `summary`, en mode *external content* (adossée à `Article`), tokenizer `unicode61 remove_diacritics 2`. Maintenue par **triggers** sur insertion, mise à jour de `title` ou `summary` (`AFTER UPDATE OF title, summary`) et suppression d'`Article` — donc écrite par le worker. La mise à jour d'un résumé par le LLM met l'index à jour automatiquement.

## 12. Embeddings

Les embeddings appartiennent à la **couche cœur** (Partie II §6.1) : calcul local, CPU, sans appel réseau. Ils servent à la similarité, au clustering, à la dédup sémantique et à la découverte de topics.

### 12.1 Moteur et modèle

- **Moteur** : `fastembed` (onnxruntime). Pas de PyTorch ni d'environnement HuggingFace lourd.
- **Modèle** : **multilingue**, obligatoire — les sources sont EN + FR, et un modèle anglais seul ne rapprocherait pas un article français de son équivalent anglais.
- **Cible** : `paraphrase-multilingual-MiniLM-L12-v2`, 384 dimensions. Sa disponibilité dans `fastembed` est **vérifiée au Sprint 0** (Partie IX §57.4) ; à défaut, un autre modèle multilingue de 384 dimensions au plus, supporté par `fastembed`. La **révision et l'empreinte** du modèle sont épinglées au build ; le choix est consigné dans l'ADR-0008.
- Le modèle est **chargé une fois** au démarrage du worker et reste en mémoire ; son empreinte RAM fait partie des mesures à réaliser avant production (Partie II §8.7).

### 12.2 Ce qui est embeddé

- **Uniquement les articles `ready`.** Ni `filtered`, ni doublons exacts (non insérés).
- **Texte d'entrée** : titre + les **N premiers caractères** du contenu (N configurable, valeur initiale 1 000). Tronquer borne le coût de calcul et rend les vecteurs comparables d'un article à l'autre.
- **L'embedding est calculé avant la purge du contenu** : un article n'est considéré comme traité (`processed_at`) qu'une fois son embedding écrit.

### 12.3 Stockage

- Table `Embedding` (§11.9), vecteur `float32` sérialisé en BLOB.
- **Normalisé à l'écriture** (norme 1) : la similarité cosine devient un simple produit scalaire.
- Pas de vector DB externe (non-objectif §5).

### 12.4 Recherche de similarité

- **Cosine brute-force numpy** sur une **fenêtre glissante** : les articles `ready` des dernières heures (même fenêtre que le clustering, 72 h par défaut, configurable).
- La fenêtre est tenue **en mémoire dans le worker**, sous forme de matrice, mise à jour à chaque nouvel embedding et reconstruite depuis la base au démarrage. Ordre de grandeur : 2 000 articles × 384 dimensions × 4 octets ≈ 3 Mo.
- **Deux seuils sur le même calcul** (valeurs configurables, à calibrer) : seuil haut → `duplicate` ; seuil médian → candidat même Event (Partie II §7.2).
- On ne compare **que des vecteurs produits par le même modèle**, c'est-à-dire de même `Embedding.model`, révision comprise (§11.9).

### 12.5 Changement de modèle

Un nouveau modèle produit de nouvelles lignes (`model` différent). Les anciens articles ne peuvent **pas** être ré-embeddés sur leur contenu, qui a été purgé ; si besoin, ils le sont sur **titre + résumé**, avec une qualité moindre. Ce cas est exceptionnel et reste manuel en V1.

## 13. Rétention des données

**Principe** : le produit accumule des **événements, topics, signaux, résumés et liens** — pas une archive d'articles. Toute suppression est exécutée par l'**étage de purge** du worker (Partie II §8.5), journalisée à chaque passage. Aucune donnée métier n'est supprimée hors de ce tableau.

| Donnée | Rétention |
|---|---|
| `Article.content` — article `ready` | purgé à `processed_at` **+ 1 jour** (configurable) ; **jamais** tant qu'un job de l'article est en `dead_letter` |
| `Article.content` — article `filtered` ou `duplicate` | purgé **immédiatement** |
| Ligne `Article` — `ready` ou `duplicate` | **indéfinie** (titre, URLs, métadonnées, résumé, hash) |
| Ligne `Article` — `filtered` | **supprimée 30 jours après `discovered_at`** |
| `Event` · `Topic` · `Entity` · tables de liaison | indéfinie |
| `Embedding` | indéfinie (volume faible ; utile pour la recherche sémantique V2) |
| `Signal` | valeurs horaires conservées 30 jours, puis seule la ligne de `window_end` = 00:00 UTC est conservée, indéfiniment (une valeur par jour et par topic/fenêtre) |
| `AIJob` — `completed` · `failed` · `cancelled` · `skipped` | supprimé 30 jours après `completed_at` |
| `AIJob` — `dead_letter` | conservé jusqu'à action de l'utilisateur (relance ou abandon) |
| `CollectorRun` | 30 jours après `finished_at` |
| `AlertLog` | 1 an après `created_at` (sert à la dédup des alertes) |
| `UserPreference` · `Setting` · `ReadState` · `EmergingCandidate` · `EmergingDecision` · `SystemState` | indéfinie |

**Effet de bord accepté** : un item `filtered` supprimé à 30 jours pourrait être re-collecté s'il réapparaît dans un flux ; il serait simplement réévalué et à nouveau écarté. Le checkpoint de collecte rend ce cas rare.

**Taille attendue** : la purge du contenu borne la base par le **nombre** d'articles, pas par leur longueur — de l'ordre de quelques centaines de Mo par an au volume réaliste. La taille de la base reste surveillée (§39, §44).

---

## Reporté en V2 (tracé depuis la Partie III)

- **Index vectoriel** (`sqlite-vec` ou équivalent) : uniquement si le cosine brute-force devient mesurablement insuffisant.
- **Recherche sémantique** de l'historique (déjà reportée par la Partie I) — les embeddings conservés indéfiniment la rendront possible.
- **Alias et fusion automatiques d'entités, en base** (ex. « Claude Code » / « claude-code » / « CC ») au-delà du `canonical_name`. En V1, les alias sont **déclarés à la main** dans `config/entities.yaml` (§11.6, Partie IV §16.4) et servent aussi à canonicaliser les entités LLM (Partie V-A décision 17).
- **Ré-embedding complet** lors d'un changement de modèle.
