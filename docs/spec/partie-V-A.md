# Partie V-A — Intelligence : machinerie & tâches LLM

> **Partie V-A — Machinerie & tâches LLM.** Version durcie issue de la revue §23–§27.
> Dernière révision : 2026-09-30 (ADR-0022, #122 ; contrat du `LLMClient`, #123). Prend les Parties I, II, III et IV durcies comme acquis.
> Les §28–§30 (clustering, trend engine, sujets émergents) relèvent de la **Partie V-B** : ils ne sont pas traités ici.

> **Déjà tranché ailleurs, non repris ici** : claim atomique, deux producteurs de jobs (l'app insère, le worker exécute), contrat d'interface = schéma SQLite, modèle d'exécution asyncio avec le travail CPU hors event-loop, heartbeat, coalescence des misfires, purge (Partie II §8) ; résilience LLM, repli déterministe, JSON malformé → `dead_letter` (Partie II §9) ; table `AIJob`, index unique partiel sur les jobs actifs, idempotence par remplacement des résultats (Partie III §11.10). Cette partie ne durcit que ce qui est **propre aux tâches LLM**.

---

## Décisions tranchées dans cette revue (Partie V-A)

1. **Catalogue V1 réduit à trois `job_type`** : `enrich_article` · `resolve_event` · `discover_topics`.
2. **`classify_article` est supprimé** : il n'avait aucune colonne cible et les topics couvrent le besoin.
3. **`extract_topics`, `extract_entities` et `summarize_article` sont fusionnés** dans `enrich_article` : **un seul appel par article**, qui remplace les trois familles de résultats `method=llm` dans une seule transaction.
4. **`analyze_trend` est reporté en V2**, tout comme la « conversation ».
5. **Exécution différée + garde d'éligibilité.** Les jobs sont créés à l'insertion (Partie IV), mais exécutés après un délai (`enrich_delay` = 15 min). Au claim, une garde **déterministe, sans appel LLM**, saute les jobs devenus inutiles. C'est ce mécanisme qui porte la réduction des appels par le clustering.
6. **Articles enrichis** : les articles hors Event et les **représentants** d'Event. Les membres non représentatifs gardent leurs liaisons keyword et leur aperçu de repli.
7. **`resolve_event` = enrichissement seul** (titre + description). Il **ne touche jamais** à l'appartenance ni aux compteurs (Partie II §7.3). L'arbitrage des cas ambigus est **reporté en V2**. Pas de job sur un Event à une seule source.
8. **Nouveau statut terminal `skipped`**, avec une colonne `skip_reason` (liste fermée). Il rend le taux de réduction mesurable.
9. **Deux familles d'échecs** : les échecs d'**infrastructure** (API injoignable ou surchargée, 429, limite de dépense, erreur de configuration) **ne consomment pas de tentative** et ouvrent un **disjoncteur LLM** ; les échecs **du job** (sortie malformée, timeout) consomment une tentative. Une panne de l'API ne vide donc jamais la file vers `dead_letter`. Les requêtes refusées et les refus du modèle sont **non rejouables** (§25.4, #123).
10. **Disjoncteur LLM** à trois états (`closed` · `open` · `half_open`). Tant qu'il est ouvert, le worker **ne claime plus** de job LLM. Son état est exposé dans `SystemState.llm_gateway`.
11. **Ordre de claim** : priorité décroissante, puis **les plus récents d'abord** (`created_at DESC`). Après une panne, le quota va à l'actualité fraîche.
12. **TTL par type** : 72 h pour `enrich_article`, 7 j pour `resolve_event` et `discover_topics`. Au-delà, le job est `skipped` (`expired`). Cela borne le backlog et la rétention du contenu.
13. **Budget quotidien local optionnel** (`llm.daily_request_budget`, désactivé par défaut), avec une réserve pour les demandes de l'app.
14. **Pas de batching en V1** : un appel = un job. Le contrat reste compatible avec un batching ultérieur (« À durcir pendant la formation »).
15. **Contrat `LLMClient` fixé** : SDK `anthropic` créé avec `max_retries=0`, sortie structurée, traitement de chaque `stop_reason`, signature typée, validation Pydantic **dans le client**, **aucun retry interne**, erreurs typées (§25, #123).
16. **Validation à deux niveaux** : une structure invalide fait échouer le job ; un **élément de liste invalide est écarté seul** et compté.
17. **Entités LLM canonicalisées** : on passe d'abord par le matcher d'alias de `entities.yaml`, puis par un slug déterministe. Évite les doublons d'entités.
18. **Jobs créables par l'app : liste fermée** `enrich_article` · `resolve_event` (régénération). Le rattachement de l'historique à un topic créé est un **traitement déterministe** dérivé de `EmergingDecision`, **hors `AIJob`**.
19. **Exception documentée à la règle d'un seul écrivain** : l'app peut faire passer un job de `dead_letter` à `pending` ou à `cancelled`, et **uniquement** ces deux transitions.
20. **File dérivée des embeddings** : elle ne sélectionne que les articles dont le contenu n'est **pas purgé**, ce qui empêche tout ré-embedding automatique de l'historique. Un échec persistant est enregistré comme une **ligne `Embedding` en échec**.
21. **`processed_at` est posé par une passe unique de l'étage purge**, de façon idempotente.
22. **LLM non configuré** (`ANTHROPIC_API_KEY` absent) → le worker démarre, avec le disjoncteur ouvert en permanence (`not_configured`). Le produit tourne sans LLM, à 0 € de LLM.
23. **`discover_topics` écrit dans de nouvelles colonnes de `EmergingCandidate`**. Son résultat est **indicatif** : il n'écarte jamais un candidat automatiquement (Partie II §6.1-4).
24. **Tous les réglages LLM vivent dans `pipeline.yaml`, section `llm.*`** (§27.8), modèle compris (`llm.model`) ; seul le secret `ANTHROPIC_API_KEY` est dans `.env` (#123).

---

## 23. AI Job Queue

La mécanique de la file (table, claim atomique, deux producteurs, idempotence par remplacement) est **acquise** : Partie II §8.3 et Partie III §11.10. Cette section fixe ce que la file doit **exposer** aux tâches LLM.

### 23.1 Registre des `job_type`

Chaque `job_type` est déclaré une fois, dans un registre en code. Un `job_type` absent du registre est rejeté en `failed` (acquis).

```python
@dataclass(frozen=True)
class JobSpec:
    job_type: str
    entity_type: Literal["article", "event", "emerging_candidate"]
    uses_llm: bool                  # True pour les trois types V1
    default_priority: int
    initial_delay: timedelta        # next_attempt_at = now + delay à la création par le worker
    ttl: timedelta                  # au-delà, skipped (expired)
    max_attempts: int
    creatable_by_app: bool
    eligibility: Callable[[ReadSession, AIJob], Awaitable[SkipReason | None]]
    handler: Callable[[AIJob, LLMClient], Awaitable[None]]
```

### 23.2 Catalogue V1

| `job_type` | `entity_type` | Créé par | Quand | Priorité | Délai | TTL | App |
|---|---|---|---|---|---|---|---|
| `enrich_article` | `article` | worker | à l'insertion de chaque article `ready`, dans la transaction de la page (Partie IV §14.3) ; par le clustering, pour un nouveau représentant d'Event non enrichi (V-B §28.8) | 60 si source `relevance: always`, sinon 50 | 15 min | 72 h | oui (régénérer) |
| `resolve_event` | `event` | worker (V-B) | l'Event atteint `distinct_source_count = 2`, puis `article_count` ∈ {4, 8, 16, …} ; déclenchement par le marqueur `Event.resolve_enqueued_count` (V-B §28.10) | 50 | 10 min | 7 j | oui (régénérer) |
| `discover_topics` | `emerging_candidate` | worker (V-B) | à chaque évolution significative d'un candidat sans décision, sa création comprise (V-B §30.5) | 10 | 0 | 7 j | non |

- Un job créé par l'app a la **priorité 100** et un **délai nul**.
- Si un job actif existe déjà pour la même cible et le même type, la demande de l'app est ignorée, sans erreur (index unique partiel acquis). Le dashboard l'indique.
- Le délai de `resolve_event` sert d'anti-rebond : les articles qui arrivent peu après se rattachent avant que le job s'exécute.

### 23.3 Statut `skipped` et garde d'éligibilité

Après le claim, **avant tout appel LLM**, le worker évalue la garde du type. Si elle renvoie un motif, le job passe en `skipped`, avec `skip_reason` et `completed_at`, sans aucun appel.

| `skip_reason` | Types concernés | Condition |
|---|---|---|
| `expired` | tous | `now − created_at > ttl` |
| `article_not_ready` | `enrich_article` | l'article n'existe plus ou n'est plus `ready` (ex. devenu `duplicate`) |
| `event_member` | `enrich_article` (job créé par le worker uniquement) | l'article appartient à un Event dont il n'est pas le représentant |
| `event_not_active` | `resolve_event` | l'Event est `merged` ou `archived` |
| `event_single_source` | `resolve_event` | `distinct_source_count < 2` |
| `candidate_decided` | `discover_topics` | le candidat a une `EmergingDecision` ou a déjà été converti en topic |

- La garde `event_not_active` reste valable : un Event ne passe en `archived` qu'après 7 jours d'inactivité (V-B §28.11), durée au moins égale au TTL de `resolve_event`.
- `skipped` est **terminal**. Pour la purge, il compte comme `completed` : il débloque `processed_at` (§24.5) et il est supprimé à 30 jours.
- Une demande de régénération venue de l'app n'est **jamais** sautée pour `event_member` : l'utilisateur l'a demandée explicitement.

### 23.4 Extension du claim

La requête de claim acquise (Partie II) reçoit deux filtres et un nouvel ordre :

```sql
UPDATE aijob
SET status='processing', started_at=:now, attempts=attempts+1
WHERE id = (
  SELECT id FROM aijob
  WHERE status IN ('pending','retry')
    AND next_attempt_at <= :now
    AND job_type IN (:claimable_types)   -- vide si le disjoncteur LLM est ouvert (§24.2)
    AND priority >= :min_priority        -- 0 normalement ; 100 si le budget est en réserve (§24.3)
  ORDER BY priority DESC, created_at DESC
  LIMIT 1
)
RETURNING *;
```

- **`created_at DESC`** : à priorité égale, on traite d'abord les jobs les plus récents. Avec le TTL, cela évite de consommer le quota sur des jobs qui vont expirer.
- Tant que `:claimable_types` est vide, la boucle AI dort jusqu'au prochain changement d'état du disjoncteur ; elle ne tourne pas à vide.

### 23.5 Retry et tentatives

- **Échec du job** (§26.1) : la tentative est consommée. Backoff `30 s · 2 min · 10 min` ; `max_attempts = 3` ; au-delà → `dead_letter` (acquis).
- **Échec d'infrastructure** : la tentative est **rendue** (`attempts = attempts − 1`), le job repasse en `retry` avec `next_attempt_at` = réouverture prévue du disjoncteur.
- **Échec non rejouable** (requête refusée par l'API, ou refus du modèle ; §25.4, §26.1) → `failed`.
- `completed_at` est renseigné à toute transition vers `completed`, `failed`, `cancelled` ou `skipped`, et reste `NULL` pour `dead_letter` (Partie III §11.10).

### 23.6 Actions de l'app sur les jobs

- **Création** : uniquement les types marqués `creatable_by_app` (§23.2), avec `created_by='app'`.
- **Relance d'un `dead_letter`** : `UPDATE` de `dead_letter` vers `pending`, avec `attempts = 0` et `next_attempt_at = now`.
- **Abandon d'un `dead_letter`** : `UPDATE` de `dead_letter` vers `cancelled`, qui renseigne `completed_at` (règle de la Partie III §11.10).
- Ces deux transitions sont la **seule exception** à la règle « statuts écrits par le worker » (Partie II §8.3). Elles sont exécutées dans une transaction conditionnelle (`WHERE status='dead_letter'`), donc sans course avec le worker, qui ne touche jamais un `dead_letter`.

## 24. Worker & scheduler

Processus unique, event-loop, concurrence bornée, requalification des `processing` au démarrage, misfires : **acquis** (Partie II §8.4 et §9.2). Cette section ajoute les composants propres aux tâches LLM.

### 24.1 Boucle AI

```
tant que le worker tourne :
    attendre un slot (sémaphore llm.max_concurrent = 2)
    job ← claim (§23.4)            # rien → dormir (tick 5 s ou réveil sur changement d'état)
    motif ← garde d'éligibilité    # lecture seule, sans LLM
    si motif : skipped(motif) ; continuer
    résultat ← handler(job)        # appel LLMClient hors transaction
    écriture du résultat + completed, dans UNE transaction BEGIN IMMEDIATE
    en cas d'exception typée → §26.1
```

- **Tâche permanente supervisée** (Partie VII §36.6) : si la boucle AI meurt sur une exception non gérée, le worker s'arrête en erreur et Docker le relance.
- **Aucun appel réseau dans une transaction d'écriture** : l'appel LLM est terminé et validé avant l'ouverture de la transaction (même règle que Partie IV §14.2).
- Le passage à `completed` se fait **dans la transaction qui écrit le résultat**. Si le worker meurt entre les deux, le job reste `processing` : il est requalifié en `retry` au démarrage et rejoué, et le remplacement des résultats rend ce rejeu sans effet de bord (acquis).

### 24.2 Disjoncteur LLM

L'état vit en mémoire du worker (processus unique). Il est recopié à chaque transition dans `SystemState.llm_gateway` : `{state, since, reason, open_until}`.

| Transition | Déclencheur |
|---|---|
| `closed → open` | `LLMUnavailable`, `LLMRateLimited`, `LLMSpendLimit`, `LLMConfigError`, ou **3 `LLMTimeout` consécutifs** |
| `open → half_open` | cause `unavailable` : une sonde `health()` réussit (sonde toutes les 60 s) · cause `rate_limited` : `open_until` est atteint · cause `config` : sonde toutes les 5 min · cause `spend_limit` : renvoyée au budget (§24.3, #125) |
| `half_open → closed` | le **job test** (un seul job claimé) aboutit |
| `half_open → open` | le job test subit à nouveau un échec d'infrastructure |
| — (permanent) | `ANTHROPIC_API_KEY` absent : état `open`, `reason = not_configured`, aucune sonde |

- **`open_until` après un 429** (`LLMRateLimited`) : valeur de `retry-after` plafonnée à `llm.breaker.retry_after_cap` (6 h). Sans `retry-after` : 60 s, doublé à chaque réouverture en échec, dans la même limite.
- **Pourquoi un job test** : une sonde `health()` ne détecte ni une limite de débit ni une limite de dépense. Seul un vrai appel le peut.
- **`LLMSpendLimit`** : jamais `failed`, aucune tentative consommée ; la reprise et le plafond interne relèvent du budget (§24.3, #125).
- Les jobs déjà en cours au moment de l'ouverture subissent chacun leur propre échec d'infrastructure ; leur tentative est rendue.

### 24.3 Budget quotidien

> **À réviser (ADR-0022, #125).** L'ADR-0022 remplace ce budget quotidien en requêtes par un **budget mensuel plafonné**
> en coût réel : plafond configuré en USD (défaut ≈ 15 €), suivi en tokens et en coût, plafond dur appliqué par le
> worker, remise à zéro le 1er du mois (UTC) ; cadre en Partie I §4.3 et VII §45.1. Le contrat ci-dessous reste en
> vigueur tant que #125 ne l'a pas réécrit ; il ne doit pas être implémenté en l'état.

- Compteur `SystemState.llm_usage` = `{day, requests}` (jour UTC). Il est incrémenté pour chaque appel ayant reçu une réponse du gateway (2xx ou sortie malformée) ; un 429 ou une erreur réseau ne compte pas.
- `llm.daily_request_budget` : `null` (défaut) = pas de limite locale ; les quotas du gateway s'appliquent via les 429.
- Budget défini, avec `used ≥ budget − llm.app_reserve` → `:min_priority = 100` : seuls les jobs de l'app passent.
- `used ≥ budget` → plus aucun claim LLM jusqu'à 00:00 UTC.
- État exposé dans `/health` et le monitoring.

### 24.4 File dérivée des embeddings

Pas d'`AIJob` (Partie IV, décision 21). Le composant est distinct de la boucle AI et **ne dépend pas du disjoncteur LLM** : c'est une couche cœur (Partie II §6.1-3). Comme la boucle AI, c'est une **tâche permanente supervisée** : sa mort arrête le worker (Partie VII §36.6). Seul le **mécanisme de sélection** est fixé ici ; l'usage (similarité, clustering) relève de V-B.

**Sélection** :

```sql
SELECT a.id FROM article a
LEFT JOIN embedding e ON e.article_id = a.id AND e.model = :model
WHERE a.status = 'ready'
  AND a.content_purged_at IS NULL
  AND e.article_id IS NULL
ORDER BY a.discovered_at ASC
LIMIT :batch_size;          -- embeddings.batch_size = 32
```

- `content_purged_at IS NULL` empêche un changement de modèle de relancer automatiquement l'embedding de tout l'historique (le ré-embedding reste manuel, Partie III §12.5).
- **Réveil** : un `asyncio.Event` signalé après la validation de chaque page insérée, et un tick de 60 s.
- **Calcul hors event-loop** (acquis).

**Échecs** :

- Un lot échoue → ses articles sont rejoués **un par un**.
  - Tous échouent : le **moteur** est considéré en panne. `SystemState.embeddings` passe à `down`, les ticks suivants font un backoff (60 s, doublé, plafonné à 30 min), et **aucun article n'est marqué**.
  - Seuls certains échouent : un compteur d'échecs en mémoire, par article, est incrémenté.
- Un article qui atteint `embeddings.max_failures` (3) → une ligne `Embedding` est écrite avec `vector = NULL` et `error`. Elle compte comme **traitée** pour `processed_at` et elle est **exclue** de la similarité.
- Le compteur en mémoire est remis à zéro au redémarrage. Un article à problème peut donc coûter 3 tentatives de plus après chaque redémarrage, ce qui est acceptable.

### 24.5 Passe `processed_at`

Exécutée par l'étage purge (Partie II §8.5), avant la purge proprement dite. C'est le **seul** endroit où `processed_at` est posé.

```sql
UPDATE article SET processed_at = :now
WHERE status = 'ready' AND processed_at IS NULL
  AND EXISTS (SELECT 1 FROM embedding e
              WHERE e.article_id = article.id AND e.model = :model)
  AND NOT EXISTS (SELECT 1 FROM aijob j
                  WHERE j.entity_type = 'article' AND j.entity_id = article.id
                    AND j.status IN ('pending','processing','retry','dead_letter'));
```

- Seuls les jobs **ciblant l'article** comptent : `resolve_event` ne lit que les résumés, jamais `content`, et ne retarde donc pas la purge.
- Rétention maximale effective du contenu d'un article `ready` ≈ TTL de `enrich_article` + délai de grâce, soit **4 jours**, hors `dead_letter` et hors panne du moteur d'embeddings.
- Une demande de régénération faite après la purge travaille sur une entrée dégradée (§27.2).

### 24.6 Rattachement de l'historique à un topic créé

Ce traitement est **déterministe** et hors `AIJob` (décision 18). Il est déclenché par la lecture des `EmergingDecision` de type `create_topic` que le worker n'a pas encore traitées (coordination par la base, Partie II §8.3).

1. Le worker crée le `Topic` avec `origin = user`, selon la Partie V-B §30.8 : `name` = `llm_label`, ou à défaut `label` ; slug dérivé de `name`, suffixé `-2`, `-3`… en cas de collision ; mots-clés = `suggested_keywords` ∪ {terme de base}, où le terme de base est `key` pour un `ngram` et `canonical_name` (`owner/repo`) pour un `repository`.
2. Il renseigne `EmergingCandidate.topic_id`.
3. Il re-score, **pour ce seul topic**, les articles `ready` des `topic_backfill.window` derniers jours (30 j) sur **titre + URL**, plus le **résumé seulement si `summary_origin = fallback`** (contenu purgé ; V-B §30.8) : une liaison keyword ne dépend jamais d'un texte produit par le LLM. Il écrit des `ArticleTopic` `method=keyword`, par lots bornés.

Ce n'est pas le re-scoring rétroactif reporté par la Partie IV : ce dernier porte sur la modification des mots-clés de topics existants. La logique détaillée du cycle de vie des candidats relève de V-B.

**Taxonomie** : `origin = discovered` n'est produit par **aucun** mécanisme en V1 ; un topic n'est créé que sur action de l'utilisateur (`origin = user`).

## 25. API Claude & LLMClient

Chaîne `AI Tech Radar → LLMClient → SDK anthropic (AsyncAnthropic) → Messages API` (ADR-0022). Le SDK n'est importé que
par le `LLMClient` (T-LLM-19).

**Sources.** Chaque règle issue de l'API cite sa page de documentation, relative à `https://platform.claude.com/docs/en/`
et consultée le 2026-09-30, ou le code source du SDK `anthropic` 1.9.0 (dernière version publiée, le 2026-09-28 ; la
version épinglée est fixée au Sprint 6 et ces règles y sont revérifiées). La mention **à vérifier** marque ce qu'aucune
page officielle ne confirme.

### 25.1 Configuration

| Réglage | Où | Rôle |
|---|---|---|
| `ANTHROPIC_API_KEY` | `.env`, worker seul (Partie VII §36.7) | clé de l'API, jamais journalisée. **Absente → LLM désactivé** : le worker démarre, avec le disjoncteur en `open / not_configured` |
| `llm.model` | `pipeline.yaml` (§27.8) | identifiant de modèle **épinglé**, unique pour toutes les tâches en V1. Aucun défaut ; aucun identifiant de modèle en dur dans le code |
| `ANTHROPIC_BASE_URL` | environnement de test seulement | adresse du double de l'API ; acceptée seulement si `APP_ENV=test`, sinon le worker refuse de démarrer (T-CFG-12, §26.3) |

- **Clé présente, `llm.model` absent** : le worker démarre ; le disjoncteur s'ouvre avec `reason = config` et la
  condition `llm_config_error` est levée (Partie VII §39.5). Il n'y a pas de refus de démarrer : le produit tourne sans
  LLM.
- **Identifiant épinglé** : un identifiant de modèle désigne une version figée. Depuis la génération 4.6, un identifiant
  sans date (`claude-sonnet-4-6`) est lui-même un snapshot ; avant, un identifiant sans date (`claude-sonnet-4-5`) est
  un alias vers le dernier snapshot daté (doc : `about-claude/models/model-ids-and-versions`). Un motif ne peut donc pas
  distinguer un alias : l'interdiction des alias flottants est une **règle de revue**, consignée dans `docs/llm.md`
  (Partie IX §55.4).
- **Sortie structurée sur le modèle épinglé** : **à vérifier** au choix du modèle (Sprint 6, M6). La page
  `build-with-claude/structured-outputs` liste les modèles compatibles, et la liste des modèles déclare la capacité
  (`capabilities.structured_outputs`, doc : `api/models/list`).
- **Variables lues d'office par le SDK** : `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN`, `ANTHROPIC_BASE_URL`,
  `ANTHROPIC_CUSTOM_HEADERS`, `ANTHROPIC_PROFILE` et les variables de fédération (source SDK 1.9.0, `_client.py`). Le
  `LLMClient` passe la clé et l'adresse **explicitement**, et Compose ne transmet au worker que des variables listées
  une à une (Partie VII §36.5) : aucune autre variable `ANTHROPIC_*` que la clé n'atteint le worker (volet de T-SEC-08,
  §26.3).

Les autres réglages (timeouts, `max_tokens` par tâche) sont dans `pipeline.yaml` (§27.8). `temperature` n'est jamais
envoyée (§25.2).

### 25.2 Client et interface

**Construction**, une fois, au démarrage du worker, si la clé est présente :

```python
AsyncAnthropic(
    api_key=...,                     # ANTHROPIC_API_KEY, passée explicitement
    base_url=...,                    # https://api.anthropic.com ; ANTHROPIC_BASE_URL si APP_ENV=test
    max_retries=0,
    timeout=httpx2.Timeout(...),     # llm.connect_timeout, llm.read_timeout
    http_client=DefaultAsyncHttpxClient(follow_redirects=False),
)
```

- **`max_retries=0`** (ADR-0022). Par défaut, le SDK rejoue deux fois, avec backoff, les erreurs de connexion, 408,
  409, 429 et ≥ 500, en respectant `retry-after` (doc : `api/errors` et `cli-sdks-libraries/sdks/python` ; source SDK :
  `DEFAULT_MAX_RETRIES = 2`). Ces reprises cachées multiplieraient les appels facturés, consommeraient la limite de
  débit, masqueraient les 429 au disjoncteur et contrediraient la règle « un appel = une requête ». La reprise
  appartient à la file et au disjoncteur (§23.5, §24.2, §26) : T-LLM-21 (§26.3).
- **Aucune redirection suivie.** Les clients HTTP par défaut du SDK suivent les redirections (`follow_redirects=True`,
  source SDK 1.9.0, `_base_client.py`, `_DefaultAsyncHttpxClient`) ; aucune page de la documentation n'en parle
  (**à vérifier**). Le `LLMClient` fournit donc son propre client, construit avec `follow_redirects=False` ; une
  réponse de redirection est une `LLMConfigError` (§25.4, T-LLM-20).
- **`httpx2`** : le SDK 1.9.0 dépend de `httpx2`, et non de `httpx` ; le client fourni doit être un client `httpx2`
  (doc : `cli-sdks-libraries/sdks/python` ; source SDK). Le `HttpClient` des collectors reste sur httpx (Partie IV
  §21.1) : deux piles HTTP coexistent dans l'image (Partie VII §35).
- **Hors du `HttpClient`** : pas de limiteur par hôte, pas de User-Agent de collecte, pas de garde anti-SSRF (Partie IV
  §21.1) ; destination fixe.
- **Timeouts** : connexion 5 s, lecture 60 s (`llm.connect_timeout`, `llm.read_timeout`). Le défaut du SDK (10 min)
  n'est pas utilisé.

**Interface** :

```python
T = TypeVar("T", bound=BaseModel)

@dataclass(frozen=True)
class LLMResult(Generic[T]):
    value: T                                    # objet validé
    dropped_items: int                          # éléments de listes écartés à la validation
    model: str                                  # modèle rapporté par la réponse
    stop_reason: str
    input_tokens: int
    output_tokens: int
    cache_creation_input_tokens: int | None     # tels que renvoyés, non exploités (§25.6)
    cache_read_input_tokens: int | None
    request_id: str | None
    latency_ms: int

class LLMHealth(BaseModel):
    reachable: bool
    model_listed: bool
    detail: str | None

class LLMClient:
    async def generate(
        self, *,
        task: str,                    # nom de la tâche, pour logs et métriques
        system: str,
        user: str,
        response_model: type[T],
        max_output_tokens: int,
    ) -> LLMResult[T]: ...

    async def health(self) -> LLMHealth: ...
```

- **`generate`** : `POST /v1/messages`, avec `model = llm.model`, `system` au premier niveau, un seul message `user`,
  `max_tokens = max_output_tokens` et la sortie structurée (§25.3) (doc : `api/messages`).
  - **Jamais `temperature`** : les modèles publiés après Claude Opus 4.6 refusent toute valeur autre que 1.0 par une
    400 (doc : `api/messages`).
  - Ni `stop_sequences`, ni outils, ni `thinking`, ni `effort` : les défauts de l'API s'appliquent (« À durcir pendant
    la formation »). Le thinking compte dans `max_tokens` (doc : `build-with-claude/effort`) : les plafonds du §27.8
    sont à recaler au choix du modèle (**à vérifier**, M6).
- **`health`** : `GET /v1/models`, timeout de 5 s, en suivant la pagination (`limit` jusqu'à 1000, `has_more`) (doc :
  `api/models/list`). Réussite = API joignable **et** `llm.model` présent dans la liste ; modèle absent →
  `LLMConfigError`, donc `llm_config_error`. Facturation ou consommation de quota de cet appel : **à vérifier**, aucune
  page ne le précise.

### 25.3 Sortie structurée, `stop_reason` et validation

**Sortie structurée : structured outputs** (décision du 2026-09-30). Chaque tâche envoie le schéma JSON de son
`response_model` dans `output_config.format = {"type": "json_schema", "schema": …}`. La fonction est disponible sans
en-tête bêta ; l'ancien paramètre `output_format` est déprécié (doc : `build-with-claude/structured-outputs`).

- **Garantie** : le décodage contraint produit un JSON conforme au schéma, sauf en cas de `refusal` ou de `max_tokens`
  (même page).
- **Limites** (même page) : ni `minLength` / `maxLength`, ni `minimum` / `maximum` ; `additionalProperties` à `false` ;
  casse des valeurs d'enum non garantie ; un schéma trop complexe est refusé par une 400. Le schéma envoyé est donc une
  version compatible du `response_model`, sans bornes de longueur.
- **La validation Pydantic reste la seule autorité** : `SoftStr` et `TolerantList` sont conservés.

**Option écartée : tool use forcé.** `tool_choice` `any` ou `tool` renvoie une 400 sur Claude Opus 5.5, Sonnet 5.5,
Fable 5.1 et Mythos 5.1 (doc : `api/errors`, « Forced tool use not supported » ; `agents-and-tools/tool-use/define-tools`).
L'alternative `auto` avec `strict` ne garantit pas l'appel de l'outil, et le tool use forcé est incompatible avec le
thinking manuel. L'option est écartée : elle ne fonctionne pas avec les modèles actuels.

**`stop_reason`** : les sept valeurs documentées (doc : `build-with-claude/handling-stop-reasons` ; `api/messages`).
Aucune sortie n'est écrite en base hors `end_turn` (T-LLM-22, §26.3).

| `stop_reason` | Traitement |
|---|---|
| `end_turn` | validation (étapes ci-dessous) |
| `max_tokens` | sortie tronquée → `LLMMalformed` |
| `stop_sequence` | inattendue (aucune séquence envoyée) → `LLMMalformed` |
| `tool_use` | inattendue (aucun outil envoyé) → `LLMMalformed` |
| `pause_turn` | inattendue (aucun outil serveur) → `LLMMalformed` |
| `refusal` | refus du modèle (réponse HTTP 200, facturée ; `stop_details.category`) → `LLMRefused` |
| `model_context_window_exceeded` | entrée trop longue → `LLMBadRequest` |
| valeur inconnue | → `LLMMalformed` |

**Validation**, réalisée **dans `LLMClient`** ; le handler reçoit un objet validé ou une exception typée :

1. Seuls les blocs `text` de `content` sont lus ; les blocs `thinking` éventuels sont ignorés. Aucun bloc `text`, ou
   texte vide → `LLMMalformed`.
2. Analyse JSON du texte, sans réparation ni extraction heuristique. JSON invalide → `LLMMalformed`.
3. Validation par `response_model`.
4. **Types utilitaires** fournis avec le client :
   - `TolerantList[X]` : chaque élément est validé séparément ; un élément invalide est écarté et compté dans
     `dropped_items`, sans faire échouer la réponse ;
   - `SoftStr(max, min)` : texte trimé ; au-delà de `max`, coupé sur une frontière de mot et suivi de `…` ; sous `min`,
     erreur de validation.
5. Toute autre erreur de validation → `LLMMalformed`. **Aucune écriture** n'a lieu avant la fin de la validation
   (acquis).

### 25.4 Erreurs typées

Sources : doc `api/errors` et `api/rate-limits` ; source SDK 1.9.0, `_exceptions.py`.

| Exception | Cause : statut HTTP, `error.type`, exception du SDK | Famille |
|---|---|---|
| `LLMUnavailable` | `APIConnectionError` (connexion, DNS, timeout de connexion) · 500 `api_error`, 503, 504 `timeout_error` (`InternalServerError`) · 529 `overloaded_error` (`OverloadedError`) · 409 `conflict_error` (`ConflictError`) · tout autre ≥ 500 | infrastructure |
| `LLMRateLimited(retry_after)` | 429 `rate_limit_error` (`RateLimitError`) ; `retry-after` en secondes | infrastructure |
| `LLMSpendLimit` | 429 avec `error.details.error_code = enforced_spend_limit_reached` (plafond de dépense du palier, sans `retry-after`) · 400 `invalid_request_error` dont le message commence par « You have reached your specified API usage limits » ou « You have reached your specified workspace API usage limits » (limite fixée dans la Console) (doc : `api/rate-limits`) | infrastructure |
| `LLMConfigError` | 401 `authentication_error` · 403 `permission_error` · 404 `not_found_error` · 402 `billing_error` (le SDK lève un `APIStatusError` générique) · réponse de redirection (§25.2) · `llm.model` absent de la configuration ou de la liste des modèles | infrastructure |
| `LLMTimeout` | timeout de lecture | job |
| `LLMMalformed` | §25.3 : JSON absent ou invalide, validation échouée, sortie vide, tronquée ou inattendue | job |
| `LLMRefused` | `stop_reason = refusal` | non rejouable |
| `LLMBadRequest` | autre 400 `invalid_request_error` · 413 `request_too_large` · 422 (`UnprocessableEntityError`, non documenté par l'API) · `model_context_window_exceeded` · tout autre 4xx | non rejouable |

- **Crédit prépayé épuisé** : statut et type **à vérifier** ; aucune page officielle ne les donne. Tant que ce n'est
  pas vérifié, un tel cas pourrait être classé `LLMBadRequest`, donc `failed`.
- **Timeout de connexion ou de lecture** : `APITimeoutError` ne les distingue pas par son type ; la distinction par la
  cause `httpx2` sous-jacente est **à vérifier**.
- **`request_id`** : en-tête `request-id` de chaque réponse, champ `request_id` du corps d'erreur (doc : `api/errors`) ;
  journalisé avec l'erreur.
- **En-têtes `anthropic-ratelimit-*`** (`limit`, `remaining`, `reset` au format RFC 3339) : journalisés sur un 429,
  sans effet sur l'état ; seul `retry-after` fixe `open_until` (doc : `api/rate-limits`).
- Les valeurs d'`error.type` peuvent s'enrichir avec le temps (doc : `api/errors`) : le classement se fait d'abord sur
  le statut HTTP.

Le traitement de chaque famille est décrit au §26.1.

### 25.5 Prompts

- Un module par tâche (`app/llm/prompts/<task>.py`). Chacun expose la construction de `system` et `user`, le `response_model` et une constante `PROMPT_VERSION`, présente dans les logs.
- `system` est envoyé au premier niveau de la requête ; le message `user` est unique (§25.2).
- Le contenu des articles est une **donnée non fiable**. Il est placé dans le message `user`, entre délimiteurs explicites. Le prompt système indique qu'il ne contient aucune instruction à suivre.
- **Protection contre l'injection** : une sortie bornée par le schéma, des topics choisis dans une liste fermée, des longueurs plafonnées, une sortie jamais exécutée et **toujours échappée** à l'affichage.

### 25.6 Observabilité

- **Log par appel** : `task`, `job_id`, `model`, `stop_reason`, `input_tokens`, `output_tokens`, `request_id`, latence,
  classe d'erreur, `PROMPT_VERSION`. Jamais le prompt ni la réponse au niveau `info`. Au niveau `debug`, les 200
  premiers caractères d'une réponse malformée.
- **Champs de cache** : `cache_creation_input_tokens` et `cache_read_input_tokens` sont journalisés tels que l'`usage`
  de la réponse les renvoie, éventuellement `null` (doc : `api/messages`). Ils ne sont pas exploités : aucun code ni
  réglage de cache (Partie VIII §47.5, « rien par anticipation »).
- **Métriques** : appels par tâche et par issue · `stop_reason` par tâche · tokens d'entrée et de sortie par tâche ·
  latence · `dropped_items` · jobs `skipped` par motif · backlog par type et par statut · état du disjoncteur ·
  consommation du budget (§24.3, #125).

## 26. Résilience LLM & retry

Principe et tableau de pannes : **acquis** (Partie II §9.1). Cette section précise la **distinction des familles d'échec** sans laquelle la reprise automatique promise par §9.1 serait fausse : sans elle, les tentatives seraient épuisées en quelques minutes de panne.

### 26.1 Traitement par famille

| Famille | Tentative | Statut du job | Disjoncteur |
|---|---|---|---|
| **Infrastructure** (`LLMUnavailable`, `LLMRateLimited`, `LLMSpendLimit`, `LLMConfigError`) | **rendue** | `retry`, `next_attempt_at` = réouverture prévue ; **jamais** `failed` | ouvert (§24.2) ; `LLMConfigError` déclenche en plus une **alerte de configuration** |
| **Job** (`LLMMalformed`, `LLMTimeout`) | consommée | `retry` avec backoff §23.5, puis `dead_letter` | inchangé, sauf 3 `LLMTimeout` consécutifs → ouvert (cause `unavailable`) |
| **Non rejouable** (`LLMBadRequest`, `LLMRefused`) | — | `failed` | inchangé |
| **Exception inattendue** du handler | consommée | comme un échec du job | inchangé |

Dans tous les cas, `last_error` reçoit la classe d'erreur et un message sans secret.

### 26.2 Garanties

- **API indisponible pendant N heures** : aucun job ne passe en `dead_letter` du fait de la panne. Au retour, les jobs reprennent, les plus récents d'abord, et les jobs expirés sont `skipped`.
- **Limite de débit atteinte (429)** : le disjoncteur reste ouvert jusqu'au `retry-after` (plafonné), puis un job test vérifie que la limite est levée. Aucune rafale d'appels voués au 429.
- **Limite de dépense atteinte** (`LLMSpendLimit`) : aucun job ne passe en `failed` ni en `dead_letter` du fait de la limite ; la reprise relève du budget (§24.3, #125).
- **Aucune écriture partielle** : validation complète, puis une transaction unique.

### 26.3 Scénarios de test obligatoires

```
API down (connexion refusée ou 529) → disjoncteur ouvert → aucun claim LLM
  → attempts inchangés → API up → sonde OK → job test OK → reprise, plus récents d'abord

429 avec retry-after: 120 → open_until = +120 s → half_open → job test → closed

429 persistant sans retry-after → réouvertures en 60 s, 120 s, 240 s… plafonnées à 6 h

réponse non-JSON ×3 → dead_letter ; purge du contenu bloquée ; relance app → pending

élément d'entité invalide dans une réponse valide → écarté, dropped_items = 1, job completed

3 timeouts consécutifs → disjoncteur ouvert

ANTHROPIC_API_KEY absent → worker démarre, jobs créés, restent pending, /health = llm not_configured

kill -9 après l'appel LLM, avant la transaction → retry → rejoué → état final identique
```

**Tests à créer au Sprint 6** (décision du 2026-09-30 : aucune ligne de catalogue sans test ; ils entrent au catalogue de
la Partie VIII §50.5 avec leurs tests, et figurent au contenu du Sprint 6, VIII §47.2) :

- **T-LLM-21** : client créé avec `max_retries=0` ; un 429, un 529 ou un 5xx donnent **une seule** requête dans le
  journal du double (§25.2).
- **T-LLM-22** : chaque `stop_reason` documenté reçoit son traitement (§25.3) ; aucune sortie écrite en base hors
  `end_turn` ; `refusal` → `failed`.
- **T-CFG-12** : `ANTHROPIC_BASE_URL` renseignée avec un `APP_ENV` autre que `test` → le worker refuse de démarrer
  (§25.1, sur le modèle de T-CFG-09).
- **Volet de T-SEC-08** (politique Compose) : aucune autre variable `ANTHROPIC_*` que la clé n'atteint le worker
  (§25.1).
- **Volet de T-SEC-02** : la clé `x-api-key` est masquée par le processeur de logs (Partie VII §42.4).

## 27. LLM Tasks & réduction des appels

### 27.1 Règles communes aux tâches

- **Entrée** : construite par le handler à partir de la base, en lecture seule, avant l'appel.
- **Langue** : tous les textes produits (résumés, titres, descriptions, labels) sont dans `llm.summary_language` (`fr`), quelle que soit la langue de la source.
- **Écriture** : une transaction `BEGIN IMMEDIATE` par job, qui écrit le résultat **et** le statut `completed`. Chaque job **remplace intégralement** ses propres résultats pour sa cible. Il ne touche jamais aux lignes `method=keyword` ni aux champs déterministes.
- **Repli** : si le job n'aboutit pas (LLM absent, `skipped`, `failed`, `dead_letter`), la valeur déterministe reste en place. Rien dans la couche cœur n'attend le résultat.

### 27.2 `enrich_article`

**Entrée** (message `user`) :

- `title`, `language`, nom et type de la source ;
- `content` tronqué à `llm.input_max_chars` (6 000). S'il est purgé, cas d'une régénération tardive : `title` + résumé courant ;
- la liste des topics **activés** : `slug`, `name`, `description`. Si la taxonomie dépasse `llm.max_topics_in_prompt` (80), seuls les topics racines et ceux dont `score_t > 0` pour cet article sont envoyés.

**Sortie** :

```python
class TopicAssignment(BaseModel):
    slug: str
    confidence: float = Field(ge=0, le=1)

class EntityMention(BaseModel):
    type: Literal["company", "product", "person", "project",
                  "technology", "model", "repository"]
    name: SoftStr(max=80, min=1)
    confidence: float = Field(ge=0, le=1)

class EnrichArticleOutput(BaseModel):
    summary: SoftStr(max=500, min=40)       # 2 à 3 phrases factuelles, sans « Cet article… »
    topics: TolerantList[TopicAssignment]    # au plus 5 retenus
    entities: TolerantList[EntityMention]    # au plus 10 retenues
```

**Post-traitement déterministe**, avant l'écriture :

- **Topics** : on écarte les `slug` inconnus ou désactivés (comptés dans `dropped_items`) et ceux dont `confidence < llm.topic_min_confidence` (0,5). On dédoublonne, puis on garde les 5 meilleures confiances.
- **Entités** : on écarte celles sous `llm.entity_min_confidence` (0,5), puis on garde les 10 meilleures. Chacune est résolue ainsi :
  1. `name` passe dans le **matcher d'alias** de `entities.yaml` (normalisation Partie IV §20.2). S'il correspond, l'entité existante est rattachée ;
  2. sinon, `canonical_name = slug(name)` : `norm`, puis espaces et `_` remplacés par `-` et tirets multiples fusionnés. Pour `repository`, c'est `owner/repo` en minuscules ;
  3. si `(type, canonical_name)` existe déjà, quelle que soit son origine, elle est réutilisée ; sinon, elle est créée avec `origin = llm`.

**Écriture** (une transaction) :

1. `DELETE FROM article_topic WHERE article_id = :id AND method = 'llm'`, puis insertion des topics retenus (`method = 'llm'`, `confidence`) ;
2. idem pour `article_entity`, après l'upsert des `Entity` ;
3. `UPDATE article SET summary = :s, summary_origin = 'llm', summary_lang = :lang` ;
4. `aijob` → `completed`.

L'index `article_fts` est mis à jour par son trigger `UPDATE` (Partie III §11.14). **Aucune ré-indexation manuelle.**

**Garde** : `article_not_ready`, `event_member` (jobs du worker seulement), `expired`.

### 27.3 `resolve_event`

**Entrée** : au plus `llm.event_max_articles` (8) articles `ready` de l'Event, choisis dans cet ordre :

1. le représentant ;
2. un article par source distincte ;
3. les plus récents.

Pour chacun : `title`, `summary` (llm ou repli), nom et type de la source, `published_at`. **Jamais `content`.**

**Sortie** :

```python
class ResolveEventOutput(BaseModel):
    title: SoftStr(max=120, min=10)
    description: SoftStr(max=600, min=40)
```

**Écriture** : `UPDATE event SET title, description, title_origin = 'llm'`, puis `aijob → completed`. **Ne modifie jamais** `article_count`, `distinct_source_count`, `distinct_channel_count`, l'appartenance des articles ni le statut de l'Event (Partie II §7.3).

**Repli** : `title` reste le titre du représentant, ou le dernier titre LLM si l'Event a déjà été résolu une fois. `description` reste `NULL` ou sa dernière valeur.

**Garde** : `event_not_active`, `event_single_source`, `expired`.

### 27.4 `discover_topics`

Cible : un `EmergingCandidate`. **Quand** le créer et **quels articles** lui fournir relèvent de V-B ; seul le contrat est fixé ici.

**Entrée** :

- `key` et `label` déterministes ;
- `evidence` (mentions, sources, écosystèmes, croissance) ;
- titres et résumés d'au plus 8 articles portant le terme, choisis par V-B ;
- la liste des topics activés (`slug`, `name`, `description`).

**Sortie** :

```python
class DiscoverTopicOutput(BaseModel):
    label: SoftStr(max=60, min=2)
    description: SoftStr(max=400, min=20)
    covered_by: str | None                  # slug existant ; slug inconnu → None
    keywords: TolerantList[SoftStr(max=60, min=2)]   # au plus 8 retenus
```

**Écriture** : `EmergingCandidate.llm_label`, `llm_description`, `covered_by_topic_id`, `suggested_keywords`, `assessed_at` sont **remplacés** ; puis `aijob → completed`. `label`, `key` et `evidence`, déterministes, ne sont jamais touchés.

**Statut du résultat** : il est **indicatif**. `covered_by` est affiché comme suggestion ; il ne retire jamais un candidat automatiquement (Partie II §6.1-4). Les mots-clés suggérés servent au « Create topic » (§24.6).

**Repli** : le dashboard affiche le `label` déterministe et les preuves. Le recouvrement est inconnu.

**Garde** : `candidate_decided`, `expired`.

### 27.5 Réduction des appels

```
N items collectés
 → too_old · doublons exacts                   non insérés, 0 job
 → relevance filter → filtered                  0 job
 → ready                                        1 enrich_article chacun, exécuté à +15 min
      au claim :  devenu duplicate               → skipped
                  membre non représentatif       → skipped
                  plus vieux que 72 h            → skipped
 → Events ≥ 2 sources                           resolve_event à 2 sources, puis à 4, 8, 16… articles
 → candidats émergents                          discover_topics (création + évolution significative)
```

Avant tout appel LLM, le code déterministe a déjà produit : le statut (`ready`/`filtered`), les topics et entités keyword, le résumé de repli, l'appartenance à un Event, la hotness. **Le LLM n'est jamais appelé pour une information que le cœur possède déjà.**

**Ordre de grandeur** (illustration, à remplacer par la mesure) :

- Appels par jour ≈ `R × (1 − m) + E × ⌈log₂ taille⌉ + C`, avec R articles `ready`, m la part de membres non représentatifs, E les Events multi-sources et C les candidats émergents.
- Pour R = 300 et m = 30 % : environ **260 appels par jour**, contre environ 1 200 avec quatre jobs par article.

### 27.6 Aperçu de repli et aperçu enrichi

| État | `summary_origin` | Origine |
|---|---|---|
| **Repli** | `fallback` | posé à l'insertion (Partie IV §14.5, 300 caractères) |
| **Enrichi** | `llm` | `enrich_article` `completed` |

- **Passage `fallback → llm`** : uniquement par `enrich_article`. Il a lieu automatiquement quand le LLM revient, puisque les jobs attendent en `pending` ou `retry` sans perdre de tentative (§26). **Aucun mécanisme de rattrapage supplémentaire.**
- **Restent en repli**, de façon assumée : les articles `filtered`, les membres non représentatifs d'un Event, les jobs `skipped`, `failed` ou `dead_letter`, et tous les articles si le LLM n'est pas configuré.
- **Régénération** : à la demande de l'app (`enrich_article`, priorité 100). Elle remplace le résumé et les liaisons `llm`.
- **Recherche** : le trigger FTS suit chaque changement de résumé ; le résumé enrichi devient cherchable sans action supplémentaire.

### 27.7 Événements : titre de repli et titre enrichi

Même logique, portée par `Event.title_origin` : `fallback` à la création (V-B), `llm` après `resolve_event`. Le titre enrichi est actualisé aux seuils de taille (§23.2), jamais à chaque rattachement.

### 27.8 Réglages `llm.*` et `embeddings.*` dans `pipeline.yaml`

| Clé | Défaut | Section |
|---|---|---|
| `llm.model` | aucun (identifiant épinglé requis pour activer le LLM) | §25.1 |
| `llm.max_concurrent` | 2 | §24.1 |
| `llm.connect_timeout` · `read_timeout` | 5 s · 60 s | §25.2 |
| `llm.summary_language` | `fr` | §27.1 |
| `llm.input_max_chars` | 6 000 | §27.2 |
| `llm.max_topics_in_prompt` | 80 | §27.2 |
| `llm.max_output_tokens.enrich_article` · `resolve_event` · `discover_topics` | 800 · 400 · 500 | §27 |
| `llm.delay.enrich_article` · `resolve_event` | 15 min · 10 min | §23.2 |
| `llm.ttl.enrich_article` · `resolve_event` · `discover_topics` | 72 h · 7 j · 7 j | §23.2 |
| `llm.max_attempts` | 3 | §23.5 |
| `llm.retry_backoff` | `[30s, 2m, 10m]` | §23.5 |
| `llm.topic_min_confidence` · `entity_min_confidence` | 0,5 · 0,5 | §27.2 |
| `llm.max_topics` · `max_entities` | 5 · 10 | §27.2 |
| `llm.event_max_articles` | 8 | §27.3 |
| `llm.breaker.probe_interval` · `config_probe_interval` | 60 s · 5 min | §24.2 |
| `llm.breaker.retry_after_cap` · `rate_limit_default_wait` | 6 h · 60 s | §24.2 |
| `llm.breaker.timeout_threshold` | 3 | §24.2 |
| `llm.daily_request_budget` · `app_reserve` | `null` · 20 | §24.3 |
| `embeddings.batch_size` · `tick` · `max_failures` | 32 · 60 s · 3 | §24.4 |
| `topic_backfill.window` | 30 j | §24.6 |

Les priorités par type sont des constantes du registre (§23.1), pas des réglages.

---

## À durcir pendant la formation

Points connus, **non spécifiés** (#123). Chacun entre par la règle de la Partie VIII §47.5 (une décision, puis une
ligne du tableau, avant toute implémentation), au chapitre indiqué ; rien n'est préparé d'ici là. Quand un point
recoupe un élément de la Partie X, il y renvoie au lieu de le décrire.

- **Réparation d'une sortie invalide par un second appel** (Ch06) : renvoyer au modèle l'erreur de validation avant de
  compter l'échec. Déplacé de « Reporté en V2 ».
- **Thinking et effort pour `discover_topics`** (Ch07) : régler la réflexion et le niveau d'effort de la tâche la plus
  analytique ; le thinking adaptatif ne se désactive pas sur Claude Opus 5.5 et compte dans `max_tokens` (doc :
  `build-with-claude/effort`).
- **Modèle par tâche** (Ch08) : un modèle par tâche au lieu d'un `llm.model` unique. Déplacé de « Reporté en V2 ». La
  comparaison des modèles relève des évaluations (Partie X §64, X.6).
- **Prompt caching de la liste des topics** (Ch08) : mettre en cache le préfixe commun des prompts d'`enrich_article`
  et de `discover_topics` ; le minimum de tokens cachables dépend du modèle (doc : `build-with-claude/prompt-caching`).
- **Batching** (Ch08) : Message Batches API pour les jobs non urgents (doc : `build-with-claude/batch-processing`), et
  regroupement de plusieurs jobs par appel (décision 14). Déplacé de « Reporté en V2 ».
- **Taux de cache et analyse du coût par tâche** (Ch08) : exploiter les champs de cache journalisés (§25.6) et ventiler
  le coût réel par tâche. Le suivi du coût réel lui-même est en V1 (§24.3, #125).

---

## Reporté en V2 (tracé depuis la Partie V-A)

- **`analyze_trend`** : lecture qualitative des tendances par le LLM, avec sa table de résultats.
- **Conversation** avec l'historique : candidate en Partie X §59 (X.1).
- **Arbitrage des cas ambigus par `resolve_event`** : il suppose de pouvoir modifier l'appartenance des articles, ce que la V1 interdit.
- **Enrichissement des membres non représentatifs** d'un Event.
- **Ré-enrichissement en masse** après un changement de `PROMPT_VERSION` ou de modèle.
- **Priorité dynamique** (relever la priorité d'un job quand son Event devient chaud).
- **Nettoyage des entités `origin=llm` orphelines** et fusion d'entités de types différents.
