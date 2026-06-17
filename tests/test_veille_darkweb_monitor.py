"""Tests du script Veille ``DarkWebMonitorScript`` (archi v2).

Hermétique : mémoire de pôle sous ``tmp_path`` (``poles_root=``), domaines
clients et état de dédup injectés (``customers_path=`` / ``seen_path=``). Aucun
appel réseau : :func:`fetch_hibp_breaches` est monkeypatché dans le namespace du
module sous test.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from argos_ops.poles import memory
from argos_ops.poles.base import run_script
from argos_ops.poles.veille.scripts.darkweb_monitor import (
    DarkWebMonitorScript,
    DomainHit,
    cross_domains_with_breaches,
    load_domains,
    load_seen_hits,
    save_seen_hits,
)

_BREACHES: list[dict[str, str | int]] = [
    {
        "Domain": "acme.test",
        "Name": "AcmeBreach",
        "PwnCount": 1234,
        "BreachDate": "2025-01-01",
    },
    {
        "Domain": "other.test",
        "Name": "OtherBreach",
        "PwnCount": 0,
        "BreachDate": "2025-02-01",
    },
]


def _write_customers(path: Path, rows: list[tuple[str, str]]) -> None:
    lines = ["customers:"]
    for name, domain in rows:
        lines.append(f"  - name: {name}")
        lines.append(f"    domain: {domain}")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# =============================================================================
# Pure helpers
# =============================================================================
def test_load_domains_empty_when_missing(tmp_path: Path) -> None:
    assert load_domains(tmp_path / "absent.yaml") == []


def test_load_domains_lowercases(tmp_path: Path) -> None:
    path = tmp_path / "customers.yaml"
    path.write_text("customers:\n  - name: Acme\n    domain: ACME.test\n", encoding="utf-8")
    assert load_domains(path) == [("Acme", "acme.test")]


def test_cross_domains_finds_matches() -> None:
    hits = cross_domains_with_breaches([("Acme", "acme.test")], _BREACHES)
    assert len(hits) == 1
    assert hits[0].breach_name == "AcmeBreach"
    assert hits[0].pwn_count == 1234


def test_cross_domains_returns_empty_when_no_match() -> None:
    breaches: list[dict[str, str | int]] = [
        {"Domain": "other.test", "Name": "X", "PwnCount": 0, "BreachDate": ""}
    ]
    assert cross_domains_with_breaches([("Acme", "acme.test")], breaches) == []


def test_seen_hits_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "seen.json"
    save_seen_hits({"a::b"}, path=path)
    assert load_seen_hits(path=path) == {"a::b"}


# =============================================================================
# run()
# =============================================================================
async def test_run_writes_new_hits_as_facts(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    customers = tmp_path / "customers.yaml"
    _write_customers(customers, [("Acme", "acme.test")])
    seen = tmp_path / "seen.json"

    async def _fake_fetch() -> list[dict[str, str | int]]:
        return _BREACHES

    monkeypatch.setattr(
        "argos_ops.poles.veille.scripts.darkweb_monitor.fetch_hibp_breaches",
        _fake_fetch,
    )

    result = await run_script(
        DarkWebMonitorScript(poles_root=tmp_path, customers_path=customers, seen_path=seen)
    )

    assert result.status == "success"
    assert len(result.written) == 1
    record = result.written[0]
    assert record.kind == "darkweb"
    assert "darkweb" in record.tags
    assert record.important is False
    assert "acme.test" in record.body
    assert "AcmeBreach" in record.body


async def test_run_idempotent_no_duplicate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    customers = tmp_path / "customers.yaml"
    _write_customers(customers, [("Acme", "acme.test")])
    seen = tmp_path / "seen.json"

    async def _fake_fetch() -> list[dict[str, str | int]]:
        return _BREACHES

    monkeypatch.setattr(
        "argos_ops.poles.veille.scripts.darkweb_monitor.fetch_hibp_breaches",
        _fake_fetch,
    )

    # 1er run : 1 nouveau hit écrit + persisté dans seen.json.
    first = await run_script(
        DarkWebMonitorScript(poles_root=tmp_path, customers_path=customers, seen_path=seen)
    )
    assert len(first.written) == 1

    # 2e run : le hit est déjà dans seen.json -> aucun nouveau fait écrit.
    second = await run_script(
        DarkWebMonitorScript(poles_root=tmp_path, customers_path=customers, seen_path=seen)
    )
    assert second.written == []

    records = await memory.read_memory("veille", "darkweb_monitor", poles_root=tmp_path)
    assert len(records) == 1  # pas de doublon en mémoire


async def test_run_empty_domains_writes_nothing(tmp_path: Path) -> None:
    result = await run_script(
        DarkWebMonitorScript(
            poles_root=tmp_path,
            customers_path=tmp_path / "absent.yaml",
            seen_path=tmp_path / "seen.json",
        )
    )
    assert result.status == "success"
    assert result.written == []
    records = await memory.read_memory("veille", "darkweb_monitor", poles_root=tmp_path)
    assert records == []


async def test_run_no_match_writes_nothing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    customers = tmp_path / "customers.yaml"
    _write_customers(customers, [("Nope", "nomatch.test")])
    seen = tmp_path / "seen.json"

    async def _fake_fetch() -> list[dict[str, str | int]]:
        return _BREACHES

    monkeypatch.setattr(
        "argos_ops.poles.veille.scripts.darkweb_monitor.fetch_hibp_breaches",
        _fake_fetch,
    )

    result = await run_script(
        DarkWebMonitorScript(poles_root=tmp_path, customers_path=customers, seen_path=seen)
    )
    assert result.written == []


def _hit() -> DomainHit:
    return DomainHit(
        customer_name="Acme",
        domain="acme.test",
        breach_name="AcmeBreach",
        pwn_count=1234,
        breach_date="2025-01-01",
    )


def test_domain_hit_fields() -> None:
    hit = _hit()
    assert hit.domain == "acme.test"
    assert hit.pwn_count == 1234
