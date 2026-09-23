# ADR 0012 — Sémantique de /health

| | |
|---|---|
| **Statut** | Accepté |
| **Date** | 2026-09-23 |
| **Décision(s) couverte(s)** | DV-14 ; VI décision 14 · VII §39.5, §40, §41 · VIII §47.2 (Sprints 1 et 11) |

## Contexte

Un monitoring externe doit alerter quand le produit ne rend plus son service, sans connaître l'intérieur (VII §41).
`/health` est public : il ne doit rien révéler. Le produit vit aussi en mode dégradé (LLM absent, backup en échec),
qui ne justifie pas une alerte externe.

## Décision

`/health` public renvoie seulement `{"status": "ok" | "degraded" | "down"}`, en HTTP 200, 200, 503. `down` = base
inaccessible **ou** worker mort (heartbeat périmé). Le détail par composant est sur `/api/health`, authentifié ; les
deux, et `/api/status`, sont calculés par le même module (VII §40).

## Alternatives écartées

- **`/health` public détaillé** : expose des informations internes sans authentification (VII §40.1).
- **503 dès l'état `degraded`** : le monitoring externe alerterait pour un LLM non configuré ou un backup en retard, déjà couverts par les alertes `system` du worker (VII §39.6).
- **`down` sur la seule panne de l'app** : un worker arrêté, donc une collecte arrêtée, passerait inaperçu : seul le heartbeat le révèle.
- **Healthchecks Docker comme source de santé** : Compose ne redémarre pas un conteneur `unhealthy` ; décision P-06 : aucun healthcheck.

## Conséquences

- **On gagne** : un contrat simple pour le monitoring externe ; aucune fuite d'information ; un seul calcul de santé.
- **On accepte** : le dashboard reste lisible alors que `/health` vaut `down` si le worker est mort ; la nuance `degraded` n'est visible qu'authentifié.
- **Preuve de réexamen** : un incident réel non détecté par le monitoring externe, ou une alerte externe à tort répétée ; un test T-OPS-* qui montre un statut incohérent avec la table VII §39.5.

## Preuve

Sans objet : cet ADR ne remplace aucune décision précédente.

## Remplace

Aucun.
