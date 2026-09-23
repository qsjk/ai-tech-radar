# ADR 0011 — Authentification du dashboard

| | |
|---|---|
| **Statut** | Proposé |
| **Date** | 2026-09-23 |
| **Décision(s) couverte(s)** | DV-13 ; VI §32 · VII §37, §43.3 · IX §56.6-P4 |

## Contexte

Le produit est mono-utilisateur (I §5). Le dashboard et l'API exposent des données et des actions (régénération,
décisions), sans compte ni rôle à gérer. `/health` doit rester public pour le monitoring externe (VII §41).

## Décision

L'authentification est le **`basic_auth` de Caddy** (hash bcrypt, mot de passe aléatoire de 20 caractères au moins)
sur tout sauf `/health` ; l'app ajoute une protection **anti-CSRF** sur toute requête non `GET` (VI §32.1, §32.2).
`DASHBOARD_TOKEN` n'existe plus.

## Alternatives écartées

- **`basic_auth` plus un jeton applicatif (`DASHBOARD_TOKEN`)** : deux secrets pour un même utilisateur, sans gain de sécurité ; décision retirée (VI §32, VII Réconciliations).
- **Sessions et formulaire de connexion dans l'app** : gestion des sessions, du stockage des mots de passe et des cookies à écrire et à tester dans l'app.
- **Fournisseur d'identité (OAuth, SSO)** : dépendance externe et configuration disproportionnées pour un utilisateur.
- **Aucune authentification, accès restreint par VPN** : le dashboard doit rester joignable par une simple URL HTTPS (VII §37.2).

## Conséquences

- **On gagne** : aucun code d'authentification dans l'app ; l'app ne reçoit aucun secret (VII §36.7) ; rotation par `docker compose up -d caddy` (IX §56.6-P4).
- **On accepte** : pas de déconnexion explicite ni de gestion fine des sessions ; le navigateur retient les identifiants.
- **Preuve de réexamen** : un besoin fonctionnel multi-utilisateur validé ; un incident ou une vulnérabilité sur l'authentification de Caddy ; un test T-SEC-03 ou T-SEC-04 en échec sans correctif.

## Preuve

Sans objet : cet ADR ne remplace aucune décision précédente.

## Remplace

Aucun.
