"""Endpoints cockpit du pôle **Direction** (archi v2, S6).

Sert au shell ``poles.html`` tout l'onglet Direction, 100 % fichiers / local-first
(D-017) — tout est recalculé à chaud depuis la mémoire des pôles + les snapshots
``data/poles/direction/…`` :

- ``GET  /api/poles/direction/overview``        — vue d'ensemble flotte (santé par
  pôle), synthèse de la semaine, plan d'oversight, OKR vs prorata, board pack,
  journal des décisions, changelog, roadmap publique, feedback, triage des bugs,
  docs générés, état du garde-fou publication, compteurs.
- ``GET  /api/poles/direction/docs/{name}``     — contenu markdown d'un doc (preview).
- ``POST /api/poles/direction/docs/generate``   — génère board / roadmap / changelog
  / release_notes (409 si la publication est gelée — « Python tranche »).
- ``POST /api/poles/direction/board/export``    — génère + renvoie le board pack markdown.
- ``POST /api/poles/direction/decisions``       — append une décision au journal local.
- ``PUT  /api/poles/direction/okr``             — met à jour l'``actual`` d'un key result.

``POLES_DIR`` est un global de module → patchable en test.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Literal

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import FileResponse
from pydantic import BaseModel

from argos_ops.poles.config import POLES_DIR
from argos_ops.poles.direction import (
    board,
    bugs,
    changelog,
    decisions,
    docs,
    feedback,
    okr,
    release,
    roadmap,
)
from argos_ops.poles.direction.agent import DirectionAgent
from argos_ops.poles.direction.fleet import build_fleet_snapshot
from argos_ops.poles.direction.plan import PUBLISHABLE_KINDS, plan_actions
from argos_ops.poles.direction.synthesis import build_synthesis

router = APIRouter(prefix="/api/poles/direction", tags=["poles", "direction"])


def _f(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None


# =============================================================================
# Schemas — sortie
# =============================================================================
class PoleHealthOut(BaseModel):
    pole: str
    name: str
    n_facts: int
    n_important: int
    n_critical: int
    n_warning: int
    last_activity: datetime | None
    health: str
    headline: str | None
    scripts: list[str]


class FleetOut(BaseModel):
    generated_at: datetime
    poles: list[PoleHealthOut]
    total_facts: int
    total_important: int
    total_critical: int
    poles_red: int
    poles_yellow: int
    poles_active: int
    worst_health: str


class SynthesisOut(BaseModel):
    headline: str
    narrative: str
    highlights: list[str]
    risks: list[str]


class KeyResultOut(BaseModel):
    objective: str
    name: str
    target: float
    actual: float
    unit: str
    status: str
    progress_pct: float
    expected_pct: float


class OkrOut(BaseModel):
    quarter: str
    summary: str
    should_alert: bool
    key_results: list[KeyResultOut]


class BoardOut(BaseModel):
    period: str
    mrr_eur: float
    arr_eur: float
    burn_eur: float | None
    runway_months: float | None
    nrr_pct: float | None
    runs_month: int
    breakers_tripped: int
    incidents_month: int


class PlanOut(BaseModel):
    severity: str
    kind: str
    action: str
    detail: str
    pole: str
    suppressed_by_release: bool


class DecisionOut(BaseModel):
    decision_id: str
    title: str
    decision_date: str
    partie: str
    decision: str


class DecisionWithStatus(BaseModel):
    """Décision du journal + statut de cycle de vie (sidecar additif).

    Reprend tels quels les champs de :class:`DecisionOut` et ajoute ``status``
    (``open`` par défaut, ``closed`` si la décision est marquée close dans le
    sidecar ``decision_status.yaml``).
    """

    decision_id: str
    title: str
    decision_date: str
    partie: str
    decision: str
    status: Literal["open", "closed"]


class SectionCount(BaseModel):
    type: str
    count: int


class ChangelogOut(BaseModel):
    period_label: str
    n_commits: int
    n_sections: int
    section_counts: list[SectionCount]
    markdown: str


class RoadmapOut(BaseModel):
    entries_total: int
    done: int
    partial: int
    roadmap: int
    services: int
    markdown: str


class FeedbackThemeOut(BaseModel):
    topic: str
    count: int
    sources: list[str]
    customers: list[str]


class FeedbackOut(BaseModel):
    items_total: int
    themes: list[FeedbackThemeOut]


class TriagedIssueOut(BaseModel):
    number: int
    title: str
    severity: str
    suggested_label: str
    reason: str


class BugsOut(BaseModel):
    issues_total: int
    p0: int
    p1: int
    p2: int
    triaged: list[TriagedIssueOut]


class DocOut(BaseModel):
    name: str
    kind: str
    has_pdf: bool


class DirectionCounts(BaseModel):
    poles_active: int
    poles_red: int
    fleet_critical: int
    okr_off_track: int
    okr_at_risk: int
    bugs_p0: int
    feedback_recurring: int
    decisions: int
    actions_planned: int
    actions_critical: int
    release_blocking: bool


class DirectionOverview(BaseModel):
    pole: str
    generated_at: datetime
    fleet: FleetOut
    synthesis: SynthesisOut
    okr: OkrOut
    board: BoardOut
    plan: list[PlanOut]
    decisions: list[DecisionOut]
    changelog: ChangelogOut
    roadmap: RoadmapOut
    feedback: FeedbackOut
    bugs: BugsOut
    docs: list[DocOut]
    release_blocking: bool
    release_reason: str
    counts: DirectionCounts


# =============================================================================
# Schemas — entrée
# =============================================================================
class GenerateDocPayload(BaseModel):
    kind: str  # board | roadmap | changelog | release_notes


class DecisionPayload(BaseModel):
    title: str
    partie: str = "direction"
    decision: str
    pourquoi: str
    implication_technique: str | None = None
    annule: str | None = None
    action_de_suivi: str | None = None


class DecisionStatusPayload(BaseModel):
    status: Literal["open", "closed"]


class OkrUpdatePayload(BaseModel):
    objective: str
    name: str
    actual: float


class DocGenResult(BaseModel):
    name: str
    kind: str
    has_pdf: bool


class ExportResult(BaseModel):
    path: str
    markdown: str


class DocContent(BaseModel):
    name: str
    content: str


# =============================================================================
# Helpers de mapping
# =============================================================================
def _okr_out(report: okr.OKRReport) -> OkrOut:
    return OkrOut(
        quarter=report.quarter,
        summary=report.summary,
        should_alert=report.should_alert,
        key_results=[
            KeyResultOut(
                objective=k.objective,
                name=k.name,
                target=k.target,
                actual=k.actual,
                unit=k.unit,
                status=k.status,
                progress_pct=k.progress_pct,
                expected_pct=k.expected_pct,
            )
            for k in report.key_results
        ],
    )


def _decision_with_status(entry: decisions.DecisionEntry, statuses: dict[str, str]) -> DecisionWithStatus:
    raw = statuses.get(entry.decision_id, decisions.DEFAULT_DECISION_STATUS)
    out_status: Literal["open", "closed"] = "closed" if raw == "closed" else "open"
    return DecisionWithStatus(
        decision_id=entry.decision_id,
        title=entry.title,
        decision_date=entry.decision_date,
        partie=entry.partie,
        decision=entry.decision,
        status=out_status,
    )


def _board_out(metrics: board.BoardMetrics) -> BoardOut:
    return BoardOut(
        period=metrics.period,
        mrr_eur=float(metrics.mrr_eur),
        arr_eur=float(metrics.arr_eur),
        burn_eur=_f(metrics.burn_eur),
        runway_months=metrics.runway_months,
        nrr_pct=metrics.nrr_pct,
        runs_month=metrics.runs_month,
        breakers_tripped=metrics.breakers_tripped,
        incidents_month=metrics.incidents_month,
    )


# =============================================================================
# Route — lecture
# =============================================================================
@router.get("/overview", response_model=DirectionOverview)
async def get_overview() -> DirectionOverview:
    """Tout ce dont l'onglet Direction a besoin en un seul fetch."""
    today = date.today()
    snapshot = await build_fleet_snapshot(poles_root=POLES_DIR)
    gate = release.evaluate(snapshot, bugs.open_p0(poles_root=POLES_DIR))

    okr_report = okr.load_current(poles_root=POLES_DIR, today=today)
    synth = build_synthesis(snapshot, okr_report, gate)
    board_metrics = board.build_metrics(snapshot, poles_root=POLES_DIR, today=today)
    decision_entries = decisions.load_decisions(poles_root=POLES_DIR)
    changelog_view = changelog.build_changelog(poles_root=POLES_DIR)
    roadmap_view = roadmap.build_roadmap(poles_root=POLES_DIR)
    feedback_report = feedback.build_report(poles_root=POLES_DIR)
    recurring = {t.topic for t in feedback.recurring_themes(poles_root=POLES_DIR)}
    bug_stats = bugs.triage(poles_root=POLES_DIR)
    doc_items = docs.list_docs(poles_root=POLES_DIR)

    # Plan d'oversight : récupéré via le contexte de l'agent (own + cross-pôle "*").
    context = await DirectionAgent(poles_root=POLES_DIR).load_context()
    plans = plan_actions(context.all_records(), release_blocking=gate.blocking)

    counts = DirectionCounts(
        poles_active=snapshot.poles_active,
        poles_red=snapshot.poles_red,
        fleet_critical=snapshot.total_critical,
        okr_off_track=sum(1 for k in okr_report.key_results if k.status == "off_track"),
        okr_at_risk=sum(1 for k in okr_report.key_results if k.status == "at_risk"),
        bugs_p0=bug_stats.p0,
        feedback_recurring=len(recurring),
        decisions=len(decision_entries),
        actions_planned=len(plans),
        actions_critical=sum(1 for p in plans if p.severity == "critical"),
        release_blocking=gate.blocking,
    )

    return DirectionOverview(
        pole="direction",
        generated_at=datetime.now(UTC),
        fleet=FleetOut(
            generated_at=snapshot.generated_at,
            poles=[
                PoleHealthOut(
                    pole=p.pole,
                    name=p.name,
                    n_facts=p.n_facts,
                    n_important=p.n_important,
                    n_critical=p.n_critical,
                    n_warning=p.n_warning,
                    last_activity=p.last_activity,
                    health=p.health,
                    headline=p.headline,
                    scripts=list(p.scripts),
                )
                for p in snapshot.poles
            ],
            total_facts=snapshot.total_facts,
            total_important=snapshot.total_important,
            total_critical=snapshot.total_critical,
            poles_red=snapshot.poles_red,
            poles_yellow=snapshot.poles_yellow,
            poles_active=snapshot.poles_active,
            worst_health=snapshot.worst_health,
        ),
        synthesis=SynthesisOut(
            headline=synth.headline,
            narrative=synth.narrative,
            highlights=list(synth.highlights),
            risks=list(synth.risks),
        ),
        okr=_okr_out(okr_report),
        board=_board_out(board_metrics),
        plan=[
            PlanOut(
                severity=p.severity,
                kind=p.kind,
                action=p.action,
                detail=p.detail,
                pole=p.pole,
                suppressed_by_release=p.suppressed_by_release,
            )
            for p in plans
        ],
        decisions=[
            DecisionOut(
                decision_id=d.decision_id,
                title=d.title,
                decision_date=d.decision_date,
                partie=d.partie,
                decision=d.decision,
            )
            for d in decision_entries
        ],
        changelog=ChangelogOut(
            period_label=changelog_view.period_label,
            n_commits=changelog_view.n_commits,
            n_sections=changelog_view.n_sections,
            section_counts=[
                SectionCount(type=t, count=c) for t, c in changelog_view.section_counts
            ],
            markdown=changelog_view.markdown,
        ),
        roadmap=RoadmapOut(
            entries_total=roadmap_view.entries_total,
            done=roadmap_view.done,
            partial=roadmap_view.partial,
            roadmap=roadmap_view.roadmap,
            services=roadmap_view.services,
            markdown=roadmap_view.markdown,
        ),
        feedback=FeedbackOut(
            items_total=feedback_report.items_total,
            themes=[
                FeedbackThemeOut(
                    topic=t.topic, count=t.count, sources=t.sources, customers=t.customers
                )
                for t in feedback_report.themes
            ],
        ),
        bugs=BugsOut(
            issues_total=bug_stats.issues_total,
            p0=bug_stats.p0,
            p1=bug_stats.p1,
            p2=bug_stats.p2,
            triaged=[
                TriagedIssueOut(
                    number=t.number,
                    title=t.title,
                    severity=t.severity,
                    suggested_label=t.suggested_label,
                    reason=t.reason,
                )
                for t in bug_stats.triaged
            ],
        ),
        docs=[DocOut(name=d.name, kind=d.kind, has_pdf=d.has_pdf) for d in doc_items],
        release_blocking=gate.blocking,
        release_reason=gate.reason,
        counts=counts,
    )


@router.get("/docs/{name}", response_model=DocContent)
async def get_doc(name: str) -> DocContent:
    """Contenu markdown d'un document généré (preview cockpit)."""
    content = docs.read_doc(name, poles_root=POLES_DIR)
    if content is None:
        raise HTTPException(status_code=404, detail=f"Document introuvable : {name}")
    return DocContent(name=name, content=content)


@router.get("/docs/{name}/pdf")
async def get_doc_pdf(name: str) -> FileResponse:
    """Sert le PDF rendu d'un document généré (binaire, téléchargement)."""
    path = docs.resolve_pdf(name, poles_root=POLES_DIR)
    if path is None:
        raise HTTPException(status_code=404, detail=f"PDF introuvable : {name}")
    return FileResponse(path, media_type="application/pdf", filename=path.name)


@router.get("/decisions", response_model=list[DecisionWithStatus])
async def list_decisions() -> list[DecisionWithStatus]:
    """Journal des décisions enrichi du statut de cycle de vie (sidecar additif).

    ``status`` vaut ``open`` par défaut (aucune entrée sidecar) ou ``closed`` si
    la décision a été marquée close via le PATCH.
    """
    entries = decisions.load_decisions(poles_root=POLES_DIR)
    statuses = decisions.load_statuses(poles_root=POLES_DIR)
    return [_decision_with_status(e, statuses) for e in entries]


# =============================================================================
# Routes — mutations
# =============================================================================
async def _ensure_publishable(kind: str) -> None:
    """Garde-fou « Python tranche » : refuse 409 si la publication est gelée.

    Évalue le garde-fou **une seule fois** (un seul scan flotte) — ``ReleaseGate``
    porte à la fois ``blocking`` et ``reason``.
    """
    if kind not in PUBLISHABLE_KINDS:
        return
    gate = await release.gate(poles_root=POLES_DIR)
    if gate.blocking:
        raise HTTPException(
            status_code=409,
            detail=f"Publication gelée (bug P0 ouvert ou pôle critique) — {gate.reason}",
        )


@router.post("/docs/generate", response_model=DocGenResult)
async def generate_doc(payload: GenerateDocPayload) -> DocGenResult:
    """Génère un document. Les artefacts **publics** sont gelés si le garde-fou est armé."""
    kind = payload.kind
    await _ensure_publishable(kind)
    if kind == "board":
        snapshot = await build_fleet_snapshot(poles_root=POLES_DIR)
        path = docs.generate_board(snapshot, poles_root=POLES_DIR)
    elif kind == "roadmap":
        path = docs.generate_roadmap(poles_root=POLES_DIR)
    elif kind == "changelog":
        path = docs.generate_changelog(poles_root=POLES_DIR)
    elif kind == "release_notes":
        path = docs.generate_release_notes(poles_root=POLES_DIR)
    else:
        raise HTTPException(status_code=422, detail=f"Type de doc inconnu : {kind}")
    return DocGenResult(name=path.name, kind=kind, has_pdf=path.with_suffix(".pdf").exists())


@router.post("/board/export", response_model=ExportResult)
async def export_board() -> ExportResult:
    """Génère le board pack et renvoie son markdown (téléchargement)."""
    snapshot = await build_fleet_snapshot(poles_root=POLES_DIR)
    path = docs.generate_board(snapshot, poles_root=POLES_DIR)
    return ExportResult(path=path.name, markdown=path.read_text(encoding="utf-8"))


@router.post("/decisions", response_model=DecisionOut, status_code=status.HTTP_201_CREATED)
async def add_decision(payload: DecisionPayload) -> DecisionOut:
    """Append une décision structurante au journal local (idempotent par titre)."""
    if not payload.title.strip() or not payload.decision.strip():
        raise HTTPException(status_code=422, detail="Titre et décision requis.")
    draft = decisions.DecisionDraft(
        title=payload.title.strip(),
        partie=payload.partie.strip() or "direction",
        decision=payload.decision.strip(),
        pourquoi=payload.pourquoi.strip(),
        implication_technique=payload.implication_technique,
        annule=payload.annule,
        action_de_suivi=payload.action_de_suivi,
    )
    result = decisions.log_decision(draft, poles_root=POLES_DIR)
    entry = next(
        (
            e
            for e in decisions.load_decisions(poles_root=POLES_DIR)
            if e.decision_id == result.decision_id
        ),
        None,
    )
    if entry is None:
        raise HTTPException(
            status_code=500, detail="Décision écrite mais introuvable au relecture."
        )
    return DecisionOut(
        decision_id=entry.decision_id,
        title=entry.title,
        decision_date=entry.decision_date,
        partie=entry.partie,
        decision=entry.decision,
    )


@router.patch("/decisions/{decision_id}", response_model=DecisionWithStatus)
async def set_decision_status(
    decision_id: str, payload: DecisionStatusPayload
) -> DecisionWithStatus:
    """Marque une décision ``open`` / ``closed`` dans le sidecar additif.

    404 si l'``decision_id`` est inconnu du journal (il doit exister dans
    ``load_decisions``). Le statut invalide est rejeté en 422 par Pydantic.
    """
    entries = decisions.load_decisions(poles_root=POLES_DIR)
    entry = next((e for e in entries if e.decision_id == decision_id), None)
    if entry is None:
        raise HTTPException(status_code=404, detail=f"Décision introuvable : {decision_id}")
    statuses = decisions.set_status(decision_id, payload.status, poles_root=POLES_DIR)
    return _decision_with_status(entry, statuses)


@router.put("/okr", response_model=OkrOut)
async def update_okr(payload: OkrUpdatePayload) -> OkrOut:
    """Met à jour la valeur ``actual`` d'un key result. 404 si introuvable."""
    report = okr.set_actual(payload.objective, payload.name, payload.actual, poles_root=POLES_DIR)
    if report is None:
        raise HTTPException(
            status_code=404,
            detail=f"Key result introuvable : « {payload.name} » (objectif « {payload.objective} »)",
        )
    return _okr_out(report)


__all__ = ["router"]
