"""``KeywordRadarScript`` — mouvements SERP keywords prioritaires (Veille, archi v2).

Porté depuis ``argos_ops.agents.keyword_radar`` (legacy). Bras déterministe :

1. lit ``data/seo/keywords_tracked.yaml`` (founder-maintained, shadow — aucun
   scraping SERP ici) et garde les keywords ``priority: high`` ;
2. compare aux positions du run précédent archivées dans
   ``data/seo/ranks_history.yaml`` ;
3. écrit chaque mouvement *significatif* dans **sa propre mémoire de pôle**
   (``kind="seo_movement"``) ;
4. réécrit l'historique (snapshot) pour le run suivant.

Pas de Discord, pas de DB, pas de LLM (D-017) : le :class:`VeilleAgent` lit cette
mémoire et agit. La sévérité (une perte > 5 positions) se traduit par le flag
``important=True`` + le tag ``loss`` ; un gain fort ou un nouveau keyword reste
non-important. Idempotent : un mouvement re-détecté a le même corps ⇒ même fait
(le socle :func:`argos_ops.poles.memory.write_memory` déduplique par hash).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

from argos_ops.config import REPO_ROOT
from argos_ops.poles.base import BaseScript, ScriptResult
from argos_ops.poles.config import POLES_DIR

KEYWORDS_PATH = REPO_ROOT / "data" / "seo" / "keywords_tracked.yaml"
HISTORY_PATH = REPO_ROOT / "data" / "seo" / "ranks_history.yaml"

# Seuils de significativité (positif = on est monté dans la SERP).
_LOSS_THRESHOLD = -5  # delta <= -5 -> perte sévère (important)
_GAIN_THRESHOLD = 5  # delta >= +5 -> gain fort


@dataclass
class KeywordMovement:
    """Mouvement d'un keyword entre le run précédent et le run courant."""

    keyword: str
    current: int
    previous: int | None

    @property
    def delta(self) -> int:
        if self.previous is None:
            return 0
        return self.previous - self.current  # positif = on est monté

    @property
    def is_new(self) -> bool:
        return self.previous is None


# =============================================================================
# Helpers déterministes purs (portés du legacy)
# =============================================================================
def load_keywords(path: Path) -> dict[str, int]:
    """Lit les keywords ``priority: high`` du YAML founder-maintained."""
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    out: dict[str, int] = {}
    for entry in data.get("keywords", []):
        if not isinstance(entry, dict):
            continue
        if str(entry.get("priority", "")).lower() != "high":
            continue
        kw = str(entry.get("term", "")).strip()
        pos = entry.get("position")
        if not kw or not isinstance(pos, int):
            continue
        out[kw] = pos
    return out


def load_history(path: Path) -> dict[str, int]:
    """Lit les positions archivées du run précédent."""
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {str(k): int(v) for k, v in data.get("positions", {}).items() if isinstance(v, int)}


def save_history(positions: dict[str, int], path: Path) -> None:
    """Réécrit le snapshot d'historique pour le run suivant."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(yaml.safe_dump({"positions": positions}), encoding="utf-8")


def diff_positions(current: dict[str, int], previous: dict[str, int]) -> list[KeywordMovement]:
    """Croise positions courantes et précédentes en mouvements."""
    movements: list[KeywordMovement] = []
    for kw, pos in current.items():
        movements.append(KeywordMovement(keyword=kw, current=pos, previous=previous.get(kw)))
    return movements


class KeywordRadarScript(BaseScript):
    """Mémorise les mouvements SERP significatifs (``kind="seo_movement"``)."""

    pole = "veille"
    name = "keyword_radar"

    def __init__(
        self,
        *,
        poles_root: Path = POLES_DIR,
        keywords_path: Path = KEYWORDS_PATH,
        history_path: Path = HISTORY_PATH,
    ) -> None:
        super().__init__(poles_root=poles_root)
        self._keywords_path = keywords_path
        self._history_path = history_path

    async def run(self) -> ScriptResult:
        current = load_keywords(self._keywords_path)
        if not current:
            return ScriptResult(
                status="success",
                summary="aucun keyword prioritaire tracké - rien à mémoriser",
                written=[],
            )

        previous = load_history(self._history_path)
        movements = diff_positions(current, previous)

        written = []
        ups = downs = new = 0
        for m in movements:
            if m.is_new:
                new += 1
                record = await self.write_memory(
                    f"SERP : nouveau keyword '{m.keyword}' en position {m.current}",
                    kind="seo_movement",
                    tags=("seo", "new"),
                    important=False,
                    source=self.name,
                )
                written.append(record)
            elif m.delta <= _LOSS_THRESHOLD:
                downs += 1
                record = await self.write_memory(
                    f"SERP : '{m.keyword}' {m.previous}->{m.current} (delta {m.delta:+d})",
                    kind="seo_movement",
                    tags=("seo", "loss"),
                    important=True,
                    source=self.name,
                )
                written.append(record)
            elif m.delta >= _GAIN_THRESHOLD:
                ups += 1
                record = await self.write_memory(
                    f"SERP : '{m.keyword}' {m.previous}->{m.current} (delta {m.delta:+d})",
                    kind="seo_movement",
                    tags=("seo", "gain"),
                    important=False,
                    source=self.name,
                )
                written.append(record)

        save_history(current, self._history_path)

        return ScriptResult(
            status="success",
            summary=f"up={ups} down={downs} new={new} sur {len(movements)} keyword(s) tracké(s)",
            written=written,
        )


__all__ = [
    "KeywordMovement",
    "KeywordRadarScript",
    "diff_positions",
    "load_history",
    "load_keywords",
    "save_history",
]
