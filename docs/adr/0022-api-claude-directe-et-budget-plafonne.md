# ADR 0022 — API Claude en direct, LLM optionnel à budget mensuel plafonné

| | |
|---|---|
| **Statut** | Accepté |
| **Date** | 2026-09-30 |
| **Décision(s) couverte(s)** | DV-09, DV-11 ; I §4, §4.3, §5 · V-A §24.3, §25 · VII §36.2, §36.5, §36.7, §45.1, §45.4 (M6) · VIII décision 21 · IX §53.2, §54.2, §54.3 |

## Contexte

Le 2026-09-29, le propriétaire a validé un besoin nouveau (#122) : ai-tech-radar reste un produit de veille utilisable
à chaque sprint, et devient aussi le projet fil rouge de ses certifications Claude (Developer, puis Architect). Le
produit doit donc s'appuyer sur l'API Claude native et sur son écosystème (Agent SDK, MCP, Claude Code).

Le choix précédent (ADR-0007) en ferme l'accès. L'API OpenAI-compatible derrière un gateway ne donne que le plus petit
dénominateur commun : les fonctions propres au fournisseur (outils, sortie structurée native, Agent SDK, MCP) restent
hors d'atteinte, ce que l'ADR-0007 acceptait explicitement. Son objectif « LLM à 0 € » reposait par ailleurs sur des
quotas gratuits changeants, et le gateway ajoutait un service à choisir, mesurer et durcir (ADR-0009 ;
`architecture.md` A-06). L'ADR-0007 prévoyait lui-même ce cas de réexamen : « un besoin fonctionnel validé qu'aucune
API OpenAI-compatible ne permet d'atteindre ».

Contraintes maintenues : cœur déterministe complet sans LLM (DV-05, ADR-0003) ; mono-utilisateur ; portable ;
infrastructure ≤ 12 €/mois (I §4.3) ; app sans secret ni sortie réseau (DV-12).

## Décision

Le **worker** appelle **directement l'API Claude** par le SDK Python officiel `anthropic`, derrière le `LLMClient`
seul. Le gateway OpenAI-compatible, le service `gateway` et les gateways candidats de M6 sont retirés. Le LLM reste
**optionnel** (`not_configured` sans `ANTHROPIC_API_KEY`). Son coût est tenu par un **budget mensuel plafonné** :
- configuré en USD, devise de facturation, pour un défaut d'environ 15 € ;
- suivi en tokens et en coût réel ;
- plafond dur appliqué par le worker ;
- remise à zéro le 1er du mois, en UTC.

Les capacités de l'écosystème Claude (Agent SDK, MCP…) n'arrivent qu'**une par une**, chacune par sa propre décision
inscrite dans la feuille de route de la Partie VIII (§47.5), désactivable par configuration, jamais par anticipation.

## Alternatives écartées

- **Garder le gateway OpenAI-compatible, avec Claude derrière lui** : laisse inaccessibles les capacités natives, qui
  sont le cœur du besoin. Garde aussi un service de plus à exploiter et à durcir (A-06).
- **Mener l'apprentissage dans un projet séparé** : double la maintenance, et prive l'apprentissage du cas réel qui en
  fait la valeur, un produit exploité avec ses pannes, son budget et ses tests.
- **LLM obligatoire** : contraire à DV-05 et au repli déterministe (I §1, §3) ; une clé absente ou un budget épuisé ne
  doivent jamais arrêter le produit.
- **Sans plafond, ou avec la seule limite de la Console Anthropic** : le coût ne serait ni observable ni borné par le
  produit (I §4.3 « Observable »). La limite de dépense de la Console est gardée comme **seconde ligne de défense**,
  réglée au même montant.

## Conséquences

- **`LLMClient`** : conservé comme adaptateur **unique**. Le SDK `anthropic` n'est importé que par lui ; aucun code
  métier n'en dépend. Le client est créé avec `max_retries=0` : la file, le backoff et le disjoncteur restent les seuls
  maîtres des reprises (V-A §26). Le contrat détaillé (sortie structurée, `stop_reason`, classement des erreurs 429,
  529, crédit épuisé, `health()` par `GET /v1/models`) est à réviser dans V-A §25.
- **Secret** : `ANTHROPIC_API_KEY` est détenu par le worker, alors que le gateway le cloisonnait. Il est ajouté à la
  liste des secrets du worker (VII §36.7), masqué dans les logs et renouvelé par P5 (IX §56.6). L'app ne reçoit
  toujours aucun secret. A-06 (durcissement du gateway) devient sans objet.
- **`ANTHROPIC_BASE_URL`** : le SDK la lit d'office. Elle n'est acceptée que si `APP_ENV=test`, pour joindre le
  double de test ; renseignée avec un autre `APP_ENV`, le worker refuse de démarrer, sur le modèle de T-CFG-09
  (VIII décision 23).
- **Réseau** : le worker sort vers `api.anthropic.com` par son réseau `egress` existant ; l'app reste sans sortie
  Internet. Le `LLMClient` reste hors du `HttpClient` et n'appelle que l'hôte de l'API (T-LLM-20).
- **Doubles et fixtures** : le faux gateway est remplacé par un double de l'API Messages, joint par
  `ANTHROPIC_BASE_URL` en test seulement. Aucun test n'appelle l'API réelle (VIII §50.1). Les fixtures (E8) sont
  enregistrées à la main contre l'API Claude ; leur coût entre dans le budget.
- **Suivi du coût en base** :
  - l'`usage` de chaque réponse, en tokens d'entrée et de sortie ;
  - une table de prix par modèle, en configuration ;
  - un cumul mensuel persistant qui survit à la purge des `AIJob` (30 jours, III §13) ;
  - avant chaque appel, une réservation du coût maximal, pour tenir le plafond malgré la concurrence
    (`llm.max_concurrent`) ;
  - l'état du budget exposé par `/api/health` et une condition `system`.

  Le modèle de données et les clés de configuration sont à réviser (V-A §24.3 ; III ; VII §39, §40).
- **Topologie** (DV-11) : trois services permanents et `migrate`, sans profil `gateway`. Le reste de l'ADR-0009 est
  reconduit sans changement.
- **On gagne** : les capacités natives de Claude ; un service de moins ; un coût LLM observable et borné par le produit
  lui-même.
- **On accepte** :
  - une dépendance à un fournisseur, confinée au `LLMClient` ;
  - un coût récurrent, borné par le plafond ;
  - un budget épuisé en cours de mois laisse le produit en repli jusqu'au 1er du mois suivant, et des jobs expirent
    (TTL, V-A §23.2).
- **Preuve de réexamen** :
  - un coût réel qui ne tient pas sous le plafond au volume nominal (M6) ;
  - un incident de disponibilité prolongé de l'API ;
  - un besoin validé qu'un autre fournisseur serait seul à couvrir.

## Preuve

Besoin fonctionnel nouveau, validé par le propriétaire le 2026-09-29 : issue #122. Il correspond à la preuve de
réexamen prévue par l'ADR-0007.

## Remplace

0007 (DV-09) et 0009 (DV-11) : DV-09 et DV-11 ne peuvent changer que l'une avec l'autre, le retrait du gateway
touchant les deux (IX §54.2).
