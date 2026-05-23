"""Tests CrisisCommBot."""

from __future__ import annotations

from pathlib import Path

import yaml

from argos_ops.agents.crisis_comm import (
    CrisisIncident,
    CrisisStats,
    build_crisis_embed,
    draft_response,
    load_incidents,
    select_template,
)
from argos_ops.notifications.discord import GREEN, RED, YELLOW


def test_load_incidents_skips_invalid(tmp_path: Path) -> None:
    path = tmp_path / "i.yaml"
    path.write_text(
        yaml.safe_dump(
            {
                "incidents": [
                    {"id": "1", "incident_type": "data_breach"},
                    {"id": "missing-type"},
                ]
            }
        ),
        encoding="utf-8",
    )
    out = load_incidents(path)
    assert len(out) == 1
    assert out[0].incident_type == "data_breach"


def test_select_template_known_and_unknown() -> None:
    assert "confiné" in select_template("data_breach")
    assert "indisponibilité" in select_template("service_down")
    assert "non reconnu" in select_template("ufo_attack")


def test_draft_response_substitutes_scope_and_time() -> None:
    incident = CrisisIncident(
        id="2026-05-23-x",
        incident_type="data_breach",
        severity="critical",
        scope="API publique",
        time="14h Paris",
        notes="à compléter",
    )
    md = draft_response(incident)
    assert "API publique" in md
    assert "14h Paris" in md
    assert "status: drafted" in md
    assert "CNIL" in md  # checklist


def test_build_crisis_embed_color_by_severity() -> None:
    quiet = CrisisStats(total=2, open_count=0)
    assert build_crisis_embed(quiet).color == GREEN
    minor = CrisisStats(total=2, open_count=1)
    assert build_crisis_embed(minor).color == YELLOW
    critical = CrisisStats(total=2, open_count=1, critical_open=1)
    assert build_crisis_embed(critical).color == RED
