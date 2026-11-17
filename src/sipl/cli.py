"""Командний рядок SIPL: parse, check, run, trace, tree, compare.

Коди завершення (стабільні):
  0 — успіх
  1 — синтаксична помилка в програмі
  2 — неправильний виклик або файл не читається
  3 — помилка виконання (наприклад, змінна без значення)
  4 — перевищено ліміт кроків
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from . import __version__, ast
from .diagnostics import Diagnostic, SiplSyntaxError
from .interpreter import DEFAULT_MAX_STEPS, Event, Interpreter
from .interpreter.events import (
    BeforeStatement,
    ConditionEvaluated,
    Finished,
    VariableChanged,
)
from .parser import build_ast, parse_tree
from .visualization import (
    from_ast,
    from_parse_tree,
    to_compare_html,
    to_dot,
    to_json_dict,
    to_svg,
    to_text,
)

SCHEMA_VERSION = 1

EXIT_OK = 0
EXIT_SYNTAX = 1
EXIT_USAGE = 2
EXIT_RUNTIME = 3
EXIT_STEP_LIMIT = 4

_STATUS_EXIT = {"ok": EXIT_OK, "runtime_error": EXIT_RUNTIME, "step_limit": EXIT_STEP_LIMIT}


# ---------- допоміжне ----------


def _state_arg(text: str) -> dict[str, int]:
    """'X=2' або 'X=2,Y=-3' -> {'X': 2, 'Y': -3}."""
    result: dict[str, int] = {}
    for item in text.split(","):
        name, sep, value = item.partition("=")
        name = name.strip()
        try:
            if not sep or not name.isidentifier():
                raise ValueError
            result[name] = int(value)
        except ValueError:
            raise argparse.ArgumentTypeError(
                f"очікується ЗМІННА=ЦІЛЕ (наприклад X=5), отримано {item!r}"
            ) from None
    return result


def _initial_state(args: argparse.Namespace) -> dict[str, int]:
    state: dict[str, int] = {}
    for part in args.set or []:
        state.update(part)
    return state


def _envelope(
    command: str, ok: bool, diagnostics: list[Diagnostic], **payload: Any
) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "command": command,
        "ok": ok,
        "diagnostics": [d.to_dict() for d in diagnostics],
        **payload,
    }


def _print_json(data: dict[str, Any]) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


def _format_state(state: dict[str, int]) -> str:
    if not state:
        return "{}"
    return "{" + ", ".join(f"{k} = {v}" for k, v in sorted(state.items())) + "}"


def _write(text: str, output: str | None) -> None:
    if output:
        Path(output).write_text(text, encoding="utf-8")
        print(f"Записано: {output}", file=sys.stderr)
    else:
        sys.stdout.write(text if text.endswith("\n") else text + "\n")


class _Input:
    def __init__(self, path: str) -> None:
        self.name = "<stdin>" if path == "-" else path
        self.source = sys.stdin.read() if path == "-" else Path(path).read_text(encoding="utf-8")


def _syntax_failure(command: str, inp: _Input, diag: Diagnostic, as_json: bool) -> int:
    if as_json:
        _print_json(_envelope(command, False, [diag]))
    else:
        print(diag.format(inp.source, inp.name), file=sys.stderr)
    return EXIT_SYNTAX


# ---------- команди ----------


def _cmd_parse(args: argparse.Namespace, inp: _Input) -> int:
    try:
        program = build_ast(parse_tree(inp.source))
    except SiplSyntaxError as exc:
        return _syntax_failure("parse", inp, exc.diagnostic, args.json)
    if args.json:
        _print_json(_envelope("parse", True, [], ast=ast.to_dict(program)))
    else:
        print(to_text(from_ast(program)))
    return EXIT_OK


def _cmd_check(args: argparse.Namespace, inp: _Input) -> int:
    try:
        parse_tree(inp.source)
    except SiplSyntaxError as exc:
        return _syntax_failure("check", inp, exc.diagnostic, args.json)
    if args.json:
        _print_json(_envelope("check", True, []))
    else:
        print(f"{inp.name}: синтаксично коректна програма SIPL")
    return EXIT_OK


def _excerpt(inp: _Input, event: Any) -> str:
    text = " ".join(event.span.text(inp.source).split())
    return text if len(text) <= 48 else text[:45] + "..."


def _trace_line(inp: _Input, event: Event) -> str | None:
    if isinstance(event, BeforeStatement):
        if event.statement == "Block":
            return None
        where = f"{event.span.start_line}:{event.span.start_column}"
        return f"[{event.step:>4}] {where:<6} {event.statement:<7} {_excerpt(inp, event)}"
    if isinstance(event, VariableChanged):
        old = "⊥" if event.old is None else str(event.old)
        return f"{'':>14}{event.name}: {old} → {event.new}"
    if isinstance(event, ConditionEvaluated):
        value = "true" if event.value else "false"
        return f"{'':>14}умова {_excerpt(inp, event)} → {value}"
    return None


def _cmd_execute(args: argparse.Namespace, inp: _Input) -> int:
    command = args.command
    try:
        program = build_ast(parse_tree(inp.source))
    except SiplSyntaxError as exc:
        return _syntax_failure(command, inp, exc.diagnostic, args.json)

    initial = _initial_state(args)
    interpreter = Interpreter(program, initial, max_steps=args.max_steps)
    events: list[Event] = []
    for event in interpreter.events():
        events.append(event)
        if command == "trace" and not args.json:
            line = _trace_line(inp, event)
            if line:
                print(line)
    final = events[-1]
    assert isinstance(final, Finished)
    diagnostics = [final.diagnostic] if final.diagnostic else []

    if args.json:
        payload: dict[str, Any] = {
            "status": final.status,
            "steps": final.steps,
            "initial_state": dict(sorted(initial.items())),
            "final_state": dict(sorted(final.state.items())),
        }
        if command == "trace":
            payload["events"] = [e.to_dict() for e in events]
        _print_json(_envelope(command, final.status == "ok", diagnostics, **payload))
    else:
        if final.diagnostic:
            print(final.diagnostic.format(inp.source, inp.name), file=sys.stderr)
        label = "Кінцевий стан" if final.status == "ok" else "Стан на момент зупинки"
        print(f"{label}: {_format_state(final.state)}")
        print(f"Кроків: {final.steps}")
    return _STATUS_EXIT[final.status]


def _cmd_tree(args: argparse.Namespace, inp: _Input) -> int:
    try:
        tree = parse_tree(inp.source)
    except SiplSyntaxError as exc:
        return _syntax_failure("tree", inp, exc.diagnostic, args.format == "json")
    root = from_parse_tree(tree) if args.kind == "parse" else from_ast(build_ast(tree))
    if args.format == "text":
        text = to_text(root)
    elif args.format == "json":
        data = _envelope("tree", True, [], kind=args.kind, tree=to_json_dict(root, inp.source))
        text = json.dumps(data, ensure_ascii=False, indent=2)
    elif args.format == "dot":
        text = to_dot(root, inp.source, name="ParseTree" if args.kind == "parse" else "AST")
    else:
        text = to_svg(root, inp.source)
    _write(text, args.output)
    return EXIT_OK


def _cmd_compare(args: argparse.Namespace, inp: _Input) -> int:
    try:
        tree = parse_tree(inp.source)
    except SiplSyntaxError as exc:
        return _syntax_failure("compare", inp, exc.diagnostic, False)
    page = to_compare_html(
        from_parse_tree(tree), from_ast(build_ast(tree)), inp.source, Path(inp.name).name
    )
    _write(page, args.output)
    return EXIT_OK


# ---------- розбір аргументів ----------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sipl", description="Інструменти для мови SIPL")
    parser.add_argument("--version", action="version", version=f"sipl {__version__}")
    sub = parser.add_subparsers(dest="command", required=True, metavar="КОМАНДА")

    def add(name: str, help_text: str, handler: Any) -> argparse.ArgumentParser:
        p = sub.add_parser(name, help=help_text, description=help_text)
        p.add_argument("file", help="файл .sipl або '-' для stdin")
        p.set_defaults(handler=handler)
        return p

    def add_json(p: argparse.ArgumentParser) -> None:
        p.add_argument("--json", action="store_true", help="структурований JSON-вивід")

    def add_run_options(p: argparse.ArgumentParser) -> None:
        p.add_argument(
            "-s",
            "--set",
            action="append",
            type=_state_arg,
            metavar="X=N",
            help="початкове значення змінної; можна повторювати або писати X=1,Y=2",
        )
        p.add_argument(
            "--max-steps",
            type=int,
            default=DEFAULT_MAX_STEPS,
            metavar="N",
            help=f"ліміт кроків виконання (типово {DEFAULT_MAX_STEPS})",
        )

    add_json(add("parse", "Розібрати програму та показати AST", _cmd_parse))
    add_json(add("check", "Перевірити синтаксичну коректність", _cmd_check))
    for name, text in (
        ("run", "Виконати програму та показати кінцевий стан"),
        ("trace", "Виконати програму та показати події виконання"),
    ):
        p = add(name, text, _cmd_execute)
        add_run_options(p)
        add_json(p)

    p = add("tree", "Експортувати дерево виводу або AST", _cmd_tree)
    p.add_argument(
        "--kind", choices=["parse", "ast"], default="parse", help="яке дерево (типово parse)"
    )
    p.add_argument(
        "--format",
        choices=["text", "json", "dot", "svg"],
        default="text",
        help="формат (типово text)",
    )
    p.add_argument("-o", "--output", metavar="ФАЙЛ", help="записати у файл замість stdout")

    p = add("compare", "HTML-сторінка порівняння Parse Tree ↔ AST", _cmd_compare)
    p.add_argument("-o", "--output", metavar="ФАЙЛ", help="записати у файл замість stdout")
    return parser


def main(argv: list[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if reconfigure is not None:  # Windows-консоль: не падати на кирилиці та '∨'
            reconfigure(encoding="utf-8", errors="replace")
    # глибоко вкладені програми обходяться рекурсивно
    sys.setrecursionlimit(max(sys.getrecursionlimit(), 20_000))

    args = _build_parser().parse_args(argv)
    try:
        inp = _Input(args.file)
    except (OSError, UnicodeDecodeError) as exc:
        print(f"sipl: не вдалося прочитати {args.file!r}: {exc}", file=sys.stderr)
        return EXIT_USAGE
    result: int = args.handler(args, inp)
    return result


if __name__ == "__main__":
    sys.exit(main())
