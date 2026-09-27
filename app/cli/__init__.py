"""Commandes d'exploitation `python -m app.cli <commande>` (IX §56.3, §56.4).

Contrat commun (IX §56.3) : codes de sortie `0` succès · `1` échec de l'opération · `2` usage ou configuration
invalide ; résultat lisible sur stdout ; logs structurés sur stderr.
"""

EXIT_OK = 0
EXIT_FAILURE = 1
EXIT_INVALID = 2
