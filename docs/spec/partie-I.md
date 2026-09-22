# Partie I — Vision & Objectifs

> **Partie I — Vision & Objectifs.** Version durcie issue de la revue §1–§5.
> Dernière révision : 2026-09-22. Les décisions tranchées lors de la revue
> sont récapitulées ci-dessous, puis intégrées au fil des sections.

---

## Décisions tranchées dans cette revue (Partie I)

1. **Objectif = 3 piliers**, pas un arbitrage recall *vs* precision : **recall à l'ingestion** · **precision à la présentation** · **hotness** (corroboration multi-sources rendue visible). Cf. §1.
2. **Exhaustivité = non-objectif V1**, explicitement **reportée en V2**. Cf. §5 et « Reporté en V2 ».
3. **Langues V1 = EN + FR.** Aperçu rendu **en français** quand l'AI est disponible, **repli déterministe** (titre ou extrait d'origine) sinon. Autres langues → V2.
4. **Canaux V1 = RSS + GitHub + Hacker News + Reddit + YouTube**, plus le collector **`webpage`** en dernier recours (Partie IV). **Newsletters (email) → V2.**
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

RSS (blogs / releases / flux) · GitHub · Hacker News · Reddit · YouTube ·
**`webpage`** — dernier recours pour un site sans flux : une seule page de liste,
jamais de suivi de liens, soumise à `robots.txt` (Partie IV §15.4).

Reddit et YouTube sont lus par leurs flux RSS publics : **aucune credential**
n'est requise pour eux en V1 (Partie IV §22).

**Reportés (V2)** : newsletters par **email** · autres réseaux (Mastodon, X…).
V1 ne traite que des sources exposant un **flux** exploitable par les collectors
ci-dessus, ou à défaut une page de liste lisible par `webpage` ; l'ingestion
email n'est pas au périmètre V1.

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
| **Simple** | ≤ 3–4 services Docker **permanents** (le service one-shot `migrate` n'est pas compté, Partie VII §36.2) ; démarrage local en **une** commande (`docker compose up`) ; aucune techno bannie (§5). |
| **Portable** | Migration vers un autre VPS = copie du volume persistant + `docker compose up`, **sans modification de code**. |
| **Observable** | Tout incident majeur (source / worker / LLM down, disque plein) est détectable via `/health` ou une alerte, **sans SSH**. |
| **Résilient** | Les tests de résilience de la Partie VIII passent (LLM down · 429 · source down · worker restart · VPS reboot · backup restore) : tableau de la Partie VIII §50.6. |
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
