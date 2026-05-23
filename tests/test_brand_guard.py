"""Tests BrandGuardBot + argos_ops.comm.brand."""

from __future__ import annotations

from pathlib import Path

from argos_ops.agents.brand_guard import (
    BrandReport,
    FileAudit,
    audit_drafts,
    build_brand_embed,
    scan_targets,
)
from argos_ops.comm.brand import BrandIssue, audit_text
from argos_ops.notifications.discord import GREEN, RED, YELLOW


def test_audit_text_detects_dot_com() -> None:
    issues = audit_text("Visitez omnividens.com pour en savoir plus")
    rule_ids = [i.rule_id for i in issues]
    assert "domain_dot_com" in rule_ids


def test_audit_text_detects_ai_validated_by_human() -> None:
    issues = audit_text("Cet email a été validé par humain.")
    rule_ids = [i.rule_id for i in issues]
    assert "ai_validated_by_human" in rule_ids


def test_audit_text_lowercase_brand_silent_if_also_caps() -> None:
    text = "Voir notre site argos. (Argos étant la marque déposée.)"
    issues = audit_text(text)
    rule_ids = [i.rule_id for i in issues]
    assert "argos_lowercase" not in rule_ids


def test_audit_text_lowercase_brand_flagged_if_only_lowercase() -> None:
    issues = audit_text("argos est notre produit")
    rule_ids = [i.rule_id for i in issues]
    assert "argos_lowercase" in rule_ids


def test_audit_text_fud_detection() -> None:
    issues = audit_text("Cette faille est terriblement dangereuse")
    rule_ids = [i.rule_id for i in issues]
    assert "fud_words" in rule_ids


def test_brand_report_colors() -> None:
    clean = BrandReport(audits=[FileAudit(path=Path("x.md"), issues=[])])
    assert clean.color == GREEN
    warn = BrandReport(
        audits=[
            FileAudit(
                path=Path("x.md"),
                issues=[BrandIssue(rule_id="argos_lowercase", severity="warning", message="m")],
            )
        ]
    )
    assert warn.color == YELLOW
    err = BrandReport(
        audits=[
            FileAudit(
                path=Path("x.md"),
                issues=[BrandIssue(rule_id="domain_dot_com", severity="error", message="m")],
            )
        ]
    )
    assert err.color == RED


def test_audit_drafts_handles_missing_files(tmp_path: Path) -> None:
    a = tmp_path / "good.md"
    a.write_text("Argos est notre produit, hébergé sur Omnividens.fr", encoding="utf-8")
    b = tmp_path / "bad.md"
    b.write_text("omnividens.com et validé par humain", encoding="utf-8")
    audits = audit_drafts([a, b])
    assert audits[0].error_count == 0
    assert audits[1].error_count >= 2


def test_scan_targets_returns_empty_for_missing_roots() -> None:
    out = scan_targets((Path("/does/not/exist"),))
    assert out == []


def test_build_brand_embed_includes_stats() -> None:
    report = BrandReport(
        audits=[
            FileAudit(
                path=Path("x.md"),
                issues=[BrandIssue(rule_id="argos_lowercase", severity="warning", message="m")],
            )
        ]
    )
    embed = build_brand_embed(report)
    assert any(f.name == "Warnings" and f.value == "1" for f in embed.fields)
