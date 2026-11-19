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


# Метазмінні БНФ практикуму
PROGRAM = "<програма>"
STATEMENT = "<оператор>"
EXPRESSION = "<вираз>"
CONDITION = "<умова>"
VARIABLE = "<змінна>"
NUMBER = "<число>"


def from_parse_tree(tree: ParseNode, prefix: str = "p") -> VisNode:
    """Дерево виводу в нотації практикуму.

    Внутрішні вузли — метазмінні БНФ курсу (<програма>, <оператор>, <вираз>,
    <умова>, <змінна>, <число>), листки — термінали програми. Допоміжні
    правила граматики Lark (seq, stmt, term, factor, bneg, batom), що існують
    лише для пріоритетів, згортаються: кожен вузол відповідає одному
    застосуванню правила БНФ NP1, NS1–NS6, NA1–NA6, NB1–NB5.
    """
    ids = _Ids(prefix)

    def node(symbol: str, span: SourceSpan, children: list[VisNode]) -> VisNode:
        vis = VisNode(ids.next(), symbol, symbol, "rule", span)
        vis.children = children
        return vis

    def token(t: ParseNode) -> VisNode:
        text = t.text or ""
        return VisNode(ids.next(), text, text, "token", t.span)

    def leaf(symbol: str, t: ParseNode, text: str | None = None) -> VisNode:
        # <змінна> -> x, <число> -> n
        outer = VisNode(ids.next(), symbol, symbol, "rule", t.span)
        value = text if text is not None else t.text or ""
        outer.children = [VisNode(ids.next(), value, value, "token", t.span)]
        return outer

    def program(n: ParseNode) -> VisNode:
        c = n.children
        return node(PROGRAM, n.span, [token(c[0]), sequence(c[1]), token(c[2])])

    def sequence(n: ParseNode) -> VisNode:
        # seq: stmt | stmt SEMI seq  ->  <оператор> ::= <оператор> ; <оператор>
        if len(n.children) == 1:
            return statement(n.children[0])
        first, semi, rest = n.children
        return node(STATEMENT, n.span, [statement(first), token(semi), sequence(rest)])

    def statement(n: ParseNode) -> VisNode:
        inner = n.children[0]
        c = inner.children
        if inner.symbol == "assign":
            kids = [leaf(VARIABLE, c[0]), token(c[1]), expression(c[2])]
        elif inner.symbol == "if_stmt":
            kids = [
                token(c[0]),
                condition(c[1]),
                token(c[2]),
                statement(c[3]),
                token(c[4]),
                statement(c[5]),
            ]
        elif inner.symbol == "while_stmt":
            kids = [token(c[0]), condition(c[1]), token(c[2]), statement(c[3])]
        elif inner.symbol == "block":
            kids = [token(c[0]), sequence(c[1]), token(c[2])]
        else:  # skip
            kids = [token(c[0])]
        return node(STATEMENT, inner.span, kids)

    def expression(n: ParseNode) -> VisNode:
        c = n.children
        if n.symbol in ("expr", "term"):
            if len(c) == 1:
                return expression(c[0])
            return node(EXPRESSION, n.span, [expression(c[0]), token(c[1]), expression(c[2])])
        # factor
        first = c[0]
        if first.symbol == "NUMBER":
            return node(EXPRESSION, n.span, [leaf(NUMBER, first)])
        if first.symbol == "MINUS":  # від'ємне число: <число> -> -5
            number = VisNode(ids.next(), NUMBER, NUMBER, "rule", n.span)
            text = "-" + (c[1].text or "")
            number.children = [VisNode(ids.next(), text, text, "token", n.span)]
            return node(EXPRESSION, n.span, [number])
        if first.symbol == "VAR":
            return node(EXPRESSION, n.span, [leaf(VARIABLE, first)])
        return node(EXPRESSION, n.span, [token(c[0]), expression(c[1]), token(c[2])])

    def condition(n: ParseNode) -> VisNode:
        c = n.children
        if n.symbol == "cond":
            if len(c) == 1:
                return condition(c[0])
            return node(CONDITION, n.span, [condition(c[0]), token(c[1]), condition(c[2])])
        if n.symbol == "bneg":
            if len(c) == 1:
                return condition(c[0])
            return node(CONDITION, n.span, [token(c[0]), condition(c[1])])
        # batom
        if c[0].symbol == "LPAR":
            return node(CONDITION, n.span, [token(c[0]), condition(c[1]), token(c[2])])
        return node(CONDITION, n.span, [expression(c[0]), token(c[1]), expression(c[2])])

    root = program(tree)
    # вузли створювались знизу вгору; нумеруємо зверху вниз, як в AST
    for index, vis in enumerate(root.walk()):
        vis.id = f"{prefix}{index}"
    return root


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
