"""Tests de la console bot (Cockpit LOT 3) — parties pures.

Compose IN, prompt de génération, parsing draft+verdict, gâchette. Le streaming
live (moteur atelier) est de l'intégration, non testé ici."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from argos_ops.fleet_memory import append_fact
from argos_ops.ops_dashboard import app as app_module
from argos_ops.ops_dashboard.app import app
from argos_ops.ops_dashboard.console import (
    build_generate_prompt,
    can_act,
    compose_in,
    parse_generation,
)


# =============================================================================
# compose_in
# =============================================================================
@pytest.mark.asyncio
async def test_compose_in_assembles_memory(tmp_path: Path) -> None:
    from argos_ops.fleet_memory import append_fact

    await append_fact("EmailBot", "Acme veut un devis", kind="lead-signal", root=tmp_path)
    comp = await compose_in(
        "EmailBot",
        include_accessible_memory=False,
        skills=("zimbra-ops",),
        data_summary="config: enabled",
        root=tmp_path,
    )
    keys = {s.key for s in comp.sources}
    assert keys == {"own_memory", "skills", "data"}
    own = next(s for s in comp.sources if s.key == "own_memory")
    assert own.count == 1
    assert "Acme veut un devis" in comp.context_text
    assert "zimbra-ops" in comp.context_text


@pytest.mark.asyncio
async def test_compose_in_respects_checkboxes(tmp_path: Path) -> None:
    comp = await compose_in(
        "EmailBot",
        include_own_memory=False,
        include_accessible_memory=False,
        include_skills=False,
        include_data=False,
        root=tmp_path,
    )
    assert comp.sources == []
    assert comp.context_text == ""


# =============================================================================
# build_generate_prompt
# =============================================================================
@pytest.mark.asyncio
async def test_build_generate_prompt_has_markers_and_task(tmp_path: Path) -> None:
    comp = await compose_in("EmailBot", root=tmp_path)
    prompt = build_generate_prompt("EmailBot", "Réponds au lead Acme", comp)
    assert "EmailBot" in prompt
    assert "Réponds au lead Acme" in prompt
    assert "<<<DRAFT>>>" in prompt and "<<<END_DRAFT>>>" in prompt
    assert "json" in prompt.lower()


# =============================================================================
# parse_generation
# =============================================================================
def test_parse_generation_extracts_draft_and_verdict() -> None:
    output = (
        "Voici le brouillon :\n"
        "<<<DRAFT>>>\nBonjour Acme, voici votre devis…\n<<<END_DRAFT>>>\n"
        "```json\n"
        '{"factual_score": 88, "tone_score": 90, "legal_score": 95, '
        '"global_score": 86, "rationale": "Solide."}\n'
        "```"
    )
    result = parse_generation(output)
    assert result.draft == "Bonjour Acme, voici votre devis…"
    assert result.report.global_score == 86
    assert result.verdict == "auto_send"  # 86/88/95 → auto


def test_parse_generation_routes_killed_on_low_legal() -> None:
    output = (
        "<<<DRAFT>>>\nun texte risqué\n<<<END_DRAFT>>>\n"
        '```json\n{"factual_score": 80, "tone_score": 80, "legal_score": 30, '
        '"global_score": 70, "rationale": "Risque RGPD."}\n```'
    )
    result = parse_generation(output)
    assert result.verdict == "killed"  # legal < 50 → kill


def test_parse_generation_raises_without_draft() -> None:
    with pytest.raises(ValueError):
        parse_generation(
            '```json\n{"factual_score":80,"tone_score":80,'
            '"legal_score":80,"global_score":80,"rationale":"x"}\n```'
        )


# =============================================================================
# can_act — la gâchette
# =============================================================================
def test_can_act_killed_never() -> None:
    assert can_act("killed", human_approved=True) is False
    assert can_act("killed", human_approved=False) is False


def test_can_act_requires_human_even_for_auto() -> None:
    # Même auto_send exige le clic humain depuis le web (jamais par surprise).
    assert can_act("auto_send", human_approved=False) is False
    assert can_act("auto_send", human_approved=True) is True


def test_can_act_queued_only_with_approval() -> None:
    assert can_act("queued", human_approved=False) is False
    assert can_act("queued", human_approved=True) is True


# =============================================================================
# Endpoint GET /console/in
# =============================================================================
def test_console_in_endpoint(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(app_module, "FLEET_MEMORY_ROOT", tmp_path)
    asyncio.run(append_fact("EmailBot", "Acme veut un devis", kind="lead-signal", root=tmp_path))
    client = TestClient(app)
    resp = client.get("/api/agents/EmailBot/console/in")
    assert resp.status_code == 200
    body = resp.json()
    assert body["bot"] == "EmailBot"
    own = next(s for s in body["sources"] if s["key"] == "own_memory")
    assert own["count"] == 1
    assert body["context_chars"] > 0


def test_console_in_unknown_agent_404(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(app_module, "FLEET_MEMORY_ROOT", tmp_path)
    assert TestClient(app).get("/api/agents/NopeBot/console/in").status_code == 404
