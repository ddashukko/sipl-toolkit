"""CORE-02: типізоване AST, позиції та діагностика синтаксичних помилок."""

import re

import pytest

from sipl import ParseNode, SiplSyntaxError, ast, build_ast, check, parse, parse_tree


def body(source: str) -> ast.Stmt:
    return parse(f"begin {source} end").body


def test_parser_returns_own_ast_nodes(power_source):
    program = parse(power_source)
    assert isinstance(program, ast.Program)
    assert isinstance(program.body, ast.Seq)
    assert isinstance(program.body.first, ast.Assign)
    loop = program.body.second
    assert isinstance(loop, ast.While)
    assert isinstance(loop.cond, ast.Compare) and loop.cond.op == ">"
    assert isinstance(loop.body, ast.Block)


def test_parse_tree_is_own_model(power_source):
    tree = parse_tree(power_source)
    assert isinstance(tree, ParseNode)
    assert tree.symbol == "program"
    leaves = [leaf.text for leaf in tree.leaves()]
    # листки дерева = лексеми програми зліва направо
    assert leaves == re.findall(r":=|[A-Za-z]+|\d+|[;>*-]", power_source)
    assert build_ast(tree) == parse(power_source)


def test_multiplication_binds_tighter_than_addition():
    stmt = body("X := 1 + 2 * 3")
    assert isinstance(stmt, ast.Assign)
    value = stmt.value
    assert isinstance(value, ast.BinOp) and value.op == "+"
    assert isinstance(value.right, ast.BinOp) and value.right.op == "*"


def test_subtraction_is_left_associative():
    stmt = body("X := 10 - 4 - 3")
    assert isinstance(stmt, ast.Assign)
    value = stmt.value
    assert isinstance(value, ast.BinOp) and isinstance(value.left, ast.BinOp)
    assert isinstance(value.right, ast.Num) and value.right.value == 3


def test_parentheses_change_structure_but_leave_no_node():
    stmt = body("X := (1 + 2) * 3")
    assert isinstance(stmt, ast.Assign)
    value = stmt.value
    assert isinstance(value, ast.BinOp) and value.op == "*"
    assert isinstance(value.left, ast.BinOp) and value.left.op == "+"


def test_negative_literal():
    stmt = body("X := -5")
    assert isinstance(stmt, ast.Assign)
    assert stmt.value == ast.Num(-5, stmt.value.span)


def test_not_binds_tighter_than_or():
    stmt = body("if not X = 1 or Y > 2 then skip else skip")
    assert isinstance(stmt, ast.If)
    assert isinstance(stmt.cond, ast.Or)
    assert isinstance(stmt.cond.left, ast.Not)
    assert isinstance(stmt.cond.right, ast.Compare)


def test_unicode_and_ascii_operators_give_equal_ast():
    ascii_form = parse("begin if not (X > 0) or X = 1 then skip else skip end")
    unicode_form = parse("begin if ¬ (X > 0) ∨ X = 1 then skip else skip end")
    assert ascii_form == unicode_form


def test_while_binds_tighter_than_sequence():
    stmt = body("while X > 0 do X := X - 1; Y := 1")
    assert isinstance(stmt, ast.Seq)
    assert isinstance(stmt.first, ast.While)
    assert isinstance(stmt.second, ast.Assign)


def test_sequence_is_left_nested():
    stmt = body("A := 1; B := 2; C := 3")
    assert isinstance(stmt, ast.Seq) and isinstance(stmt.first, ast.Seq)
    assert isinstance(stmt.second, ast.Assign) and stmt.second.target.name == "C"


def test_spans_point_into_source(power_source):
    program = parse(power_source)
    assert isinstance(program.body, ast.Seq)
    loop = program.body.second
    assert isinstance(loop, ast.While)
    assert (loop.span.start_line, loop.span.start_column) == (3, 3)
    assert loop.cond.span.text(power_source) == "Y > 0"
    assert loop.span.text(power_source).startswith("while Y > 0 do")
    assert program.span.text(power_source) == power_source.strip()


def test_equality_ignores_spans():
    assert parse("begin X := 1 end") == parse("begin\n\n   X   :=   1\nend")
    assert parse("begin X := 1 end") != parse("begin X := 2 end")


def test_to_dict_with_and_without_spans():
    program = parse("begin X := 1 end")
    with_spans = ast.to_dict(program)
    assert with_spans["type"] == "Program"
    assert with_spans["span"]["start"] == {"line": 1, "column": 1, "offset": 0}
    assert ast.to_dict(program, spans=False) == {
        "type": "Program",
        "body": {
            "type": "Assign",
            "target": {"type": "Var", "name": "X"},
            "value": {"type": "Num", "value": 1},
        },
    }


def test_long_program_does_not_hit_recursion_limit():
    source = "begin " + "; ".join(f"X{i} := {i}" for i in range(400)) + " end"
    assert check(source) == []
    assert isinstance(parse(source).body, ast.Seq)


# ---------- діагностика ----------


def diagnose(source: str):
    with pytest.raises(SiplSyntaxError) as info:
        parse(source)
    return info.value.diagnostic


@pytest.mark.parametrize(
    ("source", "code", "line", "column", "hint_part"),
    [
        ("begin\n  X := 1;\nend", "E002", 3, 1, "розділяє"),
        ("begin\n  if X > 0 then Y := 1\nend", "E002", 3, 1, "else"),
        ("begin X = 1 end", "E002", 1, 9, ":="),
        ("begin X := Y < 2 end", "E001", 1, 14, "'=' та '>'"),
        ("begin X := 6 / 2 end", "E001", 1, 14, "'+', '-' та '*'"),
        ("begin X := 1 & 2 end", "E001", 1, 14, "or"),
        ("begin X : 1 end", "E001", 1, 9, ":="),
        ("X := 1", "E002", 1, 1, "begin"),
        ("begin end", "E002", 1, 7, "skip"),
        ("begin skip end end", "E002", 1, 16, "після завершального"),
        ("begin X := 1", "E003", 1, 13, "end"),
        ("", "E003", 1, 1, "begin"),
        ("begin X := do end", "E002", 1, 12, "ключове слово"),
        ("begin X 1 end", "E002", 1, 9, ":="),
    ],
)
def test_diagnostic_position_and_hint(source, code, line, column, hint_part):
    d = diagnose(source)
    assert d.code == code
    assert (d.span.start_line, d.span.start_column) == (line, column)
    assert d.hint is not None and hint_part in d.hint


def test_expected_list_is_complete():
    # після "1 + 2" парсер може прийняти і '*', хоча LALR уже згорнув вираз
    d = diagnose("begin X := (1 + 2 end")
    for token in ("')'", "'*'", "'+'", "'-'"):
        assert token in d.message


def test_diagnostic_format_shows_source_line_and_caret():
    source = "begin\n  X = 1\nend"
    text = diagnose(source).format(source, "demo.sipl")
    lines = text.splitlines()
    assert lines[0].startswith("demo.sipl:2:5: error[E002]:")
    assert lines[1].endswith("X = 1")
    assert lines[2].index("^") == lines[1].index("=")
    assert "підказка" in lines[3]


def test_diagnostic_to_dict():
    data = diagnose("begin X = 1 end").to_dict()
    assert data["code"] == "E002" and data["kind"] == "syntax" and data["severity"] == "error"
    assert data["span"]["start"]["column"] == 9
