"""Recherche RAG sur la Knowledge Base Argos Ops.

Pipeline :

1. Embed de la query via ``argos_ops.rag.embeddings.embed_query`` (fastembed local)
2. Recherche cosine top-K sur ``kb_chunks`` via pgvector
3. Filtrage optionnel sur seuil de distance (anti-hallucination : si le top
   est trop loin, on retourne un résultat vide → escalade Tier 2)
4. Formatage en bloc texte prêt à injecter dans un prompt Claude
"""

from __future__ import annotations

from dataclasses import dataclass

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from argos_ops.crm.models import KBChunk
from argos_ops.crm.repository import search_kb_similar
from argos_ops.rag.embeddings import embed_query

# Seuil de distance cosine au-delà duquel on considère qu'aucun chunk
# n'est vraiment pertinent. pgvector cosine_distance ∈ [0, 2]
# (0 = identique, 1 = orthogonal, 2 = opposé).
#
# Calibré 2026-05-09 sur ``scripts/eval_kb_rag.py`` : 0.7 isole correctement
# les questions in-KB (top dist 0.42-0.55) des questions hors-KB (top dist
# > 0.77 sauf bruit sémantique sur termes techniques).
#
# Note : la couche LLM via ``build_support_prompt`` reste la barrière finale
# anti-hallucination (« réponds UNIQUEMENT depuis les extraits »), donc
# un seuil un peu laxiste est acceptable — l'agent-juge Tier 1 (P14)
# vérifiera que les claims pointent vers de vrais chunks.
DEFAULT_DISTANCE_THRESHOLD = 0.7


@dataclass(frozen=True)
class RAGHit:
    """Un chunk pertinent retrouvé par la recherche."""

    doc_path: str
    chunk_index: int
    content: str
    distance: float  # pgvector cosine distance, 0 = identique, 2 = opposé


@dataclass
class RAGResult:
    """Résultat d'une recherche RAG."""

    query: str
    hits: list[RAGHit]
    threshold: float

    @property
    def is_empty(self) -> bool:
        """Aucun hit assez proche pour répondre — escalade Tier 2."""
        return len(self.hits) == 0

    @property
    def top_distance(self) -> float | None:
        return self.hits[0].distance if self.hits else None


# =============================================================================
# Recherche
# =============================================================================
async def search_kb(
    session: AsyncSession,
    query: str,
    *,
    top_k: int = 5,
    distance_threshold: float = DEFAULT_DISTANCE_THRESHOLD,
) -> RAGResult:
    """Recherche les ``top_k`` chunks les plus proches de ``query``.

    Filtre les hits dont la distance dépasse ``distance_threshold`` :
    un retour vide signifie « aucune réponse fiable, escalade ».

    Convention pgvector : distance cosine ∈ [0, 2].
    """
    if not query.strip():
        raise ValueError("query is empty")

    embedding = embed_query(query)
    raw_hits = await search_kb_similar(session, query_embedding=embedding, limit=top_k)

    hits: list[RAGHit] = []
    for chunk, distance in raw_hits:
        if distance > distance_threshold:
            continue
        hits.append(
            RAGHit(
                doc_path=chunk.doc_path,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                distance=distance,
            )
        )

    logger.info(
        f"RAG query='{query[:60]}' top_k={top_k} hits={len(hits)}/{len(raw_hits)} "
        f"(seuil distance ≤ {distance_threshold})"
    )
    return RAGResult(query=query, hits=hits, threshold=distance_threshold)


# =============================================================================
# Formatage pour injection dans un prompt Claude
# =============================================================================
def format_context_block(result: RAGResult) -> str:
    """Concatène les hits en bloc citable.

    Format : numéroté + chemin doc + chunk index + contenu. Permet à Claude
    de citer ``[KB#1: pricing.md§3]`` dans sa réponse pour traçabilité.
    """
    if result.is_empty:
        return "(aucun extrait pertinent dans la KB)"
    parts: list[str] = []
    for i, hit in enumerate(result.hits, start=1):
        header = f"[KB#{i}: {hit.doc_path}§{hit.chunk_index}] (distance={hit.distance:.3f})"
        parts.append(f"{header}\n{hit.content}")
    return "\n\n---\n\n".join(parts)


def build_support_prompt(result: RAGResult) -> str:
    """Prompt système anti-hallucination pour SupportBot Tier 1.

    Instructions strictes : ne répondre QUE depuis les extraits, sinon
    escalader. Cohérent avec le garde-fou ARGOS_OPS_PLAN § 6.2.
    """
    context = format_context_block(result)
    return (
        "Tu es SupportBot Tier 1 — assistant produit Argos / SecHunter / Omnividens.\n"
        "\n"
        "Règles strictes :\n"
        "1. Réponds UNIQUEMENT à partir des extraits de la Knowledge Base ci-dessous.\n"
        "2. Cite tes sources avec la référence [KB#N: doc§index] à la fin de chaque\n"
        "   affirmation factuelle (prix, feature, intégration).\n"
        "3. Si la question n'est pas couverte par les extraits, réponds exactement :\n"
        '   "ESCALADE: <raison courte>" et ne tente PAS de répondre.\n'
        "4. Respecte le ton de marque : factuel, anti-FUD, pas de superlatif gratuit.\n"
        "5. Pas de placeholder hallucinant (ex: « notre équipe va revenir vers vous »\n"
        "   sans qu'un extrait le confirme).\n"
        "\n"
        f"Question : {result.query}\n"
        "\n"
        "Extraits Knowledge Base :\n"
        f"{context}\n"
    )


__all__ = [
    "DEFAULT_DISTANCE_THRESHOLD",
    "KBChunk",  # ré-export pour les consommateurs
    "RAGHit",
    "RAGResult",
    "build_support_prompt",
    "format_context_block",
    "search_kb",
]
