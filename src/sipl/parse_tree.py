"""Дерево синтаксичного виводу (конкретний синтаксис) — власна модель, не залежна від Lark."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .ast import SourceSpan


@dataclass(frozen=True)
class ParseNode:
    """Вузол дерева виводу: нетермінал (з дітьми) або термінал (з текстом лексеми)."""

    symbol: str
    span: SourceSpan
    children: tuple[ParseNode, ...] = ()
    text: str | None = None

    @property
    def is_terminal(self) -> bool:
        return self.text is not None

    def leaves(self) -> list[ParseNode]:
        if self.is_terminal:
            return [self]
        result: list[ParseNode] = []
        for child in self.children:
            result.extend(child.leaves())
        return result

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"symbol": self.symbol, "span": self.span.to_dict()}
        if self.is_terminal:
            out["text"] = self.text
        else:
            out["children"] = [c.to_dict() for c in self.children]
        return out
