"""Embeddings locaux via ``fastembed`` + ``paraphrase-multilingual-mpnet-base-v2``.

Modèle figé par D-017 : 768 dims natif (cf. ``KB_EMBEDDING_DIM``), multilingue
FR-EN, ~1 GB poids ONNX téléchargés au premier appel dans le cache utilisateur,
puis tout tourne offline. Aucun appel API tiers.

L'API publique est :

- :func:`embed_query` — embed un texte unique (utilisé par la recherche RAG)
- :func:`embed_batch` — embed une liste de textes (utilisé par le seed KB)

L'instance ``TextEmbedding`` est mise en cache (singleton process-local) :
le premier appel paie le coût de chargement (~3-5 s), les suivants sont
quasi instantanés.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from loguru import logger

from argos_ops.crm.models import KB_EMBEDDING_DIM

if TYPE_CHECKING:
    from fastembed import TextEmbedding

EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"

_model: TextEmbedding | None = None


def _get_model() -> TextEmbedding:
    """Singleton process-local. Le premier appel paie le chargement (~3-5 s)."""
    global _model
    if _model is None:
        from fastembed import TextEmbedding

        logger.info(f"Loading embedding model {EMBEDDING_MODEL} (premier run télécharge ~1 GB)…")
        _model = TextEmbedding(model_name=EMBEDDING_MODEL)
    return _model


def embed_batch(texts: list[str]) -> list[list[float]]:
    """Embed une liste de textes. Bloquant CPU (~50 ms/chunk en CPU moderne).

    Lève une ``RuntimeError`` si une dimension renvoyée n'est pas 768 (signal
    d'un désalignement entre le modèle et la migration SQL pgvector).
    """
    model = _get_model()
    out: list[list[float]] = []
    for i, vec in enumerate(model.embed(texts)):
        values = vec.tolist()
        if len(values) != KB_EMBEDDING_DIM:
            raise RuntimeError(
                f"Embedding renvoyé {len(values)} dims, attendu "
                f"{KB_EMBEDDING_DIM} — modèle {EMBEDDING_MODEL} et migration "
                f"SQL pgvector désalignés"
            )
        out.append(values)
        if i % 10 == 0 and i > 0:
            logger.info(f"Embedded {i}/{len(texts)} chunks")
    return out


def embed_query(text: str) -> list[float]:
    """Embed une question/requête unique. Wrapper de :func:`embed_batch`."""
    if not text.strip():
        raise ValueError("Cannot embed empty text")
    return embed_batch([text])[0]


__all__ = ["EMBEDDING_MODEL", "embed_batch", "embed_query"]
