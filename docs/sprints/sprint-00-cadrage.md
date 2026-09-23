# Sprint 0 — Rapport de cadrage

> Tâche T0.2 (#5), rédigé le 2026-09-23 sur la spec réconciliée par T0.1a (#57) et T0.1b (#58).
> Structure imposée par la Partie IX §57.5 : conflits · décisions manquantes · vérifications · risques · questions ouvertes.
> Ce rapport **ne tranche rien** (IX décision 4, §53.1) : chaque point porte une recommandation et une ligne
> « Décision du propriétaire », à remplir par le propriétaire du projet. Les identifiants sont stables : un point
> tranché ou abandonné garde son numéro.
> **Arbitrages** : le propriétaire a tranché tous les points le 2026-09-23 ; chaque décision est consignée sous
> son point, avec l'endroit où elle est appliquée (T0.2b, #66).

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

Décision du propriétaire (2026-09-23) : impact reporté dans la Partie VII (T0.1c, option A de E11) : `APP_ENV=test` et section « Réservé aux tests » avec `HTTP_TEST_ALLOW_HOSTS` — appliquée dans VII §36.7.

#### CF-02 — Séquence de déploiement exécutée par `deploy.sh`

- **VIII §49.5** : la séquence est exécutée par `scripts/deploy.sh`, après le contrôle CI ; `backup-now` passe par `docker compose exec worker`, code de sortie vérifié.
- **VII §36.9** : séquence manuelle (`git pull → build → backup-now → stop → up -d`), sans verrou CI ni script.

Décision du propriétaire (2026-09-23) : impact reporté dans la Partie VII (T0.1c) : la séquence est exécutée par `scripts/deploy.sh` après le contrôle CI, `backup-now` par `docker compose exec worker` — appliquée dans VII §36.9.

#### CF-03 — Racine en lecture seule : Sprint 1 ou Sprint 11

- **VIII décision 4, §47.3** : racine en lecture seule active dès le Sprint 1 ; le Sprint 11 ne fait que confirmer le cas de restic.
- **VII §36.5** (dernier point) : « Le système de fichiers racine en lecture seule est à valider au Sprint 11 (onnxruntime, lingua, restic). »

Décision du propriétaire (2026-09-23) : impact reporté dans la Partie VII (T0.1c) : racine en lecture seule dès le Sprint 1, le Sprint 11 confirme le cas de restic — appliquée dans VII §36.5.

#### CF-04 — Restauration outillée par `scripts/restore.sh`

- **VIII décision 24, §46.1, T-BKP-08, T-RES-07** : la procédure de restauration est outillée par `scripts/restore.sh`.
- **VII §38.5** : procédure décrite en commandes manuelles, sans script.

Décision du propriétaire (2026-09-23) : impact reporté dans la Partie VII (T0.1c) : restauration outillée par `scripts/restore.sh` — appliquée dans VII §38.5.

#### CF-05 — Jeton GitHub de `deploy.sh`

- **VIII §49.5** (« Jeton GitHub ») et **IX §56.6-P5** : si le dépôt est privé, jeton *fine-grained* en lecture seule, hors du `.env` applicatif, jamais transmis à un conteneur.
- **VII §43.4** : « Uniquement dans `.env` » ; ce jeton n'y est pas mentionné.

Décision du propriétaire (2026-09-23) : impact reporté dans la Partie VII (T0.1c) : le jeton GitHub de `deploy.sh` est la seule exception à « uniquement dans `.env` » — appliquée dans VII §43.4.

#### CF-06 — Profils de charge dans le projet `radar-load`

- **VIII décision 20, §47.4, §50.7** : profils synthétiques joués dans un projet Compose distinct (`-p radar-load`), avec son propre volume ; mesures de référence en pré-production.
- **VII §45.3–§45.4** : profils et mesures décrits sans projet distinct ni moment de référence.

Décision du propriétaire (2026-09-23) : impact reporté dans la Partie VII (T0.1c) : profils de charge dans le projet `radar-load`, mesures de référence en pré-production — appliquée dans VII §45.3 et §45.4.

#### CF-07 — Inventaire des commandes : `vacuum`, `snapshot_id`, mode d'exécution

- **IX §56.3, §56.4, décisions 19 et 21** : nouvelle commande `vacuum` ; `backup-now` affiche le `snapshot_id` ; `validate-config` s'exécute en `run --rm --no-deps worker` ; contrat commun des commandes (codes `0` / `1` / `2`, stdout / stderr).
- **VII §36.8** : pas de `vacuum` ; colonne « Où » de `validate-config` = « worker, CI » ; aucun renvoi au contrat commun.

Décision du propriétaire (2026-09-23) : impact reporté dans la Partie VII (T0.1c) : commande `vacuum`, `snapshot_id` de `backup-now`, mode d'exécution de `validate-config` et renvoi au contrat commun — appliquée dans VII §36.8.

#### CF-08 — Rollback à travers une migration

- **IX décision 18, §56.6-P2 ; VIII §49.5** : `deploy.sh` détecte une migration à défaire et refuse ; procédure *downgrade* ou restauration.
- **VII §36.9** (« Rollback ») : « redéployer le tag précédent. Si une migration irréversible est passée, restaurer le backup pris avant le déploiement. »

Décision du propriétaire (2026-09-23) : impact reporté dans la Partie VII (T0.1c) : `deploy.sh` refuse un rollback à travers une migration, procédure IX §56.6-P2 — appliquée dans VII §36.9.

#### CF-09 — Verrou de backup `/data/backup/.lock`

- **IX décision 20, §56.4.1 ; VIII T-BKP-11** : verrou exclusif partagé par les jobs `backup`, `restore_test` et les commandes `backup-now`, `restore-test`.
- **VII §38.2, §38.4** : aucun verrou ; un backup et un test de restauration peuvent se chevaucher.

Décision du propriétaire (2026-09-23) : impact reporté dans la Partie VII (T0.1c) : verrou `/data/backup/.lock` commun au backup et au test de restauration — appliquée dans VII §38.2 et §38.4.

#### CF-10 — Pas-à-pas de la restauration : runbook ou `backup-restore.md`

- **IX §55.5, réconciliation « VII §38.5 »** : le pas-à-pas vit dans `docs/backup-restore.md` ; le runbook résume et renvoie.
- **VII §38.5** (dernière ligne) : « Le détail pas à pas va au runbook (`docs/backup-restore.md`). »

Décision du propriétaire (2026-09-23) : impact reporté dans la Partie VII (T0.1c) : le pas-à-pas vit dans `docs/backup-restore.md`, le runbook résume et renvoie — appliquée dans VII §38.5.

#### CF-11 — Application d'un changement de `.env` : `restart` ou `up -d`

- **IX décision 22, §56.2, §56.6-P4, P5** : toute modification du `.env` s'applique par `docker compose up -d <service>`, jamais par `restart`.
- **VII §43.4** (« Rotation ») : « redémarrage de `caddy` » et « redémarrage du `worker` ». La même partie écrit pourtant `docker compose up -d caddy` en **VII §36.8** (ligne `caddy hash-password`). Voir aussi CF-17 pour la Partie VI.

Décision du propriétaire (2026-09-23) : impact reporté dans la Partie VII (T0.1c) : tout changement de `.env` s'applique par `docker compose up -d <service>` — appliquée dans VII §43.4.

#### CF-12 — `VACUUM` manuel

- **IX décision 21, §56.4.2, §56.6-P8** : `VACUUM` manuel par `app.cli vacuum`, worker arrêté, fichiers temporaires de SQLite sur `/data`, jamais dans le tmpfs.
- **VII §44.2** : « Un `VACUUM` manuel, worker arrêté, reste possible via le runbook », sans commande ni emplacement des fichiers temporaires.

Décision du propriétaire (2026-09-23) : impact reporté dans la Partie VII (T0.1c) : `VACUUM` manuel par `app.cli vacuum`, fichiers temporaires sur `/data` — appliquée dans VII §44.2.

### 1.B Impacts sans objet

#### CF-13 — « Décisions prises dans cette V0.3 » dans `SPEC.md`

- **Impact IX → `SPEC.md`** (section d'impacts retirée par #58) : « Supprimer "Décisions prises dans cette V0.3 (à valider)" ».
- **Préambule V0.4** (ancien `docs/spec/SPEC.md`, avant #58) : ce bloc n'existait pas. Rien à supprimer ; `SPEC.md` suit IX §55.2.

Décision du propriétaire (2026-09-23) : sans objet, rien à supprimer dans `SPEC.md` — consignée seulement.

#### CF-14 — Décision 5 de la V0.3 (« token unique + basic_auth »)

- **Impact VI → `SPEC.md`** : remplacer la décision 5 par « basic_auth Caddy seul, anti-CSRF côté app ».
- **Préambule V0.4** : la décision 5 n'y figure pas. Le point est couvert par DV-13 (**IX §53.2**) et **VI §32**.

Décision du propriétaire (2026-09-23) : sans objet, point couvert par DV-13 (IX §53.2) et VI §32 — consignée seulement.

### 1.C Contradictions entre parties

#### CF-15 — Compteurs d'Event : incrémentés ou recalculés

- **II décision 3** : compteur de sources distinctes « mis à jour à chaque rattachement » ; **II §7.2** (tableau, ligne « Hotness ») : « incrémenté à chaque rattachement » ; **II §7.3** : `distinct_source_count++`.
- **V-B décision 9, §28.9** : compteurs « toujours recalculés depuis les membres », « jamais incrémentés », dans la transaction de rattachement.
- **III §11.3** (invariant) : compatible avec les deux lectures (« mis à jour dans la même transaction », « un contrôle de cohérence peut le recalculer »).

Décision du propriétaire (2026-09-23) : compteurs d'Event recalculés depuis les membres, jamais incrémentés (lecture de V-B §28.9) — appliquée dans II décision 3, §7.2 et §7.3.

#### CF-16 — Exceptions de la garde anti-SSRF

- **IV §21.1, VII §43.3, VIII T-HTTP-08** : la garde du `HttpClient` admet deux exceptions, `LLM_BASE_URL` et le dépôt restic.
- **V-A §25.2** : le `LLMClient` utilise un **client HTTP dédié**, distinct du `HttpClient` ; **VII §38.2** : le backup appelle le binaire `restic`, qui ne passe pas par le `HttpClient`.
- Deux lectures possibles : les exceptions sont sans objet dans le `HttpClient`, ou la garde doit aussi couvrir le client LLM (avec l'exception `LLM_BASE_URL`).

Décision du propriétaire (2026-09-23) : les exceptions `LLM_BASE_URL` et restic sont retirées de la garde du `HttpClient` ; le `LLMClient` n'appelle que `LLM_BASE_URL` et ne suit aucune redirection vers un autre hôte (nouveau test T-LLM-20, niveau U, Sprint 6) — appliquée dans IV §21.1, V-A §25.2, VII §43.3, VIII §47.2 (Sprint 6) et §50.5 (T-HTTP-08, T-LLM-20).

#### CF-17 — Rotation du mot de passe du dashboard

- **VI §32.1** (« Rotation ») : « nouveau hash dans l'environnement, redémarrage de `caddy` ».
- **IX décision 22, §56.6-P4** : `docker compose up -d caddy` ; `restart` ne relit pas l'environnement.

Décision du propriétaire (2026-09-23) : rotation du mot de passe par `docker compose up -d caddy` — appliquée dans VI §32.1.

#### CF-18 — Cycle « Create topic » : slug et mots-clés

- **V-A §24.6** : slug dérivé de `llm_label`, à défaut `label` ; mots-clés = `suggested_keywords` ∪ {`key`}.
- **V-B §30.8** (T1) : `name` = `llm_label` ou `label`, slug dérivé de `name`, suffixe `-2`, `-3` en collision ; mots-clés = `suggested_keywords` ∪ {terme de base}, où le terme de base vaut `key` pour un `ngram` et `canonical_name` (`owner/repo`) pour un `repository`, dont la `key` est `repo:{canonical_name}` (**V-B §30.2**).
- Pour un `repository`, V-A ajouterait `repo:owner/repo` comme mot-clé, V-B `owner/repo`. V-B annonce « Complète V-A §24.6 » ; seul le texte d'entrée du backfill était explicitement corrigé.

Décision du propriétaire (2026-09-23) : le cycle « Create topic » suit V-B §30.8 (nom, slug suffixé, terme de base) — appliquée dans V-A §24.6.

#### CF-19 — Alias d'entités : V1 ou V2

- **IV §16.4, V-A §27.2** : `entities.yaml` porte des `aliases` matchés dès la V1 ; les entités LLM sont canonicalisées par ce matcher d'alias.
- **III** (« Reporté en V2 ») : « Alias et fusion d'entités (ex. « Claude Code » / « claude-code » / « CC ») au-delà du `canonical_name` ».
- **III §11.6** (note ajoutée par #58) : les alias vivent dans `entities.yaml`, pas en base. La frontière V1 / V2 (alias déclarés à la main contre fusion en base) n'est écrite nulle part.

Décision du propriétaire (2026-09-23) : V1 : alias déclarés à la main dans `entities.yaml` ; V2 : alias et fusion automatiques en base — appliquée dans III « Reporté en V2 ».

### 1.D Conflits relevés à la lecture

#### CF-20 — Rôle de l'AI dans le regroupement et les tendances

- **I §3** (fonctions 4 et 7) : regroupement **[mixte]** avec « confirmation des cas ambigus **[AI]** » ; tendances avec « lecture qualitative **[AI]** » ; fonction 5 (topics, entités, événements) étiquetée **[AI]**.
- **II décision 2** : `resolve_event` « arbitre les cas ambigus » ; **II §6** (couche enrichissement) : « confirmation des événements ambigus, lecture qualitative des tendances ».
- **V-A décisions 4 et 7**, « Reporté en V2 » : arbitrage des cas ambigus et `analyze_trend` reportés en V2 ; **III décision 1, IV §20.4** : topics et entités ont aussi une origine déterministe (`keyword`).

Décision du propriétaire (2026-09-23) : arbitrage des cas ambigus et `analyze_trend` reportés en V2 ; topics et entités ont aussi une origine déterministe — appliquée dans I §3 (et « Reporté en V2 »), II décision 2 et §6.

#### CF-21 — Panne du moteur d'embeddings : « jobs » d'embedding

- **II §9.1** (ligne « Moteur d'embeddings indisponible ») : détection par « échec des jobs d'embedding », reprise par « jobs d'embedding en `retry` ».
- **IV décision 21, §14.3 ; V-A §24.4** : les embeddings n'ont **pas** d'`AIJob` : file dérivée, backoff du tick, `SystemState.embeddings = down`, ligne `Embedding` en échec après `embeddings.max_failures`.

Décision du propriétaire (2026-09-23) : les embeddings n'ont pas de jobs : file dérivée, état `SystemState.embeddings` — appliquée dans II §9.1.

#### CF-22 — Lecture de `pipeline.yaml` par l'app

- **IV §16.1** : les fichiers `config/` sont chargés par le worker ; « L'app ne charge pas ces fichiers. »
- L'app a pourtant besoin de réglages qui y vivent : `ops.heartbeat_stale_after` pour `/health` (**VII §40.2**, calcul par l'app, **VII §39.7**) ; `emerging.warmup` pour l'Overview et le bandeau (**VI §31.3, §31.10**) ; `llm.daily_request_budget` et `llm.app_reserve` pour `/api/health` (**VII §40.3**). **VII §40.1** impose en plus le même seuil de heartbeat à `/health`, `/api/health` et `/api/status`.

Décision du propriétaire (2026-09-23) : option A de E17 : l'app charge `pipeline.yaml` en lecture seule, avec les mêmes modèles de validation que le worker — appliquée dans IV §16.1.

#### CF-23 — Valeur attendue quand le LLM n'est pas configuré

- **VIII §47.2** (Sprint 6, acceptation) : « `llm_gateway` à `disabled` ».
- **V-A §24.2, §26.3 ; VIII T-LLM-07** : état `open`, `reason = not_configured` ; **VII §40.3** : composant `llm_gateway` en statut `disabled`, `reason` `not_configured`.
- Le critère du Sprint 6 ne dit pas s'il vise le statut du composant (`disabled`) ou la clé `SystemState.llm_gateway` (`not_configured`).

Décision du propriétaire (2026-09-23) : le critère du Sprint 6 vise le statut du composant `llm_gateway` dans `/api/health` (`disabled`, raison `not_configured`) — appliquée dans VIII §47.2 (Sprint 6).

#### CF-24 — Préalable « Partie VII en source Markdown »

- **IX §57.2** : « les dix fichiers de spec durcis en Markdown, dont la **Partie VII en source Markdown** (l'export actuel n'en est pas une) ».
- **Décision du propriétaire du 2026-09-22** (E9) : la Partie VII a été refaite proprement en amont ; aucune reconstitution. La parenthèse de IX §57.2 décrit un état révolu.

Décision du propriétaire (2026-09-23) : la mention d'une Partie VII « non Markdown » est retirée — appliquée dans IX §57.2.

#### CF-25 — Critère « Portable »

- **I §4.3** (« Portable ») : « Migration vers un autre VPS = copie du volume persistant + `docker compose up` ».
- **VII §36.4** (« Portabilité ») : « restaurer le dernier backup (ou copier `radar.db` **à l'arrêt**) + `.env` + `docker compose up -d` » ; **VIII §52 G2** : « backup + `.env` + `docker compose up -d` ».
- Partie I n'exige ni l'arrêt pendant la copie ni le `.env`.

Décision du propriétaire (2026-09-23) : « Portable » = backup (ou copie de `radar.db` à l'arrêt) + `.env` + `docker compose up -d` — appliquée dans I §4.3.

---

## 2. Décisions manquantes

Pour chaque point : contexte, options, recommandation, sprint bloqué tant que le point n'est pas tranché.
E1 à E10 reprennent les écarts de `docs/planning.md` §2 ; E11 est la conséquence de E9 ; E12 à E15 reprennent la
liste D de la PR #58 ; E16 à E21 sont apparus à la lecture. Chaque décision est ensuite appliquée dans la spec ou
par un ADR pendant le Sprint 0 (IX §57.5) : voir E21.

### 2.A Écarts du planning (E1 à E10)

#### E1 — Traçabilité du catalogue et CI verte à chaque sprint

- **Contexte** : **VIII §50.3** rend bloquant, dès l'étape 1 de la CI, tout identifiant de niveau U, I, E ou F sans test. **VIII §47.1** exige une CI verte à la fin de chaque sprint. Dès le Sprint 1, environ 180 identifiants n'ont pas encore de test : les deux règles sont incompatibles.
- **Options** :
  - A. Hypothèse du planning : `check-test-catalog.py` ne contrôle que les identifiants des sprints **clos et en cours**, liste tirée des `docs/sprints/sprint-NN.md` ; contrôle **complet** au Sprint 11 (critère **VIII §52 A2**).
  - B. Ajouter une colonne « Sprint » au catalogue **VIII §50.5** et contrôler les identifiants de sprint ≤ sprint courant (source unique dans la spec, mais le catalogue grossit et l'attribution devient normative).
  - C. Créer des tests vides marqués `skip` pour chaque identifiant futur (CI verte, mais traçabilité fictive).
- **Recommandation** : A. Mise à jour de **VIII §50.3** en conséquence.
- **Bloque** : Sprint 1 (étape 1 de la CI) ; conception de `check-test-catalog.py` en T0.5.

Décision du propriétaire (2026-09-23) : option A : contrôle du catalogue sur les sprints clos et en cours (liste lue dans les `sprint-NN.md`), contrôle complet au Sprint 11 — appliquée dans VIII §50.3 et décision 9.
Précisé le 2026-09-23 par P-15 (T0.5, #71) : seuls les identifiants des sprints **clos** bloquent ; ceux du sprint en cours sont signalés sans bloquer jusqu'à la PR de bilan.

#### E2 — T-DB-12 et T-CFG-09 rattachés à aucun sprint

- **Contexte** : **VIII §47.2** ne cite T-DB-12 (valeurs `CHECK`) ni T-CFG-09 (`HTTP_TEST_ALLOW_HOSTS` refusée en production) dans aucun sprint.
- **Options** : A. Hypothèse du planning : T-CFG-09 au Sprint 2 (avec le `HttpClient`), T-DB-12 au Sprint 2 (`Article.status`), complété au Sprint 5 (`AIJob.status`) et au Sprint 10 (`AlertLog.status`). B. Tout au Sprint 11, sous les jokers (retarde des contrôles simples).
- **Recommandation** : A, reporté dans les listes « Tests » de **VIII §47.2**.
- **Bloque** : plan du Sprint 2 (T0.8 pour le Sprint 1 n'est pas concerné).

Décision du propriétaire (2026-09-23) : option A : T-CFG-09 et T-DB-12 au Sprint 2, T-DB-12 complété aux Sprints 5 et 10 — appliquée dans VIII §47.2.

#### E3 — Tests attribués avant que leur objet existe

- **Contexte** : **VIII §47.2** place au Sprint 7 T-PRG-05 (volet `AlertLog`, table du Sprint 10) et T-PRG-06 (`Signal`, Sprint 8), T-LLM-18 volet `discover_topics` (Sprint 8) ; au Sprint 5, T-JOB-04 `candidate_decided` (candidats au Sprint 8).
- **Options** : A. Hypothèse du planning : couverture partielle au sprint annoncé, **complétée** au sprint qui livre l'objet (Sprint 8 : T-PRG-06, T-LLM-18, T-JOB-04 ; Sprint 10 : T-PRG-05). B. Déplacer ces identifiants entiers au sprint qui livre l'objet.
- **Recommandation** : A (le mécanisme de E1 doit alors admettre un identifiant « partiel » ; à préciser en T0.5).
- **Bloque** : Sprints 5 et 7 (critères d'acceptation).

Décision du propriétaire (2026-09-23) : option A : couverture partielle au sprint annoncé, complétée au sprint qui livre l'objet (Sprint 8 : T-PRG-06, T-LLM-18, T-JOB-04 ; Sprint 10 : T-PRG-05) ; l'identifiant « partiel » est précisé en T0.5 — appliquée dans VIII §47.2.

#### E4 — Tests rattachés trop tard par le joker du Sprint 11

- **Contexte** : T-OPS-16 (coalescence des misfires, scheduler livré au Sprint 2) et T-SEC-10 (modèle intégré à l'image, Sprint 4) ne sont couverts que par « T-OPS-* » et « T-SEC-* » du Sprint 11 (**VIII §47.2**).
- **Options** : A. Hypothèse du planning : T-OPS-16 au Sprint 2, T-SEC-10 au Sprint 4. B. Laisser au Sprint 11.
- **Recommandation** : A : un comportement se teste dans le sprint qui le livre.
- **Bloque** : plans des Sprints 2 et 4.

Décision du propriétaire (2026-09-23) : option A : T-OPS-16 au Sprint 2, T-SEC-10 au Sprint 4 — appliquée dans VIII §47.2.

#### E5 — Vérification « modèle d'embeddings présent dans l'image » dès le Sprint 1

- **Contexte** : **VIII §49.2**, étape 5, vérifie le modèle dans l'image ; la CI complète existe dès le Sprint 1 (**VIII §47.2**), mais les embeddings n'arrivent qu'au Sprint 4.
- **Options** : A. Hypothèse du planning : vérification **activée au Sprint 4**, décision consignée dans `sprint-01.md`. B. Intégrer le modèle dès le Sprint 1 (build plus lourd et plus long trois sprints plus tôt, sans usage).
- **Recommandation** : A.
- **Bloque** : Sprint 1 (étape 5 de la CI).

Décision du propriétaire (2026-09-23) : option A : vérification « modèle dans l'image » activée au Sprint 4, décision reprise dans `sprint-01.md` (T0.8) — appliquée dans VIII §49.2.

#### E6 — T-CFG-04 (toutes les sections de `pipeline.yaml`) listé au Sprint 2

- **Contexte** : T-CFG-04 valide toutes les sections de `pipeline.yaml`, dont `llm`, `clustering`, `trends`, `alerts`, `ops`, `backup` (**VIII §50.5**), mais il est attendu au Sprint 2 (**VIII §47.2**).
- **Options** : A. Hypothèse du planning : validation **incrémentale**, chaque sprint ajoute et teste ses sections (DoD **VIII §51.1**-5) ; T-CFG-04 complet au Sprint 11. B. Définir tous les schémas dès le Sprint 2 (réglages spécifiés mais inutilisés pendant neuf sprints).
- **Recommandation** : A.
- **Bloque** : Sprint 2.

Décision du propriétaire (2026-09-23) : option A : validation incrémentale de `pipeline.yaml`, T-CFG-04 complet au Sprint 11 — appliquée dans VIII §47.2.

#### E7 — Table `AIJob` au Sprint 2

- **Contexte** : T-COL-12 et **IV §14.3** créent un `enrich_article` à chaque insertion dès le Sprint 2, alors que la file `AIJob` est livrée au Sprint 5 (**VIII §47.2**).
- **Options** : A. Hypothèse du planning : table `AIJob` introduite **au Sprint 2** (migration), jobs `pending` jusqu'au Sprint 5 ; `database.md` (T0.4) le reflète. B. Ne créer les jobs qu'au Sprint 5, avec rattrapage des articles déjà insérés (contredit **IV §14.3** et ajoute un mécanisme).
- **Recommandation** : A.
- **Bloque** : T0.4 (`database.md`) et Sprint 2.

Décision du propriétaire (2026-09-23) : option A : table `AIJob` introduite au Sprint 2, jobs `pending` jusqu'au Sprint 5 ; `database.md` le reflète (T0.4) — appliquée dans VIII §47.2.

#### E8 — T-LLM-16 exige des sorties LLM réelles

- **Contexte** : T-LLM-16 (niveau U, donc bloquant en CI) parse des « sorties réelles enregistrées » par `scripts/record-llm-fixtures.py`, lancé à la main contre un vrai gateway (**VIII décision 15, §50.4**). Le go-live se fait sans gateway (planning C9, **VIII décision 21**).
- **Options** : A. Hypothèse du planning : accès ponctuel à un provider OpenAI-compatible aux Sprints 7 et 8, tâche du propriétaire. B. Scinder T-LLM-16 : snapshot du prompt (U, bloquant) et sorties réelles (niveau M, consigné). C. Accepter des sorties écrites à la main, marquées comme telles.
- **Recommandation** : A ; B en repli si l'accès provider n'est pas disponible à temps.
- **Bloque** : clôture des Sprints 7 et 8.

Décision du propriétaire (2026-09-23) : option A (accès ponctuel à un provider aux Sprints 7 et 8, tâche du propriétaire), option B en repli — consignée seulement.

#### E9 — Partie VII : reconstitution des tableaux

- **Contexte** : le planning (C11, E9) prévoyait de reconstituer dans T0.1 les tableaux dégradés de la Partie VII (§36.7, §39.5, §45.3–§45.4), la Partie VII ayant été extraite d'un PDF.
- **Décision prise le 2026-09-22 par le propriétaire** : la Partie VII a été refaite proprement en amont. **Aucune reconstitution**, et `docs/spec/partie-VII.md` **n'est pas modifié** en T0.1b (#58). La conséquence est traitée en E11.
- **Statut** : décidé. `docs/planning.md` (C11, E9, fiche S0) est aligné dans la même PR que ce rapport.

Décision du propriétaire (2026-09-23) : confirme la décision du 2026-09-22 : aucune reconstitution de la Partie VII — consignée seulement.

#### E10 — Découpage de la spec en dix fichiers

- **Contexte** : **IX §57.2** attend dix fichiers de spec ; la spec arrivait consolidée dans un seul fichier.
- **Statut** : **réalisé** par T0.1a (#57, fusionnée) : découpage mécanique en `docs/spec/partie-*.md`, un commit par partie, sans modification de contenu. Le préambule résiduel est devenu l'index `SPEC.md` en T0.1b (#58).

Décision du propriétaire (2026-09-23) : réalisé par T0.1a (#57) — consignée seulement.

### 2.B Conséquence de E9

#### E11 — Partie VII non réconciliée

- **Contexte** : sans modification de la Partie VII, 12 impacts de VIII et IX restent non reportés (CF-01 à CF-12). La Partie VII garde sa section « Impacts à répercuter », ses marqueurs « (proposé) » et « À confirmer » et son en-tête V0.3. Le critère **IX §57.7** « plus aucune section d'impacts ni marqueur » (repris par **IX §55.2**) n'est donc pas atteignable, et le Sprint 0 ne peut pas être accepté en l'état.
- **Options** :

| Option | Contenu | Coût | Risque |
|---|---|---|---|
| A. **T0.1c** | PR dédiée qui reporte les 12 impacts dans VII, **sans reconstitution ni réécriture** des tableaux (ajouts ciblés : lignes de `.env.example`, `vacuum`, verrou, renvois), puis retire la section d'impacts, les marqueurs et l'en-tête V0.3 | ≈ 1 session de rédaction, 1 relecture ciblée ; diff d'une douzaine de passages | faible : on touche une partie « refaite proprement », mais seulement aux 12 endroits listés ; relecture facile |
| B. **Amender IX §57.7** (et §55.2) | mise à jour de spec qui exempte la Partie VII du critère, en gardant ses impacts comme notes | très faible | élevé : VII reste en contradiction avec VIII et IX ; le Sprint 1 lit un §36.5 et un §36.7 périmés (CF-01, CF-03), le Sprint 11 un §36.9 et un §38 périmés ; chaque conflit doit de toute façon être tranché (**VIII §51.3**) |
| C. **Report à un sprint ultérieur** | chaque impact est reporté dans VII par le sprint qui l'implémente (Sprint 1 : CF-01, CF-03 ; Sprint 11 : les autres), avec une exemption temporaire de §57.7 | étalé, mais s'ajoute à des sprints déjà chargés | moyen : oubli possible ; exige quand même l'amendement de l'option B pour clore le Sprint 0 |

- **Recommandation** : A, à enchaîner juste après l'arbitrage de ce rapport. Les 12 reports s'alignent sur des décisions déjà prises en VIII et IX ; ils peuvent être regroupés avec les corrections de spec issues des autres points (E21).
- **Bloque** : acceptation du Sprint 0 (**IX §57.7**) ; Sprint 1 si CF-01 et CF-03 restent ouverts.

Décision du propriétaire (2026-09-23) : option A (T0.1c), intégrée à T0.2b (#66) : les 12 impacts CF-01 à CF-12 sont reportés, la section d'impacts, les marqueurs et l'en-tête V0.3 retirés — appliquée dans VII (§35 à §45).

### 2.C Choix d'application de T0.1b à valider (liste D de la PR #58)

#### E12 — `Article.summary` non nul

- **Contexte** : l'impact IV → III disait que la contrainte « non nul si `ready` » « **peut devenir** non nul ». T0.1b l'a appliqué comme « **non nul** » (**III §11.2**), puisque **IV §14.5** calcule le résumé de repli pour tout article inséré, `filtered` compris.
- **Options** : A. Garder « non nul ». B. Revenir à « non nul si `ready` ».
- **Recommandation** : A : c'est ce que produit le pipeline, et la contrainte est plus simple.
- **Bloque** : T0.4 (`database.md`).

Décision du propriétaire (2026-09-23) : option A : `Article.summary` non nul, déjà dans III §11.2 — consignée seulement (reprise en T0.4).

#### E13 — Identifiants et niveaux des tests ajoutés au catalogue

- **Contexte** : l'impact IX → VIII listait cinq tests sans identifiant ni niveau. T0.1b a créé T-CFG-10 (U, codes de sortie des commandes), T-OPS-17 (I, refus de `vacuum`), T-BKP-10 (I, `snapshot_id`), T-BKP-11 (I, verrou de backup) et T-BKP-12 (I, refus d'un rollback à travers une migration) dans **VIII §50.5**.
- **Options** : A. Garder ces identifiants et niveaux. B. Ouvrir un domaine dédié au déploiement (`T-DEP-*`) pour T-BKP-12, qui teste `deploy.sh` plutôt que le backup.
- **Recommandation** : A ; B n'apporte qu'un rangement.
- **Bloque** : T0.8 et Sprint 11 (traçabilité).

Décision du propriétaire (2026-09-23) : option A : identifiants et niveaux gardés, déjà dans VIII §50.5 — consignée seulement.

#### E14 — Rattachement de T-CFG-10 à un sprint

- **Contexte** : les T-CFG sont listés un par un dans **VIII §47.2** ; T-CFG-10 n'y figure pas. T-OPS-17 et T-BKP-10 à 12 relèvent du joker du Sprint 11 (« T-OPS-* · T-BKP-* »).
- **Options** : A. T-CFG-10 au Sprint 1 : `validate-config` y est livré et le contrat commun des commandes (**IX §56.3**) s'applique dès la première commande. B. Au Sprint 11, avec l'inventaire complet des commandes.
- **Recommandation** : A ; confirmer au passage le Sprint 11 pour T-OPS-17 et T-BKP-10 à 12.
- **Bloque** : T0.8 (plan du Sprint 1).

Décision du propriétaire (2026-09-23) : option A : T-CFG-10 au Sprint 1 ; T-OPS-17 et T-BKP-10 à 12 confirmés au Sprint 11 — appliquée dans VIII §47.2.

#### E15 — Sort des listes « À confirmer à la relecture »

- **Contexte** : **IX décision 12** répute validés les points « (proposé) » et « à confirmer » des Parties I à VIII. En T0.1b, les listes de **VIII** et **IX** (« Points d'interprétation ») ont été renommées « Décisions à poids réel, prises par défaut puis validées avec la partie » plutôt que supprimées.
- **Options** : A. Garder ces listes renommées (trace des décisions par défaut). B. Les supprimer (l'historique Git les conserve, comme les sections d'impacts, **IX §55.2**).
- **Recommandation** : A.
- **Bloque** : rien (forme).

Décision du propriétaire (2026-09-23) : option A : listes renommées conservées — consignée seulement.

### 2.D Décisions relevées à la lecture

#### E16 — Image de base Python

- **Contexte** : **VII §35** fixe « Python 3.12+ ». **IX §57.4** vérifie « SQLite de l'image de base Python **retenue** », mais aucune image n'est retenue. Le choix conditionne la version de SQLite (≥ 3.35, FTS5, JSON1 : **III §10.1**), la disponibilité des wheels onnxruntime et lingua, la taille de l'image (M8) et la racine en lecture seule.
- **Options** : A. Image officielle `python:3.12-slim` (Debian), tag précis épinglé. B. Variante Alpine (musl) : image plus petite, mais wheels onnxruntime non garanties. C. Image distroless : surface minimale, mais outillage (restic, `sqlite3` de diagnostic) plus difficile à intégrer.
- **Recommandation** : A, version exacte figée après la vérification de T0.3.
- **Bloque** : T0.3 (vérification SQLite) et T0.5 (Compose, Dockerfile proposés).

Décision du propriétaire (2026-09-23) : option A : image `python:3.12-slim`, tag complet et digest épinglés, valeur de référence vérifiée en T0.3 (§3) — appliquée dans VII §35.

#### E17 — Accès de l'app aux réglages de `pipeline.yaml`

- **Contexte** : CF-22. L'app a besoin de `ops.heartbeat_stale_after`, `emerging.warmup`, `llm.daily_request_budget` et `llm.app_reserve`, alors que **IV §16.1** réserve le chargement de `config/` au worker.
- **Options** : A. L'app charge `pipeline.yaml` en lecture seule, avec les mêmes modèles Pydantic ; le worker reste le seul à charger `sources.yaml`, `topics.yaml` et `entities.yaml` en base. Amender **IV §16.1**. B. Le worker publie les réglages utiles dans une clé `SystemState` ; l'app les lit (mais `/health` dépendrait d'une valeur écrite par le processus qu'il surveille). C. Ces réglages deviennent des constantes du code (perte de configurabilité, contredit **VII §39.7**).
- **Recommandation** : A.
- **Bloque** : Sprint 1 (`/health` calcule l'âge du heartbeat) ; T0.5 (stratégie de configuration).

Décision du propriétaire (2026-09-23) : option A : l'app charge `pipeline.yaml` en lecture seule, avec les mêmes modèles de validation que le worker — appliquée dans IV §16.1.

#### E18 — Check-list de mesure du gateway (« V0.3 §25 »)

- **Contexte** : **V-A §25** et **VII §45.4** (M6) renvoient à la « checklist V0.3 §25 ». La V0.3 n'est pas dans le dépôt (**IX §57.2** retire la V0.2 et les doublons ; la V0.3 n'y a jamais été versée).
- **Options** : A. Le propriétaire fournit le texte de V0.3 §25, recopié dans `docs/llm-gateway.md` au Sprint 6. B. Le contenu de la ligne M6 (**VII §45.4** : RAM/CPU si auto-hébergé, requêtes multiples, quota épuisé, timeout, provider indisponible, 429 / `Retry-After`, `GET /models`) devient la check-list de référence ; les renvois à « V0.3 §25 » sont remplacés.
- **Recommandation** : B, sauf si la V0.3 contient d'autres points utiles (Q-02).
- **Bloque** : Sprint 6 (M6, `llm-gateway.md`).

Décision du propriétaire (2026-09-23) : option B, complétée par la V0.3 retrouvée (Q-02) : la ligne M6 devient la check-list de référence, avec les gateways candidats (OmniRoute, Free Model Router, FreeLLMAPI) et la consigne « si trop lourd, déployable séparément » ; renvois à « V0.3 §25 » retirés — appliquée dans VII §45.4 et V-A §25.

#### E19 — Langue de l'interface

- **Contexte** : **I §5.1** : « Pas d'internationalisation de l'interface (UI mono-langue) », sans dire laquelle. Les aperçus LLM sont en français (**V-A §27.1**, `llm.summary_language = fr`), le fuseau par défaut est `Europe/Paris` (**VI §34.3**), les alertes ont un contenu rédigé (**VI §33.8**).
- **Options** : A. Français (interface, alertes, digests). B. Anglais (cohérent avec les sources majoritairement EN).
- **Recommandation** : A.
- **Bloque** : Sprint 3 (premier écran) ; Sprint 10 (textes des alertes).

Décision du propriétaire (2026-09-23) : option A : interface, alertes et digests en français — appliquée dans I §5.1.

#### E20 — Stylage du frontend compatible avec la CSP

- **Contexte** : **VII §37.3** et **VIII §46.2** interdisent script et `<style>` en ligne et tout CSS-in-JS à l'exécution, sauf ADR élargissant `style-src` (**IX §54.3**). Aucune approche de stylage ni bibliothèque de composants n'est retenue.
- **Options** : A. CSS natif ou CSS Modules (fournis par Vite). B. Un framework utilitaire compilé au build (type Tailwind). C. Une bibliothèque de composants à CSS-in-JS à l'exécution, avec ADR (CSP élargie).
- **Recommandation** : A ou B ; C écarté, pour garder la CSP stricte (DV-15).
- **Bloque** : Sprint 3.

Décision du propriétaire (2026-09-23) : option A : stylage en CSS Modules — appliquée dans VII §37.3.

#### E21 — Application des décisions de ce rapport

- **Contexte** : **IX §57.5** : chaque décision est consignée, puis « l'ADR ou la mise à jour de spec correspondante est faite dans le Sprint 0 ». Plusieurs points (CF-01 à CF-25, E1 à E7, E11, E14, E17, E18) modifient `docs/spec/`. Aucune tâche T0.x n'est prévue pour cela, et T0.4 à T0.8 doivent s'appuyer sur une spec à jour.
- **Options** : A. Une PR dédiée juste après l'arbitrage (« T0.2b », éventuellement fusionnée avec T0.1c, E11), avant T0.4. B. Chaque décision appliquée dans la PR de la tâche T0.x qui la consomme (dispersion, relecture plus difficile). C. Application en fin de Sprint 0, après T0.8 (T0.4 à T0.8 rédigés sur une spec non corrigée).
- **Recommandation** : A.
- **Bloque** : T0.4 à T0.8.

Décision du propriétaire (2026-09-23) : option A : une PR dédiée avant T0.4, qui inclut T0.1c — appliquée par T0.2b (#66).

#### E22 — Accès de Claude Code à Docker en développement

- **Contexte** : T0.3 a montré que Claude Code a besoin de Docker sur le poste de développement, et ce besoin revient à chaque sprint (Compose local, tests, e2e). Pour T0.3, le compte de développement a été ajouté temporairement au groupe `docker`, ce qui équivaut à un accès root pour tout programme lancé sous ce compte. Le poste mélange en outre deux installations de Docker (section 3.A, Q-01). Rien dans la spec ne dit comment Claude Code accède à Docker en développement.
- **Options** :
  - A. Démarche progressive : **V0**, isolation réelle du poste et script `scripts/radar-dev` à sous-commandes fixes, seul point d'entrée autorisé ; **V1**, skill de projet décrivant l'usage de `radar-dev` ; **V2**, serveur MCP local qui n'appelle que `radar-dev`, conditionnel.
  - B. Serveur MCP dès le Sprint 1 (outil de plus à écrire avant d'en connaître le besoin).
  - C. Accès direct à `docker`, filtré par les permissions de Claude Code (filtre de commandes, sans cloisonnement).
- **Recommandation** : A. Le mécanisme d'isolation du poste relève d'un ADR, l'**ADR-0021**.
- **Bloque** : Sprint 1 (premier Compose local).

Décision du propriétaire (2026-09-23) : option A : V0 au Sprint 1 (#62, avec la mise en place du poste #61), V1 au Sprint 2 (#63), V2 au Sprint 3, conditionnel à un go décidé sur les bilans des Sprints 1 et 2 (#64) ; le mécanisme d'isolation est l'objet de l'ADR-0021 (accepté le 2026-09-23, parade (a)) — appliquée dans VIII §46.1, IX §54.3, §55.3, §55.4, VII §36.7 et `docs/planning.md` (T0.9, #60).

---

## 3. Résultats des vérifications (IX §57.4)

Vérifications jouées en **T0.3 (#6)** le 2026-09-23, sur le poste de développement, dans des conteneurs Docker
`linux/amd64` construits sur l'image de base recommandée par E16. Le planning (G1, §9) distingue les vérifications
**bloquantes** (V-04 à V-07) des vérifications **contournables par ADR** (V-01 à V-03, V-08). Les scripts utilisés sont
jetables, gardés hors du dépôt et jamais commités (**IX §57.4**) ; les extraits utiles à l'implémentation sont recopiés
ci-dessous. Aucun paquet, binaire ni modèle n'a été installé sur le poste hôte : tout est téléchargé et exécuté dans
les conteneurs.

### 3.A Environnement d'exécution

| Élément | Valeur |
|---|---|
| OS du poste | Ubuntu 24.04.5 LTS, x86_64, noyau 7.0.0-31-generic |
| Docker | client Docker Engine - Community 29.8.1 (`/usr/bin/docker`) ; **démon 29.6.1 fourni par le snap `docker` (Canonical, canal `latest/stable`)**, API 1.55, pilote `overlay2`, cgroup v2, racine `/var/snap/docker/common/var-lib-docker` |
| Compose | plugin v5.5.1 |
| Image de base | `python:3.12.14-slim-trixie` (Python 3.12.14, Debian 13.7 « trixie ») — c'est le tag vers lequel pointait `python:3.12-slim` au moment des tests |
| Digest de l'image (index multi-architecture) | `sha256:2f17fc044b579bab302c2e8054d3a686e2cb9a83de48e70534b94cd8ebbe06a9` |
| Digest du manifeste `linux/amd64` | `sha256:44ff437bba879d4941b710a369a8f19266aea34b29002807f0c487fabc9eec9b` (créé le 2026-09-19) |
| Plateforme | `--platform linux/amd64` explicite sur chaque `docker run`, exécution native (sans émulation) |

Dans toutes les commandes ci-dessous : `IMG=python:3.12.14-slim-trixie@sha256:2f17fc044b579bab302c2e8054d3a686e2cb9a83de48e70534b94cd8ebbe06a9`, `/w` est le dossier des scripts jetables (`~/radar-t03`) monté en lecture seule, et les options
`--root-user-action=ignore --disable-pip-version-check` de `pip` sont omises pour la lisibilité. Les volumes
`radar-t03-cache` et `radar-t03-restic` sont créés à la volée par `docker run`.

> Constat pour Q-01 : `docker version` montre un client `docker-ce` 29.8.1 mais un **démon installé par snap** (29.6.1).
> Les volumes nommés sont donc stockés sous `/var/snap/docker/common/var-lib-docker/volumes/`. V-04 a été jouée
> dans cette configuration ; elle est rejouée sur le VPS en pré-production de toute façon (issue #6).

### 3.B Synthèse

| # | Vérification | Attendu | Si échec | Résultat |
|---|---|---|---|---|
| V-01 | `paraphrase-multilingual-MiniLM-L12-v2` disponible dans `fastembed`, sur l'architecture cible (`amd64`, **IX décision 27**) | modèle chargé, 384 dimensions ; révision et empreinte sha256 du modèle notées pour épinglage au build | repli : autre modèle multilingue ≤ 384 dimensions supporté par fastembed, consigné dans l'ADR-0008 | **concluant** — fastembed 0.8.1, dimension 384 mesurée ; dépôt `qdrant/paraphrase-multilingual-MiniLM-L12-v2-onnx-Q`, révision `faf4aa42…` (détail en V-01) |
| V-02 | SQLite de l'image de base Python retenue (voir E16) | ≥ 3.35, FTS5 et JSON1 compilés | autre image de base ou wheel SQLite, consigné | **concluant** — SQLite 3.46.1 ; FTS5 et JSON1 prouvés par requêtes réelles |
| V-03 | `BEGIN IMMEDIATE` avec SQLAlchemy 2.x async et aiosqlite | transaction d'écriture ouverte en `IMMEDIATE`, mécanisme noté (gestion des transactions du driver) | proposition alternative, question au propriétaire | **concluant** — SQLAlchemy 2.0.54, aiosqlite 0.22.1 ; événements `connect` + `begin` sur `engine.sync_engine` ; verrou pris dès le `BEGIN`, pas en lecture seule |
| V-04 | WAL sur **volume nommé** Docker | `journal_mode=wal` effectif, fichiers `-wal` / `-shm` créés sur le volume | bloquant | **concluant** — `wal` effectif, `-wal` et `-shm` sur le volume ; 2 conteneurs pendant 75 s, 0 erreur ; `integrity_check` = `ok` |
| V-05 | restic en binaire statique pour l'architecture cible | version épinglée disponible | bloquant | **concluant** — restic 0.19.1 `linux_amd64`, sha256 et signature GPG contrôlés, `statically linked` |
| V-06 | onnxruntime et lingua pour l'architecture cible | wheels disponibles | bloquant | **concluant** — wheels binaires cp312 manylinux x86_64 : onnxruntime 1.30.0, lingua-language-detector 2.2.0 |
| V-07 | APScheduler 3.x sur Python 3.12 | dernière 3.x compatible, version notée | bloquant | **concluant** — APScheduler 3.11.3, `AsyncIOScheduler` déclenche le job |
| V-08 | Outils CI (analyse de secrets, audit backend et frontend) | outil retenu et version | outil équivalent, consigné | **concluant** — gitleaks 8.30.1 · pip-audit 2.10.1 · `npm audit` (npm 11.19.0, Node 24.21.0) |

### 3.C Détail par vérification

#### V-01 — Modèle d'embeddings dans fastembed

```sh
docker run --rm --platform linux/amd64 --name radar-t03-v01 -v ~/radar-t03:/w:ro -v radar-t03-cache:/cache $IMG \
  sh -c 'pip install -q fastembed && python /w/v01.py'
```

Le script charge `TextEmbedding(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2", cache_dir="/cache")`
deux fois (avec puis sans téléchargement), calcule trois embeddings, puis hache les fichiers du cache Hugging Face.

- **Versions** : fastembed 0.8.1, onnxruntime 1.30.0, huggingface_hub 1.32.0, tokenizers 0.23.2, numpy 2.5.3.
- **Sortie** (extrait) :

```text
description fastembed: {'model': 'sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2',
  'sources': {'hf': 'qdrant/paraphrase-multilingual-MiniLM-L12-v2-onnx-Q'}, 'model_file': 'model_optimized.onnx',
  'license': 'apache-2.0', 'size_in_GB': 0.22, 'dim': 384}
chargement (téléchargement compris): 9.41s
chargement (depuis le cache): 1.66s ; RSS après chargement (kB): 1059452
embed 3 textes: 0.023s ; dimension mesurée = (384,) dtype=float64
cosinus FR/EN (même sens) = 0.962 ; FR/autre = 0.210
RSS après embed (kB): 1060416 ; ru_maxrss (kB): 1263460
dépôt HF en cache: /cache/models--qdrant--paraphrase-multilingual-MiniLM-L12-v2-onnx-Q
  ref main = faf4aa4225822f3bc6376869cb1164e8e3feedd0
```

- **Mesures indicatives pour M1** (un seul processus, CPU, sans limite mémoire) : chargement 1,7 s depuis le cache ;
  mémoire résidente d'environ 1,0 Gio après chargement, pic à 1,2 Gio. Point d'attention pour R-10 (RAM du worker).
- **Conclusion** : concluant. Le modèle est servi par fastembed et produit des vecteurs de 384 dimensions. Le
  rapprochement FR/EN d'une même phrase (cosinus 0,96) confirme le caractère multilingue.

> **À reprendre dans l'ADR-0008**
>
> - Nom du modèle dans fastembed : `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2`, licence Apache-2.0, 384 dimensions.
> - Dépôt Hugging Face réellement téléchargé : **`qdrant/paraphrase-multilingual-MiniLM-L12-v2-onnx-Q`** (conversion ONNX
>   publiée par Qdrant, fichier `model_optimized.onnx`), et non le dépôt `sentence-transformers` d'origine.
> - Révision (commit, `refs/main` au 2026-09-23) : **`faf4aa4225822f3bc6376869cb1164e8e3feedd0`**.
> - Empreintes sha256 des fichiers de cette révision :
>
>   | Fichier | Taille (octets) | sha256 |
>   |---|---|---|
>   | `model_optimized.onnx` | 235 052 644 | `634d0f66c29dc934c8fa72b8a4fe91dd4d420a22f1d82a241058d4316e659a99` |
>   | `tokenizer.json` | 17 083 009 | `fa685fc160bbdbab64058d4fc91b60e62d207e8dc60b9af5c002c5ab946ded00` |
>   | `config.json` | 673 | `c8ec081fdad2df991bf5abbf18418fec7a5cdaa421f60ffb060a30040b8c376f` |
>   | `special_tokens_map.json` | 964 | `8c785abebea9ae3257b61681b4e6fd8365ceafde980c21970d001e834cf10835` |
>   | `tokenizer_config.json` | 1 416 | `0666eebf692422757e1dddf3c9fb1ded73ba3dc726c5828671fc89e45bf3609f` |
>
> - Versions testées : fastembed 0.8.1, onnxruntime 1.30.0, sur `python:3.12.14-slim-trixie` `linux/amd64`.
> - fastembed renvoie des vecteurs `float64` : le type de stockage (par exemple `float32`) est à fixer avec le modèle SQL (T0.4).
> - Mesures indicatives : chargement 1,7 s depuis le cache, RSS ≈ 1,0 Gio, pic ≈ 1,2 Gio.

#### V-02 — SQLite de l'image

```sh
docker run --rm --platform linux/amd64 --name radar-t03-v02 -v ~/radar-t03:/w:ro $IMG python /w/v02.py
```

Le script crée une table `CREATE VIRTUAL TABLE docs USING fts5(title, body)`, y insère une ligne, l'interroge par
`MATCH`, puis exécute `json_extract('{"a":{"b":[1,2,3]}}', '$.a.b[2]')`, le tout avec le module `sqlite3` de l'image.

- **Versions** : Python 3.12.14, SQLite 3.46.1 (bibliothèque liée au module `sqlite3` de l'image).
- **Sortie** :

```text
python 3.12.14
sqlite_version 3.46.1
fts5 MATCH [('Radar',)]
json_extract (3,)
compile_options ['ENABLE_FTS3', 'ENABLE_FTS3_PARENTHESIS', 'ENABLE_FTS3_TOKENIZER', 'ENABLE_FTS4', 'ENABLE_FTS5', 'THREADSAFE=1']
```

- **Conclusion** : concluant. 3.46.1 ≥ 3.35 ; FTS5 est compilé et fonctionne ; JSON1 fonctionne (il est intégré
  d'office depuis SQLite 3.38, d'où l'absence d'option de compilation dédiée).

#### V-03 — `BEGIN IMMEDIATE` avec SQLAlchemy 2.x async et aiosqlite

```sh
docker run --rm --platform linux/amd64 --name radar-t03-v03 -v ~/radar-t03:/w:ro $IMG \
  sh -c 'pip install -q "sqlalchemy>=2,<3" aiosqlite && python /w/v03.py'
docker run --rm --platform linux/amd64 --name radar-t03-v03alt -v ~/radar-t03:/w:ro $IMG \
  sh -c 'pip install -q "sqlalchemy>=2,<3" aiosqlite && python /w/v03_alt.py'
```

- **Versions** : SQLAlchemy 2.0.54, aiosqlite 0.22.1, SQLite 3.46.1, Python 3.12.14.
- **Mécanisme documenté** : documentation SQLAlchemy 2.0, dialecte SQLite, section *Enabling Non-Legacy SQLite
  Transactional Modes with the sqlite3 or aiosqlite driver* (ancre `sqlite_enabling_transactions`), variante
  *Using SQLAlchemy to emit BEGIN in lieu of SQLite's transaction control (all Python versions, sqlite3 and aiosqlite)* :
  l'événement `connect` met `dbapi_connection.isolation_level = None` (le driver n'émet plus de `BEGIN`), l'événement
  `begin` émet le `BEGIN` lui-même ; en asyncio, les deux écouteurs se posent sur `engine.sync_engine`. La section
  *Serializable isolation / Savepoints / Transactional DDL (asyncio version)* du dialecte aiosqlite renvoie à celle-ci.
- **Recette testée** (adaptation : `BEGIN IMMEDIATE` par défaut, `BEGIN DEFERRED` pour une connexion marquée lecture seule ;
  le nom de l'option `readonly` est une proposition, à fixer en T0.4) :

```python
engine = create_async_engine("sqlite+aiosqlite:////data/radar.db", connect_args={"timeout": 5})

@event.listens_for(engine.sync_engine, "connect")
def _connect(dbapi_connection, connection_record):
    dbapi_connection.isolation_level = None          # aiosqlite n'émet plus de BEGIN

@event.listens_for(engine.sync_engine, "begin")
def _begin(conn):
    mode = "DEFERRED" if conn.get_execution_options().get("readonly") else "IMMEDIATE"
    conn.exec_driver_sql(f"BEGIN {mode}")

read_only = engine.execution_options(readonly=True)   # moteur des sessions de lecture seule
```

- **Protocole** : deux moteurs indépendants A et B sur le même fichier en WAL. Une sonde `sqlite3` tierce tente
  `BEGIN IMMEDIATE` avec `timeout=0` pour lire l'état du verrou d'écriture sans attendre.
- **Sortie** :

```text
sqlalchemy 2.0.54 | aiosqlite 0.22.1 | sqlite 3.46.1

[1] A ouvre une transaction (AsyncSession) et ne fait qu'un SELECT, B tente BEGIN (timeout 1 s)
  A : transaction ouverte, aucune écriture ; sonde : verrou d'écriture PRIS (database is locked)
  B : échec sur BEGIN après 1.00s -> OperationalError: database is locked

[2] B attend : A garde le verrou 2 s puis valide ; B (timeout 10 s) mesure la durée de son BEGIN
  B : BEGIN IMMEDIATE obtenu après 1.73s (bloqué dans le BEGIN, avant toute écriture)

[3] Session de lecture seule (execution_options readonly=True -> BEGIN DEFERRED)
  lecture ouverte, lignes = ['A', 'B'] ; sonde : verrou d'écriture LIBRE
  écrivain A : BEGIN IMMEDIATE + INSERT + COMMIT en 0.012s pendant la lecture
  lecture seule toujours cohérente (instantané WAL) : 2
  lecture seule OK en 0.001s, count=3 (ne voit pas A3 non validé)

[4] Témoin sans la recette (comportement par défaut du driver) : B passe son BEGIN, échoue à la 1re écriture
  B (défaut) : begin() réussi — aucun BEGIN émis
  B (défaut) : SELECT réussi
  B (défaut) : échec seulement à l'INSERT -> database is locked
```

- **Autres mécanismes de la même section, écartés** (`v03_alt.py`) : ni `connect_args={"isolation_level": "IMMEDIATE"}`
  (mode historique du driver), ni `connect_args={"autocommit": False}` (mode Python 3.12, le plus récent documenté) ne
  prennent le verrou au `begin()` : le `BEGIN` n'est émis qu'avec la première écriture (ou reste `DEFERRED`).

```text
connect_args isolation_level='IMMEDIATE' (legacy) verrou après begin+SELECT: LIBRE | après INSERT: PRIS
connect_args autocommit=False (Python 3.12)      verrou après begin+SELECT: LIBRE | après INSERT: PRIS
```

- **Conclusion** : concluant. Avec les écouteurs `connect` et `begin` sur `engine.sync_engine`, la connexion B échoue
  (ou attend, selon son `timeout`) **dès son `BEGIN`**, alors que A n'a encore rien écrit ; une session de lecture seule
  (`BEGIN DEFERRED`) ne prend pas le verrou et ne bloque pas les écrivains. Limite notée par la documentation : cette
  recette est incompatible avec le mode `AUTOCOMMIT` de SQLAlchemy au niveau du driver.

#### V-04 — WAL sur volume nommé, deux conteneurs

```sh
docker volume create radar-t03-data
R="docker run --platform linux/amd64 -v radar-t03-data:/data -v $HOME/radar-t03:/w:ro"
$R --rm --name radar-t03-init   $IMG python /w/v04_init.py          # PRAGMA journal_mode=wal + table
$R -d   --name radar-t03-worker $IMG python /w/v04_writer.py 75     # écrit en boucle (rôle worker)
$R -d   --name radar-t03-app    $IMG python /w/v04_reader.py 75     # lit en boucle (rôle app)
docker run --rm --platform linux/amd64 -v radar-t03-data:/data:ro --name radar-t03-ls $IMG ls -la /data
$R --rm --name radar-t03-check  $IMG python /w/v04_check.py          # après l'arrêt des deux conteneurs
```

L'écrivain enchaîne des transactions `BEGIN IMMEDIATE` de 10 `INSERT` ; le lecteur enchaîne des transactions de lecture
(`count(*)` et 50 dernières lignes). Les deux utilisent `PRAGMA busy_timeout=5000` et comptent toute
`OperationalError`, dont « database is locked ».

- **Versions** : SQLite 3.46.1 de l'image ; volume `local`, point de montage hôte
  `/var/snap/docker/common/var-lib-docker/volumes/radar-t03-data/_data`.
- **Sortie** (extraits) :

```text
journal_mode ('wal',)
['radar.db', 'radar.db-shm', 'radar.db-wal']
--- pendant l'exécution, vu depuis un 3e conteneur :
-rw-r--r-- 1 root root  901120 Sep 23 15:02 radar.db
-rw-r--r-- 1 root root   32768 Sep 23 15:02 radar.db-shm
-rw-r--r-- 1 root root 4120032 Sep 23 15:02 radar.db-wal
radar-t03-app Up 6 seconds
radar-t03-worker Up 7 seconds
writer journal_mode wal
writer: 7820 transactions (78200 lignes) en 75.0s, erreurs=0
reader: 4138 lectures en 75.0s, dernier count=78200, erreurs=0
journal_mode wal
integrity_check ok
count 78200
```

- **Conclusion** : concluant. Le mode WAL est persistant sur le volume nommé, les fichiers `-wal` et `-shm` y sont
  créés et visibles depuis un autre conteneur. Deux conteneurs ont écrit et lu en même temps pendant 75 s sans aucune
  erreur (aucun « database is locked »), et `PRAGMA integrity_check` renvoie `ok`. À la fermeture de la dernière
  connexion, SQLite fait un checkpoint et supprime `-wal` et `-shm` : comportement normal. Rejouée sur le VPS en
  pré-production (seule vérification dépendante de l'hôte Docker).

#### V-05 — restic statique `linux_amd64`

```sh
docker run --rm --platform linux/amd64 --name radar-t03-v05dl -v ~/radar-t03:/w:ro -v radar-t03-restic:/out $IMG sh /w/v05.sh
docker run --rm --platform linux/amd64 --name radar-t03-v05 -v radar-t03-restic:/opt/restic:ro $IMG /opt/restic/restic version
```

`v05.sh` installe `file`, `bzip2` et `gnupg` dans le conteneur, lit la dernière release sur l'API GitHub
(`repos/restic/restic/releases/latest`), télécharge `restic_<v>_linux_amd64.bz2`, `SHA256SUMS` et `SHA256SUMS.asc`,
contrôle l'empreinte (`sha256sum -c`), vérifie la signature GPG de `SHA256SUMS` (clé récupérée sur
`keyserver.ubuntu.com`), décompresse puis lance `file`. Le binaire est ensuite exécuté dans un conteneur neuf de l'image.

- **Version** : restic **0.19.1** (dernière release au 2026-09-23), compilé avec Go 1.26.4.
- **Sortie** (extraits) :

```text
dernière release : v0.19.1
restic_0.19.1_linux_amd64.bz2: OK
f415415624dcc452f2a02b8c33641791a8c6d6d3b65bbb3543fcf9a25151585c  restic_0.19.1_linux_amd64.bz2
gpg: Good signature from "Alexander Neumann <alexander@bumpern.de>" [unknown]
Primary key fingerprint: CF8F 18F2 8445 7597 3F79  D4E1 91A6 868B D3F7 A907
20d4142678d0d95ec11a4759def1b73fd9190abc9ca19e4b62d067c0b387e639  restic
restic: ELF 64-bit LSB executable, x86-64, version 1 (SYSV), statically linked, Go BuildID=…, stripped
restic 0.19.1 compiled with go1.26.4 on linux/amd64
```

- **Conclusion** : concluant. Version à épingler : 0.19.1 ; sha256 de l'archive `.bz2`
  `f415415624dcc452f2a02b8c33641791a8c6d6d3b65bbb3543fcf9a25151585c` (conforme au `SHA256SUMS` signé de la release),
  sha256 du binaire décompressé `20d4142678d0d95ec11a4759def1b73fd9190abc9ca19e4b62d067c0b387e639`. Le binaire est
  lié statiquement et s'exécute dans l'image sans dépendance. La clé GPG n'est pas certifiée par une chaîne de confiance
  locale (« [unknown] ») : son empreinte est celle publiée par le projet restic.

#### V-06 — Wheels onnxruntime et lingua

```sh
docker run --rm --platform linux/amd64 --name radar-t03-v06 -v ~/radar-t03:/w:ro $IMG sh -c '
  pip download -q --only-binary=:all: --no-deps -d /tmp/wh onnxruntime lingua-language-detector && ls /tmp/wh &&
  pip install -q --only-binary=:all: /tmp/wh/*.whl onnxruntime lingua-language-detector && python /w/v06.py'
```

`--only-binary=:all:` interdit toute compilation depuis les sources : l'installation échoue si aucune wheel ne
correspond. Le script importe les deux paquets, liste les fournisseurs d'exécution d'onnxruntime et détecte la langue
de trois phrases.

- **Versions** : onnxruntime **1.30.0**, lingua-language-detector **2.2.0**.
- **Sortie** :

```text
lingua_language_detector-2.2.0-cp312-cp312-manylinux_2_17_x86_64.manylinux2014_x86_64.whl
onnxruntime-1.30.0-cp312-cp312-manylinux_2_28_x86_64.whl
onnxruntime 1.30.0 | providers ['AzureExecutionProvider', 'CPUExecutionProvider'] | device CPU
lingua-language-detector 2.2.0
  Language.FRENCH <- Le radar suit les modèles de langage.
  Language.ENGLISH <- The radar tracks language models.
  Language.GERMAN <- Das Radar verfolgt Sprachmodelle.
```

- **Conclusion** : concluant. Les deux paquets existent en wheels binaires `cp312` `manylinux` `x86_64`, compatibles
  avec la glibc de Debian trixie (manylinux 2.28 requis pour onnxruntime), et fonctionnent dans l'image.

#### V-07 — APScheduler 3.x sur Python 3.12

```sh
docker run --rm --platform linux/amd64 --name radar-t03-v07 -v ~/radar-t03:/w:ro $IMG sh -c '
  pip index versions apscheduler --pre | head -2
  pip install -q "apscheduler>=3,<4" && python -W error::DeprecationWarning /w/v07.py'
```

Le script crée un `AsyncIOScheduler(timezone="UTC")`, ajoute un job coroutine à intervalle d'une seconde
(`max_instances=1`, `coalesce=True`), démarre le scheduler dans la boucle asyncio, attend 3,5 s puis l'arrête.
Les `DeprecationWarning` sont transformés en erreurs.

- **Versions** : APScheduler **3.11.3** (dernière 3.x ; la branche 4.0 n'existe qu'en pré-versions, 4.0.0a6),
  tzlocal 5.4.4, Python 3.12.14.
- **Sortie** :

```text
apscheduler (4.0.0a6)
Available versions: 4.0.0a6, 4.0.0a5, 4.0.0a4, 4.0.0a3, 4.0.0a2, 4.0.0a1, 3.11.3, 3.11.2, …
python 3.12.14 | apscheduler 3.11.3 | tzlocal 5.4.4
  job exécuté #1
  job exécuté #2
  job exécuté #3
3 exécutions en 3.6s ; running=False
```

- **Conclusion** : concluant. APScheduler 3.11.3 fonctionne sous Python 3.12 avec `AsyncIOScheduler`, sans
  avertissement de dépréciation. À épingler en `<4` : `pip install apscheduler --pre` installerait la 4.0 alpha,
  dont l'API est différente.

#### V-08 — Outils de CI

```sh
# analyse de secrets : image officielle, dépôt monté en lecture seule, historique complet
docker run --rm --platform linux/amd64 --name radar-t03-gitleaks -v "$PWD":/repo:ro \
  -e GIT_CONFIG_COUNT=1 -e GIT_CONFIG_KEY_0=safe.directory -e GIT_CONFIG_VALUE_0=/repo \
  ghcr.io/gitleaks/gitleaks:latest git /repo --redact --no-banner -v
# audit backend : dans l'image, sur les dépendances vérifiées ici
docker run --rm --platform linux/amd64 --name radar-t03-pipaudit -v ~/radar-t03:/w:ro $IMG \
  sh -c 'pip install -q pip-audit && pip-audit -r /w/requirements-t03.txt --progress-spinner off'
# audit frontend : image Node LTS officielle, package.json jetable (react, react-dom, vite, typescript, @vitejs/plugin-react)
docker run --rm --platform linux/amd64 --name radar-t03-npm -v ~/radar-t03/front:/src:ro node:lts-slim \
  sh -c 'cp /src/package.json /tmp/ && cd /tmp && npm install --package-lock-only && npm audit --audit-level=high'
```

`requirements-t03.txt` : `fastembed`, `sqlalchemy>=2,<3`, `aiosqlite`, `apscheduler>=3,<4`, `onnxruntime`,
`lingua-language-detector`. Le dépôt ne contient encore ni `pyproject.toml` ni `package.json` (**IX §57.6**) : les
audits portent sur un jeu jetable, pour valider les outils et non les dépendances finales.

- **Sorties** (extraits) :

```text
v8.30.1                                   # gitleaks version
INF 27 commits scanned.
INF scanned ~1030398 bytes (1.03 MB) in 1.93s
INF no leaks found                        # code de sortie 0
pip-audit 2.10.1
No known vulnerabilities found            # code de sortie 0
node v24.21.0 npm 11.19.0
found 0 vulnerabilities                   # code de sortie 0
```

| Rôle | Outil retenu | Version | Justification |
|---|---|---|---|
| Analyse de secrets | gitleaks (image `ghcr.io/gitleaks/gitleaks`, digest `sha256:c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f`) | 8.30.1 | binaire unique, image officielle, parcourt tout l'historique git en lecture seule, code de sortie ≠ 0 en cas de fuite |
| Audit backend | pip-audit (PyPA) | 2.10.1 | outil de la PyPA, base OSV / PyPI Advisory, audite un fichier d'exigences ou l'environnement installé |
| Audit frontend | `npm audit` (image `node:lts-slim`, digest `sha256:0e0ff40c39bc087845bfb27465a0df4ea419520094bc35842ff83dd8cbe6f9b6`) | npm 11.19.0, Node 24.21.0 | intégré à npm, aucune dépendance supplémentaire, seuil réglable par `--audit-level` |

- **Conclusion** : concluant. Les trois outils tournent en conteneur sur `linux/amd64` et rendent un code de sortie
  exploitable par la CI. Les versions (et tags d'image) sont à épingler dans les workflows du Sprint 1.

---

## 4. Risques identifiés

Probabilité et impact : faible · moyen · élevé.

| # | Risque | Sprint | Probabilité | Impact | Parade proposée |
|---|---|---|---|---|---|
| R-01 | La Partie VII non réconciliée (E11) est lue telle quelle pendant l'implémentation : `.env.example` sans `HTTP_TEST_ALLOW_HOSTS`, racine en lecture seule reportée au Sprint 11, rollback et backup sans verrou | 1, 2, 11 | **levé** le 2026-09-23 : E11 tranché, Partie VII réconciliée (T0.1c dans T0.2b, #67) | — | aucune : les 12 impacts CF-01 à CF-12 sont reportés dans la Partie VII |
| R-02 | Conflits de spec laissés ouverts (CF-15 à CF-25) et implémentés selon une seule des deux lectures | 1 à 11 | **levé** le 2026-09-23 pour CF-15 à CF-25 : tranchés et appliqués par T0.2b (#67) ; risque résiduel faible sur les conflits découverts ensuite | moyen | tout nouveau conflit est signalé, pas tranché (VIII §51.3), puis appliqué dans une PR de spec |
| R-03 | `BEGIN IMMEDIATE` difficile à obtenir avec SQLAlchemy async et aiosqlite (V-03) : échecs immédiats « database is locked » entre les deux processus | 1 | moyenne | élevé | V-03 en T0.3 ; T-DB-04 dès le Sprint 1 ; repli documenté par question au propriétaire |
| R-04 | Racine en lecture seule incompatible avec un cache ou un fichier temporaire d'onnxruntime, de fastembed ou de lingua | 1, 4 | moyenne | moyen | chemins de cache explicites vers `/tmp` (tmpfs) ou l'image ; T-SEC-09 joué dès l'arrivée de chaque bibliothèque |
| R-05 | Échec d'une vérification bloquante de §57.4 (V-04 à V-07) | 0 | faible | élevé | arrêt, ADR et replanification (planning G1) |
| R-06 | Le mécanisme de traçabilité (E1) rend la CI rouge dès le Sprint 1, ou au contraire ne contrôle plus rien | 1 | faible : E1 tranché (#67), précisé par P-15 (#71) — seuls les sprints clos bloquent | moyen | tester `check-test-catalog.py` sur le catalogue réel dès le Sprint 1 ; tenir à jour le statut de chaque `sprint-NN.md` (P-11) |
| R-07 | Extraction des identifiants de test fragile : une retouche de mise en forme de **VIII §50.5** casse `check-test-catalog.py` | 1 à 11 | moyenne | faible | motif d'extraction simple (`T-[A-Z]+-\d{2}` en première colonne) et test du script lui-même |
| R-08 | Durée de la CI : e2e Compose et build des images dans GitHub Actions dépassent la cible de 10 min (**VIII §49.3**) | 1, 4 | moyenne | faible | e2e seulement sur `main` et en nightly (**VIII décision 12**) ; caches uv, npm, couches Docker |
| R-09 | Reddit bloque les IP de datacenter (**IV §15.4**) : canal perdu en pré-production | pré-prod | moyenne | moyen | traiter comme une panne de source ; mode API reporté en V2 ; le constater tôt sur le VPS |
| R-10 | RAM du worker (modèle d'embeddings, lingua, matrice) au-delà de la cible sur le VPS prévu (M1) | 4, pré-prod | moyenne | moyen | M1 indicative au Sprint 4 ; VPS provisionné tôt pour jouer `radar-load` (planning §7) |
| R-11 | Seuils de clustering inadaptés aux données réelles : bruit ou sous-regroupement jusqu'à la calibration | 4, pré-prod | élevée | moyen | `cluster-calibrate` sur 72 h réelles (**VIII §47.4**) ; recalage unique J7–J10 |
| R-12 | Accès provider indisponible pour enregistrer les sorties LLM réelles (E8) : T-LLM-16 rouge | 7, 8 | moyenne | moyen | option B de E8 (scinder T-LLM-16) décidée d'avance comme repli |
| R-13 | Gabarits `webpage` cassés par un changement du site suivi | 2, exploitation | élevée | faible | run `failed` sur liste vide (**IV §15.4**) ; fixtures de gabarit cassé (T-COL-01) |
| R-14 | Stack nouvelle pour le propriétaire (asyncio, SQLAlchemy async, React) : relecture ligne à ligne plus longue que prévu | 1 à 3 | élevée | moyen | tampon de 25 % du planning ; recalage obligatoire après les Sprints 1 et 4 (planning §8) |
| R-15 | Perte de `RESTIC_PASSWORD` ou du `.env` : backups inutilisables | 11, exploitation | faible | élevé | copie hors VPS obligatoire (**VII §38.2, §43.4**) ; exercice de restauration M7 sur machine neuve |
| R-16 | Dépendances et références vers des documents absents du dépôt (V0.3 §25, E18) | 6 | élevée | faible | trancher E18 ; tout renvoi de la spec pointe vers un fichier du dépôt |

---

## 5. Questions ouvertes

Aucune question ouverte au 2026-09-23 (**IX §57.5**). Les questions posées par ce rapport restent ci-dessous, avec la
réponse du propriétaire.

### 5.A Questions répondues

#### Q-01 — Poste de développement

- **Question** : sur quel système travaillez-vous en développement (Linux, macOS, Windows avec WSL) et avec quelle version de Docker et de Compose ?
- **Pourquoi** : `/data` en volume nommé (**IX décision 26**), autorité interne de Caddy sur `https://localhost` (**VIII décision 3**), vérification V-04 dans les mêmes conditions que votre poste.
- **Utile pour** : T0.3, T0.5, Sprint 1.

Décision du propriétaire (2026-09-23) : Ubuntu 24.04.5 LTS, x86_64, démon Docker fourni par le snap (constat de la section 3.A), dont le nettoyage est suivi en #61 — consignée seulement.

#### Q-02 — Texte de la V0.3

- **Question** : disposez-vous du texte de la V0.3, en particulier du §25 (choix du gateway, check-list de mesure) ?
- **Pourquoi** : les renvois « V0.3 §25 » de **V-A §25** et **VII §45.4** pointaient vers un document absent du dépôt (E18).
- **Utile pour** : E18, Sprint 6.

Décision du propriétaire (2026-09-23) : la V0.3 a été retrouvée ; ses points utiles sont repris par E18 (gateways candidats, consigne « déployable séparément ») — appliquée dans VII §45.4 et V-A §25.

#### Q-03 — Valeur de `HTTP_CONTACT`

- **Question** : quelle valeur de `HTTP_CONTACT` (URL ou adresse de contact) utiliser, y compris dans le `.env` de développement ?
- **Pourquoi** : le worker refuse de démarrer sans elle (**IV §22**) et elle figure dans chaque User-Agent.
- **Utile pour** : Sprint 1.

Décision du propriétaire (2026-09-23) : `HTTP_CONTACT=https://github.com/qsjk/ai-tech-radar` comme valeur d'exemple — appliquée dans VII §36.7.

#### Q-04 — Contenu de `config/` au Sprint 1

- **Question** : quelles sources, topics et entités mettre dans le `config/` du dépôt au Sprint 1 : un jeu de démonstration minimal, ou déjà un extrait de votre curation ?
- **Pourquoi** : `validate-config` tourne en CI dès le Sprint 1 sur le `config/` du dépôt (**VIII §49.2**, T-CFG-01) ; le planning ne démarre la curation qu'au Sprint 2.
- **Utile pour** : T0.5, T0.8.

Décision du propriétaire (2026-09-23) : un `config/` de démonstration minimal au Sprint 1 — consignée seulement, reprise en T0.8.

#### Q-05 — Annexes du planning

- **Question** : faut-il corriger aussi les annexes A et B de `docs/planning.md`, qui citent `docs/spec/SPEC-V0.4.md` (fichier qui n'existe pas dans le dépôt) ?
- **Pourquoi** : la consigne de T0.2 limitait la mise à jour du planning à C11, E9 et la fiche S0.
- **Utile pour** : planning.

Décision du propriétaire (2026-09-23) : oui, les annexes A et B sont corrigées — appliquée dans `docs/planning.md`, annexes A et B.
