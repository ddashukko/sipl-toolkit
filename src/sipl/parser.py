"""Парсер SIPL: текст -> дерево виводу (ParseNode) -> типізоване AST.

Lark використовується лише як LALR-рушій для граматики grammar/sipl.lark.
Назовні виходять тільки власні структури: ParseNode, вузли AST та Diagnostic.
"""

from __future__ import annotations

from functools import lru_cache
from importlib import resources
from typing import Any

from lark import Lark, Token, Tree
from lark.exceptions import UnexpectedCharacters, UnexpectedInput, UnexpectedToken

from . import ast
from .ast import SourceSpan
from .diagnostics import (
    UNEXPECTED_CHARACTER,
    UNEXPECTED_END,
    UNEXPECTED_TOKEN,
    Diagnostic,
    SiplSyntaxError,
)
from .parse_tree import ParseNode

_TOKEN_NAMES = {
    "BEGIN": "'begin'",
    "END": "'end'",
    "IF": "'if'",
    "THEN": "'then'",
    "ELSE": "'else'",
    "WHILE": "'while'",
    "DO": "'do'",
    "SKIP": "'skip'",
    "OR": "'or'",
    "OR_SYM": "'or'",
    "NOT": "'not'",
    "NOT_SYM": "'not'",
    "ASSIGN": "':='",
    "SEMI": "';'",
    "PLUS": "'+'",
    "MINUS": "'-'",
    "STAR": "'*'",
    "EQ": "'='",
    "GT": "'>'",
    "LPAR": "'('",
    "RPAR": "')'",
    "VAR": "змінна",
    "NUMBER": "число",
    "$END": "кінець програми",
}


def grammar_text() -> str:
    """Текст граматики SIPL у форматі Lark."""
    return resources.files("sipl").joinpath("grammar/sipl.lark").read_text(encoding="utf-8")


@lru_cache(maxsize=1)
def _lark() -> Lark:
    return Lark(
        grammar_text(),
        parser="lalr",
        lexer="basic",  # ключові слова — завжди ключові слова, незалежно від контексту
        start="program",
        propagate_positions=True,
        keep_all_tokens=True,
        maybe_placeholders=False,
    )


# ---------- текст -> дерево виводу ----------


def parse_tree(source: str) -> ParseNode:
    """Побудувати дерево синтаксичного виводу. Кидає SiplSyntaxError."""
    try:
        tree = _lark().parse(source)
    except UnexpectedInput as exc:
        raise SiplSyntaxError(_diagnose(exc, source)) from None
    return _convert(tree)


def _convert(item: Any) -> ParseNode:
    if isinstance(item, Token):
        return ParseNode(item.type, _token_span(item), (), str(item))
    assert isinstance(item, Tree)
    m = item.meta
    span = SourceSpan(m.line, m.column, m.end_line, m.end_column, m.start_pos, m.end_pos)
    return ParseNode(str(item.data), span, tuple(_convert(c) for c in item.children))


def _token_span(tok: Token) -> SourceSpan:
    assert tok.line is not None and tok.column is not None
    assert tok.end_line is not None and tok.end_column is not None
    assert tok.start_pos is not None and tok.end_pos is not None
    return SourceSpan(
        tok.line, tok.column, tok.end_line, tok.end_column, tok.start_pos, tok.end_pos
    )


# ---------- дерево виводу -> AST ----------


def build_ast(tree: ParseNode) -> ast.Program:
    """Згорнути дерево виводу в абстрактне синтаксичне дерево."""
    assert tree.symbol == "program"
    return ast.Program(_seq(tree.children[1]), tree.span)


def _seq(node: ParseNode) -> ast.Stmt:
    # seq: stmt | seq SEMI stmt — розгортаємо ліву рекурсію циклом
    items: list[ParseNode] = []
    cur = node
    while len(cur.children) == 3:
        items.append(cur.children[2])
        cur = cur.children[0]
    items.append(cur.children[0])
    items.reverse()
    result = _stmt(items[0])
    for item in items[1:]:
        nxt = _stmt(item)
        result = ast.Seq(result, nxt, SourceSpan.cover(result.span, nxt.span))
    return result


def _stmt(node: ParseNode) -> ast.Stmt:
    inner = node.children[0]
    c = inner.children
    if inner.symbol == "assign":
        target = ast.Var(c[0].text or "", c[0].span)
        return ast.Assign(target, _expr(c[2]), inner.span)
    if inner.symbol == "if_stmt":
        return ast.If(_cond(c[1]), _stmt(c[3]), _stmt(c[5]), inner.span)
    if inner.symbol == "while_stmt":
        return ast.While(_cond(c[1]), _stmt(c[3]), inner.span)
    if inner.symbol == "block":
        return ast.Block(_seq(c[1]), inner.span)
    assert inner.symbol == "skip"
    return ast.Skip(inner.span)


def _expr(node: ParseNode) -> ast.Expr:
    c = node.children
    if node.symbol in ("expr", "term"):
        if len(c) == 1:
            return _expr(c[0])
        return ast.BinOp(c[1].text or "", _expr(c[0]), _expr(c[2]), node.span)
    assert node.symbol == "factor"
    first = c[0]
    if first.symbol == "NUMBER":
        return ast.Num(int(first.text or "0"), node.span)
    if first.symbol == "MINUS":
        return ast.Num(-int(c[1].text or "0"), node.span)
    if first.symbol == "VAR":
        return ast.Var(first.text or "", node.span)
    return _expr(c[1])  # ( expr ) — дужки в AST не зберігаються


def _cond(node: ParseNode) -> ast.Cond:
    c = node.children
    if node.symbol == "cond":
        if len(c) == 1:
            return _cond(c[0])
        return ast.Or(_cond(c[0]), _cond(c[2]), node.span)
    if node.symbol == "bneg":
        if len(c) == 1:
            return _cond(c[0])
        return ast.Not(_cond(c[1]), node.span)
    assert node.symbol == "batom"
    if c[0].symbol == "LPAR":
        return _cond(c[1])
    return ast.Compare(c[1].text or "", _expr(c[0]), _expr(c[2]), node.span)


# ---------- публічні точки входу ----------


def parse(source: str) -> ast.Program:
    """Розібрати програму SIPL в AST. Кидає SiplSyntaxError."""
    return build_ast(parse_tree(source))


def check(source: str) -> list[Diagnostic]:
    """Перевірити синтаксис. Порожній список = програма коректна."""
    try:
        parse_tree(source)
    except SiplSyntaxError as exc:
        return [exc.diagnostic]
    return []


# ---------- діагностика синтаксичних помилок ----------


def _end_span(source: str) -> SourceSpan:
    # позиція одразу після останнього значущого символу
    text = source.rstrip()
    line = text.count("\n") + 1
    column = len(text) - (text.rfind("\n") + 1) + 1
    return SourceSpan(line, column, line, column, len(text), len(text))


def _expected(names: set[str]) -> str:
    return ", ".join(sorted({_TOKEN_NAMES.get(n, n) for n in names}))


def _context(source: str, offset: int) -> tuple[set[str], str | None]:
    """Що парсер міг прийняти в точці помилки та яка лексема була перед нею.

    LALR-автомат встигає зробити згортки до того, як помітить помилку, і тоді
    список очікуваного виходить неповним. Тому коректний префікс програється
    заново, і автомат опитується безпосередньо перед помилковою лексемою.
    """
    try:
        interactive = _lark().parse_interactive(source[:offset])
        tokens = list(interactive.exhaust_lexer())
        accepted: set[str] = set(interactive.accepts())  # type: ignore[no-untyped-call]
        return accepted, (tokens[-1].type if tokens else None)
    except UnexpectedInput:  # pragma: no cover - префікс до точки помилки завжди коректний
        return set(), None


def _diagnose(exc: UnexpectedInput, source: str) -> Diagnostic:
    if isinstance(exc, UnexpectedCharacters):
        pos = exc.pos_in_stream or 0
        char = source[pos] if pos < len(source) else ""
        span = SourceSpan(exc.line, exc.column, exc.line, exc.column + 1, pos, pos + 1)
        hint = None
        if char in "<≤≥≠":
            hint = "у базовій SIPL є лише порівняння '=' та '>'"
        elif char in "/%":
            hint = "у базовій SIPL є лише операції '+', '-' та '*'"
        elif char == ":":
            hint = "присвоювання записується як ':='"
        elif char in "&∧":
            hint = "у базовій SIPL є лише логічні операції 'or' (∨) та 'not' (¬)"
        return Diagnostic(UNEXPECTED_CHARACTER, f"Неочікуваний символ {char!r}", span, hint)

    assert isinstance(exc, UnexpectedToken)
    tok = exc.token
    offset = len(source) if tok.type == "$END" else (tok.start_pos or 0)
    accepts, prev = _context(source, offset)
    if not accepts:
        accepts = set(exc.accepts or exc.expected or ())
    wanted = _expected(accepts)

    if tok.type == "$END":
        hint = None
        if not source.strip():
            hint = "програма SIPL має вигляд: begin <оператор> end"
        elif "END" in accepts:
            hint = "схоже, бракує завершального 'end'"
        return Diagnostic(
            UNEXPECTED_END,
            f"Неочікуваний кінець програми; очікувалось: {wanted}",
            _end_span(source),
            hint,
        )

    hint = None
    if accepts == {"BEGIN"}:
        hint = "програма SIPL має вигляд: begin <оператор> end"
    elif accepts == {"$END"}:
        hint = "після завершального 'end' не може бути тексту; ';' потрібен лише між операторами"
    elif tok.type == "END" and prev == "SEMI":
        hint = "';' розділяє оператори, а не завершує їх: приберіть ';' перед 'end'"
    elif tok.type == "END" and prev == "BEGIN":
        hint = "порожній блок не дозволений; використайте 'skip'"
    elif "ELSE" in accepts and tok.type in ("SEMI", "END"):
        hint = "гілка 'else' обов'язкова; для порожньої гілки напишіть 'else skip'"
    elif tok.type == "EQ" and "ASSIGN" in accepts:
        hint = "присвоювання записується як ':=', а '=' — це порівняння"
    elif "ASSIGN" in accepts and len(accepts) == 1:
        hint = "після змінної на початку оператора очікується ':='"
    elif tok.type in _KEYWORDS and "VAR" in accepts:
        hint = f"{str(tok)!r} — ключове слово, його не можна використовувати як змінну"
    return Diagnostic(
        UNEXPECTED_TOKEN,
        f"Неочікувана лексема {str(tok)!r}; очікувалось: {wanted}",
        _token_span(tok),
        hint,
    )


_KEYWORDS = {"BEGIN", "END", "IF", "THEN", "ELSE", "WHILE", "DO", "SKIP", "OR", "NOT"}
