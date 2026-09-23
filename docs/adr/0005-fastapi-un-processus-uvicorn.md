# ADR 0005 — FastAPI, un seul processus uvicorn

| | |
|---|---|
| **Statut** | Accepté |
| **Date** | 2026-09-23 |
| **Décision(s) couverte(s)** | DV-07 ; VII §35, §36.5 · VI §31 |

## Contexte

L'API sert un seul utilisateur (I §5). Elle lit la base, dépose des jobs et calcule `/health` ; elle garde quelques
compteurs en mémoire, exposés par `/api/health` (VII §35, §39). Le code backend est asynchrone, comme le worker
(III §10.3).

## Décision

L'API est une application FastAPI, servie par **un seul processus** uvicorn (`--workers 1`) (VII §35, §36.5).

## Alternatives écartées

- **Plusieurs workers uvicorn ou gunicorn** : aucun gain de débit utile pour un utilisateur ; les compteurs en mémoire divergeraient d'un processus à l'autre (VII §35).
- **Framework synchrone (Django, Flask)** : le reste du backend est asynchrone (SQLAlchemy async, aiosqlite) ; deux modèles d'exécution à maintenir.
- **FastAPI servant la SPA** : Caddy sert le statique et porte la CSP (II décision 7, ADR-0013).

## Conséquences

- **On gagne** : validation Pydantic partagée avec la configuration et le worker ; déploiement simple ; compteurs cohérents.
- **On accepte** : un seul cœur CPU pour l'API ; toute requête longue bloque les autres, d'où l'interdiction des traitements longs côté app (II §8.3).
- **Preuve de réexamen** : la mesure M9 (p95 de l'API > 300 ms au profil cible, VII §45.3) hors critère et imputée au processus unique ; un besoin multi-utilisateur validé.

## Preuve

Sans objet : cet ADR ne remplace aucune décision précédente.

## Remplace

Aucun.
