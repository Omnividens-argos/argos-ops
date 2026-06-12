"""Cerveau LLM partagé des agents Python (Axe 2 audit, D-017).

Sous D-017, aucune API LLM tierce : le « cerveau » est le CLI ``claude``
local (abonnement Pro/Max), invoqué en **one-shot headless**
(``claude -p <prompt> --output-format json --permission-mode plan``) —
même moteur que l'Atelier libre et la Console bot, mais sans outils ni
session : une question, une réponse JSON, terminé.

Contrat (pattern juge, cf. :mod:`argos_ops.judge` : « le LLM note,
Python tranche ») — tout consommateur de :func:`think_json` DOIT :

- avoir un **fallback heuristique** si le cerveau est OFF ou en échec :
  un bot ne crash jamais et ne se tait jamais parce que le cerveau est
  indisponible ;
- respecter les **overrides humains** AVANT de consulter le cerveau ;
- **valider côté Python** la sortie (enum, bornes, ids connus) — le LLM
  propose, il ne décide jamais seul d'une action.

OFF par défaut (``OPS_BRAIN_ENABLED=false``) : toute la flotte garde son
comportement heuristique historique tant que le flag n'est pas activé.

⚠️ Windows : les agents tournent souvent sous ``SelectorEventLoop``
(requis par psycopg), incompatible avec ``asyncio.create_subprocess_*``.
Le subprocess est donc exécuté dans un thread (``anyio.to_thread``) —
même logique que l'atelier (cf. ``ops_dashboard/atelier.py``) et le
serveur MCP flotte.
"""

from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from typing import Literal

import anyio
from loguru import logger

from argos_ops.config import REPO_ROOT, get_settings

BrainEngine = Literal["claude", "disabled", "error"]

DEFAULT_TIMEOUT_S = 120
# Le prompt passe en argv → limite dure CreateProcess Windows ~32 767 chars.
# On tronque avant pour que l'appel parte quand même (le caller batch ses items).
MAX_PROMPT_CHARS = 28_000


@dataclass(frozen=True)
class BrainAnswer:
    """Réponse du cerveau — ``ok=False`` ⇒ le caller applique son fallback."""

    ok: bool
    data: dict[str, object] | None  # objet JSON parsé (si ok)
    raw: str | None  # texte brut retourné par le modèle (audit / debug)
    engine: BrainEngine
    error: str | None = None


def brain_enabled() -> bool:
    """Le cerveau est-il activé (``OPS_BRAIN_ENABLED``) ?"""
    return get_settings().ops_brain_enabled


def build_brain_argv(prompt: str, *, claude_bin: str = "claude") -> list[str]:
    """Argv one-shot : pas de session, pas d'écriture (``--permission-mode plan``)."""
    return [
        claude_bin,
        "-p",
        prompt,
        "--output-format",
        "json",
        "--permission-mode",
        "plan",
    ]


def parse_cli_payload(stdout: str) -> str:
    """Extrait le texte du modèle de l'enveloppe JSON du CLI.

    ``claude -p --output-format json`` imprime un objet avec un champ
    ``result`` (le texte final du modèle). Raise ``ValueError`` si
    l'enveloppe n'a pas la forme attendue.
    """
    try:
        envelope = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(f"sortie CLI non-JSON : {exc}") from exc
    if not isinstance(envelope, dict) or "result" not in envelope:
        raise ValueError("enveloppe CLI sans champ 'result'")
    return str(envelope["result"])


def extract_json_object(text: str) -> dict[str, object]:
    """Premier objet JSON du texte modèle — même tolérance que le juge.

    Accepte le JSON brut, un bloc ```json …```, ou du texte parasite
    autour du premier ``{ … }`` maximal. Raise ``ValueError`` sinon.
    """
    if not text or not text.strip():
        raise ValueError("réponse modèle vide")
    fence = re.search(r"```(?:json)?\s*\n?(\{.*?\})\s*```", text, re.DOTALL)
    json_str = fence.group(1) if fence else text
    if not fence:
        first, last = json_str.find("{"), json_str.rfind("}")
        if first == -1 or last <= first:
            raise ValueError("aucun objet JSON dans la réponse modèle")
        json_str = json_str[first : last + 1]
    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as exc:
        raise ValueError(f"JSON modèle invalide : {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("la réponse modèle n'est pas un objet JSON")
    return data


def _run_claude_blocking(argv: list[str], timeout_s: int) -> str:
    """Exécute le CLI claude (bloquant — appelé depuis un thread)."""
    # argv construit en interne, jamais de shell=True — pas d'injection possible.
    completed = subprocess.run(
        argv,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=timeout_s,
        cwd=REPO_ROOT,
    )
    if completed.returncode != 0:
        tail = (completed.stderr or completed.stdout or "").strip()[-300:]
        raise RuntimeError(f"claude exit {completed.returncode} : {tail}")
    return completed.stdout


async def think_json(prompt: str, *, timeout_s: int = DEFAULT_TIMEOUT_S) -> BrainAnswer:
    """Pose une question au cerveau et attend un objet JSON en retour.

    Ne raise jamais : tout échec (flag OFF, binaire absent, timeout,
    sortie improbable) retourne ``ok=False`` et le caller retombe sur son
    heuristique. Le prompt doit demander explicitement du JSON strict.
    """
    settings = get_settings()
    if not settings.ops_brain_enabled:
        return BrainAnswer(
            ok=False,
            data=None,
            raw=None,
            engine="disabled",
            error="OPS_BRAIN_ENABLED=false",
        )
    if len(prompt) > MAX_PROMPT_CHARS:
        logger.warning(
            f"brain: prompt {len(prompt)} chars > {MAX_PROMPT_CHARS} — tronqué (batcher côté caller)"
        )
        prompt = prompt[:MAX_PROMPT_CHARS]
    argv = build_brain_argv(prompt, claude_bin=settings.ops_atelier_claude_bin)
    try:
        stdout = await anyio.to_thread.run_sync(_run_claude_blocking, argv, timeout_s)
        raw = parse_cli_payload(stdout)
        data = extract_json_object(raw)
        return BrainAnswer(ok=True, data=data, raw=raw, engine="claude")
    except Exception as exc:  # le cerveau ne doit jamais faire échouer un bot
        logger.warning(f"brain: moteur claude indisponible — fallback heuristique ({exc})")
        return BrainAnswer(
            ok=False,
            data=None,
            raw=None,
            engine="error",
            error=f"{type(exc).__name__}: {exc}",
        )


__all__ = [
    "DEFAULT_TIMEOUT_S",
    "MAX_PROMPT_CHARS",
    "BrainAnswer",
    "BrainEngine",
    "brain_enabled",
    "build_brain_argv",
    "extract_json_object",
    "parse_cli_payload",
    "think_json",
]
