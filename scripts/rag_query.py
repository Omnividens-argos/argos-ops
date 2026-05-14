"""Petit utilitaire ad-hoc : query la KB Argos en CLI.

Usage : uv run python scripts/rag_query.py "ma question"
        uv run python scripts/rag_query.py --top 8 --threshold 0.95 "..."

Sortie : liste compacte des hits (doc_path, chunk_index, distance,
preview 200 premiers caractères). Utile pour piloter content-writer
ou seo-brief-writer sans passer par le slash command interactif.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from argos_ops.crm.db import session_scope
from argos_ops.rag.search import search_kb


async def _run(query: str, top_k: int, threshold: float) -> int:
    async with session_scope() as session:
        result = await search_kb(
            session,
            query=query,
            top_k=top_k,
            distance_threshold=threshold,
        )

    if result.is_empty:
        print(f"[ESCALADE] Aucun chunk sous seuil {threshold}")
        print(f"  top_distance = {result.top_distance}")
        return 1

    print(f"[OK] {len(result.hits)} hits sous seuil {threshold} (top={result.top_distance:.4f})")
    for n, hit in enumerate(result.hits, start=1):
        preview = hit.content.replace("\n", " ").strip()[:200]
        print(f"\n[KB#{n}: {hit.doc_path}§{hit.chunk_index}] dist={hit.distance:.4f}")
        print(f"  {preview}{'...' if len(hit.content) > 200 else ''}")
    return 0


def main() -> int:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    parser = argparse.ArgumentParser()
    parser.add_argument("query", help="Texte de la requête")
    parser.add_argument("--top", type=int, default=5)
    parser.add_argument("--threshold", type=float, default=0.85)
    args = parser.parse_args()

    return asyncio.run(_run(args.query, args.top, args.threshold))


if __name__ == "__main__":
    sys.exit(main())
