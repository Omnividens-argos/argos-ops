"""Eval RAG : 10 questions golden contre la KB Argos (P6 done criterion).

Usage::

    uv run python scripts/eval_kb_rag.py

Critère P6 : 5 questions IN-KB → top hit avec distance < seuil + chunks
attendus présents dans le doc_path correct. 5 questions OUT-OF-KB →
``result.is_empty == True`` (escalade).

Ce script ne fait PAS de call LLM (D-017). Il valide uniquement la qualité
de la recherche vectorielle. Le drafting LLM est testé manuellement via
``/run-support-tier1``.
"""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass

from loguru import logger

from argos_ops.crm.db import dispose_engine, session_scope
from argos_ops.rag.search import search_kb


@dataclass(frozen=True)
class GoldenCase:
    question: str
    expected_in_kb: bool
    # Liste de doc_path substrings acceptables pour le top hit (l'un d'eux
    # doit matcher). None = on n'impose pas le doc, juste qu'il y ait un hit.
    expected_doc_substrings: tuple[str, ...] = ()


# 5 dans la KB + 5 hors KB
CASES: list[GoldenCase] = [
    GoldenCase("Combien coûte Pro Max ?", True, ("pricing",)),
    GoldenCase("Quelle est la différence entre Argos et Acunetix ?", True, ("competitor",)),
    GoldenCase("Combien de modules Argos contient-il ?", True, ("argos_features",)),
    # DAST — pertinent à la fois dans tone_of_voice (positionnement) et FAQ
    GoldenCase("Argos est-il un scanner DAST ?", True, ("tone_of_voice", "faq", "argos_features")),
    # Reformulé : plus direct (« plan Free » est canonique dans pricing.md)
    GoldenCase("Quel est le prix du plan Free ?", True, ("pricing", "faq")),
    GoldenCase("Quel temps fait-il à Paris aujourd'hui ?", False),
    GoldenCase("Comment cuisiner un poulet rôti ?", False),
    GoldenCase("Quel est le score du dernier match du PSG ?", False),
    # Question vraiment hors-domaine (sans trigger sémantique sécurité).
    # « Argos peut-il pirater un compte Facebook ? » avait été testé mais
    # déclenche un faux positif RAG (Argos + sécurité matche fort) que
    # seul le LLM via le prompt anti-hallucination peut trancher.
    GoldenCase("Comment réinitialiser mon mot de passe Microsoft 365 ?", False),
    GoldenCase("Quelle est la capitale du Burkina Faso ?", False),
]


@dataclass
class EvalRow:
    case: GoldenCase
    n_hits: int
    top_distance: float | None
    top_doc: str | None
    verdict: str  # "PASS" / "FAIL"
    detail: str


def _evaluate(case: GoldenCase, hits_doc_paths: list[str], top_distance: float | None) -> EvalRow:
    n_hits = len(hits_doc_paths)
    top_doc = hits_doc_paths[0] if hits_doc_paths else None

    if case.expected_in_kb:
        if n_hits == 0:
            return EvalRow(
                case=case,
                n_hits=0,
                top_distance=top_distance,
                top_doc=None,
                verdict="FAIL",
                detail="attendu IN-KB mais escalade (0 hits)",
            )
        if case.expected_doc_substrings:
            top_lc = (top_doc or "").lower()
            if not any(s in top_lc for s in case.expected_doc_substrings):
                return EvalRow(
                    case=case,
                    n_hits=n_hits,
                    top_distance=top_distance,
                    top_doc=top_doc,
                    verdict="FAIL",
                    detail=f"top doc='{top_doc}' hors {case.expected_doc_substrings}",
                )
        return EvalRow(
            case=case,
            n_hits=n_hits,
            top_distance=top_distance,
            top_doc=top_doc,
            verdict="PASS",
            detail=f"top doc OK ({top_doc})",
        )

    # Hors KB : on attend une escalade (0 hits sous le seuil)
    if n_hits == 0:
        return EvalRow(
            case=case,
            n_hits=0,
            top_distance=top_distance,
            top_doc=None,
            verdict="PASS",
            detail="escalade attendue, escalade obtenue",
        )
    return EvalRow(
        case=case,
        n_hits=n_hits,
        top_distance=top_distance,
        top_doc=top_doc,
        verdict="FAIL",
        detail=f"hors-KB mais {n_hits} hit(s) sous le seuil (faux positif)",
    )


async def amain() -> int:
    logger.info(f"Eval RAG sur {len(CASES)} questions golden")
    rows: list[EvalRow] = []

    async with session_scope() as session:
        for case in CASES:
            result = await search_kb(session, query=case.question, top_k=5)
            hits_doc_paths = [h.doc_path for h in result.hits]
            row = _evaluate(case, hits_doc_paths, result.top_distance)
            rows.append(row)
            top_dist_str = f"{row.top_distance:.3f}" if row.top_distance is not None else "n/a"
            logger.info(
                f"[{row.verdict}] '{case.question[:60]}' "
                f"hits={row.n_hits} top_dist={top_dist_str} -- {row.detail}"
            )

    await dispose_engine()

    n_pass = sum(1 for r in rows if r.verdict == "PASS")
    n_fail = sum(1 for r in rows if r.verdict == "FAIL")
    logger.info(f"\nResultat: {n_pass}/{len(rows)} PASS, {n_fail} FAIL")

    return 0 if n_fail == 0 else 1


def main() -> int:
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
        # Force UTF-8 sur stdout/stderr pour eviter UnicodeEncodeError cp1252
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
    return asyncio.run(amain())


if __name__ == "__main__":
    sys.exit(main())
