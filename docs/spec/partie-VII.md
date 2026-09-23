# Partie VII — Ops & Production

> **Partie VII — Ops & Production.** Version durcie issue de la revue §35–§45.
> Dernière révision : 2026-09-23. Prend les Parties I, II, III, IV, V-A, V-B et VI durcies comme acquis.

> **Nature de cette partie** : essentiellement une **consolidation**. Les décisions Ops fléchées par les Parties I à VI sont rassemblées ici ; les doublons et contradictions sont réconciliés (§ « Réconciliations ») ; seul ce qui manquait est durci à neuf.

> **Déjà tranché ailleurs, non repris ici** : deux processus applicatifs sans IPC, coordination par la base (Partie II §8.2) · un seul écrivain par table et par clé `SystemState` (II §8.3, III §11.13) · travail CPU hors event-loop, coalescence des misfires, requalification des `processing` au boot (II §8.4, §9.2) · configuration SQLite de chaque connexion, `BEGIN IMMEDIATE`, prérequis vérifiés au démarrage (III §10) · rétention des données métier (III §13) · client HTTP partagé, masquage de `Authorization` (IV §21.1) · disjoncteur LLM, budget, `SystemState.llm_gateway` / `llm_usage` / `embeddings` (V-A §24) · périmètre basic_auth, anti-CSRF, séquence d'envoi des alertes, `Setting` (VI §32–§34).

---

## Décisions tranchées dans cette revue (Partie VII)

1. **Topologie** : trois services permanents `caddy · app · worker`, un one-shot `migrate`, et `gateway` optionnel via un **profil Compose**. Le critère « ≤ 3–4 services » (Partie I §4.3) compte les services **permanents** ; `migrate` n'en fait pas partie.
2. **Une seule image backend** (`radar-backend:<git sha>`) pour `migrate`, `app` et `worker` ; une image `radar-caddy:<git sha>` qui embarque le build Vite. Le tag Git sert au rollback.
3. **Segmentation réseau** : `app` n'a **aucune sortie Internet** et n'est joignable que par Caddy ; `worker` **ne peut pas joindre** `app` ; `migrate` n'a aucun réseau.
4. **Moindre privilège des secrets** : chaque service ne reçoit que ses variables. **`app` ne reçoit aucun secret** (il lit l'état des canaux et du LLM dans `SystemState`).
5. **Conteneurs durcis** : utilisateur non-root, `no-new-privileges`, `cap_drop: ALL`, système de fichiers racine en lecture seule pour `app` et `worker`, **jamais de montage du socket Docker**.
6. **`depends_on` ne joue qu'au `docker compose up`** : au redémarrage du démon (reboot), `app` et `worker` repartent directement ; c'est la **vérification de schéma au démarrage** (III §10.1) qui protège, pas l'ordre Compose.
7. **Déploiement** : backup → arrêt de `app` et `worker` → `up -d` (qui rejoue `migrate`) → contrôle de santé. Jamais d'ancienne version qui tourne sur un schéma migré.
8. **Caddy** : un seul site, adresse = `DASHBOARD_URL` ; TLS Let's Encrypt automatique ; `/health` public, tout le reste sous basic_auth ; en-têtes de sécurité complétés (`frame-ancestors`, `base-uri`, `form-action`, `object-src`, `nosniff`, HSTS).
9. **Le modèle d'embeddings est intégré à l'image** au build (aucun téléchargement au runtime).
10. **Backup exécuté par le worker** (job planifié), via **`VACUUM INTO`** sur une connexion en lecture seule, contrôle d'intégrité de la copie, puis envoi par **restic** (chiffrement, rétention `7/4/3` native, backend S3-compatible ou SFTP au choix).
11. **Test de restauration mensuel automatisé** par le worker (`restore-test`), complété par un **exercice complet manuel** avant la mise en production.
12. **`/health` public** = `{"status": "ok" | "degraded" | "down"}`, **HTTP 200 / 200 / 503**. **`down`** = base inaccessible **ou** worker mort (heartbeat périmé). Le monitoring externe n'alerte que sur un code ≠ 200.
13. **Détail authentifié** = `GET /api/health`. Il coexiste avec `GET /api/status` (bandeau, Partie VI) ; les deux sont calculés par **le même module**.
14. **Heartbeat** : tâche dédiée du worker toutes les **30 s** ; périmé au-delà de **120 s**. Il démarre **avant** le chargement des modèles.
15. **Supervision fail-fast du worker** : si une tâche permanente (boucle AI, file d'embeddings, scheduler, heartbeat) meurt sur une exception non gérée, le worker **se termine** en erreur et Docker le relance. Un **watchdog** tue le processus si l'event-loop est gelée plus de 5 min. Conséquence : le heartbeat suffit à qualifier la santé du worker, il n'y a plus de champ `scheduler` distinct.
16. **Toutes les métriques et conditions sont calculées par le worker** (tâche `ops` toutes les 60 s) et écrites dans `SystemState`. L'app ne fait que les lire : aucun balayage coûteux dans une requête HTTP.
17. **Pas de Prometheus en V1** : les métriques sont exposées par `/api/health`, les tables d'historique et les logs.
18. **Alertes d'exploitation = nouveau type d'alerte `system`**, émises par le worker via la séquence d'envoi existante (VI §33.5). **Une alerte par épisode** (passage de la condition de faux à vrai), épisodes persistés. Elles **ignorent** `alerts.mode`, les heures calmes et le plafond quotidien. Routage par défaut : **Telegram et email**.
19. **Seuil d'alerte du disjoncteur LLM ouvert : 24 h** (hors `not_configured`). `LLMConfigError` alerte immédiatement. Moteur d'embeddings `down` : alerte après 15 min.
20. **Répartition des alertes** : le **worker** alerte sur tout ce qu'il peut observer ; le **monitoring externe** couvre ce que le worker ne peut pas signaler lui-même (worker mort, app morte, VPS ou Caddy tombés, certificat).
21. **« Container stopped »** (V0.3) n'est plus une métrique : chaque arrêt de conteneur est couvert par une détection existante (tableau §39.5), sans accès au socket Docker.
22. **Logs** : JSON sur stdout, **structlog**, rotation par le driver Docker (`10 Mo × 5` par service). Pas de fichier de log dans un volume. **Un seul access log** : celui de Caddy.
23. **Rédaction des secrets à trois niveaux**, dont un **nettoyage par valeur** qui remplace toute occurrence d'un secret configuré, y compris dans les URLs d'exceptions (le token Telegram figure dans l'URL de l'API). Le même nettoyage s'applique à `Source.last_error` et `AlertLog.error`.
24. **Garde anti-SSRF** dans le `HttpClient` (Partie IV §21.1) : refus des destinations privées, locales ou internes, vérifié après résolution DNS et à chaque redirection.
25. **`.env.example` unique** (§36.7), avec statut obligatoire / obligatoire en production / optionnel / réservé V2.
26. **« Estimated cost » LLM retiré en V1** : sans table de prix par provider, l'estimation serait fausse ; on suit requêtes et tokens.
27. **Check-list des mesures avant production** unique (§45.4), avec critère d'acceptation et effet de chaque mesure.

---

## Réconciliations

| Source du conflit | Avant | Tranché |
|---|---|---|
| V0.3 §36 | services `app · worker · caddy` | + `migrate` (one-shot), `gateway` en profil optionnel |
| Partie I §4.3 | « ≤ 3–4 services Docker » | compté en services **permanents** : 3, ou 4 avec `gateway` |
| V0.3 §40 | `/health` public détaillé, champ `scheduler` | public réduit à `{status}` ; détail en `/api/health` ; `scheduler` absorbé par `worker` (supervision fail-fast, décision 15) |
| V0.3 §39 | `container stopped → critical` | remplacé par le tableau de couverture §39.5 (pas de socket Docker) |
| V0.3 §39 | LLM `estimated cost` | retiré en V1 (décision 26) |
| V0.3 « Décisions » n° 5 | token unique + basic_auth | basic_auth seul, `DASHBOARD_TOKEN` supprimé (VI) |
| Partie VI §31.11 | `GET /api/status` (bandeau) | conservé tel quel ; `/api/health` ajouté ; même module de calcul |
| Partie II §9.4 | backup échoué : détection par `last_backup` périmé, relance manuelle | détection **et alerte** `system` ; reprise automatique au job suivant ; relance manuelle possible (`backup-now`) |
| V0.3 §42 | liste de champs à plat | mappée sur des champs structurés normalisés (§42.2) |

---


## 35. Stack

Consolidation des choix déjà faits, plus ce que cette partie ajoute (**en gras**). Toute version est **épinglée** (lockfiles, tags d'images précis).

| Couche | Choix |
|---|---|
| Langage | Python 3.12+ |
| API | FastAPI · uvicorn (**un seul processus**) · Pydantic v2 |
| Base | SQLite ≥ 3.35 (FTS5, JSON1) · SQLAlchemy 2.x async · aiosqlite · Alembic (`render_as_batch`) |
| Worker | asyncio · APScheduler **3.x** (`AsyncIOScheduler`) |
| Collecte | httpx · feedparser · trafilatura · lingua |
| Embeddings | fastembed (onnxruntime) · numpy |
| Logs | **structlog** (rendu JSON) |
| Backup | **restic** (binaire statique dans l'image backend) |
| Qualité | pytest · ruff · mypy |
| Dépendances | **uv** + `uv.lock` (backend) · npm + `package-lock.json` (frontend) |
| Frontend | React · TypeScript · Vite (choix ferme) |
| Infra | Linux · Docker · Docker Compose v2 · Caddy 2 |

- **uvicorn à un seul processus** : produit mono-utilisateur, et les compteurs en mémoire de l'app (§39) restent cohérents.
- **APScheduler 3.x** : la 4.x n'est pas stable ; migration éventuelle tracée en ADR.

## 36. Infra / VPS

### 36.1 Cible

- **Production recommandée** : `4 vCPU · 8 Go RAM · 40–100 Go NVMe`. Prototype possible sur `2 vCPU · 4 Go`. Le dimensionnement définitif découle de la mesure M1 (§45.4).
- **OS** : distribution Linux LTS (Debian stable ou Ubuntu LTS), mises à jour de sécurité automatiques (§43.1).
- **Horloge** : NTP actif sur l'hôte ; conteneurs en `TZ=UTC`.

### 36.2 Services

| Service | Image | Rôle | Réseaux | Ports publiés | Redémarrage |
|---|---|---|---|---|---|
| `caddy` | `radar-caddy:<sha>` | TLS, statique, reverse proxy | `edge`, `public` | 80, 443/tcp, 443/udp | `unless-stopped` |
| `migrate` | `radar-backend:<sha>` | `alembic upgrade head`, puis sortie | aucun (`network_mode: none`) | — | `no` |
| `app` | `radar-backend:<sha>` | FastAPI : `/api`, `/health` | `edge` | — (`expose: 8000`) | `unless-stopped` |
| `worker` | `radar-backend:<sha>` | scheduler, pipeline, AI, alertes, ops, backup | `egress` | — | `unless-stopped` |
| `gateway` | image épinglée du gateway retenu | gateway LLM auto-hébergé, **profil `gateway`** | `egress` | — | `unless-stopped` |

**Réseaux** :

- `edge` : `internal: true`. Seuls `caddy` et `app` y sont. **`app` n'a donc aucune sortie Internet** — il n'en a pas besoin : il n'appelle ni LLM, ni canal d'alerte, ni source.
- `public` : réseau par défaut de `caddy`, pour ACME et le trafic entrant.
- `egress` : réseau du `worker` (et du `gateway`). Le worker **ne peut pas joindre `app`**, ce qui supprime une cible d'SSRF interne.
- Avec un gateway auto-hébergé : `LLM_BASE_URL=http://gateway:<port>/v1`.

### 36.3 Ordre de démarrage

```
docker compose up -d
  migrate  ──(service_completed_successfully)──▶ app
           └────────────────────────────────────▶ worker
  caddy (indépendant ; 502 sur /api tant que app n'est pas prêt)
```

- `app` et `worker` déclarent `depends_on: migrate: condition: service_completed_successfully`.
- **Ni `app` ni `worker` ne migrent.** Chacun vérifie au démarrage que la révision en base est `head` et **refuse de démarrer** sinon (III §10.1).
- **Reboot du VPS** : le démon Docker relance `caddy`, `app`, `worker` (et `gateway`) **sans rejouer `migrate`** ni évaluer `depends_on`. C'est sans risque : le schéma n'a pas changé, et la vérification de révision reste le garde-fou.
- Échec de `migrate` → `app` et `worker` ne démarrent pas → `/health` injoignable (502) → monitoring externe.

### 36.4 Volumes

| Volume | Monté par | Contenu | Sauvegardé |
|---|---|---|---|
| `radar_data` (driver `local`) | `migrate`, `app`, `worker` sur `/data` | `radar.db`, `-wal`, `-shm`, `/data/backup/` (zone de préparation du backup) | la base, via §38 |
| `caddy_data` | `caddy` | certificats, compte ACME | non (réémissibles) — **ne jamais le supprimer en boucle** (limites Let's Encrypt) |
| `caddy_config` | `caddy` | configuration auto-sauvegardée | non |

- `radar_data` est **local**, jamais sur un système de fichiers réseau (III §10.4) : `-wal` et `-shm` doivent rester sur le même hôte que les processus.
- Le Dockerfile crée `/data` avec le propriétaire de l'utilisateur non-root.
- **Portabilité** (Partie I §4.3) : changer de VPS = restaurer le dernier backup (ou copier `radar.db` **à l'arrêt**) + `.env` + `docker compose up -d`.

### 36.5 Esquisse `docker-compose.yml`

Contractuelle sur la structure ; les détails (tags, chemins) sont à l'implémenteur. Les blocs `environment` sont **complets par service** (la fusion YAML n'est pas profonde).

```yaml
name: radar

x-backend: &backend
  image: radar-backend:${RADAR_VERSION:-dev}
  build: { context: ., dockerfile: docker/backend.Dockerfile }
  user: "10001:10001"
  read_only: true
  tmpfs: [/tmp]
  cap_drop: [ALL]
  security_opt: ["no-new-privileges:true"]
  volumes: [radar_data:/data]
  logging:
    driver: json-file
    options: { max-size: "10m", max-file: "5" }

services:
  migrate:
    <<: *backend
    command: ["alembic", "upgrade", "head"]
    environment: { TZ: UTC, RADAR_DB_PATH: /data/radar.db, LOG_LEVEL: "${LOG_LEVEL:-INFO}" }
    network_mode: none
    restart: "no"

  app:
    <<: *backend
    command: ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000",
              "--workers", "1", "--no-access-log"]
    environment:
      TZ: UTC
      RADAR_DB_PATH: /data/radar.db
      APP_ENV: "${APP_ENV:-production}"
      LOG_LEVEL: "${LOG_LEVEL:-INFO}"
      DASHBOARD_URL: "${DASHBOARD_URL}"
      RADAR_VERSION: "${RADAR_VERSION:-dev}"
    expose: ["8000"]
    networks: [edge]
    depends_on: { migrate: { condition: service_completed_successfully } }
    restart: unless-stopped

  worker:
    <<: *backend
    command: ["python", "-m", "app.worker"]
    environment:
      TZ: UTC
      RADAR_DB_PATH: /data/radar.db
      # + toutes les variables « worker » du §36.7, passées une à une
    networks: [egress]
    depends_on: { migrate: { condition: service_completed_successfully } }
    stop_grace_period: 30s
    restart: unless-stopped

  caddy:
    image: radar-caddy:${RADAR_VERSION:-dev}
    build: { context: ., dockerfile: docker/caddy.Dockerfile }   # multi-stage : build Vite → /srv
    ports: ["80:80", "443:443", "443:443/udp"]
    environment:
      DASHBOARD_URL: "${DASHBOARD_URL}"
      DASHBOARD_USER: "${DASHBOARD_USER}"
      DASHBOARD_PASSWORD_HASH: "${DASHBOARD_PASSWORD_HASH}"
      ACME_EMAIL: "${ACME_EMAIL:-}"
    volumes: [caddy_data:/data, caddy_config:/config]
    networks: [edge, public]
    cap_drop: [ALL]
    cap_add: [NET_BIND_SERVICE]
    logging: { driver: json-file, options: { max-size: "10m", max-file: "5" } }
    restart: unless-stopped

  gateway:
    profiles: [gateway]
    image: <gateway-retenu>:<version épinglée>
    networks: [egress]
    restart: unless-stopped

networks:
  edge: { internal: true }
  public: {}
  egress: {}

volumes:
  radar_data: { driver: local }
  caddy_data: {}
  caddy_config: {}
```

- **`mem_limit`** sur `worker` (et `gateway`) : fixé **après** la mesure M1, à pic mesuré × 1,5. Sans limite, l'OOM killer de l'hôte choisit sa victime.
- **Modèle d'embeddings** : téléchargé **au build** dans l'image (cache fastembed en lecture seule). Aucun accès à un hub de modèles au runtime.
- Le système de fichiers racine en lecture seule est actif dès le Sprint 1 et validé en continu (Partie VIII décision 4) ; le Sprint 11 confirme le cas de restic (Partie VIII §47.3). Le cache restic vit dans `/tmp` (tmpfs), la préparation du backup dans `/data/backup/`, jamais dans le tmpfs.

### 36.6 Cycle de vie du worker

- **Démarrage** : vérifications (III §10.1, `validate-config`, `HTTP_CONTACT`) → **heartbeat démarré** → requalification des `processing` et des `sending` → chargement des modèles (embeddings, lingua) → reconstruction de la matrice de similarité → scheduler.
- **Supervision fail-fast** : une tâche permanente qui meurt sur une exception non gérée → log `critical` → sortie en code non nul → redémarrage par Docker. Un job **planifié** en échec n'arrête pas le worker (il est compté, §39.5 `job_failing`).
- **Watchdog** : un thread surveille un horodatage rafraîchi toutes les 5 s par l'event-loop ; au-delà de `ops.watchdog_timeout` (300 s), log `critical` et arrêt immédiat du processus. Le travail CPU étant hors event-loop, un gel de cette durée est un bug.
- **Arrêt (SIGTERM)** : plus aucun nouveau claim ni nouveau run ; attente des jobs en cours jusqu'à 20 s ; le reste est requalifié au prochain boot (acquis). `stop_grace_period` = 30 s.

### 36.7 Variables d'environnement — `.env.example`

**Liste unique.** Les réglages fonctionnels vivent dans `config/pipeline.yaml` ou `Setting`, jamais ici ; les secrets vivent ici, jamais ailleurs.

```dotenv
# ── Obligatoire ─────────────────────────────────────────────────────────────
# Contact inclus dans le User-Agent. Absent → le worker refuse de démarrer.
HTTP_CONTACT=mailto:moi@example.com
# URL publique du dashboard, sans slash final : adresse du site Caddy,
# origine attendue par l'anti-CSRF, liens des alertes.
DASHBOARD_URL=https://radar.example.com
DASHBOARD_USER=souhaib
# Hash bcrypt (caddy hash-password). Guillemets simples OBLIGATOIRES :
# le hash contient des « $ » que Compose interpolerait.
DASHBOARD_PASSWORD_HASH='$2a$14$...'

# ── Requis par les sources GitHub (seul credential de collecte en V1) ───────
# Absent → sources github non planifiées, le worker démarre quand même.
GITHUB_TOKEN=

# ── Obligatoire en production : backup (§38) ───────────────────────────────
# Absent → backup « not_configured », /health dégradé.
RESTIC_REPOSITORY=           # ex. s3:https://<endpoint>/<bucket>/radar  ou  sftp:user@host:/radar
RESTIC_PASSWORD=             # à conserver AUSSI hors du VPS (gestionnaire de mots de passe)
AWS_ACCESS_KEY_ID=           # identifiants du backend restic choisi (S3-compatible ici)
AWS_SECRET_ACCESS_KEY=

# ── Optionnel : LLM (sans eux, le produit tourne sans LLM, à 0 €) ──────────
LLM_BASE_URL=
LLM_API_KEY=
LLM_MODEL=

# ── Optionnel : canaux d'alerte (canal désactivé si incomplet) ─────────────
# Au moins un canal est exigé pour la mise en production (Partie VIII).
SMTP_HOST=
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=
ALERT_EMAIL_TO=
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=

# ── Optionnel : technique ──────────────────────────────────────────────────
ACME_EMAIL=                  # contact Let's Encrypt
APP_ENV=production           # « development » réactive /docs ; « test » réservé aux tests ; défaut sûr = production
LOG_LEVEL=INFO
RADAR_VERSION=               # tag d'image (sha Git) déployé

# ── Réservé aux tests (surcharge e2e, jamais en production) ───────────────
# Lue seulement si APP_ENV=test ; renseignée avec APP_ENV=production → le worker
# refuse de démarrer (Partie VIII décision 23, Partie IV §21.1).
# HTTP_TEST_ALLOW_HOSTS=

# ── Réservé V2 (non lu en V1) ──────────────────────────────────────────────
# REDDIT_CLIENT_ID= REDDIT_CLIENT_SECRET= YOUTUBE_API_KEY=
```

**Distribution par service** (moindre privilège) :

| Service | Variables reçues |
|---|---|
| `caddy` | `DASHBOARD_URL` · `DASHBOARD_USER` · `DASHBOARD_PASSWORD_HASH` · `ACME_EMAIL` |
| `app` | `DASHBOARD_URL` · `APP_ENV` · `LOG_LEVEL` · `RADAR_VERSION` — **aucun secret** |
| `worker` | toutes les autres, sauf `DASHBOARD_USER` et `DASHBOARD_PASSWORD_HASH` |
| `migrate` | `LOG_LEVEL` |

- `DASHBOARD_URL` est validée au démarrage de `app` et `worker` : schéma `https` (ou `http://localhost` en développement), sans chemin ni slash final.
- `DASHBOARD_TOKEN` **n'existe plus** (Partie VI).

### 36.8 Commandes opérationnelles

Inventaire. Le contrat commun des commandes (codes de sortie `0` / `1` / `2`, stdout / stderr) et le mode d'exécution de chacune (`exec` ou `run --rm --no-deps`) sont fixés par la Partie IX §56.3–§56.4 ; leur mode d'emploi détaillé relève du runbook (Partie IX §56).

| Commande | Où | Rôle | Origine |
|---|---|---|---|
| `python -m app.cli validate-config` | worker (`run --rm --no-deps`), CI | valide les quatre fichiers `config/` | IV |
| `python -m app.cli cluster-calibrate` | worker | histogrammes et échantillons pour caler les seuils | V-B §28.14 |
| `python -m app.cli recount-events` | worker | recalcule les compteurs d'Event | V-B §28.9 |
| `python -m app.cli send-test-alert --channel <email\|telegram>` | worker | message de test, hors `AlertLog` | VI §33.10 |
| `python -m app.cli backup-now` | worker | backup immédiat (avant déploiement notamment) ; affiche le `snapshot_id` | **VII** · IX §56.4 |
| `python -m app.cli restore-test` | worker | test de restauration immédiat | **VII** |
| `python -m app.cli health` | app ou worker | affiche le détail de santé (utile en SSH) | **VII** |
| `python -m app.cli vacuum` | worker (`run --rm --no-deps`), worker arrêté | `VACUUM` manuel (§44.2) | IX §56.4.2 |
| `docker compose run --rm caddy caddy hash-password` | caddy | génère le hash bcrypt ; rotation = nouveau hash + `docker compose up -d caddy` | VI §32.1 |
| `docker compose run --rm migrate alembic current` | migrate | révision appliquée | III |

### 36.9 Déploiement

Contrat. La séquence est exécutée par `scripts/deploy.sh [<sha>]`, après le contrôle CI (workflow du sha vert, étape 6 comprise) : Partie VIII §49.5. La procédure détaillée et le rollback vont au runbook (Partie IX §56.6-P1, P2).

```
git checkout <sha> → docker compose build (tag = sha Git)
→ docker compose exec worker python -m app.cli backup-now   # point de retour garanti ; succès vérifié, snapshot_id journalisé
→ docker compose stop app worker          # aucune ancienne version sur un schéma migré
→ docker compose up -d                    # migrate, puis app et worker
→ contrôle : /health = ok, docker compose ps
```

- Coupure de quelques dizaines de secondes, acceptée (mono-utilisateur). Le monitoring externe exige deux échecs consécutifs (§41) : un déploiement normal ne déclenche pas d'alerte.
- **Rollback** : `scripts/deploy.sh <sha précédent>` quand aucune migration ne sépare les deux sha. Sinon, `deploy.sh` détecte la migration à défaire et **refuse** ; la procédure Partie IX §56.6-P2 s'applique : *downgrade* si les migrations sont réversibles, sinon **restauration du snapshot pris avant le déploiement** par `scripts/restore.sh` (§38.5). Toute migration Alembic fournit un `downgrade` ou se déclare irréversible dans son en-tête.
- On conserve **l'image courante et la précédente** ; les plus anciennes sont supprimées manuellement (§44).

## 37. HTTPS & Caddy

### 37.1 Rôle

Caddy est **le seul point d'entrée** : TLS, service du build statique, reverse proxy de `/api` et `/health` vers `app`. FastAPI ne sert pas la SPA (Partie II §8.1). Aucun autre service ne publie de port.

### 37.2 TLS

- Adresse du site = `DASHBOARD_URL` : Caddy obtient et renouvelle le certificat Let's Encrypt automatiquement, redirige HTTP vers HTTPS.
- Prérequis : enregistrement DNS A (et AAAA si IPv6) vers le VPS, ports 80 et 443 ouverts.
- `caddy_data` persistant (§36.4).
- En développement, `DASHBOARD_URL=https://localhost` utilise l'autorité interne de Caddy.

### 37.3 Esquisse `Caddyfile`

```caddyfile
{
	email {$ACME_EMAIL}
	# log_credentials NON activé : Authorization et Cookie restent masqués dans les logs
}

{$DASHBOARD_URL} {
	encode zstd gzip

	log {
		output stdout
		format json
	}
	log_skip /health

	header {
		Content-Security-Policy "default-src 'self'; img-src 'self' data:; object-src 'none'; base-uri 'self'; form-action 'self'; frame-ancestors 'none'"
		X-Frame-Options "DENY"
		Referrer-Policy "same-origin"
		X-Content-Type-Options "nosniff"
		Strict-Transport-Security "max-age=31536000"
		-Server
	}

	# Public : statut minimal uniquement
	handle /health {
		reverse_proxy app:8000
	}

	# Tout le reste : authentifié
	handle {
		basic_auth {
			{$DASHBOARD_USER} {$DASHBOARD_PASSWORD_HASH}
		}

		handle /api/* {
			request_body {
				max_size 1MB
			}
			reverse_proxy app:8000
		}

		handle {
			root * /srv
			@assets path /assets/*
			header @assets Cache-Control "public, max-age=31536000, immutable"
			header /index.html Cache-Control "no-cache"
			try_files {path} /index.html
			file_server
		}
	}
}
```

- **Portée du basic_auth** : `/` (SPA et ses assets) et `/api/*`, y compris `/api/health`. **Seul `/health` est exempté.**
- **CSP `default-src 'self'`** : le frontend n'injecte ni script ni balise `<style>` en ligne. Une bibliothèque qui en injecterait (CSS-in-JS à l'exécution) est interdite, sauf ADR élargissant `style-src`. Les attributs `style` posés par React passent par le CSSOM et ne sont pas bloqués.
- **Pas de CORS** : même origine (VI §32.2).
- **Cache** : `index.html` jamais mis en cache, assets hachés immuables — un déploiement n'affiche jamais une SPA périmée.

### 37.4 Côté FastAPI

- `/docs`, `/redoc`, `/openapi.json` **désactivés** sauf `APP_ENV=development` (défaut sûr).
- Anti-CSRF (VI §32.2) : middleware de l'app, pas de Caddy.
- `uvicorn --no-access-log` : l'access log de Caddy est le seul (§42.3).

## 38. Backup & restore

La base SQLite est la mémoire accumulée du produit. **Un backup jamais restauré n'est pas validé.**

### 38.1 Objectifs

- **RPO ≤ 24 h**. En pratique la perte est moindre : après une restauration, les collectors repartent de checkpoints plus anciens et la dédup exacte absorbe les recollectes dans la limite de `max_item_age` (30 j). Ce qui est réellement perdu : les actions utilisateur de la journée (lectures, préférences, décisions) et les contenus plus anciens que 30 jours.
- **RTO ≤ 1 h**, procédure manuelle.
- **Effet de bord accepté** : les `AlertLog` de la période perdue disparaissent, une alerte peut donc être réémise après restauration ; `alerts.max_age` (48 h) borne ce cas.

### 38.2 Mécanisme

Job `backup` du worker, exécuté **hors event-loop** :

1. Connexion SQLite **synchrone dédiée**, ouverte en lecture seule (`mode=ro`), hors du pool aiosqlite.
2. `VACUUM INTO '/data/backup/radar-<horodatage>.db'` : copie **cohérente**, compactée, en un seul fichier, sans `-wal`. **Jamais** de copie brute du fichier ouvert. `VACUUM INTO` est une lecture : il ne bloque pas les écrivains (WAL), mais il retarde le checkpoint pendant sa durée (mesure M3).
3. Sur la copie : `PRAGMA integrity_check` = `ok`, et révision Alembic = `head`. Sinon : échec.
4. `restic backup` de la copie (chiffrement et compression natifs), étiquette `radar-db`.
5. `restic forget --keep-daily 7 --keep-weekly 4 --keep-monthly 3 --prune`.
6. Suppression de la copie locale, **en succès comme en échec**.
7. Écriture de `SystemState` (écrivain unique : le worker) :
   - succès → `last_backup = {at, snapshot_id, size_bytes, duration_s}` ;
   - chaque tentative → `backup_last_attempt = {at, status, error}`.

- **Espace requis** : la copie locale occupe la taille de la base ; le seuil disque de 80 % garde cette marge (§44).
- **Verrou** : les jobs `backup` et `restore_test` et les commandes `backup-now` et `restore-test` prennent un verrou exclusif `/data/backup/.lock`. Un job qui le trouve pris s'abstient et le journalise, sans ouvrir de condition `backup_failed` ; une commande s'arrête avec le code `1` (Partie IX §56.4.1).
- **Rien d'autre n'est sauvegardé** : `config/` est dans Git ; les secrets ne sont ni en base, ni dans le backup ; `caddy_data` se régénère.
- **`RESTIC_PASSWORD`** chiffre le dépôt : sa perte rend tous les backups inutilisables. Il est conservé **hors du VPS**, avec le `.env`.

### 38.3 Planification et rétention

- Quotidien à `backup.time` (03:30 UTC), et **au démarrage du worker** si le dernier succès date de plus de 24 h (même logique de coalescence que les misfires).
- Rétention `7 daily · 4 weekly · 3 monthly`, appliquée par restic sur le stockage distant.
- **Stockage hors VPS obligatoire** : tout backend restic (S3-compatible, SFTP…). Le choix du fournisseur est un choix de déploiement, pas de spec ; cible de coût 0–1 €/mois (§45.1).
- `RESTIC_REPOSITORY` absent → composant `backup` en `not_configured`, `/health` dégradé. Le worker démarre quand même.

### 38.4 Test de restauration

**Automatisé mensuel** — job `restore_test` du worker, le 1er du mois à 04:30 UTC, et au démarrage si aucun succès depuis 35 jours :

```
restic restore latest → /data/backup/restore-test/
→ PRAGMA integrity_check = ok
→ alembic upgrade head sur la copie (la migration s'applique)
→ requêtes de fumée : comptages Article / Event / Topic, requête FTS, requête Overview
→ comptages cohérents avec la base vivante (pas de base vide ou tronquée)
→ suppression de la copie
→ SystemState.last_restore_test = {at, status, snapshot_id, error}
```

Le test de restauration est soumis au même verrou que le backup (§38.2).

**Exercice complet manuel** — avant la mise en production, puis après toute évolution majeure du schéma : restauration sur une machine neuve (`git clone` + `.env` + restauration + `docker compose up -d`) jusqu'au dashboard fonctionnel, durée mesurée (M7). Critère Partie VIII.

### 38.5 Procédure de restauration (contrat)

```
docker compose stop app worker
restic restore <snapshot> → radar.db restauré
supprimer radar.db-wal et radar.db-shm existants     # IMPÉRATIF : un -wal d'une autre base corromprait la restauration
remplacer /data/radar.db
docker compose up -d                                   # migrate, puis app et worker
contrôle : /health, dashboard, bandeau d'état
```

La procédure est outillée par `scripts/restore.sh <snapshot>` (Partie VIII décision 24), qui applique ce contrat, suppression de `-wal` et `-shm` comprise ; elle est testée en e2e (T-BKP-08, T-RES-07). Le pas-à-pas détaillé vit dans `docs/backup-restore.md` ; le runbook résume et renvoie (Partie IX §55.5, §56.6-P3).

## 39. Monitoring

### 39.1 Principes

- **Le worker calcule, l'app lit.** Une tâche `ops.tick` du worker (60 s) échantillonne l'hôte, agrège les tables d'historique et les compteurs en mémoire, évalue les conditions (§39.5), et écrit un instantané dans `SystemState.ops_metrics`. Les requêtes HTTP ne font aucune agrégation coûteuse.
- **Trois sources de métriques** :
  - **tables d'historique** (`CollectorRun`, `AIJob`, `AlertLog`, `Embedding`, `Event`, `EmergingCandidate`) : agrégées sur 24 h par `ops.tick` ;
  - **`SystemState`** : états écrits par leurs composants (disjoncteur, embeddings, backup…) ;
  - **compteurs en mémoire** (verrous, latences, secondes passes…) : depuis le démarrage du processus, et sur une fenêtre glissante de 1 h et 24 h ; remis à zéro au redémarrage (champ `since` exposé).
- **Pas de Prometheus en V1.** Exposition : `/api/health` (§40.3), le bandeau et les pages du dashboard (Partie VI), les logs (§42).
- **Hôte vu depuis le worker** : disque par `statvfs` sur `/data` (partition du volume), RAM par `/proc/meminfo`, charge par `/proc/loadavg`, mémoire du conteneur par cgroup. Aucun agent supplémentaire, aucun socket Docker.

### 39.2 Catalogue des métriques

**Hôte & SQLite**

| Métrique | Source |
|---|---|
| disque utilisé (%) et libre (octets) de la partition de `/data` | échantillon |
| RAM hôte utilisée (%), mémoire du conteneur worker | échantillon |
| charge (load 1/5/15) | échantillon |
| taille de `radar.db` et de `radar.db-wal` | échantillon |
| `database is locked` : échecs définitifs après `busy_timeout` et retries, par processus | mémoire (worker ; app exposée par l'app elle-même) |
| durée de la plus longue transaction d'écriture du worker (1 h) | mémoire |

**Worker & scheduler**

| Métrique | Source |
|---|---|
| heartbeat (`at`, âge), `started_at`, version | `SystemState.worker_heartbeat` |
| par job planifié : dernière exécution, statut, durée, échecs consécutifs | mémoire → instantané |
| durée du job analytique (Trend Engine + émergence + archivage) | mémoire ; `SystemState.trends_last_run` |

**Collecte** (par source, fenêtre 24 h)

| Métrique | Source |
|---|---|
| `last_success_at` · `last_error` · `last_http_status` · `rate_limit_remaining` · `rate_limit_reset_at` | `Source` |
| runs par statut ; `items_fetched` · `created` · `duplicate` · `filtered` · `skipped` · `too_old` ; `requests_count` | `CollectorRun` |
| taux d'échec d'extraction (`extractions_failed / extractions_attempted`) | `CollectorRun` |
| disjoncteur par source (ouvert / fermé, intervalle effectif) | `CollectorRun` + règle IV §21.5 |
| sources non planifiées faute de credentials | état de démarrage → instantané |

**Embeddings & clustering**

| Métrique | Source |
|---|---|
| état du moteur (`up` / `down`, depuis) | `SystemState.embeddings` |
| backlog (articles `ready` non purgés sans ligne `Embedding`) ; lignes en échec | requête de sélection V-A §24.4 (comptage) |
| latence de clustering (insertion → `clustered_at`), p50 / p95 | mémoire |
| articles évalués sans vecteur ; secondes passes ; fusions ; doublons sémantiques | mémoire |
| Events actifs | `Event` |
| durée d'un cosine sur la fenêtre, taille de la matrice | mémoire |

**Tendances & émergence**

| Métrique | Source |
|---|---|
| dernière exécution du Trend Engine | `SystemState.trends_last_run` |
| candidats émergents actifs ; warm-up en cours (fin prévue) | `EmergingCandidate` ; `trends_since` + `emerging.warmup` |

**LLM** (V-A §25.6)

| Métrique | Source |
|---|---|
| appels par tâche et par issue · timeouts · 429 · latence · tokens · `dropped_items` | mémoire |
| jobs `skipped` par motif ; backlog par `job_type` et par statut ; `dead_letter` | `AIJob` |
| disjoncteur (`state`, `reason`, `since`, `open_until`) | `SystemState.llm_gateway` |
| budget quotidien (`day`, `used`, `budget`, `reserve`) | `SystemState.llm_usage` + `pipeline.yaml` |
| modèle configuré | env |

**Alertes**

| Métrique | Source |
|---|---|
| alertes par type, canal et statut (`sent`, `failed`, `suppressed`) sur 24 h | `AlertLog` |
| canaux actifs / désactivés faute de configuration | état de démarrage → `SystemState.alerting` |
| lignes `sending` requalifiées en `failed` au dernier boot | démarrage → instantané |

**Backup**

| Métrique | Source |
|---|---|
| dernier succès (âge, taille, durée) ; dernière tentative | `SystemState.last_backup`, `backup_last_attempt` |
| dernier test de restauration | `SystemState.last_restore_test` |
| taille du dépôt distant (`restic stats`, hebdomadaire) | instantané |

### 39.3 Clés `SystemState` écrites par le worker (ops)

| Clé | Valeur | Fréquence |
|---|---|---|
| `worker_heartbeat` | `{at, started_at, version, pid}` | 30 s |
| `ops_metrics` | instantané du §39.2, avec `computed_at` | 60 s |
| `ops_conditions` | conditions actives : `{name: {since, alerted_at}}` | à chaque transition |
| `alerting` | `{email: enabled\|disabled, telegram: enabled\|disabled, interrupted_at_boot: n}` | au démarrage |
| `last_backup` · `backup_last_attempt` | §38.2 | par backup |
| `last_restore_test` | §38.4 | par test |

Écrivain unique pour toutes : le worker. Les clés `llm_gateway`, `llm_usage`, `embeddings`, `trends_since`, `trends_last_run` sont acquises (V-A, V-B).

### 39.4 Seuils

Tous configurables dans `pipeline.yaml` (§39.7). Les seuils marqués ⚖ sont **à recaler après les mesures** du §45.4.

| Seuil | Valeur initiale |
|---|---|
| disque — warning / critical | ≥ 80 % / ≥ 90 % (fin d'épisode sous 75 % / 85 %) |
| RAM hôte | ≥ 85 % pendant 10 min (10 échantillons consécutifs) ; fin sous 80 % |
| heartbeat périmé | > 120 s |
| disjoncteur LLM ouvert | > 24 h (hors `not_configured`) |
| moteur d'embeddings `down` | > 15 min |
| backup périmé | dernier succès > 26 h, ou jamais |
| test de restauration périmé | dernier succès > 35 j, ou jamais |
| fichier `-wal` ⚖ | > 128 Mo |
| `database is locked` (worker) | ≥ 10 échecs définitifs sur 1 h |
| sources hors service | ≥ 50 % des sources planifiées avec disjoncteur ouvert |
| job planifié en échec | 3 exécutions consécutives en exception |

### 39.5 Conditions, santé et alertes — table unique

Une **condition** est une règle booléenne évaluée par `ops.tick`. Elle détermine à la fois l'état du composant dans `/api/health` et l'émission d'une alerte `system`. **Un composant est `degraded` exactement quand l'une de ses conditions est vraie** : l'état affiché et les alertes ne peuvent pas diverger.

| Condition | Règle | Composant | Effet sur `status` | Qui alerte |
|---|---|---|---|---|
| `worker_down` | heartbeat > 120 s | `worker` | **down** | monitoring externe |
| `database_down` | lecture de l'app en échec | `database` | **down** | monitoring externe |
| `disk_warning` · `disk_critical` | §39.4 | `host` | degraded | worker |
| `ram_high` | §39.4 | `host` | degraded | worker |
| `wal_large` | §39.4 | `database` | degraded | worker |
| `db_locked` | §39.4 | `database` | degraded | worker |
| `llm_config_error` | `llm_gateway.reason = config` | `llm_gateway` | degraded | worker, **immédiat** |
| `llm_down_long` | ouvert ou `half_open` depuis > 24 h, hors `not_configured` | `llm_gateway` | degraded | worker |
| `embeddings_down` | `down` depuis > 15 min | `embeddings` | degraded | worker |
| `backup_not_configured` | `RESTIC_REPOSITORY` absent | `backup` | degraded | worker (une fois) |
| `backup_failed` · `backup_stale` | §38, §39.4 | `backup` | degraded | worker |
| `restore_test_failed` · `restore_test_stale` | §38.4, §39.4 | `backup` | degraded | worker |
| `sources_down` | §39.4 | `sources` | degraded | worker |
| `job_failing:<job>` | §39.4 (hors collectors, backup et test, qui ont leurs propres règles) | `worker` | degraded | worker |
| `no_alert_channel` | aucun canal configuré | `alerting` | degraded | — (personne à prévenir : visible dans le dashboard) |

**Informatif, sans effet sur `status`** : LLM `not_configured` (état `disabled`, mode de fonctionnement voulu) · budget LLM épuisé · alertes en échec sur 24 h (bandeau, VI §31.10) · sources sans credentials · taux d'échec d'extraction · warm-up de l'émergence.

**Couverture des arrêts de conteneur** (remplace « container stopped ») :

| Conteneur arrêté | Détection |
|---|---|
| `worker` | heartbeat périmé → `/health` 503 → monitoring externe |
| `app` | Caddy répond 502 sur `/health` → monitoring externe |
| `caddy` / VPS | `/health` injoignable → monitoring externe |
| `migrate` en échec | `app` et `worker` absents → 502 → monitoring externe |
| `gateway` | disjoncteur LLM ouvert → `llm_down_long` au-delà de 24 h |

### 39.6 Alertes `system`

- **Émises par le worker** (`ops.tick`), jamais par l'app, via la séquence T1 → envoi → T2 de VI §33.5 (au plus une fois, hors transaction, timeout `alerts.send_timeout`).
- **Une alerte par épisode** : l'épisode commence quand la condition passe de faux à vrai, et finit quand elle redevient fausse (avec l'hystérésis du §39.4). Les épisodes sont **persistés** dans `SystemState.ops_conditions` : un redémarrage du worker ne réémet pas une alerte déjà envoyée.
- `dedup_key` = `system:{condition}:{since de l'épisode}:{channel}`.
- **Hors des réglages de fréquence** : ni `alerts.mode`, ni heures calmes, ni plafond quotidien (et elles ne comptent pas dans ce plafond). Ces alertes sont rares et bornées par la dédup d'épisode.
- **Routage** : type `system`, défaut **`[telegram, email]`** : un canal en panne ne rend pas l'exploitation aveugle.
- **Contenu** : condition, valeur mesurée, seuil, depuis quand, lien `<DASHBOARD_URL>/api/health`.
- **Pas de notification de rétablissement en V1** : le retour à la normale se lit dans le dashboard.
- Un échec d'envoi d'une alerte `system` ne déclenche pas d'autre alerte (pas de récursion) : il est compté et visible dans le bandeau.

### 39.7 Réglages ops dans `pipeline.yaml`

| Clé | Défaut | Section |
|---|---|---|
| `alerts.tick` · `alerts.send_timeout` | 60 s · 10 s | VI §33 (consolidé) |
| `ops.tick` | 60 s | §39.1 |
| `ops.heartbeat_interval` · `heartbeat_stale_after` | 30 s · 120 s | §40.2 |
| `ops.watchdog_timeout` | 300 s | §36.6 |
| `ops.disk_warning` · `disk_critical` · `disk_hysteresis` | 80 · 90 · 5 (points) | §39.4 |
| `ops.ram_warning` · `ram_sustained` | 85 · 10 min | §39.4 |
| `ops.wal_max_bytes` | 128 Mo ⚖ | §39.4 |
| `ops.db_locked_max_per_hour` | 10 | §39.4 |
| `ops.llm_breaker_alert_after` | 24 h | §39.4 |
| `ops.embeddings_down_alert_after` | 15 min | §39.4 |
| `ops.sources_down_ratio` | 0,5 | §39.4 |
| `ops.job_failing_threshold` | 3 | §39.4 |
| `backup.time` | `03:30` (UTC) | §38.3 |
| `backup.stale_after` | 26 h | §39.4 |
| `backup.keep_daily` · `keep_weekly` · `keep_monthly` | 7 · 4 · 3 | §38.3 |
| `restore_test.day` · `time` · `stale_after` | 1 · `04:30` (UTC) · 35 j | §38.4 |

Le routage du type `system` vit dans le `Setting` `alerts.routing` (VI §33.9), comme les autres types.

## 40. Health endpoint

### 40.1 Deux niveaux

| Endpoint | Accès | Contenu | Consommateur |
|---|---|---|---|
| `GET /health` | **public** | `{"status": "ok" \| "degraded" \| "down"}` | monitoring externe |
| `GET /api/health` | basic_auth | détail par composant, métriques, conditions actives | vous, le navigateur, `app.cli health` |
| `GET /api/status` | basic_auth | bandeau d'état (VI §31.10), **inchangé** | la SPA |

Les trois sont calculés par **un seul module** (`app/ops/health.py`) : même lecture de `SystemState`, même seuil de heartbeat.

### 40.2 `/health` public

- **Codes HTTP** : `ok` → 200 · `degraded` → 200 · `down` → **503**.
- **Calcul**, à chaque requête, **sans aucun appel réseau** (ni gateway, ni worker) :
  1. une lecture courte en `read_session` : `SystemState` (heartbeat, conditions actives). Échec ou timeout de 2 s → `down` (condition `database_down`) ;
  2. heartbeat dont l'âge, calculé **au moment de la requête**, dépasse `ops.heartbeat_stale_after` → `down` ;
  3. au moins une condition active de la table §39.5 → `degraded` ;
  4. sinon `ok`.
- **Sens de `down`** : le produit ne remplit plus sa fonction — base inaccessible, ou worker mort (plus de collecte). Le dashboard peut rester lisible (Partie II §9.2), mais l'alerte externe doit partir.
- **Pourquoi l'âge est calculé par l'app** : un worker mort ne peut pas écrire qu'il est mort. L'instantané `ops_metrics` n'est donc jamais la source du statut du worker.
- Aucune information interne dans la réponse publique : ni version, ni composant, ni horodatage.
- Temps de réponse cible ≤ 50 ms (§45.3).

### 40.3 `/api/health` détaillé

```json
{
  "status": "degraded",
  "checked_at": "2026-09-22T08:00:00Z",
  "version": "a1b2c3d",
  "components": {
    "database":    {"status": "ok", "schema_revision": "…", "db_bytes": 0, "wal_bytes": 0},
    "worker":      {"status": "ok", "heartbeat_at": "…", "heartbeat_age_s": 12, "started_at": "…", "version": "a1b2c3d"},
    "llm_gateway": {"status": "disabled", "state": "open", "reason": "not_configured", "since": "…", "open_until": null},
    "llm_budget":  {"day": "2026-09-22", "used": 0, "budget": null, "reserve": 20},
    "embeddings":  {"status": "ok", "state": "up", "since": "…", "backlog": 0},
    "backup":      {"status": "degraded", "last_success_at": "…", "last_attempt": {"at": "…", "status": "failed", "error": "…"},
                    "last_restore_test": {"at": "…", "status": "ok"}},
    "host":        {"status": "ok", "disk_used_pct": 41, "ram_used_pct": 52, "load": [0.4, 0.3, 0.3]},
    "sources":     {"status": "ok", "scheduled": 24, "breaker_open": [], "missing_credentials": []},
    "alerting":    {"status": "ok", "channels": {"email": "enabled", "telegram": "enabled"}, "failed_24h": 0},
    "app":         {"started_at": "…", "db_locked_1h": 0}
  },
  "conditions": [{"name": "backup_failed", "since": "…", "alerted_at": "…"}],
  "last_ingestion": "…",
  "last_ai_job": "…",
  "metrics": {"computed_at": "…", "…": "instantané ops_metrics §39.2"}
}
```

- Valeurs de `status` par composant : `ok` · `degraded` · `down` · `disabled` (LLM non configuré) · `not_configured` (backup sans dépôt, compté comme `degraded`).
- `last_ingestion` et `last_ai_job` sont **informatifs** : ils ne qualifient jamais la santé (une nuit sans article n'est pas une panne, Partie II §9.2).
- `metrics.computed_at` périmé ⇒ instantané affiché tel quel, avec le statut `worker` qui dit pourquoi.

## 41. Monitoring externe

- **Service externe gratuit**, hors VPS (le VPS n'est pas responsable de sa propre surveillance) : sonde HTTPS sur `<DASHBOARD_URL>/health`.
- **Réglage** : intervalle 5 min · timeout 10 s · **alerte si code ≠ 200 sur deux sondes consécutives** · notification par les canaux du service externe (email et/ou Telegram), **indépendants du VPS**.
- **Surveillance du certificat** : alerte si expiration < 14 jours (si le service le propose ; sinon, `/health` injoignable en HTTPS finit par la révéler).
- **Il n'interprète que le code HTTP**, jamais le corps : `degraded` (200) est l'affaire des alertes `system` du worker. Il n'y a donc pas de double alerte.
- **Maintenance** : mettre la sonde en pause pour une opération longue (restauration).
- **Risque résiduel accepté** : si les deux canaux du worker sont en panne en même temps, un état `degraded` n'est visible que dans le dashboard (bandeau « N alertes non envoyées »).
- Le choix du service est un choix de déploiement ; il est noté dans `docs/monitoring.md`.

## 42. Logging

### 42.1 Format et transport

- **JSON, une ligne par événement, sur stdout**, pour `app`, `worker` et `migrate` ; Caddy en JSON sur stdout également.
- **structlog** ; les loggers des bibliothèques (uvicorn, httpx, APScheduler, SQLAlchemy, alembic) passent par le même rendu JSON.
- **Collecte et rotation** par le driver Docker `json-file` : `max-size 10m`, `max-file 5` par service. Aucun fichier de log dans un volume, aucun service d'agrégation en V1.
- Les logs sont **éphémères** : l'historique durable est en base (`CollectorRun`, `AIJob`, `AlertLog`, `SystemState`).
- Niveau par défaut `INFO` (`LOG_LEVEL`). `DEBUG` n'est jamais laissé actif en production.

### 42.2 Champs

| Champ | Présence | Contenu |
|---|---|---|
| `ts` | toujours | UTC ISO-8601, millisecondes |
| `level` | toujours | `debug` · `info` · `warning` · `error` · `critical` |
| `service` | toujours | `app` · `worker` · `migrate` |
| `version` | toujours | sha Git de l'image |
| `event` | toujours | nom stable en notation pointée (`collector.run.finished`, `aijob.completed`, `alert.send.failed`, `backup.completed`…) |
| `component` | worker | `collector` · `pipeline` · `embeddings` · `clustering` · `trends` · `emerging` · `ai` · `alerts` · `purge` · `ops` · `backup` |
| `source_id` · `run_id` | collecte | identifiants de la source et du run |
| `job_id` · `job_type` · `prompt_version` | jobs AI | V-A §25.6 |
| `duration_ms` | opérations chronométrées | — |
| `items_*` | fin de run | compteurs du §14.4 de la Partie IV |
| `status` | fin d'opération | `success` · `partial` · `failed`… |
| `error_class` · `error` | erreurs | classe et message nettoyé (§42.4) |

Les champs de la liste V0.3 (`timestamp · service · job · source · duration · items_fetched · items_created · items_skipped · status · error`) sont couverts par `ts · service · job_type / component · source_id · duration_ms · items_* · status · error`.

### 42.3 Access logs

- **Un seul access log : Caddy.** uvicorn tourne avec `--no-access-log`.
- `/health` n'est pas journalisé par Caddy (`log_skip`) : une sonde toutes les 5 min n'apporte rien.
- **`log_credentials` n'est jamais activé** : Caddy masque alors `Authorization` et `Cookie` dans ses logs (comportement par défaut, vérifié par un test).

### 42.4 Rédaction des secrets

**Ne jamais journaliser** : clés d'API, mots de passe, tokens, hash d'auth, contenu du `.env`, prompts et réponses LLM au niveau `info` (V-A §25.6).

Trois niveaux, cumulatifs :

1. **Par construction** : les secrets sont chargés dans un objet de configuration typé (`SecretStr`), dont la représentation est masquée. Aucun log ne reçoit l'objet de configuration entier.
2. **Par transport** : le `HttpClient` masque `Authorization` et les paramètres sensibles (Partie IV §21.1).
3. **Par valeur (filet final)** : un processeur structlog remplace par `***` **toute occurrence de la valeur** d'un secret configuré, dans tous les champs, messages et traces d'exception. Il masque aussi les valeurs des clés nommées `authorization`, `password`, `token`, `secret`, `api_key`, `cookie`.

- Le niveau 3 est indispensable : le token Telegram fait partie de l'URL de l'API (`/bot<token>/…`), et httpx inclut l'URL dans ses exceptions.
- **Le même nettoyage s'applique à ce qui est écrit en base et affiché** : `Source.last_error`, `AlertLog.error`, `backup_last_attempt.error`, erreurs d'`AIJob`.
- **Test obligatoire** : secrets factices injectés, scénarios d'échec (401 GitHub, 401 LLM, 401 Telegram, échec d'auth SMTP, échec restic) ; aucune valeur factice ne doit apparaître ni dans les logs capturés ni dans les colonnes d'erreur.

## 43. Sécurité

### 43.1 Hôte

- **SSH** : par clé uniquement (`PasswordAuthentication no`), `PermitRootLogin no`, utilisateur de déploiement non-root avec `sudo`.
- **Pare-feu** (ufw ou nftables) : entrant autorisé **uniquement** sur SSH, 80/tcp, 443/tcp et 443/udp ; tout le reste refusé. Pare-feu du fournisseur en plus, s'il existe.
- **Piège Docker** : un port publié par Docker contourne ufw. D'où la règle : **seul `caddy` publie des ports** ; aucun `ports:` sur un autre service, jamais même temporairement pour déboguer (utiliser `docker compose exec`).
- **Mises à jour** : `unattended-upgrades` (ou équivalent) pour les correctifs de sécurité ; reboot planifié manuellement, couvert par le test de reboot.
- Aucun service inutile en écoute sur l'hôte.

### 43.2 Conteneurs

- Utilisateur non-root ; `no-new-privileges` ; `cap_drop: ALL` (Caddy : `NET_BIND_SERVICE` seul) ; racine en lecture seule pour `app` et `worker` (§36.5).
- **Socket Docker jamais monté.**
- Images de base épinglées ; **reconstruction mensuelle** pour intégrer les correctifs.
- Segmentation réseau du §36.2 : `app` sans sortie Internet, `worker` sans accès à `app`, base jamais exposée.

### 43.3 Application

- **Authentification** : basic_auth Caddy, bcrypt, mot de passe aléatoire de 20 caractères au moins (VI §32.1). `DASHBOARD_TOKEN` supprimé.
- **Anti-CSRF** : toute requête non `GET` exige `Content-Type: application/json`, `X-Radar-Client: 1` et, s'il est présent, `Origin = DASHBOARD_URL` ; sinon 403 (VI §32.2).
- Pas de CORS ; `/docs`, `/redoc`, `/openapi.json` désactivés ; en-têtes de sécurité du §37.3 ; corps de requête limité à 1 Mo.
- **Sorties LLM** rendues en texte brut, `dangerouslySetInnerHTML` interdit (VI).
- Aucun secret renvoyé par l'API ni stocké dans `Setting` (VI §32.3).
- **Anti-SSRF** (Partie IV §21.1) : les URLs à récupérer proviennent de flux tiers. Le `HttpClient` refuse toute destination dont l'adresse résolue est privée, de bouclage, lien-local (dont `169.254.169.254`, métadonnées cloud), unique-local IPv6 ou non routable, **vérifiée après résolution DNS et à chaque redirection**. Défaut : appliqué à toutes les requêtes ; exceptions explicites seulement pour `LLM_BASE_URL` et le dépôt restic, qui peuvent être internes.

### 43.4 Secrets

- **Uniquement dans `.env`** sur le VPS, droits `600`, propriétaire l'utilisateur de déploiement. Copie de référence dans un **gestionnaire de mots de passe**, avec `RESTIC_PASSWORD`.
- **Seule exception : le jeton GitHub de `scripts/deploy.sh`**, nécessaire seulement si le dépôt est privé. Jeton *fine-grained* en lecture seule (statuts et actions du seul dépôt), stocké hors du `.env` applicatif, droits `600`, **jamais transmis à un conteneur** (Partie VIII §49.5, Partie IX §56.6-P5).
- **Jamais** dans Git (`.gitignore`, analyse de secrets en CI), dans une image (`.dockerignore`, aucun `COPY .env`), dans la base, dans un backup ou dans un log.
- **Rotation** : mot de passe du dashboard (nouveau hash, `docker compose up -d caddy`) ; tokens GitHub, LLM, Telegram, SMTP (mise à jour du `.env`, `docker compose up -d worker`). Toute modification du `.env` s'applique par `docker compose up -d <service>`, jamais par `restart`, qui ne relit pas l'environnement (Partie IX décision 22). Procédures au runbook (Partie IX §56.6-P4, P5).
- Le `GITHUB_TOKEN` est *fine-grained*, lecture seule, dépôts publics (IV §22).

### 43.5 Dépendances

- Versions verrouillées (`uv.lock`, `package-lock.json`), mises à jour régulières, audit de vulnérabilités en CI (Partie VIII §49.2, §49.4).

## 44. Stockage

### 44.1 Ce qui occupe le disque

| Poste | Borne |
|---|---|
| `radar.db` | quelques centaines de Mo par an au volume réaliste (III §13) ; les pages libérées par la purge sont **réutilisées**, le fichier ne rétrécit pas |
| `radar.db-wal` | borné par l'auto-checkpoint et `journal_size_limit` (Partie III §10.2) ; surveillé (§39.4) |
| `/data/backup/` | vide hors backup ; une copie de la base pendant le backup ou le test |
| images Docker | image courante + précédente (rollback), mesurées (M8) |
| logs conteneurs | ≤ 50 Mo par service (`10 Mo × 5`) |
| `caddy_data` | négligeable |

Sur 40 Go, le budget est large ; le seuil de 80 % garantit la place d'une copie de la base pour le backup.

### 44.2 Nettoyage

- **Contrôlé et manuel** : suppression des images antérieures à la précédente, au déploiement (runbook).
- **Interdit** : `docker system prune --volumes`, `docker volume prune`, toute commande de nettoyage qui touche aux volumes.
- **Aucun `VACUUM` automatique de la base vivante** : il verrouille toute la base. Un `VACUUM` manuel, worker arrêté, reste possible par `python -m app.cli vacuum` (`run --rm --no-deps worker`, Partie IX §56.4.2, procédure §56.6-P8) : la commande refuse si le heartbeat du worker est frais ou si l'espace libre de `/data` est inférieur à deux fois la taille de la base, et place les fichiers temporaires de SQLite sur `/data`, jamais dans le tmpfs `/tmp`. Le backup (`VACUUM INTO`) est de toute façon compacté.
- **Jamais de suppression automatique de données métier** hors de la table de rétention de la Partie III §13 (acquis).

## 45. Coût & performance cibles

### 45.1 Coût (acquis Partie I)

| Poste | Cible |
|---|---|
| VPS | 5–10 €/mois |
| Stockage des backups | 0–1 €/mois (dépôt restic chiffré ; offres gratuites ou quasi gratuites de quelques Go) |
| Monitoring externe | 0 € |
| LLM | **0 €** — le produit fonctionne sans abonnement LLM payant, et sans LLM du tout |
| Domaine | faible (≈ 1 €/mois) |
| **Total** | **≤ 12 €/mois** |

### 45.2 Principe

`< 10 000 articles/jour` sur **un seul VPS**, sans architecture distribuée. Aucun Redis, Kafka, Kubernetes, PostgreSQL ni vector DB par anticipation ; migration **uniquement sur besoin démontré par la mesure**, tracée en ADR (Partie IX §53–§54).

### 45.3 Cibles de performance

Deux profils de charge, joués sur la **taille de VPS cible** avec un jeu de données synthétique (Partie VIII §50.4), dans un **projet Compose distinct** (`-p radar-load`) avec son propre volume, jamais sur le volume de production (Partie VIII décision 20) :

- **réaliste** : ordre de grandeur de la Partie III, ≈ 2 000 articles `ready` dans la fenêtre de 72 h ;
- **cible** : 10 000 items collectés par jour, hypothèse haute où tous sont `ready` (≈ 30 000 vecteurs dans la fenêtre).

| Cible | Valeur | Mesure |
|---|---|---|
| Débit d'ingestion | 10 000 items/jour tenus sans arriéré croissant (collecte, embeddings, clustering) | profil cible |
| Latence de clustering | ≤ 6 min (V-B §28.2) | métrique p95 |
| Cosine d'un article sur la fenêtre | ≤ 50 ms au profil cible | M2 |
| Plus longue transaction d'écriture du worker | ≤ 500 ms (≤ 10 % de `busy_timeout`) | M4 |
| Job analytique | ≤ 5 min au profil cible (période : 60 min) | M5 |
| API de lecture | p95 ≤ 300 ms au profil cible ; `/health` ≤ 50 ms | M9 |
| RAM totale au repos | ≤ 70 % de la RAM du VPS (marge sous le seuil de 85 %) | M1 |
| Backup / restauration | backup ≤ 10 min ; restauration complète ≤ 30 min | M7 |
| Reboot → `/health` = `ok` | ≤ 3 min | M10 |
| RPO / RTO | ≤ 24 h / ≤ 1 h | §38.1 |

### 45.4 Check-list des mesures avant production

Chaque mesure est consignée dans `docs/measurements.md` (date, VPS, profil, résultat). Les mesures prises en développement sont indicatives ; les mesures **de référence** sont jouées en pré-production sur le VPS cible (Partie VIII §47.4, §50.7). Une mesure hors critère bloque la mise en production **ou** donne lieu à un ADR qui ajuste la cible.

| # | Mesure | Méthode | Critère | Effet |
|---|---|---|---|---|
| M1 | **RAM du worker** : moteur d'embeddings chargé en permanence, **plus lingua** (ses modèles de langues sont volumineux), plus la matrice de similarité ; pic pendant un lot de 32 | RSS au repos et en pic, profils réaliste et cible ; RAM totale de l'hôte avec tous les services | ≤ 70 % de la RAM du VPS | fixe la taille du VPS et les `mem_limit` |
| M2 | Durée du **cosine** brute-force en régime nominal | chronométrage par article, deux profils | ≤ 50 ms au profil cible | valide « pas de vector DB » |
| M3 | Taille du fichier **`-wal`** en collecte soutenue, **pendant un `VACUUM INTO`** et pendant le job analytique | échantillonnage `ops.tick` | reste sous `ops.wal_max_bytes` | recale le seuil `wal_large` |
| M4 | Durée de la **plus longue transaction** du worker | métrique dédiée | ≤ 500 ms | valide le découpage en lots (II §8.6) |
| M5 | Durée du **job analytique** au volume nominal | chronométrage, profil cible | ≤ 5 min | valide le calcul horaire (V-B §29.4) |
| M6 | **Gateway LLM** : checklist V0.3 §25 (RAM/CPU si auto-hébergé, requêtes multiples, quota épuisé, timeout, provider indisponible) **+ comportement 429 / `Retry-After` + disponibilité de `GET /models`** | contre le gateway retenu | 429 conforme aux attentes du disjoncteur (V-A §24.2) ; `health()` fiable | valide le gateway ; sinon `health()` adapté, tracé en ADR |
| M7 | **Backup et restauration** : durée, taille, exercice complet sur machine neuve | §38.4 | backup ≤ 10 min ; restauration ≤ 30 min | valide le RTO |
| M8 | **Taille des images** et empreinte disque totale | `docker system df` | image courante + précédente + base + marge backup < 50 % du disque | valide le budget disque |
| M9 | **Latence de l'API** (Overview, Feed, recherche, `/health`) | charge légère sur profil cible | p95 ≤ 300 ms ; `/health` ≤ 50 ms | valide la pagination et les index |
| M10 | **Reboot** du VPS jusqu'à `/health` = `ok` | test II §9.5 chronométré | ≤ 3 min, sans alerte externe | valide le démarrage |

Rappels hors Partie VII, également bloquants : calibration du clustering (`cluster-calibrate`, V-B §28.14) et tests de résilience (Partie II §9.5).

---

## Points d'interprétation

**Tranchés dans cette partie** (l'implémenteur n'a pas à choisir) : topologie et réseaux · ordre de démarrage et procédure de déploiement · contenu du `Caddyfile` · sémantique `ok / degraded / down` et codes HTTP · valeurs du heartbeat et du watchdog · mécanisme, planification, rétention et test du backup · catalogue des métriques et seuils initiaux · qui alerte sur quoi · format et nettoyage des logs · durcissement hôte et conteneurs · liste des variables d'environnement · cibles et check-list de mesures.

**Laissés à l'implémenteur, sans impact sur le contrat** : tags exacts des images, chemins des Dockerfiles, noms d'`event` de log au-delà des exemples, forme de l'instantané `ops_metrics` tant qu'il couvre le §39.2.

**Choix de déploiement, hors spec** (à noter dans `docs/deployment.md`) : fournisseur du VPS et distribution Linux · fournisseur du dépôt restic · service de monitoring externe · gateway LLM retenu.

**Décisions à poids réel, prises par défaut puis validées avec la partie** (Partie IX décision 12) :

1. **Backup exécuté par le worker** (plutôt qu'un conteneur ou un cron hôte) : cohérent avec l'écrivain unique de `SystemState.last_backup` et le plafond de services ; en contrepartie, le worker embarque restic et les identifiants du dépôt.
2. **`down` quand le worker est mort**, alors que le dashboard reste lisible : c'est ce qui permet au monitoring externe d'alerter sur l'arrêt de la collecte.
3. **Seuil de 24 h** pour le disjoncteur LLM ouvert : ne se déclenche pas sur un quota quotidien épuisé puis rétabli, mais signale un gateway cassé depuis une journée.
4. **Test de restauration automatisé** par le worker, en plus de l'exercice manuel avant la production.
5. **Segmentation réseau** et **racine en lecture seule** des conteneurs.

---

## Reporté en V2 (tracé depuis la Partie VII)

- **Endpoint Prometheus `/metrics`** et tableaux de bord (Grafana ou équivalent).
- **Page « Santé système »** dans le dashboard (en V1 : `/api/health` en JSON et le bandeau).
- **Notifications de rétablissement** des conditions `system`.
- **Agrégation centralisée des logs.**
- **Réplication continue** de la base (type Litestream) pour réduire le RPO sous 24 h.
- **Estimation du coût LLM** par provider.
- **Alertes sur le taux d'échec d'extraction** et sur une source isolée en panne prolongée.
- **Déploiement continu** (déjà reporté par la V0.3 §49).
- **`auto_vacuum` / `VACUUM` incrémental** de la base vivante.
