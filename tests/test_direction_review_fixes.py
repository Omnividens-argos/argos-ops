"""Régressions S6 — corrige les findings de la revue adversariale du pôle Direction.

Verrouille trois corrections de robustesse / cohérence :
- OKR illisible (montant « 10 000 » avec espace) → dégradé, pas de crash de tout
  l'overview (finding #2) ;
- board pack archi v2 : libellés flotte corrects, pas la sémantique DB legacy
  (« Agent runs » / « Circuit breakers tripped ») (finding #3) ;
- ``created_at`` naïf / date nue dans la mémoire d'un pôle → tri robuste, le
  snapshot transversal ne tombe pas (finding #4).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from argos_ops.poles import memory
from argos_ops.poles.direction import board, okr
from argos_ops.poles.direction.fleet import build_fleet_snapshot


def _pole_yaml(root: Path, pole: str) -> None:
    d = root / pole
    d.mkdir(parents=True, exist_ok=True)
    (d / "pole.yaml").write_text(
        f"id: {pole}\nname: {pole.title()}\nagent: null\nscripts: []\n"
        "reads_cross_pole: []\nfront_tools: []\n",
        encoding="utf-8",
    )


# =============================================================================
# Finding #2 — OKR illisible ne doit pas faire tomber l'overview
# =============================================================================
def test_okr_load_current_resilient_to_french_thousands(tmp_path: Path) -> None:
    today = okr.date.today()
    n = (today.month - 1) // 3 + 1
    path = tmp_path / "direction" / "okr" / f"{today.year}-Q{n}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    # Montant saisi « à la française » (espace insécable de séparation) -> float() crasherait.
    path.write_text(
        "quarter: x\nyear: 2026\nobjectives:\n  - title: O\n    key_results:\n"
        '      - name: MRR\n        target: "10 000"\n        actual: 4500\n        unit: EUR\n',
        encoding="utf-8",
    )
    report = okr.load_current(poles_root=tmp_path, today=today)
    assert report.quarter == "<illisible>"
    assert report.key_results == []
    assert report.should_alert is True


def test_okr_load_current_normal_still_works(tmp_path: Path) -> None:
    today = okr.date.today()
    n = (today.month - 1) // 3 + 1
    path = tmp_path / "direction" / "okr" / f"{today.year}-Q{n}.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "quarter: x\nyear: 2026\nobjectives:\n  - title: O\n    key_results:\n"
        "      - name: MRR\n        target: 10000\n        actual: 4500\n        unit: EUR\n",
        encoding="utf-8",
    )
    report = okr.load_current(poles_root=tmp_path, today=today)
    assert report.quarter == "x"
    assert len(report.key_results) == 1


# =============================================================================
# Finding #3 — board pack : libellés archi v2, pas la sémantique DB legacy
# =============================================================================
async def test_board_render_uses_fleet_labels(tmp_path: Path) -> None:
    snapshot = await build_fleet_snapshot(poles_root=tmp_path)
    md = board.render(board.build_metrics(snapshot, poles_root=tmp_path))
    assert "Faits mémoire (flotte)" in md
    assert "Pôles en alerte critique" in md
    # Les libellés DB legacy trompeurs ne doivent PAS apparaître.
    assert "Agent runs" not in md
    assert "Circuit breakers tripped" not in md


# =============================================================================
# Finding #4 — created_at naïf / date nue ne casse pas le snapshot transversal
# =============================================================================
async def test_fleet_snapshot_tolerates_naive_created_at(tmp_path: Path) -> None:
    _pole_yaml(tmp_path, "veille")
    # Un fait écrit normalement (created_at aware/UTC).
    await memory.write_memory("veille", "s1", "fait aware récent", kind="note", poles_root=tmp_path)
    # Un fait à la main avec une date NUE (naïve) — saisie founder plausible.
    mem_dir = memory.script_memory_dir("veille", "s2", poles_root=tmp_path)
    mem_dir.mkdir(parents=True, exist_ok=True)
    (mem_dir / "naive01.md").write_text(
        "---\nid: naive01\npole: veille\nscript: s2\nkind: note\nimportant: false\n"
        "source: s2\ncreated_at: '2026-06-17'\ntags: []\n---\n\nfait à date nue\n",
        encoding="utf-8",
    )
    # read_pole_memory trie par created_at : naïf + aware mélangés -> ne doit PAS lever.
    by_script = await memory.read_pole_memory("veille", poles_root=tmp_path)
    assert {"s1", "s2"} <= set(by_script)
    # Le snapshot transversal complet passe lui aussi.
    snapshot = await build_fleet_snapshot(poles_root=tmp_path)
    veille = snapshot.by_id("veille")
    assert veille is not None and veille.n_facts == 2
    # La date nue a bien été normalisée en aware/UTC.
    recs = await memory.read_memory("veille", "s2", poles_root=tmp_path)
    assert recs[0].created_at.tzinfo is not None
    assert recs[0].created_at == datetime(2026, 6, 17, tzinfo=UTC)
