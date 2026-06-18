"""Logique **pure** de curation de la mémoire d'un pôle (archi v2, S7).

Aucune I/O, aucun LLM, 100 % testable : à partir de la mémoire d'un pôle (telle
que lue par :func:`argos_ops.poles.memory.read_pole_memory`) et d'une
:class:`~argos_ops.poles.memoire.policy.MemoryPolicy`, produit un
:class:`CurationPlan` = la liste « safe to delete » + la liste des faits
**protégés** (et lesquels auraient été supprimés sans protection).

Invariant non négociable (« vérifie qu'aucun doc *important* n'est
supprimable ») : la **protection est évaluée AVANT** la candidature à la
suppression. Un fait ``important`` (si ``protect_important``) ou matchant un
pattern protégé n'apparaît **jamais** dans ``to_delete``, même périmé/stale —
il est rangé dans ``protected`` avec ``would_delete=True`` pour rendre la
protection visible dans le preview du cockpit.

Deux motifs de suppression (déterministes) :

- **expired** (périmé) : âge > TTL du ``kind`` (cf. ``policy.ttl_for``).
- **stale** : version superseded — au-delà des ``keep_recent_per_kind`` faits
  les plus récents d'un même ``(script, kind)`` ET plus vieux que
  ``min_stale_days`` (filet anti-suppression d'un fait encore frais).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal

from argos_ops.poles.memoire.policy import MemoryPolicy
from argos_ops.poles.memory import MemoryRecord

DeleteReason = Literal["expired", "stale"]
ProtectReason = Literal["important", "pattern"]

_PREVIEW_LEN = 120


def _utcnow() -> datetime:
    return datetime.now(UTC)


def _preview(body: str) -> str:
    flat = " ".join(body.split())
    return flat if len(flat) <= _PREVIEW_LEN else flat[: _PREVIEW_LEN - 1].rstrip() + "…"


def _age_days(created_at: datetime, now: datetime) -> int:
    """Âge en jours (≥ 0). ``created_at`` est aware/UTC (normalisé à la lecture)."""
    delta = now - created_at
    return max(0, delta.days)


@dataclass(frozen=True)
class DeletionCandidate:
    """Un fait jugé **supprimable** (ni important, ni pattern-protégé)."""

    pole: str
    script: str
    record_id: str
    kind: str
    created_at: datetime
    age_days: int
    reason: DeleteReason
    detail: str
    body_preview: str


@dataclass(frozen=True)
class ProtectedFact:
    """Un fait **protégé** ; ``would_delete`` = aurait été supprimé sans la protection."""

    pole: str
    script: str
    record_id: str
    kind: str
    created_at: datetime
    age_days: int
    reason: ProtectReason
    would_delete: bool
    would_delete_reason: DeleteReason | None
    detail: str
    body_preview: str


@dataclass(frozen=True)
class CurationPlan:
    """Plan de curation d'un pôle : candidats à la suppression + protégés."""

    pole: str
    active: bool
    generated_at: datetime
    scanned: int
    to_delete: tuple[DeletionCandidate, ...]
    protected: tuple[ProtectedFact, ...]
    kept: int  # ni candidat ni protégé (jeune / frais / dans la fenêtre récente)

    @property
    def n_delete(self) -> int:
        return len(self.to_delete)

    @property
    def n_protected(self) -> int:
        return len(self.protected)

    @property
    def n_important(self) -> int:
        return sum(1 for p in self.protected if p.reason == "important")

    @property
    def n_saved_from_delete(self) -> int:
        """Protégés qui auraient été supprimés sans la protection (preuve de l'invariant)."""
        return sum(1 for p in self.protected if p.would_delete)


def _deletion_reason(
    record: MemoryRecord,
    *,
    age_days: int,
    rank_in_kind: int,
    policy: MemoryPolicy,
) -> tuple[DeleteReason, str] | None:
    """Motif de suppression d'un fait (ou ``None`` s'il est à conserver).

    ``rank_in_kind`` = position du fait (0 = le plus récent) parmi les faits du
    même ``(script, kind)``, triés du plus récent au plus ancien. ``expired``
    a priorité sur ``stale`` (signal plus explicite : durée de vie dépassée).
    """
    ttl = policy.ttl_for(record.kind)
    if age_days > ttl:
        return "expired", f"âge {age_days} j > TTL {ttl} j (kind « {record.kind} »)"
    if rank_in_kind >= policy.keep_recent_per_kind and age_days >= policy.min_stale_days:
        return (
            "stale",
            f"{policy.keep_recent_per_kind} version(s) plus récente(s) du kind "
            f"« {record.kind} » · âge {age_days} j ≥ {policy.min_stale_days} j",
        )
    return None


def plan_curation(
    records_by_script: dict[str, list[MemoryRecord]],
    policy: MemoryPolicy,
    pole: str,
    *,
    now: datetime | None = None,
) -> CurationPlan:
    """Construit le plan de curation d'un pôle (pur, déterministe).

    Si le pôle n'est pas dans ``policy.active_for`` : plan **inactif** — rien
    n'est supprimable (``to_delete`` vide), tous les faits sont comptés en
    ``kept``. Sinon, chaque fait est classé : protégé (important / pattern),
    candidat (expired / stale) ou conservé — la **protection l'emporte
    toujours** sur la candidature.
    """
    moment = now or _utcnow()
    scanned = sum(len(recs) for recs in records_by_script.values())

    if not policy.is_active(pole):
        return CurationPlan(
            pole=pole,
            active=False,
            generated_at=moment,
            scanned=scanned,
            to_delete=(),
            protected=(),
            kept=scanned,
        )

    to_delete: list[DeletionCandidate] = []
    protected: list[ProtectedFact] = []
    kept = 0

    for script, records in records_by_script.items():
        # Rang par kind : faits du même kind triés du plus récent au plus vieux.
        # Le tiebreaker ``id`` rend l'ordre TOTAL et déterministe quand plusieurs
        # faits partagent le même ``created_at`` (ex. dates nues ``YYYY-MM-DD``
        # normalisées à minuit) — sinon l'ordre du glob filesystem déciderait quel
        # fait est « stale », et le preview pourrait diverger du cleaner (un fait
        # validé refusé à l'exécution). Indispensable à la garantie « déterministe ».
        ordered = sorted(records, key=lambda r: (r.created_at, r.id), reverse=True)
        rank_by_kind: dict[str, int] = {}
        for record in ordered:
            rank = rank_by_kind.get(record.kind, 0)
            rank_by_kind[record.kind] = rank + 1

            age = _age_days(record.created_at, moment)
            del_reason = _deletion_reason(record, age_days=age, rank_in_kind=rank, policy=policy)

            # 1) Protection — évaluée AVANT la candidature (invariant central).
            protect: ProtectReason | None = None
            if policy.protect_important and record.important:
                protect = "important"
            elif policy.is_pattern_protected(
                kind=record.kind, tags=record.tags, source=record.source
            ):
                protect = "pattern"

            if protect is not None:
                detail = (
                    "fait important — jamais supprimable"
                    if protect == "important"
                    else "pattern auto-protégé (kind/tag/source)"
                )
                protected.append(
                    ProtectedFact(
                        pole=pole,
                        script=script,
                        record_id=record.id,
                        kind=record.kind,
                        created_at=record.created_at,
                        age_days=age,
                        reason=protect,
                        would_delete=del_reason is not None,
                        would_delete_reason=(del_reason[0] if del_reason else None),
                        detail=detail,
                        body_preview=_preview(record.body),
                    )
                )
                continue

            # 2) Candidature à la suppression.
            if del_reason is not None:
                reason, detail = del_reason
                to_delete.append(
                    DeletionCandidate(
                        pole=pole,
                        script=script,
                        record_id=record.id,
                        kind=record.kind,
                        created_at=record.created_at,
                        age_days=age,
                        reason=reason,
                        detail=detail,
                        body_preview=_preview(record.body),
                    )
                )
            else:
                kept += 1

    # Tri d'affichage déterministe (tiebreaker id) : suppressions les plus anciennes d'abord.
    to_delete.sort(key=lambda c: (c.created_at, c.record_id))
    protected.sort(key=lambda p: (not p.would_delete, p.created_at, p.record_id))
    return CurationPlan(
        pole=pole,
        active=True,
        generated_at=moment,
        scanned=scanned,
        to_delete=tuple(to_delete),
        protected=tuple(protected),
        kept=kept,
    )


__all__ = [
    "CurationPlan",
    "DeleteReason",
    "DeletionCandidate",
    "ProtectReason",
    "ProtectedFact",
    "plan_curation",
]
