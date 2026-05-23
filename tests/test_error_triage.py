"""Tests unitaires de :mod:`argos_ops.agents.error_triage` (P22.C).

Couvre :
- ``extract_signature`` : parsing du préfixe d'erreur
- ``collect_clusters`` : groupement cross-agents (mock ``_fetch_errors``)
- ``build_report`` : couleur RED quand critique, YELLOW sinon
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from argos_ops.agents import error_triage
from argos_ops.agents.error_triage import (
    ErrorCluster,
    build_report,
    collect_clusters,
    extract_signature,
)
from argos_ops.notifications.discord import GREEN, RED, YELLOW


# =============================================================================
# extract_signature
# =============================================================================
def test_extract_signature_from_connection_error() -> None:
    assert extract_signature("ConnectionError: foo bar") == "ConnectionError"


def test_extract_signature_from_dotted_path() -> None:
    assert extract_signature("httpx.TimeoutException: too slow") == "httpx.TimeoutException"


def test_extract_signature_simple_word() -> None:
    assert extract_signature("failed: timeout") == "failed"


def test_extract_signature_none_returns_unknown() -> None:
    assert extract_signature(None) == "<unknown>"


def test_extract_signature_empty_returns_unknown() -> None:
    assert extract_signature("") == "<unknown>"


def test_extract_signature_non_alpha_prefix_returns_unknown() -> None:
    assert extract_signature("!!!boom") == "<unknown>"


# =============================================================================
# collect_clusters
# =============================================================================
@pytest.mark.asyncio
async def test_collect_clusters_groups_across_agents() -> None:
    """3 erreurs ConnectionError de 2 agents distincts → 1 cluster count=3."""
    session = MagicMock()
    rows = [
        ("EmailBot", "ConnectionError: refused", "error"),
        ("FinanceBot", "ConnectionError: timeout", "error"),
        ("EmailBot", "ConnectionError: dns", "error"),
        ("FinanceBot", "ValueError: bad input", "error"),
    ]
    with patch.object(error_triage, "_fetch_errors", new=AsyncMock(return_value=rows)):
        clusters, total = await collect_clusters(session)
    assert total == 4
    by_sig = {c.signature: c for c in clusters}
    assert by_sig["ConnectionError"].count == 3
    assert sorted(by_sig["ConnectionError"].affected_agents) == ["EmailBot", "FinanceBot"]
    assert by_sig["ValueError"].count == 1


@pytest.mark.asyncio
async def test_collect_clusters_empty_when_no_errors() -> None:
    session = MagicMock()
    with patch.object(error_triage, "_fetch_errors", new=AsyncMock(return_value=[])):
        clusters, total = await collect_clusters(session)
    assert clusters == []
    assert total == 0


# =============================================================================
# build_report
# =============================================================================
def _cluster(sig: str, count: int) -> ErrorCluster:
    return ErrorCluster(
        signature=sig,
        count=count,
        affected_agents=["EmailBot"],
        sample_message=f"{sig}: example",
    )


def test_build_report_silence_when_below_threshold() -> None:
    """1 cluster à 2 occurrences (< 3) → silence vert."""
    report = build_report([_cluster("ConnectionError", 2)], total_errors=2)
    assert report.should_alert is False
    assert report.alert_color == GREEN
    assert report.clusters == []


def test_build_report_yellow_when_cluster_above_min_below_critical() -> None:
    """1 cluster à 5 occurrences (>=3, <10) → jaune."""
    report = build_report([_cluster("ConnectionError", 5)], total_errors=5)
    assert report.should_alert is True
    assert report.alert_color == YELLOW
    assert len(report.clusters) == 1


def test_build_report_red_when_cluster_above_critical() -> None:
    """1 cluster à 15 occurrences (>=10) → rouge."""
    report = build_report(
        [_cluster("OOM", 15), _cluster("ConnectionError", 4)], total_errors=19
    )
    assert report.should_alert is True
    assert report.alert_color == RED
    assert len(report.clusters) == 2


def test_build_report_filters_clusters_below_threshold() -> None:
    """Les clusters < min_occurrences sont retirés de la liste d'embed."""
    report = build_report(
        [_cluster("Noise", 1), _cluster("Real", 4)], total_errors=5
    )
    assert len(report.clusters) == 1
    assert report.clusters[0].signature == "Real"
