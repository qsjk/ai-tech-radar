# CLAUDE.md — règles permanentes

Règles lues à chaque session (IX §55.3). Ce fichier **renvoie** à la spec ; en cas de doute, la spec fait foi.
Il ne remplace ni la spec, ni le plan du sprint, ni les ADR.

## Lecture

1. `SPEC.md` : index de la spec, règles de lecture, renvoi aux décisions verrouillées (IX §53).
2. Les parties de `docs/spec/` que touche le sprint en cours, et son plan `docs/sprints/sprint-NN.md` (plan validé,
   identifiants de tests visés, critères d'acceptation).
3. `docs/planning.md` pour l'enchaînement des sprints et des gates (§0 : conventions et mode de travail).
4. `docs/architecture.md` (processus, configuration, conteneurs, CI) et `docs/database.md` (modèle SQL, migrations)
   pour la conception.
5. `docs/adr/README.md` pour les décisions acceptées et leurs raisons.

## Interdits

Tant qu'une règle ci-dessous s'applique, ne pas passer outre ; s'arrêter et le signaler.

- Modifier une **décision verrouillée** (IX §53.2) : cela exige une preuve, un ADR et une mise à jour de la spec
  (IX §53.1), décidés par le propriétaire.
- Passer un ADR en `Accepté` : seul le propriétaire accepte ou rejette (IX §53.1, §54.2).
- **Trancher** un conflit ou un trou de la spec (VIII §51.3).
- Démarrer un sprint dont le plan n'est pas validé, ou implémenter un sprint suivant (IX §57.8, VIII §47.1).
- Appeler un **vrai provider** dans un test : LLM, source, SMTP, Telegram, stockage distant (VIII §49.3, §50.1).
- Ajouter une brique de la liste des **interdits par anticipation** (IX §53.3) sans preuve.
- **Docker** : uniquement par `scripts/radar-dev` (VIII §46.1, ADR-0021). Jamais d'appel direct à `docker` ou
  `docker compose`, jamais les projets Compose `radar` ni `radar-load` (IX §55.3, §56.2).

## Arrêts obligatoires

S'arrêter, rendre compte et attendre le propriétaire :

- à la **fin de chaque sprint**, après le bilan dans `docs/sprints/sprint-NN.md` (VIII §51.2, IX §57.8) ;
- après avoir **proposé un ADR** (IX §53.1) ;
- sur tout **conflit ou trou** de la spec (VIII §51.3) ;
- après l'**ouverture de chaque PR** (voir « Façon de travailler »).

## Définition de terminé

Voir **VIII §51** : §51.1 pour une fonctionnalité (et chaque PR), §51.2 pour un sprint, §51.3 pour un écart à la spec.
Une tâche n'est terminée que si la CI est verte et que les identifiants de tests visés sont couverts (VIII §50.3).

## Façon de travailler

- **Issue par issue**, avec `gh` : lire l'issue en entier, y compris ses commentaires de revue, avant d'agir.
- **Une branche par issue** : `sNN/<n°>-slug` (ex. `s01/12-socle-compose`) ; **une PR dédiée** par issue, dont la
  description commence par `Closes #n`, avec la milestone du sprint.
- **Un commit par unité logique**, message en français avec un préfixe de type (`feat`, `fix`, `docs`, `test`…),
  une portée, et la référence de la tâche en fin de ligne, par exemple `(T1.3, #12)`.
- **Jamais de push sur `main`**. **Jamais de réécriture** d'un historique déjà poussé : les corrections de revue
  sont de nouveaux commits sur la même branche.
- **S'arrêter après l'ouverture de la PR** (ou après le push d'une reprise). **Ne jamais fusionner.**
- **Tout en français** : commits, PR, documents, commentaires de code destinés au lecteur du dépôt.
- **Aucune signature** dans les commits et les PR : pas de ligne `Co-Authored-By`, pas de mention de l'outil qui les
  a rédigés, pas de lien de session.
- **Écarts de spec** rencontrés en cours de tâche : listés dans la description de la PR, avec les passages en cause,
  **jamais tranchés** (VIII §51.3).
- **Périmètre** : ne modifier que ce que l'issue demande ; tout ajout utile est proposé, pas fait d'office.
- **Message final** de chaque tâche : la liste des commits, le contenu clé produit ou modifié, et les écarts relevés.

## Commandes usuelles

Prévues par la spec ; elles arrivent au Sprint 1. N'utiliser que les commandes et sous-commandes écrites ici ou dans
la spec, sans inventer d'options.

| Besoin | Commande | Référence |
|---|---|---|
| Lint et format (backend) | `ruff check` · `ruff format --check` · `mypy` (strict sur `app/`) | VIII §49.2, étape 1 |
| Lint (frontend) | eslint · `tsc --noEmit` | VIII §49.2, étape 1 |
| Configuration | `python -m app.cli validate-config` | IV §16.5 · IX §56.4 |
| Tests unitaires et d'intégration | `pytest` (réseau bloqué) · vitest | VIII §49.2, étape 4 · §50.1 |
| Traçabilité du catalogue | `scripts/check-test-catalog.py` | VIII §50.3 |
| Compose local | `scripts/radar-dev up` · `down` · `reset` · `ps` · `logs <service>` · `health` | VIII §46.1 · ADR-0021 |
| Tests par `radar-dev` | `scripts/radar-dev test` · `scripts/radar-dev e2e` | VIII §46.1 |

Le mode d'emploi détaillé vit dans `docs/testing.md` (IX §55.4), créé au Sprint 1.
