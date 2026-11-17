"""Експорт дерева: текст, JSON, Graphviz DOT, SVG (власна розкладка, без зовнішніх програм)."""

from __future__ import annotations

from html import escape
from typing import Any

from .model import VisNode

# ---------- text ----------


def to_text(root: VisNode, *, spans: bool = True) -> str:
    lines: list[str] = []

    def emit(node: VisNode, prefix: str, tail: str) -> None:
        suffix = f"  [{node.span}]" if spans else ""
        lines.append(f"{prefix}{tail}{node.title}{suffix}")
        if tail:
            prefix += "    " if tail.startswith("└") else "│   "
        for i, child in enumerate(node.children):
            last = i == len(node.children) - 1
            emit(child, prefix, "└── " if last else "├── ")

    emit(root, "", "")
    return "\n".join(lines)


# ---------- JSON ----------


def to_json_dict(root: VisNode, source: str) -> dict[str, Any]:
    return root.to_dict(source)


# ---------- DOT ----------


def _dot_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


_DOT_STYLE = {
    "rule": 'shape=box, style="rounded,filled", fillcolor="#eef2f7"',
    "token": 'shape=box, style="filled", fillcolor="#fff4d6"',
    "stmt": 'shape=box, style="rounded,filled", fillcolor="#e3f1e7"',
    "expr": 'shape=ellipse, style="filled", fillcolor="#fff4d6"',
    "cond": 'shape=ellipse, style="filled", fillcolor="#f9e3e3"',
}


def to_dot(root: VisNode, source: str, *, name: str = "SIPL") -> str:
    lines = [
        f"digraph {name} {{",
        '  node [fontname="monospace", fontsize=11];',
        "  edge [arrowsize=0.6];",
    ]
    for node in root.walk():
        fragment = " ".join(node.span.text(source).split())
        tooltip = _dot_escape(f"{node.title} [{node.span}]: {fragment}")
        style = _DOT_STYLE[node.category]
        lines.append(
            f'  {node.id} [label="{_dot_escape(node.label)}", tooltip="{tooltip}", {style}];'
        )
    for node in root.walk():
        for child in node.children:
            lines.append(f"  {node.id} -> {child.id};")
    lines.append("}")
    return "\n".join(lines) + "\n"


# ---------- SVG ----------

_CHAR_W = 7.4
_PAD_X = 10
_NODE_H = 26
_LEVEL_H = 58
_GAP = 10
_MARGIN = 16

SVG_STYLE = """
.sipl-tree text { font: 12px ui-monospace, Menlo, Consolas, monospace; text-anchor: middle;
  fill: #1c2430; pointer-events: none; }
.sipl-tree line { stroke: #9aa5b1; stroke-width: 1; }
.sipl-tree .node rect { stroke: #6b7785; stroke-width: 1; }
.sipl-tree .cat-rule rect { fill: #eef2f7; }
.sipl-tree .cat-token rect { fill: #fff4d6; }
.sipl-tree .cat-stmt rect { fill: #e3f1e7; }
.sipl-tree .cat-expr rect { fill: #fff4d6; }
.sipl-tree .cat-cond rect { fill: #f9e3e3; }
"""


def _layout(root: VisNode) -> tuple[dict[str, tuple[float, float, float]], float, float]:
    """Повертає {id: (x_центру, y_верху, ширина_вузла)}, ширину та висоту малюнка."""
    box: dict[str, float] = {}
    subtree: dict[str, float] = {}

    def measure(node: VisNode) -> float:
        box[node.id] = max(len(node.label), 1) * _CHAR_W + 2 * _PAD_X
        kids = sum(measure(c) for c in node.children) + _GAP * max(len(node.children) - 1, 0)
        subtree[node.id] = max(box[node.id], kids)
        return subtree[node.id]

    pos: dict[str, tuple[float, float, float]] = {}
    max_depth = 0

    def place(node: VisNode, left: float, depth: int) -> None:
        nonlocal max_depth
        max_depth = max(max_depth, depth)
        width = subtree[node.id]
        pos[node.id] = (left + width / 2, _MARGIN + depth * _LEVEL_H, box[node.id])
        kids = sum(subtree[c.id] for c in node.children) + _GAP * max(len(node.children) - 1, 0)
        x = left + (width - kids) / 2
        for child in node.children:
            place(child, x, depth + 1)
            x += subtree[child.id] + _GAP

    total = measure(root)
    place(root, _MARGIN, 0)
    return pos, total + 2 * _MARGIN, 2 * _MARGIN + max_depth * _LEVEL_H + _NODE_H


def to_svg(root: VisNode, source: str, *, standalone: bool = True) -> str:
    """SVG-малюнок дерева.

    Кожен вузол несе data-start/data-end (зміщення у вихідному тексті)
    і підказку <title> з відповідним фрагментом коду.
    """
    pos, width, height = _layout(root)
    w, h = round(width), round(height)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" class="sipl-tree" '
        f'width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
    ]
    if standalone:
        parts.append(f"<style>{SVG_STYLE}</style>")
    for node in root.walk():
        x, y, _ = pos[node.id]
        for child in node.children:
            cx, cy, _ = pos[child.id]
            parts.append(f'<line x1="{x:.1f}" y1="{y + _NODE_H:.1f}" x2="{cx:.1f}" y2="{cy:.1f}"/>')
    for node in root.walk():
        x, y, bw = pos[node.id]
        fragment = " ".join(node.span.text(source).split())
        radius = 3 if node.category == "token" else 9
        parts.append(
            f'<g class="node cat-{node.category}" data-id="{node.id}" '
            f'data-title="{escape(node.title, quote=True)}" '
            f'data-start="{node.span.start_offset}" data-end="{node.span.end_offset}">'
            f"<title>{escape(node.title)} [{node.span}]: {escape(fragment)}</title>"
            f'<rect x="{x - bw / 2:.1f}" y="{y:.1f}" width="{bw:.1f}" height="{_NODE_H}" '
            f'rx="{radius}"/>'
            f'<text x="{x:.1f}" y="{y + _NODE_H / 2 + 4:.1f}">{escape(node.label)}</text></g>'
        )
    parts.append("</svg>")
    return "\n".join(parts) + "\n"
