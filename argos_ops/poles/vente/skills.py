"""Banque de **skills** de l'agent Vente (archi v2, S4).

Dans le modèle archi v2, les anciens skills commerciaux / relation client
(``outbound-personalizer`` / ``demo-followup`` / ``kb-rag`` / ``deal-scoring`` …)
deviennent les **skills** de l'unique ``VenteAgent``, déclarés dans son
``pole.yaml`` (``agent.skills``) et décrits par une fiche markdown
``data/poles/vente/agent/skills/<id>.md``.

Ce module charge et **valide** la banque (parité fiches ↔ ``pole.yaml``, rôle
connu). 100 % fichiers, aucun LLM ici : sous D-017 c'est Claude Code qui *exécute*
le skill ; cette banque ne fait que le déclarer et le cadrer. Miroir de
:mod:`argos_ops.poles.pub.skills` et :mod:`argos_ops.poles.marketing.skills`.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from argos_ops.poles.config import POLES_DIR, load_pole_config
from argos_ops.poles.vente.store import read_markdown

VENTE_POLE = "vente"
SKILLS_SUBPATH = ("agent", "skills")

SkillRole = str  # "outreach" | "lifecycle" | "support" | "scoring"
KNOWN_ROLES: frozenset[str] = frozenset({"outreach", "lifecycle", "support", "scoring"})


@dataclass(frozen=True)
class VenteSkill:
    """Une fiche de skill de la banque de l'agent Vente."""

    id: str
    role: SkillRole
    summary: str
    references: str | None = None  # skill/slash global canonique (.claude/...)
    guardrails: tuple[str, ...] = ()


def skills_dir(*, poles_root: Path = POLES_DIR) -> Path:
    return poles_root.joinpath(VENTE_POLE, *SKILLS_SUBPATH)


def _skill_from_file(path: Path) -> VenteSkill:
    fm, body = read_markdown(path)
    raw_guards = fm.get("guardrails") or []
    guardrails = tuple(str(g) for g in raw_guards) if isinstance(raw_guards, list) else ()
    return VenteSkill(
        id=str(fm.get("id") or path.stem),
        role=str(fm.get("role") or "outreach"),
        summary=body.strip(),
        references=(str(fm["references"]) if fm.get("references") else None),
        guardrails=guardrails,
    )


def load_skill_bank(*, poles_root: Path = POLES_DIR) -> list[VenteSkill]:
    """Charge toutes les fiches de skill (ordre alphabétique d'id). Best-effort."""
    d = skills_dir(poles_root=poles_root)
    if not d.exists():
        return []
    out: list[VenteSkill] = []
    for path in sorted(d.glob("*.md")):
        try:
            out.append(_skill_from_file(path))
        except Exception as exc:  # best-effort
            logger.warning(f"skills — fiche illisible {path} : {type(exc).__name__}: {exc}")
    return out


def validate_skill_bank(*, poles_root: Path = POLES_DIR) -> list[str]:
    """Audite la banque vs ``pole.yaml``. Liste vide ⇒ banque saine.

    Vérifie : chaque skill déclaré dans ``pole.yaml`` a une fiche ; chaque fiche
    correspond à un skill déclaré (pas d'orpheline) ; chaque fiche porte un rôle
    connu.
    """
    cfg = load_pole_config(VENTE_POLE, poles_root=poles_root)
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
    "SkillRole",
    "VenteSkill",
    "load_skill_bank",
    "skills_dir",
    "validate_skill_bank",
]
