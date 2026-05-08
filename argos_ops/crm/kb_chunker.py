"""Chunking de fichiers markdown KB.

Stratégie (P3.3) :
- Split par section H2 d'abord
- Si une section dépasse ``max_tokens`` (~800), re-split en blocs de
  ``max_tokens`` avec overlap ``overlap_tokens`` (~100)
- 1 token ≈ 4 caractères (approximation tokenizer standard, suffisante
  pour de la KB FR/EN courante — pas besoin d'un vrai tokenizer ici)

Pure logic, pas d'I/O DB ni d'appel réseau. Testable en pur unit.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass

CHARS_PER_TOKEN = 4
DEFAULT_MAX_TOKENS = 800
DEFAULT_OVERLAP_TOKENS = 100

_H2_RE = re.compile(r"^##\s", re.MULTILINE)


@dataclass(frozen=True)
class Chunk:
    doc_path: str
    chunk_index: int
    content: str
    content_hash: str


def _hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _split_by_h2(markdown: str) -> list[str]:
    """Split sur ``##`` au début de ligne, en gardant le ``##`` dans chaque bloc."""
    matches = list(_H2_RE.finditer(markdown))
    if not matches:
        return [markdown.strip()] if markdown.strip() else []

    sections: list[str] = []
    # Préambule avant le premier H2 (titre H1, intro, etc.)
    first_start = matches[0].start()
    if first_start > 0:
        preamble = markdown[:first_start].strip()
        if preamble:
            sections.append(preamble)

    for i, match in enumerate(matches):
        start = match.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(markdown)
        block = markdown[start:end].strip()
        if block:
            sections.append(block)
    return sections


def _split_by_size(
    text: str, max_tokens: int = DEFAULT_MAX_TOKENS, overlap_tokens: int = DEFAULT_OVERLAP_TOKENS
) -> list[str]:
    """Découpe un texte trop long en sous-blocs avec overlap."""
    max_chars = max_tokens * CHARS_PER_TOKEN
    overlap_chars = overlap_tokens * CHARS_PER_TOKEN

    if len(text) <= max_chars:
        return [text]

    out: list[str] = []
    start = 0
    while start < len(text):
        end = start + max_chars
        out.append(text[start:end].strip())
        if end >= len(text):
            break
        start = end - overlap_chars
    return [b for b in out if b]


def chunk_markdown(
    doc_path: str,
    markdown: str,
    *,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    overlap_tokens: int = DEFAULT_OVERLAP_TOKENS,
) -> list[Chunk]:
    """Chunk un fichier KB en chunks indexés."""
    sections = _split_by_h2(markdown)
    chunks: list[Chunk] = []
    idx = 0
    for section in sections:
        for block in _split_by_size(section, max_tokens, overlap_tokens):
            chunks.append(
                Chunk(
                    doc_path=doc_path,
                    chunk_index=idx,
                    content=block,
                    content_hash=_hash(block),
                )
            )
            idx += 1
    return chunks


__all__ = [
    "CHARS_PER_TOKEN",
    "DEFAULT_MAX_TOKENS",
    "DEFAULT_OVERLAP_TOKENS",
    "Chunk",
    "chunk_markdown",
]
