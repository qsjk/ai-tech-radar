# Partie V-A — Intelligence : machinerie & tâches LLM

2026-09-22

> **Partie V-A — Machinerie & tâches LLM.** Version durcie issue de la revue §23–§27.
> Remplace les §23 à §27 de SPEC.md V0.3. Prend les Parties I, II, III et IV durcies comme acquis.
> Les §28–§30 (clustering, trend engine, sujets émergents) relèvent de la **Partie V-B** : ils ne sont pas traités ici, seuls leurs impacts sont tracés en fin de document.

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
9. **Deux familles d'échecs** : les échecs d'**infrastructure** (gateway injoignable, 429, erreur de configuration) **ne consomment pas de tentative** et ouvrent un **disjoncteur LLM** ; les échecs **du job** (sortie malformée, timeout) consomment une tentative. Une panne du gateway ne vide donc jamais la file vers `dead_letter`.
10. **Disjoncteur LLM** à trois états (`closed` · `open` · `half_open`). Tant qu'il est ouvert, le worker **ne claime plus** de job LLM. Son état est exposé dans `SystemState.llm_gateway`.
11. **Ordre de claim** : priorité décroissante, puis **les plus récents d'abord** (`created_at DESC`). Après une panne, le quota va à l'actualité fraîche.
12. **TTL par type** : 72 h pour `enrich_article`, 7 j pour `resolve_event` et `discover_topics`. Au-delà, le job est `skipped` (`expired`). Cela borne le backlog et la rétention du contenu.
13. **Budget quotidien local optionnel** (`llm.daily_request_budget`, désactivé par défaut), avec une réserve pour les demandes de l'app.
14. **Pas de batching en V1** : un appel = un job. Le contrat reste compatible avec un batching ultérieur.
15. **Contrat `LLMClient` fixé** : signature typée, parsing et validation Pydantic **dans le client**, **aucun retry interne**, erreurs typées.
16. **Validation à deux niveaux** : une structure invalide fait échouer le job ; un **élément de liste invalide est écarté seul** et compté.
17. **Entités LLM canonicalisées** : on passe d'abord par le matcher d'alias de `entities.yaml`, puis par un slug déterministe. Évite les doublons d'entités.
18. **Jobs créables par l'app : liste fermée** `enrich_article` · `resolve_event` (régénération). Le rattachement de l'historique à un topic créé est un **traitement déterministe** dérivé de `EmergingDecision`, **hors `AIJob`**.
19. **Exception documentée à la règle d'un seul écrivain** : l'app peut faire passer un job de `dead_letter` à `pending` ou à `cancelled`, et **uniquement** ces deux transitions.
20. **File dérivée des embeddings** : elle ne sélectionne que les articles dont le contenu n'est **pas purgé**, ce qui empêche tout ré-embedding automatique de l'historique. Un échec persistant est enregistré comme une **ligne `Embedding` en échec**.
21. **`processed_at` est posé par une passe unique de l'étage purge**, de façon idempotente.
22. **Gateway non configuré** (`LLM_BASE_URL` absent) → le worker démarre, avec le disjoncteur ouvert en permanence (`not_configured`). Le produit tourne à 0 € sans LLM.
23. **`discover_topics` écrit dans de nouvelles colonnes de `EmergingCandidate`**. Son résultat est **indicatif** : il n'écarte jamais un candidat automatiquement (Partie II §6.1-4).
24. **Tous les réglages LLM vivent dans `pipeline.yaml`, section `llm.*`** (§27.8).

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
| `enrich_article` | `article` | worker | à l'insertion de chaque article `ready`, dans la transaction de la page (Partie IV §14.3) | 60 si source `relevance: always`, sinon 50 | 15 min | 72 h | oui (régénérer) |
| `resolve_event` | `event` | worker (V-B) | l'Event atteint `distinct_source_count = 2`, puis `article_count` ∈ {4, 8, 16, …} | 50 | 10 min | 7 j | oui (régénérer) |
| `discover_topics` | `emerging_candidate` | worker (V-B) | création d'un candidat émergent, ou évolution significative de ses preuves (définie en V-B) | 10 | 0 | 7 j | non |

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
- **Échec non rejouable** (requête refusée par le gateway, §26.1) → `failed`.

### 23.6 Actions de l'app sur les jobs

- **Création** : uniquement les types marqués `creatable_by_app` (§23.2), avec `created_by='app'`.
- **Relance d'un `dead_letter`** : `UPDATE` de `dead_letter` vers `pending`, avec `attempts = 0` et `next_attempt_at = now`.
- **Abandon d'un `dead_letter`** : `UPDATE` de `dead_letter` vers `cancelled`.
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

- **Aucun appel réseau dans une transaction d'écriture** : l'appel LLM est terminé et validé avant l'ouverture de la transaction (même règle que Partie IV §14.2).
- Le passage à `completed` se fait **dans la transaction qui écrit le résultat**. Si le worker meurt entre les deux, le job reste `processing` : il est requalifié en `retry` au démarrage et rejoué, et le remplacement des résultats rend ce rejeu sans effet de bord (acquis).

### 24.2 Disjoncteur LLM

L'état vit en mémoire du worker (processus unique). Il est recopié à chaque transition dans `SystemState.llm_gateway` : `{state, since, reason, open_until}`.

| Transition | Déclencheur |
|---|---|
| `closed → open` | `LLMUnavailable`, `LLMRateLimited`, `LLMConfigError`, ou **3 `LLMTimeout` consécutifs** |
| `open → half_open` | cause `unavailable` : une sonde `health()` réussit (sonde toutes les 60 s) · cause `rate_limited` : `open_until` est atteint · cause `config` : sonde toutes les 5 min |
| `half_open → closed` | le **job test** (un seul job claimé) aboutit |
| `half_open → open` | le job test subit à nouveau un échec d'infrastructure |
| — (permanent) | `LLM_BASE_URL` absent : état `open`, `reason = not_configured`, aucune sonde |

- **`open_until` après un 429** : valeur de `Retry-After` plafonnée à `llm.breaker.retry_after_cap` (6 h). Sans `Retry-After` : 60 s, doublé à chaque réouverture en échec, dans la même limite.
- **Pourquoi un job test** : une sonde `health()` ne détecte pas un quota épuisé. Seul un vrai appel le peut.
- Les jobs déjà en cours au moment de l'ouverture subissent chacun leur propre échec d'infrastructure ; leur tentative est rendue.

### 24.3 Budget quotidien

- Compteur `SystemState.llm_usage` = `{day, requests}` (jour UTC). Il est incrémenté pour chaque appel ayant reçu une réponse du gateway (2xx ou sortie malformée) ; un 429 ou une erreur réseau ne compte pas.
- `llm.daily_request_budget` : `null` (défaut) = pas de limite locale ; les quotas du gateway s'appliquent via les 429.
- Budget défini, avec `used ≥ budget − llm.app_reserve` → `:min_priority = 100` : seuls les jobs de l'app passent.
- `used ≥ budget` → plus aucun claim LLM jusqu'à 00:00 UTC.
- État exposé dans `/health` et le monitoring.

### 24.4 File dérivée des embeddings

Pas d'`AIJob` (Partie IV, décision 21). Le composant est distinct de la boucle AI et **ne dépend pas du disjoncteur LLM** : c'est une couche cœur (Partie II §6.1-3). Seul le **mécanisme de sélection** est fixé ici ; l'usage (similarité, clustering) relève de V-B.

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

1. Le worker crée le `Topic` avec `origin = user`. Son slug est dérivé de `llm_label`, ou à défaut de `label`. Ses mots-clés sont `suggested_keywords` ∪ {`key`}.
2. Il renseigne `EmergingCandidate.topic_id`.
3. Il re-score, **pour ce seul topic**, les articles `ready` des `topic_backfill.window` derniers jours (30 j) sur **titre + résumé** (contenu purgé). Il écrit des `ArticleTopic` `method=keyword`, par lots bornés.

Ce n'est pas le re-scoring rétroactif reporté par la Partie IV : ce dernier porte sur la modification des mots-clés de topics existants. La logique détaillée du cycle de vie des candidats relève de V-B.

## 25. LLM Gateway & LLMClient

Chaîne `AI Tech Radar → LLMClient → API OpenAI-compatible → LLM Gateway → Providers` : **inchangée**. Choix du gateway et checklist de mesure : inchangés (V0.3 §25, `docs/llm-gateway.md`).

### 25.1 Configuration

| Variable d'environnement | Rôle |
|---|---|
| `LLM_BASE_URL` | URL de l'API OpenAI-compatible. **Absente → LLM désactivé** : le worker démarre, avec le disjoncteur en `open / not_configured` |
| `LLM_API_KEY` | jeton Bearer, jamais journalisé |
| `LLM_MODEL` | modèle unique pour toutes les tâches en V1 (le gateway peut router) |

Les autres réglages (timeouts, température, mode JSON) sont dans `pipeline.yaml` (§27.8).

### 25.2 Interface

```python
T = TypeVar("T", bound=BaseModel)

@dataclass(frozen=True)
class LLMResult(Generic[T]):
    value: T                    # objet validé
    dropped_items: int          # éléments de listes écartés à la validation
    model: str | None           # modèle rapporté par le gateway
    input_tokens: int | None
    output_tokens: int | None
    latency_ms: int

class GatewayHealth(BaseModel):
    reachable: bool
    detail: str | None

class LLMClient:
    async def generate(
        self, *,
        task: str,                    # nom de la tâche, pour logs et métriques
        system: str,
        user: str,
        response_model: type[T],
        max_output_tokens: int,
        temperature: float = 0.2,
    ) -> LLMResult[T]: ...

    async def health(self) -> GatewayHealth: ...
```

- **`generate`** fait un `POST {LLM_BASE_URL}/chat/completions` avec `model = LLM_MODEL`, les deux messages, `max_tokens` et `temperature`, plus `response_format={"type":"json_object"}` uniquement si `llm.json_mode = true`.
- **`health`** fait un `GET {LLM_BASE_URL}/models`, avec un timeout de 5 s. Il ne consomme pas de quota de génération.
- **Client HTTP dédié** (httpx asynchrone), distinct du `HttpClient` des collectors : pas de limiteur par hôte ni de User-Agent de collecte.
- **Aucun retry interne.** Un appel = une requête. La résilience vit au niveau du job et du disjoncteur ; aucun appel n'est multiplié en silence.
- **Timeouts** : connexion 5 s, lecture 60 s (configurables).

### 25.3 Parsing et validation

Réalisés **dans `LLMClient`**. Le handler reçoit un objet validé ou une exception typée.

1. Réponse vide, `finish_reason = "length"` (sortie tronquée) ou absence de contenu → `LLMMalformed`.
2. Extraction du JSON : retrait d'éventuelles balises de code, puis premier objet `{…}` équilibré du texte.
3. Validation par `response_model`.
4. **Types utilitaires** fournis avec le client :
   - `TolerantList[X]` : chaque élément est validé séparément ; un élément invalide est écarté et compté dans `dropped_items`, sans faire échouer la réponse ;
   - `SoftStr(max, min)` : texte trimé ; au-delà de `max`, coupé sur une frontière de mot et suivi de `…` ; sous `min`, erreur de validation.
5. Toute autre erreur de validation → `LLMMalformed`. **Aucune écriture** n'a lieu avant la fin de la validation (acquis).

### 25.4 Erreurs typées

| Exception | Cause | Famille |
|---|---|---|
| `LLMUnavailable` | erreur de connexion ou DNS, timeout de connexion, 5xx | infrastructure |
| `LLMRateLimited(retry_after)` | 429 | infrastructure |
| `LLMConfigError` | 401 · 403 · 404 (clé ou modèle invalide) | infrastructure |
| `LLMTimeout` | timeout de lecture | job |
| `LLMMalformed` | JSON absent ou invalide, validation échouée, sortie vide ou tronquée, refus | job |
| `LLMBadRequest` | 400 · 413 · 422 | non rejouable |

Le traitement de chaque famille est décrit au §26.1.

### 25.5 Prompts

- Un module par tâche (`app/llm/prompts/<task>.py`). Chacun expose la construction de `system` et `user`, le `response_model` et une constante `PROMPT_VERSION`, présente dans les logs.
- Le contenu des articles est une **donnée non fiable**. Il est placé dans le message `user`, entre délimiteurs explicites. Le prompt système indique qu'il ne contient aucune instruction à suivre.
- **Protection contre l'injection** : une sortie bornée par le schéma, des topics choisis dans une liste fermée, des longueurs plafonnées, une sortie jamais exécutée et **toujours échappée** à l'affichage.

### 25.6 Observabilité

- **Log par appel** : `task`, `job_id`, latence, tokens, classe d'erreur, `PROMPT_VERSION`. Jamais le prompt ni la réponse au niveau `info`. Au niveau `debug`, les 200 premiers caractères d'une réponse malformée.
- **Métriques** : appels par tâche et par issue · tokens · latence · `dropped_items` · jobs `skipped` par motif · backlog par type et par statut · état du disjoncteur · consommation du budget quotidien.

## 26. Résilience LLM & retry

Principe et tableau de pannes : **acquis** (Partie II §9.1). Cette section précise la **distinction des familles d'échec** sans laquelle la reprise automatique promise par §9.1 serait fausse : sans elle, les tentatives seraient épuisées en quelques minutes de panne.

### 26.1 Traitement par famille

| Famille | Tentative | Statut du job | Disjoncteur |
|---|---|---|---|
| **Infrastructure** (`LLMUnavailable`, `LLMRateLimited`, `LLMConfigError`) | **rendue** | `retry`, `next_attempt_at` = réouverture prévue | ouvert (§24.2) ; `LLMConfigError` déclenche en plus une **alerte de configuration** |
| **Job** (`LLMMalformed`, `LLMTimeout`) | consommée | `retry` avec backoff §23.5, puis `dead_letter` | inchangé, sauf 3 `LLMTimeout` consécutifs → ouvert (cause `unavailable`) |
| **Non rejouable** (`LLMBadRequest`) | — | `failed` | inchangé |
| **Exception inattendue** du handler | consommée | comme un échec du job | inchangé |

Dans tous les cas, `last_error` reçoit la classe d'erreur et un message sans secret.

### 26.2 Garanties

- **Gateway éteint pendant N heures** : aucun job ne passe en `dead_letter` du fait de la panne. Au retour, les jobs reprennent, les plus récents d'abord, et les jobs expirés sont `skipped`.
- **Quota journalier épuisé** : le disjoncteur reste ouvert jusqu'au `Retry-After` (plafonné), puis un job test vérifie que le quota est revenu. Aucune rafale d'appels voués au 429.
- **Aucune écriture partielle** : validation complète, puis une transaction unique.

### 26.3 Scénarios de test obligatoires

```
gateway down (connexion refusée) → disjoncteur ouvert → aucun claim LLM
  → attempts inchangés → gateway up → sonde OK → job test OK → reprise, plus récents d'abord

429 avec Retry-After: 120 → open_until = +120 s → half_open → job test → closed

429 persistant sans Retry-After → réouvertures en 60 s, 120 s, 240 s… plafonnées à 6 h

réponse non-JSON ×3 → dead_letter ; purge du contenu bloquée ; relance app → pending

élément d'entité invalide dans une réponse valide → écarté, dropped_items = 1, job completed

3 timeouts consécutifs → disjoncteur ouvert

LLM_BASE_URL absent → worker démarre, jobs créés, restent pending, /health = llm not_configured

kill -9 après l'appel LLM, avant la transaction → retry → rejoué → état final identique
```

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
| `llm.max_concurrent` | 2 | §24.1 |
| `llm.connect_timeout` · `read_timeout` | 5 s · 60 s | §25.2 |
| `llm.json_mode` | `false` | §25.2 |
| `llm.temperature` | 0,2 | §25.2 |
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

## Reporté en V2 (tracé depuis la Partie V-A)

- **`analyze_trend`** : lecture qualitative des tendances par le LLM, avec sa table de résultats.
- **Conversation** avec l'historique.
- **Arbitrage des cas ambigus par `resolve_event`** : il suppose de pouvoir modifier l'appartenance des articles, ce que la V1 interdit.
- **Batching** de plusieurs jobs par appel LLM.
- **Enrichissement des membres non représentatifs** d'un Event.
- **Modèle par tâche** (au lieu d'un `LLM_MODEL` unique).
- **Ré-enrichissement en masse** après un changement de `PROMPT_VERSION` ou de modèle.
- **Réparation d'une sortie malformée** par un second appel correctif.
- **Priorité dynamique** (relever la priorité d'un job quand son Event devient chaud).
- **Nettoyage des entités `origin=llm` orphelines** et fusion d'entités de types différents.

---

## Impacts à répercuter dans les autres parties

À traiter lors de la revue des parties concernées — **hors Partie V-A**.

### Partie V-B — Clustering, trends, émergents

- **Clustering** : le critère « ≥ N entités communes » ne compte que les liaisons **`method=keyword`**. Sinon, l'existence d'un Event dépendrait du LLM (Partie II §6.1-4).
- **Signal** : les catégories (`established` · `trending` · `emerging` · `declining`) se calculent sur les **topics `keyword`** uniquement. Si les topics `llm` étaient comptés, une panne du gateway ferait baisser les mentions et fabriquerait un faux `declining`. Les topics `llm` servent à l'affichage et au filtrage.
- **Cadence du clustering** : elle doit être **inférieure à `llm.delay.enrich_article`** (15 min), sinon la garde `event_member` voit des articles pas encore regroupés.
- **Création des `resolve_event`** : dans la transaction de rattachement, quand `distinct_source_count` atteint 2, puis quand `article_count` atteint 4, 8, 16… Sur une fusion d'Events, le job vise l'Event cible.
- **Membres non enrichis** : les membres non représentatifs n'ont que des topics keyword. Les tendances doivent le tolérer, ce qui est cohérent avec la règle keyword-only ci-dessus.
- **Moteur d'émergence** : il crée les `discover_topics`, définit l'« évolution significative » des preuves et choisit les articles fournis au job. `covered_by` n'intervient pas dans le critère déterministe « pas déjà couvert ».
- **Cycle de vie « Create topic »** : à détailler en V-B, en cohérence avec §24.6.
- **Points déjà signalés et toujours ouverts** : formule de `Event.importance` (qui peut utiliser `Article.metrics`) · agrégation des topics enfants dans les tendances · `webpage` et `rss`, même canal ou non, pour `distinct_channel_count` · fréquence de calcul des `Signal`.

### Partie II — Architecture

- **§8.3** : ajouter l'exception d'écriture de l'app sur `AIJob` (`dead_letter → pending | cancelled`, §23.6).
- **§9.1** : renvoyer au §26 pour la distinction des familles d'échec et le disjoncteur ; ajouter la ligne « gateway non configuré ».
- **§7.1** : « Enqueue » devient « 1 `enrich_article` par article `ready` ; embeddings par file dérivée ».
- **§8.5** : ajouter la passe `processed_at` (§24.5) et le statut `skipped` parmi les statuts terminaux qui ne bloquent pas la purge.

### Partie III — Données

- **`AIJob.job_type`** : la liste V1 devient `enrich_article · resolve_event · discover_topics`.
- **`AIJob.status`** : ajouter `skipped` au `CHECK`. Nouvelle colonne `skip_reason` (texte, nullable, validé par le code).
- **Rétention** : `AIJob` `skipped` supprimé à 30 jours.
- **`AIJob.entity_type`** : valeurs `article · event · emerging_candidate`, validées par le code.
- **`Embedding`** : `vector` et `dim` deviennent nullables ; nouvelle colonne `error`. Une ligne sans vecteur est exclue de la similarité.
- **`EmergingCandidate`** : nouvelles colonnes `llm_label` · `llm_description` · `covered_by_topic_id` (FK `Topic`, nullable) · `suggested_keywords` (JSON) · `assessed_at`.
- **`SystemState`** : nouvelles clés `llm_gateway` · `llm_usage` · `embeddings`, toutes écrites par le worker.

### Partie IV — Pipeline

- **§14.3** : les jobs créés à l'insertion sont exactement **un `enrich_article` par article `ready`**, de priorité 60 (source `always`) ou 50, avec `next_attempt_at = now + 15 min`.
- **§16.6** : ajouter les sections `llm.*`, `embeddings.*` et `topic_backfill.*` à `pipeline.yaml` (§27.8), validées comme le reste.

### Partie VI — Interfaces

- **Actions** : régénérer un aperçu (`enrich_article`) ou un titre d'Event (`resolve_event`) ; relancer ou abandonner un `dead_letter`. Quand un job actif existe déjà, le bouton indique « en cours ».
- **Indicateur discret** repli / enrichi, basé sur `summary_origin` et `title_origin`.
- **Sujets émergents** : afficher `llm_label` et `llm_description` quand ils existent, sinon `label`. `covered_by` est présenté comme une suggestion.
- **Toute sortie LLM est échappée** au rendu.

### Partie VII — Ops

- **`/health`** : `llm_gateway` se lit dans `SystemState.llm_gateway` (état du disjoncteur, cause, depuis quand). Ajouter `embeddings` et la consommation du budget.
- **Alertes** : disjoncteur ouvert depuis plus de X h (seuil à fixer) · `LLMConfigError` · moteur d'embeddings `down`.
- **Métriques** : celles du §25.6, plus le backlog d'embeddings.
- **`.env.example`** : `LLM_BASE_URL`, `LLM_API_KEY`, `LLM_MODEL`, avec la mention « optionnels — sans eux, le produit tourne sans LLM ».
- **Mesure du gateway** (checklist V0.3 §25) : y ajouter la vérification du comportement 429 / `Retry-After` et la disponibilité de `GET /models`.

### Partie VIII — Livraison

- **Tests** : les scénarios du §26.3 · chaque motif de `skip_reason` · validation tolérante (`TolerantList`, `SoftStr`) · canonicalisation des entités LLM par les alias · rejeu idempotent de chaque `job_type` · trigger FTS sur mise à jour du résumé · passe `processed_at` · article poison dans la file d'embeddings · budget quotidien et réserve de l'app.
- **Faux gateway** OpenAI-compatible en fixture (réponses valides, malformées, 429, 5xx, lentes), utilisé en CI. Aucun test n'appelle un vrai provider.
- **Fixtures de prompts** par `PROMPT_VERSION`, avec des sorties de référence.

---

