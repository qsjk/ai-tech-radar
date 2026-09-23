# Planning d'exécution — AI Tech Radar

> Version 1.1 · 2026-09-23 · s'appuie sur `SPEC.md` V0.4 (VIII §46–§52, IX §53–§57).
> Ce document dit **ce qui est prévu**. L'état courant vit dans le Project GitHub « Radar » ;
> le réel (plan détaillé, bilan, écarts) vit dans `docs/sprints/sprint-NN.md`.
> Il renvoie à la spec sans la recopier : en cas de divergence, la spec fait foi.

---

## 0. Conventions

| Terme | Sens |
|---|---|
| **Session** | 2 à 3 h de travail concentré, en soirée ou le week-end |
| 🤖 | Claude Code : code, tests, migrations, documents, issues et PR via `gh` |
| 👤 | Souhaib : décisions, relectures, validations, infra, comptes, mesures sur le VPS |
| **Effort** | en sessions **de Souhaib** (relecture, décisions, démo), montée en compétence Python comprise sur S0–S3, **hors tampon** |
| **Gate** | point de passage bloquant ; tant qu'il n'est pas vert, l'étape suivante ne démarre pas |

**Règles d'enchaînement** (VIII §47.1, §51.2 · IX §57.8, décision 28)

- Les sprints 🤖 sont **strictement séquentiels** : aucun sprint ne démarre avant que le précédent soit clos.
- **Entrée commune à tout sprint N** : sprint N−1 clos + `docs/sprints/sprint-NN.md` rédigé par 🤖 et **validé par 👤** + issues 🤖 du sprint créées depuis ce plan.
- **Sortie commune à tout sprint N** : critères d'acceptation VIII §47.2 verts · identifiants de tests du sprint couverts (VIII §50.5) · DoD fonctionnalité (§51.1) sur chaque PR · démo sur Compose neuf (`docker compose down -v` puis `up -d`) · CI verte, e2e compris sur `main` · dette et quarantaines tracées en issues · écarts à la spec résolus (§51.3) · bilan dans `sprint-NN.md` · **toutes les issues 👤 de la milestone fermées**.
- Un sprint n'est **pas fini** tant que ses tâches 👤 ne le sont pas.

**Mode de travail**

- Une issue par tâche → une branche `sNN/<n°>-slug` → une PR « Closes #n » → CI → relecture 👤 → fusion. Jamais de push direct sur `main` (règle GitHub sans contournement).
- Relecture **ligne à ligne** sur S0–S2, puis **ciblée** (CI comme filet). Relecture fine **permanente** sur : migrations, claim des jobs (`AIJob`), anti-SSRF, séquence d'envoi des alertes, backup/restauration, `deploy.sh`.
- La spec n'est pas figée : un changement passe par une PR sur `docs/spec/`, avec ADR selon le niveau (IX §53.1). Ce planning est mis à jour dans la même PR si l'impact est notable.

---

## 1. Décisions de cadrage

Prises le 2026-09-22, révisables par PR sur ce document.

| # | Sujet | Décision |
|---|---|---|
| C1 | Outillage | **Tout sur GitHub** : code, spec (`docs/spec/`), planning (ce fichier), tickets (Issues), sprints (Milestones), suivi (Project « Radar »), CI (Actions). 0 € |
| C2 | Visibilité du dépôt | **Public** : Actions sans quota sur runners standard, protection de branche disponible, aucun jeton ni clé de déploiement pour `deploy.sh`. Aucun secret dans le dépôt (gitleaks sur tout l'historique dès S1) |
| C3 | Agent | Claude Code **en local**, connecté par `gh`. Pas d'intégration `@claude` en V1 (clé API en secret du dépôt, facturation API) |
| C4 | Capacité | Hypothèse **3 sessions par semaine**, tampon **+25 %**, **2 semaines de creux** fin décembre. Recalage après S1 sur la vitesse réelle |
| C5 | Date cible | Aucune imposée ; la projection §8 en tient lieu |
| C6 | Autonomie de Claude Code | Voir « Mode de travail » ci-dessus |
| C7 | Montée en compétence | Par la relecture, sans session dédiée ; marge incluse dans les efforts S0–S3 |
| C8 | Architecture du VPS | **amd64** (IX décision 27). Fournisseur choisi en S4–S6 |
| C9 | LLM | **Go-live sans gateway** (VIII décision 21) ; LLMClient livré au S6 et testé contre le faux gateway ; accès ponctuel à un provider OpenAI-compatible aux S7–S8 pour enregistrer les fixtures (E8) ; branchement d'un gateway après le go-live, avec M6 |
| C10 | Canaux d'alerte | **Telegram + email** (routage par défaut VI §33.9 : instantané Telegram, digests email, `system` sur les deux) |
| C11 | Partie VII | **Non modifiée** en T0.1 : refaite proprement en amont, aucune reconstitution (décision du propriétaire du 2026-09-22, E9). Les impacts VIII/IX → VII non reportés sont traités dans `sprint-00-cadrage.md` (E11) |

---

## 2. Hypothèses sur la spec (E1–E10)

Relevées à la lecture de `SPEC.md` V0.4. Le planning les applique ; elles sont **consignées** dans `docs/sprints/sprint-00-cadrage.md` (T0.2) et ont été **tranchées le 2026-09-23** par 👤 : chaque hypothèse est retenue (décisions consignées dans le rapport, appliquées à la spec par T0.2b, #66).

| # | Écart | Hypothèse retenue | Décision (2026-09-23) |
|---|---|---|---|
| E1 | VIII §50.3 bloque la CI si un identifiant U/I/E/F n'a pas de test ; dès S1, ≈ 180 n'en ont pas, alors que chaque sprint finit CI verte (§47.1) | `check-test-catalog.py` contrôle les identifiants des sprints **clos et en cours** (liste tirée des `sprint-NN.md`) ; contrôle **complet** au S11 (critère A2) | retenue — VIII §50.3 |
| E2 | T-DB-12 et T-CFG-09 ne sont rattachés à aucun sprint | T-CFG-09 au S2 (avec le `HttpClient`) ; T-DB-12 au S2 (`Article.status`), complété S5 (`AIJob.status`) et S10 (`AlertLog.status`) | retenue — VIII §47.2 |
| E3 | Tests attribués avant que leur objet existe : T-PRG-05 volet `AlertLog` et T-PRG-06 (`Signal`) au S7 ; T-LLM-18 volet `discover_topics` au S7 ; T-JOB-04 `candidate_decided` au S5 | Couverture partielle au sprint annoncé, **complétée** au sprint qui livre l'objet (S8 : T-PRG-06, T-LLM-18, T-JOB-04 · S10 : T-PRG-05) | retenue — VIII §47.2 ; identifiant « partiel » précisé en T0.5 |
| E4 | Rattachés trop tard par le joker du S11 : T-OPS-16 (misfires, scheduler du S2), T-SEC-10 (modèle intégré à l'image, S4) | T-OPS-16 au S2, T-SEC-10 au S4 | retenue — VIII §47.2 |
| E5 | CI étape 5 : « modèle d'embeddings présent dans l'image » dès S1 | Vérification **activée au S4** ; tranché dans `sprint-01.md` | retenue — VIII §49.2 ; reprise dans `sprint-01.md` (T0.8) |
| E6 | T-CFG-04 (toutes les sections de `pipeline.yaml`) listé au S2 | Validation **incrémentale** : chaque sprint ajoute et teste ses sections (DoD §51.1-5) | retenue — VIII §47.2 ; T-CFG-04 complet au S11 |
| E7 | `enrich_article` créés dès S2 (T-COL-12) | Table `AIJob` introduite **au S2** ; `database.md` (T0.4) le reflète | retenue — VIII §47.2 ; `database.md` (T0.4) |
| E8 | T-LLM-16 (niveau U, donc bloquant) exige des sorties LLM **réelles** enregistrées | Accès ponctuel à un provider aux S7–S8 (C9), tâche 👤 | retenue ; en repli, T-LLM-16 scindé (option B du rapport) |
| E9 | Partie VII reconstituée depuis un PDF : §36.7 `.env.example`, §39.5 conditions, §45.3–§45.4 mesures dégradés ; §57.2 exige la source Markdown | **Levé** le 2026-09-22 : Partie VII refaite en amont, non modifiée par T0.1 (C11) ; conséquences en E11 du rapport de cadrage | levée confirmée ; Partie VII réconciliée par T0.1c, intégrée à T0.2b (#66) |
| E10 | §57.2 attend dix fichiers de spec ; `SPEC.md` est consolidé | T0.1 commence par un **découpage mécanique** en `docs/spec/partie-*.md`, dans un commit séparé, sans aucune modification | réalisé par T0.1a (#57) |

---

## 3. Vue d'ensemble

| Étape | Objectif | Identifiants (≈) | Effort (sessions) | Gate / mesures | Fin prévue (§8) |
|---|---|---|---|---|---|
| Pré-S0 | Préalables et outillage | — | 1–2 | — | 02/10/2026 |
| **S0** | Cadrage, sans code | — | 5–7 | **G1 faisabilité** | 20/10/2026 |
| S1 | Foundation | 28 | 6–9 | **G2 socle** | 11/11/2026 |
| S2 | Collecte & pipeline déterministe | ≈ 41 | 6–9 | — | 03/12/2026 |
| S3 | Feed | 10 | 3–5 | — | 14/12/2026 |
| S4 | Embeddings & clustering | ≈ 24 | 5–7 | **G3 cœur sans LLM** · M1, M2 indicatives | 15/01/2027 |
| S5 | File de jobs | 9 | 2–3 | — | 22/01/2027 |
| S6 | LLM Gateway & LLMClient | 19 | 3–4 | ADR-0020 | 01/02/2027 |
| S7 | Intelligence & purge | ≈ 14 + compléments | 4–5 | — | 14/02/2027 |
| S8 | Trends & émergence | 15 + compléments | 4–6 | M5 indicative | 01/03/2027 |
| S9 | Dashboard | ≈ 8 | 4–5 | — | 14/03/2027 |
| S10 | Alertes | 17 | 3–5 | **G4 fonctionnel complet** | 26/03/2027 |
| S11 | Production | ≈ 25 + 3 M | 6–8 | **G5 pré-prod** | 15/04/2027 |
| Pré-prod | ≥ 14 jours sur le VPS cible | M1–M10 | 5–7 | **G6 go-live** | ≥ 02/05/2027 |
| **Total** | | 211 (208 auto · 3 M) | **57–82** | | |

---

## 4. Chemin critique

```
👤 Pré-S0 ─► S0 ─G1─► S1 ─G2─► S2 ─► S3 ─► S4 ─G3─► S5 ─► S6 ─► S7 ─► S8 ─► S9 ─► S10 ─G4─► S11 ─G5─► Pré-prod (≥14 j) ─G6─► Prod
```

- **Côté 🤖, tout est sur le chemin critique** : aucun sprint ne peut en chevaucher un autre.
- **Seul parallélisme possible** : la piste 👤 (§7), menée pendant que Claude Code avance.
- **Tâches 👤 qui deviennent critiques si elles glissent** :

| Tâche 👤 | Bloque |
|---|---|
| Relecture de la PR T0.1 et arbitrages du rapport de cadrage | tout le S0, donc tout le reste |
| Décision ADR-0020 (gateway ou « sans LLM ») | clôture S6 |
| Accès provider pour les fixtures (E8) | clôture S7 et S8 (T-LLM-16 bloquant) |
| VPS provisionné et durci, domaine et DNS, bucket restic | clôture S11 (la pré-prod doit démarrer sur le VPS, D15) |
| Monitoring externe, canal d'alerte réel | J0–J1 de la pré-prod |

- **Plancher calendaire incompressible** : 14 jours de pré-prod (warm-up de l'émergence) + la revue §52.

---

## 5. Fiches par étape

Les entrées et sorties **communes** (§0) s'appliquent à chaque sprint ; les fiches ne listent que le spécifique. « Tests » = identifiants du catalogue VIII §50.5 à couvrir et verts en fin de sprint.

### Pré-S0 — Préalables

| | |
|---|---|
| **Objectif** | Réunir les préalables d'IX §57.2 et l'outillage GitHub |
| **Livrables** | dépôt public `ai-tech-radar` · `docs/spec/SPEC.md` (spec brute, découpée ensuite en `docs/spec/partie-*.md` par T0.1a) · `docs/planning.md` · règle de protection de `main` · labels, milestones, Project « Radar », issues de Pré-S0, S0 et piste 👤 |
| **Entrée** | — |
| **Sortie** | depuis Claude Code, `gh issue list --milestone S0` renvoie les issues du S0 · une PR de test ne peut pas être poussée directement sur `main` |
| **Effort** | 1–2 · entièrement 👤 |
| **Risques** | droit `project` absent du jeton `gh` (→ `gh auth refresh -s project`) |

### S0 — Cadrage *(IX §57, sans code applicatif)*

| | |
|---|---|
| **Objectif** | Transformer la spec en contrat cohérent et vérifié, préparer le S1 |
| **Livrables 🤖** | **T0.1a** découpage mécanique en `docs/spec/partie-*.md` (E10) · **T0.1b** report des impacts, retrait des marqueurs, `SPEC.md` en index, Partie VII non modifiée (C11, E9) — **PR dédiée** · **T0.2** `sprint-00-cadrage.md` (conflits, décisions manquantes dont E1–E10, risques, questions) · **T0.3** vérifications §57.4 · **T0.4** `database.md` (table par table, sprint d'introduction) · **T0.5** `architecture.md` (arborescence, configuration, Compose proposé, CI, `Clock`, `check-test-catalog.py`) · **T0.6** ADR 0001–0019 + index + gabarit · **T0.7** `CLAUDE.md` · **T0.8** `sprints/sprint-01.md` · **T0.9** ADR-0021 et E22, accès à Docker en développement (#60) |
| **Entrée** | Pré-S0 clos |
| **Sortie** | check-list IX §57.7 entièrement cochée : PR T0.1 fusionnée · documents présents · ADR 0001–0019 `Accepté` · plus aucune question ouverte · vérifications concluantes ou couvertes par ADR · diff limité à `docs/`, `SPEC.md`, `CLAUDE.md` · validation 👤 |
| **Dépendances** | T0.1 fusionnée **avant** T0.2–T0.8 (IX décision 11) |
| **Effort** | 5–7 : relecture T0.1 (2) · arbitrages (1–2) · ADR (1–2) · plan S1 (1) |
| **Risques** | diff T0.1 illisible (→ un commit par partie cible) · ~~Partie VII non réconciliée avec VIII et IX~~ : levé par T0.2b (#67), Partie VII réconciliée (E11) · vérification bloquante en échec (→ **stop**, replanification, voir G1) |
| **👤** | relire et fusionner la PR T0.1 · trancher le rapport de cadrage · accepter les ADR · valider `sprint-01.md` · revue d'acceptation |

### S1 — Foundation

| | |
|---|---|
| **Objectif** | Socle exécutable, durci et outillé, sans fonction métier |
| **Livrables 🤖** | FastAPI + SQLAlchemy async/aiosqlite, deux fabriques de sessions, PRAGMA, `UTCDateTime`, `Clock` · Alembic + service `migrate` · worker minimal (heartbeat, fail-fast, watchdog, boot, SIGTERM) · `/health` et `/api/health` minimal · configuration typée, `validate-config` · logs structlog et nettoyage des secrets · Caddy (TLS interne, basic_auth, en-têtes) · Compose conforme VII §36.5 · CI six étapes, doubles branchés, blocage réseau, traçabilité (mécanisme E1) · `.github/` : modèles d'issue et de PR (check-list DoD §51.1) · **`scripts/radar-dev` V0** (#62, E22, ADR-0021), après le socle Compose · `runbook.md`, `testing.md`, `deployment.md` (dev) |
| **Tests** | T-DB-01 à 08 · T-CFG-01, 02, 05, 07 · T-OPS-01 à 03, 07 à 11 · T-SEC-01 à 03, 05, 06, 08, 09 (sans restic) · T-RES-10 |
| **Sortie spécifique** | `docker compose up -d` : `migrate` terminé, `app`/`worker`/`caddy` `running` · `https://localhost/health` = ok sans auth, `/api/health` 401 · WAL actif · refus de démarrer hors `head` · CI verte e2e compris |
| **Dépendances** | D1 → D2 → D3 → D4 (VIII §48) |
| **Effort** | 6–9 |
| **Risques** | courbe asyncio / SQLAlchemy async (`BEGIN IMMEDIATE`) · racine en lecture seule et non-root dès le départ · durée CI (e2e Compose dans Actions) · certificat Caddy local non reconnu par le navigateur · mypy strict |
| **👤** | **poste de dev : Docker rootless, retrait du groupe `docker`** (#61), avant le premier Compose, une fois l'ADR-0021 accepté · checks CI obligatoires sur `main` dès que la CI minimale de T1.1 est verte, puis les checks 1–5 une fois la CI complétée (T1.11) · démo sur Compose neuf |

### S2 — Collecte & pipeline déterministe

| | |
|---|---|
| **Objectif** | Ingestion complète des six types de sources, sans LLM ni clustering |
| **Livrables 🤖** | `HttpClient` partagé (limiteur, retry, `Retry-After`, quota, anti-SSRF, `robots.txt`, User-Agent) · interface `Collector` et registre · collectors `rss`, `github`, `hackernews`, `reddit`, `youtube`, `webpage` · runner (normalisation → relevance → extraction → liaisons keyword → résumé de repli, transaction par page, checkpoint, `CollectorRun`) · disjoncteur par source, scheduler · `trends_since` (D11) · table `AIJob` et création des `enrich_article` (E7) · validation des trois fichiers `config/` · faux serveur de sources · `collectors.md` · **skill `radar-dev` V1** (#63, E22) |
| **Tests** | T-PIPE-* · T-HTTP-* · T-COL-* · T-CFG-02 à 06, 09 · T-DB-12 (`Article.status`) · T-OPS-16 · T-RES-04 |
| **Sortie spécifique** | six types collectés contre le faux serveur avec le `config/` de démo · rejeu sans doublon · invariant de compteurs · source en panne isolée |
| **Dépendances** | D4 → D5 → D6 · D7 amorcé (liaisons keyword, `entities.yaml`) |
| **Effort** | 6–9 (sprint le plus volumineux en tests) |
| **Risques** | volume de fixtures par type · coexistence anti-SSRF et hôtes de test (VIII décision 23) · RAM de lingua · gabarits `webpage` fragiles |
| **👤** | **démarrer la curation** du `config/` réel (`sources.yaml`, `topics.yaml`, `entities.yaml`) |

### S3 — Feed

| | |
|---|---|
| **Objectif** | Premier écran : lire et chercher les articles collectés |
| **Livrables 🤖** | API de lecture (stories = articles isolés), pagination keyset, filtres · `article_fts` et triggers, recherche `q` · frontend React/TS/Vite servi par Caddy (Feed, badge de hotness, indicateur repli / enrichi) · vitest, règle lint · **`radar-dev` V2, serveur MCP local — conditionnel** : go ou no-go au démarrage du sprint, sur les bilans S1 et S2 (#64, E22) |
| **Tests** | T-DB-11 · T-API-05 à 07 · T-FE-01 à 05, 07 |
| **Sortie spécifique** | Feed alimenté · recherche tolérante à la syntaxe FTS5 · aucun `offset` · build sans script ni style en ligne |
| **Effort** | 3–5 |
| **Risques** | stack frontend nouvelle · CSP stricte : une bibliothèque UI qui injecte des styles impose un ADR (IX §54.3) |
| **👤** | démo |

### S4 — Embeddings & clustering

| | |
|---|---|
| **Objectif** | Regrouper les articles en Events et rendre la hotness visible, toujours sans LLM |
| **Livrables 🤖** | file d'embeddings dérivée, calcul hors event-loop, matrice de fenêtre · Event clustering V-B §28 complet (hors `resolve_event`) · stories = Events + articles isolés · `cluster-calibrate`, `recount-events` · jeu synthétique, script de charge, projet `radar-load` · vérification CI « modèle dans l'image » activée (E5) · `measurements.md` |
| **Tests** | T-EMB-* · T-CLU-* (sauf volet `resolve_event` de T-CLU-08, et T-CLU-12) · T-API-01 (Feed) · T-SEC-10 |
| **Sortie spécifique** | un Event multi-sources = une story · moteur d'embeddings arrêté → clustering par URL et entités · **M1 et M2 indicatives** consignées |
| **Dépendances** | D7 → D8 |
| **Effort** | 5–7 |
| **Risques** | algorithme le plus délicat du produit (fusion, représentant, idempotence) · performance cosine au profil cible · taille de l'image |
| **👤** | lire M1/M2 · **conseillé** : provisionner le VPS et jouer `radar-load` dessus pour une M1 sur la vraie taille (§7) |

### S5 — File de jobs

| | |
|---|---|
| **Objectif** | File `AIJob` complète, handlers en stubs |
| **Livrables 🤖** | registre fermé, claim atomique et ordre, sémaphore, gardes et `skipped`, TTL, backoff, requalification au boot, transitions de l'app sur `dead_letter`, métriques de backlog |
| **Tests** | T-JOB-* (T-JOB-04 hors `candidate_decided`) · T-DB-09 · T-DB-12 (`AIJob.status`) |
| **Sortie spécifique** | redémarrage pendant un job → requalifié, résultat unique · `job_type` inconnu → `failed`, worker maintenu |
| **Dépendances** | D9 (file avant `LLMClient`) |
| **Effort** | 2–3 |
| **Risques** | concurrence du claim sous SQLite |
| **👤** | relecture fine du claim |

### S6 — LLM Gateway & LLMClient

| | |
|---|---|
| **Objectif** | Accès LLM optionnel, typé et résilient |
| **Livrables 🤖** | `LLMClient` (parsing, `TolerantList` / `SoftStr`, erreurs typées) · disjoncteur à trois états · budget et réserve · mode non configuré · observabilité · faux gateway · `llm-gateway.md` · **ADR-0020** (« go-live sans gateway », C9) |
| **Tests** | T-LLM-01 à 17, 19 · T-RES-01 (partie file de jobs) |
| **Sortie spécifique** | huit scénarios V-A §26.3 verts · `LLM_BASE_URL` absent → produit fonctionnel, `llm_gateway = disabled` |
| **Dépendances** | D9 (`LLMClient` avant toute tâche LLM) |
| **Effort** | 3–4 |
| **Mesures** | M6 sans objet tant qu'aucun gateway n'est retenu (F3) |
| **Risques** | T-LLM-16 n'a pas encore de sorties réelles : snapshot seul au S6, sorties au S7 (E8) |
| **👤** | accepter l'ADR-0020 · ouvrir un accès provider OpenAI-compatible pour les fixtures |

### S7 — Intelligence & purge

| | |
|---|---|
| **Objectif** | Enrichissement LLM des articles et des Events, rétention des données |
| **Livrables 🤖** | `enrich_article`, `resolve_event` · régénération, relance et abandon de `dead_letter` · anti-CSRF · étage de purge et passe `processed_at` · fixtures de prompts par `PROMPT_VERSION` |
| **Tests** | T-LLM-18 (hors `discover_topics`) · T-JOB-06 · T-CLU-08, 12 · T-PRG-01 à 05 (T-PRG-05 hors `AlertLog`) · T-API-08 à 10, 14 · T-SEC-04 · T-RES-01 · T-RES-02 (hors alertes) |
| **Sortie spécifique** | gateway coupé puis rétabli : reprise sans doublon, plus récents d'abord · purge conforme à III §13, jamais avec un `dead_letter` · API complète gateway éteint |
| **Dépendances** | D10 |
| **Effort** | 4–5 |
| **Risques** | purge = seule suppression de données métier : relecture fine |
| **👤** | lancer `scripts/record-llm-fixtures.py` (`enrich_article`, `resolve_event`) · relire la purge |

### S8 — Trends & émergence

| | |
|---|---|
| **Objectif** | Tendances par topic et sujets émergents |
| **Livrables 🤖** | Trend Engine (Signal horaire, cold start, agrégation parent, catégories) · émergence (termes, critères, warm-up, évolution significative, candidats) · `discover_topics` · décisions et « Create topic » avec backfill · job analytique horaire · `trends.md` |
| **Tests** | T-TRD-* · T-EMG-* · compléments : T-PRG-06, T-LLM-18 (`discover_topics`), T-JOB-04 (`candidate_decided`) |
| **Sortie spécifique** | horloge avancée au-delà du warm-up → un terme multi-histoires devient candidat · « Create topic » → liaisons sur les nouveaux articles et Signal à l'heure suivante · **M5 indicative** |
| **Dépendances** | D11 |
| **Effort** | 4–6 |
| **Risques** | logique temporelle dense : tout passe par la `Clock` |
| **👤** | fixtures `discover_topics` · **finir la curation** des topics et mots-clés (non rétroactifs, V-B §29.7) |

### S9 — Dashboard

| | |
|---|---|
| **Objectif** | Produit utilisable de bout en bout, hors alertes |
| **Livrables 🤖** | Overview six sections · vues Topic et Event · redirection des Events fusionnés · lu / non lu · préférences et sourdine héritée · related topics · registre des `Setting` · bandeau d'état · page des jobs en échec |
| **Tests** | T-API-01 à 04, 11 à 13 · T-FE-06 · T-CFG-08 |
| **Sortie spécifique** | une story une seule fois dans l'Overview · sourdine identique app / worker · produit utilisable gateway éteint |
| **Dépendances** | D12 |
| **Effort** | 4–5 |
| **Risques** | charge UI · cohérence de la sourdine entre les deux processus |
| **👤** | parcours manuel complet (répétition du critère B8) |

### S10 — Alertes

| | |
|---|---|
| **Objectif** | Alertes instantanées et digests, au plus une fois par canal |
| **Livrables 🤖** | canaux email et Telegram · séquence d'envoi (`sending`) · `important_event`, `emerging_topic` · fréquence, heures calmes, plafond, fuseau · digests · routage · `send-test-alert` · historique |
| **Tests** | T-ALR-* · T-DB-10 · T-DB-12 (`AlertLog.status`) · T-PRG-05 (volet `AlertLog`) · T-RES-02 (complet) |
| **Sortie spécifique** | une alerte sur les deux canaux, jamais deux fois par canal · digest quotidien reçu · canal non configuré → worker démarré, canal désactivé |
| **Dépendances** | D12 → D13 |
| **Effort** | 3–5 |
| **👤** | créer le bot Telegram et le compte SMTP · `send-test-alert` réel depuis le Compose local |

### S11 — Production

| | |
|---|---|
| **Objectif** | Exploitabilité complète et démarrage de la pré-prod sur le VPS |
| **Livrables 🤖** | `ops.tick`, `ops_metrics`, table §39.5, alertes `system`, `/api/health` complet, `degraded` · backup `VACUUM INTO` + restic, `backup-now`, `restore-test`, `scripts/restore.sh` · validation réseau et racine en lecture seule avec restic · `scripts/deploy.sh` · contrôle **complet** du catalogue (E1) · finalisation de `deployment.md`, `monitoring.md`, `backup-restore.md`, `runbook.md`, `go-live.md` |
| **Tests** | T-OPS-* · T-BKP-* · T-SEC-* · T-RES-* (automatisés) · T-RES-09, 11, 12 reportés dans `go-live.md` |
| **Sortie spécifique** | **tous** les tests automatisés du catalogue verts · pré-prod démarrée sur le VPS cible par `deploy.sh` |
| **Dépendances** | D13 → D14 · D15 (backup avant toute donnée réelle) |
| **Effort** | 6–8 |
| **Risques** | restic en racine en lecture seule · première exposition publique · temps de propagation DNS et certificat |
| **👤** | VPS durci (VII §43.1) · domaine et DNS · bucket S3-compatible et clés · `.env` en `600` et copie de référence dans le gestionnaire (avec `RESTIC_PASSWORD`) · `GITHUB_TOKEN` fine-grained · premier `deploy.sh` |

### Pré-production — J0 à J14 et plus

Voir §6 (déroulé) et G6 (§9). Effort 5–7 sessions, réparties sur au moins 14 jours calendaires.

---

## 6. Pré-production — déroulé

Instance de pré-prod = instance de prod : la base est conservée à la bascule (VIII décision 19). Preuves consignées dans `docs/go-live.md` et `docs/measurements.md`.

| Jour | Tâche | Qui | Preuve | Réf. |
|---|---|---|---|---|
| J0 | `deploy.sh` avec le `config/` réel et les sources réelles | 👤 | `~/radar-deploy.log` | §47.4 · E5 |
| J0 | Contrôle du durcissement de l'hôte (fait au provisioning, §7) | 👤 | `go-live.md` | D8 |
| J0 | HTTPS Let's Encrypt, redirection HTTP → HTTPS, DNS A (et AAAA) | 👤 | `curl -I` | D2 |
| J0–J1 | `backup-now` puis `restore-test` réussis | 👤 | `/api/health` | E2 |
| J0–J1 | `send-test-alert` sur Telegram et email ; routage `system` vérifié | 👤 | `go-live.md` | E1 · B9 |
| J0–J1 | Monitoring externe (5 min, 2 échecs) ; arrêt d'`app` → alerte reçue (T-RES-12) | 👤 | `monitoring.md` | E4 |
| J1–J3 | Profils synthétiques dans `radar-load` : M1, M2, M5, M8, M9 | 👤 | `measurements.md` | F1 |
| J3–J7 | `cluster-calibrate` sur au moins 72 h de données ; échantillons relus | 👤 | `measurements.md` | F2 |
| J3–J7 | M3, M4, M9 sur la charge réelle | 👤 | `measurements.md` | F1 |
| J7–J10 | **Commit de recalage unique** : seuils de clustering (F2), `mem_limit` = pic M1 × 1,5 (D6), seuils ⚖ d'après M3 (F4) → PR → CI → `deploy.sh` | 🤖 + 👤 | PR, `deploy.sh` | F2 · F4 · D6 |
| J7–J10 | **Test de rollback** : redéploiement du sha précédent (aucune migration entre les deux), puis retour au sha de recalage | 👤 | `~/radar-deploy.log` | E5 |
| avant J14 | Reboot réel du VPS : `/health = ok` en ≤ 3 min, sans alerte externe (T-RES-09, M10) | 👤 | `measurements.md` | C2 |
| avant J14 | Restauration complète sur une machine neuve (VPS jetable) : `git clone` + `.env` + restauration + `up -d` (T-RES-11, M7) | 👤 | `backup-restore.md` | C3 · G2 |
| avant J14 | T-SEC-09 rejoué sur le VPS | 👤 | `go-live.md` | D7 |
| J14 | Fin du warm-up de l'émergence ; job analytique sans erreur depuis 24 h | 👤 | `/api/health` | B7 |
| ≥ J14 | Revue complète de VIII §52 (A à H), coût mensuel détaillé (G5) ; décision avec sha, date, durée de pré-prod | 👤 | `go-live.md` | §52 |

À noter : les tendances à 30 jours restent « données insuffisantes » longtemps après le go-live (B6 l'accepte). C'est une raison de plus pour conserver la base à la bascule.

---

## 7. Piste 👤 — échéances

Menée en parallèle des sprints. « Au plus tard » = sinon l'étape citée ne peut pas se clore. Chaque ligne est une issue `qui:moi` dans la milestone indiquée.

| Tâche | Milestone | Au plus tard | Conseillé | Réf. |
|---|---|---|---|---|
| Dépôt public, spec brute, règle sur `main`, outillage `gh` | Pré-S0 | avant S0 | — | IX §57.2 |
| Arbitrages du S0 (PR T0.1, rapport, ADR, plan S1) | S0 | fin S0 | — | IX §57.7 |
| Poste de dev : Docker rootless, retrait du groupe `docker` ; sysctl `net.ipv4.ip_unprivileged_port_start=80` (parade (a)) (#61) | S1 | avant le premier Compose du S1 | dès l'acceptation de l'ADR-0021 | ADR-0021 · E22 |
| Checks CI obligatoires sur `main` | S1 | fin S1 | dès la CI verte | VIII §46.2 |
| Curation du `config/` réel | S2 → S8 | J0 | finie au S8 | IV §16 · V-B §29.7 |
| Choix du fournisseur de VPS, provisioning amd64, durcissement VII §43.1 | S4 | fin S11 | S4–S6, puis M1 indicative dans `radar-load` sur le VPS (aucune donnée réelle, D15) | VII §43.1 · §45.4 |
| ADR-0020 : go-live sans gateway | S6 | fin S6 | — | IX §54.3 |
| Accès provider OpenAI-compatible pour les fixtures | S6 | début S7 | — | E8 |
| Fixtures `enrich_article`, `resolve_event` | S7 | fin S7 | — | VIII §50.4 |
| Fixtures `discover_topics` | S8 | fin S8 | — | VIII §50.4 |
| Nom de domaine | S9 | fin S11 | S6–S9 | D2 |
| Bot Telegram, compte SMTP | S10 | fin S10 | — | VI §33.2 |
| Bucket S3-compatible, clés, `RESTIC_PASSWORD` dans le gestionnaire | S10 | fin S11 | S9–S10 | VII §38 · D9 |
| DNS A/AAAA vers le VPS | S11 | fin S11 | — | D2 |
| `GITHUB_TOKEN` fine-grained, lecture seule | S11 | J0 | — | IV §22 |
| Compte de monitoring externe | S11 | J1 | — | VII §41 |
| VPS jetable pour l'exercice M7 | Pré-prod | avant J14 | — | T-RES-11 |

---

## 8. Projection calendaire

**Hypothèses** : démarrage lundi 28/09/2026 · 3 sessions par semaine · effort × 1,25 (tampon d'interruptions) · 2 semaines de creux fin décembre · pré-prod ≈ 2,5 semaines (14 jours + revue).

| Étape | Optimiste (effort bas) | **Central** | Prudent (effort haut) |
|---|---|---|---|
| Pré-S0 | 01/10/2026 | **02/10/2026** | 04/10/2026 |
| S0 | 16/10/2026 | **20/10/2026** | 24/10/2026 |
| S1 | 02/11/2026 | **11/11/2026** | 19/11/2026 |
| S2 | 19/11/2026 | **03/12/2026** | 16/12/2026 |
| S3 | 28/11/2026 | **14/12/2026** | 13/01/2027 |
| S4 | 13/12/2026 | **15/01/2027** | 03/02/2027 |
| S5 | 02/01/2027 | **22/01/2027** | 11/02/2027 |
| S6 | 10/01/2027 | **01/02/2027** | 23/02/2027 |
| S7 | 22/01/2027 | **14/02/2027** | 10/03/2027 |
| S8 | 03/02/2027 | **01/03/2027** | 27/03/2027 |
| S9 | 14/02/2027 | **14/03/2027** | 11/04/2027 |
| S10 | 23/02/2027 | **26/03/2027** | 25/04/2027 |
| S11 | 13/03/2027 | **15/04/2027** | 19/05/2027 |
| **Décision go-live** | ≈ 30/03/2027 | **≈ 02/05/2027** | ≈ 05/06/2027 |

- Les échéances des milestones GitHub portent le scénario **central**.
- **Recalage obligatoire** à la fin de S1 et de S4 : vitesse réelle (sessions consommées / estimées) appliquée aux sprints restants.
- Seuil d'alerte : un sprint qui dépasse son effort haut de plus de 30 % déclenche une revue du planning (découpage, périmètre, ou report V2 par ADR).

---

## 9. Jalons et gates

| Gate | Fin de | Critères (tous requis) | En cas d'échec |
|---|---|---|---|
| **G0 outillage** | Pré-S0 | Claude Code lit et commente une issue via `gh` · push direct sur `main` refusé | corriger avant tout travail |
| **G1 faisabilité** | S0 | vérifications IX §57.4, **bloquantes** : WAL sur volume nommé · restic statique amd64 · wheels onnxruntime et lingua · APScheduler 3.x sur Python 3.12. **Contournables par ADR** : `paraphrase-multilingual-MiniLM-L12-v2` dans fastembed (384 dim., révision et sha256 notés ; sinon repli ADR-0008) · SQLite ≥ 3.35 avec FTS5 et JSON1 dans l'image (sinon autre image ou wheel) · `BEGIN IMMEDIATE` avec aiosqlite · outils CI | bloquante : arrêt, ADR, replanification · contournable : ADR puis poursuite |
| **G2 socle** | S1 | critères S1 · CI six étapes verte sur `main` · checks obligatoires posés | aucun code métier avant |
| **G3 cœur sans LLM** | S4 | Feed avec Events et hotness, sans LLM · M1 et M2 indicatives dans leurs critères, ou écart expliqué | M2 hors critère → ADR `sqlite-vec` (IX §54.3) |
| **G4 fonctionnel complet** | S10 | T-RES-02 complet vert · produit de bout en bout gateway éteint | — |
| **G5 pré-prod** | S11 | tous les tests automatisés verts · pré-prod démarrée par `deploy.sh` · backup restic opérationnel (D15) | pas de données réelles sans backup |
| **G6 go-live** | Pré-prod | VIII §52 A à H cochés avec preuve · ≥ 14 jours · nightly verte depuis ≥ 7 jours (A1) | mesure hors critère → correction ou ADR ajustant la cible |

---

## 10. Mesures M1–M10

Cibles et méthodes : VII §45.3–§45.4. Indicatives en développement (VIII §50.7), **de référence** en pré-prod sur le VPS cible. Consignation : `docs/measurements.md`.

| Mesure | Objet | Indicative | Référence | Effet |
|---|---|---|---|---|
| M1 | RAM au repos et en pic | S4 (local, ou VPS si provisionné) | J1–J3 · synthétique | taille du VPS, `mem_limit` (D6) |
| M2 | Cosine brute-force par article | S4 | J1–J3 · profil cible | valide « pas de vector DB » |
| M3 | Taille du `-wal` | — | J3–J7 · charge réelle | seuils ⚖ (F4) |
| M4 | Plus longue transaction du worker | — | J3–J7 · charge réelle | découpage en lots |
| M5 | Durée du job analytique | S8 | J1–J3 · profil cible | valide le calcul horaire |
| M6 | Gateway LLM | — | sans objet au go-live (C9) ; à faire au branchement | F3 |
| M7 | Backup / restauration machine neuve | — | avant J14 | RTO, portabilité (G2) |
| M8 | Images et disque | — | J1–J3 | budget disque |
| M9 | Latence API | — | J1–J3 synthétique · J3–J7 réel | index |
| M10 | Reboot réel | — | avant J14 | démarrage |

---

## 11. Suivi dans GitHub

| Objet | Usage |
|---|---|
| **Milestones** | `Pré-S0`, `S0` … `S11`, `Pré-prod` ; échéance = scénario central (§8) |
| **Issues 🤖** | créées **à la validation** du plan `sprint-NN.md`, une par tâche, dans la milestone du sprint |
| **Issues 👤** | créées dès l'initialisation pour toute la piste §7 et les arrêts de sprint |
| **Labels** | `qui:claude` · `qui:moi` · `type:tâche` · `type:infra` · `type:bug` · `type:dette` · `type:adr` · `type:spec` · `gate` · `bloquant` |
| **Project « Radar »** | champs : Status · Effort (sessions) ; milestone et labels affichés. Vues : *Sprint courant* (tableau par Status, filtre milestone) · *Mes tâches* (filtre `label:qui:moi`) · *Tout* (table) · *Roadmap* (par milestone) |
| **Clôture d'un sprint** | milestone à 100 % (issues 👤 comprises) · bilan dans `sprint-NN.md` : sessions consommées, identifiants couverts, écarts, dette → recalage §8 |

**Règle anti-doublon** : le statut d'une tâche ne vit **que** dans le Project. Ce fichier ne porte pas de cases à cocher d'avancement ; il change quand le **plan** change.

---

## Annexe A — Lancement de Claude Code pour le S0

À coller en première instruction, à la racine du dépôt (le `CLAUDE.md` n'existe pas encore) :

```text
Tu démarres le Sprint 0 du projet AI Tech Radar.
Lis docs/spec/SPEC.md (spec brute), en priorité IX §53–§57 et VIII §46–§52, puis docs/planning.md
(sections 0, 1, 2 et la fiche S0).
Le Sprint 0 suit IX §57 : documents uniquement, le diff ne touche que docs/, SPEC.md et CLAUDE.md.
Les écarts E1–E10 de docs/planning.md §2 sont à consigner dans sprint-00-cadrage.md, pas à trancher.
Travaille issue par issue (gh issue list --milestone S0), une branche et une PR par issue.
Commence par T0.1a (découpage mécanique, aucun changement de contenu), puis T0.1b dans une PR
dédiée. Arrête-toi après l'ouverture de chaque PR et attends ma validation.
Tu ne fusionnes jamais une PR, tu ne passes jamais un ADR en Accepté et tu ne démarres pas le Sprint 1.
```

---

## Annexe B — Initialisation (Pré-S0)

1. Créer le dépôt **public** `ai-tech-radar` sur GitHub.
2. Premier commit, directement sur `main` (avant la règle de protection) : `docs/spec/SPEC.md` (spec brute V0.4) et `docs/planning.md`.
3. Installer `gh` et Claude Code ; `gh auth login` puis `gh auth refresh -s project`.
4. Lancer `REPO=<owner>/ai-tech-radar ./init-github.sh`, **hors dépôt** (jamais commité) : ruleset `main-protegee`, labels, 14 milestones, Project « Radar », ≈ 56 issues (Pré-S0, S0, arrêts de sprint, piste 👤, pré-prod). Relançable sans doublon.
5. Dans l'interface du Project : options du champ Status et les quatre vues (§11).
6. Traiter les deux issues de Pré-S0 (G0), puis lancer Claude Code avec le prompt de l'annexe A.
