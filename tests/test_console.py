"""Tests de la console bot (Cockpit LOT 3) — parties pures.

Compose IN, prompt de génération, parsing draft+verdict, gâchette. Le streaming
live (moteur atelier) est de l'intégration, non testé ici."""

from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from argos_ops.config import Settings
from argos_ops.fleet_memory import append_fact
from argos_ops.ops_dashboard import app as app_module
from argos_ops.ops_dashboard.app import app
from argos_ops.ops_dashboard.atelier_audit import AuditEvent
from argos_ops.ops_dashboard.console import (
    build_generate_prompt,
    can_act,
    compose_in,
    is_bot_live,
    parse_generation,
    read_live_status,
)


def _settings(**kw: object) -> Settings:
    return Settings(_env_file=None, **kw)  # type: ignore[call-arg]


# =============================================================================
# read_live_status — badge LIVE/SHADOW relu à chaud (Axe 4)
# =============================================================================
def test_read_live_status_conservative_for_unknown_bot() -> None:
    # Bot hors table _LIVE_FLAG_BY_BOT → SHADOW (jamais LIVE par erreur).
    assert read_live_status("DigestBuilder") is False


def test_read_live_status_reflects_env_hot(monkeypatch: pytest.MonkeyPatch) -> None:
    # Relecture fraîche : un flip de OUTBOUND_LIVE_MODE est pris en compte sans
    # passer par le singleton get_settings() (hot-reload du badge).
    monkeypatch.setenv("OUTBOUND_LIVE_MODE", "true")
    assert read_live_status("OutboundBot") is True
    monkeypatch.setenv("OUTBOUND_LIVE_MODE", "false")
    assert read_live_status("OutboundBot") is False


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


# =============================================================================
# is_bot_live + SHADOW/LIVE
# =============================================================================
def test_is_bot_live_flag_armed() -> None:
    assert is_bot_live("OutboundBot", _settings(OUTBOUND_LIVE_MODE=True)) is True
    assert is_bot_live("AdBot", _settings(ADS_LIVE_MODE=True)) is True


def test_is_bot_live_default_shadow() -> None:
    s = _settings()
    assert is_bot_live("OutboundBot", s) is False  # flag off
    assert is_bot_live("EmailBot", s) is False  # bot hors table → shadow
    assert is_bot_live("InconnuBot", s) is False


# =============================================================================
# Endpoint act — la gâchette
# =============================================================================
def test_console_act_killed_blocked() -> None:
    client = TestClient(app)
    r = client.post(
        "/api/agents/EmailBot/console/act", json={"verdict": "killed", "approved": True}
    )
    assert r.status_code == 200
    body = r.json()
    assert body["acted"] is False
    assert "killed" in (body["reason"] or "")


def test_console_act_requires_approval() -> None:
    client = TestClient(app)
    r = client.post(
        "/api/agents/EmailBot/console/act", json={"verdict": "queued", "approved": False}
    )
    assert r.json()["acted"] is False


def test_console_act_runs_when_approved() -> None:
    # auto_send + approuvé sur un bot lançable → déclenche run_agent (mocké).
    fake_result = MagicMock(status="success", output_summary="ok", error=None)
    with (
        patch.object(app_module, "run_agent", AsyncMock(return_value=fake_result)) as run,
        patch.object(app_module, "_build_agent", MagicMock()),
    ):
        r = TestClient(app).post(
            "/api/agents/EmailBot/console/act", json={"verdict": "auto_send", "approved": True}
        )
    body = r.json()
    assert body["acted"] is True
    assert body["status"] == "success"
    run.assert_awaited_once()


# =============================================================================
# Axe 4 — audit de console_act (toutes branches) + hot-reload badge↔action
# =============================================================================
def test_console_act_audits_every_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    """L'audit (chantier 2) doit tracer les 4 issues de console_act, refus
    inclus — sinon une suppression d'un record() passerait inaperçue."""
    events: list[AuditEvent] = []
    monkeypatch.setattr(app_module.atelier_audit, "record", lambda e, **k: events.append(e))
    fake_result = MagicMock(status="success", output_summary="ok", error=None)
    with (
        patch.object(app_module, "run_agent", AsyncMock(return_value=fake_result)),
        patch.object(app_module, "_build_agent", MagicMock()),
    ):
        client = TestClient(app)
        client.post(
            "/api/agents/EmailBot/console/act", json={"verdict": "killed", "approved": True}
        )
        client.post(
            "/api/agents/EmailBot/console/act", json={"verdict": "queued", "approved": False}
        )
        # KNOWN mais NON runnable (writer interactif) → not_runnable.
        client.post(
            "/api/agents/LinkedInWriter/console/act",
            json={"verdict": "auto_send", "approved": True},
        )
        client.post(
            "/api/agents/EmailBot/console/act", json={"verdict": "auto_send", "approved": True}
        )

    outcomes = {e.outcome for e in events}
    assert {"blocked_killed", "blocked_not_approved", "not_runnable", "executed"} <= outcomes
    executed = next(e for e in events if e.outcome == "executed")
    assert executed.acted is True
    assert executed.bot == "EmailBot"
    assert executed.verdict == "auto_send"
    assert executed.approved is True


def test_console_status_live_reflects_env_flip(monkeypatch: pytest.MonkeyPatch) -> None:
    """GET /console/status relit le mode LIVE à chaud : un flip d'env est reflété
    sans recréer le client ni redémarrer (chantier 4)."""
    client = TestClient(app)
    monkeypatch.setenv("OUTBOUND_LIVE_MODE", "false")
    assert client.get("/api/agents/OutboundBot/console/status").json()["live"] is False
    monkeypatch.setenv("OUTBOUND_LIVE_MODE", "true")
    assert client.get("/api/agents/OutboundBot/console/status").json()["live"] is True


def test_console_act_live_consistent_via_refresh(monkeypatch: pytest.MonkeyPatch) -> None:
    """console_act rafraîchit les Settings avant d'agir → son champ ``live``
    reflète le flip d'env (cohérence badge↔action sans redémarrage)."""
    from argos_ops import config

    monkeypatch.setattr(app_module.atelier_audit, "record", lambda e, **k: None)
    monkeypatch.setenv("OUTBOUND_LIVE_MODE", "true")
    fake_result = MagicMock(status="success", output_summary="ok", error=None)
    try:
        with (
            patch.object(app_module, "run_agent", AsyncMock(return_value=fake_result)),
            patch.object(app_module, "_build_agent", MagicMock()),
        ):
            r = TestClient(app).post(
                "/api/agents/OutboundBot/console/act",
                json={"verdict": "auto_send", "approved": True},
            )
        assert r.json()["live"] is True  # refresh_settings() a capté le flip
    finally:
        config._settings = None  # purge le singleton pollué par refresh_settings
