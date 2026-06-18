"""``TrendSpotterScript`` — sujets cyber chauds, fenêtre 14j (Veille, archi v2).

Porté depuis ``argos_ops.agents.trend_spotter`` (legacy). Bras déterministe :

1. lit ``data/trends/sources.yaml`` (founder-maintained, shadow — aucun scraping
   ici) via le module domaine :mod:`argos_ops.marketing.trends` ;
2. score chaque item par *recence x poids*, garde la fenetre 14j ;
3. écrit les top sujets dans **sa propre mémoire de pôle** (``kind="trend"``).

Pas de Discord, pas de DB, pas de LLM (D-017) : le :class:`VeilleAgent` lit cette
mémoire et agit. Idempotent : un sujet re-détecté a le même corps ⇒ même fait
(le socle :func:`argos_ops.poles.memory.write_memory` déduplique par hash).

C'est le **gabarit de référence** des autres scripts Veille : importer le socle,
porter la logique pure, écrire la mémoire, renvoyer un :class:`ScriptResult`.
"""

from __future__ import annotations

from pathlib import Path

from argos_ops.marketing.trends import load_trend_sources, score_trends
from argos_ops.poles.base import BaseScript, ScriptResult
from argos_ops.poles.config import POLES_DIR

_LOOKBACK_DAYS = 14
_TOP_N = 5
_TOP_IMPORTANT_RANK = 3  # les 3 premiers sujets sont marqués important


class TrendSpotterScript(BaseScript):
    """Repère les sujets cyber chauds et les mémorise (``kind="trend"``)."""

    pole = "veille"
    name = "trend_spotter"

    def __init__(
        self,
        *,
        poles_root: Path = POLES_DIR,
        sources_path: Path | None = None,
    ) -> None:
        super().__init__(poles_root=poles_root)
        self._sources_path = sources_path

    async def run(self) -> ScriptResult:
        items = load_trend_sources(self._sources_path)
        fresh = score_trends(items, lookback_days=_LOOKBACK_DAYS)
        top = fresh[:_TOP_N]

        written = []
        for rank, item in enumerate(top):
            tags = ("cyber", *item.keywords[:3])
            record = await self.write_memory(
                f"Sujet cyber chaud (fenetre {_LOOKBACK_DAYS}j) : {item.title}",
                kind="trend",
                tags=tags,
                important=rank < _TOP_IMPORTANT_RANK,
                source=item.url or self.name,
            )
            written.append(record)

        return ScriptResult(
            status="success",
            summary=f"{len(top)} sujet(s) chaud(s) mémorisé(s) sur {len(fresh)} frais",
            written=written,
        )


__all__ = ["TrendSpotterScript"]
