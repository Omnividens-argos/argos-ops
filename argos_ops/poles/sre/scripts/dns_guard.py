"""``DnsGuardScript`` — surveillance des enregistrements DNS (archi v2, S8).

Résout les enregistrements (A/MX/TXT par défaut) des domaines déclarés dans
``data/poles/sre/dns/config.yaml`` et diffe vs le dernier snapshot
(``data/poles/sre/dns/snapshots/<domain>.json``). Un changement sur une clé
**critique** (A racine / MX) est rouge ; un autre changement est jaune ; aucun
changement est vert. Le resolver est injectable (tests hermétiques, aucun réseau).

Garde-fou : si une clé échoue à se résoudre, elle est **exclue** du diff et du
snapshot (on conserve la valeur précédente) pour ne jamais signaler une fausse
disparition critique — la sévérité passe au minimum à jaune (résolution partielle).
"""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import yaml
from loguru import logger

from argos_ops.poles.config import POLES_DIR
from argos_ops.poles.sre.base import BaseSreScript
from argos_ops.poles.sre.report import Severity, SreReport, worst

DNS_CONFIG_FILE = ("dns", "config.yaml")
DNS_SNAPSHOT_SUBDIR = ("dns", "snapshots")
DEFAULT_RECORD_TYPES = ("A", "MX", "TXT")
DEFAULT_DOMAINS = ("omnividens.fr",)
DEFAULT_CRITICAL_KEYS = ("omnividens.fr:A", "omnividens.fr:MX")

# resolver : (name, record_type) → liste d'enregistrements. Lève en cas d'échec.
Resolver = Callable[[str, str], Awaitable[list[str]]]


def dns_config_path(*, poles_root: Path = POLES_DIR) -> Path:
    return poles_root / "sre" / DNS_CONFIG_FILE[0] / DNS_CONFIG_FILE[1]


def snapshot_path(domain: str, *, poles_root: Path = POLES_DIR) -> Path:
    return poles_root / "sre" / DNS_SNAPSHOT_SUBDIR[0] / DNS_SNAPSHOT_SUBDIR[1] / f"{domain}.json"


@dataclass(frozen=True)
class DnsConfig:
    """Config de surveillance DNS."""

    domains: tuple[str, ...]
    record_types: tuple[str, ...]
    critical_keys: frozenset[str]


@dataclass(frozen=True)
class DnsChange:
    """Diff d'un jeu d'enregistrements pour une clé ``<name>:<type>``."""

    key: str
    added: tuple[str, ...]
    removed: tuple[str, ...]
    critical: bool


def load_config(*, poles_root: Path = POLES_DIR) -> DnsConfig:
    """Charge la config (valeurs par défaut si fichier absent / malformé)."""
    path = dns_config_path(poles_root=poles_root)
    raw: dict[str, object] = {}
    if path.exists():
        try:
            loaded = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if isinstance(loaded, dict):
                raw = loaded
        except yaml.YAMLError as exc:
            logger.warning(f"dns_guard — config invalide, défauts : {exc}")

    def _tuple(key: str, default: tuple[str, ...]) -> tuple[str, ...]:
        val = raw.get(key)
        return tuple(str(v) for v in val) if isinstance(val, list) and val else default

    return DnsConfig(
        domains=_tuple("domains", DEFAULT_DOMAINS),
        record_types=_tuple("record_types", DEFAULT_RECORD_TYPES),
        critical_keys=frozenset(_tuple("critical_keys", DEFAULT_CRITICAL_KEYS)),
    )


def load_snapshot(domain: str, *, poles_root: Path = POLES_DIR) -> dict[str, list[str]]:
    """Lit le dernier snapshot d'un domaine (``{}`` si absent / illisible)."""
    path = snapshot_path(domain, poles_root=poles_root)
    if not path.exists():
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        logger.warning(f"dns_guard — snapshot {domain} illisible : {exc}")
        return {}
    records = raw.get("records") if isinstance(raw, dict) else None
    if not isinstance(records, dict):
        return {}
    return {str(k): [str(x) for x in v] for k, v in records.items() if isinstance(v, list)}


def save_snapshot(
    domain: str, records: dict[str, list[str]], *, poles_root: Path = POLES_DIR
) -> None:
    path = snapshot_path(domain, poles_root=poles_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "domain": domain,
        "fetched_at": datetime.now(UTC).isoformat(),
        "records": {k: sorted(v) for k, v in sorted(records.items())},
    }
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def diff_records(
    previous: dict[str, list[str]], current: dict[str, list[str]], critical_keys: frozenset[str]
) -> list[DnsChange]:
    """Diffe deux jeux d'enregistrements (pur). Ne compare que les clés présentes
    dans ``current`` (les clés non résolues sont volontairement absentes)."""
    changes: list[DnsChange] = []
    for key in sorted(current):
        old = set(previous.get(key, []))
        new = set(current[key])
        if old == new:
            continue
        changes.append(
            DnsChange(
                key=key,
                added=tuple(sorted(new - old)),
                removed=tuple(sorted(old - new)),
                critical=key in critical_keys,
            )
        )
    return changes


def build_report(changes: list[DnsChange], *, n_keys: int, partial: bool) -> SreReport:
    has_critical = any(c.critical for c in changes)
    severity: Severity = worst(
        "red" if has_critical else "green",
        "yellow" if (changes or partial) else "green",
    )
    if not changes and not partial:
        return SreReport("green", f"{n_keys} jeu(x) d'enregistrements — DNS stable.")
    summary = f"{len(changes)} changement(s) DNS" + (" · résolution partielle" if partial else "")
    detail = "\n".join(
        f"- {c.key}{' (CRITIQUE)' if c.critical else ''} : +{list(c.added)} / -{list(c.removed)}"
        for c in changes
    )
    return SreReport(severity, summary, detail)


class DnsGuardScript(BaseSreScript):
    """Diffe les enregistrements DNS vs snapshot et alerte sur les changements critiques."""

    name = "dns_guard"

    def __init__(self, *, poles_root: Path = POLES_DIR, resolver: Resolver | None = None) -> None:
        super().__init__(poles_root=poles_root)
        self._resolver = resolver or real_resolver

    async def check(self) -> SreReport:
        config = load_config(poles_root=self.poles_root)
        all_changes: list[DnsChange] = []
        n_keys = 0
        partial = False
        for domain in config.domains:
            previous = load_snapshot(domain, poles_root=self.poles_root)
            current = dict(previous)  # repart du précédent, écrase les clés résolues
            resolved: dict[str, list[str]] = {}
            for rtype in config.record_types:
                key = f"{domain}:{rtype}"
                try:
                    resolved[key] = sorted(await self._resolver(domain, rtype))
                except Exception as exc:  # résolution échouée → clé exclue du diff
                    partial = True
                    logger.warning(f"dns_guard — échec résolution {key} : {exc}")
            n_keys += len(resolved)
            # Premier run (aucun snapshot) ⇒ on établit la baseline sans alerter ;
            # sinon on diffe les clés résolues vs le snapshot précédent.
            if previous:
                all_changes.extend(diff_records(previous, resolved, config.critical_keys))
            current.update(resolved)
            save_snapshot(domain, current, poles_root=self.poles_root)
        return build_report(all_changes, n_keys=n_keys, partial=partial)


async def real_resolver(name: str, record_type: str) -> list[str]:
    """Résolution réelle via dnspython, déportée dans un thread."""
    import asyncio

    import dns.resolver

    def _resolve() -> list[str]:
        answers = dns.resolver.resolve(name, record_type)
        return [r.to_text() for r in answers]

    return await asyncio.to_thread(_resolve)


__all__ = [
    "DEFAULT_CRITICAL_KEYS",
    "DEFAULT_RECORD_TYPES",
    "DnsChange",
    "DnsConfig",
    "DnsGuardScript",
    "Resolver",
    "build_report",
    "diff_records",
    "load_config",
    "load_snapshot",
    "real_resolver",
    "save_snapshot",
    "snapshot_path",
]
