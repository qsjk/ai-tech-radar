Closes #

## Contenu

<!-- Ce que la PR livre, par fichier ou par commit, avec les renvois à la spec et au plan du sprint. -->

## Vérifications

<!-- Sortie locale de ruff, mypy, pytest (couverture), shellcheck, eslint, vitest ; démonstration par
scripts/radar-dev ; lien et résultat du run de CI. -->

## Écarts relevés

<!-- Écarts à la spec rencontrés, avec les passages en cause ; signalés, jamais tranchés (VIII §51.3).
« Aucun » s'il n'y en a pas. -->

## Définition de terminé (VIII §51.1)

<!-- Cocher chaque point, ou écrire « sans objet » avec la raison. -->

- [ ] 1. **Tests** : identifiants du catalogue concernés couverts et verts ; comportement nouveau testé ; aucun test sur le réseau externe (VIII §51.1-1, §50.1, §50.5).
- [ ] 2. **Erreurs** : chaque erreur prévue traitée selon sa famille ; aucun `except` silencieux ; messages en base nettoyés des secrets (VIII §51.1-2, VII §42.4).
- [ ] 3. **Logs** : événements structurés aux noms stables, champs de VII §42.2, aucun secret, ni prompt ni réponse LLM en `info` (VIII §51.1-3).
- [ ] 4. **Observabilité** : métriques et conditions associées branchées (VIII §51.1-4, VII §39.2, §39.5).
- [ ] 5. **Configuration** : réglage dans `pipeline.yaml` avec défaut et validation ; variable dans `.env.example` avec son statut (VIII §51.1-5, IV §16, VII §36.7).
- [ ] 6. **Données** : migration Alembic avec `downgrade` ou en-tête « irréversible » ; valeurs fermées ; rétention couverte (VIII §51.1-6, III §10.5, §13).
- [ ] 7. **Architecture** : un seul écrivain par table et par clé `SystemState`, travail CPU hors event-loop, aucun appel réseau en transaction d'écriture, aucun LLM dans le pipeline, l'app n'exécute aucun job, `Clock` pour tout instant (VIII §51.1-7).
- [ ] 8. **Qualité** : `ruff` et `mypy` propres ; CI verte, étapes 1 à 5 sur la branche, 6 sur `main` (VIII §51.1-8, §49.2).
- [ ] 9. **Documentation** : `docs/` à jour ; runbook mis à jour pour toute commande CLI ou procédure ; ADR pour tout choix structurant (VIII §51.1-9, IX §55.4).
