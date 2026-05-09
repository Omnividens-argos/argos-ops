"""Tests unitaires du module RAG (P6).

Couvrent la logique déterministe (seuil de distance, formatage, prompt
support). Le call réel à ``fastembed`` + Postgres pgvector est testé en
intégration via ``scripts/eval_kb_rag.py`` (10 questions golden).
"""

from __future__ import annotations

import pytest

from argos_ops.rag.embeddings import EMBEDDING_MODEL, embed_query
from argos_ops.rag.search import (
    DEFAULT_DISTANCE_THRESHOLD,
    RAGHit,
    RAGResult,
    build_support_prompt,
    format_context_block,
)


# =============================================================================
# Constants
# =============================================================================
def test_embedding_model_is_768_dims_compatible() -> None:
    """Le modèle figé par D-017 doit être ``mpnet-base-v2`` (768 dims natif)."""
    assert EMBEDDING_MODEL == "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"


def test_default_distance_threshold_is_in_valid_pgvector_range() -> None:
    """pgvector cosine_distance ∈ [0, 2]."""
    assert 0 <= DEFAULT_DISTANCE_THRESHOLD <= 2


# =============================================================================
# embed_query input validation
# =============================================================================
def test_embed_query_rejects_empty_text() -> None:
    with pytest.raises(ValueError, match="empty"):
        embed_query("")


def test_embed_query_rejects_whitespace_only() -> None:
    with pytest.raises(ValueError, match="empty"):
        embed_query("   \n\t  ")


# =============================================================================
# RAGResult
# =============================================================================
def test_rag_result_is_empty_when_no_hits() -> None:
    result = RAGResult(query="foo", hits=[], threshold=0.85)
    assert result.is_empty
    assert result.top_distance is None


def test_rag_result_top_distance_returns_first_hit() -> None:
    hits = [
        RAGHit(doc_path="pricing.md", chunk_index=0, content="x", distance=0.42),
        RAGHit(doc_path="faq.md", chunk_index=2, content="y", distance=0.51),
    ]
    result = RAGResult(query="foo", hits=hits, threshold=0.85)
    assert not result.is_empty
    assert result.top_distance == 0.42


# =============================================================================
# format_context_block
# =============================================================================
def test_format_context_block_empty_says_aucun_extrait() -> None:
    block = format_context_block(RAGResult(query="foo", hits=[], threshold=0.85))
    assert "aucun extrait" in block.lower()


def test_format_context_block_includes_kb_citations() -> None:
    hits = [
        RAGHit(
            doc_path="pricing.md",
            chunk_index=3,
            content="Pro Max coûte 249 €/mois",
            distance=0.31,
        ),
        RAGHit(
            doc_path="faq.md",
            chunk_index=12,
            content="Le scan tourne en 4h en moyenne",
            distance=0.55,
        ),
    ]
    block = format_context_block(RAGResult(query="prix?", hits=hits, threshold=0.85))
    assert "[KB#1: pricing.md§3]" in block
    assert "[KB#2: faq.md§12]" in block
    assert "Pro Max coûte 249 €/mois" in block
    assert "distance=0.310" in block


def test_format_context_block_separator_between_hits() -> None:
    hits = [
        RAGHit(doc_path="a.md", chunk_index=0, content="aa", distance=0.1),
        RAGHit(doc_path="b.md", chunk_index=0, content="bb", distance=0.2),
    ]
    block = format_context_block(RAGResult(query="q", hits=hits, threshold=0.85))
    # 2 hits → 1 séparateur
    assert block.count("\n\n---\n\n") == 1


# =============================================================================
# build_support_prompt
# =============================================================================
def test_support_prompt_contains_anti_hallucination_rules() -> None:
    result = RAGResult(query="combien coûte Pro Max ?", hits=[], threshold=0.85)
    prompt = build_support_prompt(result)
    assert "UNIQUEMENT" in prompt
    assert "ESCALADE" in prompt
    assert "[KB#N" in prompt  # convention citation
    # Le ton de marque doit être mentionné
    assert "anti-FUD" in prompt


def test_support_prompt_includes_query_and_context() -> None:
    hits = [
        RAGHit(
            doc_path="pricing.md",
            chunk_index=0,
            content="Pro Max 249€",
            distance=0.3,
        )
    ]
    result = RAGResult(query="combien coûte Pro Max ?", hits=hits, threshold=0.85)
    prompt = build_support_prompt(result)
    assert "combien coûte Pro Max ?" in prompt
    assert "Pro Max 249€" in prompt
    assert "[KB#1: pricing.md§0]" in prompt


def test_support_prompt_with_empty_hits_still_buildable() -> None:
    """Quand RAG ne trouve rien, le prompt doit quand même se générer
    proprement (Claude répondra ESCALADE)."""
    result = RAGResult(query="quel temps fait-il à Mars ?", hits=[], threshold=0.85)
    prompt = build_support_prompt(result)
    assert "ESCALADE" in prompt
    assert "aucun extrait" in prompt.lower()
