"""Atelier libre embarqué — Claude Code piloté depuis le panel web (Cockpit).

Architecture (note d'archi validée 2026-06-07) :

- **Moteur** : le CLI ``claude`` local en mode headless
  (``claude -p --output-format stream-json``). Hérite du token OAuth de
  l'abonnement Pro/Max dans ``~/.claude`` → **aucune API key tierce** (D-017).
  Le Claude Agent SDK est écarté car il exige ``ANTHROPIC_API_KEY``.
- **Transport** : WebSocket full-duplex (cf. endpoint dans ``app.py``).
- **Exposition** : local-only, derrière le flag ``OPS_ATELIER_ENABLED``
  (OFF par défaut) — RCE par conception, jamais routé à distance.
- **Permissions** : ``read`` (= ``plan``, lecture seule) par défaut, ``edit``
  (= ``acceptEdits``) sur action explicite de l'humain dans l'UI.

Ce module est **pur/testable** : construction d'argv, normalisation des events
stream-json, garde-fou d'auth WS. La gestion du process vit dans
:class:`AtelierSession`.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import subprocess
import threading
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any, Literal

from loguru import logger

from argos_ops.config import REPO_ROOT, Settings
from argos_ops.ops_dashboard import auth

PermissionMode = Literal["read", "fleet"]

# Config MCP du serveur de pilotage flotte (cf. argos_ops/mcp/fleet_server.py),
# lancé en stdio par le CLI claude. cwd = racine repo → `uv run` résout le projet.
_FLEET_MCP_CONFIG = json.dumps(
    {
        "mcpServers": {
            "fleet": {
                "command": "uv",
                "args": ["run", "python", "-m", "argos_ops.mcp.fleet_server"],
            }
        }
    }
)

# Outils autorisés en mode pilotage flotte : lecture du repo + outils MCP flotte
# + écriture SCOPÉE à data/ (brouillons, contenus). L'écriture hors data/ (le
# code : argos_ops/, scripts/, etc.) n'est PAS dans l'allowlist → refusée par
# défaut en headless. C'est l'allowlist qui garantit l'inviolabilité du code.
_FLEET_ALLOWED_TOOLS = (
    "Read,Glob,Grep,Write(data/**),Edit(data/**),"
    "mcp__fleet__list_bots,mcp__fleet__run_bot,mcp__fleet__read_bot_memory,"
    "mcp__fleet__bot_in_memory,mcp__fleet__remember_fact"
)

_FLEET_SYSTEM_PROMPT = (
    "Tu es le chef d'orchestre de la flotte Argos Ops (mode « pilotage flotte »). "
    "Tu ne modifies JAMAIS le CODE du repo (argos_ops/, scripts/, .claude/, etc. — "
    "Write/Edit y sont refusés). Tu PEUX en revanche créer/éditer des brouillons et "
    "artefacts dans data/ (ex. data/content/drafts/) pour préparer du contenu. "
    "Tu peux aussi lire le repo, lire la mémoire des bots (mcp__fleet__read_bot_memory "
    "/ mcp__fleet__bot_in_memory), MÉMORISER un fait utile pour un bot "
    "(mcp__fleet__remember_fact — capitalise ce que tu apprends en pilotant : signal "
    "client, heuristique validée, contrainte découverte) et LANCER des bots "
    "(mcp__fleet__run_bot) après les avoir listés via mcp__fleet__list_bots. Méthode : "
    "comprends l'intention → propose un plan court → crée les brouillons nécessaires "
    "dans data/ → lance les bots utiles → agrège → mémorise ce qui mérite de l'être → "
    "présente clairement. Les bots qui publient/envoient ne partent en réel que si leur "
    "flag live est déjà activé (sinon brouillon shadow). En cas de doute sur une action "
    "externe (post, email), demande avant de lancer."
)


# =============================================================================
# Construction de la commande (pure)
# =============================================================================
def build_claude_argv(
    prompt: str,
    *,
    claude_bin: str = "claude",
    session_id: str | None = None,
    permission_mode: PermissionMode = "read",
) -> list[str]:
    """Construit l'argv du CLI ``claude`` headless pour un tour.

    - ``read`` : ``--permission-mode plan`` (lecture seule, aucune écriture).
    - ``fleet`` : serveur MCP flotte branché + outils flotte/lecture autorisés
      + écriture scopée à ``data/`` (le code reste hors allowlist → refusé),
      prompt système « chef d'orchestre ».

    Premier tour : pas de ``--resume`` (claude crée la session, l'``session_id``
    est capté dans l'event ``system/init``). Tours suivants : ``--resume``.
    """
    argv = [
        claude_bin,
        "-p",
        prompt,
        "--output-format",
        "stream-json",
        "--verbose",
        "--include-partial-messages",
    ]
    if permission_mode == "fleet":
        argv += [
            "--permission-mode",
            "default",
            "--mcp-config",
            _FLEET_MCP_CONFIG,
            "--allowedTools",
            _FLEET_ALLOWED_TOOLS,
            "--append-system-prompt",
            _FLEET_SYSTEM_PROMPT,
        ]
    else:
        argv += ["--permission-mode", "plan"]
    if session_id:
        argv += ["--resume", session_id]
    return argv


# =============================================================================
# Normalisation des events stream-json (pure)
# =============================================================================
def normalize_event(obj: Any) -> dict[str, Any]:
    """Réduit un event stream-json à un petit schéma stable pour le front.

    Schéma de sortie (clé ``kind``) :
    - ``system`` : ``{kind, session_id}``
    - ``text`` : ``{kind, text}`` (delta de texte assistant)
    - ``tool_use`` : ``{kind, name, id}``
    - ``result`` : ``{kind, text, is_error}``
    - ``raw`` : ``{kind, data}`` (fallback défensif, jamais perdu)

    Défensif : les formats stream-json varient selon la version du CLI, donc on
    vérifie plusieurs emplacements et on retombe sur ``raw`` si inconnu.
    """
    if not isinstance(obj, dict):
        return {"kind": "raw", "data": obj}

    etype = obj.get("type")

    if etype == "system":
        sid = obj.get("session_id")
        if sid is None and isinstance(obj.get("data"), dict):
            sid = obj["data"].get("session_id")
        return {"kind": "system", "session_id": sid}

    if etype == "result":
        return {
            "kind": "result",
            "text": obj.get("result") or obj.get("subtype") or "",
            "is_error": bool(obj.get("is_error", False)),
        }

    if etype == "stream_event":
        event = obj.get("event") or {}
        if isinstance(event, dict):
            ev = event.get("type")
            delta = event.get("delta") or {}
            if (
                ev == "content_block_delta"
                and isinstance(delta, dict)
                and delta.get("type") == "text_delta"
            ):
                return {"kind": "text", "text": str(delta.get("text", ""))}
            if ev == "content_block_start":
                block = event.get("content_block") or {}
                if isinstance(block, dict) and block.get("type") == "tool_use":
                    return {
                        "kind": "tool_use",
                        "name": str(block.get("name", "?")),
                        "id": str(block.get("id", "")),
                    }
        return {"kind": "raw", "data": obj}

    # Résultat d'outil (renvoyé par claude dans un message ``user``).
    if etype == "user":
        message = obj.get("message") or {}
        if isinstance(message, dict):
            for block in message.get("content") or []:
                if isinstance(block, dict) and block.get("type") == "tool_result":
                    return {"kind": "tool_result", "text": _block_text(block.get("content"))}

    # NB : on n'émet PAS le message ``assistant`` complet — son texte est déjà
    # arrivé en streaming via les ``content_block_delta``. Le ré-émettre
    # provoquerait un doublon a l'ecran (memes tokens, affiches 2 fois).
    return {"kind": "raw", "data": obj}


def _block_text(content: Any) -> str:
    """Extrait le texte d'un champ ``content`` (str, ou liste de blocs)."""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [
            str(b.get("text", ""))
            for b in content
            if isinstance(b, dict) and b.get("type") == "text"
        ]
        return "\n".join(p for p in parts if p)
    return ""


# =============================================================================
# Garde-fou d'auth WebSocket (pure)
# =============================================================================
def ws_authorized(
    *,
    client_ip: str | None,
    authorization: str | None,
    token: str | None,
    settings: Settings,
) -> bool:
    """Autorise une connexion WS à l'atelier — même posture que l'HTTP.

    Le middleware HTTP ne couvre PAS les WebSockets (Starlette), donc on
    re-vérifie ici : IP allowlist + (fail-open si auth applicative non armée,
    sinon Basic/JWT du handshake, avec fallback ``?token=`` pour le Bearer).
    """
    if not auth.ip_is_allowed(client_ip, settings):
        return False
    if not auth.is_basic_auth_enabled(settings):
        return True  # fail-open local, cohérent avec ops_auth_guard
    authz = authorization
    if authz is None and token:
        authz = f"Bearer {token}"
    return auth.request_is_authenticated(authz, settings)


# =============================================================================
# Session (gestion du process)
# =============================================================================
class AtelierSession:
    """Une session atelier = un fil de conversation Claude Code résumable.

    Un seul tour (process) à la fois. ``interrupt()`` tue le tour en cours.
    """

    def __init__(
        self,
        *,
        claude_bin: str = "claude",
        repo_root: Path = REPO_ROOT,
    ) -> None:
        self.session_id: str | None = None
        self._claude_bin = claude_bin
        self._repo_root = repo_root
        self._proc: subprocess.Popen[str] | None = None
        # Verrou « 1 tour in-flight par session » (Axe 4). Posé/relâché DANS la
        # coroutine ``send`` (pas dans le thread _pump) → atomique sous l'event
        # loop, pas de course thread/loop. Source de vérité du rejet « busy ».
        self._busy = False

    @property
    def running(self) -> bool:
        return self._proc is not None and self._proc.poll() is None

    def interrupt(self) -> None:
        if self.running and self._proc is not None:
            logger.info("Atelier — interruption du tour en cours")
            with contextlib.suppress(ProcessLookupError, OSError):
                self._proc.terminate()

    async def send(
        self, prompt: str, *, permission_mode: PermissionMode = "read"
    ) -> AsyncIterator[dict[str, Any]]:
        """Lance un tour et streame les events normalisés.

        Le CLI ``claude`` tourne dans un **thread** (``subprocess.Popen``
        bloquant), pas via ``asyncio.create_subprocess_exec`` : sur Windows le
        panel force le ``SelectorEventLoop`` (requis par psycopg) qui ne
        supporte pas les sous-process asyncio. Le thread pousse les events dans
        une queue asyncio. Un process en échec remonte ``error`` puis
        ``turn_done`` ; ``session_id`` est capté au 1er event ``system``.

        Rate-limit (Axe 4) : si un tour est déjà in-flight sur cette session,
        ``send`` **rejette** immédiatement (yield ``busy`` puis ``return``) au
        lieu de lancer un 2e subprocess — pas de file d'attente, le quota reste
        borné à 1 run par session.
        """
        if self._busy:
            yield {"kind": "busy", "message": "Un tour est déjà en cours."}
            return
        self._busy = True
        try:
            async for event in self._run_turn(prompt, permission_mode=permission_mode):
                yield event
        finally:
            self._busy = False

    async def _run_turn(
        self, prompt: str, *, permission_mode: PermissionMode = "read"
    ) -> AsyncIterator[dict[str, Any]]:
        """Corps du tour (subprocess + drain). Appelé sous le verrou ``_busy``."""
        argv = build_claude_argv(
            prompt,
            claude_bin=self._claude_bin,
            session_id=self.session_id,
            permission_mode=permission_mode,
        )
        logger.info(f"Atelier — tour ({permission_mode}) resume={self.session_id is not None}")

        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[dict[str, Any] | None] = asyncio.Queue()

        def _emit(event: dict[str, Any] | None) -> None:
            loop.call_soon_threadsafe(queue.put_nowait, event)

        def _pump() -> None:
            try:
                proc = subprocess.Popen(
                    argv,
                    cwd=str(self._repo_root),
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,  # fusion stderr→stdout : pas de deadlock de pipe
                    stdin=subprocess.DEVNULL,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    bufsize=1,
                )
            except FileNotFoundError:
                _emit(
                    {
                        "kind": "error",
                        "message": f"Binaire introuvable : {self._claude_bin}. "
                        "Claude Code doit être installé et loggué (abonnement Pro/Max).",
                    }
                )
                _emit({"kind": "turn_done", "returncode": 127})
                _emit(None)
                return

            self._proc = proc
            assert proc.stdout is not None
            for raw in proc.stdout:
                line = raw.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    _emit({"kind": "raw", "data": line})
                    continue
                _emit(normalize_event(obj))
            rc = proc.wait()
            if rc not in (0, None):
                _emit({"kind": "error", "message": f"claude a quitté (code {rc})"})
            _emit({"kind": "turn_done", "returncode": rc})
            _emit(None)  # sentinelle de fin

        threading.Thread(target=_pump, name="atelier-claude", daemon=True).start()

        while True:
            event = await queue.get()
            if event is None:
                break
            if event.get("kind") == "system" and event.get("session_id"):
                self.session_id = str(event["session_id"])
            yield event


__all__ = [
    "AtelierSession",
    "PermissionMode",
    "build_claude_argv",
    "normalize_event",
    "ws_authorized",
]
