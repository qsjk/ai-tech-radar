# AI Tech Radar — SPEC V0.4

> Spécification consolidée, 2026-09-22. Fusion des neuf parties durcies (I à IX) en un seul document.
> Chaque partie remplace la section correspondante de la V0.3 et prend les précédentes comme acquises.
> Document contractuel destiné à piloter le développement (Claude Code).

**Note d'assemblage.** Cette V0.4 réunit les neuf parties durcies validées une à une. Les blocs
« Décisions tranchées dans cette revue » et « Impacts à répercuter » propres à chaque revue sont
conservés (traçabilité) ; ils peuvent être retirés dans une version « build » allégée sur demande.

---

## Sommaire

- Partie I — Vision & Objectifs
- Partie II — Architecture
- Partie III — Données
- Partie IV — Pipeline d'ingestion
- Partie V-A — Intelligence : machinerie & tâches LLM
- Partie V-B — Intelligence : clustering, trends & sujets émergents
- Partie VI — Interfaces
- Partie VII — Ops & Production
- Partie VIII — Livraison
- Partie IX — Gouvernance & démarrage

---


# Partie I — Vision & Objectifs

> **Partie I — Vision & Objectifs.** Version durcie issue de la revue §1–§5.
> Remplace la Partie I de SPEC.md V0.3. Les décisions tranchées lors de la revue
> sont récapitulées ci-dessous, puis intégrées au fil des sections.

---

## Décisions tranchées dans cette revue (Partie I)

1. **Objectif = 3 piliers**, pas un arbitrage recall *vs* precision : **recall à l'ingestion** · **precision à la présentation** · **hotness** (corroboration multi-sources rendue visible). Cf. §1.
2. **Exhaustivité = non-objectif V1**, explicitement **reportée en V2**. Cf. §5 et « Reporté en V2 ».
3. **Langues V1 = EN + FR.** Aperçu rendu **en français** quand l'AI est disponible, **repli déterministe** (titre ou extrait d'origine) sinon. Autres langues → V2.
4. **Canaux V1 = RSS + GitHub + Hacker News + Reddit + YouTube.** **Newsletters (email) → V2.**
5. **Recherche = 13ᵉ fonction** explicite, **déterministe** (plein-texte simple + filtres structurés). Recherche sémantique **hors V1**.
6. **« Sans refonte »** défini en **3 niveaux** (config / config / nouveau collector) + garde-fou « toucher au modèle core ou au pipeline = refonte ». Cf. §2.
7. **Portable** et **Provider-independent** traités comme **contraintes transverses** (toujours vraies), hors ordre de priorité §4.
8. Chaque **fonction (§3) est étiquetée** *core déterministe* ou *AI-dépendante*.

---


## 1. Objectif

Construire une plateforme personnelle de veille technologique automatisée qui
**collecte, normalise, dédoublonne, regroupe, analyse, hiérarchise et présente**
l'actualité technique, et **continue de fonctionner même lorsque l'intelligence
AI est indisponible**.

L'objectif se décline en **trois piliers**, tenus à des étages différents du
pipeline pour ne pas s'opposer :

1. **Recall à l'ingestion — ne rien rater d'important.** Tout contenu *dans le
   périmètre thématique* (§2) est conservé. Le filtrage de pertinence (relevance
   filter) coupe le **hors-sujet**, jamais le **peu diffusé** : un sujet
   important mais relayé par une seule source ne doit pas être écarté pour cette
   raison.
2. **Precision à la présentation — minimiser le bruit et la redondance.** La
   déduplication, le regroupement par événement et la hiérarchisation évitent
   d'afficher plusieurs fois la même information.
3. **Hotness — rendre visible ce dont « on parle partout ».** Le produit doit
   **distinguer explicitement** un sujet corroboré par **plusieurs sources
   distinctes** d'un sujet **anecdotique** (une seule source). Cette distinction
   est une promesse de l'objectif, pas un simple raffinement du moteur de
   tendances.

> Le pilier *hotness* possède une **composante déterministe** (le nombre de
> sources distinctes parlant d'un même événement) : il **survit donc à une panne
> LLM**.

## 2. Périmètre

Le périmètre se lit sur **deux axes orthogonaux** à ne pas confondre : *ce qu'on
surveille* (domaines thématiques) et *où on va le chercher* (canaux
d'acquisition).

### 2.1 Domaines thématiques (initiaux)

Claude Code · Anthropic · AI Engineering · AI coding agents · LLM / modèles ·
MCP · agent skills · developer tools.

**Extensions futures** (l'architecture doit les permettre, cf. §2.3) : cloud ·
cybersecurity · DevOps · software engineering · infrastructure · autres domaines.

### 2.2 Canaux d'acquisition (V1)

RSS (blogs / releases / flux) · GitHub · Hacker News · Reddit · YouTube.

**Reportés (V2)** : newsletters par **email** · autres réseaux (Mastodon, X…).
V1 ne traite que des sources exposant un **flux** exploitable par les collectors
ci-dessus ; l'ingestion email n'est pas au périmètre V1.

### 2.3 Langues

- **V1** : sources **EN + FR**.
- L'**aperçu** (micro-résumé) est **toujours présent et lisible** : rendu **en
  français** quand l'AI est disponible, **repli déterministe** sur le **titre ou
  un extrait dans la langue d'origine** sinon. L'aperçu n'est **jamais bloqué**
  par une panne LLM.
- Autres langues de sources → **V2**.

### 2.4 « Sans refonte » — définition contractuelle

Étendre le périmètre doit relever de l'un des trois niveaux suivants. Tout ce qui
sort de ces niveaux est une **refonte** (interdite sans preuve, cf. gouvernance
V1) :

| Changement de périmètre | Coût | Verdict |
|---|---|---|
| Nouveau **domaine thématique** | éditer `config/topics.yaml` | **config** |
| Nouvelle **source d'un type déjà supporté** | éditer `config/sources.yaml` | **config** |
| Nouveau **type de canal** (email, Mastodon…) | ajouter un `Collector` implémentant l'interface commune ; pipeline et modèle inchangés | **extension** |
| Toucher au **modèle de données core**, au **pipeline** ou au **stockage** | — | **refonte** |

> *« Sans refonte »* signifie : les deux premiers niveaux se font par
> configuration ; le troisième par ajout d'un collector, sans modifier le
> pipeline ni le modèle de données. Toute extension exigeant de toucher au modèle
> core ou au pipeline sort de ce contrat.

## 3. Fonctions du système

Chaque fonction est étiquetée **[core]** (doit fonctionner **sans LLM**) ou
**[AI]** (best-effort, se dégrade proprement en cas de panne LLM). Une fonction
**[mixte]** possède un socle déterministe [core] et un enrichissement [AI].

| # | Fonction | Nature |
|---|---|---|
| 1 | Collecter automatiquement | **[core]** |
| 2 | Normaliser les contenus (dont détection de langue) | **[core]** |
| 3 | Éliminer les doublons **exacts** | **[core]** |
| 4 | Regrouper les contenus parlant du **même événement** | **[mixte]** — génération de candidats déterministe **[core]** ; confirmation des cas ambigus **[AI]** |
| 5 | Identifier topics, entités, événements | **[AI]** (les *candidats* d'événement restent déterministes, cf. 4) |
| 6 | Générer des résumés / l'aperçu | **[mixte]** — aperçu enrichi FR **[AI]** ; repli lisible **[core]** (cf. §2.3) |
| 7 | Détecter les tendances | **[mixte]** — comptages / diversité de sources **[core]** ; lecture qualitative **[AI]** |
| 8 | Détecter les sujets émergents | **[mixte]** — signaux déterministes **[core]** ; qualification **[AI]** |
| 9 | Envoyer des alertes | **[core]** — déclenchement possible sur base déterministe (événement multi-sources) |
| 10 | Présenter les résultats dans un dashboard, **hotness incluse** | **[core]** |
| 11 | Conserver un **historique exploitable** | **[core]** |
| 12 | Rester fonctionnel quand les services AI sont indisponibles | **garantie transverse** (voir §4 & Résilience) |
| 13 | **Rechercher et filtrer l'historique** | **[core]** |

Précisions sur les fonctions non triviales :

- **4 — Regroupement.** Critère produit vérifiable plutôt qu'un taux abstrait :
  *un événement multi-sources n'apparaît qu'une seule fois dans l'Overview.*
- **10 — Présentation & hotness.** Le dashboard doit **distinguer visuellement**
  un sujet corroboré (plusieurs sources distinctes) d'un sujet anecdotique (une
  source). Cette distinction reste calculable **sans LLM**.
- **11 — Historique « exploitable ».** *Exploitable* = **interrogeable** par
  topic, source, date, entité, événement et statut, avec la rétention définie
  par la politique de conservation.
- **13 — Recherche.** Filtrage **déterministe** sur champs structurés (topic,
  source, date, entité, événement, statut) **+ recherche plein-texte simple** sur
  titre et aperçu. La **recherche sémantique** (embeddings) **n'est pas** dans
  cette fonction en V1 : optionnelle au mieux, sinon V2. Aucune fonction de base
  ne dépend des embeddings.

## 4. Philosophie générale

Le système doit être **Simple · Portable · Observable · Résilient · Low-cost ·
Provider-independent**.

Architecture privilégiée :

```
Code déterministe  +  Jobs asynchrones  +  LLM comme service interchangeable
```

plutôt que « LLM au centre de toute l'application ».

### 4.1 Contraintes transverses (non arbitrées)

**Portable** et **Provider-independent** sont des **contraintes toujours vraies**,
hors de l'ordre de priorité ci-dessous : elles ne se négocient pas contre
d'autres qualités.

### 4.2 Ordre de priorité (arbitrage en cas de tension)

```
Reliability > Simplicity > Observability > Cost > Features > Optimization
```

### 4.3 Critères « c'est atteint »

Chaque qualité est **vérifiable**. Les seuils et procédures détaillés vivent en
Parties VII/VIII ; la Partie I n'en fixe que la **définition de succès** :

| Qualité | Critère de succès (mesurable) |
|---|---|
| **Simple** | ≤ 3–4 services Docker ; démarrage local en **une** commande (`docker compose up`) ; aucune techno bannie (§5). |
| **Portable** | Migration vers un autre VPS = copie du volume persistant + `docker compose up`, **sans modification de code**. |
| **Observable** | Tout incident majeur (source / worker / LLM down, disque plein) est détectable via `/health` ou une alerte, **sans SSH**. |
| **Résilient** | Les tests de résilience de la Partie VIII passent (LLM down · 429 · source down · worker restart · VPS reboot · backup restore). |
| **Low-cost** | Coût récurrent ≤ **12 €/mois** ; le produit **fonctionne avec un LLM à 0 €**. |
| **Provider-independent** | Changer de provider LLM = modifier `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL` ; **zéro** changement de code métier. |

## 5. Non-objectifs V1

Ne **pas** développer en V1 :

- **mobile app** ;
- **multi-user** (le produit est mono-utilisateur) ;
- **billing** ;
- **Kubernetes** · **microservices** — *l'architecture app + worker (2 processus
  sur une même base) n'est pas une architecture microservices* ;
- **Kafka** ;
- **Redis** — *aucune dépendance à Redis en V1* (la file de jobs est en base) ;
- **vector DB externe** ;
- **LLM génératif local** — *les modèles d'**embedding** légers CPU restent
  explicitement autorisés* ;
- **GPU** ;
- **scraping massif** — *autorisé : fetch **ciblé** d'une URL ayant passé le
  relevance filter, dans le respect des rate limits et de `robots.txt`.
  Interdit : crawl de sites entiers, moissonnage en masse, ignorance de
  `robots.txt`* ;
- **agent web autonome** ;
- **gateway LLM maison** — *l'**auto-hébergement d'un gateway open-source
  existant** (OmniRoute, etc.) reste autorisé.*

### 5.1 Non-objectifs implicites (rendus explicites)

- **Pas d'ingestion temps réel / push** : V1 fonctionne en **polling**.
- **Pas de personnalisation automatique** ni de recommandation par ML.
- **Pas de vérification de véracité** : le système **agrège et hiérarchise**, il
  ne **fact-checke** pas.
- **Pas d'internationalisation de l'interface** (UI mono-langue).
- **Pas de garantie d'archivage du contenu brut** : la conservation du contenu
  brut est **configurable** (la donnée structurée et l'historique analytique sont
  prioritaires).
- **Pas de couverture exhaustive** (cf. §5.2).

### 5.2 Exhaustivité — non-objectif assumé

> La **couverture exhaustive n'est pas un objectif V1** : le système **optimise
> le signal** et **assume de manquer certains items peu relayés**. Une stratégie
> de couverture plus large est à traiter en **V2**.

---

## Reporté en V2 (tracé depuis la Partie I)

Points **explicitement repoussés**, à ne pas traiter en V1 mais à garder en vue :

- **Exhaustivité / stratégie de couverture large** (§5.2).
- **Langues supplémentaires** au-delà de EN + FR (§2.3).
- **Newsletters email** et autres canaux (Mastodon, X…) (§2.2).
- **Recherche sémantique** de l'historique (§3, fonction 13).
- **Personnalisation automatique** / recommandation (§5.1).

---

## Impacts à répercuter dans les autres parties (notes, hors Partie I)

À traiter lors de la revue des parties concernées :

- **Relevance filter (Partie IV)** : ne filtre **jamais** sur la faible
  diffusion — uniquement sur la pertinence thématique (pilier *recall*).
- **Hotness déterministe (Partie V — clustering / tendances)** : le comptage de
  sources distinctes par événement alimente la *hotness* et doit rester
  calculable sans LLM.
- **Normalisation (Partie IV)** : **détection de langue** requise (champ
  `language` déjà prévu).
- **Aperçu (Partie V — LLM tasks)** : formaliser le **repli** (b) et un moyen de
  **distinguer l'aperçu enrichi de l'aperçu de repli** (flag d'état et/ou
  re-traitement via un job `summarize_article` quand le LLM revient) ; border la
  **longueur / troncature** de l'extrait de repli.

---

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

# Partie III — Données

2026-09-22

> **Partie III — Données.** Version durcie issue de la revue §10–§13.
> Remplace la Partie III de SPEC.md V0.3. Prend les Parties I et II durcies comme acquis.

---

## Décisions tranchées dans cette revue (Partie III)

Les points marqués **(proposé)** n'ont pas été discutés explicitement : ils découlent des décisions validées et sont à confirmer à la relecture.

1. **Topics et entités à double origine.** Un rattachement article↔topic ou article↔entité est produit soit **de façon déterministe** (mots-clés de `config/topics.yaml`, dictionnaire `config/entities.yaml`), soit par le **LLM**. Champ `method` ∈ `{keyword, llm}` sur les tables de liaison. Garantit que **les tendances et le clustering par entités fonctionnent sans LLM**, et corrige une incohérence de la Partie II.
2. **Nouveau fichier `config/entities.yaml`** : dictionnaire d'entités connues + motifs simples (dépôts GitHub `owner/repo`, noms de modèles).
3. **Deux URLs par article** : l'URL **propre à l'item** (page de discussion HN, post Reddit…) sert à la dédup exacte ; l'URL **pointée** (lien externe) sert de critère « URL croisée » au clustering. Évite qu'un post HN soit écrasé comme doublon de l'article qu'il commente — et qu'on perde une source distincte.
4. **`Article.event_id`** matérialise enfin la relation Article → Event (absente en V0.3).
5. **Le résumé a sa colonne** : `Article.summary` + `summary_origin` ∈ `{fallback, llm}`. Il est initialisé au repli déterministe **dès l'insertion** : un article `ready` n'a jamais de résumé vide.
6. **Statuts d'article réduits à `{ready, filtered, duplicate}`.** `discovered` / `normalized` étaient des étapes en mémoire, jamais persistées. Un **doublon exact n'est pas inséré** (il est seulement compté) ; `duplicate` ne désigne que le doublon **sémantique rétroactif**. Un item malformé n'est pas persisté non plus.
7. **`Source.type` en texte libre**, validé par le registre des collectors côté code — pas de contrainte en base. Ajouter un canal ne touche pas au schéma (Partie I §2.4). Valeurs V1 : `rss · github · hackernews · reddit · youtube`.
8. **Accès base asynchrone** dans les deux processus : SQLAlchemy 2.x async + `aiosqlite`.
9. **Toute transaction d'écriture démarre en `BEGIN IMMEDIATE`** (deux fabriques de sessions : lecture / écriture).
10. **SQLite ≥ 3.35 et FTS5 obligatoires**, vérifiés au démarrage des deux processus (arrêt immédiat avec message clair sinon).
11. **État « lu » au niveau de l'Event** (ou de l'article s'il n'appartient à aucun Event).
12. **Modèle d'embedding multilingue** (sources EN + FR), 384 dimensions, vecteurs normalisés.
13. **Tables ajoutées** : `CollectorRun` · `Setting` · `UserPreference` · `ReadState` · `EmergingCandidate` · `EmergingDecision` · `AlertLog` · `SystemState` · index `article_fts`.
14. **Rétention** : jobs terminés purgés à 30 j (sauf `dead_letter`) · embeddings conservés indéfiniment · articles `filtered` supprimés à 30 j · contenu des `filtered` / `duplicate` purgé immédiatement.
15. **(proposé)** Service Docker **one-shot `migrate`** qui applique les migrations avant le démarrage de `app` et `worker` — évite que deux processus migrent en même temps. Chaque processus refuse de démarrer si le schéma n'est pas à jour.
16. **(proposé)** `Event.distinct_channel_count` (nombre de **types** de canaux distincts) en plus de `distinct_source_count` : alimente l'indicateur « écosystèmes » des sujets émergents.
17. **(proposé)** Statut `AIJob` **`cancelled`** : un `dead_letter` peut être abandonné depuis le dashboard, ce qui débloque la purge de l'article (règle Partie II §8.5).
18. **(proposé)** `AlertLog.dedup_key` unique : garantit qu'une même alerte n'est jamais envoyée deux fois.
19. **(proposé)** `Signal` : historique horaire conservé 30 jours, puis **une valeur par jour** et par topic/fenêtre.

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
```

**Conséquence assumée de `synchronous=NORMAL` en WAL** : en cas de coupure électrique, les toutes dernières transactions validées peuvent être perdues ; la base n'est **jamais corrompue**. Acceptable pour ce produit.

L'auto-checkpoint WAL reste à sa valeur par défaut ; la taille du fichier `-wal` est surveillée (Partie II §8.6).

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

### 10.5 Migrations

- Alembic avec **`render_as_batch=True`** (SQLite ne sait pas modifier une contrainte par `ALTER`).
- **(proposé)** Les migrations sont appliquées par un **service one-shot `migrate`** (`alembic upgrade head`) ; `app` et `worker` démarrent après sa réussite (`depends_on` + `service_completed_successfully`). Aucun des deux processus applicatifs ne migre lui-même.

### 10.6 Dates et heures

- **Tout en UTC** en base, stocké en texte ISO-8601.
- Un type SQLAlchemy dédié (`UTCDateTime`) **refuse les datetimes sans fuseau** à l'écriture et renvoie des datetimes UTC à la lecture. Conversion en heure locale **uniquement à l'affichage**.

### 10.7 Transactions courtes

Rappel des contraintes de la Partie II §8.6 : transactions d'écriture découpées en lots bornés côté worker ; aucune écriture longue côté app ; lectures paginées. Échec après `busy_timeout` = retry borné + métrique dédiée. En cas de verrous persistants : **instrumenter avant de changer d'architecture**.

## 11. Modèle de données

### 11.0 Conventions

- **Clé primaire** : `id INTEGER PRIMARY KEY` partout (sauf tables de liaison et clé/valeur).
- **Horodatage** : `created_at` et, pour les tables modifiables, `updated_at` — type `UTCDateTime` (§10.6).
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
| `type` | texte (validé par le code) | V1 : `rss · github · hackernews · reddit · youtube` |
| `url` | texte | endpoint ou flux |
| `config` | JSON | paramètres propres au collector (subreddit, dépôt, requête…) |
| `enabled` | booléen | |
| `poll_interval` | entier (secondes) | |
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
| `published_at` · `discovered_at` | `UTCDateTime` ; index sur `published_at` | |
| `content` | texte, nullable | **tampon de traitement**, purgé (Partie II §8.5) |
| `content_hash` | texte ; index (non unique) | conservé après purge |
| `content_purged_at` | nullable | |
| `relevance_score` | réel | |
| `status` | `CHECK {ready, filtered, duplicate}` ; index | |
| `duplicate_of_id` | FK `Article`, nullable | renseigné si `duplicate` |
| `event_id` | FK `Event`, nullable ; index | appartenance à un événement |
| `summary` | texte, **non nul** si `ready` | aperçu : repli à l'insertion, puis synthèse LLM |
| `summary_origin` | `CHECK {fallback, llm}` | |
| `summary_lang` | texte | |
| `processed_at` | nullable | posé quand **tous** les traitements de l'article sont terminés ; point de départ du délai de grâce |

**Contraintes** : `UNIQUE(canonical_url)` · `UNIQUE(source_id, external_id)` partielle, `WHERE external_id IS NOT NULL`.

**Transitions de `status`** : l'insertion se fait en `ready` ou `filtered`. Seule transition autorisée ensuite : `ready → duplicate` (dédup sémantique rétroactive). Un article `duplicate` **conserve** ses topics et son résumé ; il est seulement **masqué à l'affichage**.

### 11.3 Event — *écrit par le worker*

| Colonne | Type / contrainte | Rôle |
|---|---|---|
| `title` | texte, non nul | repli = titre de l'article représentatif |
| `title_origin` | `CHECK {fallback, llm}` | indique ce que `resolve_event` doit encore enrichir |
| `description` | nullable | produite par `resolve_event` |
| `representative_article_id` | FK `Article` | article le plus ancien du groupe |
| `first_seen_at` · `last_seen_at` | | |
| `article_count` | entier | |
| `distinct_source_count` | entier, non nul, défaut 1 | **hotness** |
| `distinct_channel_count` | entier, non nul, défaut 1 | **(proposé)** nombre de types de canaux distincts |
| `importance` · `novelty` | réels, nullable | |
| `status` | `CHECK {active, merged, archived}` | |
| `merged_into_id` | FK `Event`, nullable | renseigné si `merged` |

**Invariant** : `distinct_source_count` = nombre de `source_id` distincts parmi les articles `ready` rattachés. Il est mis à jour **dans la même transaction** que le rattachement ; un contrôle de cohérence peut le recalculer. L'invariant est testé.

### 11.4 Topic — *écrit par le worker*

`slug` (**UNIQUE**) · `name` · `description` · `parent_id` (FK `Topic`) · `origin` `CHECK {seeded, discovered, user}` · `keywords` (JSON — mots-clés et motifs utilisés par le relevance filter) · `enabled`.

`origin` remplace le booléen `seeded` de la V0.3. Le suivi et la mise en sourdine ne sont **pas** ici : ce sont des préférences (§11.12).

### 11.5 ArticleTopic — *écrit par le worker*

`article_id` · `topic_id` · `method` `CHECK {keyword, llm}` · `confidence` · `created_at`.
**Clé** : `(article_id, topic_id, method)` — un même topic peut être attribué par les deux méthodes ; les tendances comptent les **articles distincts**.

### 11.6 Entity — *écrit par le worker*

`type` (validé par le code : `company · product · person · project · technology · model · repository`) · `name` · `canonical_name` · `origin` `CHECK {dictionary, llm}`.
**Contrainte** : `UNIQUE(type, canonical_name)`.

### 11.7 ArticleEntity — *écrit par le worker*

`article_id` · `entity_id` · `method` `CHECK {keyword, llm}` · `confidence`.
**Clé** : `(article_id, entity_id, method)`.

### 11.8 Signal — *écrit par le worker*

`topic_id` · `period` `CHECK {24h, 7d, 30d}` · `computed_at` · `window_start` · `window_end` · `mentions` · `unique_sources` · `unique_authors` · `unique_companies` · `growth_rate` · `velocity` · `novelty` · `momentum` · `category` `CHECK {established, trending, emerging, declining}`.
**Index** : `(topic_id, period, computed_at)`.

### 11.9 Embedding — *écrit par le worker*

`article_id` · `model` · `dim` · `vector` (BLOB, `float32`, **normalisé**) · `created_at`.
**Contrainte** : `UNIQUE(article_id, model)`. Détails en §12.

### 11.10 AIJob — *créé par le worker ou l'app ; exécuté par le worker*

| Colonne | Type / contrainte | Rôle |
|---|---|---|
| `job_type` | texte (validé par le code) | `classify_article · extract_topics · extract_entities · summarize_article · resolve_event · discover_topics · analyze_trend` |
| `entity_type` · `entity_id` | texte · entier (sans FK) | cible du job |
| `priority` | entier | |
| `status` | `CHECK {pending, processing, completed, failed, retry, dead_letter, cancelled}` | |
| `attempts` · `max_attempts` | entiers | |
| `next_attempt_at` | non nul, défaut = maintenant | |
| `last_error` | texte | |
| `created_by` | `CHECK {worker, app}` | |
| `started_at` · `completed_at` | nullable | |

**Statuts terminaux** : `completed` · `failed` (erreur non rejouable, ex. `job_type` inconnu) · `dead_letter` (tentatives épuisées) · `cancelled` **(proposé)** — `dead_letter` abandonné par l'utilisateur. Un `dead_letter` peut aussi être **remis en `pending`** depuis le dashboard.

**Contraintes** :

- **Un seul job actif par cible et par type** : index unique partiel sur `(job_type, entity_type, entity_id)` `WHERE status IN ('pending','processing','retry')`. Une seconde demande identique est ignorée sans erreur.
- **Index de claim** : `(status, next_attempt_at, priority)`.

**Idempotence des résultats** : elle ne repose pas sur `AIJob` mais sur les tables métier. Un job **remplace** ses propres résultats pour sa cible dans une seule transaction — par exemple `extract_topics` supprime puis réécrit les lignes `method=llm` de l'article, sans toucher aux lignes `method=keyword`. Rejouer un job produit donc le même état final.

### 11.11 CollectorRun — *écrit par le worker* (nouveau)

Une ligne par exécution d'un collector : `source_id` · `started_at` · `finished_at` · `status` `CHECK {success, partial, failed}` · `items_fetched` · `items_created` · `items_duplicate` · `items_filtered` · `items_skipped` · `http_status` · `error`.
Alimente les métriques par source (§39) ; `items_skipped` compte les items malformés, non persistés.

### 11.12 Tables écrites par l'app (nouvelles)

| Table | Colonnes | Contrainte |
|---|---|---|
| **`UserPreference`** | `subject_type` `CHECK {topic, source}` · `subject_id` · `action` `CHECK {follow, mute}` | `UNIQUE(subject_type, subject_id)` |
| **`Setting`** | `key` (PK) · `value` (JSON) · `updated_at` | réglages globaux : seuil d'importance, fréquence des alertes… |
| **`ReadState`** | `subject_type` `CHECK {event, article}` · `subject_id` · `read_at` | `UNIQUE(subject_type, subject_id)` |
| **`EmergingDecision`** | `candidate_id` (FK) · `decision` `CHECK {follow, ignore, mute, create_topic}` · `decided_at` | `UNIQUE(candidate_id)` |

**Règle « lu »** : un article rattaché à un Event est lu quand son Event est lu ; `ReadState` sur un article ne sert qu'aux articles sans Event.

### 11.13 Tables écrites par le worker (nouvelles)

| Table | Colonnes | Contrainte |
|---|---|---|
| **`EmergingCandidate`** | `key` (terme normalisé) · `label` · `first_detected_at` · `last_evidence_at` · `evidence` (JSON : mentions, sources, écosystèmes, croissance) · `topic_id` (FK, renseigné quand le worker crée le topic suite à `create_topic`) | `UNIQUE(key)` |
| **`AlertLog`** | `alert_type` `CHECK {important_event, emerging_topic, daily_digest, weekly_digest}` · `subject_type` · `subject_id` · `channel` `CHECK {email, telegram}` · `status` `CHECK {sent, failed}` · `error` · `dedup_key` | **(proposé)** `UNIQUE(dedup_key)` — une alerte n'est jamais émise deux fois, même en échec (pas de reprise en V1) |
| **`SystemState`** | `key` (PK) · `value` (JSON) · `updated_at` | clés : `worker_heartbeat`, `last_backup`… ; chaque clé a un seul écrivain |

Le candidat émergent et la décision de l'utilisateur sont **deux tables distinctes** pour respecter la règle d'un seul écrivain par table.

### 11.14 Index plein texte `article_fts`

Table virtuelle **FTS5** sur `title` et `summary`, en mode *external content* (adossée à `Article`), tokenizer `unicode61 remove_diacritics 2`. Maintenue par **triggers** sur insertion, mise à jour et suppression d'`Article` — donc écrite par le worker. La mise à jour d'un résumé par le LLM met l'index à jour automatiquement.

## 12. Embeddings

Les embeddings appartiennent à la **couche cœur** (Partie II §6.1) : calcul local, CPU, sans appel réseau. Ils servent à la similarité, au clustering, à la dédup sémantique et à la découverte de topics.

### 12.1 Moteur et modèle

- **Moteur** : `fastembed` (onnxruntime). Pas de PyTorch ni d'environnement HuggingFace lourd.
- **Modèle** : **multilingue**, obligatoire — les sources sont EN + FR, et un modèle anglais seul ne rapprocherait pas un article français de son équivalent anglais.
- **Cible** : `paraphrase-multilingual-MiniLM-L12-v2`, 384 dimensions. Sa disponibilité dans `fastembed` est **à vérifier au sprint concerné** ; à défaut, un autre modèle multilingue de 384 dimensions au plus, supporté par `fastembed`, choix tracé en ADR.
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
- On ne compare **que des vecteurs produits par le même modèle**.

### 12.5 Changement de modèle

Un nouveau modèle produit de nouvelles lignes (`model` différent). Les anciens articles ne peuvent **pas** être ré-embeddés sur leur contenu, qui a été purgé ; si besoin, ils le sont sur **titre + résumé**, avec une qualité moindre. Ce cas est exceptionnel et reste manuel en V1.

## 13. Rétention des données

**Principe** : le produit accumule des **événements, topics, signaux, résumés et liens** — pas une archive d'articles. Toute suppression est exécutée par l'**étage de purge** du worker (Partie II §8.5), journalisée à chaque passage. Aucune donnée métier n'est supprimée hors de ce tableau.

| Donnée | Rétention |
|---|---|
| `Article.content` — article `ready` | purgé à `processed_at` **+ 1 jour** (configurable) ; **jamais** tant qu'un job de l'article est en `dead_letter` |
| `Article.content` — article `filtered` ou `duplicate` | purgé **immédiatement** |
| Ligne `Article` — `ready` ou `duplicate` | **indéfinie** (titre, URLs, métadonnées, résumé, hash) |
| Ligne `Article` — `filtered` | **supprimée à 30 jours** |
| `Event` · `Topic` · `Entity` · tables de liaison | indéfinie |
| `Embedding` | indéfinie (volume faible ; utile pour la recherche sémantique V2) |
| `Signal` | **(proposé)** valeurs horaires conservées 30 jours, puis une valeur par jour et par topic/fenêtre, conservée indéfiniment |
| `AIJob` — `completed` · `failed` · `cancelled` | supprimé à 30 jours |
| `AIJob` — `dead_letter` | conservé jusqu'à action de l'utilisateur (relance ou abandon) |
| `CollectorRun` | 30 jours |
| `AlertLog` | 1 an (sert à la dédup des alertes) |
| `UserPreference` · `Setting` · `ReadState` · `EmergingCandidate` · `EmergingDecision` · `SystemState` | indéfinie |

**Effet de bord accepté** : un item `filtered` supprimé à 30 jours pourrait être re-collecté s'il réapparaît dans un flux ; il serait simplement réévalué et à nouveau écarté. Le checkpoint de collecte rend ce cas rare.

**Taille attendue** : la purge du contenu borne la base par le **nombre** d'articles, pas par leur longueur — de l'ordre de quelques centaines de Mo par an au volume réaliste. La taille de la base reste surveillée (§39, §44).

---

## Reporté en V2 (tracé depuis la Partie III)

- **Index vectoriel** (`sqlite-vec` ou équivalent) : uniquement si le cosine brute-force devient mesurablement insuffisant.
- **Recherche sémantique** de l'historique (déjà reportée par la Partie I) — les embeddings conservés indéfiniment la rendront possible.
- **Alias et fusion d'entités** (ex. « Claude Code » / « claude-code » / « CC ») au-delà du `canonical_name`.
- **Ré-embedding complet** lors d'un changement de modèle.

---

## Impacts à répercuter dans les autres parties

À traiter lors de la revue des parties concernées — **hors Partie III**.

### Partie II — Architecture (corrections)

- **§7.1 et §9.3** : remplacer « item malformé → `status=error` » par « item malformé **non persisté**, compté dans `CollectorRun.items_skipped` » (le statut `error` n'existe plus).
- **§8.3 Propriété des tables** : compléter avec `CollectorRun`, `Setting`, `UserPreference`, `ReadState`, `EmergingCandidate`, `EmergingDecision`, `AlertLog`, `SystemState`.
- **§9.1** : la phrase « clustering par entités continue sans LLM » devient vraie grâce à `entities.yaml` (`method=keyword`) — y faire référence.
- **Impacts Partie III de la Partie II** : la « contrainte d'unicité (`entity_id`, `job_type`) » est remplacée par l'index unique partiel sur les jobs actifs + l'idempotence par remplacement des résultats (§11.10).
- **§8.5** : « job résolu ou abandonné » = relancé en `pending` ou passé en `cancelled`.

### Partie IV — Pipeline d'ingestion

- **Relevance filter** : écrit les `ArticleTopic` (`method=keyword`) des articles `ready`, et les `ArticleEntity` (`method=keyword`) à partir de `entities.yaml`.
- **Dédup exacte** : un doublon exact **n'est pas inséré** (compté dans `CollectorRun`) — supprimer le statut `duplicate` de ce stade (§19 V0.3).
- **Dédup par `content_hash`** : appliquée seulement au-delà d'une longueur minimale de contenu, pour éviter les collisions sur des extraits vides ou très courts.
- **Normalisation** : chaque collector remplit `url` (page propre de l'item) **et** `link_url` (lien externe éventuel).
- **Checkpoint** : stocké dans `Source.checkpoint` ; `sources.yaml` porte une `key` unique par source.
- **Résumé de repli** : initialisé à l'insertion (`summary_origin=fallback`).
- **Nouveau fichier** `config/entities.yaml` à décrire au §16.

### Partie V — Intelligence

- **`Event.importance`** : aucune formule n'est définie — à spécifier.
- **Longueur maximale du résumé de repli** (troncature) : à fixer.
- **Fréquence de calcul des `Signal`** : à fixer (le modèle suppose un calcul horaire).
- **Sujets émergents** : `distinct_channel_count` fournit l'indicateur « écosystèmes ».
- **Jobs LLM** : chaque job **remplace** ses résultats `method=llm` pour sa cible ; `resolve_event` passe `title_origin` à `llm`.

### Partie VII — Ops

- **Service one-shot `migrate`** dans Docker Compose, avant `app` et `worker`.
- **Backup** : utiliser l'API de sauvegarde en ligne de SQLite ou `VACUUM INTO` — **jamais une copie brute** du fichier pendant que la base est ouverte. Le backup écrit `SystemState.last_backup`.
- **Volume** : local, jamais sur un système de fichiers réseau.

---

# Partie IV — Pipeline d'ingestion

2026-09-22

> **Partie IV — Pipeline d'ingestion.** Version durcie issue de la revue §14–§22.
> Remplace la Partie IV de SPEC.md V0.3. Prend les Parties I, II et III durcies comme acquis.

---

## Décisions tranchées dans cette revue (Partie IV)

Les points marqués **(proposé)** n'ont pas été discutés explicitement : ce sont des précisions de mise en œuvre qui découlent des décisions validées. Ils sont à confirmer à la relecture.

1. **Les collectors ne touchent jamais la base.** Un collector transforme des réponses HTTP en `RawItem`, rien de plus. Un **runner** unique enchaîne les étages suivants et gère toutes les écritures.
2. **Nouvelle interface `Collector`** : itérateur asynchrone de **pages** (`items` + `checkpoint` + `quota` + `skipped`) au lieu de `fetch() -> list[RawItem]`.
3. **Une transaction d'écriture par page** (≤ 50 items), en `BEGIN IMMEDIATE`. Le checkpoint est écrit **dans la même transaction** que les items de la page. **Aucun appel réseau dans une transaction d'écriture.**
4. **Le checkpoint est une optimisation, pas une garantie.** L'absence de doublon repose sur la dédup exacte ; un checkpoint perdu coûte des requêtes, jamais des doublons.
5. **Dédup exacte, dans cet ordre** : `(source_id, external_id)` → `canonical_url` → `content_hash`. Filet final `INSERT … ON CONFLICT DO NOTHING`. Un doublon **n'est pas inséré** ; il est compté.
6. **`content_hash`** : SHA-256 du texte **du flux** normalisé, `NULL` sous 200 caractères, **jamais recalculé** après extraction.
7. **`content` est toujours du texte brut** (HTML retiré dès la normalisation).
8. **Relevance filter entièrement spécifié** : score par topic basé sur la **présence** de mots-clés (titre × 3, URL × 2, corps × 1), `relevance_score = max` des topics, seuil 3. **Aucun critère de diffusion** (pilier *recall*, Partie I).
9. **Mots-clés d'exclusion par topic dès la V1**, appliqués par **masquage** du texte avant matching **(proposé — précise le mécanisme)**.
10. **Sources de confiance** : `relevance: always` → article toujours `ready`, topics et entités keyword quand même calculés.
11. **Décision de pertinence sur le texte du flux ; liaisons keyword sur le texte final** (après extraction) pour les articles `ready` **(proposé)**.
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
20. **Nouveau fichier `config/pipeline.yaml`** : tous les réglages « configurables » du pipeline y vivent, avec les défauts documentés ici **(proposé)**.
21. **Embeddings : file dérivée**, sans `AIJob` — le worker embedde les articles `ready` sans ligne `Embedding` pour le modèle courant.
22. **Jobs LLM** : la Partie IV pose seulement le principe (jobs d'enrichissement créés pour chaque article `ready`, dans la transaction d'insertion) ; la liste exacte des `job_type` relève de la Partie V.
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

### 14.3 Écriture d'une page

Dans une seule transaction `BEGIN IMMEDIATE` :

1. insertion des articles (`ready` et `filtered`) avec `ON CONFLICT DO NOTHING` — un conflit est compté en `duplicate` ;
2. pour les `ready` : `ArticleTopic` et `ArticleEntity` `method=keyword`, création des `Entity` issues du motif GitHub (§16.4), création des jobs d'enrichissement LLM (liste en Partie V) ;
3. mise à jour de `Source.checkpoint` avec le checkpoint de la page, et des champs de quota si la page en fournit.

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
- `last_error` si `partial` ou `failed` (message sans secret) ;
- `last_http_status` = statut de la dernière réponse du provider (hors extraction).

## 15. Collectors

### 15.1 Interface

```python
class Collector(Protocol):
    type: ClassVar[str]                       # clé du registre ; = Source.type
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

- Chargement **au démarrage du worker uniquement**, après la vérification du schéma (Partie III §10.1) et **avant** le démarrage du scheduler. Modifier un fichier demande un redémarrage du worker. L'app ne charge pas ces fichiers.
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

> **Impact Partie III** : `Source` doit porter `relevance` et `extract` (colonnes ou clés de `config`). Recommandation : deux colonnes, avec contrainte `CHECK`.

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

**Upsert** (clé `slug`) : `origin = seeded`.

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
- Commande `python -m app.cli validate-config` : même validation, sans base. Jouée en CI.
- `pipeline.yaml` est optionnel : absent → défauts. Présent, il est validé comme les autres.

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
- masquage de l'en-tête `Authorization` et des paramètres sensibles dans tous les logs.

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
- **Variable manquante** → les sources de ce type ne sont **pas planifiées** ; log `warning` ; état « credentials manquants » exposé au monitoring (impact Partie VII). Le worker démarre quand même.
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

---

## Impacts à répercuter dans les autres parties

À traiter lors de la revue des parties concernées — **hors Partie IV**.

### Partie I — Vision

- **§2.2 Canaux** : ajouter le collector **`webpage`** (dernier recours, sites sans flux, une page, `robots.txt`) à la liste des canaux V1.
- **§2.2 / critères de prod** : Reddit et YouTube ne dépendent plus de credentials en V1 (flux RSS).

### Partie II — Architecture

- **§7.1** : compléter le schéma avec le **contrôle d'âge** et les **liaisons keyword après extraction** ; remplacer « Enqueue → AIJob + Embedding job » par « AIJob d'enrichissement ; embeddings par file dérivée ».
- **§8.4** : les collectors ne touchent jamais la base ; toute écriture passe par le runner ; aucun appel réseau dans une transaction d'écriture.

### Partie III — Données

- **`Article.metrics`** : nouvelle colonne JSON (engagement à la collecte, validée par Pydantic, jamais mise à jour).
- **`Article.published_at`** : non nulle (repli sur `discovered_at`).
- **`Article.summary`** : renseigné aussi pour les `filtered` (la contrainte « non nul si `ready` » peut devenir « non nul »).
- **`Source`** : colonnes `relevance` `CHECK {filter, always}` et `extract` `CHECK {auto, never}`.
- **`Source.type`** : valeurs V1 = `rss · github · hackernews · reddit · youtube · webpage`.
- **`CollectorRun`** : nouvelles colonnes `items_too_old`, `extractions_attempted`, `extractions_failed`, `requests_count`.
- **Alias d'entités** : vivent dans `entities.yaml`, pas en base (cohérent avec le report V2 de la fusion d'entités).

### Partie V — Intelligence

- **Liste exacte des jobs LLM** créés à l'insertion d'un article `ready`.
- **Étage embeddings** : sélection par file dérivée (articles `ready` sans `Embedding` pour le modèle courant) ; `processed_at` doit en tenir compte.
- **Hiérarchie des topics** : pas de propagation parent en base ; décider si les tendances agrègent les enfants au calcul.
- **`Event.importance`** : peut utiliser `Article.metrics` (points HN, vues YouTube).
- **`distinct_channel_count`** : décider si `webpage` et `rss` comptent comme un même canal (« web ») ou deux.
- **Longueur du résumé de repli** : fixée en Partie IV (§14.5, 300 caractères) — retirer ce point de la liste « à fixer ».

### Partie VII — Ops

- **Monitoring** : sources non planifiées faute de credentials, disjoncteur ouvert par source, taux d'échec d'extraction, métriques `CollectorRun` (§14.4).
- **Variable d'environnement** `HTTP_CONTACT` obligatoire dans `.env.example`.

### Partie VIII — Livraison

- **CI** : étape `validate-config` sur les quatre fichiers `config/`.
- **Tests collectors** : fixtures par type (RSS, GitHub avec 304 et rate limit, Algolia, Reddit RSS avec `[link]`, YouTube RSS, `webpage` avec gabarit cassé) ; test de l'invariant de compteurs ; test de reprise par checkpoint après interruption en milieu de pagination.

---

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

