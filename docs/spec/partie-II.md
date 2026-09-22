# Partie II — Architecture

2026-09-22

> **Partie II — Architecture.** Version durcie issue de la revue §6–§9.
> Remplace la Partie II de SPEC.md V0.3. Prend la Partie I durcie comme acquis
> (objectif à 3 piliers, garantie transverse « fonctionner sans AI », hotness déterministe).

---

## Décisions tranchées dans cette revue (Partie II)

Ces points étaient absents, implicites ou contradictoires en V0.3. Ils sont tranchés ici et intégrés au fil des sections.

1. **§6 reformulé** : le principe fondamental n'est plus « les collectors ne sont jamais bloqués par le LLM » (trop étroit) mais une **architecture à deux couches** — un **cœur déterministe** complet de bout en bout, et une **couche d'enrichissement AI asynchrone**. La règle sur les collectors en devient un corollaire. Cf. §6.
2. **Un `Event` est créé de façon déterministe**, sans LLM, avec un **titre de repli** (titre de l'article représentatif). Le job `resolve_event` **enrichit** (titre de synthèse, description) et arbitre les cas ambigus — il ne conditionne jamais l'existence de l'événement.
3. **La hotness est matérialisée** : compteur de **sources distinctes** porté par l'`Event`, mis à jour à chaque rattachement d'article. Calculable et affichable **sans LLM**.
4. **La déduplication sémantique sort du pipeline synchrone.** Le pipeline ne fait que de la **dédup exacte** (URL canonique · external ID · content hash). La similarité vit dans l'**étage asynchrone embeddings/clustering**, avec **deux seuils sur un unique calcul cosine** : seuil haut → `duplicate` rétroactif ; seuil médian → même `Event`.
5. **Tout travail CPU-bound du worker s'exécute hors de l'event-loop** (`asyncio.to_thread` / `ThreadPoolExecutor` borné). Cf. §8.4.
6. **L'API peut déposer des jobs, jamais les exécuter.** Elle insère des `AIJob` de **types prédéfinis** (liste fermée §11.10) pour les actions du dashboard, et répond immédiatement.
7. **Caddy sert le frontend statique** et proxie `/api` + `/health` vers FastAPI. **FastAPI ne sert pas la SPA.**
8. **Heartbeat worker** : le worker écrit périodiquement une preuve de vie **indépendante de son activité**, pour que `/health` distingue « worker au repos » de « worker mort ».
9. **`Analytics` supprimé** du schéma §7 (boîte jamais définie ailleurs) ; le besoin est couvert par le Dashboard et la fonction 13 (recherche).
10. **Recherche plein texte = SQLite FTS5**, pas de moteur externe. Aucune dépendance de type Elasticsearch en V1.
11. **`Article.content` est un tampon de traitement, pas une donnée conservée.** Purge après achèvement des traitements + **délai de grâce de 1 jour** (configurable) ; jamais de purge si un job de l'article est en `dead_letter`. Le produit conserve **événements, topics, signaux, résumés et liens**, pas une archive d'articles.
12. **Un étage de purge** est un composant à part entière du worker, déclenché périodiquement par le scheduler.
13. **Carte de propriété des tables** app/worker établie : les **deux processus écrivent** en base ; le contrat d'interface est le **schéma SQLite**, pas un IPC.
14. **Alertes V1 sans reprise** : un échec d'envoi est journalisé et compté, l'alerte n'est pas rejouée. L'outbox avec retry est **reportée en V2**.

---


## 6. Principe fondamental

L'architecture repose sur **deux couches nettement séparées**.

> **Couche cœur — déterministe, sans aucune dépendance LLM.**
> Collecte → normalisation → dédup exacte → relevance → persistance → **clusters d'événements candidats** → **signaux et hotness déterministes** → présentation, recherche et alertes déterministes.
> Cette couche va **de bout en bout** : elle ne dépend d'aucun service AI, à aucune étape.
>
> **Couche enrichissement — AI, asynchrone, best-effort.**
> Résumés, extraction de topics et d'entités, confirmation des événements ambigus, lecture qualitative des tendances. Elle **améliore** le produit ; elle ne le **conditionne** jamais.

**Conséquence contractuelle** : lorsque la couche AI est indisponible, le produit reste **pleinement utilisable** — l'ingestion continue, la déduplication exacte fonctionne, les événements se forment, la **hotness reste affichée**, le dashboard, la recherche et les alertes déterministes fonctionnent. Seule la qualité de restitution se dégrade (titres et aperçus de repli au lieu de synthèses).

### 6.1 Corollaires

1. **Aucun collector n'attend jamais une réponse LLM.** Le LLM n'est jamais appelé depuis un collector ni depuis une requête HTTP entrante. Toute opération LLM passe par la **file de jobs asynchrone** (§23).
2. **Aucune fonction `[core]` de la Partie I (§3) ne dépend de la couche AI.** C'est le critère de vérification de cette séparation : si une fonction étiquetée `[core]` cesse de fonctionner gateway éteint, l'architecture est en faute.
3. **Les embeddings appartiennent à la couche cœur**, pas à la couche AI. Ils sont calculés localement, sur CPU, sans appel réseau — leur indisponibilité est un mode de panne **distinct** d'une panne LLM (§9).
4. **Le sens de la dépendance est unique** : la couche AI lit ce que la couche cœur a produit et y ajoute ; la couche cœur ne lit jamais un résultat AI pour prendre une décision structurante.

## 7. Architecture cible

Le schéma unique de la V0.3 mélangeait **étages de traitement** et **tables**, et se lisait comme un tuyau linéaire avec le LLM en aval. Il est remplacé par **deux schémas** : le pipeline d'ingestion (linéaire, déterministe, se termine à la base) puis le fan-out post-base (la base est le pivot).

### 7.1 Pipeline d'ingestion — linéaire et entièrement déterministe

```
  SOURCES
  RSS · GitHub · Hacker News · Reddit · YouTube
     │  (scheduler, poll_interval par source)
     ▼
  COLLECTOR            → RawItem  (isolé par source ET par item)
     ▼
  NORMALISATION        → Article  (URL, titre, auteur, date, external_id,
     │                             contenu du flux, détection de langue)
     ▼
  CANONICALISATION     → canonical_url
     ▼
  DÉDUPLICATION EXACTE → canonical_url · external_id · content_hash
     │                    (AUCUNE similarité ici — cf. 7.2)
     ▼
  RELEVANCE FILTER     → score déterministe ; sous le seuil → status=filtered
     ▼
  EXTRACTION CIBLÉE    → fetch + trafilatura, UNIQUEMENT si relevant (§17)
     ▼
  DATABASE             → Article persisté (status=ready)
     ▼
  ENQUEUE              → AIJob + Embedding job
```

**Propriétés contractuelles de ce pipeline** :

- **Aucun appel LLM**, à aucune étape.
- **Aucune attente d'un traitement asynchrone** : le pipeline se termine à l'`INSERT`, il ne dépend pas du résultat d'un embedding ni d'un job.
- **Isolation à deux niveaux** : une panne de source n'arrête pas les autres sources ; un `RawItem` malformé n'arrête pas le reste de son lot (il est journalisé, compté, `status=error`).
- **Idempotent** : rejouer une collecte ne crée pas de doublon (garanti par `external_id` / `canonical_url`).

### 7.2 Post-base — la base est le pivot

Après l'`INSERT`, l'architecture n'est plus un tuyau : c'est un **hub**. Des producteurs écrivent dans la base, des consommateurs y lisent, sans se connaître.

```
                          ┌──────────────────────────┐
                          │        DATABASE          │
                          │   (SQLite, pivot unique) │
                          └──────────────────────────┘
                ▲  ▲  ▲                      │  │  │
   PRODUCTEURS  │  │  │                      │  │  │  CONSOMMATEURS (lecture)
                │  │  │                      │  │  │
  ┌─────────────┘  │  └──────────┐           │  │  └──────────────┐
  │                │             │           │  │                 │
  │  [cœur]        │  [cœur]     │ [AI]      ▼  ▼                 ▼
  │                │             │      Dashboard            Alerts
  │ Ingestion      │ Embeddings  │ AI Job Queue   Recherche (FTS5)   /health
  │ (7.1)          │     ▼       │      ▼
  │                │ Similarité  │  LLMClient → LLM Gateway → Providers
  │                │     │       │      (résumés, topics, entités,
  │                │     ▼       │       resolve_event, analyse)
  │                │ ┌───┴────┐  │
  │                │ │ seuil  │  │
  │                │ │ haut   │→ duplicate (rétroactif)
  │                │ │ médian │→ EVENT CLUSTERING
  │                │ └────────┘       ▼
  │                │              distinct_source_count  ← HOTNESS [cœur]
  │                │                  ▼
  │  [cœur] PURGE  │           TREND ENGINE (Signal) [cœur]
  └────────────────┴───────────────────────────────────────────────┘
```

**Étages ajoutés ou rendus explicites par rapport à la V0.3** :

| Étage | Couche | Rôle |
|---|---|---|
| **Embeddings** | cœur | calcul local CPU, asynchrone, sur les seuls articles `ready` |
| **Similarité (cosine)** | cœur | **un seul calcul, deux seuils** : haut → `duplicate` rétroactif ; médian → candidat même `Event` |
| **Event clustering** | cœur | crée l'`Event` **sans LLM**, titre de repli = titre de l'article le plus ancien du groupe |
| **Hotness** | cœur | `distinct_source_count` matérialisé sur l'`Event`, incrémenté à chaque rattachement |
| **Trend Engine** | cœur | produit les `Signal` par topic et par fenêtre |
| **Purge** | cœur | efface `Article.content` après traitement + délai de grâce (§8.5) |
| **AI Job Queue → LLMClient** | AI | seul point de contact avec un provider ; **enrichit**, ne crée rien de structurant |
| **Recherche (FTS5)** | cœur | table virtuelle SQLite, plein texte sur titre + aperçu, combinée aux filtres SQL |

**Supprimé** : la boîte `Analytics`, jamais définie ailleurs dans la spec. Le besoin est couvert par le Dashboard (§31) et la fonction 13 de la Partie I (recherche et filtrage de l'historique).

### 7.3 Où vit la hotness

Chaîne complète, **entièrement dans la couche cœur** :

```
Article ready → candidats (URL croisée · entités communes · cosine)
              → rattachement à un Event (créé si besoin)
              → distinct_source_count++
              → tri et affichage Overview
```

Aucun maillon n'appelle le LLM. Le job `resolve_event` remplace ensuite le titre de repli par un titre de synthèse et ajoute la description — **sans jamais modifier le compteur ni l'appartenance des articles**.

## 8. Architecture des processus

### 8.1 Les trois conteneurs

```
caddy                    app                         worker
 ├── TLS / Let's Encrypt   └── FastAPI                ├── scheduler (APScheduler)
 ├── sert le build Vite        ├── API REST           ├── collectors
 │   (fichiers statiques)      └── /health            ├── normalisation / dédup / relevance
 └── proxie /api + /health                            ├── embeddings + similarité
     vers app                                         ├── event clustering + hotness
                                                      ├── trend calculations
                                                      ├── AI job processing
                                                      ├── purge
                                                      └── alerting
```

**Décision** : le frontend est servi **par Caddy** en fichiers statiques. FastAPI n'expose que l'API et `/health`, et ne sert pas la SPA. Aucun conteneur applicatif n'expose de port public (§37).

### 8.2 Contrat d'interface app ↔ worker

> **Il n'existe aucun IPC entre `app` et `worker`.** Leur unique interface est le **schéma SQLite** et la sémantique des colonnes d'état. Aucun appel HTTP, aucune socket, aucune file externe.

Ce contrat impose trois règles :

1. Toute coordination passe par une **écriture en base lue par l'autre processus**.
2. Toute colonne servant de coordination (`Article.status`, `AIJob.status`, heartbeat, `next_attempt_at`) a une **sémantique documentée et un jeu de valeurs fermé**.
3. Une modification de cette sémantique est un **changement de contrat** : elle se traite en migration Alembic + mise à jour de la spec, jamais par convention implicite.

### 8.3 Propriété des tables

Le raccourci « le worker écrit, l'app lit » est **faux** : les deux processus écrivent. La répartition est la suivante, et chaque table a **un seul propriétaire en écriture**.

| Table / donnée | Écriture | Lecture |
|---|---|---|
| `Source` (état, quotas, last_success/error) | **worker** | app |
| `Article` (tout le cycle de `status`) | **worker** | app |
| `Topic` (seeded et découverts) | **worker** | app |
| `Entity`, `ArticleTopic`, `ArticleEntity` | **worker** | app |
| `Event`, `distinct_source_count` | **worker** | app |
| `Signal` | **worker** | app |
| `Embedding` | **worker** | — |
| Index FTS5 | **worker** (triggers) | app |
| `AIJob` — claim, exécution, statuts terminaux | **worker** | app |
| `AIJob` — **création** | **worker** et **app** | — |
| Heartbeat worker | **worker** | app (`/health`) |
| Préférences utilisateur (§34) | **app** | worker |
| État de lecture (`unread`, §31) | **app** | — |
| Décisions sur sujets émergents (Follow / Ignore / Mute / Create topic, §30) | **app** | worker |

**Deux conséquences à ne pas manquer** :

- **La coordination est bidirectionnelle.** Le worker lit ce que l'app écrit : il doit respecter les `mute` avant d'émettre une alerte, et traiter un « Create topic » validé depuis le dashboard.
- **L'`AIJob` a deux producteurs.** L'app insère des jobs de **types prédéfinis** (liste fermée de `job_type`, §11.10) en réponse à une action utilisateur — régénérer un résumé, rattacher l'historique à un topic créé, relancer un `dead_letter`. Le claim atomique (§23) garantit qu'un job n'est exécuté qu'une fois, quel que soit son producteur. Un `job_type` inconnu est rejeté en `failed` sans faire tomber le worker.

> **Règle absolue** : **l'app insère des jobs, elle n'en exécute jamais aucun.** Elle répond immédiatement ; l'écran se met à jour quand le worker a terminé. Une requête HTTP qui attendrait un résultat LLM violerait le §6.

### 8.4 Modèle d'exécution du worker

Le worker est un **processus `asyncio` unique**.

- **Le travail I/O-bound** (HTTP vers les sources, appels au gateway) vit dans l'event-loop.
- **Tout travail CPU-bound s'exécute hors de l'event-loop**, via `asyncio.to_thread` ou un `ThreadPoolExecutor` à taille bornée (≤ nombre de vCPU). Sont concernés : **calcul d'embeddings · similarité cosine numpy · extraction trafilatura · hashing de contenu**.

> Aucune opération CPU-bound ne s'exécute directement dans une coroutine du scheduler ou de la boucle de jobs. Sans cette règle, un embedding de deux secondes gèle le scheduler, les collecteurs et la boucle AI pendant toute sa durée.

- **Concurrence bornée** : sémaphore sur les jobs AI simultanés (2–4, configurable).
- **Scheduler** : APScheduler déclenche collectes, calculs de tendances et purge selon leurs périodes propres. **Coalescence des misfires** : au démarrage, les exécutions manquées pendant l'arrêt sont regroupées en **une seule** exécution, jamais rejouées en rafale.

### 8.5 Étage de purge

La purge est un **composant à part entière**, déclenché périodiquement par le scheduler.

Règle : **`Article.content` est un tampon de traitement, pas une donnée conservée.**

| Cas | Action sur `content` |
|---|---|
| Article `ready`, tous traitements terminés (embedding + résumé + extractions) | purge après **délai de grâce de 1 jour** (configurable) |
| Article ayant **un job en `dead_letter`** | **jamais purgé** tant que le job n'est pas résolu ou abandonné |
| Article `filtered` (sous le seuil de pertinence) | purge immédiate |
| Article `duplicate` | purge immédiate |

**Conservé indéfiniment** : titre · URL d'origine · auteur · date · source · langue · statut · `content_hash` · aperçu/résumé · rattachements topics / entités / `Event` · `Signal`. Un `Event` conserve la **liste des liens** de ses articles — y compris si la page d'origine disparaît.

### 8.6 Concurrence SQLite

La configuration détaillée est en Partie III (§10). Ici, seules les **contraintes que l'architecture doit rendre tenables** :

1. **Un seul writer à la fois** (WAL). Les **deux** processus écrivant, la contention est réelle et doit être bornée.
2. **Transactions courtes des deux côtés.** Côté worker : jamais de lot entier ni de recalcul complet de tendances dans une transaction unique — découper en transactions par lot borné. Côté app : aucune écriture longue (une action utilisateur écrit quelques lignes).
3. **Lectures courtes côté app aussi.** Une lecture longue empêche le **checkpoint WAL** et fait croître le fichier `-wal` sans borne. Pagination obligatoire sur les endpoints de liste ; pas de requête de balayage complet.
4. **Échec après `busy_timeout`** : traité comme une erreur normale et non comme un incident — **retry borné**, journalisation et **métrique dédiée**. Une écriture définitivement perdue doit être visible dans le monitoring.

### 8.7 Faisabilité à la charge cible

La cible `< 10 000 articles/jour` représente environ **7 écritures/minute en moyenne** : le **débit n'est pas le facteur limitant** pour SQLite en WAL. Les points de contention réels sont ceux du §8.6 et la règle CPU du §8.4.

**Hypothèses à vérifier par la mesure avant la mise en production** (§21 de la V0.3 impose déjà cette démarche pour le gateway) :

- empreinte RAM du moteur d'embeddings chargé en permanence dans le worker ;
- durée d'un cosine brute-force sur la fenêtre glissante lorsqu'elle atteint son régime nominal ;
- taille du fichier `-wal` en régime de collecte soutenue ;
- durée de la plus longue transaction du worker.

## 9. Résilience

Chaque mode de panne est spécifié sur **quatre colonnes** : ce qui se dégrade, **comment on le détecte**, **comment on reprend**, et **quelle garantie d'idempotence** rend la reprise sûre. Une ligne sans ces quatre éléments n'est pas testable.

### 9.1 Pannes de la couche AI

| Panne | Dégradation | Détection | Reprise | Idempotence |
|---|---|---|---|---|
| **LLM Gateway indisponible** | résumés, topics, entités, `resolve_event` suspendus. **Ingestion, dédup, events, hotness, trends, dashboard, recherche, alertes déterministes → OK.** Aperçus et titres d'`Event` restent en **repli déterministe**. | échecs de jobs répétés + `llm_gateway` dans `/health` | jobs en `pending`/`retry`, repris automatiquement au retour du gateway | **chaque `job_type` est rejouable sans effet de bord** : l'écriture du résultat est un **upsert** par (`entity_id`, `job_type`). Un job ayant écrit son résultat puis mort avant `completed` est rejoué sans dupliquer. |
| **Moteur d'embeddings indisponible** *(distinct du LLM : local, CPU)* | similarité sémantique perdue → pas de `duplicate` rétroactif, pas de candidat par cosine. **Dédup exacte et clustering par entités / URL croisées continuent → la hotness survit.** | échec des jobs d'embedding | jobs d'embedding en `retry` ; le clustering tourne en mode dégradé sur les critères restants | rejouer un embedding écrase la ligne `Embedding` (clé `article_id` + `model`) |
| **Réponse LLM malformée** (JSON invalide) | le job échoue | validation Pydantic | `retry`, puis `dead_letter` après `max_attempts` | aucune écriture partielle : la validation précède l'écriture |

### 9.2 Pannes de processus

| Panne | Dégradation | Détection | Reprise | Idempotence |
|---|---|---|---|---|
| **Worker arrêté** | plus d'ingestion ni de traitement. **L'app reste disponible** en lecture sur l'historique déjà constitué. | **heartbeat périmé** — le worker écrit une preuve de vie à intervalle fixe, **indépendamment de son activité** ; `/health` compare sa fraîcheur à un seuil. Une nuit sans nouvel article ne doit pas ressembler à un worker mort. | redémarrage du conteneur | au boot : tout `AIJob` resté `processing` repasse en `retry` ; un lot de collecte interrompu est simplement re-fetché (dédup exacte par `external_id`) |
| **App (FastAPI) arrêtée** | dashboard et API indisponibles. **L'ingestion, le clustering et les tendances continuent** : le worker est indépendant. | monitoring externe sur `/health` (§41) | redémarrage du conteneur | aucune (l'app ne porte pas d'état en cours) |
| **VPS redémarré** | interruption totale temporaire | monitoring externe | `restart: unless-stopped` relance les trois conteneurs | **coalescence des misfires** : les exécutions planifiées manquées sont regroupées en une seule, jamais rejouées en rafale |

### 9.3 Pannes de sources et de données

| Panne | Dégradation | Détection | Reprise | Idempotence |
|---|---|---|---|---|
| **Une source indisponible** | isolée : une erreur GitHub n'arrête ni Reddit ni RSS | `last_error` / `last_http_status` par source | backoff exponentiel, reprise au cycle suivant | re-fetch sans doublon |
| **Item malformé dans un lot** | **l'item seul** est écarté (`status=error`), le lot continue | compteur `items_skipped` + log | aucune | isolation **au niveau item**, pas seulement au niveau source |
| **Quota / 429** | collecte ralentie sur cette source | code HTTP | respect de `Retry-After`, sinon backoff | — |

### 9.4 Pannes d'infrastructure

| Panne | Dégradation | Détection | Reprise | Idempotence |
|---|---|---|---|---|
| **`database is locked` après `busy_timeout`** | écriture refusée | **métrique dédiée** + log | retry borné côté appelant ; au-delà, l'échec est compté et visible | l'opération est rejouable (aucune écriture partielle : transaction annulée) |
| **Disque plein** | **toute écriture SQLite échoue** ; WAL bloqué | seuils §39 (`> 80 %` warning, `> 90 %` critical) — **l'alerte doit précéder la saturation** | libération d'espace (purge, logs, images Docker) puis reprise | aucune corruption : SQLite échoue proprement, il ne dégrade pas la base |
| **Corruption SQLite / échec de checkpoint** | base inexploitable | `/health` en échec sur `database` | **restauration du dernier backup** (§38) | la procédure de restore est documentée et testée mensuellement |
| **Backup échoué** | aucune dégradation immédiate, **risque différé** | `last_backup` périmé dans `/health` | relance manuelle | — |
| **Canal d'alerte indisponible** (SMTP / Telegram) | **l'alerte est perdue** — décision V1 assumée | log + métrique d'échec d'envoi | aucune reprise en V1 | — *(outbox avec retry → V2)* |

### 9.5 Tests de résilience obligatoires

Chaque ligne ci-dessus doit avoir un test. Les scénarios de bout en bout à automatiser :

```
reboot → containers restart → DB available → worker resumes → scheduler resumes
       → aucun job dupliqué, aucun misfire en rafale

gateway down → ingestion continue → events créés → hotness affichée
             → jobs en retry → gateway up → reprise sans doublon

worker kill -9 pendant un job → restart → job requalifié retry → rejoué → résultat unique
```

> **Critère de validation de la Partie II** : gateway LLM éteint, le produit doit rester utilisable de bout en bout — collecte, déduplication, événements, **hotness**, dashboard, recherche et alertes déterministes. Si l'une de ces fonctions tombe, la séparation des deux couches (§6) n'est pas respectée.

---

## Reporté en V2 (tracé depuis la Partie II)

- **Outbox et reprise des alertes** : en V1, un échec d'envoi (SMTP / Telegram) est journalisé et compté, l'alerte n'est pas rejouée. La file d'envoi persistante avec retry est reportée.
- **Re-collecte d'un article déjà ingéré** : le pipeline est one-shot et la dédup exacte écarterait une seconde collecte. Un mécanisme de reprise explicite (utile si un contenu purgé devait être régénéré) n'est pas au périmètre V1 ; le cas se traite manuellement, l'URL d'origine restant conservée.
- **Deuxième worker / parallélisation des jobs** : le claim atomique (§23) le rend possible sans changement de modèle, mais V1 reste à **un seul processus worker**.

---

## Impacts à répercuter dans les autres parties

À traiter lors de la revue des parties concernées — **hors Partie II**.

### Partie III — Données

- **`Event`** : ajouter `distinct_source_count` (compteur de sources distinctes, matérialisé) et un **indicateur d'état du titre** (repli déterministe / synthèse LLM), pour savoir ce qui reste à enrichir au retour du gateway.
- **Tables manquantes côté app** : préférences utilisateur (§34), état de lecture (`unread`, §31) et décisions sur sujets émergents (§30) n'existent pas dans le modèle §11 — elles sont pourtant écrites par l'API.
- **Heartbeat worker** : prévoir la table ou la ligne d'état portant la preuve de vie, avec son horodatage.
- **Index FTS5** : table virtuelle SQLite alimentée par triggers, à intégrer au modèle et aux migrations (`render_as_batch`).
- **Statut `duplicate` rétroactif** : le cycle de `Article.status` doit autoriser le passage de `ready` à `duplicate`. Décider du sort des topics / résumés déjà produits — **recommandation : les conserver, masquer seulement l'article à l'affichage**.
- **Rétention** : formaliser la purge de `Article.content` (§8.5) dans la politique de conservation, avec le délai de grâce configurable.
- **Contrainte d'unicité** supportant l'upsert d'idempotence des jobs : (`entity_id`, `job_type`).

### Partie IV — Pipeline d'ingestion

- **§19 Déduplication** : retirer la « semantic similarity » de la liste ordonnée des étapes du pipeline. Le pipeline synchrone ne fait que de la dédup **exacte** ; la similarité est un traitement asynchrone (§7.2).
- **Isolation au niveau item** : §15 n'isole qu'au niveau source ; ajouter l'isolation par `RawItem`.
- **Normalisation** : confirmer la **détection de langue** (déjà signalée par la Partie I).

### Partie V — Intelligence

- **§28 Event clustering** : reformuler — `resolve_event` ne **produit** plus `title` + `description`, il les **enrichit**. L'`Event` existe avant lui, avec un titre de repli.
- **Seuils configurables** : fenêtre temporelle, nombre d'entités communes, seuil de cosine haut (`duplicate`) et médian (`Event`) vivent en configuration. Leurs valeurs initiales sont des **points de départ à calibrer empiriquement**, pas des vérités.
- **§27 LLM Tasks** : préciser le contrat d'**idempotence par `job_type`** (upsert du résultat).
- **Alertes** : le worker doit lire les préférences de `mute` écrites par l'app avant d'émettre.

### Partie VII — Ops

- **Caddy** sert le build statique du frontend et proxie `/api` + `/health` (§37 à préciser).
- **`/health`** : le champ `worker` se calcule sur la **fraîcheur du heartbeat**, pas sur l'activité.
- **Monitoring** : ajouter les métriques `database is locked` (échecs après `busy_timeout`), échecs d'envoi d'alerte, et taille du fichier `-wal`.
- **Mesures à réaliser avant production** : RAM du moteur d'embeddings, durée du cosine en régime nominal, taille du `-wal`, durée de la plus longue transaction du worker (§8.7).

---

