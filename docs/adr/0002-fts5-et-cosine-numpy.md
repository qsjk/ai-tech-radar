# ADR 0002 — Recherche et similarité dans le processus : FTS5, cosine numpy

| | |
|---|---|
| **Statut** | Proposé |
| **Date** | 2026-09-23 |
| **Décision(s) couverte(s)** | DV-03, DV-04 ; II décision 10 · III §11.14, §12.3, §12.4 · VII §45.3 (M2) · IX §53.3 |

## Contexte

Il faut une recherche plein texte sur l'historique (I §3, fonction 13) et une similarité entre articles récents
pour le clustering et la dédup sémantique (III §12, V-B §28). Le produit reste sur un VPS, mono-utilisateur, sans
service de plus que nécessaire (I §4.3). La fenêtre de similarité compte de l'ordre de 2 000 articles, 30 000 au
profil cible (VII §45.3).

## Décision

La recherche plein texte est l'index SQLite FTS5 `article_fts`, maintenu par triggers (III §11.14). La similarité
est un cosine brute-force numpy sur une fenêtre glissante tenue en mémoire par le worker, avec des vecteurs `float32`
normalisés stockés en BLOB (III §12.3, §12.4).

## Alternatives écartées

- **Elasticsearch, OpenSearch ou tout moteur externe** : un service permanent de plus, une seconde source de vérité à synchroniser, pour une recherche mono-utilisateur que FTS5 couvre (IX §53.3).
- **Base vectorielle ou extension `sqlite-vec`** : un index n'apporte rien à cette taille de fenêtre : environ 3 Mo de vecteurs en mémoire pour 2 000 articles (III §12.4) ; interdit sans preuve (IX §53.3).
- **Recherche sémantique en V1** : hors fonction 13 de la Partie I, reportée en V2 (I §3, III « Reporté en V2 ») ; les embeddings conservés la rendront possible.

## Conséquences

- **On gagne** : aucune dépendance de recherche hors SQLite ; index plein texte toujours cohérent avec `article` ; similarité sans réseau ni service.
- **On accepte** : un coût CPU linéaire en taille de fenêtre ; la matrice est reconstruite au démarrage du worker ; la recherche reste lexicale en V1.
- **Preuve de réexamen** : **M2 hors critère** (cosine d'un article sur la fenêtre > 50 ms au profil cible, VII §45.3) : déclencheur conditionnel du registre, ADR `sqlite-vec` ou autre index vectoriel qui remplace celui-ci (IX §54.3) ; M9 (latence de recherche) hors critère ; besoin validé de recherche sémantique.

## Preuve

Sans objet : cet ADR ne remplace aucune décision précédente.

## Remplace

Aucun.
