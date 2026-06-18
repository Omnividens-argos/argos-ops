"""Digests consolidés de la flotte — pôle Direction (archi v2, S6).

Engine pur de mise en forme d'un :class:`~argos_ops.poles.direction.fleet.FleetSnapshot`
en digest markdown + résumé une ligne. Deux portées :

- ``weekly`` — digest hebdomadaire (StrategyBot, « chief of staff ») ;
- ``daily`` — digest quotidien (DigestBuilder, le morning digest de la flotte).

Aucune I/O (le snapshot est passé en argument) — déterministe et testable offline.
Remplace, en local-first, les requêtes Postgres des legacy ``strategy_bot`` /
``digest_builder`` (D-017) : la source de vérité est désormais la mémoire des pôles.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from argos_ops.poles.direction.fleet import FleetSnapshot

Scope = str  # "weekly" | "daily"

_HEALTH_ICON: dict[str, str] = {
    "critical": "🔴",
    "warning": "🟡",
    "healthy": "🟢",
    "idle": "⚪",
}
_SCOPE_LABEL: dict[str, str] = {"weekly": "hebdomadaire", "daily": "quotidien"}


@dataclass(frozen=True)
class DigestReport:
    """Un digest flotte (résumé + markdown)."""

    scope: Scope
    summary: str
    markdown: str
    headline: str  # corps court pour la mémoire


def _headline(snapshot: FleetSnapshot, scope: Scope) -> str:
    label = _SCOPE_LABEL.get(scope, scope)
    return (
        f"Digest {label} flotte : {snapshot.poles_active}/{len(snapshot.poles)} pôle(s) actif(s), "
        f"{snapshot.total_facts} fait(s), {snapshot.poles_red} en alerte critique, "
        f"{snapshot.total_critical} signal(aux) critique(s)."
    )


def build_digest(
    snapshot: FleetSnapshot, *, scope: Scope = "weekly", today: date | None = None
) -> DigestReport:
    """Construit le digest markdown depuis la vue d'ensemble de la flotte."""
    today = today or snapshot.generated_at.date()
    label = _SCOPE_LABEL.get(scope, scope)
    headline = _headline(snapshot, scope)

    lines = [
        f"# Digest {label} — flotte Argos Ops ({today.isoformat()})\n",
        f"> {headline}\n",
        "\n## Santé par pôle\n",
        "| Pôle | Santé | Faits | Important | Critiques |",
        "| --- | --- | --: | --: | --: |",
    ]
    for p in snapshot.poles:
        icon = _HEALTH_ICON.get(p.health, "⚪")
        lines.append(
            f"| {p.name} | {icon} {p.health} | {p.n_facts} | {p.n_important} | {p.n_critical} |"
        )

    red = snapshot.red_poles
    if red:
        lines.append("\n## Pôles en alerte critique\n")
        for p in red:
            lines.append(f"- **{p.name}** — {p.headline or 'signal critique'}")
    else:
        lines.append("\n_Aucun pôle en alerte critique._\n")

    summary = (
        f"{label} · {snapshot.poles_active}/{len(snapshot.poles)} actifs · "
        f"{snapshot.poles_red} rouge(s) · {snapshot.total_critical} critique(s)"
    )
    return DigestReport(
        scope=scope,
        summary=summary,
        markdown="\n".join(lines) + "\n",
        headline=headline,
    )


__all__ = ["DigestReport", "Scope", "build_digest"]
