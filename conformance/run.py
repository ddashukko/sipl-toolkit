#!/usr/bin/env python3
"""Conformance suite для SIPL.

Запускає довільну реалізацію SIPL як зовнішню команду та звіряє її JSON-вивід
з очікуваннями у cases/*.json. Скрипт використовує лише стандартну бібліотеку
і нічого не імпортує з пакета sipl. Формат тестів і протокол описані в README.md.

    python conformance/run.py                     # еталонна реалізація: python -m sipl
    python conformance/run.py --impl "my-sipl"    # будь-яка інша реалізація
"""

from __future__ import annotations

import argparse
import json
import os
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent


def strip_spans(value: Any) -> Any:
    """Прибрати позиції з AST: порівнюється лише структура."""
    if isinstance(value, dict):
        return {k: strip_spans(v) for k, v in value.items() if k != "span"}
    if isinstance(value, list):
        return [strip_spans(v) for v in value]
    return value


def call(impl: list[str] | str, args: list[str]) -> dict[str, Any]:
    env = dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONUTF8="1")
    # у Windows команду з --impl передаємо одним рядком, щоб лапки розібрала сама система
    command = f"{impl} {subprocess.list2cmdline(args)}" if isinstance(impl, str) else impl + args
    proc = subprocess.run(command, capture_output=True, encoding="utf-8", env=env, timeout=60)
    try:
        data = json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise RuntimeError(
            f"вивід не є JSON (код {proc.returncode}): {proc.stdout[:200]!r} {proc.stderr[:200]!r}"
        ) from None
    if not isinstance(data, dict):
        raise RuntimeError("очікувався JSON-об'єкт")
    return data


def check_error(expected: dict[str, Any], data: dict[str, Any], problems: list[str]) -> None:
    diagnostics = data.get("diagnostics") or []
    if not diagnostics:
        problems.append("очікувалась діагностика, але список diagnostics порожній")
        return
    first = diagnostics[0]
    if "kind" in expected and first.get("kind") != expected["kind"]:
        problems.append(f"вид помилки: очікувався {expected['kind']}, отримано {first.get('kind')}")
    start = first.get("span", {}).get("start", {})
    for key in ("line", "column"):
        if key in expected and start.get(key) != expected[key]:
            problems.append(
                f"{key} помилки: очікувалось {expected[key]}, отримано {start.get(key)}"
            )


def run_case(impl: list[str] | str, case_path: Path) -> list[str]:
    """Повертає список розбіжностей; порожній список = тест пройдено."""
    case = json.loads(case_path.read_text(encoding="utf-8"))
    expect = case["expect"]
    source = str(case_path.parent / case.get("source", case_path.stem + ".sipl"))
    problems: list[str] = []

    parsed = call(impl, ["parse", "--json", source])
    if expect["syntax"] == "error":
        if parsed.get("ok"):
            problems.append("очікувалась синтаксична помилка, але програму прийнято")
        else:
            check_error(expect.get("error", {}), parsed, problems)
        return problems
    if not parsed.get("ok"):
        return [f"програму відхилено: {parsed.get('diagnostics')}"]
    if "ast" in expect and strip_spans(parsed.get("ast")) != expect["ast"]:
        problems.append("AST не збігається з очікуваним")

    if "status" in expect:
        args = ["run", "--json", source]
        for name, value in case.get("input_state", {}).items():
            args += ["-s", f"{name}={value}"]
        if "max_steps" in case:
            args += ["--max-steps", str(case["max_steps"])]
        result = call(impl, args)
        if result.get("status") != expect["status"]:
            problems.append(
                f"статус: очікувався {expect['status']}, отримано {result.get('status')}"
            )
        if "final_state" in expect and result.get("final_state") != expect["final_state"]:
            problems.append(
                f"кінцевий стан: очікувався {expect['final_state']}, "
                f"отримано {result.get('final_state')}"
            )
        if "error" in expect:
            check_error(expect["error"], result, problems)
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SIPL conformance suite")
    parser.add_argument("--impl", help='команда запуску реалізації (типово: "<python> -m sipl")')
    parser.add_argument("--cases", default=str(HERE / "cases"), help="каталог із тестами")
    parser.add_argument("-v", "--verbose", action="store_true", help="показувати й пройдені тести")
    args = parser.parse_args(argv)

    impl: list[str] | str
    if not args.impl:
        impl = [sys.executable, "-m", "sipl"]
    elif os.name == "nt":
        impl = args.impl
    else:
        impl = shlex.split(args.impl)
    cases = sorted(Path(args.cases).glob("*.json"))
    if not cases:
        print(f"у {args.cases} немає тестів", file=sys.stderr)
        return 2

    failed = 0
    for case_path in cases:
        try:
            problems = run_case(impl, case_path)
        except (RuntimeError, OSError, KeyError, subprocess.TimeoutExpired) as exc:
            problems = [f"не вдалося виконати тест: {exc}"]
        if problems:
            failed += 1
            print(f"FAIL {case_path.stem}")
            for problem in problems:
                print(f"       {problem}")
        elif args.verbose:
            print(f"ok   {case_path.stem}")
    print(f"\nПройдено {len(cases) - failed} з {len(cases)}")
    return 1 if failed else 0


if __name__ == "__main__":
    for _stream in (sys.stdout, sys.stderr):
        if hasattr(_stream, "reconfigure"):
            _stream.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
