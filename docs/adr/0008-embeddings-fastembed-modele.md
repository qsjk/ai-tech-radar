# ADR 0008 — Moteur et modèle d'embeddings

| | |
|---|---|
| **Statut** | Proposé |
| **Date** | 2026-09-23 |
| **Décision(s) couverte(s)** | DV-10 ; III §12 · V-A §24.4 · VII décision 9, §36.5, §45.4 (M1) · IX §57.4 ; rapport de cadrage §3 (V-01) ; `docs/architecture.md` §4.2, P-09 |

## Contexte

Les embeddings servent la similarité, le clustering et la dédup sémantique ; ils appartiennent au cœur et doivent
tourner sans réseau, sur le CPU d'un petit VPS (II §6.1, III §12). Les sources sont en anglais et en français : le
modèle doit être multilingue (III §12.1). Aucun téléchargement de modèle au runtime (VII décision 9). IX §53.2 verrouille
le moteur, pas le modèle : ce choix est consigné ici.

## Décision

Moteur : **fastembed** (onnxruntime), sur CPU, sans PyTorch. Modèle : **`paraphrase-multilingual-MiniLM-L12-v2`**,
384 dimensions, licence Apache-2.0, intégré à l'image au build à une révision épinglée. fastembed le sert depuis la
conversion ONNX **`qdrant/paraphrase-multilingual-MiniLM-L12-v2-onnx-Q`**, révision
`faf4aa4225822f3bc6376869cb1164e8e3feedd0`, fichier `model_optimized.onnx` d'empreinte sha256
`634d0f66c29dc934c8fa72b8a4fe91dd4d420a22f1d82a241058d4316e659a99` (V-01 ; empreintes des autres fichiers au
rapport de cadrage §3). `Embedding.model` vaut `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2@faf4aa42`
(III §11.9).

## Alternatives écartées

- **PyTorch ou sentence-transformers** : plusieurs Go d'image et de RAM pour la même inférence ; exclu par DV-10.
- **API d'embeddings distante** : le cœur dépendrait du réseau et d'un provider (ADR-0003) ; coût par article.
- **Modèle anglais seul (ex. all-MiniLM)** : ne rapprocherait pas un article français de son équivalent anglais (III §12.1) ; V-01 mesure un cosinus FR/EN de 0,96 avec le modèle retenu.
- **Modèle de plus de 384 dimensions** : exclu par DV-10 : mémoire de la fenêtre et coût du cosine (ADR-0002, M2).

## Conséquences

- **On gagne** : faits du Sprint 0 : chargement en 1,7 s depuis le cache, 384 dimensions mesurées ; image autonome, sans accès à un hub au runtime (T-SEC-10).
- **On accepte** : environ **1,0 Gio de RSS** après chargement et un pic à **1,2 Gio** pour le seul modèle (V-01), à ajouter à lingua et à la matrice (M1) ; fastembed renvoie du `float64`, converti en `float32` normalisé à l'écriture (`database.md` §4) ; le chargement local hors ligne par fastembed depuis le dossier du build reste **à confirmer au Sprint 4** (P-09).
- **Preuve de réexamen** : le modèle ou sa révision devient indisponible, ou échoue à la confirmation du Sprint 4 : **repli** prévu par IX §57.4, un autre modèle multilingue de 384 dimensions au plus, supporté par fastembed, consigné dans un ADR qui remplace celui-ci ; M1 hors critère (RAM au-delà de 70 % du VPS) ; **nouveau modèle après la mise en production** : déclencheur conditionnel du registre (ré-embedding sur titre et résumé, III §12.5).

## Preuve

Sans objet : cet ADR ne remplace aucune décision précédente.

## Remplace

Aucun.
