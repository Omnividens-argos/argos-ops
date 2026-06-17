"""Tests du script Veille ``CompetitorWatcherScript`` (archi v2).

Hermétique : mémoire de pôle sous ``tmp_path`` (``poles_root=``), targets et
snapshots injectés (``targets_path=`` / ``snapshot_dir=``). Le réseau est mocké
en monkeypatchant le symbole ``fetch`` du module (jamais de call HTTP réel).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest

from argos_ops.poles import memory
from argos_ops.poles.base import run_script
from argos_ops.poles.veille.scripts.competitor_watcher import (
    CompetitorTarget,
    CompetitorWatcherScript,
    content_hash,
    load_previous_hash,
    load_targets,
    normalize_html,
    save_snapshot_hash,
)

MODULE = "argos_ops.poles.veille.scripts.competitor_watcher"


@dataclass(frozen=True)
class _FakeResponse:
    """Réplique minimale de ``FetchResponse`` (seul ``.body`` est lu)."""

    body: str


def _fake_fetch(body: str):
    async def _fetch(url: str, *, service: str) -> _FakeResponse:
        return _FakeResponse(body=body)

    return _fetch


def _target() -> CompetitorTarget:
    return CompetitorTarget(name="Acme", section="pricing", url="https://acme.test/p")


def _write_targets(path: Path, targets: list[CompetitorTarget]) -> None:
    import yaml

    entries = [{"name": t.name, "section": t.section, "url": t.url} for t in targets]
    path.write_text(yaml.safe_dump({"targets": entries}), encoding="utf-8")


# =============================================================================
# Helpers purs portés du legacy
# =============================================================================
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


def test_snapshot_roundtrip(tmp_path: Path) -> None:
    target = _target()
    save_snapshot_hash(target, hash_="abc123", base_dir=tmp_path)
    assert load_previous_hash(target, base_dir=tmp_path) == "abc123"


def test_load_previous_hash_returns_none_when_missing(tmp_path: Path) -> None:
    assert load_previous_hash(_target(), base_dir=tmp_path) is None


def test_load_previous_hash_returns_none_on_corrupt(tmp_path: Path) -> None:
    from argos_ops.poles.veille.scripts.competitor_watcher import _snapshot_path

    path = _snapshot_path(_target(), tmp_path)
    path.write_text("{not json", encoding="utf-8")
    assert load_previous_hash(_target(), base_dir=tmp_path) is None


# =============================================================================
# run() — mémoire de pôle
# =============================================================================
async def test_run_no_targets_writes_nothing(tmp_path: Path) -> None:
    result = await run_script(
        CompetitorWatcherScript(
            poles_root=tmp_path,
            targets_path=tmp_path / "absent.yaml",
            snapshot_dir=tmp_path / "snaps",
        )
    )
    assert result.status == "success"
    assert result.written == []


async def test_run_first_seen_is_baseline_no_fact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(f"{MODULE}.fetch", _fake_fetch("<p>v1</p>"))
    targets = tmp_path / "targets.yaml"
    snaps = tmp_path / "snaps"
    _write_targets(targets, [_target()])

    result = await run_script(
        CompetitorWatcherScript(poles_root=tmp_path, targets_path=targets, snapshot_dir=snaps)
    )

    # Premier passage = baseline : snapshot persisté, aucun fait.
    assert result.status == "success"
    assert result.written == []
    assert load_previous_hash(_target(), base_dir=snaps) is not None


async def test_run_writes_fact_on_change(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    targets = tmp_path / "targets.yaml"
    snaps = tmp_path / "snaps"
    _write_targets(targets, [_target()])

    # Run 1 : baseline avec contenu v1.
    monkeypatch.setattr(f"{MODULE}.fetch", _fake_fetch("<p>prix 99</p>"))
    await run_script(
        CompetitorWatcherScript(poles_root=tmp_path, targets_path=targets, snapshot_dir=snaps)
    )

    # Run 2 : le contenu a changé -> un fait competitor.
    monkeypatch.setattr(f"{MODULE}.fetch", _fake_fetch("<p>prix 149</p>"))
    result = await run_script(
        CompetitorWatcherScript(poles_root=tmp_path, targets_path=targets, snapshot_dir=snaps)
    )

    assert len(result.written) == 1
    rec = result.written[0]
    assert rec.kind == "competitor"
    assert "competitor" in rec.tags
    assert "pricing" in rec.tags
    assert "Acme" in rec.body
    assert rec.important is False


async def test_run_no_fact_when_unchanged(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    targets = tmp_path / "targets.yaml"
    snaps = tmp_path / "snaps"
    _write_targets(targets, [_target()])
    monkeypatch.setattr(f"{MODULE}.fetch", _fake_fetch("<p>stable</p>"))

    await run_script(
        CompetitorWatcherScript(poles_root=tmp_path, targets_path=targets, snapshot_dir=snaps)
    )
    # Run 2 : contenu identique -> aucun diff, aucun fait.
    result = await run_script(
        CompetitorWatcherScript(poles_root=tmp_path, targets_path=targets, snapshot_dir=snaps)
    )

    assert result.written == []


async def test_run_idempotent_no_duplicate_fact(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    targets = tmp_path / "targets.yaml"
    snaps = tmp_path / "snaps"
    _write_targets(targets, [_target()])

    # Baseline.
    monkeypatch.setattr(f"{MODULE}.fetch", _fake_fetch("<p>v1</p>"))
    await run_script(
        CompetitorWatcherScript(poles_root=tmp_path, targets_path=targets, snapshot_dir=snaps)
    )

    # Deux runs détectant le même état changé : le corps du fait (URL +
    # section) est identique -> un seul fait après dédup par hash. On force
    # le snapshot à un hash bidon avant chaque run pour rejouer le diff.
    for new_body in ("<p>v2</p>", "<p>v2</p>"):
        save_snapshot_hash(_target(), hash_="stale", base_dir=snaps)
        monkeypatch.setattr(f"{MODULE}.fetch", _fake_fetch(new_body))
        await run_script(
            CompetitorWatcherScript(poles_root=tmp_path, targets_path=targets, snapshot_dir=snaps)
        )

    records = await memory.read_memory("veille", "competitor_watcher", poles_root=tmp_path)
    assert len(records) == 1


async def test_run_summary_counts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    targets = tmp_path / "targets.yaml"
    snaps = tmp_path / "snaps"
    two = [
        CompetitorTarget(name="Acme", section="pricing", url="https://acme.test/p"),
        CompetitorTarget(name="Globex", section="features", url="https://globex.test/f"),
    ]
    _write_targets(targets, two)
    monkeypatch.setattr(f"{MODULE}.fetch", _fake_fetch("<p>v1</p>"))

    result = await run_script(
        CompetitorWatcherScript(poles_root=tmp_path, targets_path=targets, snapshot_dir=snaps)
    )
    assert "0/2" in (result.summary or "")


async def test_run_skips_failed_fetch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    targets = tmp_path / "targets.yaml"
    snaps = tmp_path / "snaps"
    _write_targets(targets, [_target()])

    async def _boom(url: str, *, service: str) -> _FakeResponse:
        raise RuntimeError("network down")

    monkeypatch.setattr(f"{MODULE}.fetch", _boom)

    result = await run_script(
        CompetitorWatcherScript(poles_root=tmp_path, targets_path=targets, snapshot_dir=snaps)
    )
    # Le fetch a échoué -> aucun changement, run reste success, rien d'écrit.
    assert result.status == "success"
    assert result.written == []


def test_save_snapshot_uses_iso_timestamp(tmp_path: Path) -> None:
    target = _target()
    save_snapshot_hash(target, hash_="h", base_dir=tmp_path)
    import json

    from argos_ops.poles.veille.scripts.competitor_watcher import _snapshot_path

    payload = json.loads(_snapshot_path(target, tmp_path).read_text(encoding="utf-8"))
    # fetched_at doit être un ISO timestamp parseable.
    datetime.fromisoformat(payload["fetched_at"]).astimezone(UTC)
