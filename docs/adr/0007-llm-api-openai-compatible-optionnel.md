# ADR 0007 — Accès LLM par API OpenAI-compatible, gateway hors app, LLM optionnel

| | |
|---|---|
| **Statut** | Accepté |
| **Date** | 2026-09-23 |
| **Décision(s) couverte(s)** | DV-09 ; II §6 · V-A §24.2, §25 · VII §36.2, §45.4 (M6) · VIII décision 21 |

## Contexte

Le produit doit être indépendant des providers : changer de provider ne doit toucher que `LLM_BASE_URL`,
`LLM_API_KEY` et `LLM_MODEL` (I §4.3, T-LLM-19). Le budget vise un LLM à 0 €, donc des quotas gratuits, changeants
et parfois indisponibles. L'enrichissement est best-effort (ADR-0003).

## Décision

Seul le **worker** accède au LLM, par le `LLMClient` dédié, et uniquement par une **API OpenAI-compatible**, derrière
un gateway **hors de l'app** (auto-hébergé en profil Compose, ou externe) ; aucun SDK de provider dans le code (V-A §25).
L'app n'appelle jamais le LLM : elle dépose des jobs (II §8.3) et n'a aucune sortie réseau (réseau `edge` interne,
VII §36.2).
Le LLM est **optionnel** : sans `LLM_BASE_URL`, le produit est complet et tourne à 0 € (V-A §24.2, VIII décision 21).
Le client n'appelle que `LLM_BASE_URL` et ne suit aucune redirection vers un autre hôte (CF-16, T-LLM-20).

## Alternatives écartées

- **SDK d'un provider dans le code** : lie le code à un fournisseur et à son format ; contraire à l'indépendance des providers (I §4.3).
- **Gateway LLM écrit dans le projet** : non-objectif de la Partie I (I §5 : « gateway LLM maison ») ; les gateways open-source existants couvrent le routage et les quotas.
- **LLM obligatoire pour la mise en production** : rendrait le produit dépendant d'un quota gratuit ; la mise en production se fait sans gateway si aucun n'est retenu (VIII décision 21).
- **LLM génératif local** : non-objectif V1 (I §5) : exige GPU ou beaucoup de RAM, hors budget du VPS.

## Conséquences

- **On gagne** : changement de provider par configuration ; panne du gateway absorbée par le disjoncteur et la file (V-A §24.2, §26) ; coût maîtrisé.
- **On accepte** : un composant à choisir et à mesurer au Sprint 6 (ADR-0020, M6) ; les fonctions propres à un provider (outils, formats natifs) restent inaccessibles.
- **Preuve de réexamen** : M6 montre `GET /models` absent ou peu fiable : déclencheur conditionnel du registre, ADR d'adaptation de `LLMClient.health()` (IX §54.3) ; un besoin fonctionnel validé qu'aucune API OpenAI-compatible ne permet d'atteindre ; le choix du gateway lui-même relève de l'ADR-0020 (Sprint 6).

## Preuve

Sans objet : cet ADR ne remplace aucune décision précédente.

## Remplace

Aucun.
