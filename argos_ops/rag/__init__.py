"""RAG (Retrieval-Augmented Generation) — recherche similarité dans la KB.

Module appelé par :
- ``/run-support-tier1`` (P6) — réponse Tier 1 sur questions fréquentes
- ``/check-emails`` (P5) — drafting email avec contexte produit
- ``ChatBot`` widget (P8) — réponses temps réel
- ``ContentBot`` (P9) — recherche d'angles éditoriaux

Toutes les inférences LLM passent par Claude Code Pro Max (D-017).
Ce module ne fait QUE la recherche vectorielle locale.
"""
