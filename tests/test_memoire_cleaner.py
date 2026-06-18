"""Tests du cleaner gardé + file validée + script (archi v2, S7).

Hermétique (tmp_path). Vérifie surtout l'invariant côté exécution : un fait
``important`` (ou pattern protégé) demandé à la suppression est **refusé** et
reste sur disque — défense en profondeur au-delà du plan.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

from argos_ops.poles import memory
from argos_ops.poles.memoire import cleaner, history
from argos_ops.poles.memoire.cleaner import DeletionTarget, execute_cleanup
from argos_ops.poles.memoire.policy import MemoryPolicy
from argos_ops.poles.memoire.scripts import MemoryCleanerScript

NOW = datetime(2026, 6, 18, tzinfo=UTC)
OLD = NOW - timedelta(days=400)
FRESH = NOW - timedelta(days=2)
POLICY = MemoryPolicy(
    active_for=("veille",),
    protect_important=True,
    protected_kinds=("decision",),
    default_ttl_days=180,
    keep_recent_per_kind=5,
    min_stale_days=30,
)


async def _seed(root: Path) -> dict[str, str]:
    imp = await memory.write_memory(
        "veille", "s", "important très vieux", important=True, created_at=OLD, poles_root=root
    )
    exp = await memory.write_memory(
        "veille", "s", "périmé ordinaire", created_at=OLD, poles_root=root
    )
    fresh = await memory.write_memory("veille", "s", "frais", created_at=FRESH, poles_root=root)
    dec = await memory.write_memory(
        "veille", "s", "décision protégée", kind="decision", created_at=OLD, poles_root=root
    )
    return {"imp": imp.id, "exp": exp.id, "fresh": fresh.id, "dec": dec.id}


async def test_deletes_only_validated_expired(tmp_path: Path) -> None:
    ids = await _seed(tmp_path)
    res = await execute_cleanup(
        "veille", [DeletionTarget("s", ids["exp"])], policy=POLICY, now=NOW, poles_root=tmp_path
    )
    assert res.n_deleted == 1
    assert {d.record_id for d in res.deleted} == {ids["exp"]}
    assert await memory.read_record("veille", "s", ids["exp"], poles_root=tmp_path) is None


async def test_important_is_refused_and_survives(tmp_path: Path) -> None:
    """INVARIANT : demander la suppression d'un fait important ⇒ refusé, fait intact."""
    ids = await _seed(tmp_path)
    res = await execute_cleanup(
        "veille", [DeletionTarget("s", ids["imp"])], policy=POLICY, now=NOW, poles_root=tmp_path
    )
    assert res.n_deleted == 0
    assert any(r.record_id == ids["imp"] and "important" in r.reason for r in res.refused)
    # Toujours là.
    assert await memory.read_record("veille", "s", ids["imp"], poles_root=tmp_path) is not None


async def test_pattern_protected_is_refused(tmp_path: Path) -> None:
    ids = await _seed(tmp_path)
    res = await execute_cleanup(
        "veille", [DeletionTarget("s", ids["dec"])], policy=POLICY, now=NOW, poles_root=tmp_path
    )
    assert res.n_deleted == 0
    assert any(r.record_id == ids["dec"] and "pattern" in r.reason for r in res.refused)
    assert await memory.read_record("veille", "s", ids["dec"], poles_root=tmp_path) is not None


async def test_non_candidate_fresh_is_refused(tmp_path: Path) -> None:
    ids = await _seed(tmp_path)
    res = await execute_cleanup(
        "veille", [DeletionTarget("s", ids["fresh"])], policy=POLICY, now=NOW, poles_root=tmp_path
    )
    assert res.n_deleted == 0
    assert any("éligible" in r.reason for r in res.refused)
    assert await memory.read_record("veille", "s", ids["fresh"], poles_root=tmp_path) is not None


async def test_mixed_batch_guards_all(tmp_path: Path) -> None:
    ids = await _seed(tmp_path)
    res = await execute_cleanup(
        "veille",
        [
            DeletionTarget("s", ids["imp"]),
            DeletionTarget("s", ids["exp"]),
            DeletionTarget("s", ids["fresh"]),
            DeletionTarget("s", ids["dec"]),
            DeletionTarget("s", "deadbeef0000"),  # absent → no-op
        ],
        policy=POLICY,
        now=NOW,
        poles_root=tmp_path,
    )
    assert {d.record_id for d in res.deleted} == {ids["exp"]}
    refused_ids = {r.record_id for r in res.refused}
    assert ids["imp"] in refused_ids
    assert ids["dec"] in refused_ids
    assert ids["fresh"] in refused_ids
    # L'absent n'est ni supprimé ni refusé (idempotent).
    assert "deadbeef0000" not in refused_ids
    # Seul l'expiré a disparu.
    assert await memory.read_record("veille", "s", ids["imp"], poles_root=tmp_path) is not None
    assert await memory.read_record("veille", "s", ids["exp"], poles_root=tmp_path) is None


async def test_duplicate_targets_deduped(tmp_path: Path) -> None:
    ids = await _seed(tmp_path)
    res = await execute_cleanup(
        "veille",
        [DeletionTarget("s", ids["exp"]), DeletionTarget("s", ids["exp"])],
        policy=POLICY,
        now=NOW,
        poles_root=tmp_path,
    )
    assert res.n_deleted == 1


async def test_history_recorded(tmp_path: Path) -> None:
    ids = await _seed(tmp_path)
    await execute_cleanup(
        "veille",
        [DeletionTarget("s", ids["exp"]), DeletionTarget("s", ids["imp"])],
        policy=POLICY,
        now=NOW,
        actor="cockpit",
        poles_root=tmp_path,
    )
    runs = history.load_runs(poles_root=tmp_path)
    assert len(runs) == 1
    assert runs[0].pole == "veille"
    assert runs[0].actor == "cockpit"
    assert runs[0].n_deleted == 1
    assert runs[0].n_refused == 1


async def test_no_history_when_nothing_happened(tmp_path: Path) -> None:
    await _seed(tmp_path)
    # Cible absente uniquement → rien ne se passe → pas d'entrée d'historique.
    await execute_cleanup(
        "veille", [DeletionTarget("s", "deadbeef0000")], policy=POLICY, now=NOW, poles_root=tmp_path
    )
    assert history.load_runs(poles_root=tmp_path) == []


async def test_skipped_accounting_sums_to_requested(tmp_path: Path) -> None:
    ids = await _seed(tmp_path)
    res = await execute_cleanup(
        "veille",
        [
            DeletionTarget("s", ids["imp"]),  # refusé (important)
            DeletionTarget("s", ids["exp"]),  # supprimé
            DeletionTarget("s", ids["exp"]),  # doublon → ignoré
            DeletionTarget("s", "deadbeef0000"),  # absent → ignoré
        ],
        policy=POLICY,
        now=NOW,
        poles_root=tmp_path,
    )
    assert res.requested == 4
    assert res.skipped == 2
    # Comptabilité exacte : deleted + refused + skipped == requested.
    assert res.n_deleted + res.n_refused + res.skipped == res.requested


async def test_inactive_pole_refusal_reason(tmp_path: Path) -> None:
    # Pôle non actif (curation off) → refus avec un motif explicite (pas « non éligible »).
    rec = await memory.write_memory("pub", "s", "périmé", created_at=OLD, poles_root=tmp_path)
    policy = MemoryPolicy(active_for=("veille",))  # pub absent → inactif
    res = await execute_cleanup(
        "pub", [DeletionTarget("s", rec.id)], policy=policy, now=NOW, poles_root=tmp_path
    )
    assert res.n_deleted == 0
    assert any("non actif" in r.reason for r in res.refused)
    # Le fait reste intact.
    assert await memory.read_record("pub", "s", rec.id, poles_root=tmp_path) is not None


async def test_cleaner_script_keeps_queue_when_all_refused(tmp_path: Path) -> None:
    (tmp_path / "memoire").mkdir(parents=True, exist_ok=True)
    # pub absent d'active_for : le cron refusera tout → la file validée est CONSERVÉE
    # pour retry (on ne jette jamais une liste validée par l'humain).
    (tmp_path / "memoire" / "policy.yaml").write_text(
        "protect_important: true\nactive_for: [veille]\ndefault_ttl_days: 180\n", encoding="utf-8"
    )
    rec = await memory.write_memory("pub", "s", "périmé", created_at=OLD, poles_root=tmp_path)
    cleaner.enqueue_validated("pub", [DeletionTarget("s", rec.id)], poles_root=tmp_path)
    await MemoryCleanerScript(poles_root=tmp_path).run()
    assert "pub" in cleaner.load_validated_queue(poles_root=tmp_path)
    assert await memory.read_record("pub", "s", rec.id, poles_root=tmp_path) is not None


# =============================================================================
# File validée + script cron
# =============================================================================
async def test_validated_queue_roundtrip(tmp_path: Path) -> None:
    targets = [DeletionTarget("s", "abc123"), DeletionTarget("t", "def456")]
    cleaner.enqueue_validated("veille", targets, poles_root=tmp_path)
    queue = cleaner.load_validated_queue(poles_root=tmp_path)
    assert queue == {"veille": targets}
    assert cleaner.clear_validated_queue("veille", poles_root=tmp_path) is True
    assert cleaner.load_validated_queue(poles_root=tmp_path) == {}


async def test_cleaner_script_processes_queue(tmp_path: Path) -> None:
    (tmp_path / "memoire").mkdir(parents=True, exist_ok=True)
    (tmp_path / "memoire" / "policy.yaml").write_text(
        "protect_important: true\nactive_for: [veille]\ndefault_ttl_days: 180\n", encoding="utf-8"
    )
    ids = await _seed(tmp_path)
    cleaner.enqueue_validated(
        "veille",
        [DeletionTarget("s", ids["exp"]), DeletionTarget("s", ids["imp"])],
        poles_root=tmp_path,
    )
    script = MemoryCleanerScript(poles_root=tmp_path)
    result = await script.run()
    assert result.status == "success"
    # L'expiré supprimé, l'important refusé (toujours là).
    assert await memory.read_record("veille", "s", ids["exp"], poles_root=tmp_path) is None
    assert await memory.read_record("veille", "s", ids["imp"], poles_root=tmp_path) is not None
    # File vidée + fait de synthèse écrit dans la mémoire du cleaner.
    assert cleaner.load_validated_queue(poles_root=tmp_path) == {}
    cleaner_mem = await memory.read_memory("memoire", "memory_cleaner", poles_root=tmp_path)
    assert any(r.kind == "cleanup" for r in cleaner_mem)


async def test_cleaner_script_skips_when_empty(tmp_path: Path) -> None:
    (tmp_path / "memoire").mkdir(parents=True, exist_ok=True)
    (tmp_path / "memoire" / "policy.yaml").write_text("active_for: [veille]\n", encoding="utf-8")
    script = MemoryCleanerScript(poles_root=tmp_path)
    result = await script.run()
    assert result.status == "success"
    assert result.written == []
