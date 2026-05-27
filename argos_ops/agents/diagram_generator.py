"""DiagramGenerator — Tech Doc (Sprint 13).

Génère un diagramme Mermaid (flowchart) à partir d'une spec YAML
minimale et l'écrit dans ``docs/diagrams/<slug>.md``.

Spec attendue (``data/diagrams/<slug>.yaml``) ::

    title: Pipeline EmailBot
    direction: LR        # LR (gauche-droite) ou TB (top-bottom)
    nodes:
      - id: imap
        label: Pull IMAP
      - id: classify
        label: email-classifier
      - id: crm
        label: CRM ingest
    edges:
      - from: imap
        to: classify
      - from: classify
        to: crm
        label: "lead_chaud"

Le bot ne consomme aucune API externe (D-017) — c'est juste de la
sérialisation YAML → Mermaid. Idempotent : ré-exécuter sur le même
input écrase le markdown.

Pas de slash watcher (silence/alert). C'est un générateur invoqué à
la demande via ``/gen-diagram <slug>``.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml
from loguru import logger

from argos_ops.agents.base import BaseAgent, RunResult
from argos_ops.config import REPO_ROOT

DEFAULT_SPECS_DIR: Path = REPO_ROOT / "data" / "diagrams"
DEFAULT_OUTPUT_DIR: Path = REPO_ROOT / "docs" / "diagrams"

_VALID_DIRECTIONS: frozenset[str] = frozenset({"LR", "RL", "TB", "BT"})
_NODE_ID_RE = re.compile(r"^[A-Za-z0-9_]+$")


@dataclass(frozen=True)
class DiagramNode:
    id: str
    label: str


@dataclass(frozen=True)
class DiagramEdge:
    src: str
    dst: str
    label: str | None


@dataclass(frozen=True)
class DiagramSpec:
    title: str
    direction: str
    nodes: list[DiagramNode]
    edges: list[DiagramEdge]


def _sanitize_label(text: str) -> str:
    """Échappe les caractères Mermaid délicats dans un label."""
    return text.replace('"', "'").replace("\n", " ").strip()


def parse_spec(raw: dict[str, object]) -> DiagramSpec:
    """Construit un :class:`DiagramSpec` depuis un dict YAML chargé.

    Lève :class:`ValueError` si la spec est incohérente (node ID
    invalide, edge pointant vers un node inconnu, direction non
    supportée). On préfère échouer fort plutôt que générer un
    diagramme invalide en silence.
    """
    title = str(raw.get("title", "Diagramme")).strip() or "Diagramme"
    direction = str(raw.get("direction", "LR")).upper()
    if direction not in _VALID_DIRECTIONS:
        raise ValueError(
            f"direction invalide : {direction!r} (attendu : {sorted(_VALID_DIRECTIONS)})"
        )

    nodes_raw = raw.get("nodes") or []
    if not isinstance(nodes_raw, list) or not nodes_raw:
        raise ValueError("spec doit déclarer au moins un node")

    nodes: list[DiagramNode] = []
    seen_ids: set[str] = set()
    for entry in nodes_raw:
        if not isinstance(entry, dict):
            raise ValueError(f"node mal formé : {entry!r}")
        node_id = str(entry.get("id", "")).strip()
        if not _NODE_ID_RE.match(node_id):
            raise ValueError(f"node id invalide : {node_id!r} (alphanum + _)")
        if node_id in seen_ids:
            raise ValueError(f"node id dupliqué : {node_id}")
        seen_ids.add(node_id)
        label = _sanitize_label(str(entry.get("label", node_id)))
        nodes.append(DiagramNode(id=node_id, label=label))

    edges_raw = raw.get("edges") or []
    if not isinstance(edges_raw, list):
        raise ValueError(f"edges doit être une liste, vu : {type(edges_raw).__name__}")
    edges: list[DiagramEdge] = []
    for entry in edges_raw:
        if not isinstance(entry, dict):
            raise ValueError(f"edge mal formé : {entry!r}")
        src = str(entry.get("from", "")).strip()
        dst = str(entry.get("to", "")).strip()
        if src not in seen_ids or dst not in seen_ids:
            raise ValueError(f"edge référence un node inconnu : {src} -> {dst}")
        label_raw = entry.get("label")
        edge_label = _sanitize_label(str(label_raw)) if label_raw is not None else None
        edges.append(DiagramEdge(src=src, dst=dst, label=edge_label))

    return DiagramSpec(title=title, direction=direction, nodes=nodes, edges=edges)


def render_mermaid(spec: DiagramSpec) -> str:
    """Sérialise une spec en bloc markdown contenant un flowchart Mermaid."""
    lines = [
        f"# {spec.title}",
        "",
        "```mermaid",
        f"flowchart {spec.direction}",
    ]
    for node in spec.nodes:
        lines.append(f'    {node.id}["{node.label}"]')
    for edge in spec.edges:
        if edge.label:
            lines.append(f'    {edge.src} -->|"{edge.label}"| {edge.dst}')
        else:
            lines.append(f"    {edge.src} --> {edge.dst}")
    lines.append("```")
    lines.append("")
    lines.append("> Généré par `DiagramGenerator` — éditer la spec YAML pour patcher.")
    lines.append("")
    return "\n".join(lines)


def write_diagram(
    slug: str, spec: DiagramSpec, *, output_dir: Path = DEFAULT_OUTPUT_DIR
) -> Path:
    """Écrit le markdown généré dans ``output_dir/<slug>.md``."""
    output_dir.mkdir(parents=True, exist_ok=True)
    target = output_dir / f"{slug}.md"
    target.write_text(render_mermaid(spec), encoding="utf-8")
    return target


def load_spec(path: Path) -> DiagramSpec:
    """Lit le YAML et parse — :class:`ValueError` si invalide."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw, dict):
        raise ValueError(f"YAML root doit être un mapping, vu : {type(raw).__name__}")
    return parse_spec(raw)


class DiagramGenerator(BaseAgent):
    """Tech Doc — génère un diagramme Mermaid depuis une spec YAML."""

    name = "DiagramGenerator"
    command = "/gen-diagram"
    breaker_name = None
    ai_act_risk_class = "minimal"

    def __init__(
        self,
        slug: str,
        *,
        specs_dir: Path = DEFAULT_SPECS_DIR,
        output_dir: Path = DEFAULT_OUTPUT_DIR,
    ) -> None:
        self._slug = slug
        self._specs_dir = specs_dir
        self._output_dir = output_dir

    async def run(self) -> RunResult:
        spec_path = self._specs_dir / f"{self._slug}.yaml"
        if not spec_path.exists():
            return RunResult(
                status="failed",
                error=f"spec introuvable : {spec_path}",
            )
        try:
            spec = load_spec(spec_path)
        except ValueError as exc:
            logger.error(f"DiagramGenerator — spec {self._slug} invalide : {exc}")
            return RunResult(status="failed", error=f"spec invalide : {exc}")

        target = write_diagram(self._slug, spec, output_dir=self._output_dir)
        logger.info(f"DiagramGenerator — diagramme écrit dans {target}")
        return RunResult(
            status="success",
            output_summary=(
                f"slug={self._slug} nodes={len(spec.nodes)} edges={len(spec.edges)}"
            ),
            extras={"written_to": str(target)},
        )


__all__ = [
    "DEFAULT_OUTPUT_DIR",
    "DEFAULT_SPECS_DIR",
    "DiagramEdge",
    "DiagramGenerator",
    "DiagramNode",
    "DiagramSpec",
    "load_spec",
    "parse_spec",
    "render_mermaid",
    "write_diagram",
]
