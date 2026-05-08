"""Seed la Knowledge Base : chunk markdown → embed local → upsert pgvector.

Usage::

    uv run python scripts/seed_kb.py                  # tous les .md
    uv run python scripts/seed_kb.py --dry-run        # pas d'écriture DB ni d'embedding
    uv run python scripts/seed_kb.py --doc pricing    # filtre sur un fichier

Idempotent : un chunk dont le ``content_hash`` n'a pas changé est skippé,
pas de re-embedding (économise le temps CPU).

Embeddings via ``fastembed`` + ``intfloat/multilingual-e5-base`` (768 dims
natif, multilingue FR-EN, CPU local — D-017). Aucun appel API tiers, aucun
quota, aucune clé. Le premier run télécharge les poids ONNX (~280 MB) dans
le cache utilisateur, ensuite tout tourne offline.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from loguru import logger

from argos_ops.config import REPO_ROOT
from argos_ops.crm.db import dispose_engine, session_scope
from argos_ops.crm.kb_chunker import Chunk, chunk_markdown
from argos_ops.crm.models import KB_EMBEDDING_DIM
from argos_ops.crm.repository import upsert_kb_chunk

if TYPE_CHECKING:
    from collections.abc import Iterable

KB_DIR = REPO_ROOT / "data" / "knowledge_base"
# paraphrase-multilingual-mpnet-base-v2 : 768 dims natif (matche pgvector
# migration), multilingue FR-EN, ~1 GB poids ONNX. Seul modèle multilingue
# 768 dims supporté par fastembed actuellement. Pas de préfixe nécessaire
# (modèle Sentence-BERT, pas e5). Cf. D-017.
EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"


# =============================================================================
# Embedding (local — fastembed ONNX)
# =============================================================================
def _embed(texts: list[str]) -> list[list[float]]:
    """Embed via fastembed local. Bloquant CPU (~50 ms/chunk en CPU moderne)."""
    from fastembed import TextEmbedding  # import local pour ne pas charger en dry-run

    logger.info(f"Loading {EMBEDDING_MODEL} (premier run télécharge ~1 GB)…")
    model = TextEmbedding(model_name=EMBEDDING_MODEL)

    out: list[list[float]] = []
    # fastembed.embed() retourne un générateur de np.ndarray ; on matérialise
    # progressivement et on log tous les 10 chunks.
    for i, vec in enumerate(model.embed(texts)):
        values = vec.tolist()
        if len(values) != KB_EMBEDDING_DIM:
            raise RuntimeError(
                f"Embedding renvoyé {len(values)} dims, attendu "
                f"{KB_EMBEDDING_DIM} — la migration SQL et le modèle "
                f"{EMBEDDING_MODEL} sont désalignés"
            )
        out.append(values)
        if i % 10 == 0 and i > 0:
            logger.info(f"Embedded {i}/{len(texts)} chunks")
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
    # psycopg async exige SelectorEventLoop sur Windows (ProactorEventLoop
    # par défaut sur Win 3.8+ n'est pas compatible).
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    return asyncio.run(amain())


if __name__ == "__main__":
    sys.exit(main())
