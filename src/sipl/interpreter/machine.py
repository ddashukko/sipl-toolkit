"""Інтерпретатор SIPL: обхід AST зі станом змінних і лімітом кроків."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field

from .. import ast
from ..ast import SourceSpan
from ..diagnostics import STEP_LIMIT, UNDEFINED_VARIABLE, Diagnostic, SiplRuntimeError
from .events import (
    AfterStatement,
    BeforeStatement,
    ConditionEvaluated,
    Event,
    Finished,
    State,
    VariableChanged,
)

DEFAULT_MAX_STEPS = 10_000


class _StepLimitReached(Exception):
    def __init__(self, span: SourceSpan) -> None:
        self.span = span


@dataclass
class ExecutionResult:
    status: str  # 'ok' | 'runtime_error' | 'step_limit'
    state: State
    steps: int
    diagnostic: Diagnostic | None = None
    events: list[Event] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status == "ok"


class Interpreter:
    """Виконує програму покроково.

    Крок — це одне присвоювання, один skip або одна перевірка умови.
    Після max_steps кроків виконання зупиняється зі статусом 'step_limit':
    так контролюються нескінченні цикли.
    """

    def __init__(
        self,
        program: ast.Program,
        state: Mapping[str, int] | None = None,
        *,
        max_steps: int = DEFAULT_MAX_STEPS,
    ) -> None:
        self.program = program
        self.state: State = dict(state or {})
        self.max_steps = max_steps
        self.steps = 0

    # ----- публічний API -----

    def events(self) -> Iterator[Event]:
        """Ліниво видає події виконання; остання подія завжди Finished."""
        status = "ok"
        diagnostic: Diagnostic | None = None
        try:
            yield from self._exec(self.program.body)
        except SiplRuntimeError as exc:
            status, diagnostic = "runtime_error", exc.diagnostic
        except _StepLimitReached as exc:
            status = "step_limit"
            diagnostic = Diagnostic(
                STEP_LIMIT,
                f"Перевищено ліміт кроків ({self.max_steps}); можливо, цикл нескінченний",
                exc.span,
                "збільшити ліміт можна параметром --max-steps",
            )
        yield Finished(status, self.steps, dict(self.state), diagnostic)

    def run(self, *, collect_events: bool = False) -> ExecutionResult:
        collected: list[Event] = []
        last: Event | None = None
        for event in self.events():
            last = event
            if collect_events:
                collected.append(event)
        assert isinstance(last, Finished)
        return ExecutionResult(last.status, last.state, last.steps, last.diagnostic, collected)

    # ----- оператори -----

    def _tick(self, span: SourceSpan) -> None:
        if self.steps >= self.max_steps:
            raise _StepLimitReached(span)
        self.steps += 1

    def _exec(self, stmt: ast.Stmt) -> Iterator[Event]:
        if isinstance(stmt, ast.Seq):
            # S1 ; S2 — виконуємо зліва направо; вкладені Seq розгортаємо без рекурсії
            pending: list[ast.Stmt] = [stmt]
            while pending:
                cur = pending.pop()
                if isinstance(cur, ast.Seq):
                    pending.append(cur.second)
                    pending.append(cur.first)
                else:
                    yield from self._exec(cur)
            return

        name = type(stmt).__name__
        yield BeforeStatement(self.steps, name, stmt.span)

        if isinstance(stmt, ast.Assign):
            self._tick(stmt.span)
            value = self._eval(stmt.value)
            old = self.state.get(stmt.target.name)
            self.state[stmt.target.name] = value
            yield VariableChanged(self.steps, stmt.target.name, old, value, stmt.span)
        elif isinstance(stmt, ast.Skip):
            self._tick(stmt.span)
        elif isinstance(stmt, ast.Block):
            yield from self._exec(stmt.body)
        elif isinstance(stmt, ast.If):
            self._tick(stmt.cond.span)
            holds = self._test(stmt.cond)
            yield ConditionEvaluated(self.steps, name, holds, stmt.cond.span)
            yield from self._exec(stmt.then_branch if holds else stmt.else_branch)
        else:
            assert isinstance(stmt, ast.While)
            while True:
                self._tick(stmt.cond.span)
                holds = self._test(stmt.cond)
                yield ConditionEvaluated(self.steps, name, holds, stmt.cond.span)
                if not holds:
                    break
                yield from self._exec(stmt.body)

        yield AfterStatement(self.steps, name, stmt.span, dict(self.state))

    # ----- вирази та умови -----

    def _eval(self, expr: ast.Expr) -> int:
        if isinstance(expr, ast.Num):
            return expr.value
        if isinstance(expr, ast.Var):
            if expr.name not in self.state:
                raise SiplRuntimeError(
                    Diagnostic(
                        UNDEFINED_VARIABLE,
                        f"Змінна {expr.name!r} не має значення в поточному стані",
                        expr.span,
                        f"задайте початкове значення: -s {expr.name}=<число>",
                    )
                )
            return self.state[expr.name]
        left, right = self._eval(expr.left), self._eval(expr.right)
        if expr.op == "+":
            return left + right
        if expr.op == "-":
            return left - right
        assert expr.op == "*"
        return left * right

    def _test(self, cond: ast.Cond) -> bool:
        if isinstance(cond, ast.Compare):
            left, right = self._eval(cond.left), self._eval(cond.right)
            return left == right if cond.op == "=" else left > right
        if isinstance(cond, ast.Not):
            return not self._test(cond.operand)
        # обидва операнди обчислюються завжди: невизначеність не «ховається» за істинним лівим
        left_holds, right_holds = self._test(cond.left), self._test(cond.right)
        return left_holds or right_holds


def run(
    program: ast.Program,
    state: Mapping[str, int] | None = None,
    *,
    max_steps: int = DEFAULT_MAX_STEPS,
    collect_events: bool = False,
) -> ExecutionResult:
    """Виконати програму на заданому початковому стані."""
    return Interpreter(program, state, max_steps=max_steps).run(collect_events=collect_events)


def trace(
    program: ast.Program,
    state: Mapping[str, int] | None = None,
    *,
    max_steps: int = DEFAULT_MAX_STEPS,
) -> list[Event]:
    """Повний список подій виконання."""
    return list(Interpreter(program, state, max_steps=max_steps).events())
