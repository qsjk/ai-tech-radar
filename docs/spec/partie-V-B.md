# Partie V-B — Intelligence : clustering, trends & sujets émergents

2026-09-22

> **Partie V-B — Clustering, trends & sujets émergents.** Version durcie issue de la revue §28–§30.
> Remplace les §28 à §30 de SPEC.md V0.3. Prend les Parties I, II, III, IV et V-A durcies comme acquis.

> **Déjà tranché ailleurs, non repris ici** : couche cœur déterministe sans LLM (Partie II §6) ; Event créé sans LLM avec titre de repli, `resolve_event` qui enrichit sans toucher à l'appartenance ni aux compteurs (Partie II §7.3, V-A §27.3) ; un calcul cosine, deux seuils (Partie II décision 4, restreinte ici) ; fenêtre glissante en mémoire, ligne `Embedding` à vecteur `NULL` exclue (Partie III §12.4, V-A §24.4) ; liaisons `method=keyword` produites par le relevance filter (Partie IV §20.4) ; catalogue et gardes des jobs LLM (V-A §23) ; rattachement déterministe de l'historique à un topic créé (V-A §24.6, précisé ici).

---

## Décisions tranchées dans cette revue (Partie V-B)

Les points marqués **(proposé)** n'ont pas été discutés explicitement : ils découlent des décisions validées et sont à confirmer à la relecture.

1. **`duplicate` rétroactif restreint à la même source.** Cosine ≥ seuil haut **et** même `source_id` **et** titres normalisés égaux. Entre sources différentes, deux textes quasi identiques vont dans le **même Event**, jamais en `duplicate` : un post HN ou Reddit dont le contenu est le billet extrait reste une source distincte. Restreint la décision 4 de la Partie II.
2. **Même source ⇒ URL croisée uniquement.** Deux articles d'une même source ne sont candidats au même Event que par URL croisée, jamais par cosine ni par entités. Empêche les releases successives d'un dépôt de former un Event unique.
3. **Entités discriminantes.** Le critère « ≥ N entités communes » ne compte que les liaisons `keyword` dont la fréquence documentaire dans la fenêtre est faible. Anthropic ou Claude Code, présents partout, ne relient rien.
4. **URL « hub » ignorées** par le critère URL croisée : racines de domaine, racines d'owner GitHub, liste `clustering.url_ignore`.
5. **Fenêtre indexée sur `discovered_at`**, avec contrôle de proximité sur `published_at` (≤ 72 h) et **durée maximale d'un Event** (`event_max_span`, 7 j).
6. **Clustering séquentiel, déclenché par deux voies** : après chaque lot d'embeddings, et par un tick pour les articles sans embedding au-delà de `embedding_wait` (5 min) ou moteur `down`. Seconde passe cosine unique pour un article d'abord évalué sans vecteur. Latence ≤ 6 min, sous `llm.delay.enrich_article`.
7. **Un Event naît à deux articles.** Un article sans candidat reste hors Event (`event_id` NULL).
8. **Fusion d'Events seulement sur liens forts** (URL ou cosine). Un lien par entités seules ne fait que rattacher, au meilleur Event.
9. **Compteurs toujours recalculés** depuis les membres dans la transaction de rattachement, jamais incrémentés.
10. **Représentant = membre `ready` le plus ancien par `published_at`.** À chaque changement, le titre de repli suit et un `enrich_article` est créé si le nouveau représentant n'est pas enrichi.
11. **Déclenchement de `resolve_event` par marqueur** `Event.resolve_enqueued_count` : robuste aux fusions et idempotent.
12. **`archived` = inactif depuis 7 j**, purement informatif (aucun effet sur les rattachements).
13. **`Event.importance` indépendante du temps**, dans [0, 1] : sources, canaux, engagement, source de confiance. **`Event.novelty` supprimé.**
14. **`rss` et `webpage` = un seul canal `web`.** Chaque collector déclare son canal dans le registre.
15. **Signal horaire**, upsert sur `(topic_id, period, window_end)`, sans rattrapage des heures manquées.
16. **Mentions sur `published_at`, liaisons `keyword` uniquement, articles `ready` hors doublons.** Un parent agrège l'**union distincte** de ses descendants au calcul.
17. **Cold start explicite** : `growth_rate`, `momentum` et `novelty` valent `NULL` tant que la couverture de données ne permet pas de les calculer.
18. **Catégorie `emerging` renommée `rising`** pour lever la collision avec les sujets émergents du §30. `category` `NULL` = support insuffisant.
19. **Termes émergents = n-grammes (1 à 3) des titres + dépôts GitHub**, calculés en mémoire sur 37 jours, **titres seulement** (le résumé est écrasé par le LLM).
20. **Critère « multi-histoires »** : un terme doit apparaître dans au moins deux Events ou articles isolés distincts. Un lancement unique ne fait pas un topic.
21. **Évolution significative** = doublement des mentions ou nouveau canal depuis la dernière référence, au plus une fois par 24 h. Elle pilote `discover_topics`, la réapparition des candidats ignorés et les alertes des candidats suivis.
22. **Sémantique des décisions** : `follow` (suivi et alertes) · `ignore` (masqué, réapparaît sur évolution significative) · `mute` (jamais reproposé) · `create_topic`.
23. **« Create topic » direct en V1**, à partir des suggestions, sans formulaire d'édition. **(proposé)**
24. **Backfill d'un topic créé sur titre + résumé de repli uniquement** : un résumé `llm` n'est pas une entrée déterministe. Corrige V-A §24.6. **(proposé)**
25. **La taxonomie du runner inclut les topics `user` de la base.** Sans cela, un topic créé n'aurait aucune liaison sur les nouveaux articles. **(proposé — impact Partie IV)**

---


## 28. Event clustering

Regrouper les articles du **même événement** pour qu'un événement multi-sources n'apparaisse qu'une fois (Partie I, fonction 4) et porter la **hotness** (`distinct_source_count`). Étage entièrement **cœur** : aucun appel LLM, aucune lecture d'un résultat LLM.

### 28.1 Contrat de l'étage

| | |
|---|---|
| **Entrée** | articles `ready` non encore évalués (`clustered_at IS NULL`) ou en attente de seconde passe cosine (§28.2) ; fenêtre en mémoire (§28.3) ; liaisons `ArticleEntity` `method=keyword` ; `Article.canonical_url` / `canonical_link_url` |
| **Sortie** | `Article.event_id` · `Article.status = duplicate` + `duplicate_of_id` · `Event` créés, mis à jour ou fusionnés · `AIJob` `resolve_event` et `enrich_article` (représentant) |
| **Tables écrites** | `Article` (`event_id`, `status`, `duplicate_of_id`, `clustered_at`, `clustered_semantic`, `importance`) · `Event` · `AIJob` |
| **Ne lit jamais** | `ArticleTopic` / `ArticleEntity` `method=llm`, `Article.summary` d'origine `llm`, `Event.title` / `description` d'origine `llm` (hormis la copie de titre lors d'une fusion, §28.6) |
| **Exécution** | composant **séquentiel unique** du worker : un seul article évalué à la fois, jamais deux passes de clustering concurrentes. Calcul cosine hors event-loop (Partie II §8.4) |

### 28.2 Déclenchement et cadence

Deux colonnes sur `Article` :

- `clustered_at` (nullable) : posé quand l'article a été évalué au moins une fois ;
- `clustered_semantic` (booléen, défaut `false`) : posé quand le critère cosine a été évalué pour cet article.

**Voie 1 — après chaque lot d'embeddings validé** (V-A §24.4) : les articles du lot sont évalués, dans l'ordre `discovered_at` croissant, **avec tous les critères**.

**Voie 2 — tick `clustering.tick` (60 s)** :

```sql
-- première évaluation, sans vecteur
SELECT a.id FROM article a
WHERE a.status = 'ready' AND a.clustered_at IS NULL
  AND (a.discovered_at <= :now - :embedding_wait      -- 5 min
       OR :embeddings_state = 'down')
ORDER BY a.discovered_at ASC
LIMIT :batch_size;

-- seconde passe cosine : article évalué sans vecteur, vecteur arrivé depuis
SELECT a.id FROM article a
JOIN embedding e ON e.article_id = a.id AND e.model = :model AND e.vector IS NOT NULL
WHERE a.status = 'ready' AND a.clustered_at IS NOT NULL
  AND a.clustered_semantic = 0
  AND a.discovered_at >= :now - :window
LIMIT :batch_size;
```

- Un article évalué sans vecteur l'est sur les critères URL et entités. Si son vecteur arrive tant qu'il est dans la fenêtre, il reçoit **une seule** seconde passe, limitée au cosine (et à la dédup rétroactive).
- Une ligne `Embedding` à vecteur `NULL` (échec définitif) ne déclenche jamais de seconde passe.
- **Latence maximale** d'une première évaluation ≈ `embedding_wait` + `tick` = 6 min, **inférieure à `llm.delay.enrich_article`** (15 min) : la garde `event_member` voit des articles déjà regroupés.
- Un article évalué tard (arriéré d'embeddings) peut rejoindre un Event après que son `enrich_article` a été exécuté : c'est un appel LLM perdu, pas une incohérence.

### 28.3 Fenêtre

- **Membres de la fenêtre** : articles `ready`, `discovered_at ≥ now − clustering.window` (72 h). L'éviction est monotone.
- **Matrice cosine en mémoire** : les membres de la fenêtre ayant un vecteur non `NULL` du modèle courant. Un article passé en `duplicate` en est retiré. Reconstruite depuis la base au démarrage (acquis).
- **Proximité temporelle** : un candidat Y n'est retenu que si `|X.published_at − Y.published_at| ≤ clustering.window`. Neutralise le premier run d'une source, qui ingère d'un coup des items vieux de 30 jours.
- Chaque paire est évaluée **une fois**, quand le plus récemment évalué des deux articles passe au clustering.

### 28.4 Génération des candidats

Pour l'article X évalué, Y est **candidat** s'il est membre de la fenêtre (§28.3), `Y ≠ X`, et vérifie au moins un critère :

| Critère | Définition | Force |
|---|---|---|
| **U — URL croisée** | l'une des égalités `X.canonical_link_url = Y.canonical_url` · `X.canonical_url = Y.canonical_link_url` · `X.canonical_link_url = Y.canonical_link_url` (valeurs non nulles, hors URL ignorées) | forte |
| **S — cosine** | `cosine(X, Y) ≥ clustering.cosine_median` (0,80), X et Y ayant un vecteur ; seuls les `clustering.top_k` (5) meilleurs voisins sont retenus | forte, ordonnée par score |
| **E — entités** | au moins `clustering.min_common_entities` (2) entités communes, liaisons `method=keyword` uniquement, **toutes discriminantes** | faible |

**URL ignorées** par le critère U :

- chemin vide ou `/` (racine d'un domaine) ;
- `github.com/{owner}` sans nom de dépôt ;
- toute URL dont le préfixe figure dans `clustering.url_ignore`.

**Entité discriminante** : entité dont la fréquence documentaire parmi les membres de la fenêtre est `≤ max(entity_max_df_min, entity_max_df_ratio × taille de la fenêtre)` (5 · 2 %). La fréquence est calculée une fois par passe et mise en cache pour la passe.

**Règle même source** : si `X.source_id = Y.source_id`, seul le critère **U** est évalué. Deux releases successives d'un dépôt, deux billets d'un même blog, ne se regroupent jamais par similarité.

**Évaluation par la voie 1 ou la seconde passe** : U et E sont évalués à la première évaluation seulement ; la seconde passe n'évalue que S.

### 28.5 Rattachement et création

Après la dédup rétroactive (§28.7), à partir de l'ensemble des candidats de X :

1. Chaque candidat est ramené à son Event (`event_id`), ou marqué **isolé** s'il n'en a pas.
2. **Events éligibles** : `status = active` et `X.published_at − Event.first_seen_at ≤ clustering.event_max_span` (7 j). Un candidat appartenant à un Event non éligible est **ignoré** : il n'est ni réaffecté, ni utilisé pour relier X.
3. Chaque Event éligible est qualifié de **fort** s'il est atteint par au moins un candidat U ou S, **faible** s'il n'est atteint que par E.
4. Décision :

| Situation | Action |
|---|---|
| aucun candidat retenu | X reste hors Event ; `clustered_at` posé |
| uniquement des isolés | **création** d'un Event avec X et tous les isolés candidats |
| exactement un Event fort | X et les isolés candidats y sont **rattachés** |
| au moins deux Events forts | **fusion** des Events forts (§28.6), puis rattachement de X et des isolés à la cible |
| aucun Event fort, au moins un faible | rattachement au **meilleur** Event faible : plus grand nombre d'entités discriminantes communes, puis `id` le plus petit. Les autres Events faibles ne sont pas touchés |

- Les Events faibles ne sont **jamais** fusionnés.
- Toute l'opération (rattachements, création ou fusion, recalcul §28.9, jobs §28.10, `clustered_at` / `clustered_semantic`) tient dans **une transaction** `BEGIN IMMEDIATE`.
- La transaction **relit** l'état des Events concernés : un Event passé en `merged` depuis le calcul est remplacé par sa cible (chaîne `merged_into_id`).
- Création : `title_origin = fallback`, `title` = titre du représentant (§28.8), `description` `NULL`, `status = active`.

### 28.6 Fusion d'Events

- **Cible** : l'Event au `first_seen_at` le plus ancien, puis l'`id` le plus petit.
- Chaque Event source passe en `status = merged`, avec `merged_into_id` = cible. Ses articles reçoivent `event_id` = cible.
- **Titre de la cible** : conservé. Seule exception : cible en `title_origin = fallback` et au moins une source en `llm` → la cible reprend `title` et `description` de la source `llm` la plus grande (`article_count`), avec `title_origin = llm`. C'est une copie de valeur, pas une décision structurante.
- Compteurs, représentant et importance de la cible **recalculés** (§28.9).
- Les jobs `resolve_event` actifs des Events sources sont sautés à l'exécution (`event_not_active`, acquis). Le déclenchement vise la cible (§28.10).
- Aucune fusion n'est défaite en V1.

### 28.7 Dédup rétroactive au seuil haut

Évaluée dès que le cosine est calculé (voie 1 ou seconde passe), **avant** le rattachement.

Une paire (X, Y) est un **doublon sémantique** si les trois conditions sont vraies :

1. `cosine(X, Y) ≥ clustering.cosine_high` (0,95) ;
2. `X.source_id = Y.source_id` ;
3. `norm(X.title) = norm(Y.title)` (normalisation Partie IV §20.2).

- L'article de plus grand `(discovered_at, id)` passe en `duplicate`, avec `duplicate_of_id` = l'autre.
- Il **conserve** son `event_id` éventuel, ses topics et son résumé (acquis), mais **sort** des compteurs, de la matrice cosine et de la représentation. Son `enrich_article` éventuel est sauté (`article_not_ready`, acquis).
- Si c'est X qui devient `duplicate`, son évaluation s'arrête là. Si c'est Y, l'évaluation de X continue sans Y, et l'Event de Y est recalculé dans la même transaction.
- **Entre sources différentes**, un cosine ≥ seuil haut n'est qu'un candidat S : même Event, deux sources distinctes, hotness intacte.
- Un Event peut, après doublons, ne compter qu'un seul membre `ready`. Il est conservé.

### 28.8 Représentant

- **Représentant** = membre `ready` de plus petit `(published_at, id)`.
- Recalculé à chaque recalcul de l'Event. Il ne change que sur fusion, sur passage d'un membre en `duplicate`, ou à l'arrivée d'un article publié plus tôt.
- **À chaque changement de représentant**, dans la même transaction :
  - si `title_origin = fallback` : `title` = titre du nouveau représentant ;
  - si le nouveau représentant a `summary_origin = fallback` : création d'un `enrich_article` (paramètres du registre V-A §23.2, `created_by = worker`). S'il existe déjà un job actif, l'insertion est ignorée (index unique partiel acquis). Sans cette règle, un article dont le job a été sauté en `event_member` ne serait jamais enrichi.

### 28.9 Compteurs et importance

Recalculés **depuis les membres**, jamais incrémentés, dans chaque transaction qui modifie l'Event :

| Colonne | Calcul |
|---|---|
| `article_count` | membres `ready` |
| `distinct_source_count` | `source_id` distincts parmi les membres `ready` (**hotness**) |
| `distinct_channel_count` | canaux distincts parmi les membres `ready` (table ci-dessous) |
| `first_seen_at` · `last_seen_at` | min · max de `published_at` des membres `ready` |
| `representative_article_id` | §28.8 |
| `importance` | formule ci-dessous |

**Canal d'une source** : déclaré par le collector dans le registre, en code.

| `Source.type` | Canal |
|---|---|
| `rss` · `webpage` | `web` |
| `github` | `github` |
| `hackernews` | `hackernews` |
| `reddit` | `reddit` |
| `youtube` | `youtube` |

**Importance** — indépendante du temps, dans [0, 1] :

```
S = min(1, log2(distinct_source_count) / 3)              1 → 0 · 2 → 0,33 · 4 → 0,67 · 8+ → 1
C = min(1, (distinct_channel_count − 1) / 3)             1 → 0 · 2 → 0,33 · 4+ → 1
E = max sur les membres ready de :
      HN       min(1, log10(1 + points) / log10(1 + 500))
      YouTube  min(1, log10(1 + views)  / log10(1 + 100 000))
      autres   0                                          métrique absente → 0
O = 1 si un membre ready vient d'une source relevance: always, sinon 0

importance = w_S·S + w_C·C + w_E·E + w_O·O               défauts 0,50 · 0,25 · 0,15 · 0,10
```

- **Limite assumée** : `Article.metrics` est un instantané pris à la collecte (Partie IV), donc faible pour un item capté tôt. D'où le poids réduit de E ; il n'a de portée réelle que pour les sources HN `front_page`.
- La **récence** n'entre pas dans l'importance : elle relève du tri à l'affichage. Aucun recalcul périodique n'est nécessaire.
- **Article hors Event** **(proposé)** : la même formule, appliquée à l'article seul (S = C = 0), est écrite dans `Article.importance` à chaque évaluation. Un article qui rejoint un Event garde sa valeur, mais c'est celle de l'Event qui s'affiche. Permet le filtre « Importance » du fil en SQL.
- **`Event.novelty` est supprimé** : c'était une fonction du temps, calculable à la lecture depuis `first_seen_at`.

**Invariant** (acquis, étendu) : `article_count`, `distinct_source_count` et `distinct_channel_count` égalent leur recalcul depuis les membres `ready`. Testé, et contrôlable par la commande `python -m app.cli recount-events`, qui corrige et journalise tout écart.

### 28.10 Déclenchement de `resolve_event`

Nouvelle colonne `Event.resolve_enqueued_count` (entier, nullable) : `article_count` au dernier enqueue.

Dans chaque transaction qui modifie un Event `active` :

```
si distinct_source_count ≥ 2 et
   ( resolve_enqueued_count IS NULL
     ou ⌊log2(article_count)⌋ > ⌊log2(resolve_enqueued_count)⌋ ) :
    insérer resolve_event (cible = cet Event)   -- ignoré si un job actif existe (index acquis)
    resolve_enqueued_count = article_count
```

- Premier job à 2 sources, puis à 4, 8, 16… articles (V-A §23.2), y compris quand une fusion fait sauter plusieurs paliers d'un coup : un seul job.
- Si un job actif existe déjà, le marqueur est quand même mis à jour : le job lit l'état courant de l'Event à son exécution.
- Sur fusion, seul l'Event **cible** est évalué.

### 28.11 Cycle de vie de l'Event

| Statut | Condition | Effet |
|---|---|---|
| `active` | création | accepte des rattachements tant qu'il est éligible (§28.5) |
| `merged` | fusion (§28.6) | terminal ; `merged_into_id` renseigné |
| `archived` | `last_seen_at < now − clustering.archive_after` (7 j), passe horaire (§29.4) | **informatif** : filtre d'affichage. Aucun effet sur les rattachements, déjà bornés par la fenêtre et `event_max_span` |

`archive_after` (7 j) est supérieur ou égal au TTL de `resolve_event` (7 j) : un job en attente pendant une panne LLM n'est jamais perdu par l'archivage.

### 28.12 Mode dégradé

| Panne | Comportement |
|---|---|
| **Moteur d'embeddings `down`** | voie 2 immédiate (sans attendre `embedding_wait`) sur les critères U et E ; pas de dédup rétroactive ; seconde passe cosine au retour du moteur, pour les articles encore dans la fenêtre. **La hotness survit** (Partie II §9.1) |
| **Gateway LLM indisponible** | aucun effet : l'étage ne dépend d'aucun résultat LLM. Les `resolve_event` et `enrich_article` créés attendent (V-A §26) |
| **Worker redémarré** | matrice reconstruite ; les articles non marqués sont réévalués ; aucune double application (§28.13) |

### 28.13 Idempotence

- **Unité de travail** = un article, une transaction. `clustered_at` et `clustered_semantic` sont posés dans la transaction qui écrit les rattachements. Un crash avant le commit laisse l'article non marqué : il est réévalué, avec un résultat identique hors nouveaux arrivants.
- Réévaluer un article déjà marqué est un **no-op**.
- **Pas de recalcul complet** en V1 : l'appariement à lien unique dépend de l'ordre d'arrivée, un recalcul depuis zéro ne reproduirait pas les mêmes Events. Seuls les compteurs sont recalculables (`recount-events`).

### 28.14 Calibration

Les seuils sont des **points de départ** (Partie II). Commande `python -m app.cli cluster-calibrate` :

- histogramme des scores cosine des paires de la fenêtre courante, par tranche de 0,05 ;
- échantillon de paires par tranche (titres, sources), à relire à la main ;
- fréquence documentaire des entités keyword de la fenêtre, pour ajuster `entity_max_df_*`.

La calibration est **obligatoire avant la mise en production** (impact Partie VIII).

### 28.15 Réglages `clustering.*` dans `pipeline.yaml`

| Clé | Défaut | Section |
|---|---|---|
| `clustering.window` | 72 h | §28.3 |
| `clustering.cosine_high` · `cosine_median` | 0,95 · 0,80 | §28.4, §28.7 |
| `clustering.top_k` | 5 | §28.4 |
| `clustering.min_common_entities` | 2 | §28.4 |
| `clustering.entity_max_df_ratio` · `entity_max_df_min` | 0,02 · 5 | §28.4 |
| `clustering.url_ignore` | `[]` | §28.4 |
| `clustering.event_max_span` | 7 j | §28.5 |
| `clustering.embedding_wait` · `tick` · `batch_size` | 5 min · 60 s · 50 | §28.2 |
| `clustering.archive_after` | 7 j | §28.11 |
| `importance.weights` (`sources` · `channels` · `engagement` · `trusted`) | 0,50 · 0,25 · 0,15 · 0,10 | §28.9 |
| `importance.hn_points_ref` · `youtube_views_ref` | 500 · 100 000 | §28.9 |

`embedding_wait + tick` doit rester strictement inférieur à `llm.delay.enrich_article` : vérifié par `validate-config`.

## 29. Trend Engine

Produit les `Signal` par topic et par fenêtre. Étage **cœur** : sans LLM, sur liaisons `keyword` uniquement.

> **Ne pas confondre volume et croissance** (acquis).

### 29.1 Contrat

| | |
|---|---|
| **Entrée** | articles `ready` (hors `duplicate`) de `published_at ≥ window_end − 60 j`, leurs liaisons `ArticleTopic` et `ArticleEntity` `method=keyword`, `Source` ; topics `enabled` ; Signal précédent de chaque (topic, période) |
| **Sortie** | une ligne `Signal` par topic activé et par période ∈ {`24h`, `7d`, `30d`} |
| **Tables écrites** | `Signal` · `SystemState.trends_last_run` |
| **Ne lit jamais** | liaisons `method=llm` : une panne du gateway ne doit pas fabriquer un faux `declining` (V-A) |
| **Exécution** | lecture paginée, calcul en mémoire hors event-loop (Partie II §8.4), écriture par lots de `trends.write_batch` topics (20), une transaction par lot |

### 29.2 Assiette

Pour un topic *t*, **A(t)** = ensemble des articles distincts, `status = ready`, ayant une liaison `ArticleTopic` `method=keyword` vers *t* **ou vers un descendant activé** de *t*.

- **Hiérarchie** : un parent agrège l'**union distincte** de ses articles et de ceux de ses descendants, calculée au moment du calcul. Pas de somme (un article lié au parent et à un enfant compte une fois), et aucune propagation en base (Partie IV §20.4 inchangée).
- Les membres non représentatifs d'un Event, qui n'ont que des liaisons keyword, comptent normalement.
- Un article compte pour chaque topic de son assiette ; les articles d'un même Event comptent chacun (un événement très relayé fait monter ses topics).

Pour une fenêtre [`start`, `end`[ :

| Mesure | Définition |
|---|---|
| `mentions` | nombre d'articles de A(t) avec `published_at ∈ [start, end[` |
| `unique_sources` | `source_id` distincts parmi ces articles |
| `unique_authors` | couples (`source_id`, `norm(author)`) distincts ; un auteur `NULL` compte comme un auteur unique par source |
| `unique_companies` | entités de type `company`, liaisons `method=keyword`, distinctes parmi ces articles |

L'axe temporel est `published_at` : l'ajout d'une source ou un premier run ne créent pas de faux pic. Un article découvert tard modifie une fenêtre passée ; c'est sans effet de bord, chaque calcul repartant de la base.

### 29.3 Couverture et cold start

- **`SystemState.trends_since`** : horodatage de la première insertion d'un article `ready`, écrit une fois par le runner (impact Partie IV).
- **`coverage_since(t)`** :
  - topic `seeded` : `trends_since` ;
  - topic `user` issu d'un « Create topic » : `max(trends_since, Topic.created_at − topic_backfill.window)` ;
  - autres cas (`discovered`, inutilisé en V1) : `Topic.created_at`.
- Une valeur qui exigerait des données antérieures à `coverage_since(t)` vaut **`NULL`** (convention « `NULL` = inconnu », Partie III §11.0).

### 29.4 Fenêtres et fréquence

- **Calcul horaire**, à la minute `trends.minute` (5) de chaque heure. Job planifié « analytique », qui enchaîne : Trend Engine → moteur d'émergence (§30) → passe d'archivage des Events (§28.11).
- `window_end` = heure courante tronquée (UTC) ; `window_start` = `window_end − durée` ; période précédente = [`window_start − durée`, `window_start`[.
- `computed_at` = instant réel d'écriture.
- **Upsert** sur `UNIQUE(topic_id, period, window_end)` : recalculer la même heure produit la même ligne.
- **Misfire** (worker arrêté) : coalescence acquise, **une seule** exécution pour l'heure courante. Les heures manquées ne sont **pas** rattrapées ; le trou est absorbé par l'EMA (§29.5).
- **Rétention** (Partie III, confirmée) : lignes horaires conservées 30 jours, puis seule la ligne de `window_end` = 00:00 UTC est gardée, indéfiniment. Exécuté par l'étage purge.

### 29.5 Formules

Notations : `m` = mentions de la fenêtre, `m_prev` = mentions de la période précédente, `d` = durée de la période en jours.

| Mesure | Formule | Cas limites |
|---|---|---|
| `growth_rate` | `(m − m_prev) / max(m_prev, 1)` | `NULL` si `window_start − durée < coverage_since(t)` |
| `velocity` | `m / d` (mentions par jour) | toujours défini ; sert à comparer les périodes entre elles |
| `novelty` | `exp(−âge / trends.novelty_tau)`, `âge = window_end − first_mention_at(t)` | `NULL` si A(t) est vide, ou si `first_mention_at(t) < coverage_since(t) + trends.novelty_warmup` |
| `momentum` | EMA de `growth_rate` : `prev + α · (growth_rate − prev)`, `α = 1 − 2^(−Δt / demi_vie)` | `NULL` si `growth_rate` est `NULL` ; égal à `growth_rate` si le Signal précédent n'existe pas ou a un `momentum` `NULL` |

- `first_mention_at(t)` = plus petit `published_at` de A(t), sur tout l'historique (lignes `Article` conservées indéfiniment). Une même valeur pour les trois périodes.
- **Warm-up de nouveauté** : un topic mentionné dès le début de la couverture ne peut pas être distingué d'un topic préexistant ; sa `novelty` reste `NULL`.
- **`momentum`** : `prev` = `momentum` du Signal de même (topic, période) au plus grand `window_end` antérieur ; `Δt` = écart réel entre les deux `window_end`. Un trou de plusieurs heures donne un `α` plus grand, sans rattrapage.
- **Demi-vies** : `24h` → 6 h · `7d` → 1 j · `30d` → 3 j.
- **Division par zéro** : impossible par construction (`max(m_prev, 1)`, `d > 0`).

### 29.6 Catégories

Évaluées dans cet ordre, la première qui s'applique l'emporte :

| Ordre | Catégorie | Condition |
|---|---|---|
| 1 | `NULL` (support insuffisant) | `m < trends.min_mentions[period]` (3 · 5 · 10) |
| 2 | `rising` | `novelty ≥ 0,5` et `growth_rate ≥ +100 %` |
| 3 | `trending` | `growth_rate ≥ +50 %` et `momentum > 0` |
| 4 | `declining` | `growth_rate ≤ −30 %` et `momentum < 0` et `m_prev ≥ trends.min_mentions[period]` |
| 5 | `established` | tous les autres cas, y compris `growth_rate` `NULL` |

- Une condition portant sur une valeur `NULL` est **fausse**.
- **`rising` remplace `emerging`** : un topic existant, jeune et en forte croissance. Les **sujets émergents** (§30) sont des termes qui **ne sont pas encore** des topics.
- Les catégories sont des **indicateurs produit**, pas des prédictions (acquis).
- Pas d'hystérésis en V1 : la lecture se fait sur `momentum`, déjà lissé.

### 29.7 Discontinuités assumées

À documenter dans `docs/trends.md` :

- **Modification des mots-clés** d'un topic : non rétroactive (Partie IV §16.3), elle crée une rupture dans ses mentions.
- **Ajout d'une source** : le premier run remonte au plus 100 items sur 30 jours ; la hausse est étalée sur les fenêtres passées, mais réelle.
- **Topic désactivé** : plus de Signal calculé ; son historique est conservé.
- **Topic mis en sourdine** (préférence) : Signal calculé normalement ; la sourdine agit sur l'affichage et les alertes.

### 29.8 Réglages `trends.*` dans `pipeline.yaml`

| Clé | Défaut | Section |
|---|---|---|
| `trends.minute` | 5 | §29.4 |
| `trends.write_batch` | 20 | §29.1 |
| `trends.novelty_tau` · `novelty_warmup` | 14 j · 7 j | §29.5 |
| `trends.momentum_half_life` (`24h` · `7d` · `30d`) | 6 h · 1 j · 3 j | §29.5 |
| `trends.min_mentions` (`24h` · `7d` · `30d`) | 3 · 5 · 10 | §29.6 |
| `trends.rising_min_novelty` · `rising_min_growth` | 0,5 · 1,0 | §29.6 |
| `trends.trending_min_growth` | 0,5 | §29.6 |
| `trends.declining_max_growth` | −0,3 | §29.6 |

## 30. Emerging topics

Détecter des **termes** qui montent et qui ne sont **pas encore** couverts par un topic. Détection **cœur**, déterministe ; qualification **AI** par `discover_topics`, **indicative** (V-A §27.4).

### 30.1 Contrat

| | |
|---|---|
| **Entrée** | articles `ready` (hors `duplicate`) de `published_at ≥ now − 37 j` : `title`, `source_id`, `author`, `event_id` ; liaisons `ArticleEntity` `method=keyword` de type `repository` ; topics activés (`slug`, `name`, `keywords`) ; `EmergingDecision` |
| **Sortie** | `EmergingCandidate` créés ou mis à jour ; jobs `discover_topics` |
| **Tables écrites** | `EmergingCandidate` · `AIJob` |
| **Ne lit jamais** | `Article.summary` (écrasé par le LLM), liaisons `method=llm`, colonnes `llm_*` et `covered_by_topic_id` du candidat |
| **Exécution** | horaire, juste après le Trend Engine (§29.4) ; comptage en mémoire, hors event-loop (≈ 11 000 titres) ; une transaction par lot de candidats |
| **Warm-up** | aucune détection tant que `now < trends_since + emerging.warmup` (14 j) : sans historique, tout paraît récent. État exposé au monitoring |

### 30.2 Termes

Deux familles, distinguées par la nouvelle colonne `EmergingCandidate.kind` `CHECK {ngram, repository}`.

**`ngram` — n-grammes des titres** :

1. **Titres seulement.** Le résumé n'est pas une entrée déterministe (il est remplacé par le LLM) ; les titres sont conservés indéfiniment.
2. `norm(title)` (Partie IV §20.2), puis retrait des préfixes de la liste `emerging.strip_prefixes` (« show hn: », « ask hn: », « [video] »…).
3. **Tokens** : suites de lettres et chiffres ; les caractères `- . + #` sont conservés à l'intérieur d'un token (`gpt-4o`, `node.js`), et `+` / `#` en fin de token (`c++`, `c#`). Écartés : tokens d'un seul caractère, nombres purs, numéros de version (`^v?\d+(\.\d+)*$`).
4. **n-grammes** de 1 à 3 tokens consécutifs, dont ni le premier ni le dernier token n'est un stopword (listes EN et FR intégrées, plus `emerging.stopwords_extra`).
5. Un terme compte **une fois par article** (présence).
6. `key` = tokens joints par une espace ; `label` = forme d'origine la plus fréquente dans les titres.

**`repository` — dépôts GitHub** : chaque entité `repository` liée en `method=keyword` (motif Partie IV §16.4). `key` = `repo:{canonical_name}` ; `label` = `name`.

**Maximalité** (`ngram` uniquement), appliquée aux termes qui passent les critères §30.3 : un n-gramme *g* contenu (tokens contigus) dans un n-gramme retenu *g'* est supprimé si `mentions_7d(g') ≥ 0,8 × mentions_7d(g)`.

### 30.3 Critères de détection

Notations sur l'ensemble des articles portant le terme : **R** = 7 derniers jours ; **P** = 7 jours précédents ; **B** = les 30 jours qui précèdent R. Toutes les conditions doivent être vraies.

| Critère | Condition (défauts) |
|---|---|
| **récent** | occurrences dans B `≤ emerging.baseline_max` (2) |
| **en accélération** | `mentions_7d ≥ emerging.min_mentions` (5) **et** `mentions_7d ≥ 2 × mentions_prev7d` |
| **multi-sources** | `source_id` distincts dans R `≥ emerging.min_sources` (3) |
| **multi-auteurs** | auteurs distincts dans R (clé §29.2) `≥ emerging.min_authors` (3) |
| **multi-écosystèmes** | canaux distincts dans R (table §28.9) `≥ emerging.min_channels` (2) |
| **multi-histoires** | histoires distinctes dans R `≥ emerging.min_stories` (2) — une histoire = un Event (`event_id`), ou un article sans Event |
| **pas déjà couvert** | voir ci-dessous |
| **pas en sourdine** | aucune `EmergingDecision` `mute` sur la clé |

- Les **écosystèmes** sont comptés directement sur les articles du terme, avec le même mapping de canaux que `Event.distinct_channel_count`. Les compteurs des Events ne s'agrègent pas proprement entre plusieurs Events.
- **Pas déjà couvert** : le terme n'est pas couvert si aucune des conditions suivantes n'est vraie, pour un topic activé :
  - ses tokens sont égaux à, ou forment une sous-suite contiguë de, ceux de `norm(name)`, du slug (tirets remplacés par des espaces) ou d'un mot-clé non-regex du topic ;
  - un mot-clé regex du topic reconnaît le terme **en entier** (*fullmatch*) ;
  - pour `repository`, `canonical_name` est un mot-clé du topic.
- Un terme qui **contient** un mot-clé existant (« claude code skills » face à « claude code ») **n'est pas couvert** : c'est typiquement un sous-sujet émergent.
- `covered_by` (LLM) **n'intervient pas** dans ce critère (acquis).
- **Croissance affichée** : `growth = (mentions_7d − mentions_prev7d) / max(mentions_prev7d, 1)`.

### 30.4 Création et mise à jour du candidat

À chaque exécution, pour chaque terme qui satisfait **tous** les critères :

- **Upsert** sur `key` :
  - `label` recalculé ;
  - `evidence` remplacé ;
  - `last_evidence_at = now` ;
  - `first_detected_at` posé à la création seulement.
- **`evidence`** (JSON validé par Pydantic) : `mentions_7d` · `mentions_prev7d` · `growth` · `sources` · `authors` · `channels` (liste) · `stories` · `first_seen_at` (premier `published_at` du terme dans la fenêtre de 37 j) · `article_ids` (au plus 20, les plus récents).
- Un terme qui ne satisfait plus les critères n'est **pas** modifié : `evidence` reste le dernier état qui les satisfaisait.
- Candidats décidés :
  - `mute` : n'est plus évalué ;
  - `follow` et `ignore` : mis à jour normalement ;
  - converti (`topic_id` renseigné) : n'est plus évalué, sa clé étant désormais couverte.

**Statut dérivé à la lecture**, sans colonne :

| Statut | Condition |
|---|---|
| `converted` | `topic_id IS NOT NULL` |
| `active` | `last_evidence_at ≥ now − emerging.stale_after` (3 j) |
| `dormant` | sinon |

### 30.5 Évolution significative

Trois nouvelles colonnes : `ref_mentions` · `ref_channel_count` · `last_significant_at`.

- **À la création** : `ref_mentions = mentions_7d`, `ref_channel_count = channels`, `last_significant_at = now`. C'est la première évolution significative.
- **Ensuite**, une évolution est significative si :

```
( mentions_7d ≥ 2 × ref_mentions  ou  channels > ref_channel_count )
et now − last_significant_at ≥ emerging.significant_min_interval   (24 h)
```

  Elle met à jour les trois colonnes.
- **Effets** d'une évolution significative :

| Situation du candidat | Effet |
|---|---|
| aucune décision | création d'un `discover_topics` |
| `follow` | alerte `emerging_topic` (impact Partie VI) |
| `ignore` | `resurfaced_at = now` : le candidat réapparaît (§30.7) |
| `mute` · converti | aucun (non évalué) |

### 30.6 `discover_topics`

- **Créé** à chaque évolution significative d'un candidat **sans décision** (y compris la création). Priorité, délai et TTL : registre V-A §23.2. Un job actif existant rend l'insertion sans effet.
- **Articles fournis** (au plus `llm` 8, V-A §27.4), choisis parmi les articles du terme dans R, dans cet ordre, sans doublon :
  1. un article par source distincte, le plus récent de chaque ;
  2. si un canal de `evidence.channels` n'est pas encore représenté, l'article le plus récent de ce canal ;
  3. les plus récents.

  À critère égal, un article `summary_origin = llm` est préféré.
- Le résultat reste **indicatif** : il ne retire, ne masque ni ne convertit jamais un candidat (acquis).

### 30.7 Décisions utilisateur

`EmergingDecision` est écrite par l'app seule. Elle devient **modifiable** : l'app fait un upsert sur `UNIQUE(candidate_id)`, en mettant à jour `decision` et `decided_at`. Seule exception : `create_topic` est **définitif**, et l'app refuse ensuite toute modification.

| Décision | Effet |
|---|---|
| `follow` | le candidat reste affiché, même `dormant` ; alerte à chaque évolution significative |
| `ignore` | masqué ; **réapparaît** si `resurfaced_at > decided_at` (évolution significative postérieure). Une nouvelle décision le masque à nouveau |
| `mute` | masqué définitivement ; la clé n'est plus évaluée |
| `create_topic` | cycle §30.8 |

La réapparition est calculée par le worker (`resurfaced_at`) sans toucher à la décision : la règle d'un seul écrivain par table est respectée.

**Affichage** (liste des sujets émergents) : candidats `active`, sans décision ou en `follow`, plus les `ignore` réapparus ; jamais `mute` ni `converted`.

### 30.8 Cycle « Create topic »

Complète V-A §24.6.

```
app      EmergingDecision(create_topic)                       [transaction app]
worker   tick 60 s : décisions create_topic, candidat.topic_id IS NULL
         ├─ T1 (1 transaction)  Topic créé + EmergingCandidate.topic_id
         └─ T2… (lots bornés)   backfill ArticleTopic keyword
                                → EmergingCandidate.backfilled_at
runner   taxonomie rechargée : les nouveaux articles sont liés au topic
trends   heure suivante : Signal du topic, coverage_since = created_at − 30 j
```

1. **Décision** : directe, à partir des valeurs connues ; pas de formulaire d'édition en V1 **(proposé)**. Disponible que `discover_topics` ait abouti ou non.
2. **T1 — création du topic**, une transaction :
   - `origin = user` · `parent_id = NULL` · `enabled = true` ;
   - `name` = `llm_label` s'il existe, sinon `label` ; `description` = `llm_description` ou `NULL` ;
   - `slug` = slug de `name` (`norm`, caractères non alphanumériques → `-`, tirets fusionnés et retirés aux extrémités). S'il existe déjà, suffixe `-2`, `-3`… ;
   - `keywords` = `suggested_keywords` ∪ {terme de base}, où le terme de base est `key` pour `ngram` et `canonical_name` (`owner/repo`) pour `repository`. Sans LLM, seul le terme de base ;
   - `EmergingCandidate.topic_id` renseigné.
3. **T2 — backfill** : pour ce seul topic, re-score des articles `ready` de `published_at ≥ now − topic_backfill.window` (30 j) avec la fonction du relevance filter (Partie IV §20.3). Liaisons `ArticleTopic` `method=keyword` si `score_t ≥ threshold`.
   - **Texte d'entrée** : `title`, URL, et `summary` **uniquement si** `summary_origin = fallback` ; sinon titre et URL seuls **(proposé — corrige V-A §24.6)**. Une liaison keyword ne doit pas dépendre d'un texte produit par le LLM.
   - Par lots bornés, `INSERT … ON CONFLICT DO NOTHING` : un backfill interrompu est rejoué intégralement, sans effet de bord.
   - `backfilled_at = now` en fin de backfill. Un candidat avec `topic_id` renseigné et `backfilled_at` `NULL` est repris au tick suivant.
4. **Nouveaux articles** : le runner charge les topics activés d'origine `user` depuis la base, en plus de `topics.yaml`, et recharge sa taxonomie quand un topic est créé **(proposé — impact Partie IV)**.
5. **Tendances** : le topic a un Signal dès l'heure suivante. `growth_rate` est défini pour `24h` et `7d`, `NULL` pour `30d` tant que la couverture est inférieure à 60 jours (§29.3).
6. **Suivi** : le topic créé n'est pas suivi automatiquement ; le suivi reste une préférence (`UserPreference`).

`origin = discovered` n'est produit par **aucun** mécanisme en V1 : aucun topic n'est créé sans action de l'utilisateur.

### 30.9 Réglages `emerging.*` dans `pipeline.yaml`

| Clé | Défaut | Section |
|---|---|---|
| `emerging.warmup` | 14 j | §30.1 |
| `emerging.max_ngram` | 3 | §30.2 |
| `emerging.strip_prefixes` · `stopwords_extra` | liste intégrée · `[]` | §30.2 |
| `emerging.maximality_ratio` | 0,8 | §30.2 |
| `emerging.recent_window` · `baseline_window` | 7 j · 30 j | §30.3 |
| `emerging.baseline_max` | 2 | §30.3 |
| `emerging.min_mentions` · `min_sources` · `min_authors` · `min_channels` · `min_stories` | 5 · 3 · 3 · 2 · 2 | §30.3 |
| `emerging.stale_after` | 3 j | §30.4 |
| `emerging.significant_min_interval` | 24 h | §30.5 |
| `emerging.create_topic_tick` | 60 s | §30.8 |

---

## Reporté en V2 (tracé depuis la Partie V-B)

- **Dédup de la syndication entre sources** (même dépêche reprise par plusieurs sites) : en V1, elle forme un Event multi-sources.
- **Recalcul complet du clustering** et **scission** d'un Event ou annulation d'une fusion.
- **Modification manuelle de l'appartenance** d'un article à un Event.
- **Rafraîchissement de l'engagement** (`Article.metrics` mis à jour après la collecte) pour une importance plus fiable.
- **Hystérésis des catégories** de tendance.
- **Détection d'émergence par clusters d'embeddings** d'articles « orphelins », en complément des n-grammes.
- **Vérification d'historique long** des termes (au-delà de 37 jours).
- **Formulaire de création de topic** (libellé, mots-clés, parent modifiables).
- **Création automatique de topics** (`origin = discovered`).
- **Re-scoring rétroactif** complet après modification des mots-clés (déjà reporté par la Partie IV).

---

## Impacts à répercuter dans les autres parties

À traiter lors de la revue des parties concernées — **hors Partie V-B**.

### Partie II — Architecture

- **Décision 4** : `duplicate` rétroactif restreint à la **même source** et aux titres normalisés égaux (§28.7). Entre sources différentes, un cosine ≥ seuil haut ne produit qu'un candidat « même Event ».
- **§7.2** : le schéma « seuil haut → duplicate » devient « seuil haut + même source → duplicate » ; ajouter les deux voies de déclenchement du clustering (§28.2).
- **§8.4** : le scheduler porte un job « analytique » horaire (trends → émergence → archivage) et deux ticks de 60 s (clustering, create topic).
- **§8.3** : `EmergingDecision` devient modifiable par upsert côté app (§30.7) ; `EmergingCandidate.resurfaced_at` est écrit par le worker.

### Partie III — Données

- **`Article`** : nouvelles colonnes `clustered_at` (nullable) · `clustered_semantic` (booléen, défaut `false`) · `importance` (réel, nullable) ; index partiel sur `clustered_at IS NULL WHERE status = 'ready'`.
- **`Event`** : suppression de `novelty` ; nouvelle colonne `resolve_enqueued_count` (entier, nullable) ; `importance` non nulle (défaut 0) ; `article_count` défini sur les membres `ready`.
- **`Signal`** : `category` nullable, `CHECK {established, trending, rising, declining}` (`emerging` → `rising`) ; contrainte `UNIQUE(topic_id, period, window_end)` ; rétention : ligne de 00:00 UTC conservée après 30 jours.
- **`EmergingCandidate`** : nouvelles colonnes `kind` `CHECK {ngram, repository}` · `ref_mentions` · `ref_channel_count` · `last_significant_at` · `resurfaced_at` · `backfilled_at` ; schéma Pydantic de `evidence` (§30.4).
- **`EmergingDecision`** : upsert autorisé ; `create_topic` définitif.
- **`SystemState`** : nouvelles clés `trends_since` (écrite une fois par le runner) et `trends_last_run`.

### Partie IV — Pipeline

- **Taxonomie du runner** : inclure les topics activés d'origine `user` de la base, en plus de `topics.yaml` ; rechargement à la création d'un topic.
- **`SystemState.trends_since`** : posé par le runner à la première insertion d'un article `ready`.
- **Registre des collectors** : chaque type déclare son **canal** (`rss` et `webpage` → `web`).
- **`validate-config`** : contrôler `clustering.embedding_wait + clustering.tick < llm.delay.enrich_article`, et valider les sections `clustering.*`, `importance.*`, `trends.*`, `emerging.*` de `pipeline.yaml`.

### Partie V-A — Machinerie & tâches LLM

- **§24.6** : le backfill re-score sur titre + URL + résumé **seulement si** `summary_origin = fallback` (§30.8), pour que la liaison keyword reste déterministe.
- **§23.2** : `enrich_article` peut aussi être créé par le clustering, pour un nouveau représentant non enrichi (§28.8). `resolve_event` : règle de déclenchement par marqueur (§28.10). `discover_topics` : créé à chaque évolution significative d'un candidat sans décision (§30.5).
- **§23.3** : la garde `event_not_active` reste valable ; `archived` n'intervient qu'après 7 jours d'inactivité (§28.11).
- **Taxonomie** : `origin = discovered` n'est produit par aucun mécanisme en V1.

### Partie VI — Interfaces

- **Overview « Emerging »** : affiche les **candidats** du §30 (règles §30.7). Les topics en catégorie `rising` apparaissent dans « Trending », avec un badge distinct.
- **Décisions** : sémantique `follow` · `ignore` · `mute` · `create_topic` (§30.7) ; affichage d'un candidat réapparu ; `create_topic` sans formulaire en V1.
- **Importance** : affichée sur 0–100 ; le réglage « seuil d'importance » (`Setting`) s'exprime sur la même échelle. Le filtre du fil utilise `Event.importance`, ou `Article.importance` hors Event.
- **Events fusionnés** : un lien vers un Event `merged` redirige vers sa cible ; l'état de lecture de la cible est conservé (celui de la source n'est pas transféré).
- **Alertes** : `important_event` dédupliquée par Event **cible** (une fusion ne réémet pas d'alerte pour un Event déjà alerté sous l'un de ses composants) ; `emerging_topic` avec `dedup_key` = `emerging:{candidate_id}:{last_significant_at}`.
- **Tendances** : `NULL` affiché « données insuffisantes », jamais 0.

### Partie VII — Ops

- **Métriques** : latence de clustering (insertion → `clustered_at`) · articles évalués sans vecteur · secondes passes · fusions · doublons sémantiques · Events actifs · durée du job analytique · candidats actifs · warm-up de l'émergence en cours.
- **Commandes CLI** : `cluster-calibrate` (§28.14) et `recount-events` (§28.9), documentées dans le runbook.
- **Mesure avant production** : durée du job analytique au volume nominal.

### Partie VIII — Livraison

- **Calibration** des seuils de clustering sur données réelles (`cluster-calibrate`) : critère de mise en production.
- **Tests** :
  - post HN dont le contenu extrait égale le billet : même Event, deux sources, aucun `duplicate` ;
  - releases successives d'un même dépôt : jamais regroupées, jamais en doublon ;
  - entité omniprésente : ne relie rien ; URL hub ignorée ;
  - premier run de 100 items anciens : aucun regroupement hors proximité `published_at` ;
  - moteur d'embeddings `down` : clustering U + E, puis seconde passe au retour ;
  - fusion de deux Events : compteurs recalculés, un seul `resolve_event` sur la cible, jobs des sources sautés ;
  - changement de représentant : titre de repli suivi, `enrich_article` créé ;
  - invariant des compteurs après chaque opération ; kill -9 pendant une évaluation ;
  - Trend Engine : cold start (`NULL`), agrégation parent sans double compte, EMA après un trou de plusieurs heures, upsert idempotent, liaisons `llm` sans effet sur les mentions ;
  - émergence : warm-up, chaque critère isolément, maximalité des n-grammes, terme contenant un mot-clé non couvert, sourdine, réapparition après `ignore` ;
  - « Create topic » : slug en collision, backfill interrompu puis repris, liaisons sur les nouveaux articles, Signal à l'heure suivante.

---

