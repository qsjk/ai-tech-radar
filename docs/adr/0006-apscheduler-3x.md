# ADR 0006 — APScheduler 3.x

| | |
|---|---|
| **Statut** | Accepté |
| **Date** | 2026-09-23 |
| **Décision(s) couverte(s)** | DV-08 ; VII §35 · II §8.4 · IV §21.6 · VIII §50.1 |

## Contexte

Le worker planifie les collectes par source, les ticks (clustering, purge, `ops.tick`), les backups et les digests
(IV §21.6, VII §38). Il faut la coalescence des misfires au redémarrage (II §8.4) et un scheduler asyncio, dans le
processus.

## Décision

Le worker utilise **APScheduler 3.x** (`AsyncIOScheduler`). La branche 4.x est exclue tant qu'elle n'est pas
stable (VII §35). Les fonctions de tick lisent l'heure dans la `Clock` et sont testées sans le scheduler
(VIII §50.1, ADR-0016).

## Alternatives écartées

- **APScheduler 4.x** : en pré-version (4.0.0a6 lors de la vérification V-07), API différente.
- **cron de l'hôte ou conteneur dédié** : un service ou un point d'exploitation de plus, hors de la supervision fail-fast du worker (VII §36.6).
- **Planificateur maison sur asyncio** : coalescence, jitter et `max_instances` à réécrire et à tester.

## Conséquences

- **On gagne** : fait du Sprint 0 : APScheduler 3.11.3 déclenche un job asynchrone sur Python 3.12, sans avertissement de dépréciation (rapport de cadrage §3, V-07) ; coalescence et `max_instances=1` disponibles.
- **On accepte** : une bibliothèque en fin de branche majeure ; épinglage en `<4` obligatoire.
- **Preuve de réexamen** : **APScheduler 4.x stable, ou 3.x sans correctif de sécurité** : déclencheur conditionnel du registre, ADR de migration qui remplace celui-ci (IX §54.3) ; une vulnérabilité sans correctif sur la version épinglée ; un test T-OPS-16 qui montre un défaut de coalescence.

## Preuve

Sans objet : cet ADR ne remplace aucune décision précédente.

## Remplace

Aucun.
