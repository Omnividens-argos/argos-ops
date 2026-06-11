"""Affiche le « IN mémoire » d'un bot — consommé par les slash commands.

Usage :
    uv run python scripts/fleet_memory_in.py LinkedInWriter

Imprime en Markdown les faits actifs visibles par le bot : sa propre
mémoire + celle des bots qu'il a le droit de lire (graphe d'accès de
``data/fleet_memory/MEMORY.md``), du plus récent au plus ancien. C'est
l'étape « charge la mémoire de flotte » des slashs ``/draft-*`` :
Claude Code lance ce script et injecte la sortie comme contexte avant
de drafter. Zéro DB, zéro réseau — pur filesystem.
"""

from __future__ import annotations

import argparse
import asyncio

from argos_ops.fleet_memory import visible_memory


def format_memory_in(bot: str) -> str:
    """Compose le IN mémoire d'un bot en Markdown (pur, testable)."""

    async def _collect() -> str:
        vis = await visible_memory(bot)
        lines: list[str] = [f"# Mémoire de flotte — IN de {bot}", ""]
        total = 0
        for source_bot in sorted(vis):
            facts = vis[source_bot].active_facts
            if not facts:
                continue
            label = "mémoire propre" if source_bot == bot else "mémoire lue"
            lines.append(f"## {source_bot} — {label} ({len(facts)} fait(s))")
            lines.append("")
            for fact in facts:
                ttl_tag = f" · TTL {fact.ttl_days}j" if fact.ttl_days is not None else ""
                pin_tag = " · pinned" if fact.pinned else ""
                lines.append(
                    f"- **[{fact.kind}]** {fact.body} "
                    f"_(confiance {fact.confidence} · {fact.created_at.date()}{ttl_tag}{pin_tag})_"
                )
                total += 1
            lines.append("")
        if total == 0:
            lines.append("_(aucun fait actif accessible — drafte sans contexte mémoire)_")
        return "\n".join(lines)

    return asyncio.run(_collect())


def main() -> None:
    parser = argparse.ArgumentParser(description="IN mémoire d'un bot (Markdown)")
    parser.add_argument("bot", help="Nom canonique du bot (ex. LinkedInWriter)")
    args = parser.parse_args()
    print(format_memory_in(args.bot))


if __name__ == "__main__":
    main()
