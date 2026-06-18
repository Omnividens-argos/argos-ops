"""Board pack mensuel — pôle Direction (archi v2, S6).

Réutilise la **dataclass** pure :class:`argos_ops.agents.board_reporter.BoardMetrics`
— **aucun re-port**. En local-first (D-017), les KPIs financiers (MRR, burn,
runway, NRR) viennent d'un snapshot ``data/poles/direction/board/metrics.yaml``
maintenu par le fondateur (analogue de ``burn.yaml``), tandis que la **section
opérations** est dérivée de la vue d'ensemble flotte (:class:`FleetSnapshot`) :
volume de faits mémoire et pôles en alerte critique.

⚠️ Le rendu legacy ``render_board_pack`` étiquette ``runs_month`` / ``breakers_tripped``
comme « Agent runs » / « Circuit breakers tripped » (sémantique DB legacy). En
archi v2 ces champs portent une sémantique **flotte** différente (faits mémoire /
pôles critiques), donc on **ne réutilise PAS** ce rendu : :func:`render` produit
un markdown aux libellés corrects. Aucun appel Stripe / DB.

Format du snapshot ::

    mrr_eur: 4500
    burn_eur: 1800
    runway_months: 5.8
    nrr_pct: 104.0       # optionnel
    incidents_month: 1   # optionnel
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path

from argos_ops.agents.board_reporter import BoardMetrics
from argos_ops.poles.config import POLES_DIR
from argos_ops.poles.direction.fleet import FleetSnapshot
from argos_ops.poles.direction.store import load_yaml_mapping

DIRECTION_POLE = "direction"


def metrics_path(*, poles_root: Path = POLES_DIR) -> Path:
    return poles_root / DIRECTION_POLE / "board" / "metrics.yaml"


def _decimal(value: object) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError):
        return None


def _float(value: object) -> float | None:
    if value is None:
        return None
    try:
        return float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None


def _int(value: object, default: int = 0) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, (int, str)):
        try:
            return int(value)
        except ValueError:
            return default
    return default


def build_metrics(
    snapshot: FleetSnapshot, *, poles_root: Path = POLES_DIR, today: date | None = None
) -> BoardMetrics:
    """Assemble les KPIs board pack : finance (snapshot fichier) + ops (flotte)."""
    today = today or date.today()
    raw = load_yaml_mapping(metrics_path(poles_root=poles_root))
    mrr = _decimal(raw.get("mrr_eur")) or Decimal("0")
    return BoardMetrics(
        period=f"{today.year:04d}-{today.month:02d}",
        mrr_eur=mrr,
        arr_eur=mrr * Decimal("12"),
        burn_eur=_decimal(raw.get("burn_eur")),
        runway_months=_float(raw.get("runway_months")),
        nrr_pct=_float(raw.get("nrr_pct")),
        runs_month=snapshot.total_facts,
        breakers_tripped=snapshot.poles_red,
        incidents_month=_int(raw.get("incidents_month")),
    )


def _line_eur(label: str, value: Decimal | None) -> str:
    return (
        f"- **{label}** : {value:.2f} €" if value is not None else f"- **{label}** : _non tracké_"
    )


def render(metrics: BoardMetrics) -> str:
    """Markdown pandoc-ready, libellés **archi v2** (pas le rendu legacy DB).

    La section opérations reflète la sémantique flotte : ``runs_month`` =
    faits mémoire, ``breakers_tripped`` = pôles en alerte critique (cf. docstring
    du module — pourquoi on ne réutilise pas ``render_board_pack``).
    """
    nrr = (
        f"{metrics.nrr_pct:.1f}%"
        if metrics.nrr_pct is not None
        else "_placeholder (cohortes insuffisantes)_"
    )
    runway = (
        f"{metrics.runway_months:.1f} mois" if metrics.runway_months is not None else "_non tracké_"
    )
    lines = [
        "---",
        f'title: "Argos Ops — Board Pack {metrics.period}"',
        'author: "Omnividens"',
        f'date: "{metrics.period}-01"',
        "---",
        "",
        f"# Board Pack — {metrics.period}",
        "",
        "## Finance",
        "",
        f"- **MRR fin de mois** : {metrics.mrr_eur:.2f} €",
        f"- **ARR (12x MRR)** : {metrics.arr_eur:.2f} €",
        _line_eur("Burn mensuel", metrics.burn_eur),
        f"- **Runway estimé** : {runway}",
        f"- **NRR** : {nrr}",
        "",
        "## Opérations (flotte)",
        "",
        f"- **Faits mémoire (flotte)** : {metrics.runs_month}",
        f"- **Pôles en alerte critique** : {metrics.breakers_tripped}",
        f"- **Incidents internes loggés** : {metrics.incidents_month}",
        "",
        "## Décisions structurantes",
        "",
        "Voir le journal des décisions du pôle Direction.",
        "",
        "## TODO board",
        "",
        "- [ ] Revue OKR trimestrielle vs prorata",
        "- [ ] Arbitrage des demandes produit récurrentes",
        "- [ ] Revue compliance (RGPD + AI Act)",
        "",
        "---",
        "",
        "*Pandoc-ready : `pandoc board-YYYY-MM.md -o board-YYYY-MM.pdf --pdf-engine=xelatex`*",
        "",
    ]
    return "\n".join(lines)


__all__ = ["BoardMetrics", "build_metrics", "metrics_path", "render"]
