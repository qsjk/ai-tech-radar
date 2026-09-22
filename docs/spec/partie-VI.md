# Partie VI — Interfaces

> **Partie VI — Interfaces.** Version durcie issue de la revue §31–§34.
> Dernière révision : 2026-09-22. Prend les Parties I, II, III, IV, V-A et V-B durcies comme acquis.

> **Déjà tranché ailleurs, non repris ici** : l'app insère des `AIJob` de types prédéfinis (`enrich_article`, `resolve_event`) et n'en exécute jamais aucun ; elle répond immédiatement (Partie II §8.3, V-A §23.6) · coordination app ↔ worker par la base, sans IPC (Partie II §8.2) · alertes émises par le worker, sans reprise en V1 (Partie II §9.4) · tables `UserPreference`, `Setting`, `ReadState`, `EmergingDecision`, `AlertLog` (Partie III §11.12–11.13) · formule d'importance, fusion d'Events, catégories de tendance, cycle des candidats émergents (V-B) · repli / enrichi (`summary_origin`, `title_origin`, V-A §27.6–27.7) · le dashboard, la recherche, la hotness et les alertes déterministes fonctionnent sans la couche AI (Partie II §6).

---

## Décisions tranchées dans cette revue (Partie VI)

1. **Unité d'affichage = la story.** Une story est un **Event** (`active` ou `archived`) ou un **article `ready` sans Event**. Le Feed et l'Overview ne listent que des stories ; les membres d'un Event n'apparaissent que dans la vue Event. Les articles `duplicate` et `filtered` ne sont jamais affichés.
2. **Hotness visible** : badge « N sources · M canaux » ; une story est **corroborée** si `distinct_source_count ≥ 2`, **isolée** sinon. Calcul SQL, sans LLM.
3. **Importance affichée sur 0–100** (`round(importance × 100)`) ; `NULL` → « — ». **Deux seuils distincts** : affichage (défaut 0) et alerte (défaut 50), plus un seuil d'alerte abaissé pour les stories suivies (défaut 25).
4. **Overview à six sections** (Important · Suivis · Trending · Emerging · Latest · Unread), chacune bornée ; **une story n'y apparaît qu'une fois**.
5. **Lu / non lu** : non lu si l'activité de la story est postérieure à la dernière lecture ; un Event lu **redevient non lu** quand son activité progresse. L'historique antérieur à `SystemState.trends_since` est réputé lu. Lecture **implicite** (ouverture de l'Event, clic sur le lien d'un article isolé), « marquer non lu » et « tout marquer lu ».
6. **Sourdine sur une story multi-sources** : masquée seulement si **tous** ses membres viennent de sources muettes, ou si **tous** ses topics sont muets. Toggle « afficher les masqués ».
7. **Sourdine héritée** dans la hiérarchie des topics ; un `follow` explicite sur un descendant l'emporte.
8. **« Follow » sur un topic ou une source** : filtre et section « Suivis », seuil d'alerte abaissé.
9. **Related topics déterministes** : parent, enfants, top 5 par co-occurrence de liaisons `keyword` sur 30 jours.
10. **Filtres du Feed** : topic, source, entité, date, importance, non lu, suivis, recherche plein texte (`q`). Le filtre « Event » de la V0.3 est supprimé (c'est la vue Event).
11. **API** : JSON, pagination **keyset** (jamais d'offset), régénération en **202** immédiat, état « en cours » exposé par ressource (`jobs_in_progress`), mise à jour par **polling** (pas de WebSocket ni SSE en V1).
12. **Rendu des sorties LLM en texte brut** ; pas de markdown en V1 ; `dangerouslySetInnerHTML` interdit par règle lint.
13. **Auth = basic_auth Caddy** (bcrypt) sur tout sauf `/health`, **plus une protection anti-CSRF** côté app. `DASHBOARD_TOKEN` est abandonné.
14. **`/health` public minimal** (`{status}` seul) ; le détail passe derrière l'authentification.
15. **Alertes « au plus une fois »** : `AlertLog` écrit **avant** l'envoi, avec un statut transitoire `sending` ; un crash entre les deux perd l'alerte (cohérent avec « V1 sans reprise »).
16. **`dedup_key` inclut le canal** : sinon la même alerte ne peut pas partir sur email **et** Telegram (`UNIQUE(dedup_key)`).
17. **`important_event`** : Event seulement (jamais un article isolé), fenêtre d'activité de 48 h (pas de rafale après une baisse de seuil ni au premier run), dédup par Event **cible** d'une fusion, attente bornée du titre LLM (30 min).
18. **« Fréquence des alertes »** = mode (`immediate` | `digest_only`) · heures calmes · plafond quotidien · horaires des digests · fuseau.
19. **Digests déclenchés par le tick d'alertes**, pas par un cron : robustes aux changements de réglage et aux arrêts du worker. Un digest vide n'est pas envoyé. Les nouveaux candidats émergents sans décision vont dans les digests, jamais en alerte instantanée.
20. **Routage des canaux par type d'alerte** (défaut : Telegram pour l'instantané, email pour les digests). Canal non configuré → désactivé, le worker démarre quand même.
21. **Registre des `Setting` en code** (clé, schéma, défaut) ; une clé absente vaut son défaut.
22. **Bandeau d'état système**, **page des jobs en échec** et **historique des alertes** dans le dashboard, en lecture seule de la base.

---

## 31. Dashboard

Frontend **React + TypeScript + Vite**, servi en statique par Caddy (Partie II §8.1). Cette section fixe le **comportement** et le **contenu**, pas le design.

### 31.1 La story

| | Event | Article isolé |
|---|---|---|
| **Éligible** | `status ∈ {active, archived}` et `article_count ≥ 1` | `status = ready` et `event_id IS NULL` |
| **Identifiant** | `("event", id)` | `("article", id)` |
| **`activity_at`** (clé d'activité) | `Event.last_seen_at` | `Article.published_at` |
| **Importance** | `Event.importance` | `Article.importance` (`NULL` possible avant évaluation) |
| **Hotness** | `distinct_source_count` · `distinct_channel_count` | 1 source · 1 canal |
| **Titre** | `Event.title` (`title_origin`) | `Article.title` |
| **Aperçu** | `Event.description` si non nulle, sinon résumé du représentant (`summary_origin`) | `Article.summary` (`summary_origin`) |

- Un Event `merged` n'est jamais une story (§31.7).
- **Membres** d'une story : ses articles `ready` (l'article lui-même pour un article isolé). Les `duplicate` sont exclus de tout affichage et de toute agrégation.
- **Topics d'une story** : union des `ArticleTopic` (`keyword` et `llm`) de ses membres, dédoublonnée. **Entités** et **sources** : idem.
- Un article qui rejoint un Event cesse d'être une story ; son état de lecture ne se transfère pas (§31.5).

### 31.2 Présentation commune

- **Hotness** : badge « N sources · M canaux ». Deux états visuels : **corroboré** (`distinct_source_count ≥ 2`) et **isolé** (1 source). C'est la distinction exigée par la Partie I (fonction 10).
- **Importance** : `round(importance × 100)` ; `NULL` → « — ».
- **Repli / enrichi** : marqueur discret sur le titre (`title_origin`) et sur l'aperçu (`summary_origin`). `fallback` = repli déterministe, `llm` = enrichi.
- **Tendances** : toute valeur `NULL` (`growth_rate`, `momentum`, `novelty`, `category`) s'affiche « données insuffisantes », **jamais 0**.
- **Badge de catégorie** d'un topic : `trending` et `rising` ont des badges distincts ; `established` et `declining` sont affichés dans la vue Topic uniquement.
- **Sorties LLM** (`summary`, `title`, `description`, `llm_label`, `llm_description`) : rendues en **texte brut**, échappées par React. Pas de rendu markdown en V1. `dangerouslySetInnerHTML` est interdit par une règle lint.
- **Dates** : UTC reçues de l'API, converties au fuseau `timezone` (§34.3) à l'affichage uniquement.

### 31.3 Overview

| Section | Contenu | Tri | Limite |
|---|---|---|---|
| **Important** | stories non masquées, `activity_at ≥ now − 72 h`, importance ≥ `display.importance_threshold` | importance ↓, puis `activity_at` ↓ | 10 |
| **Suivis** | stories suivies (§34.2) non masquées, `activity_at ≥ now − 72 h` | `activity_at` ↓ | 10 |
| **Trending** | topics activés, non muets, dont le dernier `Signal` de période `7d` a `category ∈ {trending, rising}` ; badge `rising` distinct | `rising` d'abord, puis `growth_rate` ↓ | 10 |
| **Emerging** | candidats selon V-B §30.7 (§31.8) | `last_significant_at` ↓ | 10 |
| **Latest** | stories non masquées | `activity_at` ↓ | 20 |
| **Unread** | compteur total des stories non lues non masquées + liste | `activity_at` ↓ | 20 |

- **Une story n'apparaît qu'une fois dans l'Overview** : ordre de priorité Important → Suivis → Latest → Unread ; une story déjà affichée dans une section précédente est retirée des suivantes. Le **compteur** Unread n'est pas affecté.
- Chaque section renvoie vers le Feed avec les filtres correspondants.
- Emerging en warm-up (`now < trends_since + emerging.warmup`) : la section affiche « détection active à partir du <date> ».

### 31.4 Feed

**Filtres** (combinables, ET logique) :

| Filtre | Paramètre | Sémantique |
|---|---|---|
| Topic | `topic=<slug>` | un membre a une liaison (`keyword` ou `llm`) vers le topic **ou un descendant activé** |
| Source | `source=<id>` (répétable, OU) | un membre provient de la source |
| Entité | `entity=<id>` | un membre est lié à l'entité |
| Date | `from`, `to` | sur `activity_at` |
| Importance | `min_importance` (0–100) | importance ≥ valeur ; `NULL` exclu si valeur > 0 ; défaut `display.importance_threshold` |
| Non lu | `unread=true` | §31.5 |
| Suivis | `followed=true` | §34.2 |
| Recherche | `q` | FTS5 sur titre + résumé des **membres** (§31.4.1) |
| Masqués | `include_muted=true` | inclut les stories masquées par une sourdine (§34.2), signalées comme telles |

- Une story matche un filtre si **au moins un** de ses membres le satisfait.
- Les Events `archived` sont inclus (historique exploitable, Partie I fonction 11).
- **Tri** : `sort=activity` (défaut, `activity_at` ↓) ou `sort=importance` (importance ↓, puis `activity_at` ↓).

**Champs de chaque entrée** : titre (+ marqueur) · aperçu (+ marqueur) · topics (5 au plus, avec badge `trending` / `rising`) · entités (5 au plus) · sources (noms distincts) · date (`published_at` pour un article isolé ; `first_seen_at`–`last_seen_at` pour un Event) · hotness · importance · état lu / non lu · état suivi · liens.

**Liens d'origine** (article isolé) : lien principal = `link_url` s'il existe, sinon `url`. Si les deux existent (post HN, Reddit), un second lien « discussion » pointe vers `url`. Pour un Event, les liens sont dans la vue Event.

**Indicateurs de tendance d'une entrée** : hotness, importance et badges de catégorie de ses topics. Un Event n'a pas de `Signal` propre.

#### 31.4.1 Recherche plein texte

- Index `article_fts` (Partie III §11.14) sur `title` + `summary` des articles. Une story matche si un de ses membres matche.
- La saisie utilisateur **n'est jamais passée brute** à FTS5 : elle est découpée en tokens, chacun cité comme littéral, combinés en ET. Aucune erreur de syntaxe FTS ne peut remonter à l'utilisateur.
- **Limite assumée** : un titre d'Event produit par le LLM n'est pas indexé. Le titre du représentant l'est, ainsi que les résumés enrichis des membres (le trigger suit les mises à jour).
- La recherche n'est **pas sémantique** en V1 (Partie I).

### 31.5 Lu / non lu

**Règle** : une story est **non lue** si et seulement si :

```
activity_at ≥ unread_since
ET ( aucun ReadState pour la story  OU  ReadState.read_at < activity_at )
```

- `ReadState` porte sur `("event", id)` pour un Event, `("article", id)` pour un article isolé (Partie III §11.12).
- **`unread_since`** = `SystemState.trends_since` (première insertion d'un article `ready`). Tout ce qui précède, notamment le premier run de collecte, est réputé lu. `NULL` → aucune story à afficher de toute façon.
- **Ré-ouverture** : un Event lu dont `last_seen_at` progresse au-delà de `read_at` redevient non lu. **Limite assumée** : un membre publié avant la lecture mais découvert après ne rouvre pas l'Event.
- **Limite assumée** : un article isolé lu qui rejoint ensuite un Event fait apparaître cet Event comme non lu.
- **Déclencheurs** :
  - ouverture de la vue Event → Event marqué lu ;
  - clic sur un lien d'origine d'un article isolé → article marqué lu ;
  - bouton « marquer non lu » → suppression du `ReadState` ;
  - « tout marquer lu » (§31.9, `POST /api/read/bulk`) sur les filtres courants, jusqu'à l'instant de la demande.
- Un `ReadState` sur un Event `merged` est ignoré ; seul compte celui de la cible (V-B).

### 31.6 Vue Topic

| Bloc | Contenu |
|---|---|
| **En-tête** | `name`, `description`, `origin` (badge si `user`), parent, état suivi / muet, boutons suivre / sourdine |
| **Mentions & croissance** | pour chaque période `24h` · `7d` · `30d`, dernier `Signal` : `mentions`, `unique_sources`, `growth_rate`, `velocity`, `momentum`, `novelty`, `category` — `NULL` → « données insuffisantes » |
| **Timeline** | mentions par jour sur 90 jours : lignes `Signal` de période `24h` et de `window_end` = 00:00 UTC |
| **Sources** | top 5 des sources par nombre d'articles liés (`keyword`, descendants inclus) sur 7 jours |
| **Related topics** | parent · enfants · top 5 par co-occurrence (§31.6.1) |
| **Stories** | stories du topic, paginées — même endpoint que le Feed avec `topic=<slug>` |

Un topic muet reste consultable, avec un bandeau « en sourdine ». Un topic désactivé (`enabled = false`) affiche son historique et « plus calculé ».

#### 31.6.1 Co-occurrence

Pour le topic *t*, score de *u* = nombre d'articles `ready` (hors `duplicate`) de `published_at ≥ now − 30 j` liés en `keyword` à la fois à *t* et à *u*. On retient les 5 meilleurs scores `≥ 3`, hors parent et enfants déjà listés, hors topics désactivés. Calcul à la lecture, borné par la fenêtre ; déterministe, sans LLM.

### 31.7 Vue Event

| Bloc | Contenu |
|---|---|
| **En-tête** | titre (+ marqueur), description ou résumé du représentant (+ marqueur), statut (`archived` affiché), hotness, importance, `first_seen_at`, `last_seen_at`, `article_count` |
| **Timeline / articles** | membres `ready` triés par `published_at` ↑ : source, titre, aperçu (+ marqueur), liens (principal + discussion) ; le représentant est signalé |
| **Sources · entités · topics** | unions sur les membres ; topics avec badge de catégorie |
| **Trend** | compteurs ci-dessus + catégories des topics de l'Event |
| **Actions** | régénérer le titre (§31.9.2) · régénérer l'aperçu d'un membre · marquer non lu |

**Event fusionné** : `GET /api/events/{id}` sur un Event `merged` renvoie `{"redirect_to": <id>}`, où `<id>` résout **toute la chaîne** `merged_into_id` jusqu'au premier Event non `merged`. La SPA remplace l'URL (pas d'entrée d'historique supplémentaire) et charge la cible. L'état de lecture affiché est celui de la cible.

### 31.8 Sujets émergents

**Liste** (règle V-B §30.7) : candidats `active` sans décision ou en `follow` (les `follow` restent visibles même `dormant`), plus les `ignore` réapparus (`resurfaced_at > decided_at`). Jamais `mute` ni `converted`.

**Champs** :

- libellé : `llm_label` s'il existe, sinon `label` (+ marqueur repli / enrichi) ; pour `kind = repository`, le `owner/repo` ;
- `llm_description` si elle existe ;
- preuves (`evidence`) : `mentions_7d`, `growth` (en %), `sources`, `authors`, `channels`, `stories`, `first_seen_at` ;
- articles : ceux de `evidence.article_ids` (titre + lien) ;
- **`covered_by_topic_id`** présenté comme une **suggestion** : « Peut-être couvert par <topic> » avec lien. Il n'a aucun effet.
- badges : **réapparu** (`ignore` avec `resurfaced_at > decided_at`), **suivi**, **en sommeil** (`follow` et `dormant`).

**Actions** : `follow` · `ignore` · `mute` · `create_topic`, sémantique V-B §30.7.

- Une décision s'enregistre par upsert ; changer d'avis est permis, **sauf après `create_topic`** (définitif, 409).
- **`create_topic`** : sans formulaire (V-B). Tant que `topic_id` est `NULL`, le candidat affiche « création en cours » ; ensuite il disparaît de la liste et le dashboard propose le lien vers le topic créé.
- Pas de suppression de décision en V1.

### 31.9 Actions sur les jobs

#### 31.9.1 Principes

- L'app **insère** un `AIJob` (`created_by = app`, priorité 100, délai nul — V-A §23.2) et répond **202** immédiatement. Elle n'attend jamais un résultat.
- Si un job actif existe pour la même cible et le même type, l'insertion est ignorée par l'index unique partiel ; la réponse vaut `already_active`, sans erreur.
- Toute ressource ciblable (article, Event) expose `jobs_in_progress` : la liste des `job_type` pour lesquels un job `pending`, `processing` ou `retry` existe. Le bouton correspondant affiche « en cours ».
- **Mise à jour de l'écran** : tant que `jobs_in_progress` n'est pas vide, la SPA relit la ressource toutes les **10 s**, et s'arrête après **10 min** (le job reste visible « en cours » à la prochaine lecture).

#### 31.9.2 Disponibilité des boutons

| Action | Masqué / désactivé si |
|---|---|
| Régénérer l'aperçu (`enrich_article`) | article non `ready` · LLM `not_configured` |
| Régénérer le titre (`resolve_event`) | Event `merged` ou `archived` (`event_not_active`) · `distinct_source_count < 2` (`event_single_source`) · LLM `not_configured` |

- Disjoncteur LLM ouvert (hors `not_configured`) : la demande est acceptée, avec la mention « sera traité au retour du LLM ». Le TTL du type s'applique (V-A §23.2).
- Aperçu d'un article dont le contenu est purgé : la régénération travaille sur titre + résumé courant (V-A §27.2) ; le bouton l'indique (« entrée réduite »).

#### 31.9.3 Jobs en échec

Page dédiée, paginée : `dead_letter` avec `job_type`, cible (lien), `attempts`, `last_error` (500 caractères au plus, texte brut), `created_at`.

- **Relancer** : `dead_letter → pending`, `attempts = 0`, `next_attempt_at = now` (V-A §23.6).
- **Abandonner** : `dead_letter → cancelled` ; débloque la purge du contenu de l'article.
- Transaction conditionnelle `WHERE status = 'dead_letter'` ; si le job a changé d'état entre-temps → 409.

### 31.10 Bandeau d'état système

Lecture de `SystemState`, affiché en permanence tant qu'une condition est vraie :

| Condition | Message |
|---|---|
| `llm_gateway.state = open`, `reason = not_configured` | « LLM non configuré : aperçus et titres en mode repli » (discret, permanent) |
| `llm_gateway.state ∈ {open, half_open}` | « LLM indisponible depuis <since> : enrichissements en attente » |
| `embeddings = down` | « Moteur d'embeddings indisponible : regroupement dégradé » |
| heartbeat worker périmé (seuil de `/health`) | « Worker arrêté depuis <date> : plus de collecte » |
| warm-up émergence en cours | « Détection des sujets émergents active à partir du <date> » |
| `dead_letter` > 0 | « N jobs en échec » (lien vers §31.9.3) |
| alertes `failed` sur 24 h > 0 | « N alertes non envoyées » (lien vers §33.10) |
| condition `system` active (Partie VII §39.5), au minimum `backup_*`, `restore_test_*`, `disk_*` et `no_alert_channel` | nom de la condition et « depuis <since> » |

Le bandeau ne fait **aucun appel** au gateway ni au worker : il ne lit que la base.

### 31.11 Contrat d'API

**Conventions** :

- Préfixe `/api`, JSON, schémas Pydantic en réponse. Dates en UTC ISO-8601.
- **Erreurs** : `{"error": {"code": "<code>", "message": "<texte>"}}` ; codes HTTP 400 · 403 · 404 · 409 · 422. Le 401 est émis par Caddy (§32).
- **Pagination keyset** sur tout endpoint de liste : réponse `{"items": [...], "next_cursor": <opaque> | null}`, paramètres `cursor` et `limit` (défaut 20, maximum 50). Le curseur encode `(valeur de tri, kind, id)`. **Aucun offset**, **aucun total** calculé (hors compteur Unread de l'Overview) — lectures courtes (Partie II §8.6).
- Lectures en `read_session` ; écritures en `write_session`, quelques lignes par requête.
- **Aucun endpoint ne dépend de la couche AI** : tous restent pleinement fonctionnels gateway éteint. Seuls changent les marqueurs de repli et la disponibilité des boutons de régénération.

**Schéma `StorySummary`** (entrées de Feed et d'Overview) :

```json
{
  "kind": "event | article",
  "id": 123,
  "title": "…", "title_origin": "fallback | llm",
  "summary": "…", "summary_origin": "fallback | llm",
  "importance": 42,
  "hotness": {"sources": 3, "channels": 2, "corroborated": true},
  "topics": [{"slug": "mcp", "name": "MCP", "category": "trending | rising | null"}],
  "entities": [{"id": 7, "name": "…", "type": "repository"}],
  "sources": [{"id": 2, "name": "…"}],
  "published_at": "…", "first_seen_at": "…", "last_seen_at": "…", "activity_at": "…",
  "links": {"primary": "…", "discussion": "… | null"},
  "status": "active | archived | ready",
  "unread": true, "followed": false, "muted": false,
  "jobs_in_progress": []
}
```

`links` n'est renseigné que pour un article isolé ; `published_at` pour un article, `first_seen_at` / `last_seen_at` pour un Event ; `muted` n'apparaît qu'avec `include_muted=true`.

**Endpoints — lecture** :

| Méthode · chemin | Rôle |
|---|---|
| `GET /api/overview` | six sections §31.3 + compteur Unread |
| `GET /api/stories` | Feed, filtres et tri §31.4, paginé |
| `GET /api/events/{id}` | vue Event §31.7, ou `{redirect_to}` si `merged` |
| `GET /api/articles/{id}` | article (utile aux membres et à l'aperçu régénéré) |
| `GET /api/topics` | arbre des topics avec état suivi / muet et catégorie `7d` |
| `GET /api/topics/{slug}` | vue Topic §31.6 |
| `GET /api/sources` | sources avec état suivi / muet et santé (`last_success_at`, `last_error`) |
| `GET /api/entities?q=` | autocomplétion pour le filtre Entité (20 au plus) |
| `GET /api/emerging` | liste §31.8, paginée |
| `GET /api/status` | bandeau §31.10 ; calculé par le même module que `/api/health` et `/health` (Partie VII §40.1) |
| `GET /api/health` | santé détaillée par composant, conditions actives, métriques (Partie VII §40.3) |
| `GET /api/jobs/dead-letters` | page §31.9.3, paginée |
| `GET /api/alerts` | historique §33.10, paginé, filtres `type`, `status`, `channel` |
| `GET /api/settings` | tous les réglages §34.3, valeur effective (stockée ou défaut) |

**Endpoints — écriture** :

| Méthode · chemin | Corps | Réponse |
|---|---|---|
| `PUT /api/read/{kind}/{id}` | — | 204 |
| `DELETE /api/read/{kind}/{id}` | — | 204 |
| `POST /api/read/bulk` | filtres du Feed + `until` | `{"marked": n, "remaining": bool}` |
| `PUT /api/preferences/{subject_type}/{subject_id}` | `{"action": "follow" \| "mute"}` | 204 |
| `DELETE /api/preferences/{subject_type}/{subject_id}` | — | 204 (retour au neutre) |
| `PUT /api/settings/{key}` | `{"value": …}` | 204 · 422 si hors schéma |
| `POST /api/emerging/{id}/decision` | `{"decision": "follow" \| "ignore" \| "mute" \| "create_topic"}` | 204 · 409 si `create_topic` déjà posé |
| `POST /api/articles/{id}/regenerate` | — | 202 `{"state": "queued" \| "already_active", "job_id": n}` |
| `POST /api/events/{id}/regenerate` | — | 202 idem · 409 si l'Event n'est pas éligible (§31.9.2) |
| `POST /api/jobs/{id}/retry` | — | 204 · 409 si plus en `dead_letter` |
| `POST /api/jobs/{id}/cancel` | — | 204 · 409 si plus en `dead_letter` |

**`POST /api/read/bulk`** : écrit les `ReadState` des stories correspondantes d'`activity_at ≤ until`, par lots de 500 dans des transactions séparées, **5 000 au plus par requête** ; `remaining = true` invite la SPA à rappeler. Sans aucun filtre, c'est la même opération sur toutes les stories non lues.

## 32. Auth dashboard

Mono-utilisateur. **Un seul mécanisme : basic_auth Caddy.** Le `DASHBOARD_TOKEN` de la V0.3 est abandonné.

### 32.1 Périmètre protégé

| Chemin | Accès |
|---|---|
| `/` (SPA statique) · `/api/*` | **basic_auth** |
| `/health` | **public**, réponse minimale `{"status": "ok" \| "degraded" \| "down"}` |
| Détail de santé (composants, `last_backup`…) | derrière l'auth : `GET /api/health` (Partie VII §40.3) |

- Identifiant et **hash bcrypt** fournis par l'environnement (`DASHBOARD_USER`, `DASHBOARD_PASSWORD_HASH`), injectés dans le `Caddyfile`. Jamais de mot de passe en clair dans le dépôt.
- Mot de passe **aléatoire d'au moins 20 caractères**. Pas de limitation de tentatives en V1 : la longueur suffit pour un usage mono-utilisateur.
- **Rotation** : nouveau hash dans l'environnement, redémarrage de `caddy`.
- Les logs Caddy **n'enregistrent pas** l'en-tête `Authorization` (Partie VII §42).

### 32.2 Anti-CSRF

Le navigateur renvoie automatiquement les identifiants basic_auth, y compris sur une requête forgée par un autre site. L'app refuse donc (403) toute requête **non `GET`** qui ne satisfait pas les trois conditions :

1. `Content-Type: application/json` (les requêtes sans corps envoient `{}`) ;
2. en-tête `X-Radar-Client: 1` ;
3. en-tête `Origin` égal à `DASHBOARD_URL` (s'il est présent).

Pas de CORS : l'app et la SPA sont servies par la même origine. Aucun en-tête `Access-Control-Allow-*` n'est émis.

### 32.3 Jamais exposé

- **Base SQLite** : volume local, aucun accès réseau (Partie III §10.4).
- **Ports de `app` et `worker`** : jamais publiés ; `app` n'écoute que sur le réseau Docker interne, derrière Caddy.
- **`/docs`, `/redoc`, `/openapi.json`** : désactivés en production (`docs_url = None`).
- **Secrets** (clés LLM, SMTP, Telegram, hash d'auth) : jamais renvoyés par l'API, jamais stockés dans `Setting`. `GET /api/settings` ne contient que des réglages fonctionnels.

## 33. Alerts

### 33.1 Principes

- Les alertes sont **émises par le worker**, jamais par l'app (Partie II §8.3).
- **Tous les déclencheurs sont déterministes** : ils ne dépendent d'aucun résultat LLM. Un contenu enrichi est utilisé s'il existe, le repli sinon.
- **V1 sans reprise** : un échec d'envoi est journalisé, compté, affiché ; jamais rejoué (outbox → V2).
- **Au plus une fois** : une alerte n'est jamais émise deux fois sur un même canal (§33.5).
- **Composant** : tick `alerts.tick` (60 s) du scheduler, qui évalue les alertes instantanées puis l'échéance des digests. Il relit les `Setting` et les `UserPreference` à chaque passage.

### 33.2 Canaux

| Canal | Variables d'environnement | Format |
|---|---|---|
| `email` | `SMTP_HOST` · `SMTP_PORT` · `SMTP_USER` · `SMTP_PASSWORD` · `SMTP_FROM` · `ALERT_EMAIL_TO` | sujet + `text/plain` + `text/html` échappé |
| `telegram` | `TELEGRAM_BOT_TOKEN` · `TELEGRAM_CHAT_ID` | texte brut, **sans `parse_mode`**, tronqué à 4 096 caractères |

- **Canal non configuré** (variable manquante) → canal désactivé, log `warning` au démarrage, état exposé au monitoring. Le worker démarre quand même. Une alerte routée vers un canal désactivé n'est pas écrite dans `AlertLog`.
- Timeout d'envoi : 10 s. Toujours **hors transaction** (§33.5).
- Chaque alerte contient un lien vers le dashboard (`DASHBOARD_URL`), par exemple `<DASHBOARD_URL>/events/<id>`.
- Les sorties LLM sont échappées (HTML de l'email) ou envoyées en texte brut (Telegram).

### 33.3 Types et déclencheurs

| Type | Sujet | Déclencheur |
|---|---|---|
| `important_event` | Event | voir ci-dessous |
| `emerging_topic` | candidat | candidat en `follow`, non muet, avec `last_significant_at > decided_at` (évolution significative postérieure au suivi, V-B §30.5) |
| `daily_digest` | jour | §33.7 |
| `weekly_digest` | semaine | §33.7 |
| `system` | condition d'exploitation | début d'un épisode d'une condition de la table Partie VII §39.5, émise par `ops.tick` (Partie VII §39.6) |

**`important_event`** — toutes les conditions :

1. Event `active` ;
2. `round(importance × 100) ≥ alerts.importance_threshold`, ou `≥ alerts.followed_threshold` si la story est **suivie** (§34.2) ;
3. `last_seen_at ≥ now − alerts.max_age` (48 h) — une baisse de seuil ou un premier run ne déclenchent pas de rafale sur l'historique ;
4. story **non masquée** par une sourdine — même fonction que l'affichage (§34.2) ;
5. pas déjà alertée, **y compris sous un Event fusionné** : l'Event est réputé alerté s'il existe une alerte pour lui **ou** pour un Event dont la chaîne `merged_into_id` aboutit à lui ;
6. **attente du titre** : si `title_origin = fallback` et que le disjoncteur LLM est `closed`, l'alerte attend au plus `alerts.title_wait` (30 min) après que les conditions 1–5 sont vraies pour la première fois, puis part avec le titre disponible. Disjoncteur ouvert ou LLM non configuré → envoi immédiat avec le repli.

- Un **article isolé** ne déclenche jamais `important_event`.
- La première satisfaction des conditions est mémorisée en mémoire du worker ; après un redémarrage, l'attente repart de zéro, bornée par `max_age`.

### 33.4 Clés de déduplication

`AlertLog.dedup_key` est **UNIQUE** et **inclut le canal** :

| Type | `dedup_key` |
|---|---|
| `important_event` | `important_event:{event_id}:{channel}` |
| `emerging_topic` | `emerging:{candidate_id}:{last_significant_at}:{channel}` |
| `daily_digest` | `daily:{date locale AAAA-MM-JJ}:{channel}` |
| `weekly_digest` | `weekly:{année ISO}-W{semaine ISO}:{channel}` |
| `system` | `system:{condition}:{since}:{channel}`, `since` = début de l'épisode |

`{event_id}` est l'Event **cible** au moment de l'envoi. La condition 5 du §33.3 couvre les fusions postérieures.

### 33.5 Séquence d'envoi

```
T1  (BEGIN IMMEDIATE)  INSERT AlertLog(status='sending', dedup_key…) ON CONFLICT DO NOTHING
                       → conflit : l'alerte existe déjà, on s'arrête
    (hors transaction) envoi sur le canal, timeout 10 s
T2  (BEGIN IMMEDIATE)  UPDATE AlertLog SET status = 'sent' | 'failed', error = …
```

- **Garantie au plus une fois** : le log précède l'envoi. Un crash entre T1 et T2 perd l'alerte, ce qui est cohérent avec « V1 sans reprise ».
- **Au démarrage du worker** : toute ligne `sending` passe en `failed`, `error = 'interrupted'`.
- **Échec d'envoi** : `failed` + `error`, passé par le nettoyage des secrets par valeur (Partie VII §42.4), log structuré, métrique par type et par canal. Jamais rejoué.
- Aucune requête réseau dans une transaction (Partie IV §14.2).

### 33.6 Fréquence

Pilotée par les `Setting` du §34.3 :

- **Mode** `alerts.mode` : `immediate` (défaut) ou `digest_only`. En `digest_only`, aucune alerte instantanée (`important_event`, `emerging_topic`) n'est évaluée ; les digests continuent.
- **Heures calmes** `alerts.quiet_hours` (`{start, end}` en heure locale, ou `null`) : aucune alerte instantanée n'est émise pendant la plage. À la sortie, les conditions sont réévaluées normalement ; `max_age` borne ce qui est encore envoyé. Les digests ne sont pas concernés.
- **Plafond** `alerts.max_per_day` (20) : nombre d'alertes instantanées distinctes (sujets, tous canaux confondus) par jour local. Au-delà, l'alerte est écrite avec `status = suppressed` (sans envoi) : elle ne sera jamais émise, et reste visible dans l'historique. Ses stories apparaissent dans le digest suivant.
- **Alertes `system`** : hors de ces réglages. Ni le mode, ni les heures calmes, ni le plafond ne s'y appliquent, et elles ne comptent pas dans le plafond (Partie VII §39.6).

### 33.7 Digests

**Déclenchement** : par le tick d'alertes, pas par un cron.

```
daily  : digest.daily.enabled
         ET heure locale ≥ digest.daily.time
         ET aucune ligne AlertLog pour daily:{date locale}:{channel}
weekly : digest.weekly.enabled
         ET jour local = digest.weekly.day ET heure locale ≥ digest.weekly.time
         ET aucune ligne pour weekly:{semaine ISO}:{channel}
```

- Un changement d'horaire ou de fuseau est pris en compte au tick suivant.
- **Worker arrêté à l'heure prévue** : le digest part au redémarrage s'il a lieu le même jour local (ou le même jour de semaine pour le weekly) ; sinon il est sauté. Jamais de rafale.

**Contenu** (fenêtre = 24 h ou 7 j se terminant au déclenchement) :

1. **Stories importantes** : `digest.max_items` (10) stories non masquées, `activity_at` dans la fenêtre, importance ≥ `display.importance_threshold`, triées par importance ↓ ;
2. **Suivis** : stories suivies de la fenêtre (10 au plus) ;
3. **Nouveaux sujets émergents** : candidats sans décision, `first_detected_at` dans la fenêtre ;
4. **Topics en tendance** : topics `trending` / `rising` (dernier `Signal` `7d`), non muets.

- Une story présente dans la section 1 n'est pas répétée dans la section 2.
- **Digest vide** (les quatre sections vides) : non envoyé, aucune ligne `AlertLog`.
- Les nouveaux candidats émergents sans décision ne font **jamais** l'objet d'une alerte instantanée : ils passent par les digests.

### 33.8 Contenu d'une alerte instantanée

- **`important_event`** : titre (repli ou enrichi), aperçu, hotness (« N sources · M canaux »), importance, trois sources au plus, lien vers l'Event.
- **`emerging_topic`** : libellé (`llm_label` ou `label`), croissance, sources, canaux, lien vers la liste des sujets émergents.

### 33.9 Routage

`alerts.routing` associe chaque type à une liste de canaux. Défaut : `important_event` et `emerging_topic` → `telegram` ; `daily_digest` et `weekly_digest` → `email` ; `system` → `[telegram, email]`, pour qu'un canal en panne ne rende pas l'exploitation aveugle. Un type routé vers une liste vide est désactivé.

### 33.10 Historique et test

- **Historique** : `GET /api/alerts` expose `AlertLog` (type, sujet, canal, statut, erreur, date), avec lien vers le sujet.
- **Alerte de test** : commande worker `python -m app.cli send-test-alert --channel <email|telegram>`. Elle envoie un message fixe, hors `AlertLog`, et affiche le résultat. Pas de bouton dans le dashboard : l'app n'émet jamais.

## 34. Préférences utilisateur

### 34.1 `UserPreference`

- `subject_type ∈ {topic, source}`, `action ∈ {follow, mute}`, `UNIQUE(subject_type, subject_id)` : **suivi et sourdine sont exclusifs**. Poser l'un remplace l'autre (upsert) ; supprimer la ligne ramène au neutre.
- Écrite par l'app seule ; lue par l'app (affichage) et par le worker (alertes).
- **La sourdine ne coupe jamais la collecte ni les calculs** : une source muette reste collectée (`enabled` vit dans `sources.yaml`) ; un topic muet a ses `Signal` normalement (V-B §29.7) ; les compteurs d'Event et la hotness incluent les sources muettes.

### 34.2 État effectif et effet

**Topic — héritage** : l'état effectif d'un topic est sa propre préférence, à défaut celle de l'**ancêtre le plus proche** qui en a une, à défaut neutre. Un `follow` explicite sur un descendant l'emporte donc sur la sourdine d'un parent, et inversement.

**Source** : pas de hiérarchie ; l'état effectif est la préférence de la source.

**Masquage d'une story** — la story est masquée si **au moins une** des deux conditions est vraie :

1. **tous** ses membres `ready` proviennent de sources à l'état effectif `mute` ;
2. elle a au moins un topic, et **tous** ses topics (union `keyword` + `llm`) sont à l'état effectif `mute`.

Une story où ne se trouve qu'une partie de sources ou de topics muets reste affichée. Les compteurs affichés ne sont pas recalculés.

**Suivi d'une story** : la story est suivie si **au moins un** membre provient d'une source suivie, ou si **au moins un** de ses topics est à l'état effectif `follow`. Le masquage l'emporte sur le suivi.

Ces deux fonctions sont **uniques** et partagées : l'app les applique à l'affichage, le worker aux alertes. Leur implémentation vit dans un module commun, testé une seule fois.

| Préférence | Affichage | Alertes | Calculs |
|---|---|---|---|
| **follow** topic / source | filtre et section « Suivis » ; marqueur sur les stories | seuil `alerts.followed_threshold` pour `important_event` ; section « Suivis » des digests | aucun effet |
| **mute** topic / source | stories masquées (§34.2) ; topic retiré de Trending ; toggle « afficher les masqués » | stories masquées exclues de `important_event` et des digests ; topic muet exclu des topics en tendance du digest | aucun effet |

Les décisions sur les sujets émergents (`EmergingDecision`) sont une table distincte : muter un candidat n'est pas muter un topic.

### 34.3 `Setting`

Registre **en code** : pour chaque clé, un schéma Pydantic et un défaut. Une clé absente de la table vaut son défaut ; une valeur stockée invalide est ignorée au profit du défaut, avec un log `warning`. L'API valide à l'écriture (422). Le worker relit les réglages à chaque tick.

| Clé | Type | Défaut | Rôle |
|---|---|---|---|
| `timezone` | nom IANA | `Europe/Paris` | affichage, heures calmes, digests |
| `display.importance_threshold` | entier 0–100 | 0 | filtre par défaut du Feed, section Important, digests |
| `alerts.mode` | `immediate` \| `digest_only` | `immediate` | §33.6 |
| `alerts.importance_threshold` | entier 0–100 | 50 | §33.3 |
| `alerts.followed_threshold` | entier 0–100 | 25 | §33.3 |
| `alerts.max_age` | heures | 48 | §33.3 |
| `alerts.title_wait` | minutes | 30 | §33.3 |
| `alerts.quiet_hours` | `{start, end}` \| `null` | `null` | §33.6 |
| `alerts.max_per_day` | entier | 20 | §33.6 |
| `alerts.routing` | type → liste de canaux | §33.9 | §33.9 |
| `digest.daily` | `{enabled, time}` | `{true, "08:00"}` | §33.7 |
| `digest.weekly` | `{enabled, day, time}` | `{true, "monday", "08:00"}` | §33.7 |
| `digest.max_items` | entier | 10 | §33.7 |

**Repères pour régler les seuils** (formule V-B §28.9, poids par défaut) : un article isolé plafonne à **25** ; un Event à 2 sources sur 2 canaux vaut environ **25** ; à 4 sources sur 3 canaux, environ **50**. Un seuil d'alerte de 50 signifie donc, en pratique, « au moins environ 4 sources sur plusieurs canaux ».

`alerts.tick` et `alerts.send_timeout` sont des réglages techniques : ils vivent dans `pipeline.yaml`, pas dans `Setting`.

### 34.4 Personnalisation automatique future

Hors V1 (Partie I §5.1). La structure le permet sans refonte : une personnalisation automatique produirait des préférences d'une **autre origine**, soumises à la règle **préférence utilisateur > préférence automatique**. La colonne `origin` de `UserPreference` sera ajoutée à ce moment-là ; rien n'est anticipé en V1.

---

## Reporté en V2 (tracé depuis la Partie VI)

- **Outbox et reprise des alertes** (déjà reporté par la Partie II).
- **Mise à jour temps réel** du dashboard (WebSocket / SSE) à la place du polling.
- **Rendu markdown** des sorties LLM.
- **Indexation plein texte** des titres et descriptions d'Event.
- **Ré-ouverture fine** d'un Event lu sur la date de découverte des membres, et **héritage de l'état lu** des articles isolés qui rejoignent un Event.
- **Alerte instantanée** sur les nouveaux candidats émergents sans décision.
- **Suppression d'une décision** sur un candidat émergent.
- **Bouton d'alerte de test** dans le dashboard.
- **Limitation des tentatives d'authentification** et auth plus riche (sessions, multi-utilisateur — non-objectif).
- **Colonne `origin`** de `UserPreference` et personnalisation automatique (déjà reportée par la Partie I).
- **Digests par topic** ou par source.
- **Recherche sémantique** (déjà reportée par la Partie I).
