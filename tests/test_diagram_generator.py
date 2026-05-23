"""Tests :mod:`argos_ops.agents.diagram_generator`."""

from __future__ import annotations

from pathlib import Path

import pytest

from argos_ops.agents.diagram_generator import (
    load_spec,
    parse_spec,
    render_mermaid,
    write_diagram,
)


def _valid_spec() -> dict[str, object]:
    return {
        "title": "Pipeline",
        "direction": "LR",
        "nodes": [
            {"id": "a", "label": "Étape A"},
            {"id": "b", "label": "Étape B"},
        ],
        "edges": [{"from": "a", "to": "b", "label": "trigger"}],
    }


# =============================================================================
# parse_spec
# =============================================================================
def test_parse_spec_returns_normalized_dataclass() -> None:
    spec = parse_spec(_valid_spec())
    assert spec.title == "Pipeline"
    assert spec.direction == "LR"
    assert len(spec.nodes) == 2
    assert spec.edges[0].label == "trigger"


def test_parse_spec_rejects_invalid_direction() -> None:
    raw = _valid_spec()
    raw["direction"] = "ZZ"
    with pytest.raises(ValueError):
        parse_spec(raw)


def test_parse_spec_rejects_duplicate_node_id() -> None:
    raw = _valid_spec()
    raw["nodes"] = [{"id": "a", "label": "A"}, {"id": "a", "label": "A bis"}]
    with pytest.raises(ValueError):
        parse_spec(raw)


def test_parse_spec_rejects_edge_to_unknown_node() -> None:
    raw = _valid_spec()
    raw["edges"] = [{"from": "a", "to": "ghost"}]
    with pytest.raises(ValueError):
        parse_spec(raw)


def test_parse_spec_rejects_invalid_node_id() -> None:
    raw = _valid_spec()
    raw["nodes"] = [{"id": "bad-id!", "label": "bad"}]
    with pytest.raises(ValueError):
        parse_spec(raw)


def test_parse_spec_requires_at_least_one_node() -> None:
    raw = _valid_spec()
    raw["nodes"] = []
    with pytest.raises(ValueError):
        parse_spec(raw)


# =============================================================================
# render_mermaid
# =============================================================================
def test_render_mermaid_produces_mermaid_block() -> None:
    spec = parse_spec(_valid_spec())
    md = render_mermaid(spec)
    assert "```mermaid" in md
    assert "flowchart LR" in md
    assert 'a["Étape A"]' in md
    assert 'a -->|"trigger"| b' in md


def test_render_mermaid_skips_edge_label_when_absent() -> None:
    raw = _valid_spec()
    raw["edges"] = [{"from": "a", "to": "b"}]
    spec = parse_spec(raw)
    md = render_mermaid(spec)
    assert "a --> b" in md


# =============================================================================
# load_spec + write
# =============================================================================
def test_load_spec_reads_yaml(tmp_path: Path) -> None:
    path = tmp_path / "spec.yaml"
    path.write_text(
        "title: T\n"
        "direction: LR\n"
        "nodes:\n  - id: a\n    label: A\n"
        "edges: []\n",
        encoding="utf-8",
    )
    spec = load_spec(path)
    assert spec.title == "T"


def test_write_diagram_creates_file(tmp_path: Path) -> None:
    spec = parse_spec(_valid_spec())
    target = write_diagram("test", spec, output_dir=tmp_path)
    assert target.name == "test.md"
    assert "```mermaid" in target.read_text(encoding="utf-8")
