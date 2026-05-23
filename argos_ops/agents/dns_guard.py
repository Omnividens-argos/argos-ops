"""DNSGuard — IT Network (P22.D Tech/SRE Sprint 4).

Surveille les enregistrements DNS critiques de ``omnividens.fr`` :

- ``A`` (root) : IP du serveur web public
- ``A`` (``ops.omnividens.fr``) : IP de l'Admin Panel
- ``MX`` : mail OVH (jamais censé changer)
- ``TXT`` (root) : SPF, DKIM identity, autres assertions auth

Politique anti-spam :
- **Silence** Discord si l'empreinte (hash trié des records) est
  identique au snapshot précédent
- **Embed jaune** si un nouvel enregistrement apparaît ou si un
  enregistrement disparaît (changement neutre par défaut — peut être
  intentionnel : nouveau sous-domaine, rotation DKIM)
- **Embed rouge** si l'IP du root ``A`` ou les ``MX`` changent (le
  signal classique d'un takeover DNS / hijack)

Le snapshot est rangé dans
``data/dns_snapshots/<domain>.json`` (gitignored sauf catalogue). On
résout les records via ``dnspython`` (déjà tiré par ``argos-ops``
indirectement via ``aiosmtplib``) ou — fallback — via le système
résolveur local. Pas d'API externe, pas de scraping web.

Cf. plan ``docs/ARGOS_OPS_PLAN.md`` Annexe D § 7 Tech/SRE, Sprint 4.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from loguru import logger

from argos_ops.agents._watcher_base import color_title, emit_alert_or_silence
from argos_ops.agents.base import BaseAgent, RunResult
from argos_ops.config import REPO_ROOT
from argos_ops.notifications.discord import GREEN, RED, YELLOW, Embed, EmbedField

DnsChangeKind = Literal["none", "neutral", "critical"]

DEFAULT_DOMAIN = "omnividens.fr"
DEFAULT_SUBDOMAINS: tuple[str, ...] = ("ops.omnividens.fr",)
DEFAULT_RECORD_TYPES: tuple[str, ...] = ("A", "MX", "TXT")
CRITICAL_RECORD_KEYS: frozenset[str] = frozenset(
    {f"{DEFAULT_DOMAIN}:A", f"{DEFAULT_DOMAIN}:MX"}
)
SNAPSHOT_DIR: Path = REPO_ROOT / "data" / "dns_snapshots"


@dataclass(frozen=True)
class DnsSnapshot:
    """Snapshot d'une zone DNS — clé = ``"<name>:<type>"``, valeur = set trié."""

    fetched_at: datetime
    records: dict[str, list[str]]

    def to_payload(self) -> dict[str, object]:
        return {
            "fetched_at": self.fetched_at.isoformat(),
            "records": {k: sorted(v) for k, v in self.records.items()},
        }

    @classmethod
    def from_payload(cls, payload: dict[str, object]) -> DnsSnapshot:
        raw_records = payload.get("records") or {}
        records: dict[str, list[str]] = {}
        if isinstance(raw_records, dict):
            for k, v in raw_records.items():
                if isinstance(v, list):
                    records[str(k)] = sorted(str(x) for x in v)
        return cls(
            fetched_at=datetime.fromisoformat(str(payload.get("fetched_at"))),
            records=records,
        )


@dataclass(frozen=True)
class DnsChange:
    """Une diff par clé ``"<name>:<type>"``."""

    key: str
    added: list[str]
    removed: list[str]
    is_critical: bool


@dataclass(frozen=True)
class DnsReport:
    """Résultat agrégé du run DNSGuard."""

    snapshot: DnsSnapshot
    changes: list[DnsChange]
    kind: DnsChangeKind
    should_alert: bool
    alert_color: int
    summary: str


# =============================================================================
# Résolution DNS
# =============================================================================
async def resolve_records(
    name: str, record_type: str, *, timeout: float = 5.0
) -> list[str]:
    """Résout ``name``/``record_type`` via dnspython, retourne strings triés.

    Toute erreur (timeout, NXDOMAIN, no-answer) → liste vide silencieuse.
    On préfère un faux négatif (record absent → diff détectée comme
    suppression) à un crash qui priverait le watcher d'alerte sur les
    autres records.
    """
    try:
        import dns.asyncresolver
        import dns.exception
    except ImportError:
        logger.warning("DNSGuard — dnspython non installé, fallback impossible")
        return []

    resolver = dns.asyncresolver.Resolver()
    resolver.lifetime = timeout
    try:
        answer = await resolver.resolve(name, record_type)
    except (dns.exception.DNSException, TimeoutError) as exc:
        logger.debug(f"DNSGuard {name}/{record_type} → {type(exc).__name__}: {exc}")
        return []

    out: list[str] = []
    for record in answer:
        out.append(str(record).strip().strip('"'))
    return sorted(out)


async def fetch_snapshot(
    *,
    domain: str = DEFAULT_DOMAIN,
    subdomains: tuple[str, ...] = DEFAULT_SUBDOMAINS,
    record_types: tuple[str, ...] = DEFAULT_RECORD_TYPES,
    now: datetime | None = None,
) -> DnsSnapshot:
    """Construit un snapshot complet en parallélisant les lookups."""
    names = (domain, *subdomains)
    jobs: list[tuple[str, str]] = []
    for name in names:
        for rtype in record_types:
            # TXT n'a de sens que sur le root + les sous-domaines mail.
            if rtype == "MX" and name != domain:
                continue
            jobs.append((name, rtype))

    results = await asyncio.gather(*(resolve_records(n, t) for n, t in jobs))
    records: dict[str, list[str]] = {}
    for (name, rtype), values in zip(jobs, results, strict=True):
        records[f"{name}:{rtype}"] = values

    return DnsSnapshot(fetched_at=now or datetime.now(UTC), records=records)


# =============================================================================
# Diff
# =============================================================================
def diff_snapshots(
    previous: DnsSnapshot | None, current: DnsSnapshot
) -> list[DnsChange]:
    """Compare 2 snapshots. ``None`` (premier run) → aucune diff (baseline)."""
    if previous is None:
        return []

    keys = set(previous.records) | set(current.records)
    out: list[DnsChange] = []
    for key in sorted(keys):
        old = set(previous.records.get(key, []))
        new = set(current.records.get(key, []))
        if old == new:
            continue
        out.append(
            DnsChange(
                key=key,
                added=sorted(new - old),
                removed=sorted(old - new),
                is_critical=key in CRITICAL_RECORD_KEYS,
            )
        )
    return out


def classify_changes(changes: list[DnsChange]) -> DnsChangeKind:
    """``critical`` si A root ou MX touchés, ``neutral`` si autre, ``none``."""
    if not changes:
        return "none"
    if any(c.is_critical for c in changes):
        return "critical"
    return "neutral"


# =============================================================================
# Snapshot I/O
# =============================================================================
def _snapshot_path(domain: str, base_dir: Path = SNAPSHOT_DIR) -> Path:
    return base_dir / f"{domain}.json"


def load_previous(domain: str, base_dir: Path = SNAPSHOT_DIR) -> DnsSnapshot | None:
    path = _snapshot_path(domain, base_dir)
    if not path.exists():
        return None
    try:
        return DnsSnapshot.from_payload(json.loads(path.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, ValueError, KeyError) as exc:
        logger.warning(f"DNSGuard — snapshot {path.name} corrompu: {exc}")
        return None


def save_snapshot(
    snapshot: DnsSnapshot, domain: str, base_dir: Path = SNAPSHOT_DIR
) -> None:
    base_dir.mkdir(parents=True, exist_ok=True)
    path = _snapshot_path(domain, base_dir)
    path.write_text(
        json.dumps(snapshot.to_payload(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# =============================================================================
# Report
# =============================================================================
def build_report(snapshot: DnsSnapshot, changes: list[DnsChange]) -> DnsReport:
    kind = classify_changes(changes)
    if kind == "critical":
        alert_color = RED
    elif kind == "neutral":
        alert_color = YELLOW
    else:
        alert_color = GREEN

    summary = (
        f"{len(changes)} change(s) DNS"
        if changes
        else f"{len(snapshot.records)} record sets — stable"
    )
    return DnsReport(
        snapshot=snapshot,
        changes=changes,
        kind=kind,
        should_alert=kind != "none",
        alert_color=alert_color,
        summary=summary,
    )


def build_dns_embed(report: DnsReport, *, now: datetime | None = None) -> Embed:
    """Embed Discord — un field par change avec added/removed."""
    now = now or datetime.now(UTC)
    fields = [
        EmbedField(
            name=f"{'[CRIT]' if change.is_critical else '[NEUT]'} {change.key}",
            value=(
                (f"+ {', '.join(change.added)}\n" if change.added else "")
                + (f"- {', '.join(change.removed)}" if change.removed else "")
            )[:1020]
            or "(modification non explicite)",
            inline=False,
        )
        for change in report.changes
    ]
    title_status = color_title(report.alert_color, green=GREEN, yellow=YELLOW, red=RED)
    return Embed(
        title=f"DNSGuard — {title_status}",
        description=report.summary,
        color=report.alert_color,
        fields=fields,
        footer="Argos Ops • DNSGuard",
        timestamp=now.isoformat(),
    )


class DNSGuard(BaseAgent):
    """IT Network — surveille les enregistrements DNS critiques."""

    name = "DNSGuard"
    command = None  # cron pur (pas de slash dédié, alerte rare)
    breaker_name = None

    def __init__(
        self,
        *,
        domain: str = DEFAULT_DOMAIN,
        subdomains: tuple[str, ...] = DEFAULT_SUBDOMAINS,
        snapshot_dir: Path = SNAPSHOT_DIR,
    ) -> None:
        self._domain = domain
        self._subdomains = subdomains
        self._snapshot_dir = snapshot_dir

    async def run(self) -> RunResult:
        previous = load_previous(self._domain, self._snapshot_dir)
        snapshot = await fetch_snapshot(
            domain=self._domain, subdomains=self._subdomains
        )
        changes = diff_snapshots(previous, snapshot)
        report = build_report(snapshot, changes)
        save_snapshot(snapshot, self._domain, self._snapshot_dir)
        return await emit_alert_or_silence(
            report, embed_builder=build_dns_embed, agent_name=self.name
        )


__all__ = [
    "CRITICAL_RECORD_KEYS",
    "DEFAULT_DOMAIN",
    "DEFAULT_RECORD_TYPES",
    "DEFAULT_SUBDOMAINS",
    "SNAPSHOT_DIR",
    "DNSGuard",
    "DnsChange",
    "DnsChangeKind",
    "DnsReport",
    "DnsSnapshot",
    "build_dns_embed",
    "build_report",
    "classify_changes",
    "diff_snapshots",
    "fetch_snapshot",
    "load_previous",
    "resolve_records",
    "save_snapshot",
]
