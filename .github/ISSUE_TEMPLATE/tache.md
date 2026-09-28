---
name: Tâche
about: Une tâche d'un sprint, au format des issues du projet (docs/planning.md)
title: "SN · TN.N — "
labels: ["type:tâche"]
---

<!--
Titre : « S<n> · T<n>.<m> — <intitulé> », comme dans docs/sprints/sprint-NN.md.
Labels (docs/planning.md) : qui:claude ou qui:moi ; un type parmi type:tâche, type:infra, type:bug, type:dette,
type:adr, type:spec ; gate ou bloquant au besoin.
Milestone : celle du sprint (S0 … S11, Pré-S0, Pré-prod).
Renvoyer à la spec (partie et paragraphe) plutôt que la recopier.
-->

## Contexte

<!-- Pourquoi cette tâche, à quel moment du sprint, ce qu'elle débloque. -->

## Description

<!-- Ce qui est livré : fichiers, comportements, avec les renvois à la spec, au plan du sprint et aux ADR. -->

Hors périmètre :

## Critères d'acceptation

<!-- Vérifiables : identifiants du catalogue (VIII §50.5) couverts et verts, démonstration, CI. -->

- [ ] **T-…** :
- [ ] `ruff`, `mypy` strict et `pytest` sont verts, et chaque commit passe ses propres tests.
- [ ] Règle de langue respectée : code, commentaires et messages en anglais ; documentation, commits et PR en français.

## Références

<!-- docs/sprints/sprint-NN.md T… · parties et paragraphes de la spec · ADR · issues liées -->
