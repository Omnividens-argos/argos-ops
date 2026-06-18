"""Endpoints cockpit du modèle **pôle / agent / script** (archi v2, S1).

Read-mostly, local-first (D-017) : sert au front la mémoire d'un pôle (les faits
écrits par ses scripts) et la **synthèse en insights** du pôle, plus un endpoint
``handoff`` qui enregistre la décision *humaine* de pousser un signal vers un
pôle aval (Marketing / Pub / Vente).

- ``GET  /api/poles``                 — liste des pôles (id, nom, agent).
- ``GET  /api/poles/{pole}/feed``     — faits + insights + facettes de filtrage.
- ``POST /api/poles/{pole}/handoff``  — enregistre un push vers un pôle aval.

Le handoff écrit dans ``data/poles/<pole>/handoffs/`` — c'est-à-dire dans la
donnée **du pôle source** : aucune écriture cross-pôle ici (le câblage qui fera
consommer ce handoff par le pôle cible viendra dans une session ultérieure).
"""

from __future__ import annotations

import contextlib
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from argos_ops.poles.config import POLES_DIR, list_poles, load_all_poles
from argos_ops.poles.memory import MemoryRecord, read_pole_memory
from argos_ops.poles.veille.insights import synthesize_insights

router = APIRouter(prefix="/api/poles", tags=["poles"])

HANDOFFS_DIRNAME = "handoffs"


# =============================================================================
# Schemas
# =============================================================================
class PoleSummary(BaseModel):
    id: str
    name: str
    description: str
    agent: str | None
    scripts: list[str]
    front_tools: list[str]


class MemoryFact(BaseModel):
    id: str
    pole: str
    script: str
    kind: str
    important: bool
    tags: list[str]
    body: str
    source: str | None
    created_at: datetime


class InsightOut(BaseModel):
    kind: str
    title: str
    theme: str
    severity: str
    summary: str
    suggested_poles: list[str]
    record_ids: list[str]
    count: int


class FeedCounts(BaseModel):
    total: int
    important: int
    critical: int


class PoleFeed(BaseModel):
    pole: str
    generated_at: datetime
    records: list[MemoryFact]
    insights: list[InsightOut]
    kinds: list[str]
    themes: list[str]
    scripts: list[str]
    counts: FeedCounts


class HandoffPayload(BaseModel):
    record_id: str
    target_pole: str
    note: str | None = None


class HandoffOut(BaseModel):
    id: str
    pole: str
    record_id: str
    target_pole: str
    note: str | None
    created_at: datetime


# =============================================================================
# Helpers
# =============================================================================
def _fact_of(record: MemoryRecord) -> MemoryFact:
    return MemoryFact(
        id=record.id,
        pole=record.pole,
        script=record.script,
        kind=record.kind,
        important=record.important,
        tags=list(record.tags),
        body=record.body,
        source=record.source,
        created_at=record.created_at,
    )


def _require_pole(pole: str) -> None:
    if pole not in list_poles(include_internal=True):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Pôle inconnu : {pole}")


# =============================================================================
# Routes
# =============================================================================
@router.get("", response_model=list[PoleSummary])
async def get_poles() -> list[PoleSummary]:
    """Liste les 8 pôles (miroir des ``pole.yaml``)."""
    return [
        PoleSummary(
            id=cfg.id,
            name=cfg.name,
            description=cfg.description,
            agent=cfg.agent.name if cfg.agent else None,
            scripts=[s.id for s in cfg.scripts],
            front_tools=list(cfg.front_tools),
        )
        for cfg in load_all_poles()
    ]


@router.get("/{pole}/feed", response_model=PoleFeed)
async def get_pole_feed(pole: str) -> PoleFeed:
    """Mémoire d'un pôle + insights synthétisés + facettes de filtrage."""
    _require_pole(pole)
    by_script = await read_pole_memory(pole)
    records: list[MemoryRecord] = [r for recs in by_script.values() for r in recs]
    records.sort(key=lambda r: r.created_at, reverse=True)

    insights = synthesize_insights(records)
    kinds = sorted({r.kind for r in records})
    themes = sorted({i.theme for i in insights})
    scripts = sorted(by_script.keys())

    return PoleFeed(
        pole=pole,
        generated_at=datetime.now(UTC),
        records=[_fact_of(r) for r in records],
        insights=[
            InsightOut(
                kind=i.kind,
                title=i.title,
                theme=i.theme,
                severity=i.severity,
                summary=i.summary,
                suggested_poles=list(i.suggested_poles),
                record_ids=list(i.record_ids),
                count=i.count,
            )
            for i in insights
        ],
        kinds=kinds,
        themes=themes,
        scripts=scripts,
        counts=FeedCounts(
            total=len(records),
            important=sum(1 for r in records if r.important),
            critical=sum(1 for i in insights if i.severity == "critical"),
        ),
    )


@router.post("/{pole}/handoff", response_model=HandoffOut, status_code=status.HTTP_201_CREATED)
async def post_handoff(pole: str, payload: HandoffPayload) -> HandoffOut:
    """Enregistre une décision humaine de pousser un signal vers un pôle aval.

    Idempotent : (record_id, target_pole, note) → même fichier. N'écrit que dans
    la donnée du pôle source (pas de cross-pôle).
    """
    _require_pole(pole)
    target = payload.target_pole
    if target not in list_poles():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=f"Pôle cible inconnu : {target}"
        )
    if target == pole:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Pôle cible == pôle source"
        )

    note = payload.note or None
    key = f"{payload.record_id}|{target}|{note or ''}"
    handoff_id = hashlib.sha1(key.encode("utf-8")).hexdigest()[:12]
    handoff_dir: Path = POLES_DIR / pole / HANDOFFS_DIRNAME
    handoff_dir.mkdir(parents=True, exist_ok=True)
    path = handoff_dir / f"{handoff_id}.json"

    created_at = datetime.now(UTC)
    if path.exists():
        with contextlib.suppress(json.JSONDecodeError, KeyError, ValueError):
            created_at = datetime.fromisoformat(
                json.loads(path.read_text(encoding="utf-8"))["created_at"]
            )

    out = HandoffOut(
        id=handoff_id,
        pole=pole,
        record_id=payload.record_id,
        target_pole=target,
        note=note,
        created_at=created_at,
    )
    path.write_text(out.model_dump_json(indent=2), encoding="utf-8")
    return out


__all__ = ["router"]
