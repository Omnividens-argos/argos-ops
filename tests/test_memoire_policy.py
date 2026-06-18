"""Tests de la policy de curation (archi v2, S7) : chargement défensif + écriture."""

from __future__ import annotations

from pathlib import Path

from argos_ops.poles.memoire.policy import (
    DEFAULT_TTL_DAYS,
    MemoryPolicy,
    load_policy,
    save_policy,
    set_pole_active,
)


def _write(root: Path, body: str) -> None:
    (root / "memoire").mkdir(parents=True, exist_ok=True)
    (root / "memoire" / "policy.yaml").write_text(body, encoding="utf-8")


def test_missing_file_is_safe_default(tmp_path: Path) -> None:
    policy = load_policy(poles_root=tmp_path)
    # Fail-safe : protect_important True, aucun pôle actif (rien nettoyé).
    assert policy.protect_important is True
    assert policy.active_for == ()
    assert policy.default_ttl_days == DEFAULT_TTL_DAYS


def test_load_full_policy(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "protect_important: true\n"
        "active_for: [veille, finance]\n"
        "protected_kinds: [decision]\n"
        "protected_tags: [pinned]\n"
        "protected_sources: [oracle]\n"
        "default_ttl_days: 90\n"
        "ttl_by_kind: {signal: 30}\n"
        "keep_recent_per_kind: 3\n"
        "min_stale_days: 14\n",
    )
    p = load_policy(poles_root=tmp_path)
    assert p.active_for == ("veille", "finance")
    assert p.protected_kinds == ("decision",)
    assert p.ttl_for("signal") == 30
    assert p.ttl_for("note") == 90  # défaut
    assert p.keep_recent_per_kind == 3
    assert p.min_stale_days == 14


def test_is_active_and_pattern_protection(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "active_for: [veille]\nprotected_kinds: [decision]\n"
        "protected_tags: [pinned]\nprotected_sources: [oracle]\n",
    )
    p = load_policy(poles_root=tmp_path)
    assert p.is_active("veille") is True
    assert p.is_active("pub") is False
    assert p.is_pattern_protected(kind="decision", tags=(), source=None) is True
    assert p.is_pattern_protected(kind="note", tags=("pinned",), source=None) is True
    assert p.is_pattern_protected(kind="note", tags=(), source="oracle") is True
    assert p.is_pattern_protected(kind="note", tags=(), source="autre") is False


def test_malformed_yaml_falls_back(tmp_path: Path) -> None:
    _write(tmp_path, ": : : not yaml : :\n[")
    p = load_policy(poles_root=tmp_path)
    assert p.protect_important is True  # défaut sûr


def test_present_but_null_protect_important_stays_true(tmp_path: Path) -> None:
    # INVARIANT : une clé présente mais NULLE (`protect_important:` nu, `~`, `null`,
    # valeur commentée) ne doit JAMAIS désactiver la protection (bool(None)==False).
    for body in (
        "protect_important:\nactive_for: [veille]\n",
        "protect_important: ~\nactive_for: [veille]\n",
        "protect_important: null\nactive_for: [veille]\n",
    ):
        _write(tmp_path, body)
        assert load_policy(poles_root=tmp_path).protect_important is True, body


def test_explicit_false_still_disables(tmp_path: Path) -> None:
    # Le seul moyen de désactiver = valeur explicite non nulle falsey.
    _write(tmp_path, "protect_important: false\n")
    assert load_policy(poles_root=tmp_path).protect_important is False


def test_infinite_or_nan_numbers_do_not_crash(tmp_path: Path) -> None:
    # YAML .inf / -.inf / .nan ⇒ int() lève OverflowError/ValueError : load_policy
    # ne doit jamais crasher (contrat « jamais d'exception »), retombe sur défauts.
    _write(
        tmp_path,
        "default_ttl_days: .inf\nmin_stale_days: -.inf\nkeep_recent_per_kind: .nan\n"
        "ttl_by_kind: {signal: .inf}\n",
    )
    p = load_policy(poles_root=tmp_path)
    assert p.default_ttl_days == DEFAULT_TTL_DAYS
    assert p.ttl_for("signal") == DEFAULT_TTL_DAYS  # .inf rejeté → défaut


def test_negative_or_bad_values_are_clamped(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "default_ttl_days: -5\nkeep_recent_per_kind: notanint\nmin_stale_days: -3\n",
    )
    p = load_policy(poles_root=tmp_path)
    assert p.default_ttl_days == 1  # minimum 1
    assert p.keep_recent_per_kind == 5  # défaut (illisible)
    assert p.min_stale_days == 0  # minimum 0


def test_save_then_reload_roundtrip(tmp_path: Path) -> None:
    original = MemoryPolicy(
        protect_important=True,
        active_for=("veille", "pub"),
        protected_kinds=("decision",),
        default_ttl_days=120,
        ttl_by_kind={"signal": 20},
        keep_recent_per_kind=4,
        min_stale_days=15,
    )
    save_policy(original, poles_root=tmp_path)
    reloaded = load_policy(poles_root=tmp_path)
    assert reloaded == original


def test_set_pole_active_toggles_and_persists(tmp_path: Path) -> None:
    _write(tmp_path, "protect_important: true\nactive_for: [veille]\n")
    after_add = set_pole_active("pub", True, poles_root=tmp_path)
    assert set(after_add.active_for) == {"veille", "pub"}
    # Persisté.
    assert set(load_policy(poles_root=tmp_path).active_for) == {"veille", "pub"}

    after_remove = set_pole_active("veille", False, poles_root=tmp_path)
    assert set(after_remove.active_for) == {"pub"}

    # Idempotent : re-désactiver un pôle déjà off ne change rien.
    again = set_pole_active("veille", False, poles_root=tmp_path)
    assert set(again.active_for) == {"pub"}


def test_set_pole_active_preserves_other_fields(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "protect_important: true\nactive_for: []\nprotected_kinds: [decision]\n"
        "default_ttl_days: 99\nkeep_recent_per_kind: 7\n",
    )
    updated = set_pole_active("finance", True, poles_root=tmp_path)
    assert updated.protected_kinds == ("decision",)
    assert updated.default_ttl_days == 99
    assert updated.keep_recent_per_kind == 7
    assert updated.protect_important is True
