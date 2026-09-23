# ADR 0018 — Traçabilité du catalogue, pas de seuil de couverture

| | |
|---|---|
| **Statut** | Accepté |
| **Date** | 2026-09-23 |
| **Décision(s) couverte(s)** | DV-20 ; VIII décisions 9, 10, §47.1, §50.3, §52 (A2) ; décisions E1, E3, P-15 ; `docs/architecture.md` §5.3 |

## Contexte

La spec énumère les comportements à tester dans un catalogue identifié (VIII §50.5). Chaque sprint finit avec une CI
verte (VIII §47.1), et les étapes de la CI sont obligatoires pour fusionner sur `main` (VIII §46.2). Un pourcentage de
couverture ne dit pas si les comportements exigés sont testés.

## Décision

Le critère bloquant est la **traçabilité du catalogue** : chaque identifiant automatisé visé a au moins un test,
chaque marqueur `spec` renvoie à un identifiant existant. La couverture est mesurée et publiée, jamais bloquante
(VIII décisions 9 et 10). Le contrôle porte sur les identifiants des **sprints clos** ; ceux du sprint **en cours** sont
signalés sans bloquer jusqu'à la PR de bilan ; tout le catalogue est contrôlé au Sprint 11 (E1, P-15, VIII §50.3). Un
identifiant couvert en plusieurs sprints est suivi par volets (E3, P-11).

## Alternatives écartées

- **Seuil de couverture bloquant** : récompense les lignes exécutées, pas les comportements exigés ; incite aux tests sans assertion.
- **Contrôle de tout le catalogue dès le Sprint 1** : incompatible avec une CI verte à chaque sprint : environ 180 identifiants n'ont pas encore de test (E1).
- **Identifiants du sprint en cours bloquants** : chaque PR du sprint échouerait tant que le dernier test n'existe pas, et plus rien ne se fusionnerait sur `main` (P-15).
- **Tests vides marqués `skip` pour les identifiants futurs** : traçabilité fictive (E1, option C).

## Conséquences

- **On gagne** : un lien vérifiable entre la spec et les tests ; une CI verte à chaque sprint ; un catalogue complet exigé avant la production.
- **On accepte** : des identifiants non testés tolérés pendant le sprint en cours ; le mécanisme dépend du statut tenu à jour dans chaque `sprint-NN.md`.
- **Preuve de réexamen** : un incident ou un défaut en production sur un comportement marqué comme couvert ; un test du script `check-test-catalog.py` qui montre une extraction fragile (R-07).

## Preuve

Sans objet : cet ADR ne remplace aucune décision précédente.

## Remplace

Aucun.
