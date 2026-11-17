"""CORE-03 та CORE-04: виконання, ліміт кроків, події."""

import pytest
from conftest import VALID

from sipl import Interpreter, parse, run, trace
from sipl.interpreter import (
    AfterStatement,
    BeforeStatement,
    ConditionEvaluated,
    Finished,
    VariableChanged,
)


def final(source: str, **state: int) -> dict[str, int]:
    result = run(parse(source), state)
    assert result.ok, result.diagnostic
    return result.state


@pytest.mark.parametrize(
    ("x", "y", "expected"), [(2, 10, 1024), (3, 4, 81), (5, 0, 1), (0, 3, 0), (-2, 3, -8)]
)
def test_power(power_source, x, y, expected):
    assert final(power_source, X=x, Y=y)["R"] == expected


def test_assignment_and_arithmetic():
    state = final("begin A := 2 + 3 * 4; B := (2 + 3) * 4; C := 10 - 4 - 3; D := A * -1 end")
    assert state == {"A": 14, "B": 20, "C": 3, "D": -14}


def test_big_integers_do_not_overflow(power_source):
    assert final(power_source, X=2, Y=200)["R"] == 2**200


@pytest.mark.parametrize(("x", "expected"), [(5, 1), (0, 2), (-3, 2)])
def test_if_selects_branch(x, expected):
    assert final("begin if X > 0 then R := 1 else R := 2 end", X=x)["R"] == expected


@pytest.mark.parametrize(("x", "y", "expected"), [(1, 1, 1), (1, 0, 1), (0, 1, 1), (0, 0, 0)])
def test_or(x, y, expected):
    assert final("begin if X = 1 or Y = 1 then R := 1 else R := 0 end", X=x, Y=y)["R"] == expected


def test_not():
    assert final("begin if not X = 1 then R := 1 else R := 0 end", X=1)["R"] == 0
    assert final("begin if not X = 1 then R := 1 else R := 0 end", X=2)["R"] == 1


def test_while_with_false_condition_does_nothing():
    assert final("begin while X > 0 do X := X - 1 end", X=0) == {"X": 0}


def test_skip_and_blocks_keep_state():
    assert final("begin skip; begin skip end end", X=7) == {"X": 7}


def test_input_state_is_not_mutated(power_source):
    initial = {"X": 2, "Y": 3}
    run(parse(power_source), initial)
    assert initial == {"X": 2, "Y": 3}


@pytest.mark.parametrize("path", VALID, ids=lambda p: p.stem)
def test_examples_never_crash(path):
    # приклади мають або завершитись, або дати діагностику — але не виняток Python
    result = run(parse(path.read_text(encoding="utf-8")), {}, max_steps=500)
    assert result.status in ("ok", "runtime_error", "step_limit")


# ---------- невизначеність і ліміти ----------


def test_undefined_variable_is_reported_with_span(power_source):
    result = run(parse(power_source), {"X": 2})
    assert result.status == "runtime_error" and not result.ok
    d = result.diagnostic
    assert d is not None and d.code == "E101" and d.kind == "runtime"
    assert d.span.text(power_source) == "Y"
    assert (d.span.start_line, d.span.start_column) == (3, 9)
    assert result.state == {"X": 2, "R": 1}  # стан на момент зупинки


def test_or_is_strict():
    source = "begin if X > 0 or U > 0 then R := 1 else R := 0 end"
    result = run(parse(source), {"X": 1})
    assert result.status == "runtime_error"


def test_infinite_loop_is_stopped_by_step_limit():
    source = "begin while 1 = 1 do X := X + 1 end"
    result = run(parse(source), {"X": 0}, max_steps=100)
    assert result.status == "step_limit"
    assert result.steps == 100
    assert result.diagnostic is not None and result.diagnostic.code == "E102"
    assert result.diagnostic.kind == "step_limit"


def test_step_limit_is_exact():
    program = parse("begin X := 1; Y := 2; Z := 3 end")
    assert run(program, max_steps=3).ok
    assert run(program, max_steps=2).status == "step_limit"


def test_step_count(power_source):
    # 1 присвоювання + (перевірка + 2 присвоювання) * 3 + остання перевірка
    assert run(parse(power_source), {"X": 2, "Y": 3}).steps == 1 + 3 * 3 + 1


# ---------- події ----------


def test_event_sequence_for_assignment():
    events = trace(parse("begin X := 5 end"))
    assert [e.kind for e in events] == [
        "before_statement",
        "variable_changed",
        "after_statement",
        "finished",
    ]
    before, changed, after, finished = events
    assert isinstance(before, BeforeStatement) and before.statement == "Assign"
    assert isinstance(changed, VariableChanged)
    assert (changed.name, changed.old, changed.new) == ("X", None, 5)
    assert isinstance(after, AfterStatement) and after.state == {"X": 5}
    assert isinstance(finished, Finished) and finished.status == "ok"


def test_condition_events(power_source):
    events = trace(parse(power_source), {"X": 2, "Y": 2})
    conditions = [e for e in events if isinstance(e, ConditionEvaluated)]
    assert [c.value for c in conditions] == [True, True, False]
    assert all(c.statement == "While" for c in conditions)
    assert conditions[0].span.text(power_source) == "Y > 0"


def test_before_and_after_are_balanced(power_source):
    events = trace(parse(power_source), {"X": 2, "Y": 3})
    depth = 0
    for event in events:
        if isinstance(event, BeforeStatement):
            depth += 1
        elif isinstance(event, AfterStatement):
            depth -= 1
            assert depth >= 0
    assert depth == 0


def test_variable_changes_replay_to_final_state(power_source):
    events = trace(parse(power_source), {"X": 3, "Y": 4})
    state = {"X": 3, "Y": 4}
    for event in events:
        if isinstance(event, VariableChanged):
            assert state.get(event.name) == event.old
            state[event.name] = event.new
    finished = events[-1]
    assert isinstance(finished, Finished) and finished.state == state


def test_finished_is_always_last_even_on_error(power_source):
    events = trace(parse(power_source), {})
    assert isinstance(events[-1], Finished)
    assert events[-1].status == "runtime_error"
    assert sum(isinstance(e, Finished) for e in events) == 1


def test_events_are_lazy_so_a_debugger_can_pause():
    interpreter = Interpreter(parse("begin X := 1; Y := 2 end"))
    stream = interpreter.events()
    assert isinstance(next(stream), BeforeStatement)
    assert interpreter.state == {}  # присвоювання ще не відбулося
    assert isinstance(next(stream), VariableChanged)
    assert interpreter.state == {"X": 1}  # виконання стоїть між операторами


def test_event_to_dict():
    events = trace(parse("begin if X > 0 then skip else skip end"), {"X": 1})
    data = [e.to_dict() for e in events]
    assert data[1] == {
        "event": "condition_evaluated",
        "step": 1,
        "statement": "If",
        "value": True,
        "span": events[1].span.to_dict(),  # type: ignore[union-attr]
    }
    assert data[-1]["event"] == "finished" and data[-1]["diagnostic"] is None
