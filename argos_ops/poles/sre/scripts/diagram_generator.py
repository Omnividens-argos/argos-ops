"""``DiagramGeneratorScript`` — diagrammes Mermaid depuis YAML (archi v2, S8).

Lit les specs ``data/poles/sre/diagrams/<slug>.yaml`` (sous ``poles_root``) et
génère ``docs/diagrams/<slug>.md`` (flowchart Mermaid). Idempotent (réécrit le
même contenu à spec inchangée). Générateur, pas watcher : vert si tout est
généré, jaune si au moins une spec est invalide (ignorée).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml
from loguru import logger

from argos_ops.config import REPO_ROOT
from argos_ops.poles.config import POLES_DIR
from argos_ops.poles.sre.base import BaseSreScript
from argos_ops.poles.sre.report import SreReport

SPECS_SUBDIR = "diagrams"
DEFAULT_OUTPUT_DIR = REPO_ROOT / "docs" / "diagrams"
_VALID_DIRECTIONS = frozenset({"LR", "RL", "TB", "BT"})
_NODE_ID_RE = re.compile(r"^[A-Za-z0-9_]+$")


def specs_dir(*, poles_root: Path = POLES_DIR) -> Path:
    return poles_root / "sre" / SPECS_SUBDIR


@dataclass(frozen=True)
class DiagramResult:
    """Résultat de génération d'une spec."""

    slug: str
    ok: bool
    written_to: str | None
    error: str | None


def _escape_label(label: str) -> str:
    return label.replace('"', "'").replace("\n", " ").strip()


def render_mermaid(spec: dict[str, object]) -> str:
    """Rend un flowchart Mermaid. Lève ``ValueError`` si la spec est invalide."""
    title = str(spec.get("title", "Diagramme"))
    direction = str(spec.get("direction", "LR"))
    if direction not in _VALID_DIRECTIONS:
        raise ValueError(f"direction invalide : {direction}")
    raw_nodes = spec.get("nodes")
    raw_edges = spec.get("edges") or []
    if not isinstance(raw_nodes, list) or not raw_nodes:
        raise ValueError("au moins un nœud requis")
    if not isinstance(raw_edges, list):
        raise ValueError("'edges' doit être une liste")

    node_ids: set[str] = set()
    node_lines: list[str] = []
    for node in raw_nodes:
        if not isinstance(node, dict):
            raise ValueError("chaque nœud doit être un mapping")
        nid = str(node.get("id", ""))
        if not _NODE_ID_RE.match(nid):
            raise ValueError(f"id de nœud invalide : '{nid}'")
        if nid in node_ids:
            raise ValueError(f"id de nœud dupliqué : '{nid}'")
        node_ids.add(nid)
        node_lines.append(f'    {nid}["{_escape_label(str(node.get("label", nid)))}"]')

    edge_lines: list[str] = []
    for edge in raw_edges:
        if not isinstance(edge, dict):
            raise ValueError("chaque arête doit être un mapping")
        src, dst = str(edge.get("from", "")), str(edge.get("to", ""))
        if src not in node_ids or dst not in node_ids:
            raise ValueError(f"arête vers un nœud inconnu : {src} → {dst}")
        label = edge.get("label")
        if label:
            edge_lines.append(f'    {src} -->|"{_escape_label(str(label))}"| {dst}')
        else:
            edge_lines.append(f"    {src} --> {dst}")

    body = "\n".join([f"flowchart {direction}", *node_lines, *edge_lines])
    return f"# {title}\n\n```mermaid\n{body}\n```\n"


def generate_all(*, poles_root: Path, output_dir: Path) -> list[DiagramResult]:
    """Génère tous les diagrammes des specs présentes (pur sauf l'écriture)."""
    src = specs_dir(poles_root=poles_root)
    if not src.exists():
        return []
    results: list[DiagramResult] = []
    for path in sorted(src.glob("*.yaml")):
        slug = path.stem
        try:
            raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
            if not isinstance(raw, dict):
                raise ValueError("spec racine doit être un mapping")
            markdown = render_mermaid(raw)
        except (yaml.YAMLError, ValueError) as exc:
            logger.warning(f"diagram_generator — spec '{slug}' invalide : {exc}")
            results.append(DiagramResult(slug, False, None, str(exc)))
            continue
        output_dir.mkdir(parents=True, exist_ok=True)
        out_path = output_dir / f"{slug}.md"
        out_path.write_text(markdown, encoding="utf-8")
        results.append(DiagramResult(slug, True, str(out_path), None))
    return results


def build_report(results: list[DiagramResult]) -> SreReport:
    if not results:
        return SreReport("green", "Aucune spec de diagramme.")
    n_ok = sum(1 for r in results if r.ok)
    n_bad = len(results) - n_ok
    summary = f"{n_ok} diagramme(s) généré(s) · {n_bad} spec(s) invalide(s)"
    detail = "\n".join(f"- {r.slug} : {r.error}" for r in results if not r.ok)
    return SreReport("yellow" if n_bad else "green", summary, detail)


class DiagramGeneratorScript(BaseSreScript):
    """Génère les diagrammes Mermaid depuis les specs YAML."""

    name = "diagram_generator"

    def __init__(self, *, poles_root: Path = POLES_DIR, output_dir: Path | None = None) -> None:
        super().__init__(poles_root=poles_root)
        self._output_dir = output_dir or DEFAULT_OUTPUT_DIR

    async def check(self) -> SreReport:
        return build_report(generate_all(poles_root=self.poles_root, output_dir=self._output_dir))


__all__ = [
    "DiagramGeneratorScript",
    "DiagramResult",
    "build_report",
    "generate_all",
    "render_mermaid",
    "specs_dir",
]
