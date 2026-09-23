# Architecture Decision Records

Le §53 de la Partie IX dit **quoi** (décisions verrouillées `DV-nn`) ; un ADR dit **pourquoi**, contre quoi et à quel
prix (IX §54.1). Format, règles et registre : IX §54.2–§54.3. Gabarit : [`_template.md`](_template.md).

- Numéro sur 4 chiffres, séquentiel, jamais réutilisé ; un ADR `Accepté` n'est jamais réécrit, seul son statut change.
- Claude Code rédige en `Proposé` ; seul le propriétaire du projet accepte ou rejette (IX §53.1, décision 4).
- Changer une décision verrouillée exige une **preuve** (IX §53.1) et un ADR qui remplace le précédent.

| ADR | Titre | Statut | Date | Couvre | Remplace / remplacé par |
|---|---|---|---|---|---|
| [0001](0001-sqlite-base-unique-et-file-de-jobs.md) | SQLite comme base unique et file de jobs en base | Proposé | 2026-09-23 | DV-01, DV-02 | — |
| [0002](0002-fts5-et-cosine-numpy.md) | Recherche et similarité dans le processus : FTS5, cosine numpy | Proposé | 2026-09-23 | DV-03, DV-04 | — |
| [0003](0003-coeur-deterministe-et-couche-ai-asynchrone.md) | Cœur déterministe et couche AI asynchrone | Proposé | 2026-09-23 | DV-05 | — |
| [0004](0004-deux-processus-sans-ipc.md) | Deux processus sans IPC, écrivain unique par table | Proposé | 2026-09-23 | DV-06 | — |
| [0005](0005-fastapi-un-processus-uvicorn.md) | FastAPI, un seul processus uvicorn | Proposé | 2026-09-23 | DV-07 | — |
| [0006](0006-apscheduler-3x.md) | APScheduler 3.x | Proposé | 2026-09-23 | DV-08 | — |
<!-- INDEX -->

**À venir** (IX §54.3) : 0020, gateway LLM retenu, au Sprint 6 ; 0021, Docker en développement, par T0.9 (#60) ;
ADR conditionnels, au prochain numéro libre, seulement si leur déclencheur survient.
