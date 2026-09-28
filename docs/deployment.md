# Déploiement

Installation d'un environnement (IX §55.4, §55.5). Au Sprint 1, seule la partie **développement** existe : Compose
local sur le poste, servi en `https://localhost`. La partie **production** (installation initiale de l'hôte, choix du
fournisseur, dépôt restic, monitoring externe, gateway) arrive au Sprint 11 ; le déploiement courant relève du runbook
(IX §56.6, P1).

## Développement

### Prérequis

- **Docker en mode rootless** sur le poste, compte hors du groupe `docker`, et
  `net.ipv4.ip_unprivileged_port_start=80` pour que Caddy publie 80 et 443 (ADR-0021, parade (a) ; mise en place
  #61). Détail et écarts constatés avec la CI : [`testing.md`, « Environnement local par
  `radar-dev` »](testing.md#environnement-local-par-radar-dev).
- **uv** 0.12.18 dans le `PATH` (`[tool.uv] required-version`), pour `scripts/radar-dev test` et `e2e`.
- **Un fichier `.env`** à la racine du dépôt, créé depuis `.env.example` (liste unique des variables : VII §36.7).
  Il n'est **jamais commité** : `.gitignore` l'exclut, et `.dockerignore` le tient hors des images.

```
cp .env.example .env
```

Valeurs à ajuster pour le poste, toutes factices :

| Variable | Valeur de développement |
|---|---|
| `DASHBOARD_URL` | `https://localhost` (aucun port admis, VII §36.7) |
| `DASHBOARD_USER` | un identifiant factice |
| `DASHBOARD_PASSWORD_HASH` | hash bcrypt d'un mot de passe factice, entre guillemets simples (VII §36.7) |
| `HTTP_CONTACT` | laissé à la valeur de `.env.example` |

Le hash se produit par `caddy hash-password` (IX §56.4). Sur le poste, Docker ne s'appelle que par
`scripts/radar-dev`, qui n'a pas de sous-commande pour cela : le propriétaire le produit une fois, hors de l'agent.

### Démarrer

```
scripts/radar-dev up
scripts/radar-dev ps
```

`migrate` se termine en `Exited (0)`, puis `app`, `worker` et `caddy` tournent (VII §36.3). Contrôles :

- `https://localhost/health` répond `{"status":"ok"}` sans identifiants (VII §40.2) ;
- `https://localhost/` et `https://localhost/api/health` demandent les identifiants du `.env` ;
- `scripts/radar-dev health` affiche le détail (voir [`runbook.md`](runbook.md#health)).

Arrêt : `scripts/radar-dev down` (volumes conservés) ; base neuve : `scripts/radar-dev reset`.

### Certificat et avertissement du navigateur

Pour `localhost`, Caddy émet le certificat avec son **autorité interne**, dont la racine vit dans le volume
`caddy_data` (`/data/caddy/pki/authorities/local/root.crt`). L'option `skip_install_trust` du `docker/Caddyfile`
l'empêche d'installer cette racine dans le magasin de confiance du système : la racine du conteneur est en lecture
seule, et Caddy n'écrit que dans `/data`, `/config` et `/tmp` (`architecture.md` §4.3).

Conséquences :

- le navigateur affiche un avertissement de certificat à la première visite de `https://localhost` ; l'accepter
  pour ce seul site sur le poste, ou importer la racine dans le navigateur ;
- en ligne de commande, `curl -k https://localhost/health` ; les tests e2e, eux, vérifient le certificat contre
  cette autorité (voir [`testing.md`, « Réseau et TLS »](testing.md#réseau-et-tls)) ;
- `scripts/radar-dev reset` supprime `caddy_data` : une nouvelle autorité est créée, à accepter de nouveau.

### Pour aller plus loin

- Tests, e2e et CI : [`testing.md`](testing.md).
- Commandes d'exploitation et leur équivalent sur le poste : [`runbook.md`](runbook.md).

## Production

À venir au Sprint 11 (IX §55.4).
