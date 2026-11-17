"""Типізоване AST мови SIPL та позиції у вихідному тексті (SourceSpan)."""

from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass
from typing import Any, Union


@dataclass(frozen=True)
class SourceSpan:
    """Фрагмент вихідного тексту.

    Рядки й колонки рахуються з 1, кінець не включається.
    Зміщення (offset) рахуються з 0 у символах Unicode.
    """

    start_line: int
    start_column: int
    end_line: int
    end_column: int
    start_offset: int
    end_offset: int

    def text(self, source: str) -> str:
        return source[self.start_offset : self.end_offset]

    def to_dict(self) -> dict[str, Any]:
        return {
            "start": {
                "line": self.start_line,
                "column": self.start_column,
                "offset": self.start_offset,
            },
            "end": {
                "line": self.end_line,
                "column": self.end_column,
                "offset": self.end_offset,
            },
        }

    @staticmethod
    def cover(first: SourceSpan, last: SourceSpan) -> SourceSpan:
        """Найменший фрагмент, що охоплює обидва."""
        return SourceSpan(
            first.start_line,
            first.start_column,
            last.end_line,
            last.end_column,
            first.start_offset,
            last.end_offset,
        )

    def __str__(self) -> str:
        return f"{self.start_line}:{self.start_column}-{self.end_line}:{self.end_column}"


def _span() -> Any:
    # span не бере участі в порівнянні: два AST рівні, якщо рівна їхня структура
    return field(compare=False)


# ---------- арифметичні вирази ----------


@dataclass(frozen=True)
class Num:
    value: int
    span: SourceSpan = _span()


@dataclass(frozen=True)
class Var:
    name: str
    span: SourceSpan = _span()


@dataclass(frozen=True)
class BinOp:
    op: str  # '+', '-', '*'
    left: Expr
    right: Expr
    span: SourceSpan = _span()


Expr = Union[Num, Var, BinOp]

# ---------- умови ----------


@dataclass(frozen=True)
class Compare:
    op: str  # '=', '>'
    left: Expr
    right: Expr
    span: SourceSpan = _span()


@dataclass(frozen=True)
class Or:
    left: Cond
    right: Cond
    span: SourceSpan = _span()


@dataclass(frozen=True)
class Not:
    operand: Cond
    span: SourceSpan = _span()


Cond = Union[Compare, Or, Not]

# ---------- оператори ----------


@dataclass(frozen=True)
class Assign:
    target: Var
    value: Expr
    span: SourceSpan = _span()


@dataclass(frozen=True)
class Seq:
    first: Stmt
    second: Stmt
    span: SourceSpan = _span()


@dataclass(frozen=True)
class If:
    cond: Cond
    then_branch: Stmt
    else_branch: Stmt
    span: SourceSpan = _span()


@dataclass(frozen=True)
class While:
    cond: Cond
    body: Stmt
    span: SourceSpan = _span()


@dataclass(frozen=True)
class Block:
    body: Stmt
    span: SourceSpan = _span()


@dataclass(frozen=True)
class Skip:
    span: SourceSpan = _span()


Stmt = Union[Assign, Seq, If, While, Block, Skip]


@dataclass(frozen=True)
class Program:
    body: Stmt
    span: SourceSpan = _span()


Node = Union[Program, Assign, Seq, If, While, Block, Skip, Compare, Or, Not, Num, Var, BinOp]


def children(node: Node) -> list[tuple[str, Node]]:
    """Дочірні вузли у порядку полів: [(назва_поля, вузол), ...]."""
    result: list[tuple[str, Node]] = []
    for f in fields(node):
        value = getattr(node, f.name)
        if is_dataclass(value) and not isinstance(value, SourceSpan):
            result.append((f.name, value))  # type: ignore[arg-type]
    return result


def to_dict(node: Node, *, spans: bool = True) -> dict[str, Any]:
    """AST як JSON-сумісний словник. spans=False прибирає позиції."""
    out: dict[str, Any] = {"type": type(node).__name__}
    for f in fields(node):
        value = getattr(node, f.name)
        if isinstance(value, SourceSpan):
            if spans:
                out[f.name] = value.to_dict()
        elif is_dataclass(value):
            out[f.name] = to_dict(value, spans=spans)  # type: ignore[arg-type]
        else:
            out[f.name] = value
    return out
