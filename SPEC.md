# AI Tech Radar — spécification

Plateforme personnelle de veille technologique qui collecte, dédoublonne, regroupe et hiérarchise l'actualité technique,
et reste pleinement utilisable quand l'intelligence AI est indisponible.

**Version** : V0.4, impacts reportés le 2026-09-23 (Sprint 0 : T0.1, puis réconciliation de la Partie VII par T0.2b, #67). Le contenu vit dans `docs/spec/`, une partie par fichier ; ce fichier n'en est que l'index.

## Sommaire

| Partie | Paragraphes |
|---|---|
| [I — Vision & Objectifs](docs/spec/partie-I.md) | §1 Objectif · §2 Périmètre · §3 Fonctions du système · §4 Philosophie générale · §5 Non-objectifs V1 |
| [II — Architecture](docs/spec/partie-II.md) | §6 Principe fondamental · §7 Architecture cible · §8 Architecture des processus · §9 Résilience |
| [III — Données](docs/spec/partie-III.md) | §10 SQLite · §11 Modèle de données · §12 Embeddings · §13 Rétention des données |
| [IV — Pipeline d'ingestion](docs/spec/partie-IV.md) | §14 Pipeline · §15 Collectors · §16 Seed des sources, topics et entités · §17 Extraction de contenu · §18 Normalisation · §19 Déduplication exacte · §20 Relevance filter · §21 Rate limiting, quota et scheduler · §22 Authentification des APIs |
| [V-A — Intelligence : machinerie & tâches LLM](docs/spec/partie-V-A.md) | §23 AI Job Queue · §24 Worker & scheduler · §25 LLM Gateway & LLMClient · §26 Résilience LLM & retry · §27 LLM Tasks & réduction des appels |
| [V-B — Intelligence : clustering, trends & sujets émergents](docs/spec/partie-V-B.md) | §28 Event clustering · §29 Trend Engine · §30 Emerging topics |
| [VI — Interfaces](docs/spec/partie-VI.md) | §31 Dashboard · §32 Auth dashboard · §33 Alerts · §34 Préférences utilisateur |
| [VII — Ops & Production](docs/spec/partie-VII.md) | §35 Stack · §36 Infra / VPS · §37 HTTPS & Caddy · §38 Backup & restore · §39 Monitoring · §40 Health endpoint · §41 Monitoring externe · §42 Logging · §43 Sécurité · §44 Stockage · §45 Coût & performance cibles |
| [VIII — Livraison](docs/spec/partie-VIII.md) | §46 Repository · §47 Sprints · §48 Ordre d'implémentation · §49 CI/CD · §50 Tests · §51 Definition of Done · §52 Critères de mise en production |
| [IX — Gouvernance & démarrage](docs/spec/partie-IX.md) | §53 Décisions verrouillées · §54 ADR · §55 Documentation · §56 Runbook · §57 Première mission — Sprint 0 |

## Règles de lecture

- La spec est le **contrat de développement** : le code s'y conforme.
- Aucune partie ne l'emporte sur une autre. Un conflit entre parties est **signalé**, jamais tranché par l'implémenteur (Partie VIII §51.3).
- Les décisions verrouillées et leur règle de changement sont au §53 ; elles ne sont pas recopiées ici.

## Renvois

- Décisions verrouillées : [Partie IX §53](docs/spec/partie-IX.md#53-décisions-verrouillées).
- Registre des ADR : [`docs/adr/README.md`](docs/adr/README.md).
