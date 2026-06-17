"""Tests du script Veille ``BreachWatcherScript`` (archi v2, S1).

Hermétique : mémoire de pôle sous ``tmp_path`` (``poles_root=``) et carnet client
injecté (``customers_path=``). Réseau toujours mocké : on monkeypatch
``fetch_cert_fr`` / ``fetch_hibp`` dans le namespace du module sous test pour
renvoyer des :class:`BreachEvent` construits directement (jamais de HTTP réel).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from argos_ops.poles import memory
from argos_ops.poles.base import run_script
from argos_ops.poles.veille.scripts.breach_watcher import (
    BreachEvent,
    BreachWatcherScript,
    Customer,
    _extract_domain,
    _is_critical,
    cross_with_customers,
    load_customers,
)

MODULE = "argos_ops.poles.veille.scripts.breach_watcher"


def _event(
    *,
    domain: str | None,
    title: str = "Test breach",
    summary: str = "",
    published_at: datetime | None = None,
) -> BreachEvent:
    return BreachEvent(
        source="HIBP",
        title=title,
        published_at=published_at,
        summary=summary,
        affected_domain=domain,
    )


def _write_customers(path: Path, customers: list[tuple[str, str]]) -> None:
    """Écrit un customers.yaml (name, domain)."""
    lines = ["customers:"]
    for name, domain in customers:
        lines.append(f"  - name: {name}")
        lines.append(f"    domain: {domain}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# =============================================================================
# Helpers purs portés
# =============================================================================
def test_extract_domain_finds_first_match() -> None:
    assert _extract_domain("breach at example.com today") == "example.com"
    assert _extract_domain("no domain here") is None


def test_is_critical_flags_keyword_passwords() -> None:
    assert _is_critical(_event(domain="x.test", summary="passwords leaked")) is True
    assert _is_critical(_event(domain="x.test", summary="emails leaked")) is False


def test_load_customers_empty_when_missing(tmp_path: Path) -> None:
    assert load_customers(tmp_path / "absent.yaml") == []


def test_load_customers_parses_entries(tmp_path: Path) -> None:
    path = tmp_path / "customers.yaml"
    _write_customers(path, [("Acme", "acme.test")])
    customers = load_customers(path)
    assert len(customers) == 1
    assert customers[0].domain == "acme.test"


def test_cross_with_customers_returns_empty_when_no_match() -> None:
    events = [_event(domain="other.test")]
    customers = [Customer(name="Acme", domain="acme.test")]
    assert cross_with_customers(events, customers) == []


def test_cross_with_customers_matches_domain() -> None:
    events = [_event(domain="acme.test", summary="passwords leaked")]
    customers = [Customer(name="Acme", domain="acme.test")]
    matches = cross_with_customers(events, customers)
    assert len(matches) == 1
    assert matches[0].is_critical is True


def test_cross_with_customers_skips_events_outside_window() -> None:
    now = datetime(2026, 5, 23, tzinfo=UTC)
    old_event = _event(domain="acme.test", published_at=now - timedelta(days=60))
    customers = [Customer(name="Acme", domain="acme.test")]
    assert cross_with_customers([old_event], customers, now=now) == []


# =============================================================================
# run() — mémoire de pôle
# =============================================================================
async def test_run_writes_match_to_memory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    customers = tmp_path / "customers.yaml"
    _write_customers(customers, [("Acme", "acme.test")])

    async def fake_cert() -> list[BreachEvent]:
        return []

    async def fake_hibp() -> list[BreachEvent]:
        return [_event(domain="acme.test", title="AcmeLeak", summary="emails leaked")]

    monkeypatch.setattr(f"{MODULE}.fetch_cert_fr", fake_cert)
    monkeypatch.setattr(f"{MODULE}.fetch_hibp", fake_hibp)

    result = await run_script(BreachWatcherScript(poles_root=tmp_path, customers_path=customers))

    assert result.status == "success"
    assert len(result.written) == 1
    rec = result.written[0]
    assert rec.kind == "breach"
    assert "breach" in rec.tags
    assert "warning" in rec.tags
    assert rec.important is False
    assert "Acme" in rec.body and "acme.test" in rec.body


async def test_run_marks_important_on_critical(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    customers = tmp_path / "customers.yaml"
    _write_customers(customers, [("Acme", "acme.test")])

    async def fake_cert() -> list[BreachEvent]:
        return [_event(domain="acme.test", title="AcmeLeak", summary="passwords leaked")]

    async def fake_hibp() -> list[BreachEvent]:
        return []

    monkeypatch.setattr(f"{MODULE}.fetch_cert_fr", fake_cert)
    monkeypatch.setattr(f"{MODULE}.fetch_hibp", fake_hibp)

    result = await run_script(BreachWatcherScript(poles_root=tmp_path, customers_path=customers))

    assert len(result.written) == 1
    rec = result.written[0]
    assert rec.important is True
    assert "critical" in rec.tags


async def test_run_idempotent_no_duplicate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    customers = tmp_path / "customers.yaml"
    _write_customers(customers, [("Acme", "acme.test")])

    async def fake_cert() -> list[BreachEvent]:
        return []

    async def fake_hibp() -> list[BreachEvent]:
        return [_event(domain="acme.test", title="AcmeLeak", summary="emails leaked")]

    monkeypatch.setattr(f"{MODULE}.fetch_cert_fr", fake_cert)
    monkeypatch.setattr(f"{MODULE}.fetch_hibp", fake_hibp)

    await run_script(BreachWatcherScript(poles_root=tmp_path, customers_path=customers))
    await run_script(BreachWatcherScript(poles_root=tmp_path, customers_path=customers))

    records = await memory.read_memory("veille", "breach_watcher", poles_root=tmp_path)
    assert len(records) == 1  # deux runs, pas de doublon (hash de corps stable)


async def test_run_empty_customers_writes_nothing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def fake_cert() -> list[BreachEvent]:
        raise AssertionError("ne doit pas fetcher sans client")

    async def fake_hibp() -> list[BreachEvent]:
        raise AssertionError("ne doit pas fetcher sans client")

    monkeypatch.setattr(f"{MODULE}.fetch_cert_fr", fake_cert)
    monkeypatch.setattr(f"{MODULE}.fetch_hibp", fake_hibp)

    result = await run_script(
        BreachWatcherScript(poles_root=tmp_path, customers_path=tmp_path / "absent.yaml")
    )

    assert result.status == "success"
    assert result.written == []
    records = await memory.read_memory("veille", "breach_watcher", poles_root=tmp_path)
    assert records == []
