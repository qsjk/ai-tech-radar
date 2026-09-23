# ADR 0015 — Backup restic exécuté par le worker, test de restauration automatisé

| | |
|---|---|
| **Statut** | Accepté |
| **Date** | 2026-09-23 |
| **Décision(s) couverte(s)** | DV-17 ; VII §38, §43.4 · IX §56.4.1, §56.6-P3 · VIII §47.2 (Sprint 11) ; rapport de cadrage §3 (V-05) ; `docs/architecture.md` §4.2 |

## Contexte

La base SQLite est la mémoire accumulée du produit (VII §38). Cibles : RPO 24 h, RTO 1 h, stockage hors VPS pour
0 à 1 €/mois (VII §38.1, §45.1). Le plafond de services interdit un conteneur de backup permanent (I §4.3).

## Décision

Le backup est un **job planifié du worker** : `VACUUM INTO` sur une connexion en lecture seule, contrôle
d'intégrité et de révision de la copie, envoi par **restic** (chiffré, rétention 7/4/3, backend S3-compatible ou SFTP)
hors du VPS. Un test de restauration mensuel automatisé complète l'exercice manuel avant la production (VII §38.2,
§38.4). Un verrou exclusif sépare backup et test de restauration (IX §56.4.1).

## Alternatives écartées

- **Copie brute du fichier `radar.db`** : incohérente pendant les écritures (WAL) ; interdite (VII §38.2).
- **Cron de l'hôte ou conteneur de backup dédié** : un service ou un point d'exploitation de plus ; `SystemState.last_backup` a alors deux écrivains possibles (ADR-0004).
- **Réplication continue (type Litestream)** : réduirait le RPO sous 24 h, mais un composant de plus ; reportée en V2 (VII « Reporté en V2 »).
- **Snapshot du volume par le fournisseur du VPS** : dépend du fournisseur (I §4.3 « Portable ») et n'est pas cohérent au niveau SQLite.

## Conséquences

- **On gagne** : copie cohérente et compactée ; chiffrement et rétention natifs ; échec détecté et alerté (conditions `backup_*`) ; restauration testée chaque mois.
- **On gagne** : fait du Sprint 0 : restic **0.19.1**, binaire `linux_amd64` statique, sha256 contrôlé contre le `SHA256SUMS` signé de la release, exécuté dans l'image retenue (V-05).
- **On accepte** : le worker embarque restic et les identifiants du dépôt ; `VACUUM INTO` retarde le checkpoint WAL pendant sa durée (M3) ; perte de `RESTIC_PASSWORD` = backups inutilisables (copie hors VPS obligatoire).
- **Preuve de réexamen** : M7 hors critère (backup > 10 min ou restauration > 30 min) ou M3 hors critère pendant un `VACUUM INTO` ; un `restore-test` ou un exercice de restauration en échec ; une vulnérabilité sans correctif sur la version épinglée de restic.

## Preuve

Sans objet : cet ADR ne remplace aucune décision précédente.

## Remplace

Aucun.
