"""CORE-01: граматика приймає коректні програми та відхиляє некоректні."""

import pytest
from conftest import INVALID, VALID

from sipl import SiplSyntaxError, check, grammar_text, parse


def test_enough_examples():
    assert len(VALID) >= 10
    assert len(INVALID) >= 10


@pytest.mark.parametrize("path", VALID, ids=lambda p: p.stem)
def test_valid_program_is_accepted(path):
    assert check(path.read_text(encoding="utf-8")) == []


@pytest.mark.parametrize("path", INVALID, ids=lambda p: p.stem)
def test_invalid_program_is_rejected(path):
    source = path.read_text(encoding="utf-8")
    diagnostics = check(source)
    assert len(diagnostics) == 1
    assert diagnostics[0].kind == "syntax"
    with pytest.raises(SiplSyntaxError):
        parse(source)


def test_grammar_covers_every_bnf_construct():
    text = grammar_text()
    for rule in ("program", "seq", "assign", "if_stmt", "while_stmt", "block", "skip"):
        assert f"\n{rule}:" in text
    for rule in ("expr", "term", "factor", "cond", "bneg", "batom"):
        assert f"\n{rule}:" in text


@pytest.mark.parametrize(
    "source",
    [
        "begin beginx := 1 end",  # ключове слово як префікс імені
        "begin X_1 := 0 end",
        "begin\tX:=1;Y:=2\nend",  # пробіли необов'язкові
        "begin skip end // коментар у кінці",
    ],
)
def test_lexical_details(source):
    assert check(source) == []
