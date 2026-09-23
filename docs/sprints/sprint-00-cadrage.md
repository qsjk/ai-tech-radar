# Sprint 0 — Rapport de cadrage

> Tâche T0.2 (#5), rédigé le 2026-09-23 sur la spec réconciliée par T0.1a (#57) et T0.1b (#58).
> Structure imposée par la Partie IX §57.5 : conflits · décisions manquantes · vérifications · risques · questions ouvertes.
> Ce rapport **ne tranche rien** (IX décision 4, §53.1) : chaque point porte une recommandation et une ligne
> « Décision du propriétaire », à remplir par le propriétaire du projet. Les identifiants sont stables : un point
> tranché ou abandonné garde son numéro.

Références : `docs/spec/partie-<N>.md` est abrégé en « <N> » (par exemple « VII §36.7 » pour la Partie VII, §36.7).

---

## 1. Conflits de spec

Positions en présence, sans arbitrage. Origine : listes A, B et C de la PR #58 (CF-01 à CF-19), puis lecture
complète de la spec réconciliée (CF-20 à CF-25).

### 1.A Impacts non reportés dans la Partie VII

La Partie VII n'a pas été modifiée en T0.1b, par décision du propriétaire (voir E9 et E11). Les impacts ci-dessous
restent donc en attente : la partie d'origine décrit la cible, la Partie VII décrit encore l'état antérieur.

#### CF-01 — `.env.example` : `APP_ENV=test` et `HTTP_TEST_ALLOW_HOSTS`

- **VIII décision 23, §50.1, T-CFG-09 ; IV §21.1** : `APP_ENV` accepte la valeur `test` ; nouvelle variable `HTTP_TEST_ALLOW_HOSTS`, lue seulement si `APP_ENV=test`, refusée en production.
- **VII §36.7** : `.env.example` ne connaît que `production` et `development` pour `APP_ENV`, et n'a pas de section « Réservé aux tests ».

Décision du propriétaire : —

#### CF-02 — Séquence de déploiement exécutée par `deploy.sh`

- **VIII §49.5** : la séquence est exécutée par `scripts/deploy.sh`, après le contrôle CI ; `backup-now` passe par `docker compose exec worker`, code de sortie vérifié.
- **VII §36.9** : séquence manuelle (`git pull → build → backup-now → stop → up -d`), sans verrou CI ni script.

Décision du propriétaire : —

#### CF-03 — Racine en lecture seule : Sprint 1 ou Sprint 11

- **VIII décision 4, §47.3** : racine en lecture seule active dès le Sprint 1 ; le Sprint 11 ne fait que confirmer le cas de restic.
- **VII §36.5** (dernier point) : « Le système de fichiers racine en lecture seule est à valider au Sprint 11 (onnxruntime, lingua, restic). »

Décision du propriétaire : —

#### CF-04 — Restauration outillée par `scripts/restore.sh`

- **VIII décision 24, §46.1, T-BKP-08, T-RES-07** : la procédure de restauration est outillée par `scripts/restore.sh`.
- **VII §38.5** : procédure décrite en commandes manuelles, sans script.

Décision du propriétaire : —

#### CF-05 — Jeton GitHub de `deploy.sh`

- **VIII §49.5** (« Jeton GitHub ») et **IX §56.6-P5** : si le dépôt est privé, jeton *fine-grained* en lecture seule, hors du `.env` applicatif, jamais transmis à un conteneur.
- **VII §43.4** : « Uniquement dans `.env` » ; ce jeton n'y est pas mentionné.

Décision du propriétaire : —

#### CF-06 — Profils de charge dans le projet `radar-load`

- **VIII décision 20, §47.4, §50.7** : profils synthétiques joués dans un projet Compose distinct (`-p radar-load`), avec son propre volume ; mesures de référence en pré-production.
- **VII §45.3–§45.4** : profils et mesures décrits sans projet distinct ni moment de référence.

Décision du propriétaire : —

#### CF-07 — Inventaire des commandes : `vacuum`, `snapshot_id`, mode d'exécution

- **IX §56.3, §56.4, décisions 19 et 21** : nouvelle commande `vacuum` ; `backup-now` affiche le `snapshot_id` ; `validate-config` s'exécute en `run --rm --no-deps worker` ; contrat commun des commandes (codes `0` / `1` / `2`, stdout / stderr).
- **VII §36.8** : pas de `vacuum` ; colonne « Où » de `validate-config` = « worker, CI » ; aucun renvoi au contrat commun.

Décision du propriétaire : —

#### CF-08 — Rollback à travers une migration

- **IX décision 18, §56.6-P2 ; VIII §49.5** : `deploy.sh` détecte une migration à défaire et refuse ; procédure *downgrade* ou restauration.
- **VII §36.9** (« Rollback ») : « redéployer le tag précédent. Si une migration irréversible est passée, restaurer le backup pris avant le déploiement. »

Décision du propriétaire : —

#### CF-09 — Verrou de backup `/data/backup/.lock`

- **IX décision 20, §56.4.1 ; VIII T-BKP-11** : verrou exclusif partagé par les jobs `backup`, `restore_test` et les commandes `backup-now`, `restore-test`.
- **VII §38.2, §38.4** : aucun verrou ; un backup et un test de restauration peuvent se chevaucher.

Décision du propriétaire : —

#### CF-10 — Pas-à-pas de la restauration : runbook ou `backup-restore.md`

- **IX §55.5, réconciliation « VII §38.5 »** : le pas-à-pas vit dans `docs/backup-restore.md` ; le runbook résume et renvoie.
- **VII §38.5** (dernière ligne) : « Le détail pas à pas va au runbook (`docs/backup-restore.md`). »

Décision du propriétaire : —

#### CF-11 — Application d'un changement de `.env` : `restart` ou `up -d`

- **IX décision 22, §56.2, §56.6-P4, P5** : toute modification du `.env` s'applique par `docker compose up -d <service>`, jamais par `restart`.
- **VII §43.4** (« Rotation ») : « redémarrage de `caddy` » et « redémarrage du `worker` ». La même partie écrit pourtant `docker compose up -d caddy` en **VII §36.8** (ligne `caddy hash-password`). Voir aussi CF-17 pour la Partie VI.

Décision du propriétaire : —

#### CF-12 — `VACUUM` manuel

- **IX décision 21, §56.4.2, §56.6-P8** : `VACUUM` manuel par `app.cli vacuum`, worker arrêté, fichiers temporaires de SQLite sur `/data`, jamais dans le tmpfs.
- **VII §44.2** : « Un `VACUUM` manuel, worker arrêté, reste possible via le runbook », sans commande ni emplacement des fichiers temporaires.

Décision du propriétaire : —

### 1.B Impacts sans objet

#### CF-13 — « Décisions prises dans cette V0.3 » dans `SPEC.md`

- **Impact IX → `SPEC.md`** (section d'impacts retirée par #58) : « Supprimer "Décisions prises dans cette V0.3 (à valider)" ».
- **Préambule V0.4** (ancien `docs/spec/SPEC.md`, avant #58) : ce bloc n'existait pas. Rien à supprimer ; `SPEC.md` suit IX §55.2.

Décision du propriétaire : —

#### CF-14 — Décision 5 de la V0.3 (« token unique + basic_auth »)

- **Impact VI → `SPEC.md`** : remplacer la décision 5 par « basic_auth Caddy seul, anti-CSRF côté app ».
- **Préambule V0.4** : la décision 5 n'y figure pas. Le point est couvert par DV-13 (**IX §53.2**) et **VI §32**.

Décision du propriétaire : —

### 1.C Contradictions entre parties

#### CF-15 — Compteurs d'Event : incrémentés ou recalculés

- **II décision 3** : compteur de sources distinctes « mis à jour à chaque rattachement » ; **II §7.2** (tableau, ligne « Hotness ») : « incrémenté à chaque rattachement » ; **II §7.3** : `distinct_source_count++`.
- **V-B décision 9, §28.9** : compteurs « toujours recalculés depuis les membres », « jamais incrémentés », dans la transaction de rattachement.
- **III §11.3** (invariant) : compatible avec les deux lectures (« mis à jour dans la même transaction », « un contrôle de cohérence peut le recalculer »).

Décision du propriétaire : —

#### CF-16 — Exceptions de la garde anti-SSRF

- **IV §21.1, VII §43.3, VIII T-HTTP-08** : la garde du `HttpClient` admet deux exceptions, `LLM_BASE_URL` et le dépôt restic.
- **V-A §25.2** : le `LLMClient` utilise un **client HTTP dédié**, distinct du `HttpClient` ; **VII §38.2** : le backup appelle le binaire `restic`, qui ne passe pas par le `HttpClient`.
- Deux lectures possibles : les exceptions sont sans objet dans le `HttpClient`, ou la garde doit aussi couvrir le client LLM (avec l'exception `LLM_BASE_URL`).

Décision du propriétaire : —

#### CF-17 — Rotation du mot de passe du dashboard

- **VI §32.1** (« Rotation ») : « nouveau hash dans l'environnement, redémarrage de `caddy` ».
- **IX décision 22, §56.6-P4** : `docker compose up -d caddy` ; `restart` ne relit pas l'environnement.

Décision du propriétaire : —

#### CF-18 — Cycle « Create topic » : slug et mots-clés

- **V-A §24.6** : slug dérivé de `llm_label`, à défaut `label` ; mots-clés = `suggested_keywords` ∪ {`key`}.
- **V-B §30.8** (T1) : `name` = `llm_label` ou `label`, slug dérivé de `name`, suffixe `-2`, `-3` en collision ; mots-clés = `suggested_keywords` ∪ {terme de base}, où le terme de base vaut `key` pour un `ngram` et `canonical_name` (`owner/repo`) pour un `repository`, dont la `key` est `repo:{canonical_name}` (**V-B §30.2**).
- Pour un `repository`, V-A ajouterait `repo:owner/repo` comme mot-clé, V-B `owner/repo`. V-B annonce « Complète V-A §24.6 » ; seul le texte d'entrée du backfill était explicitement corrigé.

Décision du propriétaire : —

#### CF-19 — Alias d'entités : V1 ou V2

- **IV §16.4, V-A §27.2** : `entities.yaml` porte des `aliases` matchés dès la V1 ; les entités LLM sont canonicalisées par ce matcher d'alias.
- **III** (« Reporté en V2 ») : « Alias et fusion d'entités (ex. « Claude Code » / « claude-code » / « CC ») au-delà du `canonical_name` ».
- **III §11.6** (note ajoutée par #58) : les alias vivent dans `entities.yaml`, pas en base. La frontière V1 / V2 (alias déclarés à la main contre fusion en base) n'est écrite nulle part.

Décision du propriétaire : —

### 1.D Conflits relevés à la lecture

#### CF-20 — Rôle de l'AI dans le regroupement et les tendances

- **I §3** (fonctions 4 et 7) : regroupement **[mixte]** avec « confirmation des cas ambigus **[AI]** » ; tendances avec « lecture qualitative **[AI]** » ; fonction 5 (topics, entités, événements) étiquetée **[AI]**.
- **II décision 2** : `resolve_event` « arbitre les cas ambigus » ; **II §6** (couche enrichissement) : « confirmation des événements ambigus, lecture qualitative des tendances ».
- **V-A décisions 4 et 7**, « Reporté en V2 » : arbitrage des cas ambigus et `analyze_trend` reportés en V2 ; **III décision 1, IV §20.4** : topics et entités ont aussi une origine déterministe (`keyword`).

Décision du propriétaire : —

#### CF-21 — Panne du moteur d'embeddings : « jobs » d'embedding

- **II §9.1** (ligne « Moteur d'embeddings indisponible ») : détection par « échec des jobs d'embedding », reprise par « jobs d'embedding en `retry` ».
- **IV décision 21, §14.3 ; V-A §24.4** : les embeddings n'ont **pas** d'`AIJob` : file dérivée, backoff du tick, `SystemState.embeddings = down`, ligne `Embedding` en échec après `embeddings.max_failures`.

Décision du propriétaire : —

#### CF-22 — Lecture de `pipeline.yaml` par l'app

- **IV §16.1** : les fichiers `config/` sont chargés par le worker ; « L'app ne charge pas ces fichiers. »
- L'app a pourtant besoin de réglages qui y vivent : `ops.heartbeat_stale_after` pour `/health` (**VII §40.2**, calcul par l'app, **VII §39.7**) ; `emerging.warmup` pour l'Overview et le bandeau (**VI §31.3, §31.10**) ; `llm.daily_request_budget` et `llm.app_reserve` pour `/api/health` (**VII §40.3**). **VII §40.1** impose en plus le même seuil de heartbeat à `/health`, `/api/health` et `/api/status`.

Décision du propriétaire : — (options en E17)

#### CF-23 — Valeur attendue quand le LLM n'est pas configuré

- **VIII §47.2** (Sprint 6, acceptation) : « `llm_gateway` à `disabled` ».
- **V-A §24.2, §26.3 ; VIII T-LLM-07** : état `open`, `reason = not_configured` ; **VII §40.3** : composant `llm_gateway` en statut `disabled`, `reason` `not_configured`.
- Le critère du Sprint 6 ne dit pas s'il vise le statut du composant (`disabled`) ou la clé `SystemState.llm_gateway` (`not_configured`).

Décision du propriétaire : —

#### CF-24 — Préalable « Partie VII en source Markdown »

- **IX §57.2** : « les dix fichiers de spec durcis en Markdown, dont la **Partie VII en source Markdown** (l'export actuel n'en est pas une) ».
- **Décision du propriétaire du 2026-09-22** (E9) : la Partie VII a été refaite proprement en amont ; aucune reconstitution. La parenthèse de IX §57.2 décrit un état révolu.

Décision du propriétaire : —

#### CF-25 — Critère « Portable »

- **I §4.3** (« Portable ») : « Migration vers un autre VPS = copie du volume persistant + `docker compose up` ».
- **VII §36.4** (« Portabilité ») : « restaurer le dernier backup (ou copier `radar.db` **à l'arrêt**) + `.env` + `docker compose up -d` » ; **VIII §52 G2** : « backup + `.env` + `docker compose up -d` ».
- Partie I n'exige ni l'arrêt pendant la copie ni le `.env`.

Décision du propriétaire : —
