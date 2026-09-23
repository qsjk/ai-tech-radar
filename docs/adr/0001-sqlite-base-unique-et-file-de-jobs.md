# ADR 0001 — SQLite comme base unique et file de jobs en base

| | |
|---|---|
| **Statut** | Proposé |
| **Date** | 2026-09-23 |
| **Décision(s) couverte(s)** | DV-01, DV-02 ; II §8.2, §8.6 · III §10 · V-A §23 · IX §53.3 ; `docs/database.md` §2, §5 |

## Contexte

Le produit est mono-utilisateur, tourne sur un seul VPS pour 12 €/mois au plus et doit rester portable par une
simple copie de sauvegarde (I §4.3, §5). Le volume visé reste sous 10 000 articles par jour (VII §45.2). Deux processus,
`app` et `worker`, écrivent dans la même base (II §8.3) ; les tâches LLM doivent survivre à un redémarrage et à une
panne du gateway (V-A §23, §26).

## Décision

SQLite, en WAL, est l'unique base de données V1 : un fichier sur un volume Docker nommé local, partagé par `app`,
`worker` et `migrate` (III §10). La file des jobs AI est la table `AIJob`, avec un claim atomique par
`UPDATE … RETURNING` (V-A §23.4) ; aucun broker de messages.

## Alternatives écartées

- **PostgreSQL** : un service permanent de plus à exploiter, sauvegarder et superviser, pour un seul utilisateur et un débit que SQLite tient ; interdit par anticipation sans preuve (IX §53.3).
- **Redis, Kafka ou tout broker pour la file** : un second stockage à rendre durable et cohérent avec la base ; la file en base partage la transaction du résultat, ce qui rend le rejeu sans effet de bord (III §11.10).
- **SQLite sans WAL (journal de rollback)** : les lectures de l'app bloqueraient pendant les écritures du worker.
- **Fichier SQLite sur un système de fichiers réseau** : le WAL repose sur une mémoire partagée (`-shm`) qui exige le même hôte (III §10.4).

## Conséquences

- **On gagne** : un seul fichier à sauvegarder (`VACUUM INTO`, ADR-0015) et à déplacer ; aucune dépendance réseau pour la base ; file et résultats validés dans la même transaction.
- **On gagne** : faits du Sprint 0 (rapport de cadrage §3) : SQLite 3.46.1 dans l'image retenue, FTS5 et JSON1 fonctionnels (V-02) ; WAL effectif sur volume nommé, deux conteneurs en écriture et lecture concurrentes pendant 75 s sans erreur (V-04) ; `BEGIN IMMEDIATE` pris dès le `BEGIN` avec SQLAlchemy 2 async et aiosqlite, par les écouteurs `connect` et `begin` (V-03).
- **On accepte** : un seul écrivain à la fois : transactions courtes et lots bornés obligatoires (II §8.6, III §10.7) ; pas de réplication continue en V1 (RPO 24 h, VII §38.1) ; un seul hôte.
- **On accepte** : une discipline de migration propre à SQLite : mode batch, clés étrangères coupées pendant la migration, contrôle `foreign_key_check` (III §10.5, `database.md` §5).
- **Preuve de réexamen** : la mesure M4 (plus longue transaction d'écriture du worker > 500 ms) ou M3 (`-wal` au-delà du seuil) hors critère de façon durable (VII §45.4) ; un test T-DB-04 qui montre des échecs « database is locked » malgré `BEGIN IMMEDIATE` ; un incident de corruption ; un besoin fonctionnel multi-utilisateur ou multi-hôte validé.

## Preuve

Sans objet : cet ADR ne remplace aucune décision précédente.

## Remplace

Aucun.
