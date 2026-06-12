"""Tests unitaires de :mod:`argos_ops.agents.competitor_watcher` (P22.D).

Couvre :
- ``normalize_html`` : strip tags + collapse whitespace + skip script/style
- ``build_report`` : couleurs + summary
- snapshot I/O round-trip
"""

from __future__ import annotations

from pathlib import Path

import pytest

from argos_ops.agents.competitor_watcher import (
    CompetitorChange,
    CompetitorTarget,
    build_competitor_embed,
    build_report,
    content_hash,
    load_previous_hash,
    load_targets,
    normalize_html,
    save_snapshot_hash,
)
from argos_ops.notifications.discord import GREEN, YELLOW


def _target() -> CompetitorTarget:
    return CompetitorTarget(name="Acme", section="pricing", url="https://acme.test/p")


def _change(*, changed: bool, previous: str | None = "old") -> CompetitorChange:
    return CompetitorChange(
        target=_target(),
        previous_hash=previous,
        current_hash="new" if changed else previous or "new",
        changed=changed,
    )


def test_normalize_html_strips_tags_and_collapses_whitespace() -> None:
    html = "<html><body><p>Hello   world</p></body></html>"
    assert normalize_html(html) == "Hello world"


def test_normalize_html_drops_script_and_style_blocks() -> None:
    html = (
        "<head><style>.x { color: red; }</style></head>"
        "<body>visible<script>console.log('hi')</script> after</body>"
    )
    normalized = normalize_html(html)
    assert "color: red" not in normalized
    assert "console.log" not in normalized
    assert "visible" in normalized
    assert "after" in normalized


def test_normalize_html_handles_multiline_script() -> None:
    html = "<body>A<script>\n var x = 1\n</script>B</body>"
    assert normalize_html(html) == "A B"


def test_content_hash_is_deterministic() -> None:
    a = content_hash("hello")
    b = content_hash("hello")
    c = content_hash("hello world")
    assert a == b
    assert a != c


def test_load_targets_returns_empty_when_missing(tmp_path: Path) -> None:
    assert load_targets(tmp_path / "absent.yaml") == []


def test_load_targets_parses_valid_entries(tmp_path: Path) -> None:
    path = tmp_path / "targets.yaml"
    path.write_text(
        "targets:\n  - name: Acme\n    section: pricing\n    url: https://acme.test/pricing\n",
        encoding="utf-8",
    )
    targets = load_targets(path)
    assert len(targets) == 1
    assert targets[0].name == "Acme"


def test_load_targets_raises_on_malformed(tmp_path: Path) -> None:
    path = tmp_path / "targets.yaml"
    path.write_text("targets:\n  - section: pricing\n", encoding="utf-8")
    with pytest.raises(ValueError, match="mal form"):
        load_targets(path)


def test_build_report_green_when_nothing_changed() -> None:
    report = build_report(
        [_change(changed=False, previous="abc"), _change(changed=False, previous="def")]
    )
    assert report.alert_color == GREEN
    assert report.should_alert is False
    assert "stable" in report.summary


def test_build_report_yellow_when_any_change() -> None:
    report = build_report(
        [_change(changed=True, previous="abc"), _change(changed=False, previous="def")]
    )
    assert report.alert_color == YELLOW
    assert report.should_alert is True


def test_snapshot_roundtrip(tmp_path: Path) -> None:
    target = _target()
    save_snapshot_hash(target, hash_="abc123", base_dir=tmp_path)
    assert load_previous_hash(target, base_dir=tmp_path) == "abc123"


def test_load_previous_hash_returns_none_when_missing(tmp_path: Path) -> None:
    assert load_previous_hash(_target(), base_dir=tmp_path) is None


def test_embed_only_lists_changed_pages() -> None:
    report = build_report(
        [
            _change(changed=True, previous="abc"),
            _change(changed=False, previous="def"),
        ]
    )
    embed = build_competitor_embed(report)
    assert len(embed.fields) == 1
    assert "Acme" in embed.fields[0].name


# =============================================================================
# Mémoire de flotte (Axe 1) — un diff = un fait
# =============================================================================
def test_build_competitor_facts_only_for_changed_pages() -> None:
    from argos_ops.agents.competitor_watcher import (
        CompetitorChange,
        CompetitorTarget,
        build_competitor_facts,
    )

    changed = CompetitorChange(
        target=CompetitorTarget(name="Acunetix", section="pricing", url="https://x/p"),
        previous_hash="a",
        current_hash="b",
        changed=True,
    )
    stable = CompetitorChange(
        target=CompetitorTarget(name="Detectify", section="features", url="https://y/f"),
        previous_hash="c",
        current_hash="c",
        changed=False,
    )
    facts = build_competitor_facts([changed, stable])
    assert len(facts) == 1
    fact = facts[0]
    assert fact["kind"] == "competitor"
    assert "Acunetix" in fact["body"] and "pricing" in fact["body"]
    assert fact["ttl_days"] == 60


def test_build_competitor_facts_capped_at_five() -> None:
    from argos_ops.agents.competitor_watcher import (
        CompetitorChange,
        CompetitorTarget,
        build_competitor_facts,
    )

    changes = [
        CompetitorChange(
            target=CompetitorTarget(name=f"C{i}", section="pricing", url=f"https://c{i}"),
            previous_hash="a",
            current_hash=f"b{i}",
            changed=True,
        )
        for i in range(8)
    ]
    assert len(build_competitor_facts(changes)) == 5
