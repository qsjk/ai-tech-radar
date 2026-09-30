# Partie X — Capacités Claude

> **Partie X — Capacités Claude.** Squelette, créé le 2026-09-30 (ADR-0022, #126 ; développer puis activer, #130). Prend les Parties I à IX comme
> acquis.
> **Aucune capacité n'est adoptée.** Cette partie décrit des capacités **candidates** et n'autorise aucune
> implémentation : seule une ligne de la Partie VIII §47.5, posée après l'acceptation d'un ADR, le fait. Aucun détail
> n'est spécifié ici ; chaque capacité l'est au chapitre de formation indiqué, dans la PR de son ADR.

---

## 58. Cadre

### 58.1 Nature et statut

**Nature** (décision du 2026-09-30, revue de #127). Seules les **capacités du produit** sont des capacités au sens de
l'ADR-0022 : X.1 à X.4, X.8 et X.9. Les autres éléments de cette partie n'en sont pas :

| Nature | Éléments | Adoption |
|---|---|---|
| **Capacité du produit** | X.1 · X.2 · X.3 · X.4 · X.8 · X.9 | ADR, puis ligne du tableau des capacités de VIII §47.5 (§58.2) |
| **Exigence transverse** | X.5 : durcit l'existant et les capacités, ne s'ajoute pas au produit | ADR si la décision est structurante (Partie IX §53.1), puis ligne de la section distincte de VIII §47.5 |
| **Outillage de développement** | X.6 · X.7 : hors du produit | idem |

**Statut** :

| Statut | Sens | Où |
|---|---|---|
| **candidate** | décrite en squelette, sans contrat ; rien n'est codé, préparé ni ajouté aux dépendances | ici |
| **adoptée** | ADR accepté ; paragraphe spécifié ; ligne dans le tableau de VIII §47.5 | ici et VIII §47.5 |
| **rejetée** | ADR rejeté ; le paragraphe est conservé pour éviter de reproposer la même chose sans élément nouveau | ici |

### 58.2 Cycle d'adoption

Ce cycle vaut pour les capacités du produit ; X.5, X.6 et X.7 le suivent à l'identique, l'ADR n'étant exigé que si la
décision est structurante (§58.1).

1. Le chapitre de formation de la capacité arrive (ordre au §58.5).
2. Un ADR est proposé au prochain numéro libre (déclencheur du registre, Partie IX §54.3). Dans la même PR, le
   paragraphe de la capacité passe du squelette à la spécification, et les autres parties touchées sont mises à jour.
3. Le propriétaire accepte l'ADR ; la capacité reçoit sa ligne dans VIII §47.5 (ADR, créneau, clé de désactivation,
   tests).
4. **Développement** : au moment du chapitre, au plus tôt après les dépendances produit, le créneau réservé en VIII
   §47.2 devient un créneau planifié, avec son plan validé. La capacité est développée et fusionnée **derrière son flag
   désactivé par défaut** (VIII §48, D16, D18).
5. **Activation en production** : seulement après la décision de mise en production (Partie VIII §47.4, check-list §52), par la procédure P12 (Partie IX §56.6) ; une capacité qui
   expose des outils exige en plus son socle D19 vert. La date d'activation est portée au tableau de VIII §47.5.

X.5, X.6 et X.7 n'ont pas d'étape 5 : sans flag, ils n'ont rien à activer (§58.1).

Une capacité absente de VIII §47.5 n'est ni codée, ni préparée, ni ajoutée aux dépendances, même si elle est décrite
ici (VIII §47.5, « rien par anticipation »).

### 58.3 Règles communes

- **Désactivable par configuration** : toute capacité du produit (X.1 à X.4, X.8, X.9 ; ADR-0022), **désactivée par
  défaut** jusqu'à son activation (§58.2). Désactivée, elle laisse le produit dans l'état antérieur, cœur déterministe
  et repli compris (DV-05). La clé est fixée par l'ADR.
  X.5, X.6 et X.7 ne sont pas des capacités du produit (§58.1) : la règle ne les concerne pas.
- **Dans le budget** : le coût de chaque capacité du produit entre dans le plafond mensuel du LLM (Partie I §4.3, VII §45.1,
  V-A §24.3).
- **Socle de sécurité** : tout créneau qui expose des outils (X.1, X.2, X.3, X.8) livre des outils en lecture seule,
  le moindre privilège et un test d'injection par le contenu d'article ; X.5 durcit ensuite l'ensemble (VIII §48,
  D19).
- **Tests** : les identifiants de la capacité entrent au catalogue (VIII §50.5) avec leurs tests, au moment de son
  développement ; ils tournent flag activé, plus un test « flag coupé = état antérieur » ; l'e2e tourne avec les flags
  par défaut, donc désactivés (VIII §47.5). Aucun test n'appelle l'API réelle (VIII §50.1).

### 58.4 Rubriques d'une capacité

Chaque paragraphe du §59 au §67 porte cinq rubriques : **objectif produit** (ce que la capacité apporte à la veille),
**périmètre V1 minimal** (une ligne, sans détail), **dépendances**, **chapitre** de formation, **statut**. Les
**conflits** relevés à ce stade y sont listés, sans être tranchés : l'ADR de la capacité les tranche.

### 58.5 Ordre et chapitres

Ordre des chapitres de la formation : Ch04–Ch06 couche LLM · Ch07–Ch11 assistant et MCP · Ch12–Ch13 agents · Ch14
Claude Code · Ch15 sécurité · Ch16 évaluations · Ch17 cycle de vie. La spec ne fixe que cet ordre, jamais de date.

**Développer au chapitre, activer après la mise en production** (décision du 2026-09-30, #130) : chaque créneau est
développé au moment de son chapitre, au plus tôt après ses dépendances produit, et s'intercale entre les sprints S3 à
S11, inchangés ; une capacité du produit n'est activée qu'après la décision de mise en production (Partie VIII §47.4, check-list §52) (VIII §47.2, D18).

| Élément | § | Nature | Chapitre | Développement au plus tôt après (VIII §47.2) | Activation en production |
|---|---|---|---|---|---|
| X.4 Lecture des PDF et images | §62 | capacité du produit | Ch07 | S7 | après la mise en production, P12 |
| X.1 Assistant de veille conversationnel | §59 | capacité du produit | Ch07, Ch09, Ch11 | S9 | après la mise en production, socle D19 vert, P12 |
| X.2 Serveur MCP `radar-mcp` | §60 | capacité du produit | Ch10 | S8 | après la mise en production, socle D19 vert, P12 |
| X.3 Synthèse hebdomadaire | §61 | capacité du produit | Ch12, Ch13 | S10 | après la mise en production, socle D19 vert, P12 |
| X.7 Outillage Claude Code du dépôt | §65 | outillage de développement | Ch14, puis phase Architect | aucune dépendance produit | sans objet |
| X.5 Sécurité LLM | §63 | exigence transverse | Ch15 | créneaux qui exposent des outils (D19) | sans objet (toujours active) |
| X.6 Évaluations | §64 | outillage de développement | Ch16 | S7 | sans objet |
| X.8 Recherche approfondie | §66 | capacité du produit | phase Architect | S8 | après la mise en production, socle D19 vert, P12 |
| X.9 RAG sur l'historique | §67 | capacité du produit | phase Architect Professional | S4, X.1 | après la mise en production, P12 |

### 58.6 Conflits transverses

- **Sous-plafond par capacité** : le plafond mensuel est unique (V-A §24.3). Un sous-plafond par capacité est à
  trancher par les ADR de X.1, X.3 et X.8.
- **Évaluations en CI** : voir §64 ; à trancher par l'ADR de X.6.
- **Ch17 (cycle de vie)** n'est rattaché à aucun créneau.

---

## 59. X.1 — Assistant de veille conversationnel

| Rubrique | Contenu |
|---|---|
| Objectif produit | Interroger la veille en langage naturel depuis le dashboard ; reprend la « conversation » reportée en V2 (V-A, « Reporté en V2 ») |
| Périmètre V1 minimal | Conversation multi-tours en streaming ; outils en lecture seule : recherche d'articles, détail d'un Event, tendance d'un topic ; conversations longues |
| Dépendances | S3 (API de lecture, FTS5) · S4 (Events) · S8 (tendances) · S9 (dashboard) · budget mensuel (V-A §24.3) · socle de sécurité (§58.3) |
| Chapitre | Ch07, Ch09, Ch11 |
| Statut | candidate — à spécifier au chapitre Ch07 |

**Conflits** :
- l'appel du LLM par l'app contredit DV-09 (« depuis le seul `LLMClient` du worker ») et DV-12 (`app` sans secret ni
  sortie Internet) ; par le worker, le streaming se heurte à DV-06 (deux processus sans IPC, coordination par la base) ;
- DV-07 (un seul processus uvicorn) face à des flux longs ;
- V-A décisions 1 et 18 (catalogue des `job_type` et jobs créables par l'app, listes fermées) ;
- nouvelles tables et leur rétention (Partie III §13) ;
- coût interactif dans le plafond et priorité face aux jobs (sous-plafond, §58.6) ;
- la tension de chapitre : X.1 ne peut être développée qu'après S9 ; si Ch07 à Ch11 arrivent avant, l'exercice ne peut
  pas être pratiqué sur le produit au chapitre ; Ch10 (X.2) tombe entre Ch09 et Ch11 ;
- **à vérifier** : streaming (SSE) derrière Caddy, sous la CSP `default-src 'self'` (DV-15).

## 60. X.2 — Serveur MCP `radar-mcp`

| Rubrique | Contenu |
|---|---|
| Objectif produit | Exploiter la veille depuis Claude Code et Claude Desktop |
| Périmètre V1 minimal | Tools, resources et prompts en lecture seule sur les données de la veille (articles, Events, tendances) |
| Dépendances | S3 · S4 · S8 · socle de sécurité (§58.3) |
| Chapitre | Ch10 |
| Statut | candidate — à spécifier au chapitre Ch10 |

**Conflits** :
- un serveur dédié ajoute un **service permanent** (DV-11 ; Partie IX §53.3) et un troisième processus lecteur de la
  base (DV-06) ; servi par l'app, il lui faut une authentification propre à MCP, hors `basic_auth` (DV-13) ;
- **à vérifier** : exigences de Claude Desktop pour un serveur distant (authentification, URL publique) ; transport
  local par `docker compose exec` ; dépendances du SDK MCP Python.

## 61. X.3 — Synthèse hebdomadaire

| Rubrique | Contenu |
|---|---|
| Objectif produit | Recevoir chaque semaine une synthèse de la veille, validée par le propriétaire avant tout envoi |
| Périmètre V1 minimal | D'abord un workflow ; puis un agent Claude Agent SDK : orchestrateur, subagents par thème, hook qui bloque tout envoi non validé par le propriétaire |
| Dépendances | S8 (tendances, émergence) · S10 (canaux d'alerte) · budget mensuel · socle de sécurité (§58.3) |
| Chapitre | Ch12, Ch13 |
| Statut | candidate — à spécifier au chapitre Ch12 |

**Conflits** :
- l'Agent SDK a son propre client, hors du `LLMClient` : DV-09 (« SDK confiné au `LLMClient` ») ;
- nouveau `job_type` (V-A décisions 1 et 18) ; flux de validation par le propriétaire (écriture depuis l'app,
  anti-CSRF) ;
- coût d'une exécution multi-agents dans le plafond (§58.6) ;
- non-objectif « agent web autonome » (Partie I §5), si des outils web sont ajoutés ;
- **à vérifier** : dépendances réelles de l'Agent SDK Python (CLI Claude Code, runtime Node.js dans l'image backend,
  taille d'image M8), et son fonctionnement en sous-processus sous `read_only` et `cap_drop: ALL` (VII §36.5).

## 62. X.4 — Lecture des PDF et images liés aux articles

| Rubrique | Contenu |
|---|---|
| Objectif produit | Enrichir un article à partir des PDF et images qu'il référence |
| Périmètre V1 minimal | PDF et images liés à un article `ready`, en entrée de l'enrichissement, en volume borné |
| Dépendances | S7 (`enrich_article`) · extraction ciblée (Partie IV §17) |
| Chapitre | Ch07 |
| Statut | candidate — à spécifier au chapitre Ch07 |

**Conflits** :
- téléchargement de binaires : garde anti-SSRF, `robots.txt`, taille (Partie IV §17, §21) ;
- stockage sur `/data`, rétention (Partie III §13) et budget disque (M8) ; « pas de garantie d'archivage du contenu
  brut » (Partie I §5.1) ;
- coût en tokens des pages et des images dans le plafond ; injection par document (X.5) ;
- **à vérifier** : limites de pages et de taille des documents et des images de l'API Claude, et leur tarification.

## 63. X.5 — Sécurité LLM

| Rubrique | Contenu |
|---|---|
| Objectif produit | Rendre sûres les capacités qui lisent du contenu tiers ou exposent des outils |
| Périmètre V1 minimal | Injection de prompt par le contenu des articles ; moindre privilège des outils ; données personnelles (PII). **Suite de tests d'injection par le contenu d'article** (décision du 2026-09-30, #130) : un corpus d'articles piégés, défini par X.5, rejoué contre le double de l'API ; elle vérifie la **plomberie** du produit (délimiteurs, sortie bornée par le schéma, topics en liste fermée, aucun outil exécuté, sortie échappée). Le comportement réel du modèle face à ce corpus relève de X.6 (§64) |
| Dépendances | V-A §25.5 · socle livré par X.1, X.2, X.3 (§58.3) |
| Chapitre | Ch15 |
| Statut | candidate — à spécifier au chapitre Ch15 ; **exigence transverse**, pas une capacité du produit (§58.1) : ADR si la décision est structurante (Partie IX §53.1) |

**Conflits** :
- la suite **complète** T-LLM-15 et le test d'injection du socle D19 de chaque créneau, sans les remplacer ;
  l'activation d'une capacité à outils reste conditionnée au socle D19 vert, pas à cette suite (VIII §48) ;
- périmètre des PII dans des articles publics à définir ;
- dépendance inversée : les outils de X.1, X.2 et X.3 sont livrés avant Ch15, d'où le socle du §58.3.

## 64. X.6 — Évaluations

| Rubrique | Contenu |
|---|---|
| Objectif produit | Mesurer la qualité des tâches LLM et détecter les régressions |
| Périmètre V1 minimal | Jeu d'articles étiquetés ; graders ; régression par `PROMPT_VERSION` et par modèle, en CI ; comportement réel du modèle face au corpus d'injection défini par X.5 (§63). Suite **maintenue** sur les prompts du produit, à distinguer des exercices jetables de `lab/` (VIII §46.1) |
| Dépendances | S7 (prompts, `PROMPT_VERSION`, fixtures) · corpus d'injection de X.5 |
| Chapitre | Ch16 |
| Statut | candidate — à spécifier au chapitre Ch16 ; **outillage de développement**, hors du produit (§58.1) : ADR si la décision est structurante (Partie IX §53.1) |

**Conflits** :
- des graders qui appellent l'API en CI contredisent VIII §50.1 (réseau bloqué) et §49.3 (« aucun test n'appelle un
  vrai provider ») ; à trancher par l'ADR de X.6 ;
- DV-20 : une évaluation bloquante ou seulement mesurée ;
- coût des graders dans le plafond ;
- droits sur un jeu d'articles étiquetés versionné dans le dépôt ;
- utile dès le S7 : le chapitre arrive après la mise en production.

## 65. X.7 — Outillage Claude Code du dépôt

| Rubrique | Contenu |
|---|---|
| Objectif produit | Industrialiser le développement du dépôt avec Claude Code |
| Périmètre V1 minimal | `CLAUDE.md` hiérarchique, rules par chemin, skills, hooks ; puis (phase 2) revue de PR en CI en headless, sortie JSON validée |
| Dépendances | aucune dépendance produit ; skill `radar-dev` (#107) ; ADR-0021 |
| Chapitre | Ch14, puis phase Architect (phase 2) |
| Statut | candidate — à spécifier au chapitre Ch14 ; **outillage de développement**, hors du produit (§58.1) : ADR si la décision est structurante (Partie IX §53.1) |

**Conflits** :
- une revue de PR en CI appelle l'API réelle (VIII §49.3) avec un secret GitHub ; budget imputé (plafond du produit ou
  autre) ;
- DV-19 : la revue bloque-t-elle la CI ?
- `CLAUDE.md` hiérarchique face à Partie IX §55.3 (« règles permanentes, courtes, qui renvoient à la spec ») ;
- hooks et skills face à ADR-0021 (Docker seulement par `scripts/radar-dev`) ;
- utile dès maintenant : une partie existe déjà (`CLAUDE.md`, #107) avant le chapitre.

## 66. X.8 — Recherche approfondie sur un sujet émergent

| Rubrique | Contenu |
|---|---|
| Objectif produit | Qualifier un sujet émergent par une recherche sourcée |
| Périmètre V1 minimal | Recherche multi-agents sur un candidat émergent ; sources web citées ; provenance de chaque affirmation |
| Dépendances | S8 (candidats émergents) · budget mensuel · socle de sécurité (§58.3) |
| Chapitre | phase Architect |
| Statut | candidate — à spécifier en phase Architect |

**Conflits** :
- non-objectifs de la Partie I §5 : « agent web autonome », « scraping massif » ; et §5.1 « pas de vérification de
  véracité » face à la provenance ;
- sortie web du worker hors du `HttpClient` (DV-12, garde anti-SSRF) ;
- coût multi-agents dans le plafond (§58.6) ;
- **à vérifier** : outils serveur de recherche et de lecture web de l'API Claude (tarif, filtrage de domaines,
  citations).

## 67. X.9 — RAG sur l'historique

| Rubrique | Contenu |
|---|---|
| Objectif produit | Ancrer les réponses de l'assistant dans les articles de l'historique |
| Périmètre V1 minimal | Recherche sur les embeddings existants, au service de X.1 |
| Dépendances | S4 (embeddings) · X.1 |
| Chapitre | phase Architect Professional |
| Statut | candidate — à spécifier en phase Architect Professional |

**Conflits** :
- Partie I décision 5 et « Reporté en V2 » : recherche sémantique hors V1 ;
- DV-04 (cosine brute-force sur une fenêtre en mémoire du worker) face à une recherche sur tout l'historique ;
  Partie IX §53.3 (vector DB interdite sans preuve) ;
- recherche servie à l'app (DV-06) ;
- rétention des embeddings et du contenu purgé (Partie III §12, §13).
