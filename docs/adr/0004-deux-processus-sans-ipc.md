# ADR 0004 — Deux processus sans IPC, écrivain unique par table

| | |
|---|---|
| **Statut** | Proposé |
| **Date** | 2026-09-23 |
| **Décision(s) couverte(s)** | DV-06 ; II §8.1–§8.4 · V-A §23.6, décision 19 · `docs/database.md` §1.4 |

## Contexte

L'API doit répondre immédiatement pendant que le worker collecte, calcule des embeddings et appelle le LLM
(II §6.1). Le travail long ne doit ni bloquer l'API ni dépendre d'elle. Le produit tient sur un VPS, sans service
supplémentaire (I §4.3).

## Décision

Deux processus, `app` et `worker`, se coordonnent **uniquement par la base** : le schéma SQLite est le contrat,
sans IPC (II §8.2). Chaque table et chaque clé `SystemState` ont un seul écrivain ; les exceptions sont documentées
(V-A décision 19 : `dead_letter → pending / cancelled` par l'app). L'app dépose des jobs, elle n'en exécute jamais
(II §8.3).

## Alternatives écartées

- **Un seul processus (API et worker ensemble)** : le travail CPU et les appels réseau du worker dégraderaient la latence de l'API ; un crash du worker ferait tomber l'API.
- **IPC directe (HTTP interne, file de messages, signaux)** : une seconde voie de coordination à rendre fiable, et `worker` joignant `app` casserait la segmentation réseau (ADR-0010).
- **Plusieurs écrivains par table** : courses et verrous à arbitrer dans le code ; la règle d'un seul écrivain rend chaque transition vérifiable.

## Conséquences

- **On gagne** : processus redémarrables séparément ; API toujours réactive ; propriété des données lisible (`database.md` §1.4).
- **On accepte** : une latence de coordination égale à la période de sondage de la base (ticks) ; chaque nouvelle interaction passe par une table ou une clé.
- **Preuve de réexamen** : un besoin de latence que le sondage de la base ne tient pas (mesure M9 hors critère imputable à la coordination) ; toute nouvelle exception à la règle d'un seul écrivain : déclencheur conditionnel du registre, ADR d'exception documentée (IX §54.3).

## Preuve

Sans objet : cet ADR ne remplace aucune décision précédente.

## Remplace

Aucun.
