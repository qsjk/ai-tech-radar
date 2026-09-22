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

