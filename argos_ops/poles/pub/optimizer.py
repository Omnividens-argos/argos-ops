"""Optimiseur de campagnes du pôle Pub (archi v2, S3) — CSV → recos chiffrées.

Brique *pure et déterministe* (l'analogue Pub de
:mod:`argos_ops.poles.marketing.editorial`). Elle lit un export CSV de
campagnes (Google Ads / LinkedIn / Meta), calcule CTR/CPC/CPA/taux de conversion
et produit des **recommandations chiffrées** (impact €/semaine) priorisées.
Portage de la logique du skill ``ads-optimizer`` (mode shadow, P12).

Partagée par :

- :class:`~argos_ops.poles.pub.scripts.ads_optimizer.AdsOptimizerScript` (qui
  écrit la mémoire + arme le breaker depuis ces recos) ;
- l'endpoint cockpit ``GET /api/poles/pub/overview`` (qui recalcule les recos à
  chaud depuis le dernier CSV, comme l'engagement du Marketing).

Convention de fichier : ``data/poles/pub/campaigns/<AAAA-MM-JJ>-<platform>.csv``
(un export par plateforme ; on garde le plus récent par plateforme).
``eur_delta_week`` < 0 = économie, > 0 = dépense additionnelle. Aucune I/O réseau,
aucun LLM ici (D-017).
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from loguru import logger

from argos_ops.poles.config import POLES_DIR
from argos_ops.poles.pub.platforms import PLATFORM_IDS, get_platform

PUB_POLE = "pub"
CAMPAIGNS_DIRNAME = "campaigns"

# Action recommandée. Échelle de sévérité alignée sur le reste de la flotte.
AdAction = Literal["pause", "drop_keyword", "new_creative", "diagnose_lp", "scale"]

Severity = str  # "info" | "warning" | "critical"
_SEVERITY_RANK: dict[str, int] = {"info": 0, "warning": 1, "critical": 2}

_ACTION_SEVERITY: dict[AdAction, Severity] = {
    "pause": "critical",
    "drop_keyword": "warning",
    "new_creative": "warning",
    "diagnose_lp": "warning",
    "scale": "info",
}

# Une action est « augmentatrice de dépense » (donc bridée par le breaker) ssi
# elle accroît la run-rate : scale et new_creative. pause / drop / diagnose la
# réduisent ou la laissent stable → jamais bridées.
SPEND_INCREASING: frozenset[AdAction] = frozenset({"scale", "new_creative"})

# Benchmarks CTR par plateforme (ordre de grandeur marché BtoB). Sous le
# benchmark = créa à retravailler ; au-dessus avec CPA OK = candidat scale.
_CTR_BENCHMARK: dict[str, float] = {
    "google_search": 0.03,
    "linkedin_sponsored": 0.004,
    "meta": 0.009,
}
_DEFAULT_CTR_BENCHMARK = 0.01
_WEAK_CONV_RATE = 0.01  # < 1 % de conv/clic = diagnostic landing page
_PAUSE_CPA_FACTOR = 2.0  # CPA > 2x cible = pause
_DROP_MIN_SPEND_EUR = 100.0  # dépense plancher pour recommander un drop keyword
_SCALE_STEP = 0.30  # +30 % de run-rate sur un scale
_DEFAULT_CPA_TARGET_EUR = 80.0  # cible BtoB SaaS démo (cf. skill)
_MAX_RECOS = 5  # le skill impose de prioriser : 5 actions max par run


# =============================================================================
# Ligne de campagne + métriques
# =============================================================================
@dataclass(frozen=True)
class CampaignRow:
    """Une ligne d'export de campagne et ses métriques dérivées."""

    platform: str
    campaign: str
    impressions: int
    clicks: int
    cost_eur: float
    conversions: int

    @property
    def ctr(self) -> float:
        return self.clicks / self.impressions if self.impressions else 0.0

    @property
    def cpc(self) -> float:
        return self.cost_eur / self.clicks if self.clicks else 0.0

    @property
    def cpa(self) -> float:
        return self.cost_eur / self.conversions if self.conversions else 0.0

    @property
    def conv_rate(self) -> float:
        return self.conversions / self.clicks if self.clicks else 0.0


@dataclass(frozen=True)
class AdRecommendation:
    """Une recommandation chiffrée sur une campagne (impact €/semaine)."""

    platform: str
    campaign: str
    action: AdAction
    severity: Severity
    eur_delta_week: float  # < 0 = économie, > 0 = dépense additionnelle
    rationale: str
    metrics: dict[str, float] = field(default_factory=dict)

    @property
    def id(self) -> str:
        """Identité stable d'une reco (plateforme + campagne + action)."""
        from argos_ops.poles.pub.creatives import slugify

        return f"{self.platform}-{slugify(self.campaign)}-{self.action}"


def severity_rank(severity: str) -> int:
    return _SEVERITY_RANK.get(severity, 0)


# =============================================================================
# Parsing CSV (tolérant aux variantes d'en-têtes des 3 plateformes)
# =============================================================================
_HEADER_ALIASES: dict[str, tuple[str, ...]] = {
    "campaign": ("campaign", "campaign name", "campagne", "ad set name", "ad group"),
    "impressions": ("impressions", "impr.", "impr", "impressions (reach)"),
    "clicks": ("clicks", "clics", "link clicks", "clic"),
    "cost": ("cost", "coût", "cout", "spend", "amount spent", "cost (eur)", "montant dépensé"),
    "conversions": ("conversions", "conv.", "conv", "results", "conversions (1-per-click)"),
}


def _resolve_single_separator(cleaned: str, sep: str) -> str:
    """Désambiguïse un séparateur unique : milliers vs décimal.

    Plusieurs occurrences ⇒ séparateur de milliers (``1.234.567``). Une seule
    occurrence suivie d'exactement 3 chiffres ⇒ milliers (``12,000`` / ``12.000``,
    courant pour impressions/clics) ; sinon décimal (``350.00`` / ``1,5``). Les
    montants à 3 décimales étant quasi inexistants dans les exports Ads, ce
    compromis évite le bug fréquent « 12,000 clics → 12 ».
    """
    parts = cleaned.split(sep)
    if len(parts) > 2:  # ex. "1.234.567" → milliers
        return cleaned.replace(sep, "")
    return cleaned.replace(sep, "") if len(parts[1]) == 3 else cleaned.replace(sep, ".")


def _to_float(value: str) -> float:
    """Parse un nombre tolérant aux locales : « 1 234,56 € », « 1,234.56 », « €80 ».

    Gère indifféremment les conventions FR (``1\xa0234,56``) et US (``1,234.56``) :
    si les deux séparateurs sont présents, le plus à droite est le décimal et
    l'autre les milliers ; sinon on désambiguïse (cf. :func:`_resolve_single_separator`).
    """
    cleaned = value.strip().replace("€", "").replace("\xa0", "").replace(" ", "")
    if not cleaned:
        return 0.0
    has_comma, has_dot = "," in cleaned, "." in cleaned
    if has_comma and has_dot:
        # Le séparateur le plus à droite est le décimal ; l'autre = milliers.
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif has_comma:
        cleaned = _resolve_single_separator(cleaned, ",")
    elif has_dot:
        cleaned = _resolve_single_separator(cleaned, ".")
    try:
        return float(cleaned)
    except ValueError:
        return 0.0


def _resolve_columns(fieldnames: list[str]) -> dict[str, str]:
    """Mappe nos champs canoniques → en-tête réel du CSV (insensible à la casse)."""
    lookup = {name.strip().lower(): name for name in fieldnames}
    resolved: dict[str, str] = {}
    for field_name, aliases in _HEADER_ALIASES.items():
        for alias in aliases:
            if alias in lookup:
                resolved[field_name] = lookup[alias]
                break
    return resolved


def parse_campaign_csv(content: str, *, platform: str) -> list[CampaignRow]:
    """Parse un export CSV en lignes de campagne (best-effort, lignes vides ignorées)."""
    reader = csv.DictReader(io.StringIO(content))
    if reader.fieldnames is None:
        return []
    cols = _resolve_columns(list(reader.fieldnames))
    if "campaign" not in cols:
        logger.warning(f"optimizer — CSV {platform} sans colonne campagne, ignoré")
        return []

    rows: list[CampaignRow] = []
    for raw in reader:
        name = (raw.get(cols["campaign"]) or "").strip()
        if not name:
            continue
        rows.append(
            CampaignRow(
                platform=platform,
                campaign=name,
                impressions=int(_to_float(raw.get(cols.get("impressions", ""), "") or "")),
                clicks=int(_to_float(raw.get(cols.get("clicks", ""), "") or "")),
                cost_eur=_to_float(raw.get(cols.get("cost", ""), "") or ""),
                conversions=int(_to_float(raw.get(cols.get("conversions", ""), "") or "")),
            )
        )
    return rows


# =============================================================================
# Chargement des CSV du pôle (dernier export par plateforme)
# =============================================================================
def campaigns_dir(*, poles_root: Path = POLES_DIR) -> Path:
    return poles_root / PUB_POLE / CAMPAIGNS_DIRNAME


def _platform_of_filename(stem: str) -> str | None:
    """``2026-06-15-google_search`` → ``google_search`` (None si plateforme inconnue)."""
    for pid in PLATFORM_IDS:
        if stem.endswith(f"-{pid}"):
            return pid
    return None


def load_latest_campaigns(*, poles_root: Path = POLES_DIR) -> dict[str, list[CampaignRow]]:
    """Lit le CSV le plus récent **par plateforme** sous ``campaigns/``.

    Les fichiers sont nommés ``<AAAA-MM-JJ>-<platform>.csv`` : on trie par nom
    (le préfixe ISO date garantit l'ordre chronologique) et on garde le dernier
    par plateforme. Best-effort : un fichier illisible est logué et sauté.
    """
    d = campaigns_dir(poles_root=poles_root)
    if not d.exists():
        return {}
    latest_file: dict[str, Path] = {}
    for path in sorted(d.glob("*.csv")):
        platform = _platform_of_filename(path.stem)
        if platform is None:
            logger.debug(f"optimizer — CSV ignoré (plateforme inconnue) : {path.name}")
            continue
        latest_file[platform] = path  # le tri croissant ⇒ le dernier écrase = plus récent

    out: dict[str, list[CampaignRow]] = {}
    for platform, path in latest_file.items():
        try:
            rows = parse_campaign_csv(path.read_text(encoding="utf-8"), platform=platform)
        except Exception as exc:  # best-effort
            logger.warning(f"optimizer — CSV illisible {path} : {type(exc).__name__}: {exc}")
            continue
        if rows:
            out[platform] = rows
    return out


# =============================================================================
# Agrégats
# =============================================================================
def total_spend(rows_by_platform: dict[str, list[CampaignRow]]) -> float:
    return sum(r.cost_eur for rows in rows_by_platform.values() for r in rows)


def spend_by_platform(rows_by_platform: dict[str, list[CampaignRow]]) -> dict[str, float]:
    return {platform: sum(r.cost_eur for r in rows) for platform, rows in rows_by_platform.items()}


def cpa_by_platform(rows_by_platform: dict[str, list[CampaignRow]]) -> dict[str, float]:
    """CPA pondéré par plateforme (coût total / conversions totales)."""
    out: dict[str, float] = {}
    for platform, rows in rows_by_platform.items():
        cost = sum(r.cost_eur for r in rows)
        conv = sum(r.conversions for r in rows)
        out[platform] = cost / conv if conv else 0.0
    return out


# =============================================================================
# Recommandations
# =============================================================================
def _ctr_benchmark(platform: str) -> float:
    return _CTR_BENCHMARK.get(platform, _DEFAULT_CTR_BENCHMARK)


def _recommend_row(
    row: CampaignRow, *, cpa_target_eur: float, week_factor: float
) -> AdRecommendation | None:
    """Une reco (ou ``None``) pour une campagne. Priorité décroissante de gravité."""
    weekly_cost = row.cost_eur * week_factor
    metrics = {
        "ctr": round(row.ctr, 4),
        "cpc": round(row.cpc, 2),
        "cpa": round(row.cpa, 2),
        "conv_rate": round(row.conv_rate, 4),
        "cost_eur": round(row.cost_eur, 2),
    }
    bench = _ctr_benchmark(row.platform)
    plat = get_platform(row.platform)

    # 1. PAUSE (critical) — CPA très au-dessus de la cible (gaspillage avéré).
    if row.conversions > 0 and row.cpa > cpa_target_eur * _PAUSE_CPA_FACTOR:
        return AdRecommendation(
            platform=row.platform,
            campaign=row.campaign,
            action="pause",
            severity=_ACTION_SEVERITY["pause"],
            eur_delta_week=-weekly_cost,
            rationale=(
                f"CPA {row.cpa:.0f} € > 2x cible {cpa_target_eur:.0f} € — mettre en pause "
                f"(économie ~{weekly_cost:.0f} €/sem)."
            ),
            metrics=metrics,
        )

    # 2. DROP keyword (warning, Google uniquement) — dépense sans conversion.
    if (
        plat is not None
        and plat.keyword_targeted
        and row.conversions == 0
        and row.cost_eur >= _DROP_MIN_SPEND_EUR
    ):
        return AdRecommendation(
            platform=row.platform,
            campaign=row.campaign,
            action="drop_keyword",
            severity=_ACTION_SEVERITY["drop_keyword"],
            eur_delta_week=-weekly_cost,
            rationale=(
                f"{row.cost_eur:.0f} € dépensés, 0 conversion — couper le(s) mot(s)-clé(s) "
                f"non convertisseur(s) (économie ~{weekly_cost:.0f} €/sem)."
            ),
            metrics=metrics,
        )

    # 3. DIAGNOSE LP (warning) — trafic OK mais conversion en berne.
    if row.ctr >= bench and row.clicks > 0 and row.conv_rate < _WEAK_CONV_RATE:
        return AdRecommendation(
            platform=row.platform,
            campaign=row.campaign,
            action="diagnose_lp",
            severity=_ACTION_SEVERITY["diagnose_lp"],
            eur_delta_week=0.0,
            rationale=(
                f"CTR {row.ctr * 100:.1f}% sain mais conv {row.conv_rate * 100:.1f}% < 1% — "
                "auditer la landing page (pas la créa)."
            ),
            metrics=metrics,
        )

    # 4. NEW creative (warning) — créa peu cliquée alors que la conv tient.
    if row.ctr < bench and row.conversions > 0:
        return AdRecommendation(
            platform=row.platform,
            campaign=row.campaign,
            action="new_creative",
            severity=_ACTION_SEVERITY["new_creative"],
            eur_delta_week=0.0,
            rationale=(
                f"CTR {row.ctr * 100:.1f}% < benchmark {bench * 100:.1f}% mais conv saine — "
                "tester de nouvelles créas (A/B)."
            ),
            metrics=metrics,
        )

    # 5. SCALE (info) — campagne saine : CPA sous la cible et CTR au benchmark.
    if row.conversions > 0 and row.cpa <= cpa_target_eur and row.ctr >= bench:
        return AdRecommendation(
            platform=row.platform,
            campaign=row.campaign,
            action="scale",
            severity=_ACTION_SEVERITY["scale"],
            eur_delta_week=weekly_cost * _SCALE_STEP,
            rationale=(
                f"CPA {row.cpa:.0f} € < cible et CTR {row.ctr * 100:.1f}% sain — "
                f"scaler +{int(_SCALE_STEP * 100)}% (~+{weekly_cost * _SCALE_STEP:.0f} €/sem)."
            ),
            metrics=metrics,
        )

    return None


def recommend(
    rows_by_platform: dict[str, list[CampaignRow]],
    *,
    cpa_target_eur: float = _DEFAULT_CPA_TARGET_EUR,
    window_days: int = 7,
) -> list[AdRecommendation]:
    """Produit jusqu'à 5 recommandations chiffrées, des plus graves aux moins.

    ``window_days`` normalise la dépense de la fenêtre du CSV en run-rate
    hebdomadaire (``eur_delta_week``). Tri stable : sévérité décroissante, puis
    impact absolu €/semaine décroissant (les économies/scales les plus lourds en
    tête à sévérité égale).
    """
    week_factor = 7.0 / max(1, window_days)
    recos: list[AdRecommendation] = []
    for platform in sorted(rows_by_platform):
        for row in rows_by_platform[platform]:
            reco = _recommend_row(row, cpa_target_eur=cpa_target_eur, week_factor=week_factor)
            if reco is not None:
                recos.append(reco)

    recos.sort(key=lambda r: (severity_rank(r.severity), abs(r.eur_delta_week)), reverse=True)
    return recos[:_MAX_RECOS]


__all__ = [
    "SPEND_INCREASING",
    "AdAction",
    "AdRecommendation",
    "CampaignRow",
    "Severity",
    "campaigns_dir",
    "cpa_by_platform",
    "load_latest_campaigns",
    "parse_campaign_csv",
    "recommend",
    "severity_rank",
    "spend_by_platform",
    "total_spend",
]
