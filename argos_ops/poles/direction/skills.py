"""Banque de **skills** de l'agent Direction (archi v2, S6).

Les compétences de pilotage (rédaction de release notes, synthèse hebdo, revue
OKR, board pack, journal de décisions, changelog, roadmap, arbitrage produit,
triage de bugs) sont les **skills** de l'unique ``DirectionAgent``, déclarés dans
son ``pole.yaml`` (``agent.skills``) et décrits par une fiche markdown
``data/poles/direction/agent/skills/<id>.md``.

Ce module charge et **valide** la banque (parité fiches ↔ ``pole.yaml``, rôle
connu). 100 % fichiers, aucun LLM ici : sous D-017 c'est Claude Code qui *exécute*
le skill ; cette banque ne fait que le déclarer et le cadrer. Miroir de
:mod:`argos_ops.poles.finance.skills`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from argos_ops.poles.config import POLES_DIR, load_pole_config
from argos_ops.poles.direction.store import read_markdown

DIRECTION_POLE = "direction"
SKILLS_SUBPATH = ("agent", "skills")

SkillRole = str  # "reporting" | "strategy" | "product" | "governance"
KNOWN_ROLES: frozenset[str] = frozenset({"reporting", "strategy", "product", "governance"})


@dataclass(frozen=True)
class DirectionSkill:
    """Une fiche de skill de la banque de l'agent Direction."""

    id: str
    role: SkillRole
    summary: str
    references: str | None = None
    guardrails: tuple[str, ...] = ()


def skills_dir(*, poles_root: Path = POLES_DIR) -> Path:
    return poles_root.joinpath(DIRECTION_POLE, *SKILLS_SUBPATH)


def _skill_from_file(path: Path) -> DirectionSkill:
    fm, body = read_markdown(path)
    raw_guards = fm.get("guardrails") or []
    guardrails = tuple(str(g) for g in raw_guards) if isinstance(raw_guards, list) else ()
    return DirectionSkill(
        id=str(fm.get("id") or path.stem),
        role=str(fm.get("role") or "reporting"),
        summary=body.strip(),
        references=(str(fm["references"]) if fm.get("references") else None),
        guardrails=guardrails,
    )


def load_skill_bank(*, poles_root: Path = POLES_DIR) -> list[DirectionSkill]:
    """Charge toutes les fiches de skill (ordre alphabétique d'id). Best-effort."""
    d = skills_dir(poles_root=poles_root)
    if not d.exists():
        return []
    out: list[DirectionSkill] = []
    for path in sorted(d.glob("*.md")):
        try:
            out.append(_skill_from_file(path))
        except Exception as exc:  # best-effort
            logger.warning(f"skills — fiche illisible {path} : {type(exc).__name__}: {exc}")
    return out


def validate_skill_bank(*, poles_root: Path = POLES_DIR) -> list[str]:
    """Audite la banque vs ``pole.yaml``. Liste vide ⇒ banque saine."""
    cfg = load_pole_config(DIRECTION_POLE, poles_root=poles_root)
    declared = set(cfg.agent.skills) if cfg.agent else set()
    bank = {s.id: s for s in load_skill_bank(poles_root=poles_root)}

    issues: list[str] = []
    for skill_id in sorted(declared):
        if skill_id not in bank:
            issues.append(f"Skill déclaré sans fiche : {skill_id}")
    for skill_id, skill in sorted(bank.items()):
        if skill_id not in declared:
            issues.append(f"Fiche orpheline (pas dans pole.yaml) : {skill_id}")
        if skill.role not in KNOWN_ROLES:
            issues.append(f"Rôle inconnu : {skill_id} (role={skill.role})")
    return issues


__all__ = [
    "KNOWN_ROLES",
    "DirectionSkill",
    "SkillRole",
    "load_skill_bank",
    "skills_dir",
    "validate_skill_bank",
]
