"""Tests du chargement des ``pole.yaml`` (socle archi v2).

Mélange de tests hermétiques (``tmp_path``) et de tests sur les **vrais**
squelettes committés dans ``data/poles/`` (read-only).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from argos_ops.exceptions import ConfigError
from argos_ops.poles import config


def _write_pole(root: Path, pole: str, body: str) -> None:
    d = root / pole
    d.mkdir(parents=True, exist_ok=True)
    (d / "pole.yaml").write_text(body, encoding="utf-8")


# =============================================================================
# Parsing hermétique
# =============================================================================
def test_load_minimal(tmp_path: Path) -> None:
    _write_pole(
        tmp_path,
        "veille",
        "id: veille\nname: Veille\nagent:\n  name: VeilleAgent\n  skills: [trend]\n"
        "scripts: []\nreads_cross_pole: []\nfront_tools: [memory_table]\n",
    )
    cfg = config.load_pole_config("veille", poles_root=tmp_path)
    assert cfg.id == "veille"
    assert cfg.name == "Veille"
    assert cfg.agent is not None
    assert cfg.agent.name == "VeilleAgent"
    assert cfg.agent.skills == ("trend",)
    assert cfg.has_agent
    assert cfg.front_tools == ("memory_table",)


def test_agent_null_means_no_agent(tmp_path: Path) -> None:
    _write_pole(
        tmp_path,
        "sre",
        "id: sre\nagent: null\nscripts: []\nreads_cross_pole: []\nfront_tools: []\n",
    )
    cfg = config.load_pole_config("sre", poles_root=tmp_path)
    assert cfg.agent is None
    assert not cfg.has_agent


def test_missing_agent_key_means_no_agent(tmp_path: Path) -> None:
    _write_pole(tmp_path, "x", "id: x\nname: X\n")
    cfg = config.load_pole_config("x", poles_root=tmp_path)
    assert cfg.agent is None
    assert cfg.scripts == ()
    assert cfg.reads_cross_pole == ()


def test_wildcard_reads_all(tmp_path: Path) -> None:
    _write_pole(
        tmp_path,
        "direction",
        'id: direction\nagent:\n  name: DirectionAgent\nreads_cross_pole: ["*"]\n',
    )
    cfg = config.load_pole_config("direction", poles_root=tmp_path)
    assert cfg.reads_all_poles


def test_scripts_parsed_with_schedule(tmp_path: Path) -> None:
    _write_pole(
        tmp_path,
        "sre",
        "id: sre\nagent: null\nscripts:\n  - id: uptime\n    description: ping\n"
        "    schedule: '*/5 * * * *'\nfront_tools: []\n",
    )
    cfg = config.load_pole_config("sre", poles_root=tmp_path)
    assert len(cfg.scripts) == 1
    assert cfg.scripts[0].id == "uptime"
    assert cfg.scripts[0].schedule == "*/5 * * * *"


def test_missing_file_raises(tmp_path: Path) -> None:
    with pytest.raises(ConfigError):
        config.load_pole_config("ghost", poles_root=tmp_path)


def test_agent_without_name_raises(tmp_path: Path) -> None:
    _write_pole(tmp_path, "x", "id: x\nagent:\n  skills: []\n")
    with pytest.raises(ConfigError):
        config.load_pole_config("x", poles_root=tmp_path)


def test_script_without_id_raises(tmp_path: Path) -> None:
    _write_pole(tmp_path, "x", "id: x\nscripts:\n  - description: no id\n")
    with pytest.raises(ConfigError):
        config.load_pole_config("x", poles_root=tmp_path)


def test_front_tools_not_a_list_raises(tmp_path: Path) -> None:
    _write_pole(tmp_path, "x", "id: x\nfront_tools: memory_table\n")
    with pytest.raises(ConfigError):
        config.load_pole_config("x", poles_root=tmp_path)


def test_list_poles_skips_internal(tmp_path: Path) -> None:
    _write_pole(tmp_path, "veille", "id: veille\nagent:\n  name: A\n")
    _write_pole(tmp_path, "_example", "id: _example\nagent:\n  name: B\n")
    (tmp_path / "no_yaml").mkdir()  # dossier sans pole.yaml → ignoré

    assert config.list_poles(poles_root=tmp_path) == ["veille"]
    assert "_example" in config.list_poles(poles_root=tmp_path, include_internal=True)


def test_list_poles_empty_root(tmp_path: Path) -> None:
    assert config.list_poles(poles_root=tmp_path / "absent") == []


# =============================================================================
# Vrais squelettes committés (data/poles/)
# =============================================================================
_EXPECTED_POLES = {
    "veille",
    "marketing",
    "pub",
    "vente",
    "finance",
    "direction",
    "memoire",
    "sre",
}


def test_real_repo_has_eight_poles() -> None:
    assert set(config.list_poles()) == _EXPECTED_POLES


def test_real_all_poles_load_without_error() -> None:
    cfgs = config.load_all_poles()
    assert {c.id for c in cfgs} == _EXPECTED_POLES


def test_real_sre_has_no_agent() -> None:
    assert config.load_pole_config("sre").agent is None


def test_real_memoire_agent_is_script_triggered() -> None:
    cfg = config.load_pole_config("memoire")
    assert cfg.agent is not None
    assert cfg.agent.trigger == "script"


def test_real_direction_reads_all() -> None:
    assert config.load_pole_config("direction").reads_all_poles


def test_real_example_pole_excluded_but_loadable() -> None:
    assert "_example" not in config.list_poles()
    assert "_example" in config.list_poles(include_internal=True)
    cfg = config.load_pole_config("_example")
    assert cfg.scripts[0].id == "heartbeat"
