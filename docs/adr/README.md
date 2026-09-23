# Architecture Decision Records

Le §53 de la Partie IX dit **quoi** (décisions verrouillées `DV-nn`) ; un ADR dit **pourquoi**, contre quoi et à quel
prix (IX §54.1). Format, règles et registre : IX §54.2–§54.3. Gabarit : [`_template.md`](_template.md).

- Numéro sur 4 chiffres, séquentiel, jamais réutilisé ; un ADR `Accepté` n'est jamais réécrit, seul son statut change.
- Un ADR est rédigé en `Proposé` ; seul le propriétaire du projet l'accepte ou le rejette (IX §53.1, décision 4).
- Changer une décision verrouillée exige une **preuve** (IX §53.1) et un ADR qui remplace le précédent.

| ADR | Titre | Statut | Date | Couvre | Remplace / remplacé par |
|---|---|---|---|---|---|
| [0001](0001-sqlite-base-unique-et-file-de-jobs.md) | SQLite comme base unique et file de jobs en base | Proposé | 2026-09-23 | DV-01, DV-02 | — |
| [0002](0002-fts5-et-cosine-numpy.md) | Recherche et similarité dans le processus : FTS5, cosine numpy | Proposé | 2026-09-23 | DV-03, DV-04 | — |
| [0003](0003-coeur-deterministe-et-couche-ai-asynchrone.md) | Cœur déterministe et couche AI asynchrone | Proposé | 2026-09-23 | DV-05 | — |
| [0004](0004-deux-processus-sans-ipc.md) | Deux processus sans IPC, écrivain unique par table | Proposé | 2026-09-23 | DV-06 | — |
| [0005](0005-fastapi-un-processus-uvicorn.md) | FastAPI, un seul processus uvicorn | Proposé | 2026-09-23 | DV-07 | — |
| [0006](0006-apscheduler-3x.md) | APScheduler 3.x | Proposé | 2026-09-23 | DV-08 | — |
| [0007](0007-llm-api-openai-compatible-optionnel.md) | Accès LLM par API OpenAI-compatible, gateway hors app, LLM optionnel | Proposé | 2026-09-23 | DV-09 | — |
| [0008](0008-embeddings-fastembed-modele.md) | Moteur et modèle d'embeddings | Proposé | 2026-09-23 | DV-10 | — |
| [0009](0009-topologie-docker-compose-vps-unique.md) | Topologie Docker Compose sur VPS unique | Proposé | 2026-09-23 | DV-11 | — |
| [0010](0010-exposition-et-cloisonnement.md) | Exposition et cloisonnement : Caddy, segmentation réseau, conteneurs durcis, anti-SSRF | Proposé | 2026-09-23 | DV-12 | — |
| [0011](0011-authentification-dashboard.md) | Authentification du dashboard | Proposé | 2026-09-23 | DV-13 | — |
| [0012](0012-semantique-health.md) | Sémantique de /health | Proposé | 2026-09-23 | DV-14 | — |
| [0013](0013-frontend-react-typescript-vite-csp.md) | Frontend React · TypeScript · Vite et CSP stricte | Proposé | 2026-09-23 | DV-15 | — |
| [0014](0014-pas-de-prometheus-v1.md) | Pas de Prometheus en V1 | Proposé | 2026-09-23 | DV-16 | — |
| [0015](0015-backup-restic-par-le-worker.md) | Backup restic exécuté par le worker, test de restauration automatisé | Proposé | 2026-09-23 | DV-17 | — |
| [0016](0016-horloge-injectable.md) | Horloge injectable, temps jamais lu en SQL | Proposé | 2026-09-23 | DV-18 | — |
| [0017](0017-deploiement-manuel-verrouille-par-la-ci.md) | Déploiement manuel verrouillé par la CI | Proposé | 2026-09-23 | DV-19 | — |
| [0018](0018-tracabilite-du-catalogue.md) | Traçabilité du catalogue, pas de seuil de couverture | Proposé | 2026-09-23 | DV-20 | — |
| [0019](0019-spec-dans-le-depot.md) | Spec dans le dépôt, SPEC.md en index | Proposé | 2026-09-23 | DV-21 | — |

**À venir** (IX §54.3) : 0020, gateway LLM retenu, au Sprint 6 ; 0021, Docker en développement, par T0.9 (#60) ;
ADR conditionnels, au prochain numéro libre, seulement si leur déclencheur survient.
