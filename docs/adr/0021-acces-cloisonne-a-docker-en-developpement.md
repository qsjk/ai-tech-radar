# ADR 0021 — Accès cloisonné de Claude Code à Docker en développement

| | |
|---|---|
| **Statut** | Proposé |
| **Date** | 2026-09-23 |
| **Décision(s) couverte(s)** | aucune `DV-nn` : décision structurante (IX §53.1) ; E22 du rapport de cadrage ; VIII §46.1 (`scripts/radar-dev`) ; IX §55.3 ; VII §36.7 (`DASHBOARD_URL`) ; `docs/architecture.md` §6 (P-03), §7 (A-04) |

## Contexte

Claude Code a besoin de Docker sur le poste de développement à chaque sprint : Compose local, tests, e2e (VIII §47.2,
§49.2). Or l'accès au démon Docker classique, par le groupe `docker`, équivaut à un accès root pour **tout** programme
lancé sous ce compte, Claude Code compris : il suffit d'un conteneur qui monte `/` de l'hôte. Pour T0.3, le compte de
développement a été ajouté temporairement à ce groupe (#61).

Le poste est un Ubuntu 24.04.5 x86_64, avec un client `docker-ce` 29.8.1 et un démon installé par snap, 29.6.1
(rapport de cadrage §3.A, Q-01). Le produit est mono-utilisateur et développé par un seul propriétaire (I §5) : la
protection doit tenir sans vigilance quotidienne. La démarche retenue pour l'outillage est progressive : V0, un script
`scripts/radar-dev` à sous-commandes fixes ; V1, un skill ; V2, un serveur MCP, conditionnel (E22). **Ce script est un
point d'entrée prévisible, pas une barrière** : l'isolation doit venir d'ailleurs.

La CI (GitHub Actions) et le VPS de pré-production et de production utilisent Docker en mode root ; ils ne sont pas
concernés par cet ADR.

## Décision

**Option A** : sur le poste de développement, Docker tourne en **mode rootless**. Le démon s'exécute sous le compte de
développement ; un conteneur ne donne donc jamais plus de droits que ce compte. Le compte est retiré du groupe
`docker`. Claude Code n'utilise Docker que par `scripts/radar-dev` (VIII §46.1, IX §55.3) ; ses permissions refusent
l'appel direct à `docker`.

## Alternatives écartées

- **B. Groupe `docker` et permissions de Claude Code** : les permissions ne sont qu'un filtre de commandes, pas un
  cloisonnement. Une commande autorisée qui lance un conteneur, ou un fichier Compose modifié puis lancé, suffit à
  obtenir un accès root à l'hôte.
- **C. Script exécuté en root via `sudoers`** : Claude Code peut modifier le `docker-compose.yml` que ce script lance
  en root, et obtenir ainsi un accès root. Figer le fichier hors du dépôt casserait le développement du Compose
  lui-même.
- **Machine virtuelle ou poste dédié au développement** : isolation forte, mais coût et maintenance d'un second
  environnement pour un seul développeur ; non retenue en V1.

## Conséquences

- **On gagne** : un accès à Docker qui ne vaut jamais plus que les droits du compte de développement, quelles que
  soient les commandes lancées ; le même `docker compose` qu'en production, sans fichier ni script privilégié.
- **On accepte** les écarts du mode rootless relevés par P-03 (`architecture.md` §6) :
  - **Ports 80 et 443 de Caddy (A-04)** : un démon rootless ne publie pas un port de l'hôte inférieur à
    `net.ipv4.ip_unprivileged_port_start` (1024 par défaut). Deux parades :
    - **(a), recommandée** : abaisser `net.ipv4.ip_unprivileged_port_start` à 80 sur le poste de développement,
      par un réglage sysctl persistant, posé une fois par le propriétaire. `https://localhost` reste identique à la
      production, et `DASHBOARD_URL` continue de n'admettre aucun port (VII §36.7, T-CFG-07 inchangé). Ce réglage
      vaut pour **tout le poste** : n'importe quel processus non privilégié peut alors écouter sur les ports 80 à
      1023. C'est acceptable sur un poste de développement mono-utilisateur. L'alternative ciblée, documentée par
      Docker, donne la capacité `cap_net_bind_service` au seul binaire `rootlesskit` ; elle est à reposer après chaque
      mise à jour du paquet qui fournit ce binaire. La recommandation reste le réglage sysctl ;
    - **(b)** : publier 8080 et 8443 en développement, et admettre un port dans `DASHBOARD_URL` pour `localhost`
      seulement ; la validation de VII §36.7 et T-CFG-07 changent, et l'URL de développement diffère de la production.
  - **uid des volumes** : l'uid 10001 des conteneurs correspond à un sous-uid de l'hôte. Sans effet vu des
    conteneurs ni sur un volume nommé ; seul l'accès direct aux fichiers du volume depuis l'hôte change. `/data`
    reste un volume nommé, jamais un bind mount (IX décision 26).
  - **Délégation cgroup** : `mem_limit` (à partir du Sprint 4, P-07) exige que systemd délègue le contrôleur mémoire
    de cgroup v2 au compte de développement ; sans elle, la limite est refusée ou ignorée.
  - **Réseau** : pile réseau en espace utilisateur (slirp4netns ou pasta), plus lente ; les réseaux `internal` et
    `network_mode: none` restent disponibles.
  - **Écart avec la CI et la production**, qui restent en Docker root : un comportement propre au mode rootless ne
    se voit qu'en local, et inversement. L'e2e de référence reste celui de la CI (VIII §49.2, étape 6) ; les écarts
    constatés sont consignés dans `testing.md` (#61).
  - **Prérequis** (#61) : une seule installation de Docker (`docker-ce`, démon snap retiré), mode rootless installé,
    compte retiré du groupe `docker`, avant le premier Compose du Sprint 1.
- **Preuve de réexamen** : un test ou un incident qui montre qu'une fonction nécessaire au développement ne peut pas
  tourner en rootless, sans parade (par exemple l'e2e du Sprint 1 ou `mem_limit` au Sprint 4) ; une vulnérabilité sans
  correctif dans les composants rootless (rootlesskit, slirp4netns ou pasta) ; un besoin fonctionnel validé qui exige
  un autre mode de développement.

## Preuve

Sans objet : cet ADR ne remplace aucune décision précédente.

## Remplace

Aucun.
