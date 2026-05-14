"""Tests unitaires du module ``argos_ops.judge`` (P14).

Couvrent :
- la validation des scores ([0, 100]) à la construction de ``JudgeReport``
- le parsing robuste de la sortie LLM (JSON brut, fenced markdown, texte
  parasite avant/après)
- les règles déterministes ``apply_thresholds`` selon ESCALATION_RULES.md

Le call réel à Claude Code (skill ``claude-judge``) est testé en
intégration via les fixtures ``data/judge/fixtures/`` — à exécuter
manuellement le temps qu'un ``scripts/eval_judge.py`` arrive en P14.1.
"""

from __future__ import annotations

import pytest

from argos_ops.judge import (
    AUTO_SEND_FACTUAL_MIN,
    AUTO_SEND_GLOBAL_MIN,
    AUTO_SEND_LEGAL_MIN,
    FACTUAL_KILL_FLOOR,
    LEGAL_KILL_FLOOR,
    QUEUED_GLOBAL_MIN,
    JudgeReport,
    apply_thresholds,
    parse_judge_json,
)


# =============================================================================
# JudgeReport — validation
# =============================================================================
def _make_report(
    *,
    factual: int = 90,
    tone: int = 90,
    legal: int = 90,
    global_score: int = 90,
    rationale: str = "ok",
) -> JudgeReport:
    return JudgeReport(
        factual_score=factual,
        tone_score=tone,
        legal_score=legal,
        global_score=global_score,
        rationale=rationale,
    )


def test_report_accepts_scores_in_range() -> None:
    report = _make_report()
    assert report.global_score == 90


@pytest.mark.parametrize("bad", [-1, 101, 999])
def test_report_rejects_factual_score_out_of_range(bad: int) -> None:
    with pytest.raises(ValueError, match="factual_score"):
        _make_report(factual=bad)


@pytest.mark.parametrize("bad", [-1, 101])
def test_report_rejects_legal_score_out_of_range(bad: int) -> None:
    with pytest.raises(ValueError, match="legal_score"):
        _make_report(legal=bad)


def test_report_is_frozen() -> None:
    """Garantit qu'un caller en aval ne peut pas muter le verdict après coup."""
    report = _make_report()
    with pytest.raises((AttributeError, Exception)):
        report.global_score = 0  # type: ignore[misc]


# =============================================================================
# parse_judge_json — formats acceptés
# =============================================================================
_VALID_JSON_BODY = """\
{
  "factual_score": 92,
  "tone_score": 88,
  "legal_score": 95,
  "global_score": 92,
  "rationale": "Sourcé KB, ton ok, conformité ok.",
  "factual_issues": [],
  "tone_issues": [],
  "legal_issues": []
}
"""


def test_parse_accepts_plain_json() -> None:
    report = parse_judge_json(_VALID_JSON_BODY)
    assert report.global_score == 92
    assert report.factual_issues == []


def test_parse_accepts_fenced_markdown_json() -> None:
    fenced = f"Voici l'analyse du draft :\n\n```json\n{_VALID_JSON_BODY}\n```\n\nFin."
    report = parse_judge_json(fenced)
    assert report.global_score == 92


def test_parse_accepts_fenced_without_lang_marker() -> None:
    fenced = f"```\n{_VALID_JSON_BODY}\n```"
    report = parse_judge_json(fenced)
    assert report.tone_score == 88


def test_parse_accepts_text_around_raw_json() -> None:
    """Le juge oublie parfois la fence — on doit récupérer le 1er bloc {}."""
    noisy = f"Préambule.\n{_VALID_JSON_BODY}\nÉpilogue."
    report = parse_judge_json(noisy)
    assert report.legal_score == 95


def test_parse_rejects_empty() -> None:
    with pytest.raises(ValueError, match="vide"):
        parse_judge_json("")


def test_parse_rejects_missing_field() -> None:
    invalid = """\
{
  "factual_score": 90,
  "tone_score": 90,
  "legal_score": 90,
  "rationale": "manque global"
}
"""
    with pytest.raises(ValueError, match="manquants"):
        parse_judge_json(invalid)


def test_parse_rejects_non_json_blob() -> None:
    with pytest.raises(ValueError, match="JSON"):
        parse_judge_json("Juste de la prose, pas de JSON ici.")


def test_parse_rejects_malformed_json() -> None:
    with pytest.raises(ValueError, match="JSON invalide"):
        parse_judge_json('{"factual_score": 90, "tone_score":, "legal_score": 90}')


def test_parse_propagates_score_validation() -> None:
    """Un score hors [0, 100] dans le JSON doit faire échouer la construction."""
    invalid = """\
{
  "factual_score": 150,
  "tone_score": 90,
  "legal_score": 90,
  "global_score": 90,
  "rationale": "bug"
}
"""
    with pytest.raises(ValueError, match="factual_score"):
        parse_judge_json(invalid)


# =============================================================================
# apply_thresholds — ESCALATION_RULES.md
# =============================================================================
def test_auto_send_when_all_thresholds_met() -> None:
    report = _make_report(
        factual=AUTO_SEND_FACTUAL_MIN,
        tone=70,
        legal=AUTO_SEND_LEGAL_MIN,
        global_score=AUTO_SEND_GLOBAL_MIN,
    )
    assert apply_thresholds(report) == "auto_send"


def test_killed_when_factual_under_floor() -> None:
    report = _make_report(factual=FACTUAL_KILL_FLOOR - 1, global_score=70)
    assert apply_thresholds(report) == "killed"


def test_killed_when_legal_under_floor() -> None:
    report = _make_report(legal=LEGAL_KILL_FLOOR - 1, global_score=80)
    assert apply_thresholds(report) == "killed"


def test_killed_when_global_under_queued_min() -> None:
    report = _make_report(global_score=QUEUED_GLOBAL_MIN - 1)
    assert apply_thresholds(report) == "killed"


def test_queued_when_legal_below_auto_but_above_kill_floor() -> None:
    """Le seuil legal pour auto_send est 90 ; entre 50 et 89 → queued, pas killed."""
    report = _make_report(legal=85, global_score=82, factual=85)
    assert apply_thresholds(report) == "queued"


def test_queued_when_global_in_middle_band() -> None:
    report = _make_report(global_score=70, factual=80, legal=95)
    assert apply_thresholds(report) == "queued"


def test_queued_when_factual_below_auto_but_above_kill_floor() -> None:
    """Factual 50-69 → queued (ni auto ni kill)."""
    report = _make_report(factual=65, global_score=78, legal=95)
    assert apply_thresholds(report) == "queued"


def test_kill_priority_factual_over_other_high_scores() -> None:
    """Même si tone et legal sont à 100, factual=10 → killed."""
    report = _make_report(factual=10, tone=100, legal=100, global_score=90)
    assert apply_thresholds(report) == "killed"


@pytest.mark.parametrize(
    ("factual", "tone", "legal", "global_score", "expected"),
    [
        (95, 95, 95, 95, "auto_send"),
        (70, 50, 90, 80, "auto_send"),  # boundary inférieur exact
        (69, 90, 95, 80, "queued"),  # factual juste sous 70 (mais > 50) → queued
        (80, 90, 89, 80, "queued"),  # legal 89 < 90 mais > 50 → queued
        (49, 90, 90, 80, "killed"),  # factual sous 50 → killed
        (90, 90, 49, 80, "killed"),  # legal sous 50 → killed
        (90, 90, 90, 49, "killed"),  # global sous 50 → killed
    ],
)
def test_thresholds_boundary_table(
    factual: int,
    tone: int,
    legal: int,
    global_score: int,
    expected: str,
) -> None:
    report = _make_report(
        factual=factual,
        tone=tone,
        legal=legal,
        global_score=global_score,
    )
    assert apply_thresholds(report) == expected
