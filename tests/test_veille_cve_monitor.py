"""Tests du script Veille ``CVEMonitorScript`` (archi v2).

Hermétique : mémoire de pôle sous ``tmp_path`` (``poles_root=``), stacks clients
et état "déjà vu" injectés (``customers_path=`` / ``seen_path=``). Jamais de
réseau : ``query_osv`` est monkeypatché dans le namespace du module sous test.
Gabarit calqué sur ``tests/test_veille_trend_spotter.py``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from argos_ops.poles import memory
from argos_ops.poles.base import run_script
from argos_ops.poles.veille.scripts import cve_monitor as cm
from argos_ops.poles.veille.scripts.cve_monitor import (
    CVEAlert,
    CVEMonitorScript,
    StackPackage,
    load_seen_vulns,
    load_stack_packages,
    save_seen_vulns,
)


def _pkg(name: str = "django", version: str | None = "4.0.0") -> StackPackage:
    return StackPackage(customer_name="Acme", ecosystem="PyPI", name=name, version=version)


def _alert(severity: str, *, vuln_id: str | None = None) -> CVEAlert:
    return CVEAlert(
        package=_pkg(),
        vuln_id=vuln_id or f"GHSA-{severity}",
        severity=severity,  # type: ignore[arg-type]
        summary=f"test {severity}",
    )


def _write_customers(path: Path) -> None:
    path.write_text(
        "customers:\n"
        "  - name: Acme\n"
        "    domain: acme.test\n"
        "    stack:\n"
        "      - ecosystem: PyPI\n"
        "        name: django\n"
        "        version: '4.0.0'\n",
        encoding="utf-8",
    )


# =============================================================================
# Helpers purs portés
# =============================================================================
def test_map_severity_buckets() -> None:
    assert cm._map_severity([{"score": 9.8}]) == "CRITICAL"
    assert cm._map_severity([{"score": 7.5}]) == "HIGH"
    assert cm._map_severity([{"score": 5.0}]) == "MEDIUM"
    assert cm._map_severity([{"score": 2.0}]) == "LOW"
    assert cm._map_severity(None) == "UNKNOWN"
    assert cm._map_severity([]) == "UNKNOWN"


def test_map_severity_takes_last_number_of_cvss_vector() -> None:
    # Le score réel est le dernier nombre du vector CVSS, pas le "3.1" de version.
    vector = [{"score": "CVSS:3.1/AV:N/AC:L/PR:N/UI:N/S:U/C:H/I:H/A:H/9.8"}]
    assert cm._map_severity(vector) == "CRITICAL"


def test_load_stack_packages_empty_when_missing(tmp_path: Path) -> None:
    assert load_stack_packages(tmp_path / "absent.yaml") == []


def test_load_stack_packages_parses_entries(tmp_path: Path) -> None:
    path = tmp_path / "customers.yaml"
    path.write_text(
        "customers:\n"
        "  - name: Acme\n"
        "    domain: acme.test\n"
        "    stack:\n"
        "      - ecosystem: PyPI\n"
        "        name: django\n"
        "        version: '4.2.1'\n"
        "      - ecosystem: npm\n"
        "        name: lodash\n",
        encoding="utf-8",
    )
    packages = load_stack_packages(path)
    assert len(packages) == 2
    assert packages[0].name == "django"
    assert packages[1].version is None


def test_save_and_load_seen_vulns_round_trip(tmp_path: Path) -> None:
    path = tmp_path / "seen.json"
    save_seen_vulns({"CVE-1", "CVE-2"}, path=path)
    assert load_seen_vulns(path=path) == {"CVE-1", "CVE-2"}


# =============================================================================
# run() — comportement bras déterministe
# =============================================================================
async def test_empty_stack_writes_nothing(tmp_path: Path) -> None:
    result = await run_script(
        CVEMonitorScript(
            poles_root=tmp_path,
            customers_path=tmp_path / "absent.yaml",
            seen_path=tmp_path / "seen.json",
        )
    )
    assert result.status == "success"
    assert result.written == []


async def test_run_marks_important_on_high_and_critical(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    customers = tmp_path / "customers.yaml"
    _write_customers(customers)
    alerts = [
        _alert("CRITICAL", vuln_id="CVE-CRIT"),
        _alert("HIGH", vuln_id="CVE-HIGH"),
        _alert("MEDIUM", vuln_id="CVE-MED"),
    ]

    async def fake_query(packages: list[StackPackage]) -> list[CVEAlert]:
        return alerts

    monkeypatch.setattr(cm, "query_osv", fake_query)

    result = await run_script(
        CVEMonitorScript(
            poles_root=tmp_path,
            customers_path=customers,
            seen_path=tmp_path / "seen.json",
        )
    )

    assert result.status == "success"
    assert len(result.written) == 3
    assert all(r.kind == "cve" for r in result.written)
    by_id = {r.body.split()[1]: r for r in result.written}
    assert by_id["CVE-CRIT"].important is True
    assert by_id["CVE-HIGH"].important is True
    assert by_id["CVE-MED"].important is False
    assert "critical" in by_id["CVE-CRIT"].tags
    assert "cve" in by_id["CVE-MED"].tags


async def test_run_skips_low_and_unknown(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    customers = tmp_path / "customers.yaml"
    _write_customers(customers)
    alerts = [_alert("LOW", vuln_id="CVE-LOW"), _alert("UNKNOWN", vuln_id="CVE-UNK")]

    async def fake_query(packages: list[StackPackage]) -> list[CVEAlert]:
        return alerts

    monkeypatch.setattr(cm, "query_osv", fake_query)

    result = await run_script(
        CVEMonitorScript(
            poles_root=tmp_path,
            customers_path=customers,
            seen_path=tmp_path / "seen.json",
        )
    )
    # LOW/UNKNOWN ne sont jamais mémorisées (anti-bruit), mais sont "vues".
    assert result.written == []
    assert load_seen_vulns(path=tmp_path / "seen.json") == {"CVE-LOW", "CVE-UNK"}


async def test_run_idempotent_no_duplicate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    customers = tmp_path / "customers.yaml"
    _write_customers(customers)
    seen_path = tmp_path / "seen.json"
    alerts = [_alert("HIGH", vuln_id="CVE-HIGH")]

    async def fake_query(packages: list[StackPackage]) -> list[CVEAlert]:
        return alerts

    monkeypatch.setattr(cm, "query_osv", fake_query)

    first = await run_script(
        CVEMonitorScript(poles_root=tmp_path, customers_path=customers, seen_path=seen_path)
    )
    # 2e run : la CVE est dans seen -> filtrée -> aucun nouveau fait écrit.
    second = await run_script(
        CVEMonitorScript(poles_root=tmp_path, customers_path=customers, seen_path=seen_path)
    )

    assert len(first.written) == 1
    assert second.written == []
    records = await memory.read_memory("veille", "cve_monitor", poles_root=tmp_path)
    assert len(records) == 1  # pas de doublon en mémoire


async def test_run_dedups_via_seen_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    customers = tmp_path / "customers.yaml"
    _write_customers(customers)
    seen_path = tmp_path / "seen.json"
    save_seen_vulns({"CVE-OLD"}, path=seen_path)
    alerts = [_alert("HIGH", vuln_id="CVE-OLD"), _alert("HIGH", vuln_id="CVE-NEW")]

    async def fake_query(packages: list[StackPackage]) -> list[CVEAlert]:
        return alerts

    monkeypatch.setattr(cm, "query_osv", fake_query)

    result = await run_script(
        CVEMonitorScript(poles_root=tmp_path, customers_path=customers, seen_path=seen_path)
    )
    # Seule CVE-NEW est nouvelle ; CVE-OLD était déjà vue.
    assert len(result.written) == 1
    assert "CVE-NEW" in result.written[0].body
    assert load_seen_vulns(path=seen_path) == {"CVE-OLD", "CVE-NEW"}
