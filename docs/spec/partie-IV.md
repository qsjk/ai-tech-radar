# Partie IV — Pipeline d'ingestion

> **Partie IV — Pipeline d'ingestion.** Version durcie issue de la revue §14–§22.
> Dernière révision : 2026-09-23. Prend les Parties I, II et III durcies comme acquis.

---

## Décisions tranchées dans cette revue (Partie IV)

1. **Les collectors ne touchent jamais la base.** Un collector transforme des réponses HTTP en `RawItem`, rien de plus. Un **runner** unique enchaîne les étages suivants et gère toutes les écritures.
2. **Nouvelle interface `Collector`** : itérateur asynchrone de **pages** (`items` + `checkpoint` + `quota` + `skipped`) au lieu de `fetch() -> list[RawItem]`.
3. **Une transaction d'écriture par page** (≤ 50 items), en `BEGIN IMMEDIATE`. Le checkpoint est écrit **dans la même transaction** que les items de la page. **Aucun appel réseau dans une transaction d'écriture.**
4. **Le checkpoint est une optimisation, pas une garantie.** L'absence de doublon repose sur la dédup exacte ; un checkpoint perdu coûte des requêtes, jamais des doublons.
5. **Dédup exacte, dans cet ordre** : `(source_id, external_id)` → `canonical_url` → `content_hash`. Filet final `INSERT … ON CONFLICT DO NOTHING`. Un doublon **n'est pas inséré** ; il est compté.
6. **`content_hash`** : SHA-256 du texte **du flux** normalisé, `NULL` sous 200 caractères, **jamais recalculé** après extraction.
7. **`content` est toujours du texte brut** (HTML retiré dès la normalisation).
8. **Relevance filter entièrement spécifié** : score par topic basé sur la **présence** de mots-clés (titre × 3, URL × 2, corps × 1), `relevance_score = max` des topics, seuil 3. **Aucun critère de diffusion** (pilier *recall*, Partie I).
9. **Mots-clés d'exclusion par topic dès la V1**, appliqués par **masquage** du texte avant matching.
10. **Sources de confiance** : `relevance: always` → article toujours `ready`, topics et entités keyword quand même calculés.
11. **Décision de pertinence sur le texte du flux ; liaisons keyword sur le texte final** (après extraction) pour les articles `ready`.
12. **Langues hors EN/FR stockées normalement** (le filtre thématique s'applique ; aucun rejet par langue).
13. **Âge maximal des items : 30 jours** (compteur `too_old`) ; **premier run plafonné à 100 items** par source.
14. **`published_at` absent → repli sur `discovered_at`**, colonne non nulle. Date future (> maintenant + 1 h) → `discovered_at`.
15. **Résumé de repli fixé ici** : résumé du flux, sinon début du contenu, sinon titre ; 300 caractères coupés sur une frontière de mot.
16. **Canaux V1 et endpoints** :
    - GitHub : **releases** des dépôts suivis uniquement.
    - Hacker News : **API Algolia** (une source = une requête).
    - Reddit : **flux RSS** du subreddit, sans credentials.
    - YouTube : **flux RSS** de la chaîne, sans clé.
    - Anthropic : releases GitHub `anthropics/claude-code` + **nouveau collector minimal `webpage`**.
17. **Le `type` d'une source désigne le canal, pas le protocole** : Reddit et YouTube restent `reddit` / `youtube` même s'ils sont lus en RSS (le comptage de canaux distincts en dépend).
18. **Signaux d'engagement capturés** dans une nouvelle colonne `Article.metrics` (JSON), instantané à la collecte, jamais mis à jour.
19. **Fichiers de configuration invalides → le worker refuse de démarrer** (fail-fast), avec une commande `validate-config` jouée en CI.
20. **Nouveau fichier `config/pipeline.yaml`** : tous les réglages « configurables » du pipeline y vivent, avec les défauts documentés ici.
21. **Embeddings : file dérivée**, sans `AIJob` — le worker embedde les articles `ready` sans ligne `Embedding` pour le modèle courant.
22. **Jobs LLM** : la Partie IV pose seulement le principe (jobs d'enrichissement créés pour chaque article `ready`, dans la transaction d'insertion) ; la liste exacte des `job_type` relève de la Partie V : **un `enrich_article` par article `ready`** (Partie V-A §23.2, reporté au §14.3).
23. **Disjoncteur par source** : après 3 runs `failed` consécutifs, l'intervalle double à chaque échec, jusqu'à 24 h ; retour à la normale au premier succès.
24. **Credentials manquants → sources du type non planifiées**, le worker démarre quand même. En V1, seul `GITHUB_TOKEN` est requis.

---

## 14. Pipeline

### 14.1 Étages et contrats

```
Source (config + état)
  │
  ▼  COLLECTOR ─────────────► Page { items: RawItem[], skipped, checkpoint, quota }
  │                           (HTTP uniquement, aucune écriture en base)
  ▼  NORMALISATION ─────────► NormalizedItem (texte brut, dates UTC, langue)
  │                           malformé → skipped
  ▼  CONTRÔLE D'ÂGE ────────► published_at < maintenant − max_item_age → too_old
  ▼  CANONICALISATION ──────► canonical_url, canonical_link_url
  ▼  DÉDUP EXACTE ──────────► doublon → duplicate (compté, non inséré)
  ▼  RELEVANCE FILTER ──────► relevance_score ; ready | filtered
  ▼  EXTRACTION CIBLÉE ─────► (ready uniquement) contenu enrichi ou inchangé
  ▼  LIAISONS KEYWORD ──────► topics + entités keyword (ready uniquement)
  ▼  RÉSUMÉ DE REPLI ───────► summary, summary_origin=fallback, summary_lang
  ▼  ÉCRITURE (1 transaction par page, BEGIN IMMEDIATE)
       Article + ArticleTopic + ArticleEntity + Entity (motifs) + AIJob
       + Source.checkpoint + quota
```

| Étage | Reçoit | Produit | Réseau | Base |
|---|---|---|---|---|
| Collector | spec de la source, checkpoint, client HTTP | pages de `RawItem` | oui | **non** |
| Normalisation | `RawItem` | `NormalizedItem` ou `skipped` | non | non |
| Contrôle d'âge | `NormalizedItem` | item ou `too_old` | non | non |
| Canonicalisation | `NormalizedItem` | URLs canoniques | non | non |
| Dédup exacte | item canonicalisé | item ou `duplicate` | non | lecture |
| Relevance | item + taxonomie | score, statut | non | non |
| Extraction | item `ready` éligible | contenu final | oui | non |
| Liaisons keyword | item `ready` + taxonomie + dictionnaire | liste de topics et d'entités | non | non |
| Résumé de repli | item | `summary` | non | non |
| Écriture | lot de la page | lignes en base | **non** | écriture |

Toutes ces fonctions, sauf le collector, l'extraction, la dédup et l'écriture, sont **pures** : testables sans réseau ni base.

### 14.2 Règles transverses

- **Aucun appel LLM**, à aucun étage (Partie II §6).
- **Aucun appel réseau pendant une transaction d'écriture.** Fetch et extraction sont terminés avant l'ouverture de la transaction de la page.
- **Travail CPU hors event-loop** (Partie II §8.4) : la normalisation, le hashing, le scoring et l'extraction trafilatura d'une page s'exécutent via `asyncio.to_thread` / l'exécuteur borné.
- **Isolation à deux niveaux** : une source en panne n'arrête pas les autres ; un item malformé n'arrête pas sa page.
- **Idempotence** : rejouer une collecte, entière ou partielle, ne crée aucun doublon.
- **`discovered_at`** = instant UTC du traitement de la page.
- **Temps lu par la `Clock`** (Partie VIII décision 7) : backoff et jitter (§21.2), limiteurs par hôte (§21.1), cache `robots.txt` (§17.3) et scheduler (§21.6) ne lisent jamais l'heure directement.

### 14.3 Écriture d'une page

Dans une seule transaction `BEGIN IMMEDIATE` :

1. insertion des articles (`ready` et `filtered`) avec `ON CONFLICT DO NOTHING` — un conflit est compté en `duplicate` ;
2. pour les `ready` : `ArticleTopic` et `ArticleEntity` `method=keyword`, création des `Entity` issues du motif GitHub (§16.4), création d'**exactement un `enrich_article`** par article, de priorité 60 si la source est en `relevance: always`, 50 sinon, avec `next_attempt_at` = maintenant + 15 min (Partie V-A §23.2) ;
3. mise à jour de `Source.checkpoint` avec le checkpoint de la page, et des champs de quota si la page en fournit ;
4. à la **première** insertion d'un article `ready`, écriture de `SystemState.trends_since` (une seule fois ; Partie V-B §29.3).

Les articles `filtered` sont insérés avec `content = NULL` et `content_purged_at` = maintenant (Partie III §13 : purge immédiate). Leur résumé de repli est calculé avant l'abandon du contenu.

Aucun job d'embedding n'est créé : l'étage embeddings sélectionne lui-même les articles `ready` sans ligne `Embedding` pour le modèle courant.

**Course entre deux collectors** : deux sources traitées en parallèle peuvent tenter d'insérer la même `canonical_url` ; le filet `ON CONFLICT` le gère. Une collision sur `content_hash` (index non unique) dans ce même intervalle est tolérée : elle sera rattrapée par la dédup sémantique asynchrone.

### 14.4 `CollectorRun`

Une ligne est écrite **à la fin** du run. Un worker tué en cours de run n'en écrit pas ; les pages déjà validées restent en base.

**Compteurs** :

| Compteur | Définition |
|---|---|
| `items_fetched` | nombre total d'entrées renvoyées par le provider, malformées comprises |
| `items_skipped` | entrées malformées, non persistées |
| `items_too_old` | entrées plus anciennes que `max_item_age` **(nouvelle colonne)** |
| `items_duplicate` | doublons exacts, non insérés (y compris conflits `ON CONFLICT`) |
| `items_filtered` | insérés en `filtered` |
| `items_created` | insérés en `ready` |
| `extractions_attempted` · `extractions_failed` | extraction ciblée (§17) **(nouvelles colonnes)** |
| `requests_count` | requêtes HTTP émises par le run, extraction comprise **(nouvelle colonne)** |

**Invariant testé** : `items_fetched = items_created + items_filtered + items_duplicate + items_skipped + items_too_old`.

**Statut** :

- `success` : toutes les pages attendues ont été traitées, ou le plafond de premier run est atteint ;
- `partial` : au moins une page a été traitée, puis une erreur a interrompu la pagination ;
- `failed` : aucune page n'a été traitée.

Les items `skipped` et les échecs d'extraction ne changent pas le statut.

**Mise à jour de `Source`** en fin de run :

- `last_success_at` si `success` ou `partial` ;
- `last_error` si `partial` ou `failed`, message passé par le nettoyage des secrets par valeur (Partie VII §42.4) ;
- `last_http_status` = statut de la dernière réponse du provider (hors extraction).

## 15. Collectors

### 15.1 Interface

```python
class Collector(Protocol):
    type: ClassVar[str]                       # clé du registre ; = Source.type
    channel: ClassVar[str]                    # canal : rss et webpage → web (V-B §28.9)
    config_model: ClassVar[type[BaseModel]]   # valide Source.config
    checkpoint_model: ClassVar[type[BaseModel]]
    requires: ClassVar[list[str]]             # variables d'environnement obligatoires
    default_poll_interval: ClassVar[int]      # secondes
    min_poll_interval: ClassVar[int]          # secondes
    default_extract: ClassVar[Literal["auto", "never"]]

    def pages(
        self,
        source: SourceSpec,              # key, url, config validée
        checkpoint: BaseModel | None,    # None = premier run
        http: HttpClient,                # client partagé (§21)
        limit: int | None,               # plafond d'items (premier run), sinon None
    ) -> AsyncIterator[Page]: ...

class Page(BaseModel):
    items: list[RawItem]
    skipped: int                  # entrées écartées par le parsing
    fetched: int                  # entrées renvoyées par le provider
    checkpoint: BaseModel         # état à persister après cette page
    quota: QuotaInfo | None       # None = inconnu

class RawItem(BaseModel):
    external_id: str | None
    url: str                      # page propre de l'item
    link_url: str | None          # lien externe éventuel
    title: str | None
    author: str | None
    published_at: datetime | None # avec fuseau, sinon rejet
    summary: str | None           # résumé fourni par le flux, distinct du contenu
    content: str | None
    content_format: Literal["html", "text", "markdown"]
    metrics: dict[str, int]       # engagement, clés propres au type (§15.4)

class QuotaInfo(BaseModel):
    remaining: int | None
    reset_at: datetime | None
```

**Règles** :

- Le registre associe chaque `type` à sa classe. Un `Source.type` inconnu du registre est une erreur de configuration (§16.5).
- Chaque type **déclare son canal** : `rss` et `webpage` → `web` ; les autres types sont leur propre canal (Partie V-B §28.9).
- Chaque entrée du provider est parsée **dans son propre `try`** ; un échec incrémente `skipped` et produit un log avec la source et l'identifiant de l'entrée si disponible.
- Le collector renvoie les items **du plus récent au plus ancien** quand le provider le permet, et s'arrête dès que `limit` est atteint.
- Le collector ne fait ni normalisation, ni dédup, ni filtrage : il remonte ce que le provider fournit.
- Le collector utilise **exclusivement** le `HttpClient` fourni. Les bibliothèques de parsing (feedparser) reçoivent des octets déjà téléchargés ; elles ne font jamais leurs propres requêtes.

### 15.2 Exécution

- Timeout global d'un run : **300 s** (configurable). Dépassement → run interrompu, statut selon §14.4.
- `max_instances = 1` par source.
- Sémaphore global : **3 collectors simultanés** (configurable).
- Un collector qui lève une exception non prévue donne un run `failed` (ou `partial`), journalisé ; il n'affecte ni les autres sources ni le worker.

### 15.3 Premier run

Un run est un **premier run** quand `Source.checkpoint` est vide. Il est plafonné à `first_run_limit` items (**100**, configurable), les plus récents. Le contrôle d'âge (§18.4) s'applique en plus.

### 15.4 Spécifications par type

Pour tous les types, `metrics` ne contient que des valeurs réellement fournies par le provider. Une métrique absente n'est pas mise à 0.

#### `rss` — flux RSS / Atom

- **Requête** : GET du flux avec `If-None-Match` / `If-Modified-Since` issus du checkpoint. **304 → page vide, run `success`.**
- **Parsing** : feedparser sur les octets reçus.
- **`external_id`** : `entry.id` (guid), sinon le lien de l'entrée.
- **`url`** : lien de l'entrée. **`link_url`** : `None`.
- **`summary`** : `entry.summary`. **`content`** : `entry.content[0].value` si présent, sinon `None`. Format `html`.
- **`published_at`** : `published`, sinon `updated`.
- **Pagination** : aucune.
- **Checkpoint** : `{etag, last_modified}`.
- **`metrics`** : `{}`.
- **Défauts** : intervalle 30 min (min 10 min) · `extract: auto` · pas de credentials.

#### `github` — releases d'un dépôt

- **Config** : `repo` (`owner/repo`), `include_prereleases` (défaut `false`).
- **Requête** : `GET /repos/{owner}/{repo}/releases?per_page=30`, authentifiée, avec `If-None-Match`. 304 → page vide, `success`.
- **Pagination** : page suivante (en-tête `Link`) **uniquement** si toutes les releases de la page sont plus récentes que `last_published_at` du checkpoint, dans la limite du plafond.
- **`external_id`** : id numérique de la release.
- **`url`** : `html_url`. **`link_url`** : `None`.
- **`title`** : `"{repo} {name}"`, ou `"{repo} {tag_name}"` si `name` est vide.
- **`author`** : `author.login`. **`published_at`** : `published_at`.
- **`content`** : `body`, format `markdown`. **`summary`** : `None`.
- **Checkpoint** : `{etag, last_published_at}`.
- **Quota** : en-têtes `x-ratelimit-remaining` / `x-ratelimit-reset`.
- **`metrics`** : `{}`.
- **Défauts** : 30 min (min 10 min) · `extract: never` · requiert `GITHUB_TOKEN`.

#### `hackernews` — API Algolia

Une source = une requête Algolia.

- **Config** : `mode` ∈ `{query, front_page}` ; `query` (obligatoire si `mode=query`).
  - `query` : `GET https://hn.algolia.com/api/v1/search_by_date?tags=story&query={query}&numericFilters=created_at_i>{last_created_at_i}&hitsPerPage=50`
  - `front_page` : `GET https://hn.algolia.com/api/v1/search?tags=front_page&hitsPerPage=50`
- **Pagination** (`mode=query`) : paramètre `page` tant que la page est pleine et que le plafond n'est pas atteint. Pas de pagination en `front_page`.
- **`external_id`** : `objectID`.
- **`url`** : `https://news.ycombinator.com/item?id={objectID}`. **`link_url`** : `hit.url` (`None` pour un Ask HN).
- **`author`** : `hit.author`. **`published_at`** : `created_at_i`.
- **`content`** : `story_text` si présent (format `html`), sinon `None`.
- **Checkpoint** : `{last_created_at_i}` (`mode=query`) ; `{}` (`front_page`, la dédup suffit).
- **Quota** : inconnu → `NULL`.
- **`metrics`** : `{points, num_comments}`.
- **Défauts** : 15 min (min 10 min) · `extract: auto` (la cible est `link_url`) · pas de credentials.

#### `reddit` — flux RSS d'un subreddit

- **Config** : `subreddit`, `listing` ∈ `{new, hot}` (défaut `new`).
- **Requête** : `GET https://www.reddit.com/r/{subreddit}/{listing}/.rss` avec le User-Agent du projet (§17.3) et GET conditionnel.
- **`external_id`** : id de l'entrée (fullname `t3_…`).
- **`url`** : permalink de l'entrée.
- **`link_url`** : cible de l'ancre `[link]` du contenu HTML si elle diffère du permalink ; sinon `None` (self-post).
- **`author`** : nom d'utilisateur sans préfixe `/u/`.
- **`content`** : contenu HTML de l'entrée, format `html`.
- **Checkpoint** : `{etag, last_modified}`.
- **Quota** : en-têtes `x-ratelimit-*` s'ils sont présents, sinon `NULL`.
- **`metrics`** : `{}` (non fournis par le flux).
- **Défauts** : 30 min (min 15 min) · `extract: auto` (`link_url` seulement) · pas de credentials.
- **Risque connu** : Reddit peut limiter ou bloquer les requêtes venant d'IP de datacenter. Un blocage se traite comme une panne de source (§21) ; le mode API est reporté en V2.

#### `youtube` — flux RSS d'une chaîne

- **Config** : `channel_id`.
- **Requête** : `GET https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}` (15 dernières vidéos).
- **`external_id`** : `yt:videoId`.
- **`url`** : `https://www.youtube.com/watch?v={videoId}`. **`link_url`** : `None`.
- **`author`** : nom de la chaîne. **`published_at`** : `published`.
- **`content`** : `media:description`, format `text`.
- **Pagination** : aucune. **Checkpoint** : `{etag, last_modified}`.
- **`metrics`** : `{views}` si `media:statistics` est présent.
- **Défauts** : 60 min (min 30 min) · `extract: never` · pas de clé.
- Pas de transcription en V1.

#### `webpage` — page de liste HTML (nouveau)

Collector minimal pour les sites sans flux (ex. anthropic.com/news). À utiliser **en dernier recours**, quand aucun flux ni API n'existe.

- **Config** : `item_selector` · `link_selector` (relatif à l'item) · `title_selector` (optionnel ; défaut = texte du lien) · `date_selector` (optionnel) · `date_format` (optionnel, format `strptime` ; sinon parsing ISO-8601 tolérant).
- **Requête** : GET conditionnel de `Source.url`, **une seule page**, jamais de pagination ni de suivi de liens. **Soumis à `robots.txt`** (§17.3).
- **`external_id`** : `None`. La dédup repose sur `canonical_url`.
- **`url`** : lien absolu de l'item. **`link_url`** : `None`.
- **`content`** : `None` → l'article passe presque toujours par l'extraction ciblée.
- **`published_at`** : date extraite si le sélecteur est fourni et parse, sinon `None` (repli §18.4).
- Une liste qui ne produit **aucun item** alors qu'elle en produisait avant est journalisée comme erreur de run `failed` : c'est le signe d'un changement de gabarit HTML.
- **Checkpoint** : `{etag, last_modified}`.
- **Défauts** : 120 min (min 60 min) · `extract: auto` · pas de credentials.

## 16. Seed des sources, topics et entités

### 16.1 Principes

Quatre fichiers versionnés dans `config/` :

| Fichier | Contenu | Chargé en base |
|---|---|---|
| `sources.yaml` | périmètre de collecte | oui → `Source` |
| `topics.yaml` | taxonomie + mots-clés + exclusions | oui → `Topic` |
| `entities.yaml` | dictionnaire d'entités + alias | oui → `Entity` (alias gardés en mémoire) |
| `pipeline.yaml` | réglages du pipeline (§16.6) | non (lu en mémoire) |

- Chargement par le worker **à son démarrage uniquement**, après la vérification du schéma (Partie III §10.1) et **avant** le démarrage du scheduler. Modifier un fichier demande un redémarrage du worker. Le worker est le seul à charger `sources.yaml`, `topics.yaml` et `entities.yaml` en base.
- **L'app charge `pipeline.yaml` en lecture seule**, avec les mêmes modèles de validation que le worker, pour les réglages qu'elle utilise (`ops.heartbeat_stale_after`, `emerging.warmup`, `llm.daily_request_budget`, `llm.app_reserve`). Elle ne charge aucun des trois autres fichiers et n'écrit rien en base à partir de `config/`.
- **Taxonomie du runner** : les topics de `topics.yaml` **plus** les topics activés d'origine `user` lus en base (issus d'un « Create topic », Partie V-B §30.8). Le runner recharge sa taxonomie à la création d'un topic, sans redémarrage.
- Upsert dans **une seule transaction d'écriture**, idempotent : charger deux fois les mêmes fichiers ne change rien.
- Le YAML écrase les **champs de configuration** ; il ne touche jamais aux **champs d'état** (`checkpoint`, `last_*`, `rate_limit_*`).

### 16.2 `sources.yaml`

```yaml
sources:
  - key: anthropic-news            # slug [a-z0-9-], unique, immuable
    name: Anthropic — News
    type: webpage
    url: https://www.anthropic.com/news
    relevance: always              # filter (défaut) | always
    config:
      item_selector: "article"
      link_selector: "a"
  - key: claude-code-releases
    name: Claude Code — Releases
    type: github
    url: https://github.com/anthropics/claude-code
    relevance: always
    config:
      repo: anthropics/claude-code
      include_prereleases: true
  - key: hn-mcp
    name: HN — MCP
    type: hackernews
    url: https://news.ycombinator.com
    poll_interval: 15m
    config:
      mode: query
      query: "model context protocol"
```

| Champ | Obligatoire | Défaut | Règle |
|---|---|---|---|
| `key` | oui | — | slug `[a-z0-9-]+`, unique dans le fichier, clé d'upsert |
| `name` | oui | — | |
| `type` | oui | — | présent dans le registre des collectors |
| `url` | oui | — | URL lisible de la source, affichée dans le dashboard ; pour `webpage`, c'est la page de liste |
| `enabled` | non | `true` | |
| `poll_interval` | non | défaut du type | durée (`15m`, `2h`) ; inférieure au minimum du type → erreur |
| `relevance` | non | `filter` | `filter` ou `always` |
| `extract` | non | défaut du type | `auto` ou `never` |
| `config` | selon le type | — | validé par `config_model` du collector |

**Upsert** (clé `key`) :

- nouvelle `key` → insertion, `checkpoint` vide ;
- `key` existante → mise à jour de `name`, `url`, `config`, `enabled`, `poll_interval`, `relevance`, `extract` ;
- `type` différent pour une `key` existante → **erreur** (créer une nouvelle `key`) ;
- `key` présente en base mais absente du fichier → `enabled = false`, jamais de suppression (FK `RESTRICT`), log `info`.

`relevance` et `extract` sont deux colonnes de `Source`, avec contrainte `CHECK` (Partie III §11.1).

### 16.3 `topics.yaml`

```yaml
topics:
  - slug: claude-code
    name: Claude Code
    parent: anthropic
    description: CLI agentique de codage d'Anthropic
    keywords:
      - { term: "claude code", weight: 3 }
      - { term: "claude-code", weight: 3 }
      - "claude cli"
  - slug: anthropic
    name: Anthropic
    keywords:
      - { term: "anthropic", weight: 3 }
      - { term: 'claude (opus|sonnet|haiku)', regex: true, weight: 3 }
      - "claude"
    exclude:
      - "claude monet"
      - "claude debussy"
```

| Champ | Obligatoire | Défaut | Règle |
|---|---|---|---|
| `slug` | oui | — | slug unique, clé d'upsert |
| `name` | oui | — | |
| `description` | non | `null` | |
| `parent` | non | `null` | slug d'un topic du fichier ; cycle → erreur |
| `enabled` | non | `true` | un topic désactivé n'est pas utilisé par le scoring |
| `keywords` | oui (≥ 1) | — | chaîne, ou `{term, weight=1, regex=false}` ; `weight` > 0 |
| `exclude` | non | `[]` | liste de termes (non regex) masqués avant matching (§20.3) |

**Upsert** (clé `slug`) : `origin = seeded`. `keywords` et `exclude` sont stockés ensemble dans la colonne JSON `Topic.keywords`, sous la forme `{include, exclude}` (Partie III §11.4).

- `slug` existant en `seeded` → mise à jour ;
- `slug` existant en `discovered` ou `user` → **promu en `seeded`**, champs mis à jour ;
- topic `seeded` absent du fichier → `enabled = false` ;
- topics `discovered` et `user` absents du fichier → non touchés.

Modifier des mots-clés s'applique **aux nouveaux articles seulement**. Pas de re-scoring rétroactif en V1.

### 16.4 `entities.yaml`

```yaml
entities:
  - type: company
    canonical_name: anthropic
    name: Anthropic
  - type: product
    canonical_name: claude-code
    name: Claude Code
    aliases: ["claude code", "claude-code"]
  - type: model
    canonical_name: claude-opus
    name: Claude Opus
    aliases: [{ term: 'claude[ -]?opus', regex: true }]

github_reserved_paths:   # premiers segments d'URL github.com qui ne sont pas des owners
  [orgs, topics, settings, features, marketplace, sponsors, collections, trending,
   explore, about, pricing, login, join, notifications, search, apps, enterprise]
```

| Champ | Obligatoire | Défaut | Règle |
|---|---|---|---|
| `type` | oui | — | `company · product · person · project · technology · model · repository` |
| `canonical_name` | oui | — | minuscules ; `(type, canonical_name)` unique ; clé d'upsert |
| `name` | oui | — | libellé affiché |
| `aliases` | non | `[]` | termes de matching (même forme que `keywords`) ; `name` et `canonical_name` sont toujours matchés en plus |

**Upsert** (clé `(type, canonical_name)`) : `origin = dictionary` ; `name` mis à jour. Une entité absente du fichier **reste en base** (elle porte des liaisons) mais n'est plus matchée. Les alias ne sont **pas** stockés en base : ils vivent dans la configuration chargée en mémoire.

**Motif générique unique — dépôts GitHub** : toute URL `github.com/{owner}/{repo}` trouvée dans `url`, `link_url` ou le contenu, dont `owner` n'est pas dans `github_reserved_paths`, produit une entité `repository` :

- `canonical_name` = `owner/repo` en minuscules (suffixe `.git` retiré) ;
- `name` = `owner/repo` tel qu'écrit ;
- créée à la volée dans la transaction de la page si elle n'existe pas (`origin = dictionary`).

Aucun autre motif libre en V1 (pas de regex générique `mot/mot`, trop bruitée).

### 16.5 Validation

- Les quatre fichiers sont validés par des modèles Pydantic.
- **Toute erreur** (syntaxe YAML, champ manquant, type inconnu, `poll_interval` sous le minimum, doublon de clé, parent inexistant, cycle, regex invalide, `config` refusée par le collector) → **le worker refuse de démarrer**. Le message donne le fichier, l'entrée (clé) et le champ.
- **Contraintes croisées** : `clustering.embedding_wait + clustering.tick` doit rester strictement inférieur à `llm.delay.enrich_article` (Partie V-B §28.15).
- Commande `python -m app.cli validate-config` : même validation, sans base. Jouée en CI.
- `pipeline.yaml` est optionnel : absent → défauts. Présent, il est validé comme les autres.
- **Fichier obligatoire absent** (`sources.yaml`, `topics.yaml` ou `entities.yaml`) : c'est une erreur. Le worker refuse de démarrer, et `validate-config` renvoie le code `2` (Partie IX §56.3).
- **`pipeline.yaml` invalide côté app** : l'app, qui le lit en lecture seule avec les mêmes modèles (§16.1), **refuse de démarrer**, comme le worker, avec le même message (fichier, clé, champ).

### 16.6 `pipeline.yaml` — réglages et défauts

Toute valeur qualifiée de « configurable » dans cette partie vit ici. Les secrets et les paramètres de déploiement restent en variables d'environnement.

| Clé | Défaut | Section |
|---|---|---|
| `collectors.max_concurrent` | 3 | §15.2 |
| `collectors.run_timeout` | 300 s | §15.2 |
| `collectors.first_run_limit` | 100 | §15.3 |
| `collectors.page_size_max` | 50 | §14.3 |
| `normalization.max_item_age` | 30 j | §18.4 |
| `normalization.title_max_length` | 500 | §18.2 |
| `normalization.content_max_length` | 100 000 | §18.2 |
| `normalization.tracking_params` | liste §18.3 | §18.3 |
| `language.min_text_length` | 20 | §18.5 |
| `language.min_relative_distance` | 0,25 | §18.5 |
| `dedup.hash_min_length` | 200 | §19.2 |
| `relevance.weight_title` · `weight_url` · `weight_body` | 3 · 2 · 1 | §20 |
| `relevance.threshold` | 3 | §20 |
| `relevance.body_max_length` | 20 000 | §20 |
| `summary.fallback_max_length` | 300 | §14.5 |
| `summary.feed_summary_min_length` | 40 | §14.5 |
| `extraction.min_feed_content` | 500 | §17.1 |
| `extraction.max_concurrent` | 3 | §17.3 |
| `extraction.per_host_interval` | 5 s | §17.3 |
| `extraction.timeout` · `max_bytes` · `max_redirects` | 15 s · 3 Mo · 5 | §17.3 |
| `extraction.denylist` | `[x.com, twitter.com, facebook.com, instagram.com, linkedin.com]` | §17.3 |
| `http.connect_timeout` · `read_timeout` | 5 s · 20 s | §21.1 |
| `http.max_retries` | 5 | §21.2 |
| `http.backoff_base` · `backoff_cap` · `jitter` | 1 s · 60 s · 20 % | §21.2 |
| `http.retry_after_max_wait` | 60 s | §21.3 |
| `http.per_host_interval` | 1 s (+ surcharges par hôte) | §21.1 |
| `breaker.failure_threshold` · `max_interval` | 3 · 24 h | §21.5 |
| `scheduler.startup_jitter` | 120 s | §21.6 |

Les autres sections de `pipeline.yaml` sont définies avec leur étage, et validées de la même façon : `llm.*`, `embeddings.*`, `topic_backfill.*` (Partie V-A §27.8) · `clustering.*`, `importance.*` (Partie V-B §28.15) · `trends.*` (Partie V-B §29.8) · `emerging.*` (Partie V-B §30.9) · `alerts.*`, `ops.*`, `backup.*`, `restore_test.*` (Partie VII §39.7).

### 14.5 Résumé de repli *(complément du §14, placé ici pour la lisibilité)*

Calculé pour **tout** article inséré (`ready` et `filtered`) :

1. `RawItem.summary` nettoyé (§18.2), s'il fait au moins `feed_summary_min_length` caractères ;
2. sinon, début du contenu **final** (après extraction éventuelle) ;
3. sinon, le titre.

Le texte retenu est coupé à `fallback_max_length` caractères (300) sur la dernière frontière de mot, suivi de `…` s'il a été coupé. `summary_origin = fallback`, `summary_lang = language` (éventuellement `NULL`).

## 17. Extraction de contenu

### 17.1 Déclenchement

L'extraction est tentée **si et seulement si** :

- l'article est `ready` ;
- la source est en `extract: auto` ;
- le contenu du flux normalisé fait moins de `min_feed_content` caractères (500) ;
- une cible existe : `link_url` si présent, sinon `url` — sauf pour `hackernews` et `reddit`, où seul `link_url` est une cible valable (la page propre est une discussion) ;
- l'hôte de la cible n'est pas dans la denylist.

### 17.2 Résultat

- Extraction du **texte principal** par trafilatura (sortie texte, sans commentaires ni tableaux), exécutée hors event-loop.
- Le texte extrait remplace le contenu du flux **seulement s'il est plus long**.
- `canonical_link_url` (ou `canonical_url` si la cible était `url`) est **mis à jour avec l'URL finale** après redirections, canonicalisée (§18.3). Si cette URL finale correspond à une `canonical_url` déjà en base, l'article est **quand même inséré** : le rapprochement relève du clustering, pas de la dédup.
- La langue est re-détectée si le contenu a changé.
- Le `content_hash` **n'est pas recalculé** (§19.2).

### 17.3 Règles de fetch

- **User-Agent** : `AITechRadar/{version} (+{HTTP_CONTACT})`, utilisé pour toutes les requêtes du projet.
- Timeout 15 s · 5 redirections au plus · 3 Mo au plus (au-delà, abandon) · `Content-Type` `text/html` uniquement (pas de PDF en V1).
- Concurrence globale de 3 extractions ; **une requête toutes les 5 s au plus par hôte**.
- **`robots.txt`** (RFC 9309), vérifié pour l'extraction **et** pour le collector `webpage` — pas pour les flux et API, faits pour être consommés :
  - récupéré via le `HttpClient`, mis en cache **24 h par hôte** en mémoire ;
  - `robots.txt` en 4xx → tout est autorisé ;
  - en 5xx ou timeout → tout est refusé jusqu'à la prochaine tentative ;
  - règles évaluées pour le token `AITechRadar`, sinon `*`.
- Aucun suivi de lien, aucune seconde page : **une URL par article**, conformément au non-objectif « scraping massif » (Partie I §5).

### 17.4 Échec

Échec de fetch, refus robots, type de contenu refusé, taille dépassée ou extraction vide → on garde le contenu du flux, l'article reste `ready`, `extractions_failed` est incrémenté, log `warning` avec la cause. **Pas de retry en V1**, pas de nouvelle tentative ultérieure.

## 18. Normalisation

### 18.1 Contrat

`RawItem` → `NormalizedItem` ou `skipped`. Fonction pure.

**Un item est `skipped` si** : `url` absente ou non HTTP(S) · titre et contenu vides après nettoyage · `published_at` sans fuseau.

### 18.2 Texte

Appliqué au titre, au résumé et au contenu :

1. si le format est `html` : suppression des balises (le texte des balises `script` et `style` est retiré), décodage des entités ; si `markdown` : conservé tel quel ;
2. normalisation Unicode **NFC** ;
3. fusion des espaces (retours à la ligne de paragraphe conservés dans le contenu) ;
4. trim.

- **Titre** : en plus, une seule ligne, `title_max_length` caractères au plus. Titre vide → 100 premiers caractères du contenu, coupés sur une frontière de mot.
- **Contenu** : coupé à `content_max_length` caractères.
- **Auteur** : trim ; vide → `NULL`. Jamais inventé.

### 18.3 Canonicalisation d'URL

Appliquée à `url` → `canonical_url` et à `link_url` → `canonical_link_url` :

1. scheme et host en minuscules ; host IDN converti en punycode ;
2. port par défaut retiré (`:80` en http, `:443` en https) ;
3. fragment `#…` retiré ;
4. paramètres de tracking retirés : `utm_*`, `fbclid`, `gclid`, `dclid`, `msclkid`, `mc_cid`, `mc_eid`, `ref`, `ref_src`, `source`, `igshid`, `si` (liste configurable) ;
5. paramètres restants triés par nom ;
6. `/` final retiré, sauf pour la racine ;
7. `www.` **conservé** ; scheme **conservé** (pas de forçage http → https) ;
8. aucune requête réseau (pas de suivi de redirection hors extraction).

**Canonicaliseurs spécifiques**, appliqués après les règles communes :

| Motif | Forme canonique |
|---|---|
| `youtu.be/{id}` · `youtube.com/watch?v={id}&…` · `m.youtube.com/…` | `https://www.youtube.com/watch?v={id}` |
| `old.reddit.com` · `reddit.com` · `np.reddit.com` | `https://www.reddit.com/…` |
| `news.ycombinator.com/item?id={n}&…` | `https://news.ycombinator.com/item?id={n}` |

### 18.4 Dates

- Conversion en **UTC**.
- `published_at` absent → `discovered_at`.
- `published_at` > maintenant + 1 h → `discovered_at`.
- **Contrôle d'âge** : `published_at` < maintenant − `max_item_age` (30 j) → `too_old`, non persisté. Un item dont la date vient du repli n'est donc jamais `too_old`.

### 18.5 Langue

- Bibliothèque **`lingua`**, détecteur limité à : EN, FR, DE, ES, IT, PT, NL, RU, ZH, JA. Les langues autres que EN/FR servent à ne pas classer de force un texte étranger en anglais ou en français.
- Texte analysé : titre + 1 000 premiers caractères du contenu (ou du résumé).
- `language` = code ISO 639-1 en minuscules. `NULL` si le texte fait moins de 20 caractères ou si le détecteur ne tranche pas (distance relative minimale 0,25).
- **Aucun filtrage par langue** : un article en allemand pertinent est `ready`.

## 19. Déduplication exacte

### 19.1 Critères, dans l'ordre

Le pipeline synchrone ne fait que de la dédup **exacte**. La similarité sémantique est asynchrone, hors pipeline (Partie II §7.2).

1. **`(source_id, external_id)`** existe déjà — re-collecte de la même source (si `external_id` non nul) ;
2. **`canonical_url`** existe déjà — même item vu par une autre source ou un autre flux ;
3. **`content_hash`** existe déjà — copie miroir ou syndication (si le hash n'est pas `NULL`).

La comparaison porte sur **tous les articles en base**, quel que soit leur statut (`ready`, `filtered`, `duplicate`). Deux items identiques **dans une même page** sont traités de la même façon : le second est un doublon.

**Filet** : `INSERT … ON CONFLICT DO NOTHING` sur `canonical_url` et `(source_id, external_id)` ; un conflit est compté en `duplicate`.

### 19.2 `content_hash`

- Entrée : texte **du flux** normalisé (§18.2) — le contenu s'il existe, sinon le résumé — puis passé en **minuscules**, normalisé **NFKC**, espaces fusionnés en une espace simple.
- Sortie : SHA-256 hexadécimal.
- **`NULL` si l'entrée fait moins de 200 caractères** (évite les collisions sur des extraits vides ou génériques).
- Calculé une fois, **jamais recalculé** après extraction.

### 19.3 Doublon détecté

- **Non inséré**, compté dans `items_duplicate`. Log `debug` avec le critère déclencheur.
- Deux sources ayant la même URL propre d'item ne comptent **pas** comme deux sources distinctes pour la hotness. Une discussion HN ou Reddit a sa propre URL : elle reste un article distinct, rattaché à l'Event par le clustering.
- **Mise à jour chez le provider ignorée en V1** : un item déjà en base dont le contenu a changé (release éditée, billet corrigé) n'est pas mis à jour.
- Un article `filtered` supprimé au bout de 30 jours (Partie III §13) et re-collecté est réévalué comme un nouvel item ; le contrôle d'âge l'écarte en pratique.

## 20. Relevance filter

### 20.1 Contrat

- **Entrée** : `NormalizedItem` + taxonomie chargée (`topics.yaml`) + dictionnaire (`entities.yaml`).
- **Sortie** : `relevance_score`, statut `ready` | `filtered`, puis — pour les `ready` — liste des topics et des entités keyword.
- Fonction pure, déterministe, **sans réseau ni base**.
- **Aucun critère de diffusion** (nombre de sources, engagement) : le filtre coupe le hors-sujet, jamais le peu relayé (Partie I, pilier *recall*).

### 20.2 Normalisation de matching

`norm(texte)` : NFKC → minuscules (`casefold`) → suppression des diacritiques (décomposition NFD, retrait des marques combinantes).

Trois textes par article :

- **titre** : `norm(title)` ;
- **corps** : `norm(content ou summary)`, limité à `body_max_length` caractères (20 000) ;
- **URL** : `canonical_link_url` s'il existe, sinon `canonical_url` ; host + chemin, passés par `norm`, où les caractères `/ - _ . ? = &` sont remplacés par des espaces (ainsi `github.com/anthropics/claude-code` contient `claude code`).

**Matching d'un terme** :

- terme simple : `norm(term)` cherché avec des frontières explicites `(?<![a-z0-9])` … `(?![a-z0-9])` — `gpt-4o`, `c++` ou `mcp server` sont donc matchables ;
- terme `regex: true` : expression appliquée telle quelle au texte normalisé, frontières à la charge de l'auteur ;
- on mesure la **présence** (0 ou 1) par texte, jamais le nombre d'occurrences.

### 20.3 Formule

Pour chaque topic *t* activé :

1. **masquage** : chaque terme de `exclude_t` présent dans un des trois textes y est remplacé par des espaces (copie propre au topic *t*) ;
2. score :

```
score_t = Σ_k∈keywords_t  w_k × ( W_title·[k ∈ titre] + W_url·[k ∈ URL] + W_body·[k ∈ corps] )

relevance_score = max_t score_t        (0 si aucun topic)
statut = ready     si relevance_score ≥ threshold, ou si la source est en relevance: always
         filtered  sinon
```

**Défauts** : `W_title = 3` · `W_url = 2` · `W_body = 1` · `w_k = 1` · `threshold = 3`.
Lecture : un mot-clé dans le titre suffit ; ou un mot-clé dans l'URL et un dans le corps ; ou trois mots-clés distincts dans le corps ; un terme de poids 3 suffit n'importe où.

Le **`max`** plutôt que la somme sert le recall : un seul topic bien couvert suffit à retenir l'article. Ces valeurs sont un point de départ à calibrer sur données réelles.

`relevance_score` est stocké pour tous les articles insérés, y compris en `relevance: always`.

### 20.4 Liaisons keyword (articles `ready` uniquement)

Calculées avec la même fonction, mais sur le **texte final** (après extraction éventuelle) :

- **`ArticleTopic`** `method=keyword` pour chaque topic dont `score_t ≥ threshold`, avec `confidence = min(1, score_t / (2 × threshold))`. Pas de propagation vers le topic parent en base.
- **`ArticleEntity`** `method=keyword` pour chaque entité dont `name`, `canonical_name` ou un alias est présent dans le titre ou le corps, et pour chaque dépôt GitHub trouvé par le motif (§16.4) ; `confidence = 1`.

Un article `ready` peut n'avoir aucun topic keyword (cas `relevance: always`, ou texte enrichi qui ne matche plus) ; l'enrichissement LLM pourra en ajouter.

Les articles `filtered` n'ont **aucune** liaison.

### 20.5 Testabilité

- Table de cas en fixtures : `(titre, corps, url, taxonomie) → (score attendu, statut, topics, entités)`.
- Cas obligatoires : match titre seul · match corps seul sous le seuil · exclusion par masquage · regex · terme avec ponctuation (`gpt-4o`) · diacritiques · texte FR · URL seule · source `always` sous le seuil.

## 21. Rate limiting, quota et scheduler

### 21.1 Client HTTP partagé

Un seul `HttpClient` (httpx asynchrone) pour les collectors, l'extraction et `robots.txt` :

- User-Agent du projet (§17.3) ;
- timeouts : connexion 5 s, lecture 20 s ;
- **limiteur par hôte** : un intervalle minimal entre deux requêtes vers le même hôte — 1 s par défaut, 5 s pour l'extraction, surcharges par hôte dans `pipeline.yaml` (ex. `www.reddit.com: 6s`) ;
- lecture des en-têtes de quota et production d'un `QuotaInfo` quand ils existent ;
- incrément du compteur `requests_count` du run courant ;
- masquage de l'en-tête `Authorization` et des paramètres sensibles dans tous les logs ;
- **garde anti-SSRF** (Partie VII §43.3) : refus de toute destination dont l'adresse résolue est privée, de bouclage, lien-local, unique-local IPv6 ou non routable, **vérifiée après résolution DNS et à chaque redirection**, **sans exception** : le `LLMClient` utilise son propre client HTTP (Partie V-A §25.2) et restic est un binaire externe (Partie VII §38.2), aucun des deux ne passe par le `HttpClient` ;
- **liste d'hôtes autorisés de test** : injectée par les tests, ou lue dans `HTTP_TEST_ALLOW_HOSTS` **uniquement** si `APP_ENV=test` ; elle coexiste avec la garde anti-SSRF sans l'affaiblir en production. Renseignée avec `APP_ENV=production`, le worker refuse de démarrer (Partie VIII décision 23).

### 21.2 Retry et backoff

- **Rejouables** : erreurs réseau, timeouts, 5xx, 429.
- **Non rejouables** : 400, 401, 403 (hors rate limit, §21.3), 404, 410 et autres 4xx → échec immédiat de la requête.
- Backoff exponentiel : `1 · 2 · 4 · 8 · 16 s` (`backoff_base × 2^n`, plafonné à `backoff_cap` = 60 s), **± 20 % de jitter**, `max_retries = 5`.
- Retries épuisés → échec de la requête ; le collector termine le run en `partial` ou `failed` (§14.4).

### 21.3 429 et `Retry-After`

- `Retry-After` (secondes ou date HTTP) **≤ 60 s** → attente dans le run ; compte comme un retry.
- **> 60 s**, absent après épuisement des retries, ou quota épuisé signalé par les en-têtes → **arrêt du run** (`partial` ou `failed`), avec :
  - `Source.rate_limit_remaining = 0` (valeur observée : le serveur signale l'épuisement) ;
  - `Source.rate_limit_reset_at` = instant indiqué par `Retry-After` ou par l'en-tête de reset ; à défaut, maintenant + `poll_interval`.
- **GitHub** : un 403 accompagné de `x-ratelimit-remaining: 0` est traité comme un 429.

### 21.4 Quota

- Mis à jour en fin de page quand la page fournit un `QuotaInfo`.
- En-têtes lus : GitHub `x-ratelimit-remaining` / `x-ratelimit-reset` ; Reddit `x-ratelimit-remaining` / `x-ratelimit-reset` (secondes) s'ils sont présents.
- Aucun en-tête → **`NULL`**, affiché « Quota: unknown ». Aucune estimation locale.

### 21.5 Disjoncteur par source

- *k* = nombre de runs `failed` consécutifs les plus récents (lu dans `CollectorRun`). Un run `partial` ou `success` remet *k* à 0.
- Si *k* ≥ 3 : intervalle effectif = `min(poll_interval × 2^(k−2), 24 h)`.
- Les échecs d'authentification (401, 403) comptent comme des échecs.

### 21.6 Scheduler

- Un job APScheduler par source **activée et planifiable** (§22), à `poll_interval`, avec `coalesce=True` et `max_instances=1`.
- Premier déclenchement au démarrage : maintenant + délai aléatoire dans `[0, 120 s]`, pour étaler les sources.
- **Au déclenchement, le runner saute le run** (sans écrire de `CollectorRun`, log `debug`) si :
  - `rate_limit_remaining = 0` et `rate_limit_reset_at` > maintenant ; ou
  - le disjoncteur est ouvert : dernier run + intervalle effectif > maintenant.
- Coalescence des misfires au redémarrage (Partie II §8.4).

## 22. Authentification des APIs

- API officielle **privilégiée** au scraping. Pour Reddit et YouTube, les flux RSS publics sont utilisés en V1 : ils ne demandent pas de credentials.
- Credentials en **variables d'environnement** uniquement, jamais dans le dépôt ni dans les fichiers `config/`.

| Variable | Utilisée par | Obligatoire |
|---|---|---|
| `GITHUB_TOKEN` | `github` | oui pour les sources `github` — token *fine-grained*, lecture seule, dépôts publics |
| `HTTP_CONTACT` | User-Agent (toutes requêtes) | **oui** (URL ou email de contact) — absent → le worker refuse de démarrer |
| `REDDIT_CLIENT_ID` · `REDDIT_CLIENT_SECRET` · `YOUTUBE_API_KEY` | — | réservées au mode API (V2), non lues en V1 |

- Au démarrage, pour chaque type présent dans `sources.yaml`, les variables de `Collector.requires` sont vérifiées.
- **Variable manquante** → les sources de ce type ne sont **pas planifiées** ; log `warning` ; état « credentials manquants » exposé au monitoring (`missing_credentials`, Partie VII §40.3). Le worker démarre quand même.
- Un 401 en cours d'exploitation est un échec de run normal (§21.5), journalisé sans le secret.

---

## Reporté en V2 (tracé depuis la Partie IV)

- **Mode API pour Reddit et YouTube** (OAuth Reddit, YouTube Data API) — utile si les flux RSS sont bloqués ou pour les métriques d'engagement.
- **Recherche de nouveaux dépôts GitHub** par topic ou par requête (`search/repositories`).
- **Rechargement à chaud** des fichiers `config/` sans redémarrer le worker.
- **Re-scoring rétroactif** des articles après modification des mots-clés (sur titre + résumé, le contenu étant purgé).
- **Mise à jour des items modifiés** chez le provider (release éditée, billet corrigé) et rafraîchissement des métriques d'engagement.
- **Retry de l'extraction ciblée** et extraction des PDF.
- **Transcriptions YouTube.**
- **Collector `webpage` étendu** (pagination, rendu JavaScript) — hors de question en V1.
