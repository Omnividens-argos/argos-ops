"""Tests du chunker markdown — pure logic, pas d'I/O."""

from __future__ import annotations

from argos_ops.crm.kb_chunker import (
    CHARS_PER_TOKEN,
    DEFAULT_MAX_TOKENS,
    chunk_markdown,
)


def test_empty_doc_returns_empty() -> None:
    assert chunk_markdown("data/kb/empty.md", "") == []
    assert chunk_markdown("data/kb/empty.md", "   \n\n  ") == []


def test_doc_without_h2_yields_one_chunk() -> None:
    md = "# Titre\n\nUn paragraphe simple sans H2."
    chunks = chunk_markdown("data/kb/x.md", md)
    assert len(chunks) == 1
    assert chunks[0].chunk_index == 0
    assert chunks[0].doc_path == "data/kb/x.md"
    assert "Un paragraphe" in chunks[0].content


def test_h2_split_creates_one_chunk_per_section() -> None:
    md = "# Titre\n\nIntro courte.\n\n## Section A\n\nContenu A.\n\n## Section B\n\nContenu B."
    chunks = chunk_markdown("data/kb/x.md", md)
    # Préambule (titre + intro) + 2 sections H2
    assert len(chunks) == 3
    assert "Intro courte" in chunks[0].content
    assert chunks[1].content.startswith("## Section A")
    assert chunks[2].content.startswith("## Section B")
    assert [c.chunk_index for c in chunks] == [0, 1, 2]


def test_chunks_have_unique_indices() -> None:
    md = "## A\n\nfoo\n\n## B\n\nbar\n\n## C\n\nbaz"
    chunks = chunk_markdown("p.md", md)
    indices = [c.chunk_index for c in chunks]
    assert indices == sorted(indices)
    assert len(set(indices)) == len(indices)


def test_long_section_is_resplit_with_overlap() -> None:
    big_text = "x" * (DEFAULT_MAX_TOKENS * CHARS_PER_TOKEN * 3)  # 3 fois la taille max
    md = f"## Long\n\n{big_text}"
    chunks = chunk_markdown("p.md", md)
    assert len(chunks) >= 3
    for c in chunks:
        assert len(c.content) <= DEFAULT_MAX_TOKENS * CHARS_PER_TOKEN + 50


def test_content_hash_is_stable() -> None:
    md = "## A\n\nstable content"
    a = chunk_markdown("p.md", md)
    b = chunk_markdown("p.md", md)
    assert a[0].content_hash == b[0].content_hash
    assert len(a[0].content_hash) == 64  # sha256 hex
