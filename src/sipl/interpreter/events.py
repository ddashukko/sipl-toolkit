"""Подієва модель виконання SIPL.

Інтерпретатор не друкує нічого сам: він видає потік подій.
З них будуються trace, CLI-вивід, а також можуть будуватися debugger і visualizer.
"""

from __future__ import annotations

from dataclasses import dataclass, fields
from typing import Any, ClassVar, Union

from ..ast import SourceSpan
from ..diagnostics import Diagnostic

State = dict[str, int]


class _Event:
    kind: ClassVar[str]

    def to_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {"event": self.kind}
        for f in fields(self):  # type: ignore[arg-type]
            value = getattr(self, f.name)
            if isinstance(value, (SourceSpan, Diagnostic)):
                value = value.to_dict()
            elif isinstance(value, dict):
                value = dict(sorted(value.items()))
            out[f.name] = value
        return out


@dataclass(frozen=True)
class BeforeStatement(_Event):
    """Оператор ось-ось почне виконуватись."""

    kind: ClassVar[str] = "before_statement"
    step: int
    statement: str
    span: SourceSpan


@dataclass(frozen=True)
class AfterStatement(_Event):
    """Оператор завершився; state — знімок стану після нього."""

    kind: ClassVar[str] = "after_statement"
    step: int
    statement: str
    span: SourceSpan
    state: State


@dataclass(frozen=True)
class VariableChanged(_Event):
    """Присвоювання: old = None, якщо змінна ще не мала значення."""

    kind: ClassVar[str] = "variable_changed"
    step: int
    name: str
    old: int | None
    new: int
    span: SourceSpan


@dataclass(frozen=True)
class ConditionEvaluated(_Event):
    """Обчислено умову if або while."""

    kind: ClassVar[str] = "condition_evaluated"
    step: int
    statement: str  # 'If' або 'While'
    value: bool
    span: SourceSpan


@dataclass(frozen=True)
class Finished(_Event):
    """Остання подія: status = 'ok' | 'runtime_error' | 'step_limit'."""

    kind: ClassVar[str] = "finished"
    status: str
    steps: int
    state: State
    diagnostic: Diagnostic | None = None


Event = Union[BeforeStatement, AfterStatement, VariableChanged, ConditionEvaluated, Finished]
