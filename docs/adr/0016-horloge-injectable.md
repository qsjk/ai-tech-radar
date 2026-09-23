# ADR 0016 — Horloge injectable, temps jamais lu en SQL

| | |
|---|---|
| **Statut** | Accepté |
| **Date** | 2026-09-23 |
| **Décision(s) couverte(s)** | DV-18 ; VIII décision 7, §49.3, §50.1 · III §10.6 · `docs/architecture.md` §5.2 ; décision I-04 |

## Contexte

Le produit est piloté par le temps : TTL des jobs, backoff, warm-up de l'émergence, rétentions, heartbeat, digests.
Sans maîtrise du temps, ces règles ne se testent qu'en attendant réellement, ou pas du tout (VIII décision 7).

## Décision

Une abstraction **`Clock`** unique (`now()` UTC avec fuseau, `monotonic()`, `sleep()`) est injectée partout.
Aucun `datetime.now()` ni `time.time()` dans le code métier, aucune expression temporelle SQL, ni dans les requêtes ni
en valeur par défaut de colonne (III §10.6, VIII §50.1). La production utilise `SystemClock`, les tests une horloge
manuelle ; les fonctions de tick du scheduler sont appelées directement dans les tests.

## Alternatives écartées

- **Bibliothèque qui fige le temps globalement (type freezegun)** : agit par patch global ; ne couvre ni les instants calculés en SQL ni l'event-loop asyncio.
- **`CURRENT_TIMESTAMP` en SQL et valeurs par défaut temporelles** : l'instant échapperait aux tests et son format diffère de l'ISO-8601 de `UTCDateTime` (I-04).
- **Tests avec `sleep` réels** : lents et instables ; interdits dans les tests unitaires et d'intégration (VIII §49.3).

## Conséquences

- **On gagne** : TTL, warm-ups, rétentions et backoffs testables en quelques millisecondes ; tests déterministes.
- **On accepte** : une discipline de code : tout instant passe par un paramètre ; APScheduler garde son horloge murale pour déclencher, seuls ses ticks sont testés.
- **Preuve de réexamen** : un test qui montre un comportement temporel impossible à exprimer avec la `Clock` injectée ; aucun déclencheur mesuré n'est attendu pour cette décision.

## Preuve

Sans objet : cet ADR ne remplace aucune décision précédente.

## Remplace

Aucun.
