# Runbook

Point d'entrée « que faire quand… » (IX §55.5, §56). Le contrat fait foi dans **IX §56** : ce document ne le recopie
pas, il donne l'usage des commandes livrées et leur équivalent sur le poste de développement.

- **Périmètre** : tout ce qui s'exécute sur le VPS ou agit sur l'instance (IX §56.1). Installation initiale :
  [`deployment.md`](deployment.md) ; développement, tests et CI : [`testing.md`](testing.md).
- **Conventions** (projet Compose `radar`, `exec` ou `run --rm --no-deps`, `.env`, interdits) : IX §56.2.
- **Sur le poste de développement**, Docker ne s'appelle que par `scripts/radar-dev` (projet `radar-dev`, ADR-0021) ;
  voir [`testing.md`, « Environnement local par `radar-dev` »](testing.md#environnement-local-par-radar-dev).

Créé au Sprint 1 avec `validate-config`, `health` et les commandes de base (IX §55.4) ; complété à chaque nouvelle
commande ou procédure (VIII §51.1, point 9).

## Contrat des commandes `app.cli`

IX §56.3 : codes de sortie `0` succès, `1` échec de l'opération, `2` usage ou configuration invalide ; résultat sur
stdout, logs JSON sur stderr ; secrets jamais affichés. Inventaire et mode d'exécution : IX §56.4.

## `validate-config`

- **Quand** : avant un déploiement qui touche `config/`, ou quand le worker refuse de démarrer sur une configuration
  invalide (IX §56.4, P10 à venir).
- **Production** : `docker compose run --rm --no-deps worker python -m app.cli validate-config` (IX §56.4). Ne lit
  pas la base (IX §56.3).
- **Développement** : la commande ne demande ni Docker ni base, elle se lance sur le poste :
  `uv run python -m app.cli validate-config` (dossier `config/` par défaut, `--config-dir` pour un autre).
- **Sortie** : `valid configuration (config): N source(s), N topic(s), N entity(ies)`, ou `invalid configuration
  (config): N problem(s)` suivi d'une ligne par problème, avec fichier, entrée (clé) et champ (IV §16.5).
- **Codes** : `0` configuration valide · `2` configuration invalide, fichier obligatoire absent compris (P-04) ·
  `1` lecture impossible du dossier.
- **Si `2`** : corriger le fichier cité, relancer, puis déployer (P1 à venir).

## `health`

- **Quand** : détail de santé en SSH, après un déploiement ou une alerte (IX §56.4). La sonde publique `/health` ne
  donne que le statut (VII §40.2).
- **Production** : `docker compose exec app python -m app.cli health` (IX §56.5), ou dans `worker`.
- **Développement** : `scripts/radar-dev health`.
- **Sortie** : le détail de VII §40.3 en JSON, réduit aux composants du Sprint 1 (`database` avec révision, taille,
  WAL et `journal_size_limit` ; `worker` avec l'âge du heartbeat), et `conditions`. Le composant `app` n'y figure pas :
  ses valeurs appartiennent au processus uvicorn.
- **Codes** : `0` statut `ok` ou `degraded` · `1` statut `down`, prérequis SQLite absents ou révision différente de
  `head` · `2` configuration invalide (`AppSettings`, `pipeline.yaml`).
- **Si `down`** : `worker.status = down` → logs du worker (commandes de base) ; `database.status = down` → base
  inaccessible, voir P3 (à venir). Sémantique de `down` : VII §40.2.

## Commandes de base

Commandes de production : IX §56.5. Équivalents sur le poste, projet `radar-dev` :

| Besoin (IX §56.5) | Production | Développement |
|---|---|---|
| État des services | `docker compose ps` | `scripts/radar-dev ps` |
| Logs | `docker compose logs -f --since 1h <service>` | `scripts/radar-dev logs <service>` (tout l'historique, sans suivi) |
| Santé publique | `curl -s -o /dev/null -w '%{http_code}' https://<domaine>/health` | `curl -s -o /dev/null -w '%{http_code}' https://localhost/health` (sans Docker ; certificat de l'autorité interne : ajouter `-k`, voir [`deployment.md`](deployment.md#certificat-et-avertissement-du-navigateur)) |
| Santé détaillée | `docker compose exec app python -m app.cli health` | `scripts/radar-dev health` |
| Relancer un service, sans changement de `.env` | `docker compose restart <service>` | pas d'équivalent ; `scripts/radar-dev up` recrée ce qui a changé |
| Appliquer un changement de `.env` | `docker compose up -d <service>` | `scripts/radar-dev up` |
| Révision du schéma | `docker compose run --rm migrate alembic current` | pas d'équivalent ; `scripts/radar-dev health` affiche `schema_revision` |
| Repartir d'une base vide | — (jamais en production) | `scripts/radar-dev reset` |

## Procédures

Contrat : IX §56.6. Chacune sera rédigée ici au sprint qui livre ce qu'elle utilise, avec **quand**, **prérequis**,
**étapes**, **vérification** et **retour arrière** (IX §56.1).

| Procédure | État |
|---|---|
| P1 — Déploiement | à venir (`scripts/deploy.sh`, Sprint 11) |
| P2 — Rollback | à venir (Sprint 11) |
| P3 — Restauration | à venir (backup, Sprint 11 ; détail dans `backup-restore.md`) |
| P4 — Mot de passe du dashboard | à venir |
| P5 — Rotation des secrets | à venir |
| P6 — Pause du monitoring externe | à venir (Sprint 11) |
| P7 — Nettoyage des images Docker | à venir |
| P8 — `VACUUM` manuel | à venir (`app.cli vacuum`) |
| P9 — Reboot planifié de l'hôte | à venir |
| P10 — Modifier la configuration | à venir ; en attendant, `validate-config` ci-dessus |
| P11 — Répondre à une alerte | à venir (alertes, Sprint 10 ; conditions dans `monitoring.md`) |
