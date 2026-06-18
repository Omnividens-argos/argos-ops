"""Tests du DirectionAgent (archi v2, S6) — plan d'oversight borné par le gel publication.

Hermétique : ``pole.yaml`` du pôle Direction (``reads_cross_pole: ["*"]``) + quelques
pôles cross + mémoire seedée sous ``tmp_path`` via
:func:`argos_ops.poles.memory.write_memory`. Strict miroir du style de
``tests/test_finance_agent.py`` (gel = analogue de la conformité Finance / Bloctel Vente).
"""

from __future__ import annotations

from pathlib import Path

from argos_ops.poles import memory
from argos_ops.poles.direction.agent import DirectionAgent

_SKILLS = (
    "release-notes",
    "weekly-synthesis",
    "okr-review",
    "board-pack",
    "decision-log",
    "changelog",
    "roadmap-publish",
    "feedback-arbitrage",
    "bug-triage",
)


def _pole_yaml(root: Path, pole: str, name: str, *, reads: str = "[]", skills: str = "[]") -> None:
    d = root / pole
    d.mkdir(parents=True, exist_ok=True)
    (d / "pole.yaml").write_text(
        f"id: {pole}\nname: {name}\nagent:\n  name: {name}Agent\n  skills: {skills}\n"
        f"scripts: []\nreads_cross_pole: {reads}\nfront_tools: [memory_table]\n",
        encoding="utf-8",
    )


def _direction_yaml(root: Path) -> None:
    skills = "[" + ", ".join(_SKILLS) + "]"
    _pole_yaml(root, "direction", "Direction", reads='["*"]', skills=skills)


def _scaffold_cross_poles(root: Path) -> None:
    """Quelques pôles cross-pôle (leur pole.yaml suffit à list_poles)."""
    _pole_yaml(root, "vente", "Vente")
    _pole_yaml(root, "veille", "Veille")


# =============================================================================
# Cas vide → skipped
# =============================================================================
async def test_agent_skipped_when_no_memory(tmp_path: Path) -> None:
    _direction_yaml(tmp_path)
    _scaffold_cross_poles(tmp_path)
    result = await DirectionAgent(poles_root=tmp_path).run()
    assert result.status == "skipped"


# =============================================================================
# Pôle critique cross-pôle → oversight + gel de publication armé
# =============================================================================
async def test_agent_oversight_and_freezes_publish_on_critical_cross_pole(tmp_path: Path) -> None:
    _direction_yaml(tmp_path)
    _scaffold_cross_poles(tmp_path)
    # Fait cross-pôle CRITIQUE (Vente : gel Bloctel) → pôle rouge.
    await memory.write_memory(
        "vente",
        "bloctel_guard",
        "Gel Bloctel armé — campagne outbound suspendue",
        kind="rc",
        tags=("bloctel", "frozen"),
        important=True,
        poles_root=tmp_path,
    )
    # Fait propre de publication (changelog) → devrait être GELÉ.
    await memory.write_memory(
        "direction",
        "changelog_bot",
        "Changelog v0.6 prêt à publier (3 commits).",
        kind="changelog",
        tags=("publish", "changelog"),
        poles_root=tmp_path,
    )
    result = await DirectionAgent(poles_root=tmp_path).run()
    assert result.status == "success"
    # Cross-pôle lu : vente apparaît dans le résumé.
    assert "vente" in result.summary
    joined = " ".join(result.actions)
    # Action d'oversight sur le pôle critique.
    assert "oversight" in joined and "vente" in joined
    # La publication est gelée par le garde-fou release.
    publish_action = next(a for a in result.actions if "publish" in a)
    assert "[GELÉ publication]" in publish_action
    assert "GELÉE" in result.summary


# =============================================================================
# Bug P0 ouvert → gel de publication armé (même sans pôle rouge)
# =============================================================================
async def test_agent_freezes_publish_on_open_p0(tmp_path: Path) -> None:
    _direction_yaml(tmp_path)
    _scaffold_cross_poles(tmp_path)
    # Snapshot bugs avec un P0 ouvert (mot-clé "vulnérabilité" → P0).
    bugs_path = tmp_path / "direction" / "bugs" / "issues.yaml"
    bugs_path.parent.mkdir(parents=True, exist_ok=True)
    bugs_path.write_text(
        "issues:\n"
        "  - number: 42\n"
        '    title: "Vulnérabilité XSS sur le rapport partagé"\n'
        '    body: "HTML non échappé — XSS stocké."\n'
        "    labels: [bug, security]\n"
        "    opened_at: 2026-06-16\n",
        encoding="utf-8",
    )
    # Fait propre de publication (roadmap) → devrait être GELÉ par le P0.
    await memory.write_memory(
        "direction",
        "roadmap_publisher",
        "Roadmap publique prête à publier (3 services).",
        kind="roadmap",
        tags=("publish", "roadmap"),
        poles_root=tmp_path,
    )
    result = await DirectionAgent(poles_root=tmp_path).run()
    assert result.status == "success"
    publish_action = next(a for a in result.actions if "publish" in a)
    assert "[GELÉ publication]" in publish_action
    assert "GELÉE" in result.summary


# =============================================================================
# Flotte saine (pas de pôle rouge, pas de P0) → publication NON gelée
# =============================================================================
async def test_agent_does_not_freeze_when_healthy(tmp_path: Path) -> None:
    _direction_yaml(tmp_path)
    _scaffold_cross_poles(tmp_path)
    # Fait cross-pôle sain (info) — aucun marqueur critique.
    await memory.write_memory(
        "veille",
        "trend_spotter",
        "5 sujets cyber chauds détectés",
        kind="signal",
        tags=("cyber",),
        poles_root=tmp_path,
    )
    # Fait propre de publication (changelog) — doit rester exécutable.
    await memory.write_memory(
        "direction",
        "changelog_bot",
        "Changelog v0.6 prêt à publier (3 commits).",
        kind="changelog",
        tags=("publish", "changelog"),
        poles_root=tmp_path,
    )
    result = await DirectionAgent(poles_root=tmp_path).run()
    assert result.status == "success"
    joined = " ".join(result.actions)
    assert "publish" in joined
    assert "[GELÉ publication]" not in joined
    assert "GELÉE" not in result.summary


# =============================================================================
# OKR off_track propre + cross-pôle → plan non vide avec critiques
# =============================================================================
async def test_agent_plans_own_okr_and_reads_cross_pole(tmp_path: Path) -> None:
    _direction_yaml(tmp_path)
    _scaffold_cross_poles(tmp_path)
    # Fait propre OKR off_track (critique) + fait cross-pôle Vente.
    await memory.write_memory(
        "direction",
        "okr_tracker",
        "OKR « MRR fin de trimestre » off_track : 3000/10000 EUR (30% vs 85% attendu)",
        kind="okr",
        tags=("okr", "off_track"),
        important=True,
        poles_root=tmp_path,
    )
    await memory.write_memory(
        "vente",
        "proposal_bot",
        "Devis DEAL-1 (Acme) sent",
        kind="proposal",
        tags=("DEAL-1", "sent"),
        poles_root=tmp_path,
    )
    result = await DirectionAgent(poles_root=tmp_path).run()
    assert result.status == "success"
    assert "vente" in result.summary
    joined = " ".join(result.actions)
    assert "okr" in joined
    assert "[critical]" in joined  # l'OKR off_track est critique
