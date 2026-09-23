# ADR 0003 — Cœur déterministe et couche AI asynchrone

| | |
|---|---|
| **Statut** | Proposé |
| **Date** | 2026-09-23 |
| **Décision(s) couverte(s)** | DV-05 ; I §3, §4 · II §6, §6.1, §9.1 · V-A décisions 4, 7 |

## Contexte

Le produit doit fonctionner avec un LLM à 0 €, ou sans LLM du tout, et rester indépendant des providers
(I §4.3). Les gateways gratuits ont des quotas et des pannes ; un produit qui en dépend s'arrêterait avec eux. La
hotness, le regroupement et les alertes doivent rester calculables sans LLM (I §3).

## Décision

L'architecture a deux couches : un **cœur déterministe** complet de bout en bout (collecte, dédup, relevance,
embeddings locaux, clustering, hotness, tendances, recherche, alertes) et une **couche d'enrichissement AI
asynchrone**, best-effort (II §6). Aucun appel LLM dans le pipeline d'ingestion ni dans une requête HTTP ; le LLM
enrichit, il ne décide jamais d'une structure (II §6.1).

## Alternatives écartées

- **LLM dans le pipeline (classification ou dédup à l'ingestion)** : une panne ou un quota épuisé arrêterait l'ingestion ; coût proportionnel au volume collecté.
- **LLM pour l'arbitrage des cas ambigus du clustering et l'analyse des tendances en V1** : il modifierait l'appartenance des articles ou des résultats structurants ; reporté en V2 (V-A décisions 4 et 7, CF-20).
- **Tout-déterministe, sans couche AI** : perte des résumés en français et des titres de synthèse, qui font la lisibilité du dashboard (I §2.3, §3).

## Conséquences

- **On gagne** : un produit complet gateway éteint (II §9.1) ; coût LLM borné par la file et le budget (V-A §24.3) ; comportement reproductible et testable du cœur.
- **On accepte** : des titres et aperçus de repli tant que le LLM est absent ; pas de lecture qualitative des tendances en V1.
- **Preuve de réexamen** : un besoin fonctionnel validé qu'aucun traitement déterministe ne couvre (par exemple l'arbitrage des cas ambigus, reporté en V2) ; un test T-RES-* qui montre une fonction `[core]` dépendante du LLM serait un défaut à corriger, pas une raison de revoir la décision.

## Preuve

Sans objet : cet ADR ne remplace aucune décision précédente.

## Remplace

Aucun.
