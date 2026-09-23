# ADR 0010 — Exposition et cloisonnement : Caddy, segmentation réseau, conteneurs durcis, anti-SSRF

| | |
|---|---|
| **Statut** | Accepté |
| **Date** | 2026-09-23 |
| **Décision(s) couverte(s)** | DV-12 ; VII §36.2, §36.5, §43.1–§43.3 · IV §21.1 · V-A §25.2 ; `docs/architecture.md` §4, P-02, P-10 |

## Contexte

Le produit est exposé sur Internet et récupère des URLs issues de flux tiers : un article malveillant peut viser
une adresse interne (IV §21.1). Un seul exploitant, sans équipe de sécurité : le cloisonnement doit être par défaut,
pas par vigilance (VII §43).

## Décision

Caddy est **le seul point d'entrée** et le seul service qui publie des ports. Le réseau est segmenté : `app` sans
sortie Internet, `worker` sans accès à `app`, `migrate` sans réseau (VII §36.2). `caddy`, `app`, `worker` et
`migrate` sont non-root, `cap_drop: ALL` sans capacité ajoutée, `no-new-privileges`, racine en lecture seule avec
`/tmp` en tmpfs (VII §36.5, §43.2 ; P-10). Le durcissement du `gateway` optionnel est fixé au Sprint 6, avec son choix
(A-06 de `docs/architecture.md`). Le `HttpClient` refuse toute destination privée, locale ou non routable,
après résolution DNS et à chaque redirection, **sans exception** (IV §21.1, CF-16).

## Alternatives écartées

- **Publier le port de `app` ou un port de débogage** : contourne le pare-feu de l'hôte (VII §43.1) et l'authentification de Caddy.
- **Un seul réseau Docker pour tous les services** : `worker`, qui suit des URLs tierces, pourrait joindre `app` : cible d'SSRF interne.
- **`caddy` en root avec `NET_BIND_SERVICE`** : inutile : Docker (≥ 20.10) pose `net.ipv4.ip_unprivileged_port_start=0` dans l'espace réseau du conteneur, un processus non-root lie 80 et 443 sans capacité (P-10).
- **Exceptions anti-SSRF pour `LLM_BASE_URL` et le dépôt restic** : sans objet : le `LLMClient` a son propre client, à destination unique, et restic est un binaire externe (V-A §25.2, CF-16).

## Conséquences

- **On gagne** : une compromission de l'app ne donne ni sortie Internet ni écriture hors `/data` ; aucune adresse interne atteignable par un flux tiers.
- **On accepte** : chaque bibliothèque doit fonctionner sur une racine en lecture seule (caches vers `/tmp` ou l'image, R-04) ; le durcissement de `caddy` est à vérifier au Sprint 1 sur l'image épinglée (`architecture.md` §4.3) ; il n'a pas encore d'identifiant de test (A-08) ; le `gateway` n'est pas couvert par ce durcissement tant que le Sprint 6
ne l'a pas fixé (A-06).
- **Preuve de réexamen** : un test T-SEC-09 qui montre qu'une bibliothèque nécessaire ne peut pas tourner en lecture seule, sans parade ; une vulnérabilité ou un incident sur la segmentation ; un besoin validé qui exige une sortie réseau de `app`.

## Preuve

Sans objet : cet ADR ne remplace aucune décision précédente.

## Remplace

Aucun.
