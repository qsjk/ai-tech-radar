# ADR 0014 — Pas de Prometheus en V1

| | |
|---|---|
| **Statut** | Proposé |
| **Date** | 2026-09-23 |
| **Décision(s) couverte(s)** | DV-16 ; VII décisions 16, 17, §39, §40.3 · IX §53.3 |

## Contexte

L'exploitant est seul ; il doit voir les incidents majeurs sans SSH (I §4.3 « Observable ») et recevoir des alertes
(VII §39.6). Le produit tient en 3 ou 4 services permanents (I §4.3 « Simple »).

## Décision

Pas de Prometheus ni de Grafana en V1. Le worker calcule métriques et conditions (`ops.tick`, toutes les 60 s), les
écrit dans `SystemState` ; elles sont exposées par `/api/health`, le bandeau du dashboard, les tables d'historique et
les logs JSON (VII décisions 16 et 17, §39).

## Alternatives écartées

- **Prometheus et Grafana** : deux services permanents de plus, leur stockage et leur exposition à sécuriser, pour un exploitant ; interdits par anticipation (IX §53.3).
- **Service de métriques externe (SaaS)** : coût, envoi de données hors du VPS et nouveau secret à gérer.
- **Endpoint `/metrics` sans serveur Prometheus** : sans consommateur en V1 ; reporté en V2 (VII « Reporté en V2 »).

## Conséquences

- **On gagne** : aucun service de plus ; métriques lues sans balayage coûteux dans une requête HTTP (VII décision 16) ; alertes `system` par épisode.
- **On accepte** : pas d'historique de séries temporelles ni de tableaux de bord ; l'analyse fine passe par les tables d'historique et les logs.
- **Preuve de réexamen** : un incident que les conditions de VII §39.5 n'ont pas détecté alors qu'une série temporelle l'aurait montré ; un besoin fonctionnel validé de tableaux de bord ; mesure M1 ou M5 hors critère imputée au calcul des métriques par le worker.

## Preuve

Sans objet : cet ADR ne remplace aucune décision précédente.

## Remplace

Aucun.
