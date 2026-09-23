# ADR 0009 — Topologie Docker Compose sur VPS unique

| | |
|---|---|
| **Statut** | Proposé |
| **Date** | 2026-09-23 |
| **Décision(s) couverte(s)** | DV-11 ; I §4.3 · VII §36.1–§36.4, §36.9 · VIII §49.5 ; `docs/architecture.md` §1, §4 |

## Contexte

Le critère « Simple » limite le produit à 3 ou 4 services permanents et à un démarrage en une commande ; le
critère « Portable » veut qu'on change de VPS par une restauration, le `.env` et `docker compose up -d` (I §4.3). Le
budget exclut tout cluster (I §4.3 « Low-cost »).

## Décision

Le produit tourne sous **Docker Compose sur un VPS unique** : trois services permanents `caddy`, `app`, `worker`,
un one-shot `migrate`, et `gateway` en profil optionnel (VII §36.2). Une image backend, partagée par `migrate`, `app`
et `worker`, et une image Caddy qui embarque le build Vite, toutes deux taggées par le sha Git (VII décision 2).

## Alternatives écartées

- **Kubernetes, y compris k3s** : orchestration, stockage et réseau à exploiter pour un seul hôte et un seul utilisateur ; interdit par anticipation (IX §53.3).
- **Plusieurs VPS ou services gérés (PaaS, base managée)** : coût récurrent au-delà de la cible et dépendance à un fournisseur (I §4.3).
- **Processus systemd sur l'hôte, sans conteneurs** : environnement moins reproductible entre développement, CI et production ; isolation et durcissement (ADR-0010) plus coûteux à obtenir.
- **Une image par service** : trois images à construire, à tester et à garder cohérentes pour un même code.

## Conséquences

- **On gagne** : démarrage local en une commande ; même image en CI (e2e), en pré-production et en production ; rollback par sha (VIII §49.5).
- **On accepte** : un seul hôte : sa panne arrête le produit, couverte par le backup hors VPS (ADR-0015) et le monitoring externe (VII §41) ; courte coupure à chaque déploiement (VII §36.9).
- **Preuve de réexamen** : M1 ou M8 hors critère sur la plus grande taille de VPS envisagée (VII §45.4) ; un besoin validé de disponibilité au-delà d'un hôte ; tout service permanent supplémentaire exige une preuve (IX §53.3).

## Preuve

Sans objet : cet ADR ne remplace aucune décision précédente.

## Remplace

Aucun.
