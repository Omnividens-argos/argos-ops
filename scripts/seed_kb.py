"""Seed la Knowledge Base : chunk markdown → embed Gemini → upsert pgvector.

Usage::

    uv run python scripts/seed_kb.py                  # tous les .md
    uv run python scripts/seed_kb.py --dry-run        # pas d'écriture DB ni d'embedding
    uv run python scripts/seed_kb.py --doc pricing    # filtre sur un fichier

Idempotent : un chunk dont le ``content_hash`` n'a pas changé est skippé,
pas de re-embedding (économise le quota Gemini).
"""

from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

from argos_ops.config import REPO_ROOT, get_settings
from argos_ops.crm.db import dispose_engine, session_scope
from argos_ops.crm.kb_chunker import Chunk, chunk_markdown
from argos_ops.crm.models import KB_EMBEDDING_DIM
from argos_ops.crm.repository import upsert_kb_chunk

if TYPE_CHECKING:
    from collections.abc import Iterable

KB_DIR = REPO_ROOT / "data" / "knowledge_base"
GEMINI_EMBEDDING_MODEL = "gemini-embedding-001"


# =============================================================================
# Embedding (Gemini)
# =============================================================================
def _embed(texts: list[str]) -> list[list[float]]:
    """Embed via google-genai SDK. Bloquant (le SDK n'expose pas d'async stable)."""
    from google import genai  # import local pour ne pas charger le SDK en dry-run

    settings = get_settings()
    if settings.gemini_api_key is None:
        raise RuntimeError("GEMINI_API_KEY manquante dans .env.local — impossible d'embed")

    client = genai.Client(api_key=settings.gemini_api_key.get_secret_value())
    out: list[list[float]] = []
    for chunk_text in texts:
        response = client.models.embed_content(
            model=GEMINI_EMBEDDING_MODEL,
            contents=chunk_text,
        )
        # Le SDK retourne ``response.embeddings: list[ContentEmbedding] | None``
        # avec ``.values: list[float] | None``. On valide non-None puis dim.
        if not response.embeddings:
            raise RuntimeError("Gemini a renvoyé une réponse sans embedding")
        raw_values = response.embeddings[0].values
        if raw_values is None:
            raise RuntimeError("Gemini a renvoyé un embedding sans valeurs")
        values = list(raw_values)
        if len(values) != KB_EMBEDDING_DIM:
            raise RuntimeError(
                f"Embedding renvoyé {len(values)} dims, attendu {KB_EMBEDDING_DIM} — "
                "la migration SQL et le modèle Gemini sont désalignés"
            )
        out.append(values)
        # Rate-limit doux pour le free tier (15 req/min en sécurité)
        time.sleep(0.05)
    return out


# =============================================================================
# Pipeline
# =============================================================================
def _list_kb_files(kb_dir: Path, doc_filter: str | None) -> list[Path]:
    if not kb_dir.exists():
        logger.warning(f"KB dir inexistant : {kb_dir}")
        return []
    files = sorted(kb_dir.glob("*.md"))
    if doc_filter:
        files = [f for f in files if doc_filter in f.stem]
    return files


def _chunks_for_files(files: Iterable[Path]) -> list[Chunk]:
    all_chunks: list[Chunk] = []
    for path in files:
        rel = path.relative_to(REPO_ROOT).as_posix()
        text = path.read_text(encoding="utf-8")
        chunks = chunk_markdown(rel, text)
        logger.info(f"{rel}: {len(chunks)} chunks")
        all_chunks.extend(chunks)
    return all_chunks


async def _seed(chunks: list[Chunk], *, dry_run: bool) -> tuple[int, int]:
    """Retourne ``(inserted_or_updated, skipped)``."""
    if dry_run:
        logger.info("DRY RUN — pas d'embedding, pas d'écriture DB")
        return 0, len(chunks)

    embeddings = _embed([c.content for c in chunks])

    inserted = 0
    skipped = 0
    async with session_scope() as session:
        for chunk, embedding in zip(chunks, embeddings, strict=True):
            written = await upsert_kb_chunk(
                session,
                doc_path=chunk.doc_path,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                content_hash=chunk.content_hash,
                embedding=embedding,
            )
            if written:
                inserted += 1
            else:
                skipped += 1
    return inserted, skipped


# =============================================================================
# CLI
# =============================================================================
def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Seed Knowledge Base Argos Ops")
    p.add_argument("--kb-dir", type=Path, default=KB_DIR, help="Dossier KB markdown")
    p.add_argument("--doc", default=None, help="Filtre sur stem (ex: 'pricing')")
    p.add_argument("--dry-run", action="store_true", help="Chunk seul, pas d'embed/DB")
    return p.parse_args()


async def amain() -> int:
    args = _parse_args()

    files = _list_kb_files(args.kb_dir, args.doc)
    if not files:
        logger.warning("Aucun fichier .md trouvé — rien à seed")
        return 0

    chunks = _chunks_for_files(files)
    if not chunks:
        logger.warning("Aucun chunk produit — fichiers vides ?")
        return 0

    try:
        inserted, skipped = await _seed(chunks, dry_run=args.dry_run)
    finally:
        await dispose_engine()

    logger.success(
        f"Done. {len(chunks)} chunks · {inserted} insérés/maj · {skipped} skippés (idem)"
    )
    return 0


def main() -> int:
    return asyncio.run(amain())


if __name__ == "__main__":
    sys.exit(main())
