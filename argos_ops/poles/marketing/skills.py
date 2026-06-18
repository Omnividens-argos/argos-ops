"""Banque de **skills** de l'agent Marketing (archi v2, S2).

Dans le modèle archi v2, les anciens *bots* writers (LinkedIn / Mastodon / Meta /
X / Bluesky / Truth, plus SEO brief, newsletter, reply, editorial, brand-check,
KB updater) ne sont **plus des agents** : ce sont des **skills** de l'unique
``MarketingAgent``, déclarés dans son ``pole.yaml`` (``agent.skills``) et décrits
par une fiche markdown ``data/poles/marketing/agent/skills/<id>.md``.

Ce module charge et **valide** la banque (parité fiches ↔ ``pole.yaml``, canal
connu pour les writers). 100 % fichiers, aucun LLM ici : sous D-017 c'est Claude
Code qui *exécute* le skill ; cette banque ne fait que le déclarer et le cadrer.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from loguru import logger

from argos_ops.poles.config import POLES_DIR, load_pole_config
from argos_ops.poles.marketing.channels import is_known_channel
from argos_ops.poles.marketing.store import read_markdown

MARKETING_POLE = "marketing"
SKILLS_SUBPATH = ("agent", "skills")

SkillRole = str  # "writer" | "editorial" | "brand" | "kb" | "support"


@dataclass(frozen=True)
class MarketingSkill:
    """Une fiche de skill de la banque de l'agent Marketing."""

    id: str
    role: SkillRole
    summary: str
    channel: str | None = None
    max_chars: int | None = None
    references: str | None = None  # skill global canonique (.claude/skills/<...>)
    guardrails: tuple[str, ...] = ()


def skills_dir(*, poles_root: Path = POLES_DIR) -> Path:
    return poles_root.joinpath(MARKETING_POLE, *SKILLS_SUBPATH)


def _skill_from_file(path: Path) -> MarketingSkill:
    fm, body = read_markdown(path)
    raw_guards = fm.get("guardrails") or []
    guardrails = tuple(str(g) for g in raw_guards) if isinstance(raw_guards, list) else ()
    raw_max = fm.get("max_chars")
    max_chars = int(raw_max) if isinstance(raw_max, int) else None
    return MarketingSkill(
        id=str(fm.get("id") or path.stem),
        role=str(fm.get("role") or "writer"),
        summary=body.strip(),
        channel=(str(fm["channel"]) if fm.get("channel") else None),
        max_chars=max_chars,
        references=(str(fm["references"]) if fm.get("references") else None),
        guardrails=guardrails,
    )


def load_skill_bank(*, poles_root: Path = POLES_DIR) -> list[MarketingSkill]:
    """Charge toutes les fiches de skill (ordre alphabétique d'id). Best-effort."""
    d = skills_dir(poles_root=poles_root)
    if not d.exists():
        return []
    out: list[MarketingSkill] = []
    for path in sorted(d.glob("*.md")):
        try:
            out.append(_skill_from_file(path))
        except Exception as exc:  # best-effort
            logger.warning(f"skills — fiche illisible {path} : {type(exc).__name__}: {exc}")
    return out


def validate_skill_bank(*, poles_root: Path = POLES_DIR) -> list[str]:
    """Audite la banque vs ``pole.yaml``. Liste vide ⇒ banque saine.

    Vérifie : chaque skill déclaré dans ``pole.yaml`` a une fiche ; chaque fiche
    correspond à un skill déclaré (pas d'orpheline) ; un skill ``role=writer``
    pointe vers un canal connu.
    """
    cfg = load_pole_config(MARKETING_POLE, poles_root=poles_root)
    declared = set(cfg.agent.skills) if cfg.agent else set()
    bank = {s.id: s for s in load_skill_bank(poles_root=poles_root)}

    issues: list[str] = []
    for skill_id in sorted(declared):
        if skill_id not in bank:
            issues.append(f"Skill déclaré sans fiche : {skill_id}")
    for skill_id, skill in sorted(bank.items()):
        if skill_id not in declared:
            issues.append(f"Fiche orpheline (pas dans pole.yaml) : {skill_id}")
        if skill.role == "writer" and (
            skill.channel is None or not is_known_channel(skill.channel)
        ):
            issues.append(f"Writer sans canal connu : {skill_id} (channel={skill.channel})")
    return issues


__all__ = [
    "MarketingSkill",
    "SkillRole",
    "load_skill_bank",
    "skills_dir",
    "validate_skill_bank",
]
