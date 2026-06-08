"""BloctelGuard — Compliance Bloctel (P22.E Compliance Sprint 8).

Vérifie l'existence et la fraîcheur d'une liste mensuelle Bloctel
(``data/compliance/bloctel/bloctel_YYYY-MM.txt``) et croise les numéros
de téléphone de ``data/outbound/inbox/leads.csv`` contre la liste pour
pré-filtrer les leads BtoC interdits de démarchage téléphonique.

Pas de slash command — exécution cron pur (mensuel). Le check est silencieux
si tout est ok.

Politique anti-spam :
- **Silence** Discord si la liste est < 35 jours ET aucun match leads
- **Embed jaune** si ≥1 lead match Bloctel (à retirer de la séquence
  outbound avant tout envoi)
- **Embed rouge** si la liste est absente ou > 35 jours (mise à jour
  mensuelle obligatoire selon le code de la consommation)

Cf. plan ``docs/ARGOS_OPS_PLAN.md`` Annexe D § 9 Compliance, Sprint 8.

Argos étant BtoB primaire, ce bot est surtout un filet de sécurité : un
contact BtoC qui se glisserait dans la liste outbound serait
immédiatement signalé avant tout envoi.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import UTC, date, datetime
from pathlib import Path

from argos_ops.agents._watcher_base import color_title, emit_alert_or_silence
from argos_ops.agents.base import BaseAgent, IOItem, RunResult
from argos_ops.compliance import is_phone_on_bloctel
from argos_ops.config import REPO_ROOT
from argos_ops.notifications.discord import GREEN, RED, YELLOW, Embed, EmbedField

DEFAULT_BLOCTEL_DIR: Path = REPO_ROOT / "data" / "compliance" / "bloctel"
DEFAULT_LEADS_CSV: Path = REPO_ROOT / "data" / "outbound" / "inbox" / "leads.csv"
MAX_LIST_AGE_DAYS = 35  # marge sur le cycle mensuel


@dataclass(frozen=True)
class BloctelMatch:
    """Un lead trouvé dans la liste Bloctel."""

    phone: str
    lead_identifier: str  # email ou slug du lead


@dataclass(frozen=True)
class BloctelGuardReport:
    """Résultat agrégé du run BloctelGuard."""

    list_path: Path | None
    list_age_days: int | None
    matches: list[BloctelMatch]
    leads_checked: int
    should_alert: bool
    alert_color: int
    summary: str


# =============================================================================
# Resolve la liste la plus récente
# =============================================================================
def find_latest_list(bloctel_dir: Path) -> Path | None:
    """Retourne le fichier ``bloctel_YYYY-MM.txt`` le plus récent dans le dir."""
    if not bloctel_dir.exists():
        return None
    candidates = sorted(bloctel_dir.glob("bloctel_*.txt"))
    return candidates[-1] if candidates else None


def list_age(list_path: Path, *, today: date) -> int | None:
    """Calcule l'âge en jours depuis la date encodée dans le nom du fichier.

    Convention : ``bloctel_YYYY-MM.txt`` → on prend le 1er du mois comme
    référence (pire cas : liste prise au début du mois).
    """
    stem = list_path.stem  # bloctel_2026-05
    parts = stem.split("_")
    if len(parts) != 2:
        return None
    try:
        ym = parts[1]
        year, month = ym.split("-")
        ref_date = date(int(year), int(month), 1)
    except (ValueError, IndexError):
        return None
    return (today - ref_date).days


# =============================================================================
# Lecture leads CSV
# =============================================================================
def load_lead_phones(csv_path: Path) -> list[tuple[str, str]]:
    """Retourne la liste ``(identifiant, phone)`` depuis le CSV outbound.

    On accepte les colonnes ``phone``, ``telephone``, ``mobile``.
    L'identifiant est ``email`` si présent, sinon ``slug``, sinon le numéro.
    """
    if not csv_path.exists():
        return []
    out: list[tuple[str, str]] = []
    with csv_path.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            return []
        phone_keys = [
            k for k in reader.fieldnames if k.lower() in ("phone", "telephone", "mobile")
        ]
        if not phone_keys:
            return []
        for row in reader:
            phone = next((row.get(k, "").strip() for k in phone_keys if row.get(k)), "")
            if not phone:
                continue
            identifier = row.get("email") or row.get("slug") or phone
            out.append((identifier.strip(), phone))
    return out


# =============================================================================
# Décision
# =============================================================================
def build_report(
    *,
    list_path: Path | None,
    list_age_days: int | None,
    matches: list[BloctelMatch],
    leads_checked: int,
) -> BloctelGuardReport:
    list_too_old = list_age_days is None or list_age_days > MAX_LIST_AGE_DAYS

    if list_path is None or list_too_old:
        alert_color = RED
        should_alert = True
        if list_path is None:
            summary = "liste Bloctel introuvable (MAJ mensuelle obligatoire)"
        else:
            summary = (
                f"liste Bloctel trop ancienne ({list_age_days}j > "
                f"{MAX_LIST_AGE_DAYS}j) — MAJ mensuelle obligatoire"
            )
    elif matches:
        alert_color = YELLOW
        should_alert = True
        summary = (
            f"{len(matches)} lead(s) BtoC dans Bloctel (sur {leads_checked} testés) — "
            "retirer avant tout envoi"
        )
    else:
        alert_color = GREEN
        should_alert = False
        summary = (
            f"0 match Bloctel sur {leads_checked} leads (liste âgée de "
            f"{list_age_days}j)"
        )

    return BloctelGuardReport(
        list_path=list_path,
        list_age_days=list_age_days,
        matches=matches,
        leads_checked=leads_checked,
        should_alert=should_alert,
        alert_color=alert_color,
        summary=summary,
    )


# =============================================================================
# Formatting
# =============================================================================
def build_bloctel_embed(
    report: BloctelGuardReport, *, now: datetime | None = None
) -> Embed:
    """Embed Discord — un field par lead matché."""
    now = now or datetime.now(UTC)
    fields = [
        EmbedField(
            name=f"[BTC] {m.lead_identifier}",
            value=f"phone `{m.phone}`",
            inline=False,
        )
        for m in report.matches[:15]
    ]
    title_status = color_title(report.alert_color, green=GREEN, yellow=YELLOW, red=RED)
    return Embed(
        title=f"BloctelGuard — {title_status}",
        description=report.summary,
        color=report.alert_color,
        fields=fields,
        footer="Argos Ops • BloctelGuard",
        timestamp=now.isoformat(),
    )


# =============================================================================
# Agent
# =============================================================================
class BloctelGuard(BaseAgent):
    """Compliance Bloctel — filtre les leads BtoC dans la liste d'opposition."""

    name = "BloctelGuard"
    command = None  # cron pur
    breaker_name = None
    ai_act_risk_class = "minimal"

    def __init__(
        self,
        *,
        bloctel_dir: Path = DEFAULT_BLOCTEL_DIR,
        leads_csv: Path = DEFAULT_LEADS_CSV,
        today: date | None = None,
    ) -> None:
        self._bloctel_dir = bloctel_dir
        self._leads_csv = leads_csv
        self._today = today or datetime.now(UTC).date()

    async def run(self) -> RunResult:
        list_path = find_latest_list(self._bloctel_dir)
        age = list_age(list_path, today=self._today) if list_path else None

        matches: list[BloctelMatch] = []
        leads = load_lead_phones(self._leads_csv)
        if list_path is not None:
            for identifier, phone in leads:
                if is_phone_on_bloctel(phone, bloctel_list_path=list_path):
                    matches.append(BloctelMatch(phone=phone, lead_identifier=identifier))

        report = build_report(
            list_path=list_path,
            list_age_days=age,
            matches=matches,
            leads_checked=len(leads),
        )
        inputs = [
            IOItem(
                label="Liste Bloctel mensuelle",
                kind="file",
                detail=(
                    f"{list_path.name} ({age}j)" if list_path is not None else "introuvable"
                ),
                ref=str(list_path) if list_path is not None else None,
            ),
            IOItem(
                label="Leads outbound (téléphones)",
                kind="file",
                detail=str(self._leads_csv),
                ref=str(self._leads_csv),
                count=len(leads),
            ),
        ]
        outputs = [
            IOItem(
                label="Leads BtoC matchés Bloctel",
                kind="other",
                detail=", ".join(m.lead_identifier for m in matches) or None,
                count=len(matches),
            )
        ]
        return await emit_alert_or_silence(
            report,
            embed_builder=build_bloctel_embed,
            agent_name=self.name,
            inputs=inputs,
            outputs=outputs,
        )


__all__ = [
    "DEFAULT_BLOCTEL_DIR",
    "DEFAULT_LEADS_CSV",
    "MAX_LIST_AGE_DAYS",
    "BloctelGuard",
    "BloctelGuardReport",
    "BloctelMatch",
    "build_bloctel_embed",
    "build_report",
    "find_latest_list",
    "list_age",
    "load_lead_phones",
]
