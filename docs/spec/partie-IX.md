# Partie IX — Gouvernance & démarrage

> **Partie IX — Gouvernance & démarrage.** Version durcie issue de la revue §53–§57, 2026-09-22.
> Remplace la Partie IX de SPEC.md V0.3. Prend les Parties I, II, III, IV, V-A, V-B, VI, VII et VIII durcies comme acquis.

**Nature de cette partie : une consolidation.** Elle rassemble les décisions verrouillées accumulées au fil du durcissement, la liste des ADR, l'arbre de documentation, le runbook et la mission de cadrage. Elle réconcilie ce que les Parties I à VIII ont fléché vers elle ; seul ce qui manquait pour rendre la gouvernance et le démarrage exécutables est durci à neuf.

**Déjà tranché ailleurs, non repris ici** :
- séquence de déploiement et verrou CI (VII §36.9, VIII §49.5) ;
- contrat de restauration (VII §38.5) ;
- check-list de mise en production et preuves (VIII §52, consignées dans `docs/go-live.md`) ;
- pré-production (VIII §47.4) ;
- mesures M1–M10 (VII §45.4) ;
- table des conditions et alertes `system` (VII §39.5–§39.6) ;
- contenu du Sprint 1 à 11 (VIII §47.2). **Le §57 est la description canonique du Sprint 0** ; VIII §47.2 y renvoie.

---

## Décisions tranchées dans cette revue (Partie IX)

Les points marqués **(tranché par défaut)** n'avaient pas de réponse dans la revue : ils sont tranchés pour rendre la partie implémentable, à confirmer à la relecture.

1. **§53 est la source unique des décisions verrouillées.** Aucune autre partie, ni `SPEC.md`, ni `CLAUDE.md` n'en recopie la liste : ils y renvoient.
2. **Trois niveaux de décision** : *verrouillée* (§53, changement sur preuve + ADR) · *structurante* (ADR, sans exigence de preuve) · *ordinaire* (mise à jour de la spec, VIII §51.3).
3. **Changer une décision verrouillée** exige, dans la même PR : une **preuve** au sens du §53.1, un **ADR qui remplace** le précédent, et la mise à jour de `docs/spec/`. « Une alternative plus *enterprise* » n'est jamais une preuve.
4. **Seul le propriétaire du projet accepte un ADR.** Claude Code rédige un ADR en statut `Proposé` et **s'arrête**. Il ne change jamais une décision verrouillée, ne tranche jamais un conflit entre parties de la spec, et ne démarre jamais un sprint non validé.
5. **Liste §53 regroupée par familles et dédoublonnée** (21 entrées `DV-nn`). Ajouts par rapport à la liste accumulée : **cœur déterministe + couche AI asynchrone**, **FTS5**, **React · TypeScript · Vite**. Caddy seul point d'entrée est rattaché à l'entrée « exposition et cloisonnement ».
6. **Embeddings : le moteur est verrouillé, pas le modèle.** fastembed (onnxruntime), CPU, multilingue, ≤ 384 dimensions. Le modèle précis (cible `paraphrase-multilingual-MiniLM-L12-v2`) et son éventuel repli relèvent de l'ADR-0008, produit au Sprint 0.
7. **« Gateway LLM externe » reformulé** : accès LLM uniquement par une API OpenAI-compatible, derrière un gateway hors de l'app, sans SDK de provider, et **optionnel**.
8. **ADR produits à trois moments** : 19 ADR au Sprint 0 · l'ADR du gateway retenu au **Sprint 6** (et non au Sprint 0) · des ADR **conditionnels**, sur déclencheur listé.
9. **Format ADR fixé** : `docs/adr/NNNN-slug.md`, statut `Proposé` · `Accepté` · `Rejeté` · `Remplacé par NNNN`, champ **Preuve** obligatoire quand l'ADR remplace une décision verrouillée. Un ADR accepté n'est jamais réécrit.
10. **La spec vit dans `docs/spec/`**, un fichier par partie : `partie-I.md` … `partie-IV.md`, `partie-V-A.md`, `partie-V-B.md`, `partie-VI.md` … `partie-IX.md`. **`SPEC.md` devient l'index** : sommaire, règles de lecture, lien vers §53, **sans copie** de la liste (précise VIII décision 22).
11. **Report des impacts = première tâche du Sprint 0**, dans une PR dédiée relue avant toute autre tâche. Une fois reportées, les sections « Impacts à répercuter » et les marqueurs « (proposé) » / « à confirmer » disparaissent de `docs/spec/`.
12. **Les points « (proposé) » et « à confirmer » des Parties I à VIII sont réputés validés**, les parties ayant été validées. **(tranché par défaut)**
13. **`CLAUDE.md` à la racine** : règles permanentes de Claude Code, courtes, qui renvoient à la spec sans la recopier.
14. **Dossier `docs/sprints/`** : rapport de cadrage (`sprint-00-cadrage.md`) puis un fichier par sprint (`sprint-NN.md`) — plan validé avant implémentation, bilan à la fin.
15. **Documentation créée au fil des sprints, finalisée au Sprint 11** (tableau §55.4). Le runbook et `testing.md` existent dès le Sprint 1.
16. **Frontières documentaires** : le runbook est le point d'entrée unique « que faire quand… » ; il résume et renvoie, il ne duplique pas. Les procédures de développement et de CI vivent dans `testing.md`, le protocole de charge dans `measurements.md`.
17. **Contrat commun des commandes `app.cli`** : codes de sortie, sortie sur stdout, logs sur stderr, mode d'exécution (`exec` ou `run --rm --no-deps`).
18. **Rollback à travers une migration** : `deploy.sh` **détecte** qu'une migration serait à défaire et **refuse** ; le runbook décrit les deux chemins, *downgrade* si la migration est réversible, *restauration* du snapshot du déploiement sinon.
19. **`backup-now` affiche le `snapshot_id`** et `deploy.sh` le journalise.
20. **Verrou d'exclusion** entre backup et test de restauration planifiés et manuels (impact VII).
21. **Nouvelle commande `app.cli vacuum`**, qui refuse de s'exécuter si le heartbeat du worker est frais.
22. **Toute modification du `.env` s'applique par `docker compose up -d <service>`**, jamais par `restart`, qui ne relit pas l'environnement.
23. **Le runbook contient la table « répondre à une alerte »**, une ligne par condition du VII §39.5 et par alerte du monitoring externe.
24. **Sprint 0 = documents seulement.** Critère vérifiable : son diff ne touche que `docs/`, `SPEC.md` et `CLAUDE.md`.
25. **Vérifications de dépendances complétées** : WAL sur volume nommé, `BEGIN IMMEDIATE` avec SQLAlchemy async + aiosqlite, révision et empreinte du modèle d'embeddings épinglées, architecture du VPS cible.
26. **`/data` n'est jamais un bind mount**, en développement comme en production, quel que soit l'OS de développement : toujours un volume nommé.
27. **Architecture du VPS cible** : donnée d'entrée du Sprint 0 ; `amd64` par défaut, vérifications rejouées avant le Sprint 11 si le choix final est `arm64`. **(tranché par défaut)**
28. **Enchaînement** : le Sprint 1 démarre sur validation explicite (PR du Sprint 0 fusionnées, ADR acceptés, plan du Sprint 1 validé). La même règle vaut pour chaque sprint suivant.

---

## Réconciliations

| Source du conflit | Avant | Tranché |
|---|---|---|
| V0.3 §53 | 7 technos, liste à plat | 21 entrées `DV-nn` par familles, liste des interdits par anticipation (§53.2–§53.3) |
| V0.3 §53 | « embeddings locaux/légers » + modèle cible à part | moteur verrouillé, modèle en ADR-0008 (décision 6) |
| V0.3 §53 | « external LLM gateway » | API OpenAI-compatible, gateway hors app, optionnel (décision 7) |
| V0.3 §54 | un ADR par décision verrouillée « et chaque choix structurant » | registre à trois moments (§54.3) ; regroupement par décision réversible indépendamment |
| Brief de revue | ADR du gateway au Sprint 0 | au Sprint 6, avec M6 (VIII §47.2 Sprint 6) |
| V0.3 §55 | 8 documents | arbre complet (§55.1) : `docs/spec/`, `docs/sprints/`, index d'ADR, `trends.md`, `measurements.md`, `testing.md`, `go-live.md` |
| VIII décision 22 | `SPEC.md` = sommaire, **décisions verrouillées**, renvois | `SPEC.md` = sommaire, règles de lecture, **lien** vers §53 (décision 1) |
| VIII §47.2 Sprint 11 | documentation d'exploitation livrée au Sprint 11 | créée au fil des sprints, **finalisée** au Sprint 11 (§55.4) |
| VII §38.5 | « le détail pas à pas va au runbook (`docs/backup-restore.md`) » | runbook = résumé et contrôles ; `backup-restore.md` = pas à pas (§55.5) |
| V0.3 §56 · VII §43.4 | `docker compose restart` ; « redémarrage du worker » après rotation | `docker compose up -d <service>` dès que `.env` change (décision 22) |
| V0.3 §56 · VII §36.9 · VIII §49.5 | rollback = redéployer le tag précédent | valable **sans** migration entre les deux sha ; sinon détection et procédure §56.6-P2 |
| VIII (impacts vers §56) | charge `radar-load`, `record-llm-fixtures`, échec d'audit au runbook | dans `measurements.md` et `testing.md` (décision 16) |
| V0.3 §57 | 11 étapes, dont « lire `SPEC.md` » et « vérifier la faisabilité SQLite WAL » | Sprint 0 canonique (§57) : lecture de `SPEC.md` et `docs/spec/`, WAL réintégré aux vérifications |
| V0.3 §57 | Sprint 1 = FastAPI · SQLite · Docker · logging · `/health` · tests | Sprint 1 tel que VIII §47.2 (Caddy, supervision du worker, CI six étapes compris) |
| SPEC.md V0.3 | « Décisions prises dans cette V0.3 (à valider) » | supprimé de l'index : décision 5 remplacée (VI), les autres absorbées par les parties durcies |

---


## 53. Décisions verrouillées

### 53.1 Règle

**Trois niveaux de décision.**

| Niveau | Où | Changer exige |
|---|---|---|
| **Verrouillée** | liste §53.2 | une **preuve** + un ADR qui remplace le précédent + la mise à jour de `docs/spec/`, dans la même PR |
| **Structurante** | choix d'architecture, de dépendance ou de processus qui engage plusieurs parties | un ADR + la mise à jour de `docs/spec/` |
| **Ordinaire** | tout le reste de la spec | la mise à jour de `docs/spec/` (VIII §51.3) |

**Est une preuve**, et seulement :
- une **mesure** consignée dans `docs/measurements.md` (identifiant M-nn ou mesure ad hoc datée, avec VPS et profil) qui sort du critère ;
- un **test** reproductible qui met en évidence une limite ou un défaut ;
- un **incident** réel, daté, décrit (fiabilité, sécurité, perte de données) ;
- une **vulnérabilité** sans correctif sur la version verrouillée ;
- un **besoin fonctionnel** nouveau, validé par le propriétaire du projet.

**N'est pas une preuve** : une alternative plus « enterprise », plus populaire ou plus récente ; une anticipation de charge non mesurée ; une préférence d'implémenteur.

**Qui décide.** Le propriétaire du projet accepte ou rejette un ADR. Claude Code :
- rédige l'ADR en statut `Proposé`, avec la preuve, puis **s'arrête** et le soumet ;
- n'implémente rien qui dépende de l'ADR avant son acceptation ;
- signale, sans trancher, tout conflit entre parties de la spec (VIII §51.3).

### 53.2 Liste

Une ligne par décision, son origine et son ADR (§54.3).

**A. Données**

| ID | Décision | Origine | ADR |
|---|---|---|---|
| DV-01 | **SQLite** (WAL, ≥ 3.35, FTS5, JSON1) est l'unique base de données V1, fichier sur volume local | II · III §10 | 0001 |
| DV-02 | **File de jobs AI en base** (`AIJob`, claim atomique) ; aucun broker de messages | V-A §23 | 0001 |
| DV-03 | **Recherche plein texte = FTS5** ; aucun moteur de recherche externe | II décision 10 | 0002 |
| DV-04 | **Similarité = cosine brute-force numpy** sur une fenêtre en mémoire du worker, vecteurs en BLOB | III §12.4 | 0002 |

**B. Architecture et processus**

| ID | Décision | Origine | ADR |
|---|---|---|---|
| DV-05 | **Deux couches** : un cœur déterministe complet de bout en bout, sans LLM ; une couche d'enrichissement AI asynchrone. Aucun appel LLM dans le pipeline d'ingestion | I · II §6 | 0003 |
| DV-06 | **Deux processus `app` et `worker`, sans IPC** : le schéma SQLite est le contrat ; un seul écrivain par table et par clé `SystemState` (exceptions documentées V-A décision 19) ; l'app dépose des jobs, ne les exécute jamais | II §8.2–§8.3 | 0004 |
| DV-07 | **FastAPI, un seul processus uvicorn** | VII §35 | 0005 |
| DV-08 | **APScheduler 3.x** (`AsyncIOScheduler`) dans le worker ; la 4.x est exclue tant qu'elle n'est pas stable | VII §35 | 0006 |

**C. Intelligence**

| ID | Décision | Origine | ADR |
|---|---|---|---|
| DV-09 | **Accès LLM uniquement par une API OpenAI-compatible**, derrière un gateway hors de l'app ; aucun SDK de provider dans le code ; **LLM optionnel** : le produit est complet à 0 € sans lui | II · V-A §25 · VIII décision 21 | 0007 |
| DV-10 | **Embeddings locaux sur CPU** : fastembed (onnxruntime), sans PyTorch ; modèle multilingue ≤ 384 dimensions, intégré à l'image au build. Le modèle précis n'est pas verrouillé | III §12.1 · VII décision 9 | 0008 |

**D. Infrastructure et exposition**

| ID | Décision | Origine | ADR |
|---|---|---|---|
| DV-11 | **Docker Compose sur un VPS unique** : trois services permanents `caddy` · `app` · `worker`, `migrate` one-shot, `gateway` en profil optionnel ; une image backend et une image Caddy taggées par sha | VII §36.1–§36.2 | 0009 |
| DV-12 | **Exposition et cloisonnement** : Caddy seul point d'entrée et seul service qui publie des ports ; segmentation réseau (`app` sans sortie Internet, `worker` sans accès à `app`, `migrate` sans réseau) ; conteneurs non-root, `cap_drop: ALL`, racine en lecture seule ; garde anti-SSRF dans le `HttpClient` | VII §36.2, §36.5, §43 | 0010 |
| DV-13 | **Auth = `basic_auth` Caddy** (bcrypt) sur tout sauf `/health`, plus anti-CSRF dans l'app ; `DASHBOARD_TOKEN` retiré | VI §32 · VII §37 | 0011 |
| DV-14 | **Sémantique de `/health`** : public `{status}` = `ok` · `degraded` · `down` (200 / 200 / 503) ; `down` = base inaccessible ou heartbeat périmé ; détail authentifié sur `/api/health` | VI décision 14 · VII §40 | 0012 |
| DV-15 | **Frontend React · TypeScript · Vite**, servi en statique par Caddy ; CSP `default-src 'self'`, aucun script ni style en ligne | VII §35, §37.3 | 0013 |

**E. Exploitation**

| ID | Décision | Origine | ADR |
|---|---|---|---|
| DV-16 | **Pas de Prometheus en V1** : métriques calculées par le worker (`ops.tick`), écrites dans `SystemState`, exposées par `/api/health`, le dashboard et les logs | VII décision 17 | 0014 |
| DV-17 | **Backup exécuté par le worker** : `VACUUM INTO`, contrôle d'intégrité, envoi par **restic** (chiffré, 7/4/3, hors VPS) ; test de restauration mensuel automatisé | VII §38 | 0015 |

**F. Livraison et gouvernance**

| ID | Décision | Origine | ADR |
|---|---|---|---|
| DV-18 | **Horloge injectable** : une `Clock` unique ; aucun instant lu en SQL ni par `datetime.now()` / `time.time()` dans le code métier | VIII décision 7 | 0016 |
| DV-19 | **Déploiement V1 manuel, verrouillé par la CI** : `scripts/deploy.sh` refuse un sha dont la CI (e2e compris) n'est pas verte ; aucun contournement | VIII §49.5 | 0017 |
| DV-20 | **Critère de test bloquant = traçabilité du catalogue** ; la couverture est mesurée, jamais bloquante | VIII décisions 9–10 | 0018 |
| DV-21 | **La spec vit dans le dépôt** sous `docs/spec/`, `SPEC.md` en index ; les identifiants de test sont extraits de `docs/spec/partie-VIII.md` | VIII décision 22 · §55.2 | 0019 |

### 53.3 Interdits par anticipation

Corollaire de DV-01 à DV-04, DV-11 et DV-16 : **aucune** des briques suivantes n'est ajoutée en V1 sans preuve au sens du §53.1 :

```
PostgreSQL · Redis · Kafka (ou tout broker) · Kubernetes · vector DB (dont sqlite-vec)
Elasticsearch (ou tout moteur de recherche) · Prometheus / Grafana · service Docker permanent supplémentaire
```

---

## 54. ADR

### 54.1 Rôle

Le §53 dit **quoi** ; l'ADR dit **pourquoi**, contre quoi, et à quel prix. Un ADR ne redéfinit jamais le contrat : la décision normative vit dans `docs/spec/`, l'ADR la justifie et y renvoie. Pas de doublon : le §53 cite le numéro d'ADR, l'ADR cite l'identifiant `DV-nn` et les paragraphes de la spec.

### 54.2 Format

**Fichiers**
- `docs/adr/NNNN-slug.md` : numéro sur 4 chiffres, séquentiel, jamais réutilisé ; slug en kebab-case.
- `docs/adr/_template.md` : gabarit.
- `docs/adr/README.md` : index (numéro, titre, statut, date, `DV-nn` couverts, remplace / remplacé par).

**Sections d'un ADR**

| Section | Contenu |
|---|---|
| Statut | `Proposé` · `Accepté` · `Rejeté` · `Remplacé par NNNN` |
| Date | date du dernier changement de statut |
| Décision(s) couverte(s) | identifiants `DV-nn` et paragraphes de la spec |
| Contexte | le problème, les contraintes (Partie I : low-cost, mono-utilisateur, provider-independent, portable) |
| Décision | la décision, en une à trois phrases |
| Alternatives écartées | chacune avec la raison du rejet |
| Conséquences | ce qu'on gagne, ce qu'on accepte de perdre, ce qui deviendrait une preuve de réexamen |
| Preuve | **obligatoire** si l'ADR remplace une décision verrouillée : lien vers la mesure, le test, l'incident ou la vulnérabilité |
| Remplace | numéro de l'ADR remplacé, le cas échéant |

**Règles**
- Cible : une page. Un ADR couvre une décision **réversible indépendamment** ; deux décisions qui ne peuvent changer que l'une avec l'autre partagent un ADR.
- Un ADR `Accepté` n'est jamais réécrit : seules la ligne de statut et la mention « Remplacé par » changent. Revenir sur une décision = un nouvel ADR.
- Un ADR `Rejeté` est conservé : il évite de reproposer la même chose sans élément nouveau.

### 54.3 Registre

**Produits au Sprint 0** (statut `Proposé`, puis `Accepté` par le propriétaire du projet)

| ADR | Titre | Couvre |
|---|---|---|
| 0001 | SQLite comme base unique et file de jobs en base | DV-01, DV-02 |
| 0002 | Recherche et similarité dans le processus : FTS5, cosine numpy | DV-03, DV-04 |
| 0003 | Cœur déterministe et couche AI asynchrone | DV-05 |
| 0004 | Deux processus sans IPC, écrivain unique par table | DV-06 |
| 0005 | FastAPI, un seul processus uvicorn | DV-07 |
| 0006 | APScheduler 3.x | DV-08 |
| 0007 | Accès LLM par API OpenAI-compatible, gateway hors app, LLM optionnel | DV-09 |
| 0008 | Moteur et modèle d'embeddings (modèle retenu, repli éventuel, révision épinglée) | DV-10 |
| 0009 | Topologie Docker Compose sur VPS unique | DV-11 |
| 0010 | Exposition et cloisonnement : Caddy, segmentation réseau, conteneurs durcis, anti-SSRF | DV-12 |
| 0011 | Authentification du dashboard | DV-13 |
| 0012 | Sémantique de `/health` | DV-14 |
| 0013 | Frontend React · TypeScript · Vite et CSP stricte | DV-15 |
| 0014 | Pas de Prometheus en V1 | DV-16 |
| 0015 | Backup restic exécuté par le worker, test de restauration automatisé | DV-17 |
| 0016 | Horloge injectable, temps jamais lu en SQL | DV-18 |
| 0017 | Déploiement manuel verrouillé par la CI | DV-19 |
| 0018 | Traçabilité du catalogue, pas de seuil de couverture | DV-20 |
| 0019 | Spec dans le dépôt, `SPEC.md` en index | DV-21 |

**Produit au sprint concerné**

| ADR | Titre | Sprint | Appui |
|---|---|---|---|
| 0020 | Gateway LLM retenu | 6 | `docs/llm-gateway.md`, première mesure M6 |

Si aucun gateway n'est retenu à ce stade, l'ADR 0020 le consigne (produit sans LLM, VIII décision 21).

**Conditionnels** — rédigés au prochain numéro libre, seulement si le déclencheur survient :

| Déclencheur | Objet de l'ADR | Référence |
|---|---|---|
| Une bibliothèque frontend exige des styles injectés | élargissement de `style-src` | VII §37.3 · VIII §46.2 |
| M6 montre `GET /models` absent ou peu fiable | `LLMClient.health()` adapté | VII §45.4 M6 |
| Une mesure M1–M10 hors critère est acceptée | ajustement de la cible | VII §45.4 · VIII §52 |
| Nouveau modèle d'embeddings après la mise en production | changement de modèle (ré-embedding sur titre + résumé) | III §12.5 |
| APScheduler 4.x stable, ou 3.x sans correctif de sécurité | migration de scheduler (remplace 0006) | DV-08 |
| M2 hors critère | `sqlite-vec` ou autre index vectoriel (remplace 0002) | DV-04 · §53.3 |
| Toute preuve contre une décision `DV-nn` | ADR qui remplace l'ADR de la décision | §53.1 |
| Écart structurant découvert en cours de sprint | décision structurante | VIII §51.3 |
| Nouvelle exception à la règle d'un seul écrivain | exception documentée | DV-06 |

---

## 55. Documentation

### 55.1 Arbre

```
ai-tech-radar/
├── SPEC.md                    # index de la spec (§55.2)
├── CLAUDE.md                  # règles permanentes de Claude Code (§55.3)
├── README.md                  # présentation, démarrage local en une commande
└── docs/
    ├── spec/
    │   ├── partie-I.md   · partie-II.md  · partie-III.md · partie-IV.md
    │   ├── partie-V-A.md · partie-V-B.md
    │   └── partie-VI.md  · partie-VII.md · partie-VIII.md · partie-IX.md
    ├── adr/
    │   ├── README.md          # index
    │   ├── _template.md
    │   └── NNNN-slug.md
    ├── sprints/
    │   ├── sprint-00-cadrage.md
    │   └── sprint-NN.md       # plan (validé avant implémentation) + bilan
    ├── architecture.md · database.md · collectors.md · llm-gateway.md · trends.md
    ├── deployment.md · monitoring.md · backup-restore.md · measurements.md
    └── runbook.md · testing.md · go-live.md
```

Cet arbre remplace le bloc `docs/` de VIII §46.1.

### 55.2 `SPEC.md` et `docs/spec/`

**`SPEC.md` (index)** contient, et seulement :
1. l'objet du produit en deux lignes et la version de la spec ;
2. le sommaire, avec un lien par partie vers `docs/spec/` et les paragraphes de chacune ;
3. les **règles de lecture** :
   - la spec est le contrat de développement ; le code s'y conforme ;
   - aucune partie ne l'emporte sur une autre : un conflit est **signalé**, jamais tranché par l'implémenteur (VIII §51.3) ;
   - les décisions verrouillées et leur règle de changement sont au §53 ;
4. un lien vers le §53 et vers `docs/adr/README.md`.

La liste des décisions verrouillées n'y est **pas** recopiée (décision 1).

**`docs/spec/partie-*.md`**
- Chaque fichier garde son bloc « Décisions tranchées », ses sections, ses « Points d'interprétation » et son « Reporté en V2 ».
- Les sections « **Impacts à répercuter** » **n'existent plus** une fois reportées dans les parties cibles ; l'historique Git les conserve.
- Les marqueurs « (proposé) », « (tranché par défaut) » et « à confirmer » sont retirés une fois validés.
- L'en-tête « Remplace la Partie X de SPEC.md V0.3 » est remplacé par la date de dernière révision.
- Modifier la spec = une PR qui touche `docs/spec/`, avec un ADR selon le niveau de la décision (§53.1).

### 55.3 `CLAUDE.md`

Règles permanentes, lues par Claude Code à chaque session. **Court** (cible < 150 lignes) ; renvoie à la spec, n'en recopie aucun contenu normatif.

Contenu :
- **Lecture** : `SPEC.md`, puis la ou les parties du sprint en cours et le fichier `docs/sprints/sprint-NN.md`.
- **Interdits** : modifier une décision verrouillée (§53) ; passer un ADR en `Accepté` ; trancher un conflit de spec ; démarrer un sprint dont le plan n'est pas validé ; implémenter un sprint suivant ; appeler un vrai provider dans un test ; ajouter une brique du §53.3.
- **Arrêts obligatoires** : fin de chaque sprint (bilan dans `sprint-NN.md`) ; ADR proposé ; conflit ou trou dans la spec.
- **Définition de terminé** : renvoi à VIII §51.
- **Commandes usuelles** de développement : lint, tests, lancement du Compose local, e2e.

### 55.4 Documents, contenu et moment de création

| Document | Contenu | Créé au sprint | Mis à jour |
|---|---|---|---|
| `architecture.md` | vue d'ensemble, processus et propriété des tables, arborescence, stratégie de configuration, Compose (proposé au Sprint 0, réel ensuite) | 0 | à chaque changement d'architecture |
| `database.md` | modèle SQL cible, conventions, PRAGMA, migrations, rétention en résumé | 0 | à chaque migration |
| `sprints/` | rapport de cadrage, plans et bilans | 0 | chaque sprint |
| `adr/` | ADR 0001–0019 | 0 | sur décision |
| `runbook.md` | §56 | 1 (`validate-config`, `health`, commandes de base) | à chaque commande CLI ou procédure (VIII §51.1-9) |
| `testing.md` | niveaux, doubles, blocage réseau, horloge, marqueurs `spec`, e2e en local, traitement d'un échec d'audit, `record-llm-fixtures` | 1 | à chaque double ou règle de test |
| `deployment.md` | développement (Compose local, `https://localhost`) ; production : installation initiale de l'hôte, choix de déploiement (fournisseur, architecture, dépôt restic, monitoring externe, gateway) | 1 (dev) · 11 (prod) | — |
| `collectors.md` | types, configuration, ajout d'une source ou d'un collector (Partie I §2.4) | 2 | à chaque type |
| `measurements.md` | format, protocole de charge dans le projet `radar-load`, résultats M1–M10, calibration | 4 | à chaque mesure |
| `llm-gateway.md` | choix, installation, configuration, providers, fallback, quota, modes de panne, RAM/CPU | 6 | sur changement de gateway |
| `trends.md` | formules lisibles, cold start, discontinuités assumées (V-B §29.7) | 8 | — |
| `monitoring.md` | table des conditions, seuils, qui alerte sur quoi, service externe | 11 | — |
| `backup-restore.md` | mécanisme, restauration pas à pas, exercice sur machine neuve, migration de VPS | 11 | après toute évolution majeure du schéma |
| `go-live.md` | check-list VIII §52 et ses preuves | 11 | jusqu'à la décision |

Tous sont **finalisés** au Sprint 11 (critère VIII §52 H1).

### 55.5 Frontières

| Question | Document |
|---|---|
| Que faire quand… (opération, incident, alerte) | `runbook.md` — toujours le point d'entrée |
| Comment installer l'hôte la première fois | `deployment.md` |
| Restaurer pas à pas, exercice complet, changer de VPS | `backup-restore.md` (le runbook résume et renvoie) |
| Que signifie une condition, quel seuil | `monitoring.md` (le runbook dit quoi faire) |
| Est-on prêt pour la production | `go-live.md` (joué une fois, jamais une procédure récurrente) |
| Lancer les tests, gérer une exception d'audit, enregistrer des fixtures LLM | `testing.md` |
| Jouer une mesure ou un test de charge | `measurements.md` |

**Règle** : une procédure n'est décrite en détail qu'à un seul endroit. Les autres documents y renvoient.

---

## 56. Runbook

### 56.1 Rôle et périmètre

`docs/runbook.md` couvre **tout ce qui s'exécute sur le VPS ou agit sur l'instance** : commandes, opérations récurrentes, incidents, réponse aux alertes. Chaque procédure donne : **quand** · **prérequis** · **étapes** · **vérification** · **retour arrière**.

Hors périmètre, par renvoi : installation initiale (`deployment.md`) · mise en production (`go-live.md`) · développement et CI (`testing.md`) · charge et mesures (`measurements.md`).

### 56.2 Conventions

- Commandes exécutées sur le VPS, depuis le clone du dépôt, par l'utilisateur de déploiement. Projet Compose `radar` ; le projet `radar-load` n'est jamais touché par une procédure du runbook.
- **Conteneur en marche** → `docker compose exec <service> …`.
- **Conteneur arrêté ou en boucle d'erreur** → `docker compose run --rm --no-deps <service> …`.
- **Modification du `.env`** → `docker compose up -d <service>`, qui recrée le conteneur. `docker compose restart` ne relit pas l'environnement : il ne sert qu'à relancer un service sans changement de configuration.
- **Jamais** : `ports:` ajouté à un service, même temporairement (VII §43.1) ; `docker system prune --volumes` ou `docker volume prune` (VII §44.2) ; modification de fichiers suivis par Git sur le VPS (`deploy.sh` exige un arbre propre).
- Toute opération longue (plus de 10 minutes d'indisponibilité possible) commence par la mise en pause de la sonde externe (P6) et finit par sa reprise.

### 56.3 Contrat commun des commandes `app.cli`

- **Codes de sortie** : `0` succès · `1` échec de l'opération · `2` usage ou configuration invalide.
- **Sorties** : résultat lisible sur **stdout** ; logs structurés sur **stderr**. Aucun fichier écrit hors de `/data` et `/tmp` (racine en lecture seule).
- **Prérequis** : les vérifications de démarrage (III §10.1, révision à `head`) s'appliquent, sauf pour `validate-config`, qui ne lit pas la base.
- **Secrets** : jamais affichés ; le nettoyage par valeur (VII §42.4) s'applique aux sorties.

### 56.4 Inventaire des commandes

| Commande | Exécution | Écrit en base | Worker en marche | Usage |
|---|---|---|---|---|
| `python -m app.cli validate-config` | `run --rm --no-deps worker` | non | indifférent | vérifier `config/` avant un déploiement ou quand le worker refuse de démarrer ; `2` si invalide, avec fichier, clé et champ |
| `python -m app.cli health` | `exec app` ou `exec worker` | non | indifférent | détail de santé en SSH : composants, conditions actives, révision, WAL, `journal_size_limit` |
| `python -m app.cli backup-now` | `exec worker` | `SystemState` (backup) | oui | backup immédiat ; affiche le `snapshot_id` ; `1` en échec ; soumis au verrou (§56.4.1) |
| `python -m app.cli restore-test` | `exec worker` | `SystemState` (`last_restore_test`) | oui | test de restauration immédiat ; soumis au verrou |
| `python -m app.cli send-test-alert --channel <email\|telegram>` | `exec worker` | non (hors `AlertLog`) | oui | vérifier un canal après configuration ou rotation |
| `python -m app.cli cluster-calibrate` | `exec worker` | non | oui | histogrammes, échantillons, fréquences d'entités sur stdout ; résultats reportés dans `measurements.md` |
| `python -m app.cli recount-events` | `exec worker` | `Event` (compteurs) | oui, sûr | contrôle l'invariant de compteurs, corrige et journalise les écarts ; une transaction courte par Event |
| `python -m app.cli vacuum` *(nouveau)* | `run --rm --no-deps worker` | toute la base | **non, refusé** | `VACUUM` manuel (P8) |
| `caddy hash-password` | `run --rm caddy` | — | — | hash bcrypt du mot de passe du dashboard (P4) |
| `alembic current` · `alembic downgrade <rev>` | `run --rm migrate` | schéma | non pour `downgrade` | révision appliquée ; downgrade du rollback (P2) |
| `scripts/deploy.sh [<sha>]` | hôte | — | — | déploiement (P1) |
| `scripts/restore.sh <snapshot>` | hôte | tout | arrêté par le script | restauration (P3) |

#### 56.4.1 Verrou de backup

`backup-now`, `restore-test` et les jobs planifiés `backup` et `restore_test` prennent un **verrou exclusif** (`/data/backup/.lock`). Une commande qui trouve le verrou pris s'arrête avec le code `1` et un message explicite. Un job planifié qui le trouve pris s'abstient et le journalise, sans ouvrir de condition `backup_failed`.

#### 56.4.2 `vacuum`

- Refuse de s'exécuter si le heartbeat du worker a moins de `ops.heartbeat_stale_after` (120 s).
- Refuse si l'espace libre de `/data` est inférieur à **deux fois** la taille de la base.
- Place les fichiers temporaires de SQLite sur `/data` (jamais dans `/tmp`, qui est un tmpfs en mémoire).
- Affiche la taille avant et après ; journalise la durée.

### 56.5 Commandes de base

| Besoin | Commande |
|---|---|
| État des services | `docker compose ps` |
| Logs | `docker compose logs -f --since 1h <service>` |
| Santé publique | `curl -s -o /dev/null -w '%{http_code}' https://<domaine>/health` |
| Santé détaillée | `docker compose exec app python -m app.cli health` |
| Relancer un service, sans changement de `.env` | `docker compose restart <service>` |
| Appliquer un changement de `.env` | `docker compose up -d <service>` |
| Révision du schéma | `docker compose run --rm migrate alembic current` |

### 56.6 Procédures

#### P1 — Déploiement

- **Quand** : toute mise à jour du code ou de `config/` (P10).
- **Étapes** : `scripts/deploy.sh <sha>`. Contrat et séquence : VIII §49.5, VII §36.9.
- **Vérification** : `/health` = `ok`, `docker compose ps`, ligne ajoutée à `~/radar-deploy.log` avec le sha et le `snapshot_id` du backup pris avant l'arrêt.
- **Échec** : le script s'arrête sur la première étape en erreur, avec le message ; voir P2 si la nouvelle version ne démarre pas.
- La sonde externe n'est pas mise en pause : la coupure reste sous deux sondes consécutives (VII §36.9).

#### P2 — Rollback

- **Quand** : la version déployée est défectueuse.
- **Sha cible** : le dernier déploiement réussi précédent, lu dans `~/radar-deploy.log`. Seul un sha **déjà déployé avec succès** est une cible de rollback : il a passé le verrou CI.

**Cas 1 — aucune migration entre les deux sha** : `scripts/deploy.sh <sha cible>`.

**Cas 2 — migration à défaire.** `deploy.sh` détecte qu'une migration du sha courant est absente du sha cible et **refuse**, en listant les migrations et leur réversibilité. On suit alors l'un des deux chemins, à la main, sans `deploy.sh`.

*2a — toutes les migrations sont réversibles* :
1. `docker compose exec worker python -m app.cli backup-now` ; noter le `snapshot_id`.
2. `docker compose stop app worker`.
3. `docker compose run --rm migrate alembic downgrade <révision head du sha cible>` — avec **l'image courante**, la seule qui connaît les `downgrade`.
4. `git checkout <sha cible>` ; `docker compose build` (ou image déjà présente) ; `docker compose up -d`.
5. Vérifier `/health`, `docker compose ps`, `alembic current` ; consigner l'opération dans `~/radar-deploy.log`.

*2b — au moins une migration irréversible* :
1. Mettre la sonde externe en pause (P6).
2. `docker compose exec worker python -m app.cli backup-now` (état de la version fautive, pour analyse).
3. `docker compose stop app worker`.
4. `git checkout <sha cible>` ; `docker compose build` — **l'ancien code doit être en place avant la restauration**, sinon `up -d` remigrerait la base.
5. `scripts/restore.sh <snapshot_id pris par deploy.sh avant le déploiement fautif>`.
6. Vérifications de P3 ; reprise de la sonde ; consigner.
7. Perte acceptée : les données depuis le déploiement fautif (les collectors recollectent, VII §38.1).

#### P3 — Restauration

- **Quand** : base corrompue ou perdue, erreur de données, exercice.
- **Étapes** (détail pas à pas dans `backup-restore.md`) :
  1. Pause de la sonde externe (P6).
  2. Choisir le snapshot : `docker compose run --rm --no-deps worker restic snapshots --tag radar-db`.
  3. `scripts/restore.sh <snapshot>` : arrêt d'`app` et `worker`, restauration, **suppression de `radar.db-wal` et `radar.db-shm` existants**, remplacement de `/data/radar.db`, `docker compose up -d` (VII §38.5).
  4. Contrôles : `/health`, `app.cli health` (révision, WAL), dashboard, bandeau d'état.
  5. Reprise de la sonde.
- **Jamais** : copier `radar.db` à côté d'un `-wal` existant. Un `-wal` issu d'une autre base corrompt la restauration.
- **Snapshot d'une révision plus récente que le code** : `migrate` échoue ; redéployer d'abord le sha correspondant.

#### P4 — Mot de passe du dashboard

1. Générer un mot de passe aléatoire de 20 caractères au moins, dans le gestionnaire de mots de passe.
2. `docker compose run --rm caddy caddy hash-password` — saisie interactive, jamais en argument (historique du shell).
3. Remplacer `DASHBOARD_PASSWORD_HASH` dans `.env`, **entre guillemets simples**.
4. `docker compose up -d caddy`.
5. Vérifier : 401 sans identifiants, 200 avec les nouveaux, `/health` toujours public.

#### P5 — Rotation des secrets

| Secret | Étapes | Vérification |
|---|---|---|
| `GITHUB_TOKEN` · `LLM_API_KEY` · `SMTP_PASSWORD` · `TELEGRAM_BOT_TOKEN` · identifiants du backend restic | créer le nouveau chez le fournisseur → `.env` (droits `600`) → `docker compose up -d worker` → révoquer l'ancien → gestionnaire de mots de passe | `/api/health` (sources, `llm_gateway`) ; `send-test-alert` pour les canaux ; `backup-now` pour restic |
| `RESTIC_PASSWORD` | `restic key add` (nouveau mot de passe) → `.env` → `docker compose up -d worker` → `backup-now` réussi → `restic key remove <ancienne clé>` → copie hors VPS mise à jour | `backup-now` puis `restore-test` |
| Jeton GitHub de `deploy.sh` (dépôt privé) | nouveau jeton *fine-grained* lecture seule → fichier hors `.env`, droits `600` → révoquer l'ancien | `deploy.sh` sur le sha courant |

Sans copie de `RESTIC_PASSWORD` hors du VPS, tous les backups sont perdus avec lui (VII §38.2).

#### P6 — Pause du monitoring externe

- **Quand** : restauration (P3), rollback 2b, `VACUUM` (P8), maintenance de plus de 10 minutes.
- **Inutile** : déploiement, reboot planifié (sous deux sondes consécutives).
- **Comment** : depuis l'interface du service retenu (noté dans `monitoring.md`).
- **Fin** : reprise de la sonde et vérification qu'elle repasse au vert. Une sonde oubliée en pause laisse l'instance sans surveillance.

#### P7 — Nettoyage des images Docker

- **Quand** : après un déploiement réussi, ou sur condition `disk_warning`.
- **Conserver** : l'image courante et la précédente (sha lus dans `~/radar-deploy.log`), pour le rollback.
- **Étapes** : `docker image ls radar-backend radar-caddy` → `docker image rm` des sha plus anciens → `docker image prune` (images orphelines seulement, **sans** `-a`) → `docker builder prune` si le cache de build pèse.
- **Vérification** : `docker system df` (mesure M8).

#### P8 — `VACUUM` manuel

- **Quand** : sur constat (fichier de base très supérieur aux données utiles), jamais planifié (VII §44.2).
1. Pause de la sonde (P6).
2. `docker compose exec worker python -m app.cli backup-now`.
3. `docker compose stop app worker` ; attendre que le heartbeat soit périmé (2 minutes).
4. `docker compose run --rm --no-deps worker python -m app.cli vacuum`.
5. `docker compose up -d` ; contrôles de P3 ; reprise de la sonde.

#### P9 — Reboot planifié de l'hôte

- **Quand** : mises à jour de sécurité qui l'exigent.
- **Étapes** : `sudo reboot`, sans pause de la sonde.
- **Vérification** : `/health` = `ok` en 3 minutes au plus (M10), `docker compose ps`. Au-delà, voir la ligne « `/health` injoignable » de P11.

#### P10 — Modifier la configuration

- `config/` est versionné : toute modification passe par un commit, une PR, la CI (`validate-config`) et P1. Jamais d'édition sur le VPS.
- Les réglages `Setting` se modifient dans le dashboard, sans déploiement.
- Les secrets et paramètres de déploiement se modifient dans `.env`, puis `docker compose up -d <service>`.

#### P11 — Répondre à une alerte

**Alertes `system` du worker** (VII §39.5) :

| Condition | Premier diagnostic | Action |
|---|---|---|
| `disk_warning` · `disk_critical` | `app.cli health` (host), `docker system df`, taille de `radar.db` et du `-wal` | P7 ; si la base croît anormalement, vérifier la purge (`job_failing:purge`) |
| `ram_high` | `docker stats` ; mémoire du worker dans `app.cli health` | relancer le worker (`restart`) ; si récurrent, mesure M1 et `mem_limit` |
| `wal_large` | job analytique ou backup en cours ; `db_locked` | attendre la fin de l'opération ; si persistant, relancer le worker ; recaler `ops.wal_max_bytes` d'après M3 |
| `db_locked` | logs `database is locked`, plus longue transaction (M4) | relancer le worker ; ouvrir une issue avec les logs (transaction trop longue = bug) |
| `llm_config_error` | `llm_gateway.reason`, variables `LLM_*` | corriger `.env`, `docker compose up -d worker` |
| `llm_down_long` | état du gateway ou du provider, quota | rétablir le gateway ; sinon rien : le produit tourne en repli |
| `embeddings_down` | logs du worker (`embeddings`) | relancer le worker ; si l'échec persiste, issue (modèle, RAM) |
| `backup_not_configured` | `RESTIC_REPOSITORY` | configurer le dépôt dans `.env`, `docker compose up -d worker`, `backup-now` |
| `backup_failed` · `backup_stale` | `backup_last_attempt.error` dans `app.cli health` | corriger la cause (identifiants, dépôt, espace), puis `backup-now` |
| `restore_test_failed` · `restore_test_stale` | `last_restore_test.error` | `restore-test` ; si le backup est en cause, `backup-now` puis `restore-test` |
| `sources_down` | `/api/health` (sources), `last_error` par source | panne réseau ou fournisseur : attendre le disjoncteur ; source morte : désactiver dans `config/` (P10) |
| `job_failing:<job>` | logs du job | issue ; relancer le worker si le job est bloqué |
| `no_alert_channel` | visible seulement dans le dashboard | configurer au moins un canal, `send-test-alert` |

**Alertes du monitoring externe** (VII §39.5, couverture des arrêts) :

| Symptôme | Premier diagnostic | Action |
|---|---|---|
| `/health` → 503 | `app.cli health` : heartbeat périmé ou base inaccessible | `docker compose logs worker` ; `validate-config` si le worker boucle ; `up -d` |
| `/health` → 502 | `docker compose ps` : `app` arrêté, ou `migrate` en échec | `docker compose logs migrate app` ; si la révision est inconnue du code, P2 |
| `/health` injoignable | VPS, DNS, Caddy, certificat | accès SSH ; `docker compose ps` ; `docker compose logs caddy` ; console du fournisseur si le VPS ne répond pas |
| Certificat expirant | logs Caddy (ACME) | ports 80/443 et DNS ; `docker compose restart caddy` |

---

## 57. Première mission de Claude Code — Sprint 0 · Cadrage

Description canonique du Sprint 0. VIII §47.2 y renvoie.

### 57.1 Objet

Transformer la spec en un contrat cohérent et vérifié, et préparer le Sprint 1, **sans écrire de code applicatif**. Le Sprint 0 produit **uniquement des documents** : les propositions de fichiers (Compose, CI, schéma, configuration) y figurent sous forme de blocs, jamais sous forme de fichiers exécutables.

### 57.2 Préalables

Fournis au lancement du Sprint 0 :
- les dix fichiers de spec durcis en Markdown, dont la **Partie VII en source Markdown** (l'export actuel n'en est pas une) ;
- un dépôt initialisé, les fichiers de spec bruts placés sous `docs/spec/` ;
- l'architecture du VPS cible (`amd64` par défaut, décision 27).

Retirés du contexte : la V0.2 et tout doublon de fichier de spec.

### 57.3 Déroulé

Les tâches s'enchaînent dans cet ordre. T0.1 fait l'objet d'une **PR dédiée**, validée avant les suivantes, qui s'appuient sur une spec réconciliée.

| # | Tâche | Livrable |
|---|---|---|
| T0.1 | **Report des impacts** : appliquer chaque « Impact à répercuter » des Parties I à IX dans sa partie cible ; retirer les sections d'impacts et les marqueurs ; écrire `SPEC.md` (index). Tout impact inapplicable ou contradictoire est listé, **pas arbitré** | `docs/spec/*`, `SPEC.md` ; liste des conflits dans `sprint-00-cadrage.md` |
| T0.2 | **Lecture de la spec** réconciliée ; décisions techniques manquantes, ambiguïtés, trous | `sprint-00-cadrage.md` |
| T0.3 | **Vérification des dépendances** (§57.4) | `sprint-00-cadrage.md` |
| T0.4 | **Modèle SQL cible** : toutes les tables, colonnes, contraintes, index et triggers FTS, avec le sprint qui introduit chacun (VIII §47.1) | `database.md` |
| T0.5 | **Arborescence**, **stratégie de configuration** (quatre fichiers `config/`, `.env`, `Setting`, validation), **proposition de `docker-compose.yml`** conforme à VII §36, **conception** du squelette CI (six étapes), de `Clock` et de `scripts/check-test-catalog.py` | `architecture.md` |
| T0.6 | **ADR 0001 à 0019**, statut `Proposé` ; index et gabarit | `docs/adr/` |
| T0.7 | **`CLAUDE.md`** (§55.3) | `CLAUDE.md` |
| T0.8 | **Plan détaillé du Sprint 1** : tâches ordonnées selon les contraintes D1 à D4 (VIII §48), identifiants de tests visés, critères d'acceptation de VIII §47.2 | `sprints/sprint-01.md` |

### 57.4 Vérifications de dépendances

Chaque vérification consigne la commande, la version et le résultat dans `sprint-00-cadrage.md`. Les scripts utilisés sont jetables, **jamais commités**.

| Vérification | Attendu | Si échec |
|---|---|---|
| `paraphrase-multilingual-MiniLM-L12-v2` disponible dans `fastembed`, sur l'architecture cible | modèle chargé, 384 dimensions ; **révision et empreinte sha256 du modèle notées** pour épinglage au build | repli : autre modèle multilingue ≤ 384 dimensions supporté par fastembed, consigné dans l'ADR-0008 |
| SQLite de l'image de base Python retenue | ≥ 3.35, FTS5 et JSON1 compilés | autre image de base ou wheel SQLite, consigné |
| `BEGIN IMMEDIATE` avec SQLAlchemy 2.x async et aiosqlite | transaction d'écriture ouverte en `IMMEDIATE`, mécanisme noté (gestion des transactions du driver) | proposition alternative, question au propriétaire |
| WAL sur **volume nommé** Docker | `journal_mode=wal` effectif, fichiers `-wal` / `-shm` créés sur le volume | bloquant |
| restic en binaire statique pour l'architecture cible | version épinglée disponible | bloquant |
| onnxruntime et lingua pour l'architecture cible | wheels disponibles | bloquant |
| APScheduler 3.x sur Python 3.12 | dernière 3.x compatible, version notée | bloquant |
| Outils CI (analyse de secrets, audit backend et frontend) | outil retenu et version | outil équivalent, consigné |

### 57.5 Rapport de cadrage — `docs/sprints/sprint-00-cadrage.md`

Sections :
1. **Conflits de spec** relevés en T0.1, avec les passages en cause.
2. **Décisions manquantes** : pour chacune, contexte, options, recommandation. Chaque point est tranché par le propriétaire du projet ; la réponse est consignée, et l'ADR ou la mise à jour de spec correspondante est faite dans le Sprint 0.
3. **Résultats des vérifications** (§57.4).
4. **Risques identifiés** pour les sprints suivants.
5. **Questions ouvertes** : vide à l'acceptation.

### 57.6 Interdits du Sprint 0

- Tout code sous `app/`, `frontend/`, `migrations/`, `scripts/`, `tests/`.
- Tout fichier exécutable ou de configuration d'outillage : `docker-compose*.yml`, Dockerfiles, `Caddyfile`, `pyproject.toml`, lockfiles, workflows CI, `config/*.yaml`, `.env.example`.
- Toute implémentation d'un sprint suivant, même partielle.

### 57.7 Acceptation

Le Sprint 0 est terminé quand **tous** les points suivants sont vrais :
- [ ] la PR de T0.1 est fusionnée : `docs/spec/` réconcilié, `SPEC.md` en index, plus aucune section d'impacts ni marqueur « (proposé) » ;
- [ ] `architecture.md`, `database.md`, `docs/adr/` (index, gabarit, 0001–0019), `CLAUDE.md`, `sprint-00-cadrage.md` et `sprint-01.md` sont présents ;
- [ ] les ADR 0001 à 0019 sont en statut `Accepté` ;
- [ ] le rapport de cadrage n'a plus de question ouverte ;
- [ ] toutes les vérifications du §57.4 sont concluantes ou couvertes par un ADR ;
- [ ] le diff du sprint ne touche que `docs/`, `SPEC.md` et `CLAUDE.md` (`git diff --stat` depuis le commit initial) ;
- [ ] relu et validé par le propriétaire du projet.

La CI n'existe pas encore : elle est créée au Sprint 1. La protection de `main` est posée à ce moment-là.

### 57.8 Enchaînement

- Le **Sprint 1 — Foundation** démarre quand le Sprint 0 est accepté **et** que le plan `sprint-01.md` est validé. Son contenu et ses critères sont ceux de VIII §47.2 ; ils ne sont pas repris ici.
- La même règle s'applique à chaque sprint : plan dans `docs/sprints/sprint-NN.md` validé avant l'implémentation ; à la fin, Claude Code complète le bilan (écarts à la spec, dette tracée, identifiants couverts) et **s'arrête** jusqu'à validation (VIII §51.2).

---

## Points d'interprétation — tranchés ou à confirmer

**Tranchés dans cette partie** (l'implémenteur n'a pas à choisir) :
- niveaux de décision, définition de la preuve, circuit d'acceptation ;
- liste des décisions verrouillées et des interdits par anticipation ;
- registre des ADR, format, statuts, règles de remplacement ;
- arbre de documentation, contenu de `SPEC.md` et de `CLAUDE.md`, moment de création et frontières des documents ;
- contrat commun des commandes CLI, mode d'exécution, verrou de backup, commande `vacuum` ;
- procédures du runbook, dont le rollback à travers une migration et la table de réponse aux alertes ;
- déroulé, livrables, interdits et acceptation du Sprint 0 ; enchaînement des sprints.

**Laissés à l'implémenteur, sans impact sur le contrat** :
- rédaction et longueur des ADR dans la cible d'une page ;
- options des commandes CLI au-delà de celles citées ;
- forme du rapport de cadrage et des fichiers de sprint, tant qu'ils couvrent les sections imposées ;
- organisation interne de chaque document de `docs/`.

**À confirmer à la relecture** :
1. Points « (proposé) » et « à confirmer » des Parties I à VIII réputés validés (décision 12).
2. Architecture `amd64` par défaut (décision 27).
3. Codes de sortie `0` / `1` / `2` et séparation stdout / stderr des commandes CLI (§56.3).
4. Détection du rollback à travers une migration par comparaison des fichiers de migration entre le sha déployé et le sha cible (impact VIII).

---

## Reporté en V2 (tracé depuis la Partie IX)

- **Rollback outillé** : `deploy.sh` exécute lui-même le downgrade ou la restauration au lieu de refuser.
- **Contrôles CI de gouvernance** : chaque `DV-nn` a un ADR `Accepté` ; liens de `SPEC.md` et de `docs/` valides ; index des ADR généré.
- **Opérations depuis le dashboard** (backup, test d'alerte, santé détaillée) ; en V1, elles restent en CLI, l'app n'émettant ni n'exécutant rien.
- **Rotation automatique des secrets.**
- **Site de documentation généré** à partir de `docs/`.
- **Déploiement continu** (déjà reporté par VII et VIII).

---

## Impacts à répercuter dans les autres parties

À traiter au Sprint 0, tâche T0.1 — **hors Partie IX**.

### `SPEC.md`

- Devient l'index du §55.2. Supprimer « Décisions prises dans cette V0.3 (à valider) ».

### Partie VIII — Livraison

- **§47.2 Sprint 0** : remplacer le contenu par un renvoi à IX §57, description canonique.
- **§47.2 Sprint 11** : « Documentation d'exploitation » devient « finalisation » des documents d'exploitation (IX §55.4).
- **§47.1 et §51.2** : plan de sprint validé avant implémentation, bilan en fin de sprint, dans `docs/sprints/sprint-NN.md`.
- **Décision 22** : `SPEC.md` contient un lien vers le §53, pas la liste.
- **§46.1 arborescence** : ajouter `CLAUDE.md`, `docs/sprints/`, `docs/adr/README.md` et `_template.md`, `docs/spec/partie-V-A.md` et `partie-V-B.md` ; ajouter `vacuum` au commentaire de `app/cli/`.
- **§49.5 `deploy.sh`** :
  - détecter une migration du sha déployé absente du sha cible (comparaison de `migrations/versions/` entre les deux sha) et refuser en listant les migrations et leur réversibilité, avec renvoi au runbook ;
  - journaliser le `snapshot_id` renvoyé par `backup-now` dans `~/radar-deploy.log` ;
  - la ligne « Rollback » renvoie à IX §56.6-P2.
- **§50.5 catalogue** — tests à ajouter :
  - `backup-now` affiche le `snapshot_id` ;
  - verrou de backup : commande concurrente d'un job en cours → code `1` ; job planifié qui trouve le verrou → abstention sans `backup_failed` ;
  - `vacuum` refusé avec un heartbeat frais et avec un espace libre insuffisant ;
  - codes de sortie `2` sur usage ou configuration invalide ;
  - `deploy.sh` refuse un rollback à travers une migration.

### Partie VII — Ops

- **§36.8** : ajouter `vacuum` ; `backup-now` affiche le `snapshot_id` ; colonne « Où » de `validate-config` : `run --rm --no-deps worker` ; renvoi au contrat commun IX §56.3.
- **§36.9** : la ligne « Rollback » renvoie à IX §56.6-P2 (cas avec migration).
- **§38.2 et §38.4** : verrou exclusif `/data/backup/.lock` partagé par les jobs `backup`, `restore_test` et les commandes `backup-now`, `restore-test` (IX §56.4.1).
- **§38.5** : « le détail pas à pas va dans `docs/backup-restore.md` ; le runbook le résume ».
- **§43.4** : « redémarrage du worker » devient `docker compose up -d worker` ; `docker compose up -d caddy` pour le mot de passe.
- **§44.2** : `VACUUM` manuel par `app.cli vacuum`, fichiers temporaires de SQLite sur `/data`, jamais dans le tmpfs.

### Partie III — Données

- **§12.1** : disponibilité du modèle vérifiée **au Sprint 0** (IX §57.4) ; révision et empreinte du modèle épinglées au build ; choix consigné dans l'ADR-0008.
- **§10.4** : `/data` est toujours un volume nommé, jamais un bind mount, en développement comme en production.
