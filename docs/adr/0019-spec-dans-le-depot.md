# ADR 0019 — Spec dans le dépôt, SPEC.md en index

| | |
|---|---|
| **Statut** | Proposé |
| **Date** | 2026-09-23 |
| **Décision(s) couverte(s)** | DV-21 ; VIII décision 22 · IX §53.1, §55.1, §55.2 |

## Contexte

La spec est le contrat entre l'implémentation et le propriétaire du projet (IX §53). Les tests en tirent leurs identifiants
(ADR-0018). Chaque changement de décision exige une mise à jour de la spec dans la même PR que l'ADR (IX §53.1).

## Décision

La spec vit dans le dépôt, sous `docs/spec/`, une partie par fichier ; `SPEC.md` à la racine est l'index, sans copie
des décisions (IX §55.2). Les identifiants de test sont extraits de `docs/spec/partie-VIII.md` par la CI
(VIII décision 22).

## Alternatives écartées

- **Spec hors du dépôt (wiki, document partagé)** : versions désynchronisées du code ; impossible d'exiger la mise à jour de la spec dans la PR qui change une décision.
- **Spec en un seul fichier** : diffs illisibles et conflits fréquents ; découpage réalisé en T0.1a (E10).
- **Catalogue de tests dans un fichier séparé de la spec** : deux sources à tenir cohérentes ; le catalogue fait partie du contrat.

## Conséquences

- **On gagne** : historique Git de chaque décision ; relecture en PR ; source unique pour les identifiants de test.
- **On accepte** : la spec suit les règles de revue du code ; une retouche de forme de VIII §50.5 peut casser l'extraction des identifiants (R-07).
- **Preuve de réexamen** : un besoin fonctionnel validé de publier la spec hors du dépôt ; un test qui montre que l'extraction depuis `partie-VIII.md` ne peut pas être rendue fiable.

## Preuve

Sans objet : cet ADR ne remplace aucune décision précédente.

## Remplace

Aucun.
