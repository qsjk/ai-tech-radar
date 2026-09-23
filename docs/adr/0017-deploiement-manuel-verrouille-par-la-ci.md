# ADR 0017 — Déploiement manuel verrouillé par la CI

| | |
|---|---|
| **Statut** | Accepté |
| **Date** | 2026-09-23 |
| **Décision(s) couverte(s)** | DV-19 ; VIII §49.1, §49.5 · VII §36.9 · IX décision 18, §56.6-P1, P2 |

## Contexte

Un seul exploitant déploie sur un seul VPS (ADR-0009). La CI ne détient aucun secret de production (VIII §49.1).
Une migration non réversible déployée à tort peut coûter des données (IX décision 18).

## Décision

Le déploiement V1 est **manuel**, par `scripts/deploy.sh [<sha>]` sur le VPS. Le script refuse un sha dont la CI
n'est pas terminée et verte, **e2e compris**, refuse un rollback à travers une migration, prend un backup avant
l'arrêt et journalise le sha et le `snapshot_id` ; aucun contournement (`--force`) (VIII §49.5).

## Alternatives écartées

- **Déploiement continu depuis la CI** : la CI recevrait des secrets de production et un accès au VPS ; reporté en V2 (VIII « Reporté en V2 »).
- **Déploiement manuel sans contrôle CI** : un sha non testé peut atteindre la production.
- **Option `--force` d'urgence** : contourne le seul garde-fou ; la voie d'urgence est le rollback vers un sha déjà vert (IX §56.6-P2).

## Conséquences

- **On gagne** : aucun secret de production en CI ; seul un sha vert est déployable ; point de retour garanti par le backup du déploiement.
- **On accepte** : une étape manuelle à chaque livraison ; dépendance à l'API GitHub au moment du déploiement ; un jeton en lecture seule si le dépôt devient privé (VIII §49.5).
- **Preuve de réexamen** : un incident de déploiement que le verrou n'a pas empêché ; un test T-BKP-12 en échec ; un besoin fonctionnel validé de livraison continue.

## Preuve

Sans objet : cet ADR ne remplace aucune décision précédente.

## Remplace

Aucun.
