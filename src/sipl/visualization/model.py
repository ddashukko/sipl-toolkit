"""Спільна модель дерева для всіх експортерів (text / JSON / DOT / SVG / HTML).

І дерево виводу, і AST спочатку перетворюються на VisNode,
тому кожен формат реалізовано один раз для обох дерев.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .. import ast
from ..ast import SourceSpan
from ..parse_tree import ParseNode


@dataclass
class VisNode:
    id: str
    label: str  # короткий підпис для малюнка
    title: str  # повний підпис для текстового подання
    category: str  # 'rule' | 'token' | 'stmt' | 'expr' | 'cond'
    span: SourceSpan
    children: list[VisNode] = field(default_factory=list)

    def walk(self) -> list[VisNode]:
        out = [self]
        for child in self.children:
            out.extend(child.walk())
        return out

    def to_dict(self, source: str | None = None) -> dict[str, Any]:
        out: dict[str, Any] = {
            "id": self.id,
            "label": self.label,
            "title": self.title,
            "category": self.category,
            "span": self.span.to_dict(),
        }
        if source is not None:
            out["source"] = self.span.text(source)
        out["children"] = [c.to_dict(source) for c in self.children]
        return out


class _Ids:
    def __init__(self, prefix: str) -> None:
        self.prefix = prefix
        self.count = 0

    def next(self) -> str:
        self.count += 1
        return f"{self.prefix}{self.count - 1}"


def from_parse_tree(tree: ParseNode, prefix: str = "p") -> VisNode:
    """Дерево виводу -> VisNode (термінали стають листками з текстом лексеми)."""
    ids = _Ids(prefix)

    def build(node: ParseNode) -> VisNode:
        node_id = ids.next()
        if node.is_terminal:
            text = node.text or ""
            return VisNode(node_id, text, f'{node.symbol} "{text}"', "token", node.span)
        vis = VisNode(node_id, node.symbol, node.symbol, "rule", node.span)
        vis.children = [build(c) for c in node.children]
        return vis

    return build(tree)


_SYMBOL = {"Or": "∨", "Not": "¬"}
_CATEGORY = {
    "Num": "expr",
    "Var": "expr",
    "BinOp": "expr",
    "Compare": "cond",
    "Or": "cond",
    "Not": "cond",
}


def from_ast(program: ast.Program, prefix: str = "a") -> VisNode:
    """AST -> VisNode."""
    ids = _Ids(prefix)

    def build(node: ast.Node) -> VisNode:
        node_id = ids.next()
        name = type(node).__name__
        if isinstance(node, ast.Num):
            label, title = str(node.value), f"Num {node.value}"
        elif isinstance(node, ast.Var):
            label, title = node.name, f"Var {node.name}"
        elif isinstance(node, (ast.BinOp, ast.Compare)):
            label, title = node.op, f"{name} {node.op}"
        elif name in _SYMBOL:
            label, title = _SYMBOL[name], f"{name} {_SYMBOL[name]}"
        else:
            label = title = name
        vis = VisNode(node_id, label, title, _CATEGORY.get(name, "stmt"), node.span)
        vis.children = [build(child) for _, child in ast.children(node)]
        return vis

    return build(program)
