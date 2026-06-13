"""Tests de l'atelier libre embarqué (Cockpit) — parties pures.

Couvre la construction d'argv CLI, la normalisation des events stream-json
et le garde-fou d'auth WebSocket. La boucle WS + le subprocess claude sont de
l'intégration (non testés ici, pas de binaire claude en CI)."""

from __future__ import annotations

import pytest

from argos_ops.config import Settings
from argos_ops.ops_dashboard import auth
from argos_ops.ops_dashboard.atelier import (
    AtelierSession,
    build_claude_argv,
    normalize_event,
    ws_authorized,
)


def _settings(**kw: object) -> Settings:
    return Settings(_env_file=None, **kw)  # type: ignore[call-arg]


# =============================================================================
# build_claude_argv
# =============================================================================
def test_argv_first_turn_no_resume() -> None:
    argv = build_claude_argv("salut", permission_mode="read")
    assert argv[0] == "claude"
    assert "-p" in argv and "salut" in argv
    assert "--output-format" in argv and "stream-json" in argv
    assert "--resume" not in argv
    i = argv.index("--permission-mode")
    assert argv[i + 1] == "plan"  # read → plan


def test_argv_resume_when_session() -> None:
    argv = build_claude_argv("suite", session_id="sess-123")
    assert "--resume" in argv
    assert argv[argv.index("--resume") + 1] == "sess-123"


def test_argv_fleet_mode_wires_mcp_and_scopes_writes_to_data() -> None:
    argv = build_claude_argv("lance TrendSpotter", permission_mode="fleet")
    # Serveur MCP flotte branché + outils flotte autorisés.
    assert "--mcp-config" in argv
    assert "argos_ops.mcp.fleet_server" in argv[argv.index("--mcp-config") + 1]
    allowed = argv[argv.index("--allowedTools") + 1]
    assert "mcp__fleet__run_bot" in allowed
    # Écriture SCOPÉE à data/ (brouillons) — le code n'est pas dans l'allowlist.
    assert "Write(data/**)" in allowed
    assert "Edit(data/**)" in allowed
    # Pas d'allow-write global (qui ouvrirait le code).
    assert "Write,Edit" not in allowed and ",Write," not in allowed
    # Prompt orchestrateur présent, et PAS le mode plan (qui est read-only).
    assert "--append-system-prompt" in argv
    assert "plan" not in argv


def test_argv_read_is_plan() -> None:
    argv = build_claude_argv("question", permission_mode="read")
    assert argv[argv.index("--permission-mode") + 1] == "plan"
    assert "--mcp-config" not in argv


def test_argv_custom_bin() -> None:
    argv = build_claude_argv("x", claude_bin="/usr/local/bin/claude")
    assert argv[0] == "/usr/local/bin/claude"


# =============================================================================
# normalize_event
# =============================================================================
def test_normalize_system_top_level_session() -> None:
    ev = normalize_event({"type": "system", "subtype": "init", "session_id": "abc"})
    assert ev == {"kind": "system", "session_id": "abc"}


def test_normalize_system_nested_session() -> None:
    ev = normalize_event({"type": "system", "data": {"session_id": "xyz"}})
    assert ev["kind"] == "system"
    assert ev["session_id"] == "xyz"


def test_normalize_text_delta() -> None:
    ev = normalize_event(
        {
            "type": "stream_event",
            "event": {
                "type": "content_block_delta",
                "delta": {"type": "text_delta", "text": "Hello"},
            },
        }
    )
    assert ev == {"kind": "text", "text": "Hello"}


def test_normalize_tool_use_start() -> None:
    ev = normalize_event(
        {
            "type": "stream_event",
            "event": {
                "type": "content_block_start",
                "content_block": {"type": "tool_use", "name": "Read", "id": "t1"},
            },
        }
    )
    assert ev == {"kind": "tool_use", "name": "Read", "id": "t1"}


def test_normalize_result() -> None:
    ev = normalize_event({"type": "result", "result": "fini", "is_error": False})
    assert ev == {"kind": "result", "text": "fini", "is_error": False}


def test_normalize_assistant_full_message_is_raw_not_duplicated() -> None:
    # Le message assistant complet ne doit PAS être ré-émis comme texte : son
    # contenu est déjà arrivé en streaming via les deltas. Sinon → doublon.
    ev = normalize_event(
        {"type": "assistant", "message": {"content": [{"type": "text", "text": "Bonjour"}]}}
    )
    assert ev["kind"] == "raw"


def test_normalize_tool_result() -> None:
    ev = normalize_event(
        {
            "type": "user",
            "message": {
                "content": [{"type": "tool_result", "content": [{"type": "text", "text": "fait"}]}]
            },
        }
    )
    assert ev == {"kind": "tool_result", "text": "fait"}


def test_normalize_unknown_falls_back_to_raw() -> None:
    assert normalize_event({"type": "weird"})["kind"] == "raw"
    assert normalize_event("not a dict")["kind"] == "raw"


# =============================================================================
# ws_authorized
# =============================================================================
def test_ws_open_when_auth_not_configured() -> None:
    # Aucun basic auth armé → fail-open local (cohérent avec ops_auth_guard).
    s = _settings()
    assert ws_authorized(client_ip="127.0.0.1", authorization=None, token=None, settings=s) is True


def test_ws_blocked_by_ip_allowlist() -> None:
    # Settings utilise des alias (pas de populate_by_name) → init par alias.
    s = _settings(OPS_DASHBOARD_IP_ALLOWLIST="10.0.0.0/8")
    assert ws_authorized(client_ip="1.2.3.4", authorization=None, token=None, settings=s) is False


def test_ws_requires_creds_when_basic_enabled() -> None:
    s = _settings(
        OPS_DASHBOARD_BASIC_AUTH_USER="admin",
        OPS_DASHBOARD_BASIC_AUTH_PASSWORD="pw",
    )
    assert ws_authorized(client_ip="127.0.0.1", authorization=None, token=None, settings=s) is False


def test_ws_accepts_valid_bearer_token_via_query() -> None:
    s = _settings(
        OPS_DASHBOARD_BASIC_AUTH_USER="admin",
        OPS_DASHBOARD_BASIC_AUTH_PASSWORD="pw",
        OPS_DASHBOARD_JWT_SECRET="super-secret-key-at-least-32-bytes-long",
    )
    token = auth.issue_session_token("admin", s)
    assert ws_authorized(client_ip="127.0.0.1", authorization=None, token=token, settings=s) is True


# =============================================================================
# AtelierSession — rate-limit « 1 tour in-flight » (Axe 4)
# =============================================================================
@pytest.mark.asyncio
async def test_session_rejects_concurrent_turn_with_busy() -> None:
    """Un 2e tour pendant qu'un tour est in-flight est REJETÉ (busy), sans
    lancer de subprocess claude (pas de file d'attente, quota borné à 1)."""
    session = AtelierSession(claude_bin="claude")
    session._busy = True  # simule un tour déjà en cours
    events = [ev async for ev in session.send("salut", permission_mode="read")]
    assert events == [{"kind": "busy", "message": "Un tour est déjà en cours."}]
    # Le verrou n'a pas été touché (on a rejeté avant de l'acquérir).
    assert session._busy is True


@pytest.mark.asyncio
async def test_session_releases_busy_after_turn(monkeypatch: pytest.MonkeyPatch) -> None:
    """Le verrou ``_busy`` est pris pendant le tour puis relâché par le finally —
    un tour suivant est de nouveau accepté (pas de blocage permanent)."""
    session = AtelierSession(claude_bin="claude")

    async def fake_run_turn(prompt: str, *, permission_mode: str = "read") -> object:
        assert session._busy is True  # verrou pris pendant le tour
        yield {"kind": "text", "text": "hi"}

    monkeypatch.setattr(session, "_run_turn", fake_run_turn)
    events = [ev async for ev in session.send("salut")]
    assert events == [{"kind": "text", "text": "hi"}]
    assert session._busy is False  # relâché par le finally

    # Un 2e tour repart (le slot a bien été rouvert).
    events2 = [ev async for ev in session.send("encore")]
    assert events2 == [{"kind": "text", "text": "hi"}]
